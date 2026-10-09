"""Tests ASEC47 — le formulaire de connexion de l'admin Django est limité par
`login_limit` (5 r/min), pas par `api_limit` (backend/nginx/nginx.conf).

Stdlib pure (unittest). Run :
    python -m unittest scripts.tests.test_nginx_asec47_admin_login -v
"""
import unittest

from scripts.tests.test_nginx_cache_control import (
    analyser,
    entetes_effectifs,
    location_pour,
    server_principal,
)

ENTETES_PROXY = ("Host", "X-Real-IP", "X-Forwarded-For", "X-Forwarded-Proto")


def _directives(enfants, nom):
    return [a for n, a, _ in enfants if n == nom]


class AdminLoginLimiteTests(unittest.TestCase):
    def setUp(self):
        self.arbre = analyser()
        self.server = server_principal(self.arbre)
        _, self.jumeau = location_pour(self.server, "/api/django/token/")

    def _verifier(self, uri):
        motif, loc = location_pour(self.server, uri)
        self.assertIn(["zone=login_limit", "burst=3", "nodelay"],
                      _directives(loc, "limit_req"), f"{uri} → {motif}")
        self.assertIn(["429"], _directives(loc, "limit_req_status"))
        self.assertIn(["http://django_backend"], _directives(loc, "proxy_pass"))
        entetes = {a[0]: a[1] for a in _directives(loc, "proxy_set_header")}
        jumeau = {a[0]: a[1] for a in _directives(self.jumeau, "proxy_set_header")}
        for nom in ENTETES_PROXY:
            self.assertEqual(entetes.get(nom), jumeau.get(nom), f"{uri} : {nom}")

    def test_location_admin_login_limitee(self):
        self._verifier("/api/django/admin/login/")

    def test_admin_url_personnalise_sous_api_django(self):
        self._verifier("/api/django/console-x7/login/")

    def test_reste_de_l_admin_inchange(self):
        motif, loc = location_pour(self.server, "/api/django/admin/ventes/devis/")
        self.assertEqual(motif, "/api/django/")
        self.assertIn(["zone=api_limit", "burst=30", "nodelay"],
                      _directives(loc, "limit_req"))

    def test_no_store_et_securite_sur_le_login_admin(self):
        entetes = entetes_effectifs(self.arbre, "/api/django/admin/login/")
        self.assertEqual(entetes.get("Cache-Control"), "no-store")
        self.assertIn("Content-Security-Policy", entetes)


if __name__ == "__main__":
    unittest.main()
