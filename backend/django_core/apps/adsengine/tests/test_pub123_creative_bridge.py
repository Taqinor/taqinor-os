"""PUB123 — Tests du PONT ``CreativeAsset`` → payload créatif Meta.

Le maillon central du mur : un asset approuvé devient un fragment ``creative``
consommable par les dispatchs de création d'ad. Prouve :

  * golden PAR ``asset_type`` — statique avec lien (``link_data``), statique sans
    lien (``photo_data``), reel et explainer (``video_data``) — payload créatif
    COMPLET, bâti sur le ``page_id`` de la connexion et les identifiants de
    COMPTE de PUB122 (jamais une clé de stockage interne) ;
  * refus FR EXPLICITE et NOMMÉ pour chaque non-conformité : policy non validée,
    étiquette IA manquante (PUB126), consentement PUB75 absent / révoqué /
    expiré / hors portée, média jamais uploadé, type d'asset sans son média,
    société sans Page ;
  * la divulgation IA (PUB126) voyage jusqu'au payload, et RIEN n'est ajouté à
    la spec Graph tant que le champ de divulgation n'est pas confirmé ;
  * la chaîne de provenance asset → fait → version de ``FactTable`` survit
    jusqu'à l'ad (``generation_audit`` dans le payload de l'``EngineAction``).
"""
import datetime
import json
from unittest.mock import Mock

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import creative_bridge, policy as policy_mod, services
from apps.adsengine.models import (
    ConsentRecord, CreativeAsset, CreativeBacklogItem,
    CreativeGenerationBatch, EngineAction, FactEntry, FactTable,
    MetaConnection,
)

TODAY = datetime.date(2026, 7, 16)


def make_company(slug, nom=None):
    return Company.objects.create(nom=nom or slug, slug=slug)


class CreativeBridgeMixin:
    def _connect(self, page_id='page-42'):
        return MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', page_id=page_id)

    def _asset(self, **kw):
        kw.setdefault('asset_type', CreativeAsset.AssetType.STATIC)
        kw.setdefault('policy_stamp', {'passed': True})
        kw.setdefault('meta_image_hash', 'hash-abc')
        kw.setdefault('hook_text', 'Facture divisée')
        kw.setdefault('primary_text', 'Vos factures baissent.')
        kw.setdefault('cta', 'LEARN_MORE')
        return CreativeAsset.objects.create(company=self.company, **kw)


class GoldenPayloadPerAssetTypeTests(CreativeBridgeMixin, TestCase):
    def setUp(self):
        self.company = make_company('pub123-golden', 'PUB123 Golden')
        self.connection = self._connect()

    def test_static_with_link_gives_link_data(self):
        asset = self._asset()
        payload = creative_bridge.build_creative_payload(
            asset, connection=self.connection,
            link_url='https://taqinor.ma/devis')
        self.assertEqual(payload['creative'], {'object_story_spec': {
            'page_id': 'page-42',
            'link_data': {
                'image_hash': 'hash-abc',
                'link': 'https://taqinor.ma/devis',
                'message': 'Vos factures baissent.',
                'name': 'Facture divisée',
                'call_to_action': {
                    'type': 'LEARN_MORE',
                    'value': {'link': 'https://taqinor.ma/devis'}},
            },
        }})
        self.assertEqual(payload['creative_asset_id'], asset.pk)

    def test_static_without_link_gives_photo_data(self):
        asset = self._asset()
        payload = creative_bridge.build_creative_payload(
            asset, connection=self.connection)
        self.assertEqual(payload['creative'], {'object_story_spec': {
            'page_id': 'page-42',
            'photo_data': {'image_hash': 'hash-abc',
                           'caption': 'Vos factures baissent.'},
        }})

    def test_reel_gives_video_data_without_a_fabricated_thumbnail(self):
        asset = self._asset(asset_type=CreativeAsset.AssetType.REEL,
                            meta_image_hash='', meta_video_id='vid-9',
                            thumbnail_key='societe/vignette.jpg')
        payload = creative_bridge.build_creative_payload(
            asset, connection=self.connection,
            link_url='https://taqinor.ma/devis')
        oss = payload['creative']['object_story_spec']
        self.assertEqual(oss['video_data']['video_id'], 'vid-9')
        self.assertEqual(oss['video_data']['title'], 'Facture divisée')
        self.assertEqual(oss['video_data']['message'],
                         'Vos factures baissent.')
        self.assertEqual(oss['video_data']['call_to_action'],
                         {'type': 'LEARN_MORE',
                          'value': {'link': 'https://taqinor.ma/devis'}})
        # La vignette CHOISIE est une clé de stockage interne : jamais envoyée
        # comme si c'était un asset de compte Meta.
        self.assertNotIn('image_hash', oss['video_data'])
        self.assertNotIn('image_url', oss['video_data'])
        self.assertNotIn('societe/vignette.jpg', json.dumps(payload))

    def test_explainer_is_treated_as_video(self):
        asset = self._asset(asset_type=CreativeAsset.AssetType.EXPLAINER,
                            meta_image_hash='', meta_video_id='vid-x')
        payload = creative_bridge.build_creative_payload(
            asset, connection=self.connection)
        self.assertIn('video_data',
                      payload['creative']['object_story_spec'])

    def test_empty_texts_are_omitted_never_blank_keys(self):
        asset = self._asset(hook_text='', primary_text='', cta='')
        payload = creative_bridge.build_creative_payload(
            asset, connection=self.connection)
        self.assertEqual(
            payload['creative']['object_story_spec']['photo_data'],
            {'image_hash': 'hash-abc'})

    def test_connection_is_read_from_the_company_when_not_passed(self):
        asset = self._asset()
        payload = creative_bridge.build_creative_payload(asset)
        self.assertEqual(
            payload['creative']['object_story_spec']['page_id'], 'page-42')

    def test_is_ready_mirrors_the_refusal(self):
        self.assertTrue(creative_bridge.is_ready(
            self._asset(), connection=self.connection))
        self.assertFalse(creative_bridge.is_ready(
            self._asset(policy_stamp={}), connection=self.connection))


class RefusalTests(CreativeBridgeMixin, TestCase):
    def setUp(self):
        self.company = make_company('pub123-refus', 'PUB123 Refus')
        self.connection = self._connect()

    def _refuse(self, asset, **kw):
        kw.setdefault('connection', self.connection)
        with self.assertRaises(creative_bridge.CreativeAssetNotReady) as ctx:
            creative_bridge.build_creative_payload(asset, **kw)
        return ctx.exception

    def test_absent_asset_is_refused(self):
        exc = self._refuse(None)
        self.assertEqual(exc.key, creative_bridge.REFUS_ASSET_ABSENT)
        self.assertIn('introuvable', exc.reason_fr)

    def test_unstamped_policy_is_refused(self):
        exc = self._refuse(self._asset(policy_stamp={}))
        self.assertEqual(exc.key, creative_bridge.REFUS_POLICY)
        self.assertIn('check-list policy', exc.reason_fr)

    def test_policy_explicitly_failed_is_refused(self):
        exc = self._refuse(self._asset(policy_stamp={'passed': False}))
        self.assertEqual(exc.key, creative_bridge.REFUS_POLICY)

    def test_ai_lane_without_the_label_is_refused(self):
        # Lane « gen » = contenu IA : sans ``ai_generated``, PUB126 bloque.
        exc = self._refuse(self._asset(source_lane='gen', ai_generated=False))
        self.assertEqual(exc.key, creative_bridge.REFUS_ETIQUETTE_IA)
        self.assertEqual(exc.reason_fr, policy_mod.AI_DISCLOSURE_BLOCK_LABEL)

    def test_ai_lane_with_the_label_passes(self):
        payload = creative_bridge.build_creative_payload(
            self._asset(source_lane='gen', ai_generated=True),
            connection=self.connection)
        self.assertTrue(payload['ai_generated'])

    def test_missing_consent_is_refused(self):
        exc = self._refuse(self._asset(depicts_real_client=True))
        self.assertEqual(exc.key, creative_bridge.REFUS_CONSENTEMENT)
        self.assertIn('Consentement manquant', exc.reason_fr)

    def test_revoked_consent_is_refused(self):
        consent = ConsentRecord.objects.create(
            company=self.company, client_nom='Client A', portee_photo=True,
            date_consentement=TODAY,
            revoked_at=datetime.datetime(
                2026, 7, 1, tzinfo=datetime.timezone.utc))
        exc = self._refuse(self._asset(
            depicts_real_client=True, consent=consent))
        self.assertEqual(exc.key, creative_bridge.REFUS_CONSENTEMENT)
        self.assertIn('RÉVOQUÉ', exc.reason_fr)

    def test_consent_scope_not_covered_is_refused(self):
        consent = ConsentRecord.objects.create(
            company=self.company, client_nom='Client A', portee_photo=True,
            date_consentement=TODAY)
        exc = self._refuse(self._asset(
            depicts_real_client=True, consent=consent,
            consent_scopes_required=['temoignage']))
        self.assertEqual(exc.key, creative_bridge.REFUS_CONSENTEMENT)
        self.assertIn('portée requise', exc.reason_fr)

    def test_valid_consent_passes(self):
        consent = ConsentRecord.objects.create(
            company=self.company, client_nom='Client A', portee_photo=True,
            date_consentement=TODAY)
        payload = creative_bridge.build_creative_payload(
            self._asset(depicts_real_client=True, consent=consent,
                        consent_scopes_required=['photo']),
            connection=self.connection)
        self.assertIn('object_story_spec', payload['creative'])

    def test_image_never_uploaded_is_refused(self):
        exc = self._refuse(self._asset(meta_image_hash=''))
        self.assertEqual(exc.key, creative_bridge.REFUS_MEDIA)
        self.assertIn('image_hash', exc.reason_fr)

    def test_video_asset_without_video_id_is_refused_even_with_an_image(self):
        # Un reel « rattrapé » par une image est un bug, pas une option.
        exc = self._refuse(self._asset(
            asset_type=CreativeAsset.AssetType.REEL,
            meta_image_hash='hash-abc', meta_video_id=''))
        self.assertEqual(exc.key, creative_bridge.REFUS_MEDIA)
        self.assertIn('video_id', exc.reason_fr)

    def test_company_without_page_is_refused(self):
        MetaConnection.objects.filter(company=self.company).update(page_id='')
        exc = self._refuse(self._asset(), connection=None)
        self.assertEqual(exc.key, creative_bridge.REFUS_PAGE)
        self.assertIn('Page Facebook', exc.reason_fr)

    def test_company_without_any_connection_is_refused(self):
        other = make_company('pub123-sans-conn', 'Sans connexion')
        asset = CreativeAsset.objects.create(
            company=other, asset_type=CreativeAsset.AssetType.STATIC,
            policy_stamp={'passed': True}, meta_image_hash='h')
        exc = self._refuse(asset, connection=None)
        self.assertEqual(exc.key, creative_bridge.REFUS_PAGE)

    def test_conformity_reasons_come_before_technical_ones(self):
        # Asset à la fois non validé policy ET sans média : l'humain doit lire
        # d'abord la raison de CONFORMITÉ.
        exc = self._refuse(self._asset(policy_stamp={}, meta_image_hash=''))
        self.assertEqual(exc.key, creative_bridge.REFUS_POLICY)


class AiDisclosurePropagationTests(CreativeBridgeMixin, TestCase):
    def setUp(self):
        self.company = make_company('pub123-ia', 'PUB123 IA')
        self.connection = self._connect()

    def test_internal_key_travels_and_no_graph_field_is_invented(self):
        payload = creative_bridge.build_creative_payload(
            self._asset(source_lane='gen', ai_generated=True),
            connection=self.connection)
        self.assertIs(payload['ai_generated'], True)
        # Le champ Graph n'est PAS confirmé (note sourcée de policy.py) : la
        # spec Graph ne porte donc QUE object_story_spec.
        self.assertEqual(policy_mod.GRAPH_AI_DISCLOSURE_FIELD, '')
        self.assertEqual(list(payload['creative']), ['object_story_spec'])

    def test_real_site_photo_is_never_over_labelled(self):
        payload = creative_bridge.build_creative_payload(
            self._asset(source_lane='chantier'), connection=self.connection)
        self.assertIs(payload['ai_generated'], False)


class ProvenanceSurvivesToTheAdTests(CreativeBridgeMixin, TestCase):
    """La chaîne asset → fait → version FactTable survit jusqu'à l'ad."""

    def setUp(self):
        self.company = make_company('pub123-prov', 'PUB123 Provenance')
        self.connection = self._connect()
        table = FactTable.objects.create(
            company=self.company, version=3,
            statut=FactTable.Statut.PUBLIEE)
        FactEntry.objects.create(
            table=table, company=self.company,
            cle='production_mesuree_kwh_par_kwc_jour', valeur='4.5',
            unite='kWh/kWc/jour', source='Moyenne mesurée Taqinor',
            verifie_le=TODAY)
        self.asset = self._asset(source_lane='gen', ai_generated=True,
                                 facts_version=3)
        self.batch = CreativeGenerationBatch.objects.create(
            company=self.company,
            status=CreativeGenerationBatch.Statut.APPROUVEE,
            fact_table_version=3,
            claim_verdicts={'variants': [{'grounded': True}]})
        CreativeBacklogItem.objects.create(
            company=self.company, asset=self.asset, batch=self.batch,
            status=CreativeBacklogItem.Statut.EN_FILE)

    def test_payload_carries_the_generation_audit(self):
        payload = creative_bridge.build_creative_payload(
            self.asset, connection=self.connection)
        audit = payload['generation_audit']
        self.assertEqual(audit['asset_id'], self.asset.pk)
        self.assertEqual(audit['batch_id'], self.batch.pk)
        self.assertEqual(audit['fact_table_version'], 3)
        self.assertEqual(audit['claim_verdicts'],
                         {'variants': [{'grounded': True}]})
        self.assertEqual(audit['policy_stamp'], {'passed': True})

    def test_provenance_survives_on_the_engine_action_payload(self):
        fragments = creative_bridge.build_creative_payload(
            self.asset, connection=self.connection)
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.CREATE_AD,
            reason_fr="Créer une ad depuis cet asset ponté.",
            payload={'name': '20260716_STATIC', 'adset_id': 'as-1',
                     **fragments})
        action.refresh_from_db()
        self.assertEqual(
            action.payload['generation_audit']['fact_table_version'], 3)
        self.assertEqual(action.payload['creative_asset_id'], self.asset.pk)
        self.assertIs(action.payload['ai_generated'], True)

    def test_provenance_is_optional(self):
        payload = creative_bridge.build_creative_payload(
            self.asset, connection=self.connection, with_provenance=False)
        self.assertNotIn('generation_audit', payload)


class BridgedCreateAdDispatchTests(CreativeBridgeMixin, TestCase):
    """Un CREATE_AD porteur d'un ``creative`` ponté route et naît PAUSED."""

    def setUp(self):
        self.company = make_company('pub123-dispatch', 'PUB123 Dispatch')
        self.connection = self._connect()

    def test_dispatch_encodes_the_bridged_creative(self):
        fragments = creative_bridge.build_creative_payload(
            self._asset(), connection=self.connection)
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.CREATE_AD,
            reason_fr="Créer une ad depuis cet asset ponté.",
            payload={'name': 'Ad pontée', 'adset_id': 'as-1', **fragments})
        EngineAction.objects.filter(pk=action.pk).update(
            status=EngineAction.Statut.APPROUVEE)
        action.refresh_from_db()
        client = Mock()
        client.create_ad.return_value = {'id': 'ad-1'}
        services.apply_action(action, client=client)
        kwargs = client.create_ad.call_args.kwargs
        self.assertEqual(
            json.loads(kwargs['extra_fields']['creative']),
            fragments['creative'])
        # Aucun statut n'est émis par ce chemin (le client FORCE PAUSED).
        self.assertNotIn('status', kwargs)
        self.assertNotIn('status', kwargs['extra_fields'])

    def test_unstamped_asset_can_never_reach_a_proposal(self):
        # ENG15 — la garde policy de ``propose_action`` reste la dernière digue.
        asset = self._asset(policy_stamp={})
        with self.assertRaises(services.CreativePolicyNotPassed):
            services.propose_action(
                self.company, kind=EngineAction.Kind.CREATE_AD,
                reason_fr="Créer une ad depuis un asset non validé.",
                payload={'name': 'Ad', 'adset_id': 'as-1',
                         'creative_asset_id': asset.pk})
