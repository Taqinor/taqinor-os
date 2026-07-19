"""PUB16 — Câblage du pipeline de génération IA ANCRÉE (AGEN2) en production.

Prouve : l'orchestration produit un ``CreativeGenerationBatch`` EN_ATTENTE de
variantes ancrées FactTable (assets nés PENDING) avec l'audit ``claim_verdicts``
persisté ; sans clé LLM le pipeline est un NO-OP propre (aucun lot, zéro crash) ;
l'endpoint est gaté ``adsengine_manage`` et renvoie un message clair sans clé.
"""
import os
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import tasks
from apps.adsengine.models import (
    CreativeAsset, CreativeGenerationBatch, FactEntry, FactTable,
)

User = get_user_model()

BASE = '/api/django/adsengine/generation/variantes-ancrees/'


def _publish_table(company):
    table = FactTable.create_draft(company)
    FactEntry.objects.create(
        table=table, cle='economie_annuelle', valeur='12 000',
        unite='MAD', source='étude interne', verifie_le=date(2026, 1, 1))
    FactEntry.objects.create(
        table=table, cle='autoconsommation', valeur='82',
        unite='%', source='RedaSolar', verifie_le=date(2026, 1, 1))
    table.publish()
    return table


def _mock_gen(context):
    return [{
        'asset_type': 'static',
        'hook_text': "Jusqu'à 82 % d'autoconsommation",
        'primary_text': 'Économisez 12 000 MAD par an.',
        'cta': 'Devis gratuit',
        'claims': [
            {'fact_key': 'autoconsommation'},
            {'fact_key': 'economie_annuelle'},
        ],
    }]


class OrchestrationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Gen Co', slug='gen-co')

    def test_noop_without_generator_or_key(self):
        _publish_table(self.company)
        result = tasks._run_grounded_generation(
            self.company, 'panneaux solaires économies maison sud')
        self.assertFalse(result['enabled'])
        self.assertIsNone(result['batch_id'])
        self.assertEqual(CreativeGenerationBatch.objects.count(), 0)
        self.assertEqual(CreativeAsset.objects.count(), 0)

    def test_creates_batch_with_persisted_claim_verdicts(self):
        _publish_table(self.company)
        result = tasks._run_grounded_generation(
            self.company, 'panneaux solaires économies maison sud',
            generator=_mock_gen)
        self.assertTrue(result['enabled'])
        self.assertEqual(result['assets'], 1)

        batch = CreativeGenerationBatch.objects.get(id=result['batch_id'])
        # Lot EN_ATTENTE d'approbation humaine (l'IA produit des ASSETS).
        self.assertEqual(batch.status,
                         CreativeGenerationBatch.Statut.EN_ATTENTE)
        # Audit claim_verdicts persisté + version de la table de faits.
        self.assertIn('variants', batch.claim_verdicts)
        self.assertTrue(batch.claim_verdicts['variants'][0]['grounded'])
        self.assertIsNotNone(batch.fact_table_version)
        # L'asset ancré est né PENDING (jamais auto-validé).
        asset = CreativeAsset.objects.get(pk=batch.visual_ids[0])
        self.assertEqual(asset.policy_stamp, {})

    def test_task_noop_when_company_missing(self):
        result = tasks.generate_grounded_variants(999999, 'x')
        self.assertFalse(result['enabled'])
        self.assertEqual(result['reason'], 'société introuvable')


class EndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Gen Co', slug='gen-co')
        role = Role.objects.create(
            company=self.company, nom='r',
            permissions=['adsengine_view', 'adsengine_manage'])
        self.user = User.objects.create_user(
            username='u', password='x', company=self.company,
            role_legacy='normal', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_requires_seed_brief(self):
        resp = self.api.post(BASE, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch.dict(os.environ, {}, clear=False)
    def test_keygated_message_without_key(self):
        os.environ.pop('ADSENGINE_GEN_API_KEY', None)
        resp = self.api.post(BASE, {'seed_brief': 'solaire maison'},
                             format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['enabled'])
        self.assertEqual(CreativeGenerationBatch.objects.count(), 0)

    def test_dispatches_task_when_key_present(self):
        with patch.dict(os.environ,
                        {'ADSENGINE_GEN_API_KEY': 'k'}, clear=False), \
                patch('apps.adsengine.tasks.generate_grounded_variants.delay'
                      ) as delay:
            resp = self.api.post(BASE, {'seed_brief': 'solaire maison'},
                                 format='json')
        self.assertEqual(resp.status_code, 202)
        self.assertTrue(resp.data['enabled'])
        delay.assert_called_once()

    def test_permission_gated(self):
        viewer_role = Role.objects.create(
            company=self.company, nom='viewer', permissions=['adsengine_view'])
        viewer = User.objects.create_user(
            username='v', password='x', company=self.company,
            role_legacy='normal', role=viewer_role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(viewer)}')
        resp = api.post(BASE, {'seed_brief': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)
