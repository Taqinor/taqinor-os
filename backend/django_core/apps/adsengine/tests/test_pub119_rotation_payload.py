"""PUB119 — Tests de la FIN du payload ROTATE_CREATIVE creux.

Prouve, sur fixtures :
  * ``naming.build_name`` est bien le PENDANT de ``parse_name`` (un nom produit
    par le moteur se re-parse en ses tags d'origine) ;
  * ``services.resolve_rotation_payload`` résout les TROIS pièces à la
    PROPOSITION — ad set cible, nom, source créative — avec la priorité
    backlog approuvé → créatif LIVE de l'ad set ;
  * un finding ``frequency_high`` déclenché produit une proposition au payload
    COMPLET (``adset_id`` + ``name`` + ``creative``) ;
  * aucune source créative prête ⇒ ALERTE explicite « aucun créatif prêt » +
    raison consignée au journal de la règle, et ZÉRO action (jamais une action
    creuse) ;
  * un payload creux FORCÉ ⇒ l'action passe « echouee » avec sa raison FR SANS
    qu'aucun appel réseau ne soit émis ;
  * la naissance PAUSED reste intacte (aucun ``status`` n'est jamais émis par
    ce chemin).
"""
import datetime
from unittest.mock import Mock

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import naming, rules_engine, services
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, CreativeAsset,
    CreativeBacklogItem, EngineAction, EngineAlert, InsightSnapshot,
    MetaConnection, RulePolicy,
)

TODAY = datetime.date(2026, 7, 16)


def make_company(slug, nom=None):
    return Company.objects.create(nom=nom or slug, slug=slug)


class BuildNameTests(SimpleTestCase):
    """PUB119 — Le constructeur de nom est l'inverse exact du parseur."""

    def test_round_trip_through_parse_name(self):
        name = naming.build_name({
            'date': '20260716', 'format': 'REEL', 'hook': 'FACTURE',
            'angle': 'ROI'})
        self.assertEqual(name, '20260716_REEL_FACTURE_ROI')
        self.assertEqual(naming.tags_from_name(name), {
            'hook_tag': 'FACTURE', 'angle_tag': 'ROI', 'format_tag': 'REEL'})

    def test_trailing_missing_segments_are_omitted_never_filled(self):
        # Queue non renseignée : OMISE (aucun segment fabriqué pour combler).
        self.assertEqual(
            naming.build_name({'date': '20260716', 'format': 'REEL'}),
            '20260716_REEL')

    def test_gap_before_a_filled_segment_keeps_positions_aligned(self):
        # Un trou AVANT un segment renseigné doit garder la position des
        # suivants (sinon le nom se re-parserait faux).
        name = naming.build_name({'date': '20260716', 'angle': 'ROI'})
        self.assertEqual(name, '20260716_NA_NA_ROI')
        self.assertEqual(naming.tags_from_name(name)['angle_tag'], 'ROI')

    def test_delimiter_inside_a_segment_is_neutralised(self):
        name = naming.build_name({'date': '2026', 'format': 'A_B C'})
        self.assertEqual(name, '2026_A-B-C')

    def test_empty_values_give_empty_name(self):
        self.assertEqual(naming.build_name({}), '')
        self.assertEqual(naming.build_name(None), '')
        self.assertEqual(naming.build_name({'date': '1'}, convention=''), '')


class ResolveRotationPayloadTests(TestCase):
    def setUp(self):
        self.company = make_company('pub119-resolve', 'PUB119 Resolve')
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-1', name='Solaire',
            status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-1', name='Toit Casa',
            status='PAUSED', campaign=self.campaign)
        # PUB123 — le pont exige une Page connectée : un ``object_story_spec``
        # n'existe pas sans ``page_id`` (Meta veut l'acteur qui publie).
        self.connection = MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', page_id='page-42')

    def _ad_with_creative(self, meta_id, creative_id, *, name='', link_url=''):
        ad = AdMirror.objects.create(
            company=self.company, meta_id=meta_id, adset=self.adset,
            name=name or meta_id)
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, creative_meta_id=creative_id,
            link_url=link_url)
        return ad

    def _asset(self, *, passed=True, image_hash='', video_id='', **kw):
        return CreativeAsset.objects.create(
            company=self.company,
            asset_type=kw.pop('asset_type', CreativeAsset.AssetType.STATIC),
            policy_stamp={'passed': True} if passed else {},
            meta_image_hash=image_hash, meta_video_id=video_id, **kw)

    def _backlog(self, asset, **kw):
        return CreativeBacklogItem.objects.create(
            company=self.company, asset=asset,
            status=kw.pop('status', CreativeBacklogItem.Statut.EN_FILE), **kw)

    # ── Source (b) : créatif LIVE du miroir ──────────────────────────────────
    def test_live_mirror_creative_when_backlog_empty(self):
        self._ad_with_creative('ad-1', 'cr-1')
        payload = services.resolve_rotation_payload(
            self.company, target_type='adset', target_meta_id='as-1',
            now=TODAY)
        self.assertEqual(payload['adset_id'], 'as-1')
        self.assertEqual(payload['creative'], {'creative_id': 'cr-1'})
        self.assertEqual(payload['creative_source'],
                         services.ROTATION_SOURCE_LIVE_MIRROR)
        self.assertEqual(payload['source_ad_id'], 'ad-1')
        self.assertTrue(payload['name'])

    def test_ad_target_resolves_its_adset(self):
        ad = self._ad_with_creative('ad-1', 'cr-1')
        payload = services.resolve_rotation_payload(
            self.company, target_type='ad', target_meta_id=ad.meta_id,
            now=TODAY)
        self.assertEqual(payload['adset_id'], 'as-1')

    def test_best_live_creative_is_the_one_with_most_results(self):
        weak = self._ad_with_creative('ad-weak', 'cr-weak')
        strong = self._ad_with_creative('ad-strong', 'cr-strong')
        ct = ContentType.objects.get_for_model(AdMirror)
        for ad, results in ((weak, 1), (strong, 9)):
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct, object_id=ad.pk,
                date=TODAY, spend='10.00', results=results, impressions=1000)
        payload = services.resolve_rotation_payload(
            self.company, target_type='adset', target_meta_id='as-1',
            now=TODAY)
        self.assertEqual(payload['creative'], {'creative_id': 'cr-strong'})

    # ── Source (a) : tête du backlog approuvé, pontée par PUB123 ─────────────
    def test_approved_backlog_head_wins_over_live_mirror(self):
        self._ad_with_creative('ad-1', 'cr-1',
                               link_url='https://taqinor.ma/devis')
        asset = self._asset(image_hash='hash-abc', hook_text='Facture divisée',
                            primary_text='Vos factures baissent.', cta='LEARN_MORE',
                            hook_tag='FACTURE', angle_tag='ROI',
                            format_tag='STATIC')
        item = self._backlog(asset)
        payload = services.resolve_rotation_payload(
            self.company, target_type='adset', target_meta_id='as-1',
            now=TODAY)
        self.assertEqual(payload['creative_source'],
                         services.ROTATION_SOURCE_BACKLOG)
        self.assertEqual(payload['creative_asset_id'], asset.pk)
        self.assertEqual(payload['backlog_item_id'], item.pk)
        # PUB123 — le fragment est un ``object_story_spec`` complet (Page +
        # média de COMPTE + textes), pas un média nu que Graph refuserait.
        oss = payload['creative']['object_story_spec']
        self.assertEqual(oss['page_id'], 'page-42')
        # Le lien vient du miroir de l'ad set (donnée RÉELLE, jamais fabriquée).
        self.assertEqual(oss['link_data']['link'], 'https://taqinor.ma/devis')
        self.assertEqual(oss['link_data']['image_hash'], 'hash-abc')
        self.assertEqual(oss['link_data']['message'], 'Vos factures baissent.')
        self.assertEqual(oss['link_data']['name'], 'Facture divisée')
        self.assertEqual(oss['link_data']['call_to_action'],
                         {'type': 'LEARN_MORE',
                          'value': {'link': 'https://taqinor.ma/devis'}})
        # Étiquette IA + provenance voyagent avec la proposition.
        self.assertIn('ai_generated', payload)
        self.assertEqual(payload['generation_audit']['asset_id'], asset.pk)
        # Le nom hérite des tags de l'asset via la convention de nommage.
        self.assertEqual(naming.tags_from_name(payload['name']), {
            'hook_tag': 'FACTURE', 'angle_tag': 'ROI',
            'format_tag': 'STATIC'})

    def test_image_asset_without_link_uses_photo_data(self):
        self._ad_with_creative('ad-1', 'cr-1')  # miroir sans link_url
        self._backlog(self._asset(image_hash='hash-abc',
                                  primary_text='Sans lien.'))
        payload = services.resolve_rotation_payload(
            self.company, target_type='adset', target_meta_id='as-1',
            now=TODAY)
        oss = payload['creative']['object_story_spec']
        self.assertEqual(oss['photo_data'],
                         {'image_hash': 'hash-abc', 'caption': 'Sans lien.'})
        self.assertNotIn('link_data', oss)

    def test_video_asset_uses_video_data(self):
        self._ad_with_creative('ad-1', 'cr-1')
        asset = self._asset(asset_type=CreativeAsset.AssetType.REEL,
                            video_id='vid-9', hook_text='Accroche',
                            primary_text='Corps')
        self._backlog(asset)
        payload = services.resolve_rotation_payload(
            self.company, target_type='adset', target_meta_id='as-1',
            now=TODAY)
        oss = payload['creative']['object_story_spec']
        self.assertEqual(oss['video_data']['video_id'], 'vid-9')
        self.assertEqual(oss['video_data']['title'], 'Accroche')
        self.assertEqual(oss['video_data']['message'], 'Corps')
        self.assertNotIn('image_hash', oss['video_data'])

    def test_backlog_is_skipped_when_no_page_is_connected(self):
        # Sans Page, le pont refuse : la rotation retombe sur le créatif LIVE
        # (jamais un object_story_spec sans acteur).
        MetaConnection.objects.filter(company=self.company).update(page_id='')
        self._ad_with_creative('ad-1', 'cr-1')
        self._backlog(self._asset(image_hash='hash-abc'))
        payload = services.resolve_rotation_payload(
            self.company, target_type='adset', target_meta_id='as-1',
            now=TODAY)
        self.assertEqual(payload['creative_source'],
                         services.ROTATION_SOURCE_LIVE_MIRROR)

    def test_backlog_asset_without_uploaded_media_is_skipped(self):
        self._ad_with_creative('ad-1', 'cr-1')
        self._backlog(self._asset())  # aucun hash/video_id → inutilisable
        payload = services.resolve_rotation_payload(
            self.company, target_type='adset', target_meta_id='as-1',
            now=TODAY)
        self.assertEqual(payload['creative_source'],
                         services.ROTATION_SOURCE_LIVE_MIRROR)

    def test_backlog_asset_failing_policy_is_skipped(self):
        self._ad_with_creative('ad-1', 'cr-1')
        self._backlog(self._asset(passed=False, image_hash='hash-x'))
        payload = services.resolve_rotation_payload(
            self.company, target_type='adset', target_meta_id='as-1',
            now=TODAY)
        self.assertEqual(payload['creative_source'],
                         services.ROTATION_SOURCE_LIVE_MIRROR)

    def test_backlog_item_of_another_campaign_is_never_diverted(self):
        self._ad_with_creative('ad-1', 'cr-1')
        other_campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-2', name='Autre',
            status='PAUSED')
        self._backlog(self._asset(image_hash='hash-x'),
                      target_campaign=other_campaign)
        payload = services.resolve_rotation_payload(
            self.company, target_type='adset', target_meta_id='as-1',
            now=TODAY)
        self.assertEqual(payload['creative_source'],
                         services.ROTATION_SOURCE_LIVE_MIRROR)

    def test_backlog_item_not_en_file_is_skipped(self):
        self._ad_with_creative('ad-1', 'cr-1')
        self._backlog(self._asset(image_hash='hash-x'),
                      status=CreativeBacklogItem.Statut.RETIRE)
        payload = services.resolve_rotation_payload(
            self.company, target_type='adset', target_meta_id='as-1',
            now=TODAY)
        self.assertEqual(payload['creative_source'],
                         services.ROTATION_SOURCE_LIVE_MIRROR)

    # ── Refus EXPLICITES (jamais une action creuse) ──────────────────────────
    def test_no_creative_at_all_raises_explicit_fr_reason(self):
        with self.assertRaises(services.RotationCreativeUnavailable) as ctx:
            services.resolve_rotation_payload(
                self.company, target_type='adset', target_meta_id='as-1',
                now=TODAY)
        self.assertEqual(str(ctx.exception), services.ROTATION_NO_CREATIVE_FR)
        self.assertIn('Aucun créatif prêt', str(ctx.exception))

    def test_unknown_adset_raises_explicit_fr_reason(self):
        with self.assertRaises(services.RotationCreativeUnavailable) as ctx:
            services.resolve_rotation_payload(
                self.company, target_type='adset', target_meta_id='inconnu',
                now=TODAY)
        self.assertIn('introuvable', str(ctx.exception))

    def test_other_company_adset_is_never_resolved(self):
        other = make_company('pub119-autre', 'Autre')
        with self.assertRaises(services.RotationCreativeUnavailable):
            services.resolve_rotation_payload(
                other, target_type='adset', target_meta_id='as-1', now=TODAY)

    def test_adset_without_meta_id_is_refused(self):
        AdSetMirror.objects.create(
            company=self.company, meta_id='', name='Sans id')
        with self.assertRaises(services.RotationCreativeUnavailable):
            services.resolve_rotation_payload(
                self.company, target_type='adset', target_meta_id='',
                now=TODAY)


class ValidateRotationPayloadTests(SimpleTestCase):
    def test_complete_payload_returns_the_creative(self):
        creative = {'creative_id': 'cr-1'}
        self.assertEqual(
            services.validate_rotation_payload(
                {'adset_id': 'as-1', 'name': 'Ad', 'creative': creative}),
            creative)

    def test_missing_creative_is_refused_in_french(self):
        with self.assertRaises(services.ActionPayloadInvalid) as ctx:
            services.validate_rotation_payload(
                {'adset_id': 'as-1', 'name': 'Ad'})
        self.assertIn('créatif', str(ctx.exception))

    def test_missing_adset_id_is_refused(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.validate_rotation_payload(
                {'name': 'Ad', 'creative': {'creative_id': 'c'}})

    def test_missing_name_is_refused(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.validate_rotation_payload(
                {'adset_id': 'as-1', 'creative': {'creative_id': 'c'}})

    def test_extra_fields_never_carry_a_status(self):
        extra = services.ad_extra_fields_with_creative({
            'adset_id': 'as-1', 'name': 'Ad',
            'creative': {'creative_id': 'cr-1'},
            'extra_fields': {'status': 'ACTIVE', 'bid_amount': 300}})
        self.assertNotIn('status', extra)
        self.assertEqual(extra['bid_amount'], 300)
        self.assertEqual(extra['creative'], '{"creative_id": "cr-1"}')


class RotationProposalFromRuleTests(TestCase):
    """Le chemin CADENCÉ : finding frequency_high → payload complet OU alerte."""

    def setUp(self):
        self.company = make_company('pub119-rule', 'PUB119 Rule')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-9', name='Toit Rabat',
            status='PAUSED')
        self.policy = RulePolicy.objects.create(
            company=self.company, template_key='frequency_high', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        ct = ContentType.objects.get_for_model(AdSetMirror)
        for i in range(4):
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct,
                object_id=self.adset.pk,
                date=TODAY - datetime.timedelta(days=i),
                spend='10.00', results=1, frequency='4.0')

    def _live_creative(self):
        ad = AdMirror.objects.create(
            company=self.company, meta_id='ad-9', adset=self.adset,
            name='20260101_REEL_FACTURE_ROI')
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, creative_meta_id='cr-9')
        return ad

    def test_fired_finding_proposes_a_complete_payload(self):
        self._live_creative()
        rules_engine.evaluate_company(self.company, now=TODAY)
        action = EngineAction.objects.get(company=self.company)
        self.assertEqual(action.kind, EngineAction.Kind.ROTATE_CREATIVE)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(action.payload['adset_id'], 'as-9')
        # Nom construit par la convention : les tags sont RELUS du nom de la
        # source (jamais inventés), la date est celle de l'évaluation.
        self.assertEqual(action.payload['name'],
                         '20260716_REEL_FACTURE_ROI')
        self.assertEqual(action.payload['creative'], {'creative_id': 'cr-9'})
        # Le payload DESCRIPTIF (dédup cooldown) reste présent.
        self.assertEqual(action.payload['template_key'], 'frequency_high')
        self.assertEqual(action.payload['target_meta_id'], 'as-9')

    def test_without_any_creative_no_action_but_explicit_alert(self):
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)
        alerts = EngineAlert.objects.filter(company=self.company)
        self.assertTrue(alerts.exists())
        self.assertTrue(any('Aucun créatif prêt' in a.message
                            for a in alerts))
        # La raison est consignée au journal de la règle (jamais un skip muet).
        self.policy.refresh_from_db()
        findings = self.policy.last_result['findings']
        self.assertEqual(len(findings), 1)
        self.assertIn('Aucun créatif prêt', findings[0]['blocked_fr'])
        self.assertNotIn('action', findings[0])

    def test_simulation_without_creative_proposes_nothing(self):
        self.policy.dry_run = True
        self.policy.save(update_fields=['dry_run'])
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)
        self.policy.refresh_from_db()
        self.assertIn(
            'Aucun créatif prêt',
            self.policy.last_result['findings'][0]['blocked_fr'])


class RotationFromCreativeFatigueTests(TestCase):
    """Le chemin AD (ADSDEEP45) exige la même complétude de payload."""

    def setUp(self):
        self.company = make_company('pub119-fat', 'PUB119 Fatigue')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-f', name='Fatigue',
            status='PAUSED')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad-f', name='Reel v3',
            adset=self.adset)
        self.ct = ContentType.objects.get_for_model(AdMirror)
        for i in range(10):
            InsightSnapshot.objects.create(
                company=self.company, content_type=self.ct,
                object_id=self.ad.pk,
                date=TODAY - datetime.timedelta(days=8 + i),
                spend='20.00', clicks=40, impressions=2000, results=2,
                frequency='2.0')
        for i in range(5):
            InsightSnapshot.objects.create(
                company=self.company, content_type=self.ct,
                object_id=self.ad.pk, date=TODAY - datetime.timedelta(days=i),
                spend='20.00', clicks=10, impressions=2000, results=1,
                frequency='4.8')

    def test_with_live_creative_payload_is_complete(self):
        AdCreativeMirror.objects.create(
            company=self.company, ad=self.ad, creative_meta_id='cr-f')
        findings = rules_engine.evaluate_creative_fatigue(
            self.company, now=TODAY)
        self.assertEqual(len(findings), 1)
        self.assertIn('action', findings[0])
        action = EngineAction.objects.get(pk=findings[0]['action']['id'])
        self.assertEqual(action.payload['adset_id'], 'as-f')
        self.assertEqual(action.payload['creative'], {'creative_id': 'cr-f'})

    def test_without_creative_records_reason_and_proposes_nothing(self):
        findings = rules_engine.evaluate_creative_fatigue(
            self.company, now=TODAY)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0]['fired'])
        self.assertNotIn('action', findings[0])
        self.assertIn('Aucun créatif prêt', findings[0]['blocked_fr'])
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)


class RotationDispatchTests(TestCase):
    """``_dispatch`` : complétude FAIL-FAST, zéro appel réseau, PAUSED intact."""

    def setUp(self):
        self.company = make_company('pub119-dispatch', 'PUB119 Dispatch')

    def _approved(self, payload):
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.ROTATE_CREATIVE,
            reason_fr='Roter le créatif fatigué.', payload=payload)
        EngineAction.objects.filter(pk=action.pk).update(
            status=EngineAction.Statut.APPROUVEE)
        action.refresh_from_db()
        return action

    def test_hollow_payload_fails_without_any_network_call(self):
        action = self._approved({'template_key': 'frequency_high',
                                 'target_meta_id': 'as-1'})
        client = Mock()
        with self.assertRaises(services.ActionPayloadInvalid):
            services.apply_action(action, client=client)
        client.create_ad.assert_not_called()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)
        self.assertIn('créatif', action.error)

    def test_complete_payload_creates_the_ad_without_any_status(self):
        action = self._approved({
            'adset_id': 'as-1', 'name': '20260716_REEL_FACTURE_ROI',
            'creative': {'creative_id': 'cr-1'}})
        client = Mock()
        client.create_ad.return_value = {'id': 'ad-new', 'status': 'PAUSED'}
        services.apply_action(action, client=client)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        kwargs = client.create_ad.call_args.kwargs
        self.assertEqual(kwargs['adset_id'], 'as-1')
        self.assertEqual(kwargs['name'], '20260716_REEL_FACTURE_ROI')
        self.assertEqual(kwargs['extra_fields']['creative'],
                         '{"creative_id": "cr-1"}')
        # Naissance PAUSED : aucun statut n'est JAMAIS émis par ce chemin (le
        # client le FORCE lui-même, cf. ``_forced_status_payload``).
        self.assertNotIn('status', kwargs)
        self.assertNotIn('status', kwargs['extra_fields'])

    def test_real_client_signature_refuses_a_status_kwarg(self):
        from apps.adsengine.meta_client import MetaClient
        with self.assertRaises(TypeError):
            MetaClient.create_ad(
                Mock(), name='Ad', adset_id='as-1', status='ACTIVE')
