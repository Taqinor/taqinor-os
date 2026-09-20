"""PUB118 — Tests de la recombinaison DCO ZÉRO-CLÉ depuis les miroirs.

``dco.py`` portait ses validateurs (plafonds + exclusion mutuelle) SANS aucun
appelant hors tests, et ``sync.py`` miroitait déjà les assets : il manquait le
service de moisson. Prouve, sur fixtures :

  * la proposition porte une spec VALIDE, PLAFONNÉE et construite UNIQUEMENT
    d'assets déjà mirorés (aucun asset fabriqué, aucun appel réseau) ;
  * le pool est CONDITIONNÉ À LA PERFORMANCE : une ad sans résultat n'y entre
    pas (le remix de perdants ne gagne rien) ;
  * une violation d'exclusion mutuelle DCO ↔ rotation multi-ads → refus FR ;
  * le DCO reste réservé au BOOTSTRAP à froid (un ad set déjà signalé refuse) ;
  * l'application (transport mocké) crée l'ad via ``asset_feed_spec`` INLINE et
    elle naît PAUSED (invariant permanent règle #3) ;
  * l'endpoint « Recombiner (DCO) » est gaté, company-scopé, et rend la raison
    FR du refus en 400 (jamais un 500).
"""
import datetime
import json
from unittest.mock import Mock
from urllib.parse import parse_qs

import httpx
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import dco, services
from apps.adsengine import meta_client as mc
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, EngineAction,
    InsightSnapshot, MetaConnection,
)

User = get_user_model()
TODAY = datetime.date(2026, 7, 16)


def make_company(slug, nom=None):
    return Company.objects.create(nom=nom or slug, slug=slug)


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DcoFixtureMixin:
    def _page(self, page_id='page-42'):
        """PUB-P8/C2 — la Page qui PUBLIE : un créatif dynamique ne peut pas
        partir sans son acteur (même source que le pont PUB123)."""
        return MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', page_id=page_id,
            enabled=True, credentials={'access_token': 'tok'})

    def _adset(self, meta_id='as-1', name='Toit Casa'):
        campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id=f'cmp-{meta_id}', name='Solaire',
            status='PAUSED')
        return AdSetMirror.objects.create(
            company=self.company, meta_id=meta_id, name=name, status='PAUSED',
            campaign=campaign)

    def _winner(self, adset, idx, *, results=5, impressions=1000, date=None,
                **creative):
        """Ad GAGNANTE mirorée + son instantané de performance.

        ``date`` : le JOUR de l'instantané, à aligner sur l'horloge que verra la
        moisson (``dco.HARVEST_WINDOW_DAYS`` = 30 j). Par défaut ``TODAY``, ce qui
        va de pair avec un appel passant ``now=TODAY`` ; un appelant qui tourne sur
        l'horloge RÉELLE (une requête HTTP, par exemple) doit dater son gagnant
        sur cette horloge-là, sinon le pool est vide."""
        ad = AdMirror.objects.create(
            company=self.company, meta_id=f'ad-{idx}', name=f'Ad {idx}',
            adset=adset)
        defaults = {
            'creative_meta_id': f'cr-{idx}',
            'image_hash': f'hash-{idx}',
            'title': f'Titre {idx}',
            'body': f'Corps {idx}',
            'description': f'Desc {idx}',
            'cta_type': 'LEARN_MORE',
            'link_url': 'https://taqinor.ma',
        }
        defaults.update(creative)
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, **defaults)
        if results or impressions:
            ct = ContentType.objects.get_for_model(AdMirror)
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct, object_id=ad.pk,
                date=date or TODAY, spend='30.00', results=results,
                impressions=impressions)
        return ad


class HarvestWinningPoolTests(DcoFixtureMixin, TestCase):
    def setUp(self):
        self.company = make_company('pub118-harvest', 'PUB118 Harvest')
        self.source_adset = self._adset('as-src', 'Gagnants')

    def test_pool_is_built_only_from_mirrored_assets(self):
        self._winner(self.source_adset, 1)
        pool = dco.harvest_winning_pool(self.company, now=TODAY)
        self.assertEqual(pool['images'], ['hash-1'])
        self.assertEqual(pool['titles'], ['Titre 1'])
        self.assertEqual(pool['bodies'], ['Corps 1'])
        self.assertEqual(pool['descriptions'], ['Desc 1'])
        self.assertEqual(pool['ctas'], ['LEARN_MORE'])
        self.assertEqual(pool['links'], ['https://taqinor.ma'])
        self.assertEqual(pool['sources'], ['cr-1'])

    def test_ad_without_results_never_enters_the_pool(self):
        # Beaucoup d'impressions, ZÉRO résultat : jamais un « gagnant ».
        self._winner(self.source_adset, 9, results=0, impressions=50000)
        pool = dco.harvest_winning_pool(self.company, now=TODAY)
        self.assertEqual(pool['images'], [])
        self.assertEqual(pool['sources'], [])

    def test_ad_without_any_snapshot_never_enters_the_pool(self):
        self._winner(self.source_adset, 8, results=0, impressions=0)
        pool = dco.harvest_winning_pool(self.company, now=TODAY)
        self.assertEqual(pool['sources'], [])

    def test_best_results_come_first_so_caps_truncate_the_weakest(self):
        self._winner(self.source_adset, 1, results=1)
        self._winner(self.source_adset, 2, results=99)
        pool = dco.harvest_winning_pool(self.company, now=TODAY)
        self.assertEqual(pool['images'], ['hash-2', 'hash-1'])

    def test_duplicate_assets_are_deduplicated(self):
        self._winner(self.source_adset, 1, image_hash='same', body='Corps')
        self._winner(self.source_adset, 2, image_hash='same', body='Corps')
        pool = dco.harvest_winning_pool(self.company, now=TODAY)
        self.assertEqual(pool['images'], ['same'])
        self.assertEqual(pool['bodies'], ['Corps'])

    def test_another_company_pool_is_never_mixed_in(self):
        self._winner(self.source_adset, 1)
        other = make_company('pub118-autre', 'Autre')
        pool = dco.harvest_winning_pool(other, now=TODAY)
        self.assertEqual(pool['sources'], [])

    def test_window_excludes_stale_performance(self):
        ad = self._winner(self.source_adset, 1, results=0, impressions=0)
        ct = ContentType.objects.get_for_model(AdMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=ad.pk,
            date=TODAY - datetime.timedelta(days=90), spend='30.00', results=9)
        pool = dco.harvest_winning_pool(self.company, now=TODAY)
        self.assertEqual(pool['sources'], [])


class CapAndBuildSpecTests(TestCase):
    def test_per_field_caps_are_enforced(self):
        pool = {'images': [f'h{i}' for i in range(14)],
                'titles': [f't{i}' for i in range(9)],
                'bodies': [f'b{i}' for i in range(9)]}
        capped = dco.cap_pool(pool)
        self.assertEqual(len(capped['images']), dco.DCO_MAX_IMAGES)
        self.assertEqual(len(capped['titles']), dco.DCO_MAX_TITLES)
        self.assertEqual(len(capped['bodies']), dco.DCO_MAX_BODIES)

    def test_total_cap_is_enforced_by_trimming_the_biggest_field(self):
        pool = {'images': [f'h{i}' for i in range(10)],
                'videos': [f'v{i}' for i in range(10)],
                'titles': [f't{i}' for i in range(5)],
                'bodies': [f'b{i}' for i in range(5)],
                'descriptions': [f'd{i}' for i in range(5)]}
        capped = dco.cap_pool(pool)
        total = sum(len(capped[k]) for k in dco._FIELD_CAPS)
        self.assertLessEqual(total, dco.DCO_MAX_TOTAL_ASSETS)

    def test_spec_uses_the_repo_observed_graph_shapes(self):
        spec = dco.build_asset_feed_spec({
            'images': ['h1', 'h2'], 'titles': ['Titre'], 'bodies': ['Corps'],
            'descriptions': ['Desc'], 'ctas': ['LEARN_MORE'],
            'links': ['https://taqinor.ma']})
        self.assertEqual(spec['ad_formats'], [dco.AD_FORMAT_IMAGE])
        self.assertEqual(spec['images'], [{'hash': 'h1'}, {'hash': 'h2'}])
        self.assertEqual(spec['titles'], [{'text': 'Titre'}])
        self.assertEqual(spec['bodies'], [{'text': 'Corps'}])
        self.assertEqual(spec['descriptions'], [{'text': 'Desc'}])
        self.assertEqual(spec['call_to_action_types'], ['LEARN_MORE'])
        self.assertEqual(spec['link_urls'],
                         [{'website_url': 'https://taqinor.ma'}])
        self.assertNotIn('videos', spec)

    def test_video_only_pool_gives_a_video_spec(self):
        spec = dco.build_asset_feed_spec({
            'videos': ['v1'], 'bodies': ['Corps']})
        self.assertEqual(spec['ad_formats'], [dco.AD_FORMAT_VIDEO])
        self.assertEqual(spec['videos'], [{'video_id': 'v1'}])
        self.assertNotIn('images', spec)

    def test_images_win_and_videos_are_dropped_never_a_mixed_spec(self):
        spec = dco.build_asset_feed_spec({
            'images': ['h1'], 'videos': ['v1'], 'bodies': ['Corps']})
        self.assertEqual(spec['ad_formats'], [dco.AD_FORMAT_IMAGE])
        self.assertNotIn('videos', spec)

    def test_pool_without_media_is_refused_in_french(self):
        with self.assertRaises(dco.DcoPoolEmpty) as ctx:
            dco.build_asset_feed_spec({'bodies': ['Corps']})
        self.assertIn('aucun visuel', str(ctx.exception))

    def test_pool_without_body_is_refused_in_french(self):
        with self.assertRaises(dco.DcoPoolEmpty) as ctx:
            dco.build_asset_feed_spec({'images': ['h1']})
        self.assertIn('aucun texte principal', str(ctx.exception))

    def test_capped_spec_always_passes_the_dco_validator(self):
        pool = {'images': [f'h{i}' for i in range(40)],
                'titles': [f't{i}' for i in range(40)],
                'bodies': [f'b{i}' for i in range(40)]}
        spec = dco.build_asset_feed_spec(pool)
        self.assertEqual(len(spec['images']), dco.DCO_MAX_IMAGES)
        self.assertLessEqual(
            len(spec['images']) + len(spec['titles']) + len(spec['bodies']),
            dco.DCO_MAX_TOTAL_ASSETS)


class ProposeDcoRecombinationTests(DcoFixtureMixin, TestCase):
    def setUp(self):
        self.company = make_company('pub118-propose', 'PUB118 Propose')
        self._page()
        self.source_adset = self._adset('as-src', 'Gagnants')
        self._winner(self.source_adset, 1)
        self._winner(self.source_adset, 2)
        # La cible du bootstrap : un ad set NEUF (aucun signal, aucune ad).
        self.target = self._adset('as-new', 'Nouveau Rabat')

    def test_proposes_a_capped_valid_spec_from_mirrored_assets_only(self):
        action = services.propose_dco_recombination(
            self.company, adset=self.target, now=TODAY)
        self.assertEqual(action.kind, EngineAction.Kind.CREATE_AD)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        spec = action.payload['asset_feed_spec']
        self.assertEqual(
            {i['hash'] for i in spec['images']}, {'hash-1', 'hash-2'})
        self.assertEqual(
            {t['text'] for t in spec['titles']}, {'Titre 1', 'Titre 2'})
        self.assertEqual(action.payload['adset_id'], 'as-new')
        self.assertTrue(action.payload['name'])
        self.assertEqual(action.payload['creative_source'],
                         services.DCO_CREATIVE_SOURCE)
        self.assertEqual(action.payload['dco_mode'], dco.MODE_DCO_BOOTSTRAP)
        self.assertTrue(action.payload['dco_cold_start'])
        # Traçabilité : les créatifs SOURCES sont nommés dans le payload.
        self.assertEqual(set(action.payload['source_creative_ids']),
                         {'cr-1', 'cr-2'})
        # La spec reste sous les plafonds (le validateur DCO ne lève pas).
        self.assertEqual(
            dco.validate_dco_asset_spec({
                'images': spec['images'], 'titles': spec['titles'],
                'bodies': spec['bodies'],
                'descriptions': spec.get('descriptions', []),
                'ctas': spec.get('call_to_action_types', []),
                'links': spec.get('link_urls', [])}),
            10)  # 2 visuels + 2 titres + 2 textes + 2 desc + 1 CTA + 1 lien
        # La spec ne cite AUCUN asset absent des miroirs.
        self.assertEqual(
            {b['text'] for b in spec['bodies']}, {'Corps 1', 'Corps 2'})

    def test_reason_fr_counts_the_real_assets(self):
        action = services.propose_dco_recombination(
            self.company, adset=self.target, now=TODAY)
        self.assertIn('2 visuel(s)', action.reason_fr)
        self.assertIn('créatifs gagnants', action.reason_fr)

    def test_mutual_exclusion_violation_is_refused_in_french(self):
        # L'ad set porte DÉJÀ plusieurs ads (rotation multi-ads) : le DCO,
        # qui n'expose qu'UN ad par ad set, est structurellement exclu.
        for idx in (11, 12):
            AdMirror.objects.create(
                company=self.company, meta_id=f'ad-x{idx}', adset=self.target,
                name=f'Ad x{idx}')
        with self.assertRaises(dco.DcoModeConflict) as ctx:
            services.propose_dco_recombination(
                self.company, adset=self.target, now=TODAY)
        self.assertIn('exclusion mutuelle', str(ctx.exception))
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)

    def test_adset_with_signal_is_refused_dco_is_bootstrap_only(self):
        ct = ContentType.objects.get_for_model(AdSetMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.target.pk,
            date=TODAY, spend='10.00', results=2)
        with self.assertRaises(dco.DcoModeConflict) as ctx:
            services.propose_dco_recombination(
                self.company, adset=self.target, now=TODAY)
        self.assertIn('démarrage à froid', str(ctx.exception))

    def test_company_without_winner_proposes_nothing(self):
        empty = make_company('pub118-vide', 'Vide')
        adset = AdSetMirror.objects.create(
            company=empty, meta_id='as-v', name='Vide', status='PAUSED')
        with self.assertRaises(dco.DcoPoolEmpty):
            services.propose_dco_recombination(empty, adset=adset, now=TODAY)
        self.assertEqual(EngineAction.objects.filter(company=empty).count(), 0)

    def test_adset_without_meta_id_is_refused(self):
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='', name='Sans id')
        with self.assertRaises(dco.DcoPoolEmpty):
            services.propose_dco_recombination(
                self.company, adset=adset, now=TODAY)

    def test_payload_declares_the_page_that_publishes(self):
        # PUB-P8/C2 — le créatif DCO partait SANS acteur : la spec dynamique
        # porte désormais l'``object_story_spec.page_id`` de la connexion (même
        # source que le pont PUB123).
        action = services.propose_dco_recombination(
            self.company, adset=self.target, now=TODAY)
        self.assertEqual(action.payload['object_story_spec'],
                         {'page_id': 'page-42'})


class DcoWithoutPageTests(DcoFixtureMixin, TestCase):
    """PUB-P8/C2 — aucune Page connectée ⇒ refus FR, jamais un créatif sans
    acteur (que Graph rejetterait après l'approbation humaine)."""

    def setUp(self):
        self.company = make_company('pub118-sans-page', 'PUB118 Sans Page')
        self.source_adset = self._adset('as-src', 'Gagnants')
        self._winner(self.source_adset, 1)
        self.target = self._adset('as-new', 'Nouveau')

    def test_recombination_is_refused_in_french(self):
        from apps.adsengine import creative_bridge

        with self.assertRaises(creative_bridge.CreativeAssetNotReady) as ctx:
            services.propose_dco_recombination(
                self.company, adset=self.target, now=TODAY)
        self.assertIn('aucune Page Facebook connectée', str(ctx.exception))
        self.assertEqual(ctx.exception.key, creative_bridge.REFUS_PAGE)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)

    def test_connection_without_page_id_is_the_same_refusal(self):
        from apps.adsengine import creative_bridge

        MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', page_id='',
            enabled=True, credentials={'access_token': 'tok'})
        with self.assertRaises(creative_bridge.CreativeAssetNotReady):
            services.propose_dco_recombination(
                self.company, adset=self.target, now=TODAY)


class DcoDispatchTests(DcoFixtureMixin, TestCase):
    """L'application route vers la méthode à spec INLINE et l'ad naît PAUSED."""

    def setUp(self):
        self.company = make_company('pub118-dispatch', 'PUB118 Dispatch')
        self._page()
        self.source_adset = self._adset('as-src', 'Gagnants')
        self._winner(self.source_adset, 1)
        self.target = self._adset('as-new', 'Nouveau')

    def _approved(self):
        action = services.propose_dco_recombination(
            self.company, adset=self.target, now=TODAY)
        EngineAction.objects.filter(pk=action.pk).update(
            status=EngineAction.Statut.APPROUVEE)
        action.refresh_from_db()
        return action

    def test_dispatch_routes_to_the_asset_feed_spec_method(self):
        action = self._approved()
        client = Mock()
        client.create_ad_with_asset_feed_spec.return_value = {'id': 'ad-dco'}
        services.apply_action(action, client=client)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        client.create_ad.assert_not_called()
        kwargs = client.create_ad_with_asset_feed_spec.call_args.kwargs
        self.assertEqual(kwargs['adset_id'], 'as-new')
        self.assertEqual(kwargs['asset_feed_spec'],
                         action.payload['asset_feed_spec'])
        # PUB-P8/C2 — l'acteur est routé jusqu'au client.
        self.assertEqual(kwargs['object_story_spec'], {'page_id': 'page-42'})
        self.assertNotIn('status', kwargs)

    def test_real_client_forces_paused_and_encodes_the_spec(self):
        action = self._approved()
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'id': 'ad-dco'})

        client = mc.MetaClient(
            access_token='tok', ad_account_id='act_1',
            http_client=httpx.Client(
                transport=httpx.MockTransport(handler)),
            max_retries=0, backoff_base=0)
        services.apply_action(action, client=client)
        self.assertEqual(len(requests), 1)
        body = parse_qs(requests[0].content.decode('utf-8'))
        # Naissance PAUSED : invariant permanent règle #3.
        self.assertEqual(body['status'], ['PAUSED'])
        creative = json.loads(body['creative'][0])
        self.assertEqual(creative['asset_feed_spec'],
                         action.payload['asset_feed_spec'])
        self.assertEqual(creative['object_story_spec']['page_id'], 'page-42')


class DcoRecombineEndpointTests(DcoFixtureMixin, TestCase):
    def setUp(self):
        self.company = make_company('pub118-api', 'PUB118 API')
        self._page()
        self.source_adset = self._adset('as-src', 'Gagnants')
        # Une requête HTTP n'a pas d'horloge injectable : la vue propose « pour
        # aujourd'hui ». Le gagnant est donc daté sur l'horloge RÉELLE, sinon il
        # tombe hors de la fenêtre de moisson (30 j) et le pool est vide.
        self._winner(self.source_adset, 1, date=timezone.now().date())
        self.target = self._adset('as-new', 'Nouveau')
        self.manager = make_user(
            self.company, 'pub118-manager',
            ['adsengine_view', 'adsengine_manage'])
        self.viewer = make_user(
            self.company, 'pub118-viewer', ['adsengine_view'])

    def _url(self, meta_id):
        return f'/api/django/adsengine/adsets/{meta_id}/recombiner-dco/'

    def _client(self, user):
        return auth(user)

    def test_manager_gets_a_proposal(self):
        resp = self._client(self.manager).post(self._url('as-new'))
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['action']['kind'],
                         EngineAction.Kind.CREATE_AD)
        action = EngineAction.objects.get(company=self.company)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(action.proposed_by, self.manager)

    def test_viewer_is_refused(self):
        resp = self._client(self.viewer).post(self._url('as-new'))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)

    def test_unknown_adset_is_404(self):
        resp = self._client(self.manager).post(self._url('inconnu'))
        self.assertEqual(resp.status_code, 404)

    def test_another_company_adset_is_404(self):
        other = make_company('pub118-api-autre', 'Autre API')
        AdSetMirror.objects.create(
            company=other, meta_id='as-etranger', name='Étranger')
        resp = self._client(self.manager).post(self._url('as-etranger'))
        self.assertEqual(resp.status_code, 404)

    def test_business_refusal_is_a_400_with_the_french_reason(self):
        ct = ContentType.objects.get_for_model(AdSetMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.target.pk,
            date=TODAY, spend='10.00', results=2)
        resp = self._client(self.manager).post(self._url('as-new'))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('démarrage à froid', resp.data['detail'])
