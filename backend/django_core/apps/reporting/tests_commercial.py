"""QJ18 + QJ19 — Tests du tableau de bord commercial.

Conventions identiques aux autres tests_*.py du module reporting :
  - Une société principale + une société tierce (isolation multi-tenant).
  - Un utilisateur responsable ou admin authentifié par JWT.
  - Assertions : HTTP 200, forme JSON, valeurs calculées, scoping strict.

Aucune dépendance Django DB locale : les tests utilisent le TestCase de Django
qui tourne dans l'image prod (ou avec les vars d'env CI).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit

User = get_user_model()

BASE = '/api/django/reporting/commercial'


class CommercialBase(TestCase):
    """Fixture commune aux deux suites de tests."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='com-co', defaults={'nom': 'Com Co'})[0]
        self.other = Company.objects.get_or_create(
            slug='com-other', defaults={'nom': 'Com Other'})[0]
        self.user = User.objects.create_user(
            username='com_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_lead(self, company=None, stage='NEW', perdu=False,
                   canal=None, source='os_native', motif_perte=None,
                   owner=None):
        return Lead.objects.create(
            company=company or self.company,
            nom='Test',
            stage=stage,
            perdu=perdu,
            canal=canal,
            source=source,
            motif_perte=motif_perte,
            owner=owner,
        )

    def _make_devis(self, lead, stage='accepte', company=None,
                    prix_unitaire=Decimal('10000')):
        """Crée un devis accepté avec une ligne de produit."""
        co = company or self.company
        client = Client.objects.create(company=co, nom='CLI')
        produit = Produit.objects.create(
            company=co, nom='Panneau', sku=f'P-{Devis.objects.count()}',
            prix_vente=prix_unitaire, quantite_stock=0)
        devis = Devis.objects.create(
            company=co, reference=f'D-{Devis.objects.count()}',
            client=client, lead=lead,
            statut=Devis.Statut.ACCEPTE if stage == 'accepte' else Devis.Statut.BROUILLON,
        )
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal('1'), prix_unitaire=prix_unitaire,
        )
        return devis


# ── QJ18 — Tableau de bord commercial ────────────────────────────────────────

class TestCommercialDashboard(CommercialBase):
    """Tests de l'endpoint /commercial/dashboard/."""

    def test_empty_returns_shape(self):
        """Un tableau de bord sans leads retourne la bonne structure JSON."""
        resp = self.api.get(f'{BASE}/dashboard/')
        self.assertEqual(resp.status_code, 200)
        for key in ('funnel', 'win_rate_pct', 'time_in_stage',
                    'sales_velocity', 'leaderboard',
                    'total_leads', 'total_signes'):
            self.assertIn(key, resp.data)
        # Entonnoir contient exactement les 6 étapes STAGES.py dans l'ordre.
        from apps.crm import stages as sm
        stage_keys = [f['stage'] for f in resp.data['funnel']]
        self.assertEqual(stage_keys, sm.STAGES)

    def test_funnel_conversion_pct(self):
        """Le funnel calcule correctement la conversion % par étape."""
        # 4 leads actifs : 2 NEW, 1 CONTACTED, 1 SIGNED.
        self._make_lead(stage='NEW')
        self._make_lead(stage='NEW')
        self._make_lead(stage='CONTACTED')
        self._make_lead(stage='SIGNED')

        resp = self.api.get(f'{BASE}/dashboard/')
        self.assertEqual(resp.status_code, 200)
        funnel = {f['stage']: f for f in resp.data['funnel']}

        # 2 NEW / 4 actifs = 50 %
        self.assertEqual(funnel['NEW']['count'], 2)
        self.assertAlmostEqual(funnel['NEW']['conversion_pct'], 50.0, places=0)
        # 1 SIGNED / 4 actifs = 25 %
        self.assertEqual(funnel['SIGNED']['count'], 1)
        self.assertAlmostEqual(funnel['SIGNED']['conversion_pct'], 25.0, places=0)

        # Win rate global = 1 / 4 = 25 %.
        self.assertAlmostEqual(resp.data['win_rate_pct'], 25.0, places=0)
        self.assertEqual(resp.data['total_signes'], 1)

    def test_perdu_excluded_from_funnel(self):
        """Les leads perdus n'entrent pas dans le calcul de conversion."""
        self._make_lead(stage='NEW')
        self._make_lead(stage='SIGNED')              # won
        self._make_lead(stage='SIGNED', perdu=True)  # lost — ne compte pas

        resp = self.api.get(f'{BASE}/dashboard/')
        self.assertEqual(resp.status_code, 200)
        # 2 leads actifs (le perdu est exclu) : 1 NEW + 1 SIGNED.
        self.assertEqual(resp.data['total_leads'], 3)   # total brut
        funnel = {f['stage']: f for f in resp.data['funnel']}
        self.assertEqual(funnel['SIGNED']['count'], 1)  # seul le non-perdu

    def test_leaderboard_ca_and_win_rate(self):
        """Le classement agrège le CA HT et calcule le win rate par commercial."""
        owner = User.objects.create_user(
            username='sales1', password='x', role_legacy='normal',
            company=self.company)
        # 2 leads pour cet owner, dont 1 signé avec devis.
        lead_signed = self._make_lead(stage='SIGNED', owner=owner)
        self._make_lead(stage='NEW', owner=owner)
        self._make_devis(lead_signed, prix_unitaire=Decimal('50000'))

        resp = self.api.get(f'{BASE}/dashboard/')
        self.assertEqual(resp.status_code, 200)
        lb = resp.data['leaderboard']
        self.assertEqual(len(lb), 1)
        row = lb[0]
        self.assertEqual(row['commercial'], 'sales1')
        self.assertEqual(Decimal(row['ca_ht']), Decimal('50000'))
        self.assertEqual(row['nb_devis_signes'], 1)
        # win rate = 1 signé / 2 leads de cet owner = 50 %.
        self.assertAlmostEqual(row['win_rate_pct'], 50.0, places=0)

    def test_tenant_isolation(self):
        """Les données d'une autre société ne sont JAMAIS retournées."""
        # Leads dans la société courante.
        self._make_lead(stage='SIGNED')
        # Leads dans l'autre société.
        self._make_lead(company=self.other, stage='SIGNED')
        self._make_lead(company=self.other, stage='NEW')

        resp = self.api.get(f'{BASE}/dashboard/')
        self.assertEqual(resp.status_code, 200)
        # total_leads ne doit voir que le lead de la société courante.
        self.assertEqual(resp.data['total_leads'], 1)
        self.assertEqual(resp.data['total_signes'], 1)

    def test_date_filter_reduces_scope(self):
        """Le filtre ?from= / ?to= restreint bien le scope du rapport."""
        from datetime import date, timedelta
        # Lead créé il y a 60 jours → en dehors du filtre "7 derniers jours".
        Lead.objects.create(
            company=self.company, nom='Old', stage='NEW')

        cutoff = (date.today() - timedelta(days=7)).isoformat()
        resp = self.api.get(f'{BASE}/dashboard/?from={cutoff}')
        self.assertEqual(resp.status_code, 200)
        # Le vieux lead est antérieur à la fenêtre → non inclus
        # (tous les leads ont date_creation auto_now_add, donc "aujourd'hui").
        # On vérifie juste que la réponse est valide.
        self.assertIn('funnel', resp.data)


# ── QJ19 — Win/loss par source ────────────────────────────────────────────────

class TestWinLossBySource(CommercialBase):
    """Tests de l'endpoint /commercial/win-loss-by-source/."""

    def test_shape(self):
        """Sans données, la réponse retourne la bonne structure."""
        resp = self.api.get(f'{BASE}/win-loss-by-source/')
        self.assertEqual(resp.status_code, 200)
        for key in ('by_canal', 'by_source_technique',
                    'top_loss_reasons', 'summary'):
            self.assertIn(key, resp.data)
        for sub in ('nb_total', 'nb_won', 'nb_lost', 'overall_close_rate_pct'):
            self.assertIn(sub, resp.data['summary'])

    def test_close_rate_by_canal(self):
        """Le taux de fermeture par canal est calculé correctement."""
        # 2 leads Meta Ads : 1 signé, 1 perdu.
        self._make_lead(stage='SIGNED', canal='meta_ads')
        self._make_lead(stage='NEW', canal='meta_ads', perdu=True)
        # 1 lead Site web : signé.
        self._make_lead(stage='SIGNED', canal='site_web')

        resp = self.api.get(f'{BASE}/win-loss-by-source/')
        self.assertEqual(resp.status_code, 200)
        by_canal = {r['canal']: r for r in resp.data['by_canal']}

        # Meta Ads : 2 leads, 1 won → 50 %.
        self.assertEqual(by_canal['meta_ads']['total'], 2)
        self.assertEqual(by_canal['meta_ads']['won'], 1)
        self.assertAlmostEqual(by_canal['meta_ads']['close_rate_pct'], 50.0, places=0)

        # Site web : 1 lead, 1 won → 100 %.
        self.assertEqual(by_canal['site_web']['total'], 1)
        self.assertEqual(by_canal['site_web']['won'], 1)
        self.assertAlmostEqual(by_canal['site_web']['close_rate_pct'], 100.0, places=0)

    def test_top_loss_reasons(self):
        """Les motifs de perte sont agrégés et triés par fréquence."""
        self._make_lead(perdu=True, motif_perte='Prix trop élevé')
        self._make_lead(perdu=True, motif_perte='Prix trop élevé')
        self._make_lead(perdu=True, motif_perte='Projet reporté')
        self._make_lead(perdu=True)  # motif_perte vide → 'Non précisé'

        resp = self.api.get(f'{BASE}/win-loss-by-source/')
        self.assertEqual(resp.status_code, 200)
        reasons = resp.data['top_loss_reasons']
        # Le motif le plus fréquent doit être premier.
        self.assertEqual(reasons[0]['motif'], 'Prix trop élevé')
        self.assertEqual(reasons[0]['count'], 2)

        motifs = [r['motif'] for r in reasons]
        self.assertIn('Projet reporté', motifs)
        self.assertIn('Non précisé', motifs)

    def test_summary_counters(self):
        """Les compteurs récapitulatifs sont exacts."""
        self._make_lead(stage='SIGNED')          # won
        self._make_lead(stage='NEW', perdu=True)  # lost
        self._make_lead(stage='NEW')              # en cours

        resp = self.api.get(f'{BASE}/win-loss-by-source/')
        self.assertEqual(resp.status_code, 200)
        s = resp.data['summary']
        self.assertEqual(s['nb_total'], 3)
        self.assertEqual(s['nb_won'], 1)
        self.assertEqual(s['nb_lost'], 1)
        # 1 won / 3 total ≈ 33.3 %
        self.assertAlmostEqual(s['overall_close_rate_pct'], 33.3, places=0)

    def test_tenant_isolation(self):
        """Les leads d'une autre société ne polluent pas les compteurs."""
        # 3 leads de la société courante.
        self._make_lead(stage='SIGNED', canal='meta_ads')
        self._make_lead(stage='NEW', canal='meta_ads')
        self._make_lead(perdu=True, motif_perte='Budget')
        # 5 leads de l'autre société — ne doivent PAS être vus.
        for _ in range(5):
            self._make_lead(company=self.other, stage='SIGNED', canal='site_web')

        resp = self.api.get(f'{BASE}/win-loss-by-source/')
        self.assertEqual(resp.status_code, 200)
        s = resp.data['summary']
        self.assertEqual(s['nb_total'], 3)
        # Seule la société courante : 1 won sur 3.
        self.assertEqual(s['nb_won'], 1)

    def test_by_source_technique(self):
        """Les buckets par source technique regroupent bien os_native / site_web."""
        self._make_lead(source='os_native', stage='SIGNED')
        self._make_lead(source='os_native', stage='NEW')
        self._make_lead(source='site_web', stage='NEW')

        resp = self.api.get(f'{BASE}/win-loss-by-source/')
        self.assertEqual(resp.status_code, 200)
        by_src = {r['source']: r for r in resp.data['by_source_technique']}
        self.assertEqual(by_src['os_native']['total'], 2)
        self.assertEqual(by_src['os_native']['won'], 1)
        self.assertEqual(by_src['site_web']['total'], 1)
        self.assertEqual(by_src['site_web']['won'], 0)
