"""PUB99 — Tests d'enregistrement plateforme (ARC28) du moteur publicitaire.

Prouve : le manifeste ``platform.PLATFORM`` est collecté et normalisé ; les
campagnes sont cherchables globalement (spec + manifeste) ; le provider KPI
fédéré renvoie les tuiles dépense/leads ; les actions d'agent sont LECTURE SEULE
et enregistrées.
"""
import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from core import platform as core_platform

from apps.adsengine import agent_actions, selectors
from apps.adsengine.models import (
    AdCampaignMirror, InsightSnapshot, MetaLeadMirror,
)
from apps.agent.registry import RISK_INTERNAL, _REGISTRY


class PlatformManifestTests(TestCase):
    def test_manifest_collected_and_normalized(self):
        manifests = core_platform.collect_platform_manifests()
        self.assertIn('adsengine', manifests)
        m = manifests['adsengine']
        self.assertIn('adsengine.adcampaignmirror', m['searchable_models'])
        self.assertEqual(
            m['agent_actions_module'], 'apps.adsengine.agent_actions')
        self.assertIn(
            'apps.adsengine.selectors.kpi_publicite', m['kpi_providers'])

    def test_campaign_searchable_for_company(self):
        company = Company.objects.create(nom='Search Co', slug='search-co')
        cherchables = core_platform.searchable_models(company)
        self.assertIn('adsengine.adcampaignmirror', cherchables)

    def test_search_spec_finds_campaign(self):
        from apps.reporting.search import _spec_campagne
        company = Company.objects.create(nom='Spec Co', slug='spec-co')
        AdCampaignMirror.objects.create(
            company=company, meta_id='c1', name='Solaire Casa', status='PAUSED')
        _, _, qs, mapper = _spec_campagne({'company': company}, 'Solaire')
        rows = list(qs)
        self.assertEqual(len(rows), 1)
        self.assertEqual(mapper(rows[0])['label'], 'Solaire Casa')


class KpiPubliciteTests(TestCase):
    def test_kpi_tiles(self):
        company = Company.objects.create(nom='Kpi Co', slug='kpi-co')
        camp = AdCampaignMirror.objects.create(
            company=company, meta_id='c1', name='Camp', status='PAUSED')
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        InsightSnapshot.objects.create(
            company=company, content_type=ct, object_id=camp.pk,
            date=datetime.date.today(), spend=Decimal('300.00'))
        MetaLeadMirror.objects.create(company=company, leadgen_id='lg1')
        tiles = selectors.kpi_publicite(company)
        by_id = {t['id']: t for t in tiles}
        self.assertEqual(by_id['adsengine_spend_7j']['valeur'], 300.0)
        self.assertEqual(by_id['adsengine_leads_7j']['valeur'], 1)

    def test_kpi_empty_company_zero(self):
        company = Company.objects.create(nom='Empty Co', slug='empty-co')
        tiles = selectors.kpi_publicite(company)
        self.assertEqual(tiles[0]['valeur'], 0.0)
        self.assertEqual(tiles[1]['valeur'], 0)


class AgentActionsTests(TestCase):
    def test_actions_registered_read_only(self):
        agent_actions.register_actions()
        keys = ('adsengine.spend.week', 'adsengine.ads.top',
                'adsengine.campaigns.list')
        for key in keys:
            self.assertIn(key, _REGISTRY)
            self.assertEqual(_REGISTRY[key].risk, RISK_INTERNAL)
            self.assertEqual(_REGISTRY[key].method, 'GET')

    def test_rep7_depense_bornee_par_debut_et_fin(self):
        """REP7 — « cette semaine » exige deux dates : sans elles la route
        rendait TOUT l'historique. Les bornes déclarées sont lues par la route
        (dépense d'il y a 30 jours exclue) et la garde est ``adsengine_view``."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        from apps.agent.tests.test_registry import _gardes_de_la_route
        from apps.roles.models import Role
        action = agent_actions.DEPENSE_SEMAINE
        self.assertEqual(action.inputs['required'], ['debut', 'fin'])
        self.assertIn(action.required_permission, _gardes_de_la_route(action)[0])
        company = Company.objects.create(nom='Rep7 Co', slug='rep7-co')
        camp = AdCampaignMirror.objects.create(
            company=company, meta_id='c7', name='Camp', status='PAUSED')
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        today = datetime.date.today()
        for jour, montant in ((today, '300.00'), (today - datetime.timedelta(days=30), '999.00')):
            InsightSnapshot.objects.create(
                company=company, content_type=ct, object_id=camp.pk,
                date=jour, spend=Decimal(montant))
        user = get_user_model().objects.create_user(
            username='rep7', password='x', company=company,
            role=Role.objects.create(company=company, nom='Pub',
                                     permissions=['adsengine_view']))
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get(action.endpoint, {'debut': today.isoformat(),
                                         'fin': today.isoformat()})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Decimal(resp.data['spend']), Decimal('300.00'))
