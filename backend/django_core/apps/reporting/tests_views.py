"""Reporting — tableau de bord (dashboard) : agrégats lecture seule.

Couvre le bucketing du CA mensuel : 12 mois calendaires distincts finissant
ce mois (pas de dérive ni de saut/duplication de mois — bug i*30 jours).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.reporting.views import _ca_mensuel
from apps.ventes.models import Facture

User = get_user_model()


class TestCaMensuelBucketing(TestCase):
    """_ca_mensuel doit renvoyer 12 mois calendaires distincts, sans trou."""

    def test_twelve_distinct_calendar_months(self):
        series = _ca_mensuel(Facture.objects.none())
        self.assertEqual(len(series), 12)
        labels = [m['mois'] for m in series]
        # 12 libellés distincts (aucun mois dupliqué/sauté).
        self.assertEqual(len(set(labels)), 12)

    def test_last_bucket_is_current_month(self):
        series = _ca_mensuel(Facture.objects.none())
        mois_labels = {
            '01': 'Jan', '02': 'Fév', '03': 'Mar', '04': 'Avr',
            '05': 'Mai', '06': 'Jun', '07': 'Jul', '08': 'Aoû',
            '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Déc',
        }
        today = date.today()
        expected = f"{mois_labels[today.strftime('%m')]} {today.year}"
        self.assertEqual(series[-1]['mois'], expected)


class TestDashboardEndpoint(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='rep-views-co', defaults={'nom': 'Rep Views Co'})[0]
        self.user = User.objects.create_user(
            username='rep_views_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_dashboard_returns_twelve_months(self):
        resp = self.api.get('/api/django/reporting/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['ca_mensuel']), 12)

    def test_dashboard_xlsx_export(self):
        resp = self.api.get('/api/django/reporting/dashboard/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        body = (b''.join(resp.streaming_content)
                if getattr(resp, 'streaming', False) else resp.content)
        self.assertTrue(body.startswith(b'PK'))


class DemoResumeEtKpiOnboardingTests(TestCase):
    """NTDMO21/31/41/42 — résumé démo servi du cache, KPI internes d'onboarding."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        User = get_user_model()
        self.demo = Company.objects.create(
            slug='ntdmo21-demo', nom='Demo', est_demo=True)
        self.reelle = Company.objects.create(slug='ntdmo21-reelle', nom='Reelle')
        self.u_demo = User.objects.create_user(
            username='ntdmo21_d', password='x', role_legacy='responsable',
            company=self.demo)
        self.u_reelle = User.objects.create_user(
            username='ntdmo21_r', password='x', role_legacy='responsable',
            company=self.reelle)
        self.root = User.objects.create_superuser(
            username='ntdmo41_root', password='x', email='r@x.ma')

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_resume_demo_present_et_phrase(self):
        resp = self._api(self.u_demo).get('/api/django/reporting/demo-resume/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('données de démonstration', resp.data['phrase'])
        self.assertEqual(resp.data['devis_envoyes'], 0)

    def test_resume_jamais_sur_societe_reelle(self):
        resp = self._api(self.u_reelle).get('/api/django/reporting/demo-resume/')
        self.assertEqual(resp.status_code, 404)

    def test_resume_servi_depuis_le_cache(self):
        from unittest import mock
        from apps.reporting import demo_resume
        api = self._api(self.u_demo)
        api.get('/api/django/reporting/demo-resume/')
        with mock.patch.object(
                demo_resume, 'calculer_resume',
                side_effect=AssertionError('agrégation synchrone')):
            resp = api.get('/api/django/reporting/demo-resume/')
        self.assertEqual(resp.status_code, 200)

    def test_precalcul_nocturne_remplit_le_cache_des_societes_demo(self):
        from django.core.cache import cache
        from apps.reporting import demo_resume
        from apps.reporting.tasks import run_recalcul_nocturne_onboarding
        out = run_recalcul_nocturne_onboarding()
        self.assertEqual(out['societes_demo'], 1)
        self.assertTrue(out['kpi_interne'])
        self.assertIsNotNone(cache.get(
            demo_resume.cle_cache(self.demo.id, date.today())))
        self.assertIsNone(cache.get(
            demo_resume.cle_cache(self.reelle.id, date.today())))

    def test_phrase_formate_les_milliers(self):
        from apps.reporting.demo_resume import phrase
        self.assertEqual(
            phrase(12, 5, 45200),
            '12 devis envoyés, 5 chantiers réceptionnés, 45 200 MAD '
            'facturés ce mois — données de démonstration')

    def test_kpi_interne_refuse_aux_tenants(self):
        url = '/api/django/reporting/kpi-onboarding-interne/'
        self.assertEqual(self._api(self.u_reelle).get(url).status_code, 403)
        self.assertEqual(self._api(self.root).get(url).status_code, 200)

    def test_temps_jusqua_valeur_mediane_sur_deux_societes(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.onboarding.models import (
            OnboardingChecklistItem, OnboardingProgress)
        from apps.reporting.onboarding_kpi import temps_jusqua_valeur
        User = get_user_model()
        OnboardingChecklistItem.objects.filter(company__isnull=True).update(
            actif=False)
        item = OnboardingChecklistItem.objects.create(
            company=None, key='ntdmo41-unique', libelle='X', actif=True)
        now = timezone.now()
        for slug, jours in (('ntdmo41-a', 2), ('ntdmo41-b', 6)):
            co = Company.objects.create(slug=slug, nom=slug)
            Company.objects.filter(pk=co.pk).update(
                date_creation=now - timedelta(days=jours))
            u = User.objects.create_user(
                username=slug, password='x', role_legacy='responsable',
                company=co)
            OnboardingProgress.objects.create(
                company=co, user=u, item=item, complete_le=now)
        res = temps_jusqua_valeur()
        self.assertEqual(res['societes_mesurees'], 2)
        self.assertEqual(res['mediane_jours'], 4.0)

    def test_adoption_tours_liste_les_tours_avec_pourcentage(self):
        from django.utils import timezone
        from apps.onboarding.models import ProductTourStep, TourProgress
        from apps.reporting.onboarding_kpi import adoption_tours
        for cle in ('devis', 'leads'):
            ProductTourStep.objects.get_or_create(
                company=None, tour_key=cle, ordre=10,
                defaults={'titre': 't', 'texte': 't', 'ecran_cible': '/x'})
        TourProgress.objects.create(
            company=self.reelle, user=self.u_reelle, tour_key='devis',
            vu_le=timezone.now())
        par_cle = {t['tour_key']: t for t in adoption_tours()}
        self.assertEqual(par_cle['devis']['completion_pct'], 100.0)
        self.assertEqual(par_cle['leads']['completion_pct'], 0.0)


class AdoptionToursIssueTest(TestCase):
    """Follow-up NTDMO42 — termines / fermes_avant_la_fin / sans_issue."""
    setUp = DemoResumeEtKpiOnboardingTests.setUp

    def test_compte_termines_fermes_et_historique(self):
        from django.utils import timezone
        from apps.onboarding.models import ProductTourStep, TourProgress
        from apps.reporting.onboarding_kpi import (
            RAISON_FIN_VS_PASSE, adoption_tours, kpis_onboarding_internes)
        ProductTourStep.objects.get_or_create(
            company=None, tour_key='devis', ordre=10,
            defaults={'titre': 't', 'texte': 't', 'ecran_cible': '/x'})
        TourProgress.objects.create(
            company=self.reelle, user=self.u_reelle, tour_key='devis',
            vu_le=timezone.now(), issue='termine')
        ligne = {t['tour_key']: t for t in adoption_tours()}['devis']
        self.assertEqual(ligne['termines'], 1)
        self.assertEqual(ligne['fermes_avant_la_fin'], 0)
        self.assertEqual(ligne['sans_issue'], 0)
        self.assertEqual(ligne['fin_vs_passe'], 100.0)
        self.assertIsNone(kpis_onboarding_internes()['fin_vs_passe_raison'])
        TourProgress.objects.filter(tour_key='devis').update(issue='')
        ligne = {t['tour_key']: t for t in adoption_tours()}['devis']
        self.assertEqual(ligne['vus_ou_fermes'], 1)
        self.assertEqual(ligne['sans_issue'], 1)
        self.assertIsNone(ligne['fin_vs_passe'])
        self.assertEqual(
            kpis_onboarding_internes()['fin_vs_passe_raison'],
            RAISON_FIN_VS_PASSE)
