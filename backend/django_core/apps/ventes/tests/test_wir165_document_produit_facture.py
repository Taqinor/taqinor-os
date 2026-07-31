"""WIR165 — Premier émetteur RÉEL de `core.events.document_produit`.

Le signal (``core/events.py``) n'avait aucun producteur hors tests
(``apps/ged/tests/test_zged6_routage_documentaire.py`` fabrique ses propres
fichiers) : ``apps/ged/receivers.py`` était dormant en production. WIR165
branche ``generate_facture_pdf`` (``apps/ventes/utils/pdf.py``) comme premier
émetteur réel (``source='ventes_facture'``), juste après le stockage du PDF.

Couvre :
  * SANS ``RoutageDocumentaire`` configuré pour ``ventes_facture`` : no-op
    strict — la génération de PDF (legacy) est byte-identique à avant (le
    critère « comportement inchangé sans réglage » de ZGED6) ;
  * AVEC un ``RoutageDocumentaire`` actif pour ``ventes_facture`` : le PDF
    généré est effectivement ROUTÉ dans le dossier GED configuré, avec ses
    tags par défaut — le critère DONE du plan (« un flux réel déclenche le
    signal et une règle RoutageDocumentaire de test route le fichier ») ;
  * idempotence : régénérer le PDF de la MÊME facture ne duplique jamais le
    document GED (même patron que les autres sources ZGED6) ;
  * émission best-effort : un récepteur qui échoue ne casse jamais la
    génération du PDF (déjà réussie, le vrai travail de cette fonction).

Run :
    python manage.py test apps.ventes.tests.test_wir165_document_produit_facture -v2
"""
import itertools
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.ged.models import Cabinet, Document, DocumentTag, RoutageDocumentaire
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture

User = get_user_model()


# Compteur de tenants : une société NEUVE à chaque appel sans slug.
_company_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    """Une société neuve par appel — passer ``slug`` pour la nommer.

    Sans compteur, ce helper faisait un ``get_or_create`` sur un slug
    FIXE ('wir165-co') : deux appels rendaient la MÊME société, et un
    test cross-tenant écrivant ``other = make_company()`` ne testait rien.
    """
    from authentication.models import Company
    n = next(_company_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'wir165-co-{n}',
        defaults={'nom': nom or f'WIR165 Co {n}'})
    return company


def make_user(company):
    return User.objects.create_user(
        username='wir165_user', password='x', role_legacy='responsable',
        company=company)


def make_client():
    return Client.objects.create(
        nom='Dupont', prenom='Jean', email='wir165-jean@example.invalid',
        telephone='0600000000', adresse='12 rue de la Paix, Paris')


def make_produit():
    return Produit.objects.create(
        nom='Produit WIR165', sku='WIR165-001',
        prix_vente=Decimal('100.00'), prix_achat=Decimal('60.00'),
        quantite_stock=50)


def make_facture(user, client, produit, reference='FAC-WIR165-0001'):
    facture = Facture.objects.create(
        reference=reference, client=client, statut='emise',
        taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
        created_by=user, company=user.company)
    LigneFacture.objects.create(
        facture=facture, produit=produit, designation='Produit WIR165',
        quantite=Decimal('2'), prix_unitaire=Decimal('100.00'),
        remise=Decimal('0'))
    return facture


class DocumentProduitFactureTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client()
        self.produit = make_produit()

    def tearDown(self):
        User.objects.filter(username='wir165_user').delete()

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_sans_routage_comportement_inchange(self, mock_dl, mock_upload):
        """ZGED6 — sans RoutageDocumentaire pour 'ventes_facture', no-op
        strict : aucun document GED créé, le PDF legacy est généré comme
        avant (même clé, même sauvegarde)."""
        from apps.ventes.utils.pdf import generate_facture_pdf
        facture = make_facture(self.user, self.client_obj, self.produit)

        key = generate_facture_pdf(facture.id)

        self.assertEqual(key, f'factures/{facture.reference}.pdf')
        mock_upload.assert_called_once()
        facture.refresh_from_db()
        self.assertEqual(facture.fichier_pdf, key)
        self.assertEqual(Document.objects.filter(company=self.company).count(), 0)

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_avec_routage_le_pdf_est_route_dans_la_ged(self, mock_dl, mock_upload):
        """DONE — un flux réel (génération PDF facture) déclenche
        document_produit, et une règle RoutageDocumentaire de test route
        effectivement le fichier dans le bon dossier avec ses tags."""
        from apps.ventes.utils.pdf import generate_facture_pdf

        cabinet = Cabinet.objects.create(company=self.company, nom='Ventes')
        tag = DocumentTag.objects.create(
            company=self.company, nom='Facture', slug='facture')
        routage = RoutageDocumentaire.objects.create(
            company=self.company, source='ventes_facture',
            cabinet_cible=cabinet, dossier_cible='Factures/{{ annee }}')
        routage.tags_defaut.add(tag)

        facture = make_facture(self.user, self.client_obj, self.produit)
        key = generate_facture_pdf(facture.id)

        self.assertEqual(key, f'factures/{facture.reference}.pdf')
        documents = Document.objects.filter(company=self.company)
        self.assertEqual(documents.count(), 1)
        document = documents.first()
        self.assertEqual(document.folder.nom, str(facture.date_emission.year))
        self.assertEqual(document.folder.parent.nom, 'Factures')
        self.assertEqual(document.folder.cabinet_id, cabinet.pk)
        self.assertEqual(document.versions.count(), 1)
        tags = {a.tag.slug for a in document.tag_assignments.select_related('tag')}
        self.assertEqual(tags, {'facture'})
        # Idempotence de la référence — régénérer le PDF de la même facture
        # ne duplique jamais le document GED.
        self.assertEqual(
            document.custom_data.get('routage_reference'), facture.reference)

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_regenerer_le_meme_pdf_ne_duplique_pas_le_document_ged(
            self, mock_dl, mock_upload):
        from apps.ventes.utils.pdf import generate_facture_pdf

        cabinet = Cabinet.objects.create(company=self.company, nom='Ventes')
        RoutageDocumentaire.objects.create(
            company=self.company, source='ventes_facture',
            cabinet_cible=cabinet, dossier_cible='Factures')

        facture = make_facture(self.user, self.client_obj, self.produit)
        generate_facture_pdf(facture.id)
        generate_facture_pdf(facture.id)

        self.assertEqual(Document.objects.filter(company=self.company).count(), 1)

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_echec_du_recepteur_ne_casse_jamais_la_generation_pdf(
            self, mock_dl, mock_upload):
        """Best-effort : une émission qui échoue (ex. panne MinIO côté GED)
        laisse la génération de PDF — déjà réussie — intacte."""
        from apps.ventes.utils.pdf import generate_facture_pdf

        cabinet = Cabinet.objects.create(company=self.company, nom='Ventes')
        RoutageDocumentaire.objects.create(
            company=self.company, source='ventes_facture',
            cabinet_cible=cabinet, dossier_cible='Factures')

        facture = make_facture(self.user, self.client_obj, self.produit)
        with patch(
                'apps.ged.services.router_document_module',
                side_effect=RuntimeError('minio down')):
            key = generate_facture_pdf(facture.id)

        self.assertEqual(key, f'factures/{facture.reference}.pdf')
        facture.refresh_from_db()
        self.assertEqual(facture.fichier_pdf, key)
