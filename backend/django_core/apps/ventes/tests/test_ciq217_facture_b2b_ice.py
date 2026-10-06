"""CIQ217 — facture d'un client entreprise : raison sociale, ICE, IF et RC
imprimés, et émission REFUSÉE sans ICE (D-CIQ-11), indépendamment de
l'interrupteur de transmission DGI (qui reste éteint).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq217_facture_b2b_ice"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

ECHEANCIER = [
    {'type': 'acompte', 'pct_or_montant': 40},
    {'type': 'solde', 'pct_or_montant': 60},
]


class _Base(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='ciq217-co', defaults={'nom': 'CIQ217 Co'})[0]
        self.user = User.objects.create_user(
            username='ciq217_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.emises = []
        from core.events import facture_emise
        facture_emise.connect(self._capter, weak=False)
        self.addCleanup(facture_emise.disconnect, self._capter)

    def _capter(self, sender, instance=None, **kwargs):
        self.emises.append(instance.pk)

    def _client(self, nom, **extra):
        from apps.crm.models import Client
        return Client.objects.create(
            company=self.company, nom=nom,
            email=f'{nom.lower().replace(" ", "")}@example.com', **extra)

    def _facture_brouillon(self, client, ref):
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.create(
            company=self.company, reference=ref, client=client,
            statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20.00'),
            created_by=self.user)
        from apps.stock.models import Produit
        produit = Produit.objects.create(
            company=self.company, nom='Kit PV', sku=f'SKU-{ref}',
            prix_vente=Decimal('10000'), quantite_stock=10,
            tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Centrale PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20.00'))
        return facture

    def _html(self, facture):
        from apps.ventes.utils.pdf import _company_context, _render_html
        ctx = _company_context(company=self.company)
        ctx['facture'] = facture
        return _render_html('facture.html', ctx)


class GardeEmissionTest(_Base):
    def test_entreprise_sans_ice_refusee_nommant_client_ice(self):
        from apps.ventes.domain.facturation_ops import (
            EmissionRefusee, emettre_facture,
        )
        client = self._client('Usine Atlas SA', type_client='entreprise')
        facture = self._facture_brouillon(client, 'FAC-CIQ217-0010')
        with self.assertRaises(EmissionRefusee) as ctx:
            emettre_facture(facture, user=self.user, source='test')
        self.assertEqual(ctx.exception.champ, 'client.ice')
        self.assertIn('client.ice', ctx.exception.motif)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, 'brouillon')
        self.assertEqual(self.emises, [])

    def test_ecran_emettre_rend_400(self):
        client = self._client('Usine Rif SA', type_client='entreprise')
        facture = self._facture_brouillon(client, 'FAC-CIQ217-0020')
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/emettre/')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('client.ice', r.data['detail'])
        self.assertEqual(self.emises, [])

    def test_bulk_emettre_meme_garde(self):
        client = self._client('Usine Sous SA', type_client='entreprise')
        facture = self._facture_brouillon(client, 'FAC-CIQ217-0030')
        r = self.api.post('/api/django/ventes/factures/bulk/', {
            'action': 'emettre', 'ids': [facture.id]}, format='json')
        self.assertIn(r.status_code, (200, 207), r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, 'brouillon')
        self.assertEqual(self.emises, [])

    def test_entreprise_avec_ice_emise_et_pdf_montre_identifiants(self):
        from apps.ventes.domain.facturation_ops import emettre_facture
        client = self._client(
            'Usine Draa SA', type_client='entreprise',
            ice='001234567000089', if_fiscal='IF-4455', rc='RC-778')
        facture = self._facture_brouillon(client, 'FAC-CIQ217-0040')
        emettre_facture(facture, user=self.user, source='test')
        facture.refresh_from_db()
        self.assertEqual(facture.statut, 'emise')
        self.assertEqual(self.emises, [facture.pk])
        html = self._html(facture)
        self.assertIn('ICE : 001234567000089', html)
        self.assertIn('IF : IF-4455', html)
        self.assertIn('RC : RC-778', html)
        self.assertIn('Usine Draa SA', html)

    def test_identifiant_vide_omis_sans_tiret(self):
        client = self._client(
            'Usine Ziz SA', type_client='entreprise', ice='001234567000090')
        facture = self._facture_brouillon(client, 'FAC-CIQ217-0050')
        html = self._html(facture)
        self.assertIn('ICE : 001234567000090', html)
        self.assertNotIn('IF :', html)
        self.assertNotIn('RC :', html)

    def test_particulier_sans_ice_emise_comme_hier(self):
        from apps.ventes.domain.facturation_ops import emettre_facture
        client = self._client('Particulier', type_client='particulier')
        facture = self._facture_brouillon(client, 'FAC-CIQ217-0060')
        emettre_facture(facture, user=self.user, source='test')
        facture.refresh_from_db()
        self.assertEqual(facture.statut, 'emise')


class TrancheSansIceTest(_Base):
    def test_tranche_echoue_sans_rien_ecrire(self):
        from apps.ventes.models import Devis, Facture, LigneDevis
        client = self._client('Usine Oum SA', type_client='entreprise')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-CIQ217-0070',
            client=client, statut='accepte', taux_tva=Decimal('20.00'),
            mode_installation='industriel', echeancier=ECHEANCIER)
        LigneDevis.objects.create(
            devis=devis, designation='Centrale PV', quantite=Decimal('1'),
            prix_unitaire=Decimal('50000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('client.ice', r.data['detail'])
        self.assertFalse(Facture.objects.filter(devis=devis).exists())
        self.assertEqual(self.emises, [])
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
