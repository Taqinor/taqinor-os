"""Tests de scripts/check_taches_cablage.py (garde de cablage du 03/08/2026).

Stdlib pur (unittest), aucune base de donnees, aucun node, aucun build. Lancer :
    python -m unittest scripts.tests.test_check_taches_cablage -v
    python -m pytest scripts/tests/test_check_taches_cablage.py -q

Chaque test correspond a un piege REEL rencontre en calibrant la garde sur les
13 fichiers de plan du depot. Une garde de cablage ne vaut RIEN si elle crie au
loup : une tache qui MODIFIE un ecran existant, une tache de suppression, une
tache qui livre un composant monte ailleurs, un ecran public a jeton et une
tache qui ETEND l'ecran cree par sa voisine sont toutes LEGITIMES. Les tests
ci-dessous verrouillent ces silences autant que les detections.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_taches_cablage as ctc  # noqa: E402


CLAUSE = ("**Et l'ecran est ATTEIGNABLE** : route declaree + entree de nav "
          "(ou onglet monte dans son ecran parent).")


def tache(identifiant, texte, files):
    return f"- [ ] {identifiant} — {texte} Files: {files}\n"


class FauxDepot:
    """Depot jetable : un fichier de plan + une arborescence frontend."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        (self.racine / "docs").mkdir(parents=True)
        self.src = self.racine / "frontend" / "src"
        (self.src / "features").mkdir(parents=True)
        self._sauvegarde = (ctc.ROOT, ctc.FRONT_SRC, ctc._INDEX_NOMS)
        ctc.ROOT = self.racine
        ctc.FRONT_SRC = self.src
        ctc._INDEX_NOMS = None

    def plan(self, *lignes) -> list:
        chemin = self.racine / "docs" / "PLAN.md"
        chemin.write_text("".join(lignes), encoding="utf-8")
        return ["docs/PLAN.md"]

    def ecran(self, relatif: str, contenu: str = "export default 1\n"):
        chemin = self.src / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu, encoding="utf-8")
        ctc._INDEX_NOMS = None
        return chemin

    def close(self):
        ctc.ROOT, ctc.FRONT_SRC, ctc._INDEX_NOMS = self._sauvegarde


class BaseDepot(unittest.TestCase):
    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.close)

    def constats(self, fichiers, forme=None):
        trouves, _ = ctc.analyse(fichiers, avec_doublons=False)
        return sorted(c.cible for c in trouves
                      if forme is None or c.forme == forme)

    def ecrans(self, fichiers):
        return self.constats(fichiers, ctc.FORME_ECRAN)


# ===========================================================================
# Lecture d'une ligne de tache
# ===========================================================================

class LectureTests(BaseDepot):
    def test_identifiants_reels_du_depot(self):
        fichiers = self.depot.plan(
            tache("PACT42", "x", "`a.py`"),
            tache("NTSRV4", "x", "`a.py`"),
            tache("VX198", "x", "`a.py`"),
            tache("FE-ZSTK6/12", "x", "`a.py`"),
        )
        self.assertEqual([t.identifiant for t in ctc.lire_taches(fichiers)],
                         ["PACT42", "NTSRV4", "VX198", "FE-ZSTK6/12"])

    def test_crochets_imbriques_dans_la_case(self):
        """Piege REEL (PLAN2.md:502) : `- [BLOCKED: ... [GATED ...]] VX198 — `.

        Un `\\[([^\\]]*)\\]` naif s'arrete au premier `]` et lit « ] VX198 »
        comme identifiant : la tache devient introuvable et jamais gardee.
        """
        fichiers = self.depot.plan(
            "- [BLOCKED: dev-dep manquante [GATED si dev-dep]] VX198 — x "
            "Files: `a.py`\n")
        taches = ctc.lire_taches(fichiers)
        self.assertEqual([t.identifiant for t in taches], ["VX198"])

    def test_tache_cochee_jamais_examinee(self):
        """On ne reecrit pas l'histoire : `[x]` est hors sujet, toujours."""
        fichiers = self.depot.plan(
            "- [x] PACT1 — x Files: `frontend/src/features/a/Neuf.jsx`\n")
        self.assertEqual(self.ecrans(fichiers), [])

    def test_tache_bloquee_reste_examinee(self):
        """`[BLOCKED]` n'est pas `[x]` : elle sera construite un jour."""
        fichiers = self.depot.plan(
            "- [BLOCKED: attend NTX1] PACT1 — x "
            "Files: `frontend/src/features/a/Neuf.jsx`\n")
        self.assertEqual(self.ecrans(fichiers), ["PACT1"])

    def test_sans_clause_files_aucune_alerte(self):
        """On sous-detecte, on n'invente pas."""
        fichiers = self.depot.plan(
            "- [ ] PACT1 — cree frontend/src/features/a/Neuf.jsx un jour\n")
        self.assertEqual(self.ecrans(fichiers), [])


# ===========================================================================
# FORME 1 — ce qui EST un ecran, et ce qui n'en est pas
# ===========================================================================

class EcranTests(BaseDepot):
    def test_creation_nue_est_signalee(self):
        fichiers = self.depot.plan(
            tache("PACT1", "Nouvel ecran.", "`frontend/src/features/a/Neuf.jsx`"))
        self.assertEqual(self.ecrans(fichiers), ["PACT1"])

    def test_montage_plus_clause_est_conforme(self):
        fichiers = self.depot.plan(tache(
            "PACT1", f"Nouvel ecran. {CLAUSE}",
            "`frontend/src/features/a/Neuf.jsx`, "
            "`frontend/src/features/a/module.config.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_montage_seul_ne_suffit_pas(self):
        """Sans clause, rien n'OBLIGE l'agent a declarer la route."""
        fichiers = self.depot.plan(tache(
            "PACT1", "Nouvel ecran.",
            "`frontend/src/features/a/Neuf.jsx`, "
            "`frontend/src/features/a/module.config.jsx`"))
        self.assertEqual(self.ecrans(fichiers), ["PACT1"])

    def test_clause_seule_ne_suffit_pas(self):
        """La regle du depot interdit de toucher un fichier hors `Files:` :
        exiger la route sans nommer le module.config, c'est l'interdire."""
        fichiers = self.depot.plan(tache(
            "PACT1", f"Nouvel ecran. {CLAUSE}",
            "`frontend/src/features/a/Neuf.jsx`"))
        self.assertEqual(self.ecrans(fichiers), ["PACT1"])

    def test_composant_partage_n_est_pas_un_ecran(self):
        """`components/`, `ui/`, `hooks/` ne se routent pas et n'ont pas de menu.

        Sans ce silence, chaque tache livrant un bouton partage rougirait —
        le faux positif qui ferait desactiver la garde.
        """
        for chemin in ("components/sav/Wizard.jsx", "ui/module/ListShell.jsx",
                       "hooks/useX.jsx", "i18n/fr.jsx"):
            fichiers = self.depot.plan(
                tache("PACT1", "x", f"`frontend/src/{chemin}`"))
            self.assertEqual(self.ecrans(fichiers), [], chemin)

    def test_fichier_de_test_n_est_pas_un_ecran(self):
        fichiers = self.depot.plan(tache(
            "PACT1", "x", "`frontend/src/features/a/Neuf.test.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_module_config_seul_n_est_pas_un_ecran(self):
        """La tache de CABLAGE elle-meme ne peut pas etre accusee de non-cablage."""
        fichiers = self.depot.plan(tache(
            "VAO32", "Nav et routes du module.",
            "`frontend/src/features/a/module.config.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])


# ===========================================================================
# FORME 1 — le coeur anti-faux-positif : creation vs modification
# ===========================================================================

class CreationVsModificationTests(BaseDepot):
    def test_ecran_deja_sur_disque_est_une_modification(self):
        """Signal STRUCTUREL, et il prime sur tout signal textuel."""
        self.depot.ecran("features/a/Fiche.jsx")
        fichiers = self.depot.plan(
            tache("PACT1", "Ajoute un onglet.", "`frontend/src/features/a/Fiche.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_le_gabarit_colle_ne_transforme_pas_une_correction_en_creation(self):
        """Piege REEL : PACT44/45/49 portent la clause « l'ecran est
        ATTEIGNABLE » par copier-coller alors que leur ecran existe DEJA et est
        deja branche. Le disque doit primer, sinon la garde les classe mal."""
        self.depot.ecran("features/a/Fiche.jsx")
        fichiers = self.depot.plan(tache(
            "PACT44", f"Corrige un champ. {CLAUSE}",
            "`frontend/src/features/a/Fiche.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_existence_toleree_sur_un_chemin_divergent(self):
        """Piege REEL (NTCON14, NTPRJ12, NTESG17) : la tache cite
        `pages/x/Y.jsx` alors que le fichier vit en `features/x/pages/Y.jsx`,
        ou `ProjetDetail.jsx` pour `ProjetDetailPage.jsx`. Un match STRICT du
        chemin les declare « creations » et les accuse a tort."""
        self.depot.ecran("features/gp/pages/PlanningPage.jsx")
        fichiers = self.depot.plan(tache(
            "NTCON14", "x", "`frontend/src/pages/gp/PlanningPage.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])

        self.depot.ecran("features/gp/pages/ProjetDetailPage.jsx")
        fichiers = self.depot.plan(tache(
            "NTPRJ12", "x", "`frontend/src/pages/gp/ProjetDetail.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_la_tache_qui_ETEND_n_est_pas_accusee_a_la_place_du_createur(self):
        """Piege REEL (NTFSM4/25, NTSRV29, NTHCM22) : plusieurs taches nomment
        le meme fichier neuf ; la PREMIERE le cree, les suivantes l'etendent.
        Accuser les extensions triplerait le bruit pour un seul defaut."""
        chemin = "`frontend/src/pages/dispatch/Board.jsx`"
        fichiers = self.depot.plan(
            tache("NTFSM1", "Cree le tableau.", chemin),
            tache("NTFSM4", "Ajoute une colonne.", chemin),
            tache("NTFSM25", "Ajoute un filtre.", chemin))
        self.assertEqual(self.ecrans(fichiers), ["NTFSM1"])

    def test_le_marqueur_nouveau_designe_le_proprietaire(self):
        """`(nouveau)` l'emporte sur l'ordre d'apparition."""
        chemin = "frontend/src/pages/d/Board.jsx"
        fichiers = self.depot.plan(
            tache("NTA1", "Etend le tableau.", f"`{chemin}`"),
            tache("NTA2", "Cree le tableau.", f"`{chemin} (nouveau)`"))
        self.assertEqual(self.ecrans(fichiers), ["NTA2"])

    def test_annotation_hors_des_accents_graves(self):
        """Piege REEL (NTAGR27) : `` `X.jsx` (nouveau ou section de Y) ``.
        L'annotation est posee DEHORS les accents graves ; sans les retirer,
        elle etait invisible et la tache accusee a tort."""
        fichiers = self.depot.plan(tache(
            "NTAGR27", "x",
            "`frontend/src/pages/a/ParcelleDetail.jsx` "
            "(nouveau ou section de ParcellesPage)"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_annotation_onglet(self):
        """`X.jsx (onglet RMA)` : le livrable est un onglet de X, pas un ecran."""
        fichiers = self.depot.plan(tache(
            "NTFSM16", "x", "`frontend/src/pages/sav/GarantiesPage.jsx` (onglet RMA)"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_tache_de_suppression_ne_cree_rien(self):
        fichiers = self.depot.plan(tache(
            "ODY33", "Retrait du legacy : supprimer la coquille.",
            "`frontend/src/features/a/Vieux.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_tache_qui_modifie_une_garde_cite_des_preuves(self):
        """PACT149/150 modifient check_ecrans_atteignables.py et citent des
        ecrans a titre de PREUVE, jamais comme livrable."""
        fichiers = self.depot.plan(tache(
            "PACT149", "Etend la garde.",
            "`scripts/check_ecrans_atteignables.py`, "
            "`frontend/src/features/a/Orphelin.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_ecran_public_a_jeton_est_hors_du_menu_par_conception(self):
        """NTPRO23/NTSVC12 : lui exiger une entree de nav serait absurde."""
        fichiers = self.depot.plan(tache(
            "NTPRO23", "Ecran public par lien de partage, AllowAny, "
            "meme pattern que PartageGed.",
            "`frontend/src/pages/pub/Suivi.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_composant_monte_ailleurs_n_est_pas_un_ecran(self):
        """NTAI10 : « Panneau monte dans cinq fiches », aucune route propre."""
        fichiers = self.depot.plan(tache(
            "NTAI10", "Panneau composant monte dans les fiches existantes.",
            "`frontend/src/features/a/Panneau.jsx`"))
        self.assertEqual(self.ecrans(fichiers), [])

    def test_mais_le_mot_ecran_annule_cette_exemption(self):
        """« l'ecran X avec son panneau Y » ne doit pas s'exempter tout seul."""
        fichiers = self.depot.plan(tache(
            "NTAI11", "Nouvel ecran avec un panneau lateral.",
            "`frontend/src/features/a/Neuf.jsx`"))
        self.assertEqual(self.ecrans(fichiers), ["NTAI11"])


# ===========================================================================
# FORME 3 — deux moities sans contrat commun
# ===========================================================================

class ContratTests(BaseDepot):
    def test_deux_moities_sans_contrat_sont_signalees(self):
        fichiers = self.depot.plan(tache(
            "NTX1", "Expose et affiche.",
            "`apps/sav/views.py`, `frontend/src/api/savApi.js`"))
        self.assertEqual(self.constats(fichiers, ctc.FORME_CONTRAT), ["NTX1"])

    def test_un_contrat_partage_verifiable_suffit(self):
        for clause in ("le test backend AFFIRME l'exemple committe dans "
                       "docs/api-contracts.md et le test frontend importe",
                       "check_api_shapes.py reste vert",
                       "la meme fixture des deux cotes"):
            fichiers = self.depot.plan(tache(
                "NTX1", f"Expose et affiche. {clause}",
                "`apps/sav/views.py`, `frontend/src/api/savApi.js`"))
            self.assertEqual(self.constats(fichiers, ctc.FORME_CONTRAT), [], clause)

    def test_backend_seul_n_est_jamais_un_contrat_absent(self):
        fichiers = self.depot.plan(tache("NTX1", "x", "`apps/sav/views.py`"))
        self.assertEqual(self.constats(fichiers, ctc.FORME_CONTRAT), [])

    def test_forme2_est_exclusive_de_forme3(self):
        """Une tache a deux moities a DEJA son consommateur : elle ne peut pas
        etre en meme temps « backend sans consommateur »."""
        fichiers = self.depot.plan(tache(
            "NTX1", "Expose un endpoint.",
            "`apps/sav/views.py`, `frontend/src/api/savApi.js`"))
        self.assertEqual(self.constats(fichiers, ctc.FORME_BACKEND), [])


# ===========================================================================
# FORME 4 — composants redefinis (mesuree, jamais bloquante)
# ===========================================================================

class DoublonTests(BaseDepot):
    def test_redefinition_hors_du_fichier_proprietaire(self):
        self.depot.ecran("features/c/SimpleTable.jsx",
                         "export default function SimpleTable() { return null }\n")
        self.depot.ecran("features/l/RetoursScreen.jsx",
                         "function SimpleTable() { return null }\n"
                         "export default function RetoursScreen() { return null }\n")
        trouves, _, _ = ctc.doublons()
        self.assertEqual([(n, f) for n, f, _ in trouves],
                         [("SimpleTable", "frontend/src/features/l/RetoursScreen.jsx")])

    def test_homonymie_de_fichier_n_est_pas_un_doublon(self):
        """`features/ao/DashboardPage.jsx` et `features/contrats/DashboardPage.jsx`
        sont deux tableaux de bord DIFFERENTS — 14 des 25 cas bruts mesures."""
        self.depot.ecran("features/ao/DashboardPage.jsx",
                         "export default function DashboardPage() { return null }\n")
        self.depot.ecran("features/contrats/DashboardPage.jsx",
                         "export default function DashboardPage() { return null }\n")
        trouves, _, _ = ctc.doublons()
        self.assertEqual(trouves, [])

    def test_adaptateur_qui_importe_le_partage_n_est_pas_un_doublon(self):
        """`Rapports.jsx` importe `reporting/Table` et se contente de l'adapter."""
        self.depot.ecran("pages/reporting/Table.jsx",
                         "export default function Table() { return null }\n")
        self.depot.ecran("pages/Rapports.jsx",
                         "import { Table as Partage } from './reporting/Table'\n"
                         "function Table() { return Partage }\n")
        trouves, _, _ = ctc.doublons()
        self.assertEqual(trouves, [])

    def test_un_composant_cite_en_commentaire_n_est_pas_declare(self):
        self.depot.ecran("features/c/SimpleTable.jsx",
                         "export default function SimpleTable() { return null }\n")
        self.depot.ecran("features/l/Autre.jsx",
                         "// function SimpleTable() {}\n"
                         "export default function Autre() { return null }\n")
        trouves, _, _ = ctc.doublons()
        self.assertEqual(trouves, [])

    def test_la_forme4_n_est_pas_bloquante(self):
        """64 % de faux positifs MESURES (7 sur 11 verifies a la lecture du
        code) : elle informe, elle ne barre jamais la route."""
        self.assertNotIn(ctc.FORME_DOUBLON, ctc.FORMES_BLOQUANTES)
        self.assertIn(ctc.FORME_DOUBLON, ctc.FORMES_AVERTISSEMENT)

    def test_la_forme2_n_est_pas_bloquante(self):
        self.assertNotIn(ctc.FORME_BACKEND, ctc.FORMES_BLOQUANTES)


# ===========================================================================
# Base de reference : elle ne peut que RETRECIR
# ===========================================================================

class BaseDeReferenceTests(unittest.TestCase):
    def test_ecriture_puis_relecture(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "allow.txt"
            ctc.ecrire_base({"ecran-sans-cablage|PACT1"}, chemin)
            self.assertEqual(ctc.charger_base(chemin), {"ecran-sans-cablage|PACT1"})

    def test_signature_ne_depend_pas_du_numero_de_ligne(self):
        """Une tache qui se decale dans son fichier ne doit pas invalider la base."""
        constat = ctc.Constat(ctc.FORME_ECRAN, "PACT42")
        self.assertEqual(constat.signature, "ecran-sans-cablage|PACT42")

    def test_chemin_de_base_resolu_a_l_appel(self):
        """Piege documente dans check_ecrans_atteignables.py :
        `def charger_base(path=BASELINE_PATH)` fige le chemin a la definition
        du module, si bien qu'un test ecrasait la VRAIE base du depot."""
        sauvegarde = ctc.BASELINE_PATH
        avant = sauvegarde.read_text(encoding="utf-8") if sauvegarde.is_file() else None
        self.addCleanup(lambda: setattr(ctc, "BASELINE_PATH", sauvegarde))
        with tempfile.TemporaryDirectory() as tmp:
            ctc.BASELINE_PATH = Path(tmp) / "allow.txt"
            ctc.ecrire_base({"ecran-sans-cablage|PACT1"})
            self.assertEqual(ctc.charger_base(), {"ecran-sans-cablage|PACT1"})
        apres = sauvegarde.read_text(encoding="utf-8") if sauvegarde.is_file() else None
        self.assertEqual(avant, apres, "la VRAIE base du depot a ete ecrasee")

    def test_refus_de_croissance_sans_drapeau(self):
        depot = FauxDepot()
        self.addCleanup(depot.close)
        sauvegarde = ctc.BASELINE_PATH
        ctc.BASELINE_PATH = depot.racine / "allow.txt"
        self.addCleanup(lambda: setattr(ctc, "BASELINE_PATH", sauvegarde))
        sauvegarde_plans = ctc.PLAN_FILES_EXPLICITES
        ctc.PLAN_FILES_EXPLICITES = ("docs/PLAN.md",)
        self.addCleanup(lambda: setattr(ctc, "PLAN_FILES_EXPLICITES", sauvegarde_plans))

        ctc.ecrire_base(set())                       # base existante et VIDE
        depot.plan(tache("PACT1", "Nouvel ecran.",
                         "`frontend/src/features/a/Neuf.jsx`"))
        self.assertEqual(ctc.main(["--write-baseline"]), 1)
        self.assertEqual(ctc.charger_base(ctc.BASELINE_PATH), set())
        self.assertEqual(ctc.main(["--write-baseline", "--autoriser-croissance"]), 0)
        self.assertEqual(ctc.charger_base(ctc.BASELINE_PATH),
                         {"ecran-sans-cablage|PACT1"})


# ===========================================================================
# Calibration sur le VRAI depot (la garde ne vaut que si elle est juste ici)
# ===========================================================================

_REEL = None


def analyse_reelle():
    global _REEL
    if _REEL is None:
        _REEL = ctc.analyse()
    return _REEL


@unittest.skipUnless((ROOT / "docs" / "PLAN.md").is_file(), "fichiers de plan absents")
class DepotReelTests(unittest.TestCase):
    def test_la_base_de_reference_couvre_le_passif(self):
        """Le passif est GELE : sur un depot propre, la garde est verte."""
        constats, _ = analyse_reelle()
        base = ctc.charger_base()
        nouveaux = sorted(c.signature for c in constats
                          if c.forme in ctc.FORMES_BLOQUANTES
                          and c.signature not in base)
        self.assertEqual(nouveaux, [])

    def test_le_corpus_est_reellement_lu(self):
        """Si l'extraction casse, la garde devient muette EN SILENCE."""
        _, stats = analyse_reelle()
        self.assertGreater(stats["taches"], 1200)
        # 250 -> 150 : le lot §E du 08/08/2026 a COCHÉ 76 tâches, donc le
        # corpus de candidates rétrécit légitimement (191 aujourd'hui).
        # 150 -> 100 : le lot du 13/08/2026 en a coché 52 de plus (142
        # aujourd'hui). Le plancher garde son rôle — une extraction cassée
        # rendrait ~0 — sans punir le fait d'avoir livré.
        self.assertGreater(stats["f1_candidates"], 100)
        # 80 -> 25 -> 0. ATTENTION : ce plancher a PERDU son pouvoir
        # discriminant et ne doit plus être lu comme une canari. Il ne compte
        # que les tâches NON COCHÉES qui CRÉENT un écran avec montage +
        # clause ; le lot du 13/08/2026 les a quasiment toutes livrées, donc
        # il vaut 1 — pas parce que l'extraction casse, mais parce que le
        # corpus est drainé. Le rôle de canari est désormais porté par
        # `taches` (1690) et `f1_candidates` (142) ci-dessus, qui eux
        # tomberaient bien à 0 si l'extraction se cassait.
        # 0 atteint le 14/08/2026 (vague 1 du run SUPPLY) : la DERNIÈRE tâche
        # non cochée qui créait un écran avec montage + clause vient d'être
        # livrée. Le compteur ne peut donc plus servir de plancher — il est
        # conservé en OBSERVATION seulement. Les deux canaris réels restent
        # `taches` et `f1_candidates` juste au-dessus.
        self.assertGreaterEqual(stats["f1_conformes"], 0)

    def test_les_taches_conformes_du_depot_ne_rougissent_pas(self):
        """~120 taches de docs/PLAN.md portent deja la clause canonique et
        nomment leur fichier de montage : si elles rougissent, la garde est
        fausse et sera desactivee des le premier run."""
        constats, _ = analyse_reelle()
        fautives = {c.cible for c in constats if c.forme == ctc.FORME_ECRAN}
        conformes = ["PACT98", "PACT99", "PACT100", "PACT101", "PACT102"]
        self.assertEqual([i for i in conformes if i in fautives], [])

    def test_le_passif_ecran_ne_peut_que_diminuer(self):
        """Invariant de SENS DE VARIATION, jamais un nombre fige.

        Une premiere version de ce test aurait epingle le nombre mesure
        (102) : elle serait devenue ROUGE pour cause de PROGRES des la
        premiere tache corrigee. Un test qui punit la guerison est un test
        faux — la lecon est ecrite dans
        test_check_ecrans_atteignables.py::test_le_passif_ao_ne_peut_que_diminuer.
        """
        constats, _ = analyse_reelle()
        ecrans = [c for c in constats if c.forme == ctc.FORME_ECRAN]
        self.assertLessEqual(
            len(ecrans), 102,
            "le nombre de taches creant un ecran sans exiger son cablage a "
            "AUGMENTE depuis le passif mesure le 03/08/2026 (102)")

    def test_les_formes_non_bloquantes_ne_sont_pas_dans_la_base(self):
        """La base ne gele que ce qui BARRE la route."""
        base = ctc.charger_base()
        for signature in base:
            forme = signature.split("|", 1)[0]
            self.assertIn(forme, ctc.FORMES_BLOQUANTES, signature)


if __name__ == "__main__":
    unittest.main()
