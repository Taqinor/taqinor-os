"""ADSENG19 — La règle homme-mort est une SPEC + une commande : RIEN d'activé.

Ces tests verrouillent l'invariant de sécurité (règle #3) : le module ne peut
PAS activer la règle, ne fait AUCUN appel réseau, ne PORTE PAS de secret, et son
payload met en PAUSE (jamais ACTIVATE).
"""
from django.test import SimpleTestCase

from apps.adsengine import deadman


class DeadmanIsOffByDesignTests(SimpleTestCase):
    def test_disabled_in_source(self):
        self.assertFalse(deadman.DEADMAN_ENABLED)
        status = deadman.deadman_status()
        self.assertFalse(status['enabled'])
        self.assertFalse(status['installed_by_us'])

    def test_no_activation_or_network_function_exists(self):
        # Aucun chemin d'installation/activation/réseau : le module ne fait que
        # CONSTRUIRE des données et RENDRE une chaîne. On interdit toute méthode
        # qui laisserait croire qu'elle agit sur le compte.
        for forbidden in (
            'install', 'activate', 'enable', 'apply', 'create_rule',
            'push', 'post', 'call_meta', 'run',
        ):
            self.assertFalse(
                hasattr(deadman, forbidden),
                f'Aucune fonction « {forbidden} » ne doit exister (rien d\'activé).')


class DeadmanSpecTests(SimpleTestCase):
    def test_spec_pauses_never_activates(self):
        spec = deadman.build_deadman_rule_spec(ceiling_mad=1500)
        self.assertEqual(spec['execution_spec']['execution_type'], 'PAUSE')
        # Jamais d'ACTIVATE dans le payload sérialisé.
        self.assertNotIn('ACTIVATE', str(spec))
        self.assertEqual(spec['schedule_spec']['schedule_type'], 'SEMI_HOURLY')

    def test_spec_encodes_ceiling_in_centimes(self):
        spec = deadman.build_deadman_rule_spec(ceiling_mad=2000)
        spent = next(f for f in spec['evaluation_spec']['filters']
                     if f['field'] == 'spent')
        self.assertEqual(spent['value'], 2000 * 100)
        self.assertEqual(spent['operator'], 'GREATER_THAN')

    def test_default_ceiling_is_a_last_resort_high_value(self):
        spec = deadman.build_deadman_rule_spec()
        spent = next(f for f in spec['evaluation_spec']['filters']
                     if f['field'] == 'spent')
        self.assertEqual(spent['value'],
                         deadman.DEFAULT_CATASTROPHE_CEILING_MAD * 100)


class DeadmanInstallCommandTests(SimpleTestCase):
    def test_command_is_a_string_and_carries_no_secret(self):
        cmd = deadman.deadman_install_command(ad_account_id='act_123')
        self.assertIsInstance(cmd, str)
        # Le jeton est lu de l'environnement, jamais incorporé.
        self.assertIn('$META_SYSTEM_USER_TOKEN', cmd)
        self.assertIn('act_123', cmd)
        self.assertIn(deadman.ADRULES_EDGE, cmd)
        # C'est une commande curl documentée — pas un effet.
        self.assertIn('curl', cmd)

    def test_command_honours_custom_token_env(self):
        cmd = deadman.deadman_install_command(
            ad_account_id='act_9', access_token_env='MY_TOKEN')
        self.assertIn('$MY_TOKEN', cmd)
