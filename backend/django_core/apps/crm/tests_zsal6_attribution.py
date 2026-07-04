"""ZSAL6 — Rapport d'attribution des leads par source + par commercial.

Covers:
  - Agrégation croisée correcte : leads/conversions/CA par commercial ET par
    canal/source sur la période.
  - Filtrage par période (debut/fin).
  - Un commercial sans lead = absent (jamais une fausse ligne à 0 fabriquée
    pour un commercial hors du jeu de leads considéré).
  - Garde division-par-zéro (aucun lead -> 0.0, jamais d'exception).
  - Isolation multi-tenant.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.crm.selectors import attribution_leads
from apps.crm import stages as stage_mod
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def make_company(slug='zsal6-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


def make_devis_signe(company, client, lead, ttc):
    produit = Produit.objects.create(
        company=company, nom='Onduleur', sku=f'SKU-Z6-{lead.id}',
        prix_vente=Decimal('100'), quantite_stock=10, tva=Decimal('20.00'))
    devis = Devis.objects.create(
        company=company, reference=f'DEV-Z6-{lead.id}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'))
    ht = (Decimal(ttc) / Decimal('1.2')).quantize(Decimal('0.01'))
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Onduleur',
        quantite=Decimal('1'), prix_unitaire=ht, taux_tva=Decimal('20.00'))
    return devis


class TestAttributionLeads(TestCase):
    def setUp(self):
        self.company = make_company()
        self.resp1 = User.objects.create_user(
            username='zsal6resp1', password='x', company=self.company)
        self.resp2 = User.objects.create_user(
            username='zsal6resp2', password='x', company=self.company)
        self.client_obj = Client.objects.create(company=self.company, nom='Client Z6')

        # resp1 : 2 leads site_web (1 signé), resp2 : 1 lead meta_ads (signé).
        self.l1 = Lead.objects.create(
            company=self.company, nom='L1', owner=self.resp1,
            canal=Lead.Canal.SITE_WEB, stage=stage_mod.SIGNED)
        self.l2 = Lead.objects.create(
            company=self.company, nom='L2', owner=self.resp1,
            canal=Lead.Canal.SITE_WEB, stage=stage_mod.CONTACTED)
        self.l3 = Lead.objects.create(
            company=self.company, nom='L3', owner=self.resp2,
            canal=Lead.Canal.META_ADS, stage=stage_mod.SIGNED)

        make_devis_signe(self.company, self.client_obj, self.l1, 1200)
        make_devis_signe(self.company, self.client_obj, self.l3, 2400)

    def test_agregation_par_commercial(self):
        rapport = attribution_leads(self.company)
        par_com = {r['commercial']: r for r in rapport['par_commercial']}
        self.assertEqual(par_com['zsal6resp1']['nb_leads'], 2)
        self.assertEqual(par_com['zsal6resp1']['nb_signes'], 1)
        self.assertEqual(par_com['zsal6resp1']['taux_conversion_pct'], 50.0)
        self.assertEqual(Decimal(par_com['zsal6resp1']['ca_signe']), Decimal('1200'))
        self.assertEqual(par_com['zsal6resp2']['nb_leads'], 1)
        self.assertEqual(par_com['zsal6resp2']['nb_signes'], 1)
        self.assertEqual(par_com['zsal6resp2']['taux_conversion_pct'], 100.0)

    def test_agregation_par_source(self):
        rapport = attribution_leads(self.company)
        par_src = {r['canal']: r for r in rapport['par_source']}
        self.assertEqual(par_src['site_web']['nb_leads'], 2)
        self.assertEqual(par_src['site_web']['nb_signes'], 1)
        self.assertEqual(Decimal(par_src['site_web']['ca_signe']), Decimal('1200'))
        self.assertEqual(par_src['meta_ads']['nb_leads'], 1)
        self.assertEqual(par_src['meta_ads']['nb_signes'], 1)

    def test_commercial_sans_lead_absent(self):
        User.objects.create_user(
            username='zsal6resp_sans_lead', password='x', company=self.company)
        rapport = attribution_leads(self.company)
        noms = [r['commercial'] for r in rapport['par_commercial']]
        self.assertNotIn('zsal6resp_sans_lead', noms)

    def test_periode_filtre(self):
        hier = datetime.date.today() - datetime.timedelta(days=1)
        avant_hier = datetime.date.today() - datetime.timedelta(days=2)
        rapport = attribution_leads(self.company, debut=avant_hier, fin=hier)
        self.assertEqual(rapport['par_commercial'], [])
        self.assertEqual(rapport['par_source'], [])

    def test_aucun_lead_pas_de_division_par_zero(self):
        vide = make_company('zsal6-vide')
        rapport = attribution_leads(vide)
        self.assertEqual(rapport, {'par_commercial': [], 'par_source': []})


class TestAttributionAPI(TestCase):
    def setUp(self):
        self.company = make_company('zsal6-api-co')
        self.other = make_company('zsal6-api-other')
        self.user = User.objects.create_user(
            username='zsal6apiuser', password='x', role_legacy='responsable',
            company=self.company)
        Lead.objects.create(
            company=self.company, nom='L', owner=self.user,
            canal=Lead.Canal.SITE_WEB, stage=stage_mod.NEW)
        Lead.objects.create(
            company=self.other, nom='Autre', canal=Lead.Canal.SITE_WEB,
            stage=stage_mod.NEW)
        self.api = APIClient()
        token = AccessToken.for_user(self.user)
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_endpoint_scope_societe(self):
        resp = self.api.get('/api/django/crm/rapports/attribution/')
        self.assertEqual(resp.status_code, 200, resp.content)
        total_leads = sum(r['nb_leads'] for r in resp.data['par_commercial'])
        self.assertEqual(total_leads, 1)
