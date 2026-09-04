"""AUD306 — le PV de réception (N21) porte enfin une trace de signature.

Défaut : `generate_pv_reception` n'injectait JAMAIS
`chantier.signature_client` / `signataire_nom` / `signe_le`, contrairement à
`generate_bon_livraison` juste à côté (NTMOB16) — le gabarit n'affichait
qu'une mention manuscrite statique. Et comme le PV est régénéré à la volée
depuis l'état LIVE du chantier à chaque `GET`, deux téléchargements pouvaient
diverger sans qu'aucune version « signée » ne soit distinguable.

Rouge d'abord : on rend le PV, on pose la signature, on le rend à nouveau —
avant le correctif les deux rendus sont dépourvus de tout bloc signature.
Après : le second porte le trait, le nom du signataire, l'horodatage PERSISTÉ
`signe_le` et une empreinte stable de l'état signé.

Run :
    docker compose exec django_core python manage.py test \
        apps.documents.tests.test_aud306_pv_reception_signature -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

# Marqueur du bloc signature RENDU (jamais la classe CSS nue : `.signature-
# trace` est aussi déclarée dans la feuille de style du gabarit).
SIGNATURE_IMG = '<img class="signature-trace"'

# Trait de signature capturé par SignaturePad.jsx (data-URL PNG minimale).
TRAIT = (
    'data:image/png;base64,'
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')


def _company():
    return Company.objects.get_or_create(
        slug='aud306-co', defaults={'nom': 'AUD306 Co'})[0]


def _chantier(company, ref='CH-AUD306-01'):
    client = Client.objects.create(
        company=company, nom='Tazi', prenom='Salma',
        telephone='+212600000306', adresse='3 rue Test, Casablanca')
    produit = Produit.objects.create(
        company=company, nom='Panneau 550W', sku=f'PV-{ref}',
        prix_vente=Decimal('1500.00'), prix_achat=Decimal('999.99'),
        quantite_stock=10, marque='JA Solar', garantie='25 ans')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{ref}', client=client,
        statut='accepte', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'))
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Panneau 550W',
        quantite=Decimal('8'), prix_unitaire=Decimal('1500.00'),
        remise=Decimal('0'))
    return Installation.objects.create(
        company=company, reference=ref, client=client, devis=devis,
        puissance_installee_kwc=Decimal('4.40'),
        date_mise_en_service='2026-06-01', date_pose_reelle='2026-05-28',
        site_adresse='3 rue Test', site_ville='Casablanca')


@patch('apps.ventes.utils.pdf._download', return_value=None)
@patch('apps.documents.builders._html_to_pdf')
class PvReceptionSignatureTests(TestCase):
    def setUp(self):
        self.company = _company()

    def _html(self, mock_pdf, chantier):
        from apps.documents import builders
        mock_pdf.return_value = b'%PDF-fake'
        builders.generate_pv_reception(chantier)
        return mock_pdf.call_args[0][0]

    def test_pv_non_signe_garde_la_mention_manuscrite(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-AUD306-NOSIG')

        html = self._html(mock_pdf, chantier)

        self.assertIn('Mention manuscrite', html)
        self.assertNotIn(SIGNATURE_IMG, html)
        self.assertNotIn('Signé le', html)

    def test_signature_posee_entre_deux_rendus_apparait(self, mock_pdf, _dl):
        """LE scénario de la fiche."""
        chantier = _chantier(self.company, 'CH-AUD306-SIG')

        avant = self._html(mock_pdf, chantier)
        self.assertNotIn(SIGNATURE_IMG, avant)

        chantier.signature_client = TRAIT
        chantier.signataire_nom = 'Salma Tazi'
        chantier.signe_le = timezone.now()
        chantier.save(update_fields=[
            'signature_client', 'signataire_nom', 'signe_le'])

        apres = self._html(mock_pdf, chantier)
        self.assertIn(SIGNATURE_IMG, apres)
        self.assertIn(TRAIT, apres)
        self.assertIn('Salma Tazi', apres)
        self.assertIn('Signé le', apres)
        self.assertIn(
            chantier.signe_le.strftime('%d/%m/%Y'), apres)
        # Le bloc CLIENT ne montre plus la mention à remplir (il porte le
        # trait) ; celui de L'INSTALLATEUR la garde — d'où exactement une
        # occurrence restante, contre deux avant signature.
        self.assertEqual(apres.count('Mention manuscrite'), 1)
        self.assertEqual(avant.count('Mention manuscrite'), 2)

    def test_empreinte_stable_entre_deux_telechargements(self, mock_pdf, _dl):
        from apps.documents import builders
        chantier = _chantier(self.company, 'CH-AUD306-EMP')
        chantier.signature_client = TRAIT
        chantier.signataire_nom = 'Salma Tazi'
        chantier.signe_le = timezone.now()
        chantier.save(update_fields=[
            'signature_client', 'signataire_nom', 'signe_le'])

        empreinte = builders.empreinte_signature(chantier)
        premier = self._html(mock_pdf, chantier)
        second = self._html(mock_pdf, chantier)

        self.assertIn(empreinte, premier)
        self.assertIn(empreinte, second)

    def test_empreinte_change_si_letat_signe_change(self, mock_pdf, _dl):
        from apps.documents import builders
        chantier = _chantier(self.company, 'CH-AUD306-DIFF')
        chantier.signature_client = TRAIT
        chantier.signataire_nom = 'Salma Tazi'
        chantier.signe_le = timezone.now()
        chantier.save(update_fields=[
            'signature_client', 'signataire_nom', 'signe_le'])
        initiale = builders.empreinte_signature(chantier)

        chantier.signataire_nom = 'Autre signataire'
        chantier.save(update_fields=['signataire_nom'])

        self.assertNotEqual(builders.empreinte_signature(chantier), initiale)

    def test_pv_signe_ne_fuit_aucun_prix_achat(self, mock_pdf, _dl):
        chantier = _chantier(self.company, 'CH-AUD306-LEAK')
        chantier.signature_client = TRAIT
        chantier.signataire_nom = 'Salma Tazi'
        chantier.signe_le = timezone.now()
        chantier.save(update_fields=[
            'signature_client', 'signataire_nom', 'signe_le'])

        html = self._html(mock_pdf, chantier)

        self.assertNotIn('999.99', html)
        self.assertNotIn('prix_achat', html)
