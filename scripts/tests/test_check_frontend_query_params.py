"""Tests de scripts/check_frontend_query_params.py (ENF, décision D1 du 09/10/2026).

Stdlib pur (unittest), aucune base, aucun Django, aucun node. Lancer :
    python -m unittest scripts.tests.test_check_frontend_query_params -v

Chaque test bâtit un mini-frontend dans un dossier temporaire + un extrait de
contrat (section ``query_params:`` de docs/openapi-schema.yml) et vérifie le
verdict : un paramètre déclaré passe, un non déclaré échoue, une expression
illisible est LISTÉE (jamais ignorée), l'intercepteur ``?entite=`` est modélisé.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_frontend_query_params as fqp  # noqa: E402

CONTRAT = """operations:
- get /api/django/crm/leads/ -> crm_leads_list
- get /api/django/crm/leads/{id}/ -> crm_leads_retrieve
- get /api/django/crm/leads/doublons/ -> crm_leads_doublons
- post /api/django/crm/leads/{id}/noter/ -> crm_leads_noter
query_params:
  get /api/django/crm/leads/: page search
  get /api/django/crm/leads/doublons/: archived
components:
- Lead
"""

AXIOS = """const ENDPOINTS_ENTITE = [
  /\\/crm\\/leads\\/$/,
]
"""


class Fixture:
    def __init__(self, fichiers: dict):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        self.chemins = []
        for nom, texte in fichiers.items():
            chemin = self.racine / nom
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(texte, encoding="utf-8")
            self.chemins.append(chemin)

    def analyser(self, contrat=CONTRAT, axios=""):
        try:
            return fqp.analyser(self.chemins, contrat, axios)
        finally:
            self.tmp.cleanup()


def noms_constats(constats):
    return sorted((c[3], c[2]) for c in constats)


class ContratTests(unittest.TestCase):
    def test_section_query_params_lue_par_operation(self):
        contrat = fqp.charger_contrat(CONTRAT)
        self.assertEqual(contrat[("get", ("api", "django", "crm", "leads"))],
                         frozenset({"page", "search"}))
        # opération connue SANS paramètre déclaré : ensemble vide, pas absente
        self.assertEqual(contrat[("get", ("api", "django", "crm", "leads", "{}"))], frozenset())

    def test_segment_litteral_prefere_au_gabarit(self):
        c = fqp.Contrat(fqp.charger_contrat(CONTRAT))
        self.assertEqual(c.autorises("get", ("api", "django", "crm", "leads", "doublons")),
                         frozenset({"archived"}))
        self.assertIsNone(c.autorises("get", ("api", "django", "inconnu")))


class VerdictTests(unittest.TestCase):
    def test_parametre_declare_passe(self):
        f = Fixture({"api/crmApi.js":
                     "import api from './axios'\n"
                     "export const crmApi = {\n"
                     "  liste: () => api.get('/crm/leads/', { params: { search: 'x', page: 2 } }),\n"
                     "}\n"})
        constats, non_resolus, stats = f.analyser()
        self.assertEqual(constats, [])
        self.assertEqual(non_resolus, [])
        self.assertEqual(stats["parametres_verifies"], 2)

    def test_parametre_non_declare_echoue_avec_fichier_et_ligne(self):
        f = Fixture({"api/crmApi.js":
                     "import api from './axios'\n"
                     "export const liste = () =>\n"
                     "  api.get('/crm/leads/', { params: { statut: 'x' } })\n"})
        constats, _, _ = f.analyser()
        self.assertEqual(noms_constats(constats), [("statut", "/api/django/crm/leads/")])
        self.assertTrue(constats[0][0].endswith("api/crmApi.js:3"))

    def test_chaine_de_requete_litterale_et_format_plateforme(self):
        f = Fixture({"a.js":
                     "import api from './axios'\n"
                     "export const x = (id) => api.get(`/crm/leads/${id}/?format=json&mode=${id}`)\n"})
        constats, _, _ = f.analyser()
        # `format` est honoré par DRF partout ; `mode` n'est pas déclaré
        self.assertEqual(noms_constats(constats), [("mode", "/api/django/crm/leads/{…}/")])

    def test_passe_plat_remonte_aux_appelants(self):
        f = Fixture({
            "api/crmApi.js":
                "import api from './axios'\n"
                "export const crmApi = {\n"
                "  getLeads: (params) => api.get('/crm/leads/', { params }),\n"
                "}\n",
            "pages/Leads.jsx":
                "import { crmApi } from '../api/crmApi'\n"
                "export function Leads() {\n"
                "  crmApi.getLeads({ search: 'a', inconnu: 1 })\n"
                "  return <p>l'écran</p>\n"
                "}\n"})
        constats, non_resolus, _ = f.analyser()
        self.assertEqual(noms_constats(constats), [("inconnu", "/api/django/crm/leads/")])
        self.assertIn("pages/Leads.jsx:3", constats[0][4])
        self.assertEqual(non_resolus, [])

    def test_objet_mute_et_fonction_d_ordre_superieur(self):
        f = Fixture({
            "api/crmApi.js":
                "import api from './axios'\n"
                "export const crmApi = {\n"
                "  getLeads: (params) => api.get('/crm/leads/', { params }),\n"
                "}\n",
            "pages/Leads.jsx":
                "import { crmApi } from '../api/crmApi'\n"
                "const toutes = (appel, params) => appel({ ...params, page: 1 })\n"
                "export function Leads(q) {\n"
                "  const p = {}\n"
                "  if (q) p.search = q\n"
                "  p['tri'] = 1\n"
                "  return toutes(crmApi.getLeads, p)\n"
                "}\n"})
        constats, non_resolus, _ = f.analyser()
        self.assertEqual(noms_constats(constats), [("tri", "/api/django/crm/leads/")])
        self.assertEqual(non_resolus, [])

    def test_expression_illisible_est_listee_jamais_ignoree(self):
        f = Fixture({"a.js":
                     "import api from './axios'\n"
                     "export const x = (f) => api.get('/crm/leads/', { params: construire(f) })\n"
                     "x(1)\n"})
        constats, non_resolus, _ = f.analyser()
        self.assertEqual(constats, [])
        self.assertEqual(len(non_resolus), 1)
        self.assertIn("construire(f)", non_resolus[0][1])

    def test_declaration_statique_est_verifiee_pas_exemptee(self):
        f = Fixture({"a.js":
                     "import api from './axios'\n"
                     "export const x = (f) =>\n"
                     "  // parametres-requete: search, cache\n"
                     "  api.get('/crm/leads/', { params: construire(f) })\n"})
        constats, non_resolus, _ = f.analyser()
        self.assertEqual(non_resolus, [])
        self.assertEqual(noms_constats(constats), [("cache", "/api/django/crm/leads/")])

    def test_url_servie_declaree_par_gabarits(self):
        f = Fixture({"a.js":
                     "import api from './axios'\n"
                     "export const x = (endpoint) =>\n"
                     "  // chemins-requete: /crm/leads/doublons/ /crm/leads/\n"
                     "  api.get(endpoint, { params: { archived: 1 } })\n"})
        constats, non_resolus, _ = f.analyser()
        self.assertEqual(non_resolus, [])
        # déclaré sur doublons/, PAS sur la liste : vérifié contre CHAQUE gabarit
        self.assertEqual(noms_constats(constats), [("archived", "/api/django/crm/leads/")])

    def test_intercepteur_entite_modele(self):
        source = {"a.js": "import api from './axios'\n"
                          "export const x = () => api.get('/crm/leads/')\n"
                          "export const y = () => api.post('/crm/leads/')\n"}
        constats, _, _ = Fixture(source).analyser(axios=AXIOS)
        # GET seulement (l'intercepteur ne touche que les GET de la liste blanche)
        self.assertEqual(noms_constats(constats), [("entite", "/api/django/crm/leads/")])
        declare = CONTRAT.replace("get /api/django/crm/leads/: page search",
                                  "get /api/django/crm/leads/: entite page search")
        constats, _, _ = Fixture(source).analyser(contrat=declare, axios=AXIOS)
        self.assertEqual(constats, [])

    def test_apostrophe_de_texte_jsx_ne_masque_pas_le_fichier(self):
        f = Fixture({"pages/P.jsx":
                     "import api from '../api/axios'\n"
                     "export function P() {\n"
                     "  const t = <p>l'automatisation d'un écran</p>\n"
                     "  api.get('/crm/leads/', { params: { cache: 1 } })\n"
                     "  return t\n"
                     "}\n"})
        constats, _, _ = f.analyser()
        self.assertEqual(noms_constats(constats), [("cache", "/api/django/crm/leads/")])


class ExceptionsTests(unittest.TestCase):
    def test_raison_obligatoire_et_lecture(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "allow.txt"
            chemin.write_text("# commentaire\nECHEC|a.js|GET|/x/|y  # raison\nNON-RESOLU|b.js|z\n",
                              encoding="utf-8")
            self.assertEqual(fqp.charger_exceptions(chemin),
                             {"ECHEC|a.js|GET|/x/|y": "raison", "NON-RESOLU|b.js|z": ""})


class DepotReelTests(unittest.TestCase):
    def test_le_depot_reel_s_analyse_en_moins_de_30_s(self):
        import time
        debut = time.monotonic()
        _, _, stats = fqp.analyser()
        self.assertLess(time.monotonic() - debut, 30)
        self.assertGreater(stats["appels"], 1000)
        self.assertGreater(stats["parametres_verifies"], 300)


if __name__ == "__main__":
    unittest.main()
