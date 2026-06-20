"""Feature B — RIB/paiement/CGV sur la FACTURE.

Vérifie, via le vrai chemin de rendu (``_render_html`` + ``_company_context``),
que les blocs « Instructions de paiement » et « Conditions générales » ne
s'affichent QUE si renseignés dans le profil entreprise — sinon le PDF reste
identique. Aucun MinIO requis (logo non posé)."""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Facture, LigneFacture
from apps.ventes.utils.pdf import _company_context, _render_html


class TestFactureBlocks(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Bloc Co', slug='bloc-co')
        self.profile = CompanyProfile.get(company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            telephone='+212600000000')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-BLK',
            prix_vente=Decimal('5000'), tva=Decimal('20.00'))
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-BLK-1',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))

    def _render(self):
        ctx = _company_context(company=self.company)
        ctx['facture'] = self.facture
        return _render_html('facture.html', ctx)

    def test_empty_settings_hide_blocks(self):
        html = self._render()
        self.assertNotIn('Instructions de paiement', html)
        self.assertNotIn('Conditions générales', html)

    def test_payment_block_renders_when_set(self):
        self.profile.instructions_paiement = 'Acompte 30% à la commande'
        self.profile.save()
        html = self._render()
        self.assertIn('Instructions de paiement', html)
        self.assertIn('Acompte 30% à la commande', html)
        self.assertNotIn('Conditions générales', html)

    def test_cgv_block_renders_when_set(self):
        self.profile.conditions_generales = 'Garantie 10 ans onduleur.'
        self.profile.save()
        html = self._render()
        self.assertIn('Conditions générales', html)
        self.assertIn('Garantie 10 ans onduleur.', html)
