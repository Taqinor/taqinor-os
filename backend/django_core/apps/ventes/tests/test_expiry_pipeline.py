"""T7 — expiration des devis à la volée + tableau de bord valeur du pipeline."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.expiry import is_expired
from authentication.models import Company

User = get_user_model()


class TestExpiry(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='exp-co', defaults={'nom': 'Exp Co'})[0]
        self.client_obj = Client.objects.create(company=self.company, nom='C')

    def _devis(self, statut, validite):
        return Devis.objects.create(
            company=self.company, reference=f'D-{statut}-{validite}',
            client=self.client_obj, statut=statut, date_validite=validite,
            taux_tva=Decimal('20'), remise_globale=Decimal('0'))

    def test_pending_past_validity_is_expired(self):
        d = self._devis('envoye', date.today() - timedelta(days=1))
        self.assertTrue(is_expired(d))

    def test_pending_future_validity_not_expired(self):
        d = self._devis('envoye', date.today() + timedelta(days=10))
        self.assertFalse(is_expired(d))

    def test_accepted_never_expired(self):
        d = self._devis('accepte', date.today() - timedelta(days=30))
        self.assertFalse(is_expired(d))

    def test_serializer_exposes_is_expired(self):
        user = User.objects.create_user(
            username='exp_u', password='x', role_legacy='responsable',
            company=self.company)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        self._devis('envoye', date.today() - timedelta(days=2))
        resp = api.get('/api/django/ventes/devis/')
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertTrue(any(r.get('is_expired') for r in rows))


class TestPipelineDashboard(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='pipe-co', defaults={'nom': 'Pipe Co'})[0]
        self.user = User.objects.create_user(
            username='pipe_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_pipeline_groups_by_stage_and_motif(self):
        from apps.stock.models import Produit
        c = Client.objects.create(company=self.company, nom='C')
        produit = Produit.objects.create(
            company=self.company, nom='Kit', sku='PIPE-1',
            prix_vente=Decimal('10000'), quantite_stock=10)
        signed = Lead.objects.create(company=self.company, nom='Gagné', stage='SIGNED')
        d = Devis.objects.create(
            company=self.company, reference='D-WIN', client=c, lead=signed,
            statut='accepte', taux_tva=Decimal('20'), remise_globale=Decimal('0'))
        LigneDevis.objects.create(
            devis=d, produit=produit, designation='Kit', quantite=Decimal('1'),
            prix_unitaire=Decimal('10000'), remise=Decimal('0'))
        Lead.objects.create(company=self.company, nom='Perdu', stage='QUOTE_SENT',
                            perdu=True, motif_perte='Prix')
        resp = self.api.get('/api/django/reporting/pipeline/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('par_etape', resp.data)
        self.assertIn('prevision_ponderee', resp.data)
        self.assertEqual(resp.data['gagnes']['count'], 1)
        motifs = {m['motif']: m for m in resp.data['perdus_par_motif']}
        self.assertIn('Prix', motifs)
        self.assertEqual(motifs['Prix']['count'], 1)
