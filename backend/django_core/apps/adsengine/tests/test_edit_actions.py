"""ADSDEEP31 — EngineAction surface d'édition : EDIT_COPY / SET_SPEND_CAP / RENAME.

Prouve le cycle propose→approuve→applique pour les 3 kinds (route vers la bonne
méthode d'édition de ``meta_client``, atterrit APPLIQUEE), et que les DEUX
avertissements (reset d'apprentissage + perte de preuve sociale) sont portés dans
``payload['warnings']`` d'une EDIT_COPY — donc rendus à l'approbateur. Invariant
permanent (règle #3) : aucune de ces méthodes n'envoie de ``status`` (garanti par
meta_client, cf. test_write_methods) — ici on prouve le routage, pas d'activation.
"""
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import services
from apps.adsengine.models import EngineAction

User = get_user_model()


class EditWarningsTests(TestCase):
    def test_edit_copy_carries_both_warnings(self):
        warns = services.edit_warnings(EngineAction.Kind.EDIT_COPY)
        self.assertIn(services.WARN_LEARNING_RESET, warns)
        self.assertIn(services.WARN_SOCIAL_PROOF_LOSS, warns)
        self.assertEqual(len(warns), 2)

    def test_rename_and_spend_cap_have_no_warning(self):
        self.assertEqual(
            services.edit_warnings(EngineAction.Kind.RENAME), [])
        self.assertEqual(
            services.edit_warnings(EngineAction.Kind.SET_SPEND_CAP), [])


class EditActionCycleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Edit Co', slug='edit-co')
        self.user = User.objects.create_user(
            username='approver', password='x', company=self.company)

    def _cycle(self, action, client):
        services.approve_action(action, user=self.user)
        services.apply_action(action, client=client)
        action.refresh_from_db()
        return action

    def test_edit_copy_proposes_with_warnings_then_swaps_creative(self):
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.EDIT_COPY,
            reason_fr="Rafraîchir l'accroche fatiguée de l'ad.",
            payload={'ad_id': 'ad-1',
                     'creative_spec': {'name': 'Nouvelle accroche'}})
        # Avertissements présents DÈS la proposition (rendus à l'approbateur).
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertIn(services.WARN_LEARNING_RESET, action.payload['warnings'])
        self.assertIn(
            services.WARN_SOCIAL_PROOF_LOSS, action.payload['warnings'])

        client = Mock()
        client.swap_ad_creative.return_value = {'creative_id': 'cr-9'}
        action = self._cycle(action, client)
        client.swap_ad_creative.assert_called_once_with(
            ad_id='ad-1', creative_spec={'name': 'Nouvelle accroche'},
            creative_id=None, extra_fields=None)
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        self.assertEqual(action.result, {'creative_id': 'cr-9'})

    def test_set_spend_cap_cycle_reaches_client(self):
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.SET_SPEND_CAP,
            reason_fr="Plafonner la dépense totale de la campagne à 5000 MAD.",
            payload={'campaign_id': 'c-1', 'spend_cap': 500000})
        self.assertEqual(action.payload.get('warnings', []), [])
        client = Mock()
        client.set_campaign_spend_cap.return_value = {'success': True}
        action = self._cycle(action, client)
        client.set_campaign_spend_cap.assert_called_once_with(
            campaign_id='c-1', spend_cap=500000, extra_fields=None)
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

    def test_rename_cycle_reaches_client(self):
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.RENAME,
            reason_fr="Renommer la campagne selon la convention 2026.",
            payload={'object_id': 'c-1', 'name': 'SOLAIRE-2026-Q1'})
        client = Mock()
        client.rename_object.return_value = {'success': True}
        action = self._cycle(action, client)
        client.rename_object.assert_called_once_with(
            object_id='c-1', name='SOLAIRE-2026-Q1', extra_fields=None)
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

    def test_edit_action_not_applied_before_approval(self):
        """Belt-and-suspenders : une EDIT_COPY seulement proposée ne touche jamais
        le client (le chemin d'apply exige APPROUVEE)."""
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.EDIT_COPY,
            reason_fr="Édition en attente d'approbation.",
            payload={'ad_id': 'ad-2', 'creative_id': 'cr-x'})
        client = Mock()
        with self.assertRaises(services.ActionNotApproved):
            services.apply_action(action, client=client)
        client.swap_ad_creative.assert_not_called()

    def test_caller_warnings_preserved_and_deduped(self):
        """Un avertissement fourni par l'appelant (ex. reset-seuil ADSDEEP32) est
        conservé et jamais dupliqué par la fusion des avertissements d'édition."""
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.EDIT_COPY,
            reason_fr="Édition avec avertissement pré-existant.",
            payload={'ad_id': 'ad-3', 'creative_id': 'cr-y',
                     'warnings': ['Avertissement métier maison',
                                  services.WARN_LEARNING_RESET]})
        warns = action.payload['warnings']
        self.assertIn('Avertissement métier maison', warns)
        self.assertIn(services.WARN_SOCIAL_PROOF_LOSS, warns)
        # WARN_LEARNING_RESET fourni ET calculé → présent une seule fois.
        self.assertEqual(warns.count(services.WARN_LEARNING_RESET), 1)
