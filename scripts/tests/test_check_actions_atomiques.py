"""ACRM54 — scripts/check_actions_atomiques.py.

    python -m unittest scripts.tests.test_check_actions_atomiques -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_actions_atomiques as guard  # noqa: E402

SERVICES = '''
def ecrire_a(lead):
    lead.save()

def ecrire_b(lead):
    Modele.objects.create(lead=lead)

def ecrire_via_a(lead):
    ecrire_a(lead)

def lire(lead):
    d = {}
    d.update({'x': 1})
    return d
'''

VUE_SANS_ATOMIC = '''
from .services import ecrire_a, ecrire_b

class V(ViewSet):
    @action(detail=True, methods=['post'])
    def geste(self, request, pk=None):
        ecrire_a(1)
        ecrire_b(1)
'''

VUE_AVEC_ATOMIC = VUE_SANS_ATOMIC.replace(
    "        ecrire_a(1)\n        ecrire_b(1)\n",
    "        with transaction.atomic():\n            ecrire_a(1)\n"
    "            ecrire_b(1)\n")

VUE_DECOREE = VUE_SANS_ATOMIC.replace(
    "    @action(detail=True, methods=['post'])\n",
    "    @action(detail=True, methods=['post'])\n    @_geste_atomique\n")

VUE_UNE_ECRITURE = '''
from .services import ecrire_a, lire

class V(ViewSet):
    @action(detail=True, methods=['post'])
    def geste(self, request, pk=None):
        lire(1)
        ecrire_a(1)
'''

VUE_GET = VUE_SANS_ATOMIC.replace("methods=['post']", "methods=['get']")

VUE_HELPER = '''
from .services import ecrire_a, ecrire_b

class V(ViewSet):
    def _marquer(self, request):
        ecrire_a(1)
        ecrire_b(1)

    @action(detail=True, methods=['post'])
    def geste(self, request, pk=None):
        return self._marquer(request)
'''


def _symboles(vue):
    return [s for s, _l, _n in guard.analyser(vue, SERVICES)]


class DetectionTests(unittest.TestCase):
    def test_action_multi_ecriture_sans_atomic_detectee(self):
        self.assertEqual(_symboles(VUE_SANS_ATOMIC), ['V.geste'])

    def test_atomic_with_ou_decorateur_accepte(self):
        self.assertEqual(_symboles(VUE_AVEC_ATOMIC), [])
        self.assertEqual(_symboles(VUE_DECOREE), [])

    def test_une_seule_ecriture_ou_get_hors_perimetre(self):
        self.assertEqual(_symboles(VUE_UNE_ECRITURE), [])
        self.assertEqual(_symboles(VUE_GET), [])

    def test_helper_non_atomique_detecte(self):
        self.assertEqual(_symboles(VUE_HELPER), ['V.geste'])
        ok = VUE_HELPER.replace("    def _marquer", "    @_geste_atomique\n    def _marquer")
        self.assertEqual(_symboles(ok), [])

    def test_fonctions_d_ecriture_cloture_transitive_sans_dict_update(self):
        self.assertEqual(guard.fonctions_d_ecriture(SERVICES),
                         {'ecrire_a', 'ecrire_b', 'ecrire_via_a'})

    def test_seuil_de_deux_ecritures(self):
        """Test-du-test : avec un seuil de trois, le cas témoin ne serait
        plus signalé — ici il l'est (deux écritures suffisent)."""
        self.assertEqual(len({'ecrire_a', 'ecrire_b'}), 2)
        self.assertTrue(_symboles(VUE_SANS_ATOMIC))

    def test_liste_blanche_et_cle_morte(self):
        cle = f"{guard.VIEWS_REL}::V.geste"
        v, m = guard.evaluer(VUE_SANS_ATOMIC, SERVICES, {cle: "raison"})
        self.assertEqual((v, m), ([], []))
        v, m = guard.evaluer(VUE_AVEC_ATOMIC, SERVICES, {cle: "raison"})
        self.assertEqual(m, [cle])


class DepotTests(unittest.TestCase):
    def test_depot_vert(self):
        self.assertEqual(guard.main([]), 0)

    def test_retirer_l_atomic_de_marquer_nomme_l_action(self):
        vues = (ROOT / guard.VIEWS_REL).read_text(encoding="utf-8")
        services = guard.source_services()
        casse = vues.replace("@_geste_atomique\n    def _marquer",
                             "def _marquer", 1)
        self.assertNotEqual(vues, casse)
        violations, _ = guard.evaluer(casse, services, {})
        self.assertTrue(any("RelanceEtapeViewSet" in v for v in violations))


if __name__ == "__main__":
    unittest.main()
