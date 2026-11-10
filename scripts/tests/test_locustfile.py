"""ADCG73 — scénarios Locust (`load/locustfile.py`) : aucune requête vouée au 4xx.

Faux client HTTP (aucun serveur, Locust non requis : le fichier porte ses shims).
    python -m unittest scripts.tests.test_locustfile -v
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _module():
    spec = importlib.util.spec_from_file_location("locustfile_adcg73", ROOT / "load" / "locustfile.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Reponse:
    def __init__(self, status_code=200, corps=None):
        self.status_code = status_code
        self._corps = corps or {}

    def json(self):
        return self._corps


class _FauxClient:
    def __init__(self, count):
        self.count = count
        self.appels = []

    def get(self, url, name=None):
        self.appels.append(("GET", url, None))
        return _Reponse(200, {"count": self.count, "results": []})

    def post(self, url, json=None, name=None):
        self.appels.append(("POST", url, json))
        return _Reponse(201, {"id": 7})


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.mod = _module()

    def _utilisateur(self, count):
        user = self.mod.ErpUser.__new__(self.mod.ErpUser)  # sans environnement Locust
        user.client = _FauxClient(count)
        return user

    def test_page_tiree_dans_les_bornes_du_compte(self):
        user = self._utilisateur(60)  # 60 leads, pages de 50 => {1, 2}
        for _ in range(200):
            user.liste_leads()
        pages = {int(url.rsplit("page=", 1)[1]) for _, url, _ in user.client.appels}
        self.assertEqual(pages, {1, 2})

    def test_base_vide_reste_sur_la_page_1(self):
        user = self._utilisateur(0)
        for _ in range(20):
            user.liste_leads()
        self.assertEqual({url for _, url, _ in user.client.appels}, {"/api/django/crm/leads/?page=1"})

    def test_client_cree_avec_un_email_unique_puis_devis_sur_ce_client(self):
        user = self._utilisateur(0)
        user.on_start()
        creation = [c for c in user.client.appels if c[1] == "/api/django/crm/clients/"]
        self.assertEqual(len(creation), 1)
        self.assertTrue(creation[0][2]["email"].endswith("@taqinor.local"))
        user.creation_devis()
        self.assertEqual(user.client.appels[-1][2]["client"], 7)

    def test_sans_client_aucun_devis_voue_au_400(self):
        user = self._utilisateur(0)
        user.client_id = None
        user.creation_devis()
        self.assertEqual(user.client.appels, [])


if __name__ == "__main__":
    unittest.main()
