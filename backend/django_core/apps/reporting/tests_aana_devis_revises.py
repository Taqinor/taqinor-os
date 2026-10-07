"""AANA19 (C-AANA-019, D-AANA-5) — un devis accepté puis RÉVISÉ en V2
acceptée n'est compté qu'UNE fois comme « signé ».

Scénario R1 : V1 acceptée puis révisée (V1 reste ``accepte`` mais
``is_active=False``, ``superseded_by=V2``), V2 acceptée active. Avant le
correctif : commissions count=2 (base 20 000 pour un devis de 10 000),
``nb_acceptes=2`` au tableau de bord.

Données RÉELLES en base (aucun mock) ; tous les sites passent par le helper
unique ``apps.reporting.pipeline._devis_signes`` — retirer ``is_active=True``
du helper (ou d'un site) rougit ce test.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/reporting'


class TestDevisReviseCompteUneFois(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana19-co', defaults={'nom': 'AANA19 Co'})[0]
        self.admin = User.objects.create_user(
            username='aana19_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.commercial = User.objects.create_user(
            username='aana19_comm', password='x', role_legacy='responsable',
            company=self.company)
        prof = CompanyProfile.get(self.company)
        prof.commission_mode = 'pct_devis'
        prof.commission_valeur = Decimal('5')
        prof.save(update_fields=['commission_mode', 'commission_valeur'])

        client = Client.objects.create(company=self.company, nom='Cli R1')
        lead = Lead.objects.create(
            company=self.company, nom='Lead R1', stage=stages.SIGNED,
            owner=self.commercial)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='AANA19-P',
            prix_vente=Decimal('1000'), quantite_stock=0)
        self.v1 = Devis.objects.create(
            company=self.company, reference='DEV-AANA19-V1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE,
            date_acceptation=date.today())
        LigneDevis.objects.create(
            devis=self.v1, produit=produit, designation='P',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
        self.v2 = Devis.objects.create(
            company=self.company, reference='DEV-AANA19-V2', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE,
            date_acceptation=date.today(), version=2, version_parent=self.v1)
        LigneDevis.objects.create(
            devis=self.v2, produit=produit, designation='P',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
        # État laissé par la révision : V1 acceptée mais remplacée (inactive).
        Devis.objects.filter(pk=self.v1.pk).update(
            is_active=False, superseded_by=self.v2)

    def test_revision_comptee_une_fois(self):
        # Commissions (mode pct_devis 5 %) : 1 devis, base = HT de V2 seul.
        resp = self.api.get(f'{BASE}/insights/commissions/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['rows']), 1)
        row = resp.data['rows'][0]
        self.assertEqual(row['count'], 1)
        self.assertEqual(Decimal(row['base']), Decimal('10000'))
        self.assertEqual(Decimal(row['commission']), Decimal('500'))

        # Tableau de bord : 1 devis accepté.
        resp = self.api.get(f'{BASE}/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['conversion']['nb_acceptes'], 1)

        # Classement (export) et classement du tableau commercial : 1 signé.
        resp = self.api.get(f'{BASE}/insights/sales-leaderboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['rows'][0]['nb_devis_signes'], 1)
        resp = self.api.get(f'{BASE}/commercial/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['leaderboard'][0]['nb_devis_signes'], 1)
        # Vélocité : un seul échantillon.
        self.assertEqual(resp.data['sales_velocity']['sample_count'], 1)

        # Analytics lead→signature : un seul échantillon.
        resp = self.api.get(f'{BASE}/insights/analytics/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['lead_to_signature_count'], 1)

        # Seaux de statut (rapport ventes + pipeline) : 1 accepté.
        resp = self.api.get(f'{BASE}/reports/sales/')
        self.assertEqual(resp.status_code, 200)
        acc = [b for b in resp.data['devis_par_statut']
               if b['statut'] == Devis.Statut.ACCEPTE]
        self.assertEqual(acc[0]['count'], 1)
        resp = self.api.get(f'{BASE}/pipeline/')
        self.assertEqual(resp.status_code, 200)
        acc = [b for b in resp.data['devis_par_statut']
               if b['statut'] == Devis.Statut.ACCEPTE]
        self.assertEqual(acc[0]['count'], 1)
