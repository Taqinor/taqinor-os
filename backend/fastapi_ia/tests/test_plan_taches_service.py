"""XPRJ29 — Génération IA d'un brouillon de plan de tâches depuis un devis.

Couvre le service (``app/services/plan_taches_service.py``), sans dépendance
réseau : la factory LLM est monkeypatchée. Vérifie le no-op propre (503-style
exception) sans clé LLM, le parsing/validation du JSON renvoyé par le LLM, et
la propreté (dépendances vers un code inexistant retirées).

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests
"""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.services import plan_taches_service as _svc
    _OK = True
    _ERR = None
except Exception as exc:  # pragma: no cover - deps absentes
    _svc = None
    _OK = False
    _ERR = exc


@unittest.skipUnless(_OK, f"plan_taches_service indisponible: {_ERR}")
class ClePLMManquanteTests(unittest.TestCase):
    def test_sans_cle_leve_indisponible(self):
        with mock.patch.object(_svc, 'GROQ_API_KEY', ''):
            with self.assertRaises(_svc.PlanTachesIndisponible):
                _svc._build_llm()

    def test_generer_plan_taches_sans_cle_leve_indisponible(self):
        with mock.patch.object(_svc, 'GROQ_API_KEY', ''):
            with self.assertRaises(_svc.PlanTachesIndisponible):
                _svc.generer_plan_taches(
                    {'nb_lignes_materiel': 3, 'nb_lignes_main_oeuvre': 1},
                    'residentiel')

    def test_provider_inconnu_leve_indisponible(self):
        with mock.patch.object(_svc, 'SQL_AGENT_PROVIDER', 'inconnu'):
            with self.assertRaises(_svc.PlanTachesIndisponible):
                _svc._build_llm()


@unittest.skipUnless(_OK, f"plan_taches_service indisponible: {_ERR}")
class ParserReponseLlmTests(unittest.TestCase):
    def test_json_pur(self):
        out = _svc._parser_reponse_llm('{"taches": []}')
        self.assertEqual(out, {'taches': []})

    def test_json_entoure_de_texte(self):
        texte = 'Voici le plan : {"taches": [{"code": "1"}]} merci.'
        out = _svc._parser_reponse_llm(texte)
        self.assertEqual(out['taches'][0]['code'], '1')

    def test_sans_json_leve_valueerror(self):
        with self.assertRaises(ValueError):
            _svc._parser_reponse_llm('pas de json ici')


@unittest.skipUnless(_OK, f"plan_taches_service indisponible: {_ERR}")
class ValiderPlanTests(unittest.TestCase):
    def test_plan_valide_normalise(self):
        plan = {
            'taches': [
                {'code': '1', 'libelle': 'Étude', 'phase': 'ETUDE',
                 'duree_jours': '3', 'dependances_fs': []},
                {'code': '2', 'libelle': 'Pose', 'phase': 'pose',
                 'duree_jours': 5, 'dependances_fs': ['1']},
            ]
        }
        out = _svc._valider_plan(plan)
        self.assertEqual(len(out['taches']), 2)
        self.assertEqual(out['taches'][0]['phase'], 'etude')
        self.assertEqual(out['taches'][0]['duree_jours'], 3)
        self.assertEqual(out['taches'][1]['dependances_fs'], ['1'])

    def test_phase_inconnue_repliee_sur_etude(self):
        plan = {'taches': [{'code': '1', 'libelle': 'X', 'phase': 'inconnue'}]}
        out = _svc._valider_plan(plan)
        self.assertEqual(out['taches'][0]['phase'], 'etude')

    def test_dependance_vers_code_inexistant_retiree(self):
        plan = {
            'taches': [
                {'code': '1', 'libelle': 'X', 'dependances_fs': ['999']},
            ]
        }
        out = _svc._valider_plan(plan)
        self.assertEqual(out['taches'][0]['dependances_fs'], [])

    def test_auto_dependance_retiree(self):
        plan = {
            'taches': [
                {'code': '1', 'libelle': 'X', 'dependances_fs': ['1']},
            ]
        }
        out = _svc._valider_plan(plan)
        self.assertEqual(out['taches'][0]['dependances_fs'], [])

    def test_tache_sans_libelle_ignoree(self):
        plan = {'taches': [{'code': '1', 'libelle': ''}]}
        with self.assertRaises(ValueError):
            _svc._valider_plan(plan)

    def test_plan_sans_taches_leve_valueerror(self):
        with self.assertRaises(ValueError):
            _svc._valider_plan({'taches': 'pas une liste'})

    def test_duree_negative_repliee_sur_1(self):
        plan = {'taches': [{'code': '1', 'libelle': 'X', 'duree_jours': -5}]}
        out = _svc._valider_plan(plan)
        self.assertEqual(out['taches'][0]['duree_jours'], 1)


@unittest.skipUnless(_OK, f"plan_taches_service indisponible: {_ERR}")
class GenererPlanTachesIntegrationTests(unittest.TestCase):
    """Bout-en-bout avec un LLM factice (pas de réseau)."""

    def test_llm_repond_plan_exploitable(self):
        class _FakeLLM:
            def invoke(self, prompt):
                class _R:
                    content = (
                        '{"taches": [{"code": "1", "libelle": "Étude", '
                        '"phase": "etude", "duree_jours": 2, '
                        '"dependances_fs": []}]}')
                return _R()

        with mock.patch.object(_svc, 'GROQ_API_KEY', 'fake-key'), \
                mock.patch.object(_svc, '_build_llm', return_value=_FakeLLM()):
            plan = _svc.generer_plan_taches(
                {'nb_lignes_materiel': 2, 'nb_lignes_main_oeuvre': 1}, 'residentiel')
        self.assertEqual(len(plan['taches']), 1)
        self.assertEqual(plan['taches'][0]['libelle'], 'Étude')

    def test_llm_repond_texte_inexploitable_leve_valueerror(self):
        class _FakeLLM:
            def invoke(self, prompt):
                class _R:
                    content = 'ceci n\'est pas du JSON'
                return _R()

        with mock.patch.object(_svc, 'GROQ_API_KEY', 'fake-key'), \
                mock.patch.object(_svc, '_build_llm', return_value=_FakeLLM()):
            with self.assertRaises(ValueError):
                _svc.generer_plan_taches({}, 'residentiel')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
