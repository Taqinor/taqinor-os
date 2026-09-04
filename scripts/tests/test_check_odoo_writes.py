"""Tests CRX11 — scripts/check_odoo_writes.py.

Stdlib pure (unittest), sans Django ni base : la garde elle-meme n'en a pas.
Chaque cas NEGATIF prouve que la garde rougit vraiment ; le dernier prouve
qu'elle est verte sur le depot REEL (une garde qui ne peut plus rougir et une
garde deja rouge sont toutes les deux inutilisables).

Run:
    python -m unittest scripts.tests.test_check_odoo_writes -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_odoo_writes as cow  # noqa: E402

ODOO_SYNC = 'apps/crm/odoo_sync.py'

ALLOWLIST_CONFORME = """
_WRITE_ALLOWED = frozenset({('crm.lead', 'write')})


def odoo_call(config, model, method, payload):
    if (model, method) not in _WRITE_ALLOWED:
        raise RuntimeError('non')
"""


def _echecs(fonction, textes):
    echecs = []
    fonction(textes, echecs)
    return echecs


class TestAppels(unittest.TestCase):
    def test_lecture_ne_rougit_pas(self):
        echecs = _echecs(cow._verifier_appels, {
            'apps/crm/lecture.py':
                "odoo_call(cfg, 'crm.lead', 'search_read', {})",
        })
        self.assertFalse([e for e in echecs if 'crm.lead' in e and
                          'ECRITURE' in e], echecs)

    def test_ecriture_non_declaree_rougit(self):
        echecs = _echecs(cow._verifier_appels, {
            'apps/crm/ailleurs.py':
                "odoo_call(cfg, 'res.partner', 'write', {'vals': {}})",
        })
        self.assertTrue(
            any('res.partner.write' in e and 'ECRITURE' in e for e in echecs),
            echecs)

    def test_unlink_non_declare_rougit(self):
        echecs = _echecs(cow._verifier_appels, {
            ODOO_SYNC: "odoo_call(cfg, 'crm.lead', 'unlink', {})",
        })
        self.assertTrue(
            any('crm.lead.unlink' in e for e in echecs), echecs)

    def test_ecriture_declaree_ne_rougit_pas(self):
        echecs = _echecs(cow._verifier_appels, {
            ODOO_SYNC: "odoo_call(cfg, 'crm.lead', 'write', {'ids': ids})",
        })
        self.assertFalse(
            [e for e in echecs if 'crm.lead.write' in e and 'ECRITURE' in e],
            echecs)

    def test_meme_ecriture_depuis_un_autre_fichier_rougit(self):
        # L'exception est declaree POUR odoo_sync : la meme ecriture lancee
        # d'ailleurs reste un rouge (le transport a un proprietaire).
        echecs = _echecs(cow._verifier_appels, {
            'apps/ventes/services.py':
                "odoo_call(cfg, 'crm.lead', 'write', {'ids': ids})",
        })
        self.assertTrue(
            any('crm.lead.write' in e and 'ECRITURE' in e for e in echecs),
            echecs)

    def test_modele_non_litteral_rougit(self):
        echecs = _echecs(cow._verifier_appels, {
            ODOO_SYNC: "odoo_call(cfg, modele, methode, {})",
        })
        self.assertTrue(
            any('litteral' in e for e in echecs), echecs)

    def test_exception_qui_ne_couvre_plus_rien_rougit(self):
        # Aucun appel dans le corpus : les 3 exceptions declarees sont
        # signalees comme perimees (la garde pointe dans les deux sens).
        echecs = _echecs(cow._verifier_appels, {'apps/crm/vide.py': 'x = 1'})
        self.assertTrue(
            any('AUCUN appel correspondant' in e for e in echecs), echecs)

    def test_les_tests_du_depot_sont_ignores(self):
        echecs = _echecs(cow._verifier_appels, {
            'apps/crm/tests_odoo_sync.py':
                "odoo_call(cfg, 'res.partner', 'unlink', {})",
        })
        self.assertFalse(
            [e for e in echecs if 'res.partner' in e], echecs)


class TestTransportsDeclares(unittest.TestCase):
    def _corpus(self, extra=None):
        textes = {rel: '' for rel in
                  list(cow.TRANSPORTS_DECLARES) + list(cow.HOOKS_DECLARES)}
        textes.update(extra or {})
        return textes

    def test_corpus_complet_ne_rougit_pas(self):
        self.assertEqual(
            _echecs(cow._verifier_transports_declares, self._corpus()), [])

    def test_nouveau_transport_json2_rougit(self):
        echecs = _echecs(cow._verifier_transports_declares, self._corpus({
            'apps/compta/pont_odoo.py':
                "url = base + '/json/2/account.move/create'",
        }))
        self.assertTrue(
            any('pont_odoo.py' in e and 'NON DECLARE' in e for e in echecs),
            echecs)

    def test_nouveau_transport_jsonrpc_rougit(self):
        echecs = _echecs(cow._verifier_transports_declares, self._corpus({
            'apps/stock/rpc.py': "resp = post(base + '/jsonrpc', json=p)",
        }))
        self.assertTrue(any('rpc.py' in e for e in echecs), echecs)

    def test_transport_declare_disparu_rougit(self):
        textes = self._corpus()
        textes.pop(ODOO_SYNC)
        echecs = _echecs(cow._verifier_transports_declares, textes)
        self.assertTrue(
            any(ODOO_SYNC in e and 'INTROUVABLE' in e for e in echecs), echecs)


class TestAllowlistExecution(unittest.TestCase):
    def test_conforme_ne_rougit_pas(self):
        self.assertEqual(
            _echecs(cow._verifier_allowlist_execution,
                    {ODOO_SYNC: ALLOWLIST_CONFORME}), [])

    def test_absente_rougit(self):
        echecs = _echecs(cow._verifier_allowlist_execution, {
            ODOO_SYNC: "def odoo_call(config, model, method, payload):\n"
                       "    return 1\n"})
        self.assertTrue(any('_WRITE_ALLOWED' in e for e in echecs), echecs)

    def test_elargie_rougit(self):
        echecs = _echecs(cow._verifier_allowlist_execution, {
            ODOO_SYNC: ALLOWLIST_CONFORME.replace(
                "{('crm.lead', 'write')}",
                "{('crm.lead', 'write'), ('res.partner', 'unlink')}")})
        self.assertTrue(any('res.partner' in e for e in echecs), echecs)

    def test_declaree_mais_jamais_consultee_rougit(self):
        echecs = _echecs(cow._verifier_allowlist_execution, {
            ODOO_SYNC: "_WRITE_ALLOWED = frozenset({('crm.lead', 'write')})\n"
                       "def odoo_call(config, model, method, payload):\n"
                       "    return 1\n"})
        self.assertTrue(
            any('jamais consultee' in e for e in echecs), echecs)


class TestModuleDormant(unittest.TestCase):
    def test_sans_appelant_ne_rougit_pas(self):
        self.assertEqual(_echecs(cow._verifier_module_dormant, {
            'core/odoo_accounting.py': 'x = 1',
            'core/tests/test_odoo_accounting.py': 'from core import '
                                                  'odoo_accounting',
        }), [])

    def test_appelant_hors_tests_rougit(self):
        echecs = _echecs(cow._verifier_module_dormant, {
            'core/odoo_accounting.py': 'x = 1',
            'apps/compta/services.py': 'from core import odoo_accounting',
        })
        self.assertTrue(
            any('plus dormant' in e and 'apps/compta/services.py' in e
                for e in echecs), echecs)


class TestHookConnecteur(unittest.TestCase):
    def test_hook_present_ne_rougit_pas(self):
        self.assertEqual(_echecs(cow._verifier_hook_connecteur, {
            cow.HOOK_FICHIER:
                "CONNECTEUR_ODOO_MODULE = 'apps.publicapi.connectors.odoo'",
        }), [])

    def test_hook_disparu_rougit(self):
        echecs = _echecs(cow._verifier_hook_connecteur, {
            cow.HOOK_FICHIER: 'rien = 1',
        })
        self.assertTrue(any('a disparu' in e for e in echecs), echecs)


class TestDepotReel(unittest.TestCase):
    def test_le_depot_est_vert(self):
        self.assertEqual(cow.main(), 0)


if __name__ == '__main__':
    unittest.main()
