"""ADSENG11 — Tests table d'autorité par barreau (purs : SimpleTestCase).

Prouve (dd-science-core §3) :
  * chaque barreau porte le bon niveau (CTR/proxy autonomes ; qualifié propose ;
    signature inform) ;
  * une action issue d'un barreau non-autonome DOIT être proposée ;
  * ``promote_challenger`` n'est jamais autonome (règle #3) ;
  * au-dessus du plafond de garde-fou, même une action autonome est proposée ;
  * la config est modifiable SANS code (overrides) — la logique lit la donnée.
"""
from django.test import SimpleTestCase

from apps.adsengine import authority as A


class LevelPerRungTests(SimpleTestCase):
    def test_ctr_autonomous(self):
        self.assertEqual(A.authority_level(A.RUNG_CTR), A.AUTONOMOUS)
        self.assertTrue(A.is_autonomous(A.RUNG_CTR))

    def test_proxy_autonomous(self):
        self.assertEqual(A.authority_level(A.RUNG_PROXY), A.AUTONOMOUS)

    def test_qualified_propose_only(self):
        self.assertEqual(A.authority_level(A.RUNG_QUALIFIED), A.PROPOSE)
        self.assertFalse(A.is_autonomous(A.RUNG_QUALIFIED))

    def test_signature_inform_only(self):
        self.assertEqual(A.authority_level(A.RUNG_SIGNATURE), A.INFORM)
        self.assertFalse(A.is_autonomous(A.RUNG_SIGNATURE))

    def test_unknown_rung_raises(self):
        with self.assertRaises(A.UnknownRungError):
            A.authority_level('made_up_rung')


class DispositionTests(SimpleTestCase):
    def test_ctr_rebalance_is_auto(self):
        self.assertTrue(A.is_auto_applicable(
            A.RUNG_CTR, A.ACTION_REBALANCE_BUDGET))
        self.assertFalse(A.requires_proposal(
            A.RUNG_CTR, A.ACTION_REBALANCE_BUDGET))

    def test_proxy_pause_is_auto(self):
        self.assertTrue(A.is_auto_applicable(
            A.RUNG_PROXY, A.ACTION_PAUSE_ARM))

    def test_qualified_action_must_be_proposed(self):
        self.assertFalse(A.is_auto_applicable(
            A.RUNG_QUALIFIED, A.ACTION_REBALANCE_BUDGET))
        self.assertTrue(A.requires_proposal(
            A.RUNG_QUALIFIED, A.ACTION_REBALANCE_BUDGET))

    def test_signature_action_must_be_proposed(self):
        self.assertTrue(A.requires_proposal(
            A.RUNG_SIGNATURE, A.ACTION_REBALANCE_BUDGET))

    def test_promote_challenger_never_autonomous(self):
        # Même sur un barreau autonome, promouvoir naît PAUSED → propose (règle #3).
        for rung in (A.RUNG_CTR, A.RUNG_PROXY):
            self.assertFalse(A.is_auto_applicable(
                rung, A.ACTION_PROMOTE_CHALLENGER))
            self.assertTrue(A.requires_proposal(
                rung, A.ACTION_PROMOTE_CHALLENGER))

    def test_pause_not_authorized_on_ctr(self):
        # CTR n'autorise que le rééquilibrage, pas le kill.
        self.assertFalse(A.is_auto_applicable(A.RUNG_CTR, A.ACTION_PAUSE_ARM))

    def test_above_guardrail_downgrades_to_propose(self):
        # Autonome mais changement au-dessus du plafond ⇒ propose (§3).
        self.assertFalse(A.is_auto_applicable(
            A.RUNG_CTR, A.ACTION_REBALANCE_BUDGET, within_guardrail=False))
        self.assertTrue(A.requires_proposal(
            A.RUNG_CTR, A.ACTION_REBALANCE_BUDGET, within_guardrail=False))


class ConfigModifiableWithoutCodeTests(SimpleTestCase):
    def test_override_downgrades_ctr(self):
        # Rétrograder CTR en propose via DONNÉES seulement : la logique suit.
        table = A.load_authority_table(
            overrides={A.RUNG_CTR: {'level': A.PROPOSE,
                                    'autonomous_actions': []}})
        self.assertFalse(A.is_autonomous(A.RUNG_CTR, table=table))
        self.assertTrue(A.requires_proposal(
            A.RUNG_CTR, A.ACTION_REBALANCE_BUDGET, table=table))
        # La table par défaut reste intacte (copie profonde).
        self.assertTrue(A.is_autonomous(A.RUNG_CTR))

    def test_override_upgrades_qualified(self):
        table = A.load_authority_table(
            overrides={A.RUNG_QUALIFIED: {
                'level': A.AUTONOMOUS,
                'autonomous_actions': [A.ACTION_REBALANCE_BUDGET]}})
        self.assertTrue(A.is_auto_applicable(
            A.RUNG_QUALIFIED, A.ACTION_REBALANCE_BUDGET, table=table))
        # Défaut inchangé.
        self.assertFalse(A.is_autonomous(A.RUNG_QUALIFIED))

    def test_default_table_not_mutated_by_load(self):
        table = A.load_authority_table()
        table[A.RUNG_CTR]['autonomous_actions'].append('hack')
        self.assertNotIn('hack',
                         A.AUTHORITY_TABLE[A.RUNG_CTR]['autonomous_actions'])
