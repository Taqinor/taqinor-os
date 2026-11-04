"""NTDATA12 — metriques gouvernees offertes a l'agent NL->SQL.

Reseau Django moque (unittest stdlib). A lancer depuis backend/fastapi_ia :

    python -m unittest tests.test_metriques_gouvernees
"""
import json
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import action_tools as at  # noqa: E402 — après sys.path (D-ENF22)
from app.services import metriques_gouvernees as mg  # noqa: E402 — après sys.path (D-ENF22)
from app.services.action_tools import ActionContext  # noqa: E402 — après sys.path (D-ENF22)

CATALOGUE = {"metriques": [
    {"cle": "dso", "libelle": "DSO", "description": "Délai moyen.",
     "unite": "jours"},
    {"cle": "marge_brute", "libelle": "Marge brute", "description": "",
     "unite": "MAD"},
    {"cle": "Pas Une Cle", "libelle": "x", "description": "", "unite": ""},
]}


def _ctx(token="jwt-xyz"):
    return ActionContext(company_id=7, role="responsable", permissions=[],
                         token=token)


class CatalogueTests(unittest.TestCase):
    def _catalogue(self, reponse, allow_price=False, token="jwt-xyz"):
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000"), \
                mock.patch.object(mg, "_django_call",
                                  return_value=reponse) as appel:
            out = mg.catalogue_metriques(_ctx(token), allow_price)
        return out, appel

    def test_catalogue_lu_chez_django_avec_le_jeton(self):
        out, appel = self._catalogue({"ok": True, "data": CATALOGUE})
        self.assertEqual(appel.call_args.args[1], mg.CATALOGUE_PATH)
        self.assertEqual(appel.call_args.kwargs["method"], "GET")
        self.assertEqual([m["cle"] for m in out], ["dso"])

    def test_marge_offerte_seulement_avec_le_droit(self):
        out, _ = self._catalogue({"ok": True, "data": CATALOGUE},
                                 allow_price=True)
        self.assertEqual([m["cle"] for m in out], ["dso", "marge_brute"])

    def test_django_injoignable_catalogue_vide(self):
        out, _ = self._catalogue({"ok": False, "status": 0, "error": "x"})
        self.assertEqual(out, [])

    def test_sans_jeton_aucun_appel(self):
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000"), \
                mock.patch.object(mg, "_django_call") as appel:
            self.assertEqual(mg.catalogue_metriques(_ctx(token="")), [])
        appel.assert_not_called()

    def test_description_cite_les_metriques(self):
        texte = mg.description_outil([
            {"cle": "dso", "libelle": "DSO", "description": "Délai moyen.",
             "unite": "jours"}])
        self.assertIn("PREFERE", texte)
        self.assertIn("- dso : DSO (jours) — Délai moyen.", texte)


class ValeurTests(unittest.TestCase):
    def test_valeur_lue_par_le_resolveur_serveur(self):
        reponse = {"ok": True, "data": {
            "cle": "dso", "libelle": "DSO", "unite": "jours", "valeur": 42.5}}
        with mock.patch.object(mg, "_django_call",
                               return_value=reponse) as appel:
            out = mg.lire_valeur(_ctx(), {"dso"}, "dso")
        self.assertEqual(out["valeur"], 42.5)
        self.assertEqual(appel.call_args.args[1],
                         "/api/django/semantic/metriques/dso/valeur/")
        self.assertEqual(appel.call_args.kwargs["payload"], {"group_by": ""})

    def test_cle_hors_catalogue_refusee_sans_appel(self):
        with mock.patch.object(mg, "_django_call") as appel:
            out = mg.lire_valeur(_ctx(), {"dso"}, "../auth/me")
        self.assertFalse(out["ok"])
        appel.assert_not_called()

    def test_outil_absent_sans_catalogue(self):
        with mock.patch.object(mg, "catalogue_metriques", return_value=[]):
            self.assertIsNone(mg.outil_metrique_gouvernee(_ctx()))

    def test_outil_langchain(self):
        try:
            __import__("langchain_core.tools")
        except ImportError:
            self.skipTest("langchain_core indisponible")
        catalogue = [{"cle": "dso", "libelle": "DSO", "description": "",
                      "unite": "jours"}]
        with mock.patch.object(mg, "catalogue_metriques",
                               return_value=catalogue), \
                mock.patch.object(mg, "_django_call", return_value={
                    "ok": True, "data": {"valeur": 3}}):
            outil = mg.outil_metrique_gouvernee(_ctx())
            sortie = json.loads(outil.func(cle="dso"))
        self.assertEqual(outil.name, "metrique_gouvernee")
        self.assertEqual(sortie["valeur"], 3)


if __name__ == "__main__":
    unittest.main()
