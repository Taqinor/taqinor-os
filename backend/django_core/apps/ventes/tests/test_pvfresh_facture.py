"""PVFRESH (résidu, fondateur 19/08/2026) — la facture PUBLIQUE ne sert plus
un fichier stocké sans vérifier sa fraîcheur.

``apps/ventes/public_views.py::public_document`` servait la facture avec
``facture.fichier_pdf or generate_facture_pdf(facture.id)`` — un fichier déjà
présent était renvoyé TEL QUEL, sans jamais comparer ses octets aux données
courantes de la facture. Un client pouvait donc tenir un PDF antérieur à une
correction de ligne pendant que l'écran interne affichait déjà les bons
montants — exactement le défaut PVFRESH réparé côté devis (``Devis.
pdf_render_meta`` / ``quote_engine.cle_pdf_a_jour``), non répercuté sur le PDF
facture LÉGATAIRE (règle #4 : les factures gardent leur propre moteur —
seule la petite fonction d'empreinte générique QX8 est réutilisée, jamais un
routage par le moteur devis).

Deux couches :
  (1) unitaire sur ``apps.ventes.utils.pdf.cle_facture_pdf_a_jour`` — le
      contrat de fraîcheur (rendu réel, MinIO mocké, comme ``test_pdf.py``) ;
  (2) routage public — le endpoint appelle bien le chemin fraîcheur, et
      dégrade proprement sur le fichier stocké si le rafraîchissement échoue.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_pvfresh_facture -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, ShareLink

User = get_user_model()


def _company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def _user(company):
    return User.objects.create_user(
        username=f'pvfresh-fac-{company.pk}', password='x',
        role_legacy='responsable', company=company)


def _client_obj(company):
    return Client.objects.create(
        company=company, nom='Client', prenom='PVFRESH',
        email=f'pvfresh-fac-{company.pk}@example.com',
        telephone='+212622000000')


def _produit(company):
    return Produit.objects.create(
        company=company, nom='Produit PVFRESH', sku=f'PVF-{company.pk}',
        prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
        quantite_stock=500)


def _facture(company, client_obj, produit):
    facture = Facture.objects.create(
        company=company, reference=f'FAC-PVFRESH-{company.pk}',
        client=client_obj, statut='emise', created_by=None,
        taux_tva=Decimal('20'), remise_globale=Decimal('0'))
    LigneFacture.objects.create(
        facture=facture, produit=produit, designation='Produit PVFRESH',
        quantite=Decimal('2'), prix_unitaire=Decimal('1000'))
    return facture


# ═════════════════════════════════════════════════════════════════════════════
# (1) Unitaire — cle_facture_pdf_a_jour (rendu réel, MinIO mocké)
# ═════════════════════════════════════════════════════════════════════════════

@tag('pdf')  # rendu WeasyPrint réel — lourd, comme test_pdf.py
class ClePdfAJourFactureTests(TestCase):
    def setUp(self):
        self.company = _company('pvfresh-fac-co')
        self.user = _user(self.company)
        self.client_obj = _client_obj(self.company)
        self.produit = _produit(self.company)
        self.facture = _facture(self.company, self.client_obj, self.produit)

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_premier_appel_rend_et_persiste_empreinte(self, mock_dl, mock_upload):
        """Facture jamais rendue : rend, persiste fichier_pdf ET pdf_render_meta."""
        from apps.ventes.utils.pdf import cle_facture_pdf_a_jour

        key = cle_facture_pdf_a_jour(self.facture)

        self.assertEqual(
            key,
            f'factures/{self.facture.company_id}/'
            f'{self.facture.reference}.pdf')
        mock_upload.assert_called_once()
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.fichier_pdf, key)
        self.assertIsInstance(self.facture.pdf_render_meta, dict)
        self.assertTrue(self.facture.pdf_render_meta.get('empreinte'))

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_appel_repete_sans_changement_ne_re_rend_pas(self, mock_dl, mock_upload):
        """À contenu inchangé, le fichier stocké est réutilisé (0 re-rendu)."""
        from apps.ventes.utils.pdf import cle_facture_pdf_a_jour

        key1 = cle_facture_pdf_a_jour(self.facture)
        self.facture.refresh_from_db()
        self.assertEqual(mock_upload.call_count, 1)

        key2 = cle_facture_pdf_a_jour(self.facture)
        self.assertEqual(key1, key2)
        # AUCUN second rendu : l'empreinte comparée est identique.
        self.assertEqual(mock_upload.call_count, 1)

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_editer_une_ligne_force_le_re_rendu(self, mock_dl, mock_upload):
        """Éditer une ligne (quantité) invalide l'empreinte → re-rendu."""
        from apps.ventes.utils.pdf import cle_facture_pdf_a_jour

        cle_facture_pdf_a_jour(self.facture)
        self.facture.refresh_from_db()
        empreinte_avant = self.facture.pdf_render_meta['empreinte']
        self.assertEqual(mock_upload.call_count, 1)

        ligne = self.facture.lignes.first()
        ligne.quantite = Decimal('5')
        ligne.save(update_fields=['quantite'])

        cle_facture_pdf_a_jour(self.facture)
        self.facture.refresh_from_db()
        self.assertEqual(mock_upload.call_count, 2)
        self.assertNotEqual(self.facture.pdf_render_meta['empreinte'],
                            empreinte_avant)

    @patch('apps.ventes.utils.pdf._upload_pdf')
    @patch('apps.ventes.utils.pdf._download', return_value=None)
    def test_facture_legacy_sans_render_meta_force_le_re_rendu(
            self, mock_dl, mock_upload):
        """Une facture ANTÉRIEURE à PVFRESH (fichier_pdf posé, pdf_render_meta
        NULL) doit re-rendre plutôt que servir un fichier dont on ne sait pas
        de quoi il a été rendu — jamais un fichier périmé servi à l'aveugle."""
        from apps.ventes.utils.pdf import cle_facture_pdf_a_jour

        self.facture.fichier_pdf = (
            f'factures/{self.facture.company_id}/'
            f'{self.facture.reference}.pdf')
        self.facture.pdf_render_meta = None
        self.facture.save(update_fields=['fichier_pdf', 'pdf_render_meta'])

        cle_facture_pdf_a_jour(self.facture)
        mock_upload.assert_called_once()
        self.facture.refresh_from_db()
        self.assertTrue(self.facture.pdf_render_meta.get('empreinte'))


# Rendu WeasyPrint réel, SANS ``@tag('pdf')`` (la CI exclut ce tag) : comme
# test_atot_pdf_chaine_totaux, le contrat VNT42 doit tourner à chaque PR.
@patch('apps.ventes.utils.pdf._upload_pdf')
@patch('apps.ventes.utils.pdf._download', return_value=None)
class EmpreinteBlocsVenteTests(TestCase):
    """VNT42 — l'empreinte PVFRESH d'une facture rattachée à un devis porte
    l'objet de la vente, les garanties, la situation, les prochaines
    échéances et le filigrane : (a) paiement sur la facture SŒUR et (d)
    brouillon → émise ⇒ re-rendu ; (b) révision de la tête et (c)
    ``garantie_mois`` changé ⇒ AUCUN re-rendu de l'émise (instantanés),
    re-rendu du brouillon ; sans changement ⇒ servi tel quel."""

    def setUp(self):
        from apps.ventes.models import Devis, LigneDevis
        self.company = _company('pvfresh-vnt42-co')
        self.client_obj = _client_obj(self.company)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-VNT42-0001',
            client=self.client_obj, statut='accepte',
            taux_tva=Decimal('20.00'))
        for nom, prix, mois in (
                ('Onduleur hybride Deye SUN-8K-SG05LP3', '12500', 120),
                ('Coffret de protection AC/DC', '1500', None)):
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku=f'VNT42-{prix}',
                prix_vente=Decimal(prix), quantite_stock=50,
                garantie_mois=mois)
            LigneDevis.objects.create(
                devis=self.devis, produit=produit, designation=nom,
                quantite=Decimal('1'), prix_unitaire=Decimal(prix),
                remise=Decimal('0'), taux_tva=Decimal('20.00'))

    def _tranche(self, reference, type_facture='acompte', emettre=True):
        from apps.ventes.domain.facturation_ops import emettre_facture
        facture = Facture.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, devis=self.devis,
            statut=Facture.Statut.BROUILLON, type_facture=type_facture,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        if emettre:
            emettre_facture(facture, source='test_vnt42')
        return facture.pk

    def _re_rendu(self, pk, mock_upload):
        from apps.ventes.utils.pdf import cle_facture_pdf_a_jour
        avant = mock_upload.call_count
        cle_facture_pdf_a_jour(Facture.objects.get(pk=pk))
        return mock_upload.call_count > avant

    def test_quatre_cas(self, mock_dl, mock_upload):
        from datetime import date

        from apps.ventes.domain.encaissements import (
            recalculer_statut_paiement)
        from apps.ventes.domain.facturation_ops import emettre_facture
        from apps.ventes.models import LigneDevis, Paiement
        emise = self._tranche('FAC-VNT42-0001')
        soeur = self._tranche('FAC-VNT42-0002', 'intermediaire')
        brouillon = self._tranche('FAC-VNT42-0003', 'solde', emettre=False)
        for pk in (emise, brouillon):
            self.assertTrue(self._re_rendu(pk, mock_upload))
        # Sans changement : servi tel quel.
        self.assertFalse(self._re_rendu(emise, mock_upload))
        self.assertFalse(self._re_rendu(brouillon, mock_upload))
        # (c) garantie du catalogue changée.
        Produit.objects.filter(company=self.company,
                               nom__startswith='Onduleur').update(
            garantie_mois=60)
        self.assertFalse(self._re_rendu(emise, mock_upload))
        self.assertTrue(self._re_rendu(brouillon, mock_upload))
        # (b) révision de la tête (désignation d'une ligne du devis).
        LigneDevis.objects.filter(
            devis=self.devis, designation__startswith='Coffret').update(
            designation='Coffret de protection AC/DC 32 A')
        self.assertFalse(self._re_rendu(emise, mock_upload))
        self.assertTrue(self._re_rendu(brouillon, mock_upload))
        # (a) paiement sur la facture SŒUR : la situation de la vente bouge.
        Paiement.objects.create(
            company=self.company, facture_id=soeur, montant=Decimal('1200'),
            date_paiement=date(2026, 10, 12), mode=Paiement.Mode.VIREMENT)
        recalculer_statut_paiement(Facture.objects.get(pk=soeur))
        self.assertTrue(self._re_rendu(emise, mock_upload))
        # (d) brouillon → émise.
        emettre_facture(Facture.objects.get(pk=brouillon),
                        source='test_vnt42')
        self.assertTrue(self._re_rendu(brouillon, mock_upload))
        self.assertFalse(self._re_rendu(brouillon, mock_upload))


# ═════════════════════════════════════════════════════════════════════════════
# (2) Routage public — le endpoint passe par la fraîcheur, dégrade si besoin
# ═════════════════════════════════════════════════════════════════════════════

class PublicDocumentFactureFraicheurTests(TestCase):
    def setUp(self):
        self.company = _company('pvfresh-fac-pub-co')
        self.user = _user(self.company)
        self.client_obj = _client_obj(self.company)
        self.produit = _produit(self.company)
        self.facture = _facture(self.company, self.client_obj, self.produit)
        self.link = ShareLink.objects.create(
            company=self.company, facture=self.facture)

    @patch('apps.ventes.public_views.download_pdf',
           return_value=b'%PDF-1.4 stub pvfresh-fac')
    @patch('apps.ventes.public_views.cle_facture_pdf_a_jour')
    def test_le_endpoint_public_appelle_le_chemin_fraicheur(
            self, mock_cle, mock_dl):
        """Le lien public n'utilise plus ``fichier_pdf or generate_facture_pdf``
        directement : il passe par ``cle_facture_pdf_a_jour``."""
        mock_cle.return_value = 'factures/FAC-PVFRESH-STUB.pdf'
        resp = APIClient().get(
            f'/api/django/public/document/{self.link.token}/')
        self.assertEqual(resp.status_code, 200)
        mock_cle.assert_called_once_with(self.facture)
        mock_dl.assert_called_once_with('factures/FAC-PVFRESH-STUB.pdf')

    @patch('apps.ventes.public_views.download_pdf',
           return_value=b'%PDF-1.4 stub perime')
    @patch('apps.ventes.public_views.cle_facture_pdf_a_jour')
    def test_degrade_sur_le_fichier_stocke_si_le_rafraichissement_echoue(
            self, mock_cle, mock_dl):
        """Le rafraîchissement échoue (moteur/stockage indisponible) MAIS un
        fichier stocké existe déjà : le lien sert ce fichier plutôt que de
        refuser le téléchargement — il fonctionnait avant PVFRESH, il doit
        continuer de fonctionner."""
        self.facture.fichier_pdf = 'factures/FAC-PVFRESH-PERIME.pdf'
        self.facture.save(update_fields=['fichier_pdf'])
        mock_cle.side_effect = RuntimeError('MinIO indisponible')

        resp = APIClient().get(
            f'/api/django/public/document/{self.link.token}/')
        self.assertEqual(resp.status_code, 200)
        mock_dl.assert_called_once_with('factures/FAC-PVFRESH-PERIME.pdf')

    @patch('apps.ventes.public_views.cle_facture_pdf_a_jour')
    def test_sans_fichier_stocke_lechec_du_rafraichissement_reste_un_404(
            self, mock_cle):
        """Aucun fichier stocké ET le rafraîchissement échoue : rien à servir,
        404 amical (comportement inchangé — jamais une fuite d'erreur brute)."""
        mock_cle.side_effect = RuntimeError('MinIO indisponible')

        resp = APIClient().get(
            f'/api/django/public/document/{self.link.token}/')
        self.assertEqual(resp.status_code, 404)
