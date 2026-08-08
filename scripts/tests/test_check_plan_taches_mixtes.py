"""Tests PACT12 — scripts/check_plan_taches_mixtes.py.

Stdlib pur (unittest), aucune base de donnees, aucun Django, aucun git requis.
Lancer :
    python -m unittest scripts.tests.test_check_plan_taches_mixtes -v

Le fait que cette garde devait empecher : en juillet 2026,
`docs/FRONTEND_GAP_PLAN.md` a constate que « the paired frontend half of each
task was never built, EVEN THOUGH most tasks named a `frontend/` file in their
own Files: line ». 147 taches de rattrapage ecrites, 145 encore ouvertes un
mois plus tard.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_plan_taches_mixtes as mixtes  # noqa: E402


def ecrire(chemin: Path, texte: str) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8", newline="\n")
    return chemin


class LectureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, *lignes):
        return [ecrire(self.base / "docs" / "PLAN.md",
                       "# BUILD QUEUE\n\n" + "\n".join(lignes) + "\n")]

    def test_une_tache_qui_ne_nomme_qu_un_cote_n_est_pas_mixte(self):
        plan = self._plan("- [x] X1 — back seul. "
                          "Files: `backend/django_core/apps/ao/urls.py`.")
        self.assertEqual(mixtes.taches_mixtes(plan), [])

    def test_une_tache_qui_nomme_les_deux_cotes_est_mixte(self):
        plan = self._plan("- [x] X2 — les deux. "
                          "Files: `backend/django_core/apps/ao/urls.py`, "
                          "`frontend/src/api/aoApi.js`.")
        lus = mixtes.taches_mixtes(plan)
        self.assertEqual(len(lus), 1)
        self.assertEqual(lus[0][2], "X2")
        self.assertTrue(lus[0][3])
        self.assertEqual(sorted(lus[0][4]), ["backend", "frontend"])

    def test_le_raccourci_apps_compte_comme_backend(self):
        plan = self._plan("- [ ] X3 — . Files: `apps/ao/selectors.py`, "
                          "`frontend/src/features/ao/E.jsx`.")
        self.assertEqual(sorted(mixtes.taches_mixtes(plan)[0][4]),
                         ["backend", "frontend"])

    def test_les_identifiants_a_trait_d_union_sont_lus(self):
        # `docs/FRONTEND_GAP_PLAN.md` nomme ses taches `FE-XFLT4`,
        # `FE-XFLT7/15/18` : sans cela, ses 145 taches etaient invisibles.
        plan = self._plan("- [ ] FE-XFLT7/15/18 — . "
                          "Files: `apps/flotte/urls.py`, "
                          "`frontend/src/api/flotteApi.js`.")
        self.assertEqual(mixtes.taches_mixtes(plan)[0][2], "FE-XFLT7/15/18")


class MoitieAbsenteTests(unittest.TestCase):
    """Le controle disponible PARTOUT : un fichier declare qui n'existe pas."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        ecrire(self.base / "backend" / "django_core" / "apps" / "flotte" / "urls.py",
               "urlpatterns = []\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, ligne):
        return [ecrire(self.base / "docs" / "PLAN.md",
                       f"# BUILD QUEUE\n\n{ligne}\n")]

    LIGNE = ("- [{etat}] FE-XFLT4 — onglet « Cycle de vie » + changerStatut. "
             "Files: `backend/django_core/apps/flotte/urls.py`, "
             "`frontend/src/api/flotteApi.js`.")

    def test_la_moitie_frontend_absente_est_NOMMEE(self):
        # LE cas de FRONTEND_GAP_PLAN : le backend est reel, teste, fusionne ;
        # la moitie frontend annoncee dans la MEME ligne Files: n'existe pas.
        constats = mixtes.moities_absentes(self.base, self._plan(
            self.LIGNE.format(etat="x")))
        self.assertEqual([s for s, _ in constats], ["FE-XFLT4|frontend"])
        message = constats[0][1]
        self.assertIn("FRONTEND", message)
        self.assertIn("frontend/src/api/flotteApi.js", message)
        self.assertIn("Seule la moitie backend", message)

    def test_une_tache_OUVERTE_n_est_jamais_accusee(self):
        # La garde parle de ce qui est COCHE. Une tache `[ ]` est du travail
        # a faire, pas un mensonge.
        self.assertEqual(mixtes.moities_absentes(
            self.base, self._plan(self.LIGNE.format(etat=" "))), [])

    def test_les_deux_moities_presentes_ne_produisent_rien(self):
        ecrire(self.base / "frontend" / "src" / "api" / "flotteApi.js", "export default {}\n")
        self.assertEqual(mixtes.moities_absentes(
            self.base, self._plan(self.LIGNE.format(etat="x"))), [])

    def test_un_seul_fichier_present_sur_un_cote_suffit(self):
        # Une tache qui nomme trois ecrans et n'en cree qu'un a bien livre
        # cette moitie : accuser serait deviner.
        ecrire(self.base / "frontend" / "src" / "api" / "flotteApi.js", "\n")
        ligne = ("- [x] X9 — . Files: `apps/flotte/urls.py`, "
                 "`frontend/src/api/flotteApi.js`, "
                 "`frontend/src/features/flotte/PasEncore.jsx`.")
        self.assertEqual(mixtes.moities_absentes(self.base, self._plan(ligne)), [])

    def test_le_raccourci_apps_est_resolu_sous_backend_django_core(self):
        # `apps/flotte/urls.py` et `backend/django_core/apps/flotte/urls.py`
        # designent le MEME fichier : ne pas le savoir accuserait a tort.
        ecrire(self.base / "frontend" / "src" / "api" / "flotteApi.js", "\n")
        ligne = ("- [x] X10 — . Files: `apps/flotte/urls.py`, "
                 "`frontend/src/api/flotteApi.js`.")
        self.assertEqual(mixtes.moities_absentes(self.base, self._plan(ligne)), [])


class EchantillonFrontendGapTests(unittest.TestCase):
    """PACT12 — verifie sur un ECHANTILLON REEL de `docs/FRONTEND_GAP_PLAN.md`.

    Ses 145 taches encore ouvertes sont le RATTRAPAGE ; les taches d'origine
    (X-series `XFLT/XQHS/XGED/XCTR/XPRJ/XPAI/XRH/XSAV/XACC`) nommaient bien un
    fichier `frontend/` dans leur propre ligne `Files:` et ont ete cochees avec
    la seule moitie backend livree. On rejoue exactement cette situation : la
    garde doit rougir, et NOMMER le cote manquant.
    """

    # Echantillon repris mot pour mot des lanes de docs/FRONTEND_GAP_PLAN.md
    # (domaine, client API annonce, ecran annonce).
    ECHANTILLON = [
        ("XFLT4", "flotte", "flotteApi.js", "VehiculeDetail.jsx"),
        ("XQHS7", "qhse", "qhseApi.js", "Environnement.jsx"),
        ("XGED11", "ged", "gedApi.js", "GedDocumentInsights.jsx"),
        ("XCTR3", "contrats", "contratsApi.js", "ContratDetail.jsx"),
        ("XPRJ9", "gestion_projet", "gestionProjetApi.js", "RessourcesPage.jsx"),
        ("XRH33", "rh", "rhApi.js", "Recrutement.jsx"),
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_chaque_tache_de_l_echantillon_est_refusee_sans_sa_moitie_frontend(self):
        lignes = []
        for tache, app, client, ecran in self.ECHANTILLON:
            # Backend REEL (« real, tested, and merged »), frontend absent.
            ecrire(self.base / "backend" / "django_core" / "apps" / app / "urls.py",
                   "urlpatterns = []\n")
            lignes.append(
                f"- [x] {tache} — build-out round 2. "
                f"Files: `backend/django_core/apps/{app}/urls.py`, "
                f"`frontend/src/api/{client}`, "
                f"`frontend/src/features/{app}/{ecran}`.")
        plan = [ecrire(self.base / "docs" / "PLAN.md",
                       "# BUILD QUEUE\n\n" + "\n".join(lignes) + "\n")]
        constats = mixtes.moities_absentes(self.base, plan)
        self.assertEqual(
            sorted(s for s, _ in constats),
            sorted(f"{t}|frontend" for t, *_ in self.ECHANTILLON))

    def test_la_meme_tache_avec_ses_DEUX_moities_passe(self):
        lignes = []
        for tache, app, client, ecran in self.ECHANTILLON:
            ecrire(self.base / "backend" / "django_core" / "apps" / app / "urls.py", "\n")
            ecrire(self.base / "frontend" / "src" / "api" / client, "\n")
            ecrire(self.base / "frontend" / "src" / "features" / app / ecran, "\n")
            lignes.append(
                f"- [x] {tache} — build-out round 2. "
                f"Files: `backend/django_core/apps/{app}/urls.py`, "
                f"`frontend/src/api/{client}`, "
                f"`frontend/src/features/{app}/{ecran}`.")
        plan = [ecrire(self.base / "docs" / "PLAN.md",
                       "# BUILD QUEUE\n\n" + "\n".join(lignes) + "\n")]
        self.assertEqual(mixtes.moities_absentes(self.base, plan), [])


class BaseEtDepotTests(unittest.TestCase):
    def test_la_base_ne_peut_que_retrecir(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "allow.txt"
            mixtes.ecrire_base({"X1|frontend"}, chemin)
            self.assertEqual(mixtes.charger_base(chemin), {"X1|frontend"})
            self.assertIn("NE PEUT QUE RETRECIR",
                          chemin.read_text(encoding="utf-8"))

    def test_le_depot_reel_ne_produit_aucun_constat(self):
        self.assertEqual(mixtes.moities_absentes(), [])

    def test_le_depot_reel_contient_bien_des_taches_mixtes(self):
        # Garde-fou de la LECTURE : si le parseur cassait, la garde deviendrait
        # verte en ne lisant RIEN — le defaut meme qu'elle combat.
        self.assertGreater(len(mixtes.taches_mixtes()), 20)

    def test_un_clone_superficiel_ne_produit_JAMAIS_de_faux_rouge(self):
        # Le job CI `stage-names` est un clone superficiel : la comparaison de
        # diff y est impossible et doit renvoyer None, jamais un constat.
        self.assertIsNone(mixtes.moities_non_touchees("ref/inexistante/xyz"))

    def test_l_entete_cite_le_constat_de_FRONTEND_GAP_PLAN(self):
        entete = Path(mixtes.__file__).read_text(encoding="utf-8")[:3000]
        self.assertIn("FRONTEND_GAP_PLAN", entete)
        self.assertIn("EVEN THOUGH", entete)


if __name__ == "__main__":
    unittest.main()
