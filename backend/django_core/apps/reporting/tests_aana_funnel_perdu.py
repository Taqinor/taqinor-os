"""AANA21 (C-AANA-021, D-AANA-1) — un lead ``perdu=True`` n'est JAMAIS
compté gagné, même à l'étape SIGNED, et UN seul taux de gain (gagnés ÷ leads
non perdus) est servi par le funnel, le rapport planifié, les cohortes, le
tableau commercial, le classement et le gain/perte par source.

Scénario R7 : un commercial porte 3 leads du mois — SIGNED perdu, NEW,
SIGNED (avec devis accepté). Avant le correctif : rapport ventes SIGNED=2,
pipeline 1 ; cohorte 66,7 %, classement 33,3 %, tableau commercial 50 %.

Données RÉELLES en base (aucun mock). Retirer l'exclusion d'un site rougit.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.reporting.scheduled_reports import render_sales
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company
from core.dates import aujourd_hui_local

User = get_user_model()

BASE = '/api/django/reporting'


class TestSignePerduExclu(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana21-co', defaults={'nom': 'AANA21 Co'})[0]
        self.admin = User.objects.create_user(
            username='aana21_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.owner = User.objects.create_user(
            username='aana21_comm', password='x', role_legacy='responsable',
            company=self.company)
        Lead.objects.create(
            company=self.company, nom='Perdu signé', stage=stages.SIGNED,
            perdu=True, owner=self.owner)
        Lead.objects.create(
            company=self.company, nom='Nouveau', stage=stages.NEW,
            owner=self.owner)
        gagne = Lead.objects.create(
            company=self.company, nom='Gagné', stage=stages.SIGNED,
            owner=self.owner)
        client = Client.objects.create(company=self.company, nom='Cli R7')
        produit = Produit.objects.create(
            company=self.company, nom='Kit', sku='AANA21-P',
            prix_vente=Decimal('1000'), quantite_stock=0)
        devis = Devis.objects.create(
            company=self.company, reference='DEV-AANA21', client=client,
            lead=gagne, statut=Devis.Statut.ACCEPTE,
            date_acceptation=date.today())
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))

    def test_signe_perdu_exclu_partout(self):
        # Rapport ventes : funnel SIGNED = 1 (le perdu exclu), gagnés = 1.
        resp = self.api.get(f'{BASE}/reports/sales/?compare=prev')
        self.assertEqual(resp.status_code, 200)
        funnel = {f['stage']: f['count'] for f in resp.data['funnel']}
        self.assertEqual(funnel[stages.SIGNED], 1)
        resp_row = next(r for r in resp.data['par_responsable']
                        if r['owner__username'] == 'aana21_comm')
        self.assertEqual(resp_row['gagnes'], 1)
        self.assertEqual(
            resp.data['comparison']['leads_signes']['current'], 1.0)

        # Rapport planifié « funnel » : même compte.
        _entetes, lignes = render_sales(SimpleNamespace(company=self.company))
        par_etape = dict(lignes)
        self.assertEqual(par_etape[stages.STAGE_LABELS[stages.SIGNED]], 1)

        # Pipeline : 1 gagné.
        resp = self.api.get(f'{BASE}/pipeline/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['gagnes']['count'], 1)

        # Tableau commercial : funnel SIGNED=1, taux de gain 1/2 = 50 %.
        resp = self.api.get(f'{BASE}/commercial/dashboard/')
        self.assertEqual(resp.status_code, 200)
        funnel = {f['stage']: f['count'] for f in resp.data['funnel']}
        self.assertEqual(funnel[stages.SIGNED], 1)
        self.assertEqual(resp.data['total_signes'], 1)
        taux = resp.data['win_rate_pct']
        self.assertEqual(taux, 50.0)
        # Classement du tableau commercial : LE même taux.
        self.assertEqual(resp.data['leaderboard'][0]['win_rate_pct'], taux)

        # Classement (export) : LE même taux.
        resp = self.api.get(f'{BASE}/insights/sales-leaderboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['rows'][0]['win_rate_pct'], taux)

        # Cohortes : 1 signé, LE même taux.
        resp = self.api.get(f'{BASE}/insights/cohorts/')
        self.assertEqual(resp.status_code, 200)
        cle = aujourd_hui_local().strftime('%Y-%m')
        cohorte = next(c for c in resp.data['cohorts'] if c['cohorte'] == cle)
        self.assertEqual(cohorte['nb_leads'], 3)
        self.assertEqual(cohorte['nb_signes'], 1)
        self.assertEqual(cohorte['taux_signature'], taux)

        # Gain/perte par source : 1 gagné, le perdu compté perdu.
        resp = self.api.get(f'{BASE}/commercial/win-loss-by-source/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['summary']['nb_won'], 1)
        self.assertEqual(resp.data['summary']['nb_lost'], 1)
