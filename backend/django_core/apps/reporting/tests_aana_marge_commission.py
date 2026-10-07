"""AANA23 (C-AANA-039) — la marge du plan MARGE_INTERNE déduit les remises
de ligne et globale, ne lit que les lignes comptées dans les totaux, et
c'est LA même fonction que job-costing / rentabilité (``_marge_devis``).

Scénario R9 : une ligne produit PU 1000, achat 600, remise ligne 20 %, plan
MARGE_INTERNE 10 %. Avant le correctif : base 400, commission 40 (remise
ignorée) alors que le devis vaut 800 HT.

Données RÉELLES en base (aucun mock). Retirer une remise rougit.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, PlanCommission
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/reporting/insights'


class TestMargeCommission(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana23-co', defaults={'nom': 'AANA23 Co'})[0]
        self.admin = User.objects.create_user(
            username='aana23_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.commercial = User.objects.create_user(
            username='aana23_comm', password='x', role_legacy='responsable',
            company=self.company)
        PlanCommission.objects.create(
            company=self.company, owner=self.commercial,
            base=PlanCommission.Base.MARGE_INTERNE,
            taux_pct=Decimal('10'), actif=True)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli R9')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead R9', stage=stages.SIGNED,
            owner=self.commercial)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='AANA23-P',
            prix_vente=Decimal('1000'), prix_achat=Decimal('600'),
            quantite_stock=0)

    def _devis(self, reference, remise_globale=Decimal('0')):
        return Devis.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.ACCEPTE, date_acceptation=date.today(),
            remise_globale=remise_globale)

    def test_remise_deduite(self):
        devis = self._devis('DEV-AANA23-1')
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('20'))

        resp = self.api.get(f'{BASE}/commissions/')
        self.assertEqual(resp.status_code, 200)
        row = resp.data['rows'][0]
        # (1000 × 0,8) − 600 = 200 ; 10 % = 20.
        self.assertEqual(Decimal(row['base']), Decimal('200'))
        self.assertEqual(Decimal(row['commission']), Decimal('20'))

    def test_remise_globale_et_ligne_optionnelle(self):
        devis = self._devis('DEV-AANA23-2', remise_globale=Decimal('10'))
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        option = Produit.objects.create(
            company=self.company, nom='Monitoring', sku='AANA23-O',
            prix_vente=Decimal('500'), prix_achat=Decimal('100'),
            quantite_stock=0)
        LigneDevis.objects.create(
            devis=devis, produit=option, designation='Monitoring (option)',
            quantite=Decimal('1'), prix_unitaire=Decimal('500'),
            optionnelle=True)
        Installation.objects.create(
            company=self.company, reference='CH-AANA23', client=self.client_obj,
            devis=devis, statut=Installation.Statut.RECEPTIONNE,
            date_reception=date.today())

        resp = self.api.get(f'{BASE}/commissions/')
        self.assertEqual(resp.status_code, 200)
        row = resp.data['rows'][0]
        # CA = 1000 × 0,9 = 900 (option non activée hors totaux) ; coût 600.
        self.assertEqual(Decimal(row['base']), Decimal('300'))
        self.assertEqual(Decimal(row['commission']), Decimal('30'))

        # Job-costing lit LA même fonction : coût = 600 (option exclue).
        resp = self.api.get(f'{BASE}/job-costing/')
        self.assertEqual(resp.status_code, 200)
        chantier = next(c for c in resp.data['chantiers']
                        if c['ref'] == 'CH-AANA23')
        self.assertEqual(Decimal(chantier['cost_estimate']), Decimal('600'))
