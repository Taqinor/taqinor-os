"""Tests CALX2 — les quatre surfaces APPEND-ONLY du module « calepinage ».

CE QU'ILS PROTÈGENT
-------------------
``scripts/plan_lanes.py`` unionne deux lanes dès que deux tâches déclarent le
MÊME fichier dans leur ``Files:`` — sinon elles se collisionnent au fold.
Quatre surfaces du module calepinage sont partagées PAR CONSTRUCTION et
APPEND-ONLY (décision D-CALX 13, 21/09/2026) : une capacité neuve s'y ajoute
par UNE ligne écrite en fin, donc deux tâches ne s'y marchent jamais dessus.
Sans l'exemption, mesuré sur ``docs/PLAN2.md`` : 13 des 16 fusions de lanes du
groupe CALX venaient de ces seules surfaces, et la clé de pairage PACT11 sur
``urls.py`` faisait refuser les moitiés frontend.

Deux d'entre elles (``atelier/onglets.js``, ``services/parametres_cles.py``)
N'EXISTENT PAS ENCORE sur le disque : les règles sont purement TEXTUELLES
(suffixe du chemin déclaré), ce que ``test_la_regle_ne_touche_pas_le_disque``
prouve explicitement.

Pur stdlib (unittest), sans Django ni base. Run :
    python -m pytest scripts/tests/test_plan_lanes_append_only.py -q
    python -m unittest scripts.tests.test_plan_lanes_append_only -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import plan_lanes as pl  # noqa: E402


#: Les quatre suffixes posés par CALX2, et le chemin RÉEL du dépôt que chacun
#: doit attraper.
SURFACES_CALX2 = {
    "api/calepinageApi.js":
        "frontend/src/api/calepinageApi.js",
    "calepinage/atelier/onglets.js":
        "frontend/src/features/calepinage/atelier/onglets.js",
    "calepinage/views/rattachements.py":
        "backend/django_core/apps/calepinage/views/rattachements.py",
    "calepinage/services/parametres_cles.py":
        "backend/django_core/apps/calepinage/services/parametres_cles.py",
}

#: L'état de ``_APPEND_ONLY_SUFFIXES`` AVANT CALX2 — sert à prouver que ces
#: tests échoueraient sans le correctif (un test qui passerait aussi bien
#: avant qu'après ne prouve rien).
SUFFIXES_AVANT_CALX2 = (
    "index.css", "tokens.css", "print.css", "records-panels.css",
    "ui/index.js", "router/index.jsx", "main.jsx", "App.jsx",
    "docs/PLAN.md", "docs/PLAN2.md", "docs/CODEMAP.md",
)

#: Un mini-plan qui reproduit EXACTEMENT le défaut mesuré : trois lanes qui ne
#: partagent QUE des surfaces append-only du calepinage. Avant CALX2 elles se
#: fondaient en une ; après, elles restent trois. Écrit en fixture (et pas lu
#: du vrai plan) pour que le test survive au drain du groupe CALX.
PLAN_FIXTURE = """\
## BUILD QUEUE

- [ ] CALX901 — onglet A. Files: `frontend/src/api/calepinageApi.js`, \
`frontend/src/features/calepinage/atelier/onglets.js`, \
`backend/django_core/apps/calepinage/views/moteur.py` (@lane: backend/cal-a)
- [ ] CALX902 — onglet B. Files: `frontend/src/api/calepinageApi.js`, \
`frontend/src/features/calepinage/atelier/onglets.js`, \
`backend/django_core/apps/calepinage/views/rattachements.py`, \
`backend/django_core/apps/calepinage/views/sorties.py` (@lane: backend/cal-b)
- [ ] CALX903 — action C. Files: \
`backend/django_core/apps/calepinage/views/rattachements.py`, \
`backend/django_core/apps/calepinage/services/parametres_cles.py`, \
`backend/django_core/apps/calepinage/views/photos.py` (@lane: backend/cal-c)
"""


def _lanes_et_fusions(tasks):
    """Regroupe en lanes puis unionne comme ``schedule()`` le fait."""
    lanes = {}
    for t in tasks:
        if t["gate"] == "buildable" and t["lane"] != "UNASSIGNED":
            lanes.setdefault(t["lane"], []).append(t)
    fondues, fusions = pl._merge_lanes_by_shared_files(lanes)
    return fondues, fusions


class SuffixesAppendOnlyTest(unittest.TestCase):
    """Le test unitaire des quatre suffixes demandé par CALX2."""

    def test_les_quatre_suffixes_sont_declares(self):
        for suffixe in SURFACES_CALX2:
            with self.subTest(suffixe=suffixe):
                self.assertIn(suffixe, pl._APPEND_ONLY_SUFFIXES)

    def test_chaque_suffixe_attrape_le_chemin_reel_du_depot(self):
        for suffixe, chemin in SURFACES_CALX2.items():
            with self.subTest(suffixe=suffixe):
                self.assertTrue(
                    pl._is_append_only(chemin),
                    f"{chemin} n'est pas reconnu append-only : le suffixe "
                    f"« {suffixe} » ne correspond pas au chemin réel.")

    def test_les_surfaces_historiques_restent_append_only(self):
        """CALX2 AJOUTE, il ne retire rien (règle append-only appliquée à
        la règle elle-même)."""
        for suffixe in SUFFIXES_AVANT_CALX2:
            with self.subTest(suffixe=suffixe):
                self.assertIn(suffixe, pl._APPEND_ONLY_SUFFIXES)

    def test_les_voisins_ne_sont_pas_attrapes(self):
        """Une règle trop large rendrait tout le module co-schedulable."""
        voisins = (
            "frontend/src/api/crmApi.js",
            "frontend/src/api/calepinageApi.usage.test.mjs",
            "frontend/src/features/calepinage/atelier/Rail.jsx",
            "backend/django_core/apps/calepinage/views/calepinages.py",
            "backend/django_core/apps/calepinage/services/parametres.py",
            "backend/django_core/apps/ao/views/rattachements.py",
        )
        for chemin in voisins:
            with self.subTest(chemin=chemin):
                self.assertFalse(
                    pl._is_append_only(chemin),
                    f"{chemin} exempté à tort : seules les QUATRE surfaces "
                    "nommées par D-CALX 13 le sont.")

    def test_la_regle_ne_touche_pas_le_disque(self):
        """``onglets.js`` et ``parametres_cles.py`` n'existent pas encore.

        Ils sont créés par CALX1 et par des tâches ultérieures. La règle doit
        donc être purement TEXTUELLE : un chemin qui n'existera JAMAIS et qui
        porte le bon suffixe est reconnu tout autant.
        """
        for suffixe in SURFACES_CALX2:
            chemin_fantome = f"zzz/inexistant/{suffixe}"
            with self.subTest(suffixe=suffixe):
                self.assertFalse((ROOT / chemin_fantome).exists())
                self.assertTrue(pl._is_append_only(chemin_fantome))

    def test_task_files_les_retire_de_la_cle_de_fusion(self):
        ligne = (
            "- [ ] CALX999 — une tâche. Files: "
            "`frontend/src/api/calepinageApi.js`, "
            "`frontend/src/features/calepinage/atelier/onglets.js`, "
            "`backend/django_core/apps/calepinage/views/rattachements.py`, "
            "`backend/django_core/apps/calepinage/services/"
            "parametres_cles.py`, "
            "`backend/django_core/apps/calepinage/views/moteur.py`")
        self.assertEqual(
            pl._task_files(ligne),
            frozenset({"backend/django_core/apps/calepinage/views/moteur.py"}),
            "Seuls les fichiers SUBSTANTIFS doivent rester : les quatre "
            "surfaces append-only ne forcent aucune fusion de lanes.")


class LanesNonFonduesTest(unittest.TestCase):
    """Deux tâches qui ne partagent QUE ces surfaces restent séparées."""

    def _tasks(self, texte):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "PLAN_FIXTURE.md"
            chemin.write_text(texte, encoding="utf-8")
            return pl.parse_tasks(chemin)

    def test_trois_lanes_restent_trois(self):
        _, fusions = _lanes_et_fusions(self._tasks(PLAN_FIXTURE))
        self.assertEqual(
            fusions, [],
            f"Fusion(s) de lanes sur une surface append-only : {fusions}.")

    def test_sans_calx2_les_trois_lanes_se_fondaient_en_une(self):
        """La preuve que le test ci-dessus n'est pas vide."""
        avant = pl._APPEND_ONLY_SUFFIXES
        try:
            pl._APPEND_ONLY_SUFFIXES = SUFFIXES_AVANT_CALX2
            fondues, fusions = _lanes_et_fusions(self._tasks(PLAN_FIXTURE))
        finally:
            pl._APPEND_ONLY_SUFFIXES = avant
        self.assertEqual(len(fondues), 1)
        self.assertTrue(fusions)


class PlanReelTest(unittest.TestCase):
    """Le critère « Done » de CALX2, mesuré sur le VRAI ``docs/PLAN2.md``."""

    PLAN = ROOT / "docs" / "PLAN2.md"

    def setUp(self):
        if not self.PLAN.is_file():           # pragma: no cover
            self.skipTest("docs/PLAN2.md absent")
        self.tasks = pl.parse_tasks(self.PLAN)
        citations = {
            suffixe: sum(1 for t in self.tasks
                         for f in (t.get("files_bruts") or ())
                         if f.endswith(chemin))
            for suffixe, chemin in SURFACES_CALX2.items()
        }
        if not any(nombre >= 2 for nombre in citations.values()):
            self.skipTest(
                "Aucune des quatre surfaces n'est citée par deux tâches "
                "ouvertes : le groupe CALX est drainé, il n'y a plus rien à "
                f"prouver ici ({citations}).")
        self.citations = citations

    def test_aucune_tache_ne_les_porte_comme_cle_de_fusion(self):
        fautives = [
            (t["id"], f)
            for t in self.tasks
            for f in t.get("files", ())
            if f in set(SURFACES_CALX2.values())
        ]
        self.assertEqual(
            fautives, [],
            f"Surface append-only restée clé de fusion : {fautives}.")

    def test_plus_aucune_fusion_de_lanes_sur_ces_quatre_fichiers(self):
        _, fusions = _lanes_et_fusions(self.tasks)
        fautives = [triplet for triplet in fusions
                    if triplet[0] in set(SURFACES_CALX2.values())]
        self.assertEqual(
            fautives, [],
            "plan_lanes fond encore deux tâches sur une surface "
            f"append-only : {fautives}.")

    def test_sans_calx2_ces_fusions_existaient_bel_et_bien(self):
        """Encore la preuve de non-vacuité, sur le vrai plan cette fois."""
        avant = pl._APPEND_ONLY_SUFFIXES
        try:
            pl._APPEND_ONLY_SUFFIXES = SUFFIXES_AVANT_CALX2
            tasks = pl.parse_tasks(self.PLAN)
            _, fusions = _lanes_et_fusions(tasks)
        finally:
            pl._APPEND_ONLY_SUFFIXES = avant
        fautives = [triplet for triplet in fusions
                    if triplet[0] in set(SURFACES_CALX2.values())]
        self.assertTrue(
            fautives,
            "Sans les suffixes CALX2, aucune fusion n'est constatée sur ces "
            "fichiers : la fixture ne mesure plus le défaut qu'elle garde "
            f"(citations = {self.citations}).")


class RailOngletsEstUnFichierDeMontageTest(unittest.TestCase):
    """CALX2 — ``check_taches_cablage.py`` admet le registre d'onglets.

    POURQUOI CE TEST VIT ICI et pas dans
    ``scripts/tests/test_check_taches_cablage.py`` : la tâche CALX2 ne
    m'autorise à écrire que les fichiers de son ``Files:``, et ce fichier-ci
    est le seul test ``scripts/`` qu'elle nomme. Le volet gardé est le même —
    la surface ``atelier/onglets.js`` — d'où le regroupement.

    Le rail d'onglets (décision D-CALX 3) est un REGISTRE ``.js`` : un panneau
    neuf s'y monte par une ligne ajoutée en fin. C'est donc bien un fichier de
    MONTAGE au sens de la garde, au même titre qu'un ``module.config.jsx`` —
    sans quoi toute tâche d'onglet du calepinage sortait en faux
    « écran-sans-câblage » (2 mesurés sur le bloc CALX).
    """

    @staticmethod
    def _tache(texte):
        import check_taches_cablage as ctc

        return ctc.Tache("docs/PLAN2.md", 1, " ", "CALX999", texte)

    def test_le_registre_monte_un_ecran_de_la_meme_feature(self):
        tache = self._tache(
            "- [ ] CALX999 — un onglet neuf de l'atelier. Files: "
            "`frontend/src/features/calepinage/atelier/PanneauX.jsx` "
            "(nouveau), "
            "`frontend/src/features/calepinage/atelier/onglets.js`")
        self.assertEqual(
            tache.fichier_de_montage(),
            "frontend/src/features/calepinage/atelier/onglets.js",
            "Le registre d'onglets doit compter comme fichier de montage "
            "d'un écran de `features/calepinage/**` (CALX2).")

    def test_le_registre_ne_monte_pas_un_ecran_d_une_autre_feature(self):
        """Un rail ne monte que les panneaux de SON module."""
        tache = self._tache(
            "- [ ] CALX998 — un écran ailleurs. Files: "
            "`frontend/src/features/ventes/EcranY.jsx` (nouveau), "
            "`frontend/src/features/calepinage/atelier/onglets.js`")
        self.assertIsNone(tache.fichier_de_montage())

    def test_un_module_config_garde_la_priorite(self):
        tache = self._tache(
            "- [ ] CALX997 — un écran routé. Files: "
            "`frontend/src/features/calepinage/EcranZ.jsx` (nouveau), "
            "`frontend/src/features/calepinage/module.config.jsx`, "
            "`frontend/src/features/calepinage/atelier/onglets.js`")
        self.assertEqual(
            tache.fichier_de_montage(),
            "frontend/src/features/calepinage/module.config.jsx")

    def test_le_registre_seul_ne_monte_rien(self):
        """Sans écran déclaré, il n'y a rien à monter — et rien à exempter."""
        tache = self._tache(
            "- [ ] CALX996 — juste le registre. Files: "
            "`frontend/src/features/calepinage/atelier/onglets.js`")
        self.assertIsNone(tache.fichier_de_montage())


if __name__ == "__main__":       # pragma: no cover
    unittest.main()
