"""Tests ADOC79 — scripts/check_ip_primitive.py.

Stdlib pure (unittest), aucune base. Run :
    python -m unittest scripts.tests.test_check_ip_primitive -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_ip_primitive as guard  # noqa: E402

LECTURE = """
def _adresse_ip_requete(request):
    return request.META.get('REMOTE_ADDR') or ''
"""

DOCSTRING_SEULE = '''
def f(request):
    """Ne lit jamais REMOTE_ADDR ; renvoie ip_de_requete."""
    # HTTP_X_FORWARDED_FOR n'est cite que dans ce commentaire
    return ip_de_requete(request)
'''


class Depot(unittest.TestCase):
    def _monter(self, fichiers):
        tmp = Path(tempfile.mkdtemp())
        django = tmp / "backend" / "django_core"
        for rel, contenu in fichiers.items():
            cible = django / rel
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(contenu, encoding="utf-8")
        sauve = (guard.ROOT, guard.DJANGO_CORE)
        guard.ROOT, guard.DJANGO_CORE = tmp, django

        def restaurer():
            guard.ROOT, guard.DJANGO_CORE = sauve
        self.addCleanup(restaurer)


class TestGarde(Depot):
    def test_lecture_remote_addr_hors_primitive_refusee(self):
        self._monter({"apps/ged/services.py": LECTURE})
        echecs = guard.verifier(exceptions=set())
        self.assertEqual(len(echecs), 1, echecs)
        self.assertIn("apps/ged/services.py:3", echecs[0])
        self.assertIn("REMOTE_ADDR", echecs[0])
        self.assertIn("ip_de_requete", echecs[0])

    def test_cles_forwarded_et_cloudflare_refusees(self):
        self._monter({"apps/x/a.py": "m.get('HTTP_X_FORWARDED_FOR')\n",
                      "apps/x/b.py": "m.get('HTTP_CF_CONNECTING_IP')\n"})
        echecs = guard.verifier(exceptions=set())
        self.assertEqual(len(echecs), 2, echecs)

    def test_primitive_autorisee(self):
        self._monter({"core/throttling.py": LECTURE})
        self.assertEqual(guard.verifier(exceptions=set()), [])

    def test_retirer_la_primitive_de_l_autorisation_fait_echouer(self):
        # Test-du-test : si la primitive n'etait plus exemptee, elle rougirait.
        self._monter({"core/throttling.py": LECTURE})
        sauve = guard.PRIMITIVE
        guard.PRIMITIVE = "autre/chemin.py"
        try:
            self.assertEqual(len(guard.verifier(exceptions=set())), 1)
        finally:
            guard.PRIMITIVE = sauve

    def test_exception_par_fichier_tolere_la_lecture(self):
        self._monter({"apps/crm/webhooks.py": LECTURE})
        rel = "backend/django_core/apps/crm/webhooks.py"
        self.assertEqual(guard.verifier(exceptions={rel}), [])

    def test_exception_morte_refusee(self):
        self._monter({"apps/crm/webhooks.py": "x = 1\n"})
        rel = "backend/django_core/apps/crm/webhooks.py"
        echecs = guard.verifier(exceptions={rel})
        self.assertEqual(len(echecs), 1, echecs)
        self.assertIn("exception morte", echecs[0])

    def test_vider_les_exceptions_fait_echouer_sur_les_lecteurs_reels(self):
        # Mutation : sur le depot reel, sans liste d'exceptions, les 6
        # lecteurs historiques rougissent.
        self.assertGreaterEqual(len(guard.verifier(
            trouves=_depot_reel(), exceptions=set())), len(guard.EXCEPTIONS))

    def test_docstring_et_commentaire_ne_comptent_pas(self):
        self._monter({"apps/x/doc.py": DOCSTRING_SEULE})
        self.assertEqual(guard.verifier(exceptions=set()), [])

    def test_tests_et_migrations_hors_perimetre(self):
        self._monter({"apps/x/tests/test_ip.py": LECTURE,
                      "apps/x/migrations/0001_ip.py": LECTURE,
                      "apps/x/tests.py": LECTURE})
        self.assertEqual(guard.verifier(exceptions=set()), [])


def _depot_reel():
    sauve = (guard.ROOT, guard.DJANGO_CORE)
    guard.ROOT = ROOT
    guard.DJANGO_CORE = ROOT / "backend" / "django_core"
    try:
        return guard.balayer()
    finally:
        guard.ROOT, guard.DJANGO_CORE = sauve


class TestDepotReel(unittest.TestCase):
    def test_depot_reel_vert(self):
        sauve = (guard.ROOT, guard.DJANGO_CORE)
        guard.ROOT = ROOT
        guard.DJANGO_CORE = ROOT / "backend" / "django_core"
        try:
            self.assertEqual(guard.verifier(), [])
        finally:
            guard.ROOT, guard.DJANGO_CORE = sauve


if __name__ == "__main__":
    unittest.main()
