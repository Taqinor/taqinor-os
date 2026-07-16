"""ADSENG26 — Tests de la recombinaison créative déterministe (mocked).

Prouve : une recombinaison mockée bout-en-bout (accroche gagnante × visuels via
les adaptateurs ENG17) produit un lot ≤2 de variantes PENDING avec la lignée
héritée ; l'approbation par LOT humain est OBLIGATOIRE avant tout passage au
backlog (une variante non approuvée n'y entre jamais) ; la policy est héritée +
revalidée ; et la substitution ne porte JAMAIS de clé génératrice.
"""
import contextlib
import os
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role
from apps.adsengine import creative_factory as cf
from apps.adsengine import policy, recombine
from apps.adsengine.models import (
    CreativeAsset, CreativeBacklogItem, CreativeGenerationBatch,
)

User = get_user_model()

_FORBIDDEN_KEYS = [r['key'] for r in policy.DEFAULT_FORBIDDEN]


def make_user(company):
    role = Role.objects.create(
        company=company, nom='rec-role', permissions=['adsengine_manage'])
    return User.objects.create_user(
        username='recmgr', password='x', company=company,
        role_legacy='normal', role=role)


class RecombineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Re Co', slug='re-co')
        self.user = make_user(self.company)
        # Accroche GAGNANTE validée (toutes les règles interdites confirmées).
        self.hook = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            hook_id='H03', hook_text='Économisez 40%',
            primary_text='Passez au solaire.', cta='LEARN_MORE',
            policy_stamp={'passed': True, 'rules_checked': _FORBIDDEN_KEYS})
        self.vis1 = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            visual_asset_key='re/v1.png')
        self.vis2 = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            visual_asset_key='re/v2.png')

    @contextlib.contextmanager
    def _mocked_templated(self):
        """Mock bout-en-bout des adaptateurs Templated (submit/poll) + stockage
        MinIO, avec la clé d'environnement présente."""
        with patch.dict(os.environ, {'TEMPLATED_API_KEY': 'k'}, clear=False), \
             patch.object(cf.TemplatedAdapter, 'submit', return_value='r1'), \
             patch.object(cf.TemplatedAdapter, 'poll', return_value=b'IMG'), \
             patch('apps.adsengine.creative_factory._store_bytes',
                   return_value='adsengine/1/x.png'):
            yield

    def test_recombine_end_to_end_then_lot_approval(self):
        with self._mocked_templated():
            batch = recombine.recombine_hook_across_visuals(
                self.hook, [self.vis1, self.vis2], http_client=Mock())
        # Lot EN ATTENTE, 2 variantes produites, lignée héritée, PENDING.
        self.assertEqual(
            batch.status, CreativeGenerationBatch.Statut.EN_ATTENTE)
        self.assertEqual(len(batch.visual_ids), 2)
        members = list(CreativeAsset.objects.filter(pk__in=batch.visual_ids))
        for m in members:
            self.assertFalse(m.is_policy_passed)   # PENDING avant approbation
            self.assertEqual(m.hook_id, 'H03')     # accroche héritée
            self.assertEqual(m.parent_id, self.hook.id)
        # AUCUN backlog tant que le lot n'est pas approuvé.
        self.assertEqual(CreativeBacklogItem.objects.count(), 0)

        # Approbation PAR LOT (humain) → tampon passed + backlog.
        batch2, items = recombine.approve_lot(batch, user=self.user)
        self.assertEqual(
            batch2.status, CreativeGenerationBatch.Statut.APPROUVEE)
        self.assertEqual(batch2.approved_by_id, self.user.id)
        self.assertEqual(len(items), 2)
        for m in members:
            m.refresh_from_db()
            self.assertTrue(m.is_policy_passed)    # héritée + revalidée
        self.assertEqual(
            CreativeBacklogItem.objects.filter(
                source=CreativeBacklogItem.Source.RECOMBINAISON).count(), 2)

    def test_per_lot_approval_is_mandatory(self):
        # Sans approbation, les variantes restent PENDING et hors backlog.
        with self._mocked_templated():
            batch = recombine.recombine_hook_across_visuals(
                self.hook, [self.vis1], http_client=Mock())
        member = CreativeAsset.objects.get(pk=batch.visual_ids[0])
        self.assertFalse(member.is_policy_passed)
        self.assertEqual(CreativeBacklogItem.objects.count(), 0)

    def test_batch_capped_at_two_per_run(self):
        extra = [CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            visual_asset_key=f're/x{i}.png') for i in range(5)]
        with self._mocked_templated():
            batch = recombine.recombine_hook_across_visuals(
                self.hook, extra, http_client=Mock())
        self.assertLessEqual(
            len(batch.visual_ids), recombine.RECOMBINATION_CAP)

    def test_reject_lot_keeps_members_out_of_backlog(self):
        with self._mocked_templated():
            batch = recombine.recombine_hook_across_visuals(
                self.hook, [self.vis1], http_client=Mock())
        recombine.reject_lot(batch, user=self.user)
        batch.refresh_from_db()
        self.assertEqual(
            batch.status, CreativeGenerationBatch.Statut.REJETEE)
        self.assertEqual(CreativeBacklogItem.objects.count(), 0)

    def test_requires_validated_source(self):
        unvalidated = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC)
        with self.assertRaises(ValueError):
            recombine.recombine_hook_across_visuals(
                unvalidated, [self.vis1])


class SubstitutionOnlyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Su Co', slug='su-co')
        self.hook = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            hook_id='H1', hook_text='Accroche', primary_text='Corps',
            cta='LEARN_MORE', perf={'transcript_task_id': 'T42'},
            policy_stamp={'passed': True, 'rules_checked': _FORBIDDEN_KEYS})

    def test_static_payload_uses_layers_no_prompt(self):
        vis = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            visual_asset_key='su/v.png')
        payload = recombine.build_substitution_payload(self.hook, vis)
        self.assertIn('layers', payload['input'])
        self.assertNotIn('prompt', payload['input'])

    def test_video_payload_reuses_transcript_task_id(self):
        reel = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.REEL,
            file_key='su/reel.mp4')
        payload = recombine.build_substitution_payload(self.hook, reel)
        self.assertEqual(payload['input']['transcriptTaskId'], 'T42')
        self.assertNotIn('prompt', payload['input'])

    def test_generative_key_is_rejected(self):
        with self.assertRaises(ValueError):
            recombine._assert_substitution_only(
                {'input': {'prompt': 'invente un faux chantier'}})
