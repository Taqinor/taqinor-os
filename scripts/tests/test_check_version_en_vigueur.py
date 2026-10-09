"""ACRM51 — scripts/check_version_en_vigueur.py.

    python -m unittest scripts.tests.test_check_version_en_vigueur -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_version_en_vigueur as guard  # noqa: E402

SANS_PREDICAT = '''
def ca_signe(lead):
    for devis in lead.devis.all():
        if devis.statut == 'accepte':
            return devis.total_ttc
'''

AVEC_IS_ACTIVE = '''
def ca_signe(lead):
    return [d for d in lead.devis.all()
            if d.statut == 'accepte' and d.is_active]
'''

AVEC_PREDICAT = '''
def ca_signe(lead):
    return [d for d in lead.devis.all() if _devis_compte_comme_signe(d)]
'''

REQUETE_SANS = '''
def lus(company):
    return Devis.objects.filter(company=company, statut='accepte')
'''

REQUETE_AVEC = '''
def lus(company):
    return Devis.objects.filter(company=company, statut='accepte',
                                is_active=True)
'''


class DetectionTests(unittest.TestCase):
    def test_lecture_sans_is_active_detectee(self):
        self.assertEqual(
            [f for _l, f in guard.analyser_source(SANS_PREDICAT)], ['ca_signe'])
        self.assertEqual(
            [f for _l, f in guard.analyser_source(REQUETE_SANS)], ['lus'])

    def test_lecture_avec_version_en_vigueur_acceptee(self):
        for src in (AVEC_IS_ACTIVE, AVEC_PREDICAT, REQUETE_AVEC):
            self.assertEqual(guard.analyser_source(src), [], src)

    def test_la_garde_nomme_la_ligne(self):
        violations, _ = guard.evaluer({"x.py": SANS_PREDICAT}, {})
        self.assertEqual(len(violations), 1)
        self.assertIn("x.py:4", violations[0])

    def test_exception_nommee_et_cle_morte(self):
        violations, mortes = guard.evaluer(
            {"x.py": SANS_PREDICAT}, {"x.py::ca_signe": "raison"})
        self.assertEqual((violations, mortes), ([], []))
        _, mortes = guard.evaluer({"x.py": AVEC_IS_ACTIVE},
                                  {"x.py::ca_signe": "raison"})
        self.assertEqual(mortes, ["x.py::ca_signe"])

    def test_accepter_toute_ligne_avec_accepte_est_refuse(self):
        """Test-du-test : une simple mention de 'accepte' (hors lecture de
        statut) n'est pas une violation, et une lecture l'est."""
        self.assertEqual(guard.analyser_source("x = 'accepte'\n"), [])
        self.assertTrue(guard.analyser_source(SANS_PREDICAT))


class DepotTests(unittest.TestCase):
    def test_depot_vert(self):
        self.assertEqual(guard.main([]), 0)

    def test_liste_blanche_vide_nomme_les_sites(self):
        sources = {rel: (ROOT / rel).read_text(encoding="utf-8")
                   for rel in guard.FICHIERS if (ROOT / rel).exists()}
        violations, _ = guard.evaluer(sources, {})
        self.assertGreaterEqual(len(violations), len(guard.ALLOWLIST))


if __name__ == "__main__":
    unittest.main()
