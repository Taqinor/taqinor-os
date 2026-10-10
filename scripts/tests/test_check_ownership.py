"""Tests OWN — le registre de propriété des fichiers (``docs/ownership.yml``).

CE QU'ILS PROTÈGENT
-------------------
Plusieurs sessions « work on the plan <x> » tournent en parallèle. Elles ne se
marchent jamais dessus SI ET SEULEMENT SI chaque fichier a exactement UN
propriétaire, et si chaque tâche d'un plan ne touche que les fichiers du
propriétaire de ce plan (une tâche multi-propriétaires va au plan transverse).
La construction QJR5 (30/09/2026) a dû faire passer 155 de ses 159 tâches dans
UNE lane série parce que rien de tout cela n'était écrit.

``scripts/check_ownership.py`` vérifie trois choses :
  (a) chaque fichier suivi sous les racines a exactement un propriétaire ;
  (b) une tâche ouverte d'un plan ne déclare (``Files:``) que des fichiers de
      SON propriétaire — plans transverse/plateforme exemptés, surfaces
      append-only tolérées ;
  (c) un fichier NOUVEAU (déclaré par une tâche, ou ajouté par une branche)
      sans propriétaire est refusé.
``scripts/plan_lanes.py`` lit le même registre pour la disjonction des lanes.

Pur stdlib (unittest), sans Django ni base. Run :
    python -m unittest scripts.tests.test_check_ownership -v
"""
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_ownership as co  # noqa: E402
import plan_lanes as pl  # noqa: E402


REGISTRE = textwrap.dedent("""\
    version: 1
    roots: [backend/django_core/apps/, backend/django_core/core/, frontend/src/, apps/web/]
    containers: [backend/django_core/apps/, frontend/src/, frontend/src/features/, frontend/src/pages/, frontend/src/api/]
    exempt: [transverse, platform, parked]
    owners:
      devis:
        plan: docs/plans/PLAN_DEVIS.md
        paths:
          - backend/django_core/apps/ventes/quote_engine/**
          - frontend/src/pages/ventes/Devis*.jsx
        fallback:
          - backend/django_core/apps/ventes/**
      facturation:
        plan: docs/plans/PLAN_FACTURATION.md
        paths:
          - backend/django_core/apps/ventes/views/facture.py
          - frontend/src/pages/ventes/Facture*.jsx
      cadence:
        plan: docs/plans/PLAN_CADENCE.md
        paths:
          - backend/django_core/apps/crm/cadence_*.py
      fiche:
        plan: docs/plans/PLAN_FICHE.md
        fallback:
          - backend/django_core/apps/crm/**
      web:
        plan: docs/WEB_PLAN.md
        paths:
          - apps/web/**
      platform:
        plan: docs/plans/PLAN_PLATFORM.md
        paths:
          - backend/django_core/core/**
          - frontend/src/ui/**
          - frontend/src/router/**
          - frontend/src/index.css
      parked:
        plan: docs/backlog/PHASE2_PLAN.md
        paths_from_parked_registry: true
      transverse:
        plan: docs/plans/PLAN_TRANSVERSE.md
    append_only:
      - path: frontend/src/router/index.jsx
        rule: "une route ajoutée en fin de bloc"
      - path: "backend/django_core/apps/*/migrations/**"
        rule: "un NOUVEAU fichier seulement"
    plans:
      docs/PLAN2.md: platform
      docs/plans/PLAN_CRM_VENTES.md: [fiche, cadence, devis, facturation]
""")


def registre(texte=REGISTRE, racine=None):
    return co.charger_registre(texte=texte, racine=racine or ROOT)


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.reg = registre()

    def test_fichier_possede_exactement_une_fois(self):
        self.assertEqual(co.proprietaire(
            self.reg, "backend/django_core/apps/crm/cadence_temps.py"), "cadence")
        self.assertEqual(co.proprietaire(
            self.reg, "backend/django_core/apps/ventes/views/facture.py"), "facturation")
        self.assertEqual(co.verifier_fichiers(self.reg, [
            "backend/django_core/apps/crm/cadence_temps.py",
            "backend/django_core/apps/ventes/views/facture.py",
            "apps/web/src/lib/lead.ts",
        ]), [])

    def test_fichier_sans_proprietaire_refuse(self):
        erreurs = co.verifier_fichiers(self.reg, ["frontend/src/lib/format.js"])
        self.assertEqual(len(erreurs), 1)
        self.assertIn("sans propriétaire", erreurs[0])
        self.assertIn("frontend/src/lib/format.js", erreurs[0])

    def test_fichier_possede_deux_fois_refuse(self):
        texte = REGISTRE.replace(
            "      - backend/django_core/apps/crm/cadence_*.py\n",
            "      - backend/django_core/apps/crm/cadence_*.py\n"
            "      - backend/django_core/apps/ventes/views/facture.py\n")
        erreurs = co.verifier_fichiers(
            registre(texte), ["backend/django_core/apps/ventes/views/facture.py"])
        self.assertEqual(len(erreurs), 1)
        self.assertIn("deux propriétaires", erreurs[0])
        self.assertIn("cadence", erreurs[0])
        self.assertIn("facturation", erreurs[0])

    def test_paths_prime_sur_fallback(self):
        # quote_engine/** (devis, paths) est aussi sous le fallback ventes/**
        # de devis ; views/facture.py (facturation, paths) bat le fallback devis.
        self.assertEqual(co.proprietaire(
            self.reg, "backend/django_core/apps/ventes/views/facture.py"), "facturation")
        self.assertEqual(co.proprietaire(
            self.reg, "backend/django_core/apps/ventes/views/devis.py"), "devis")

    def test_deux_fallbacks_qui_se_chevauchent_refuses(self):
        texte = REGISTRE.replace(
            "  web:\n",
            "  intrus:\n"
            "    plan: docs/plans/PLAN_INTRUS.md\n"
            "    fallback:\n"
            "      - backend/django_core/apps/crm/**\n"
            "  web:\n")
        erreurs = co.verifier_fichiers(
            registre(texte), ["backend/django_core/apps/crm/views.py"])
        self.assertEqual(len(erreurs), 1)
        self.assertIn("deux propriétaires", erreurs[0])

    def test_fallbacks_imbriques_le_plus_specifique_gagne(self):
        # ventes/** (devis) ⊃ quote_engine/** (moteur) ⊃ facturx.py (facturation,
        # paths) : trois niveaux. Entre résiduels, le préfixe le plus long gagne
        # (règle « fichier > dossier > résiduel » de docs/audits/unites.yml).
        texte = REGISTRE.replace(
            "      - backend/django_core/apps/ventes/quote_engine/**\n", "").replace(
            "  web:\n",
            "  moteur:\n"
            "    plan: docs/plans/PLAN_AUDIT_MOTEUR.md\n"
            "    fallback:\n"
            "      - backend/django_core/apps/ventes/quote_engine/**\n"
            "  web:\n").replace(
            "      - backend/django_core/apps/ventes/views/facture.py\n",
            "      - backend/django_core/apps/ventes/views/facture.py\n"
            "      - backend/django_core/apps/ventes/quote_engine/facturx.py\n")
        reg = registre(texte)
        self.assertEqual(co.proprietaire(
            reg, "backend/django_core/apps/ventes/quote_engine/builder.py"), "moteur")
        self.assertEqual(co.proprietaire(
            reg, "backend/django_core/apps/ventes/quote_engine/facturx.py"), "facturation")
        self.assertEqual(co.proprietaire(
            reg, "backend/django_core/apps/ventes/serializers.py"), "devis")

    def test_motif_specifique_bat_le_residuel_de_meme_prefixe(self):
        # `ventes/*_facturation.py` et `ventes/**` ont le MÊME préfixe littéral :
        # départager par la longueur du préfixe les mettait à égalité (fichier
        # neuf à deux propriétaires). Le plus de caractères littéraux gagne.
        texte = REGISTRE.replace(
            "      - backend/django_core/apps/ventes/views/facture.py\n",
            "      - backend/django_core/apps/ventes/views/facture.py\n").replace(
            "  cadence:\n",
            "  cadence:\n"
            "    fallback:\n"
            "      - backend/django_core/apps/ventes/*_cadence.py\n")
        reg = registre(texte)
        self.assertEqual(co.proprietaire(
            reg, "backend/django_core/apps/ventes/selectors_cadence.py"), "cadence")
        self.assertEqual(co.proprietaire(
            reg, "backend/django_core/apps/ventes/selectors.py"), "devis")

    def test_semantique_des_globs(self):
        rx = co.compiler_glob("frontend/src/pages/ventes/Devis*.jsx")
        self.assertTrue(rx.fullmatch("frontend/src/pages/ventes/DevisList.jsx"))
        self.assertFalse(rx.fullmatch("frontend/src/pages/ventes/sous/DevisList.jsx"))
        rx = co.compiler_glob("backend/django_core/apps/*/migrations/**")
        self.assertTrue(rx.fullmatch("backend/django_core/apps/crm/migrations/0001_initial.py"))
        self.assertFalse(rx.fullmatch("backend/django_core/apps/crm/models.py"))
        rx = co.compiler_glob("frontend/src/ui/**")
        self.assertTrue(rx.fullmatch("frontend/src/ui/Button.jsx"))
        self.assertTrue(rx.fullmatch("frontend/src/ui/charts/Bar.jsx"))
        self.assertFalse(rx.fullmatch("frontend/src/uikit/Button.jsx"))


class RegistreTests(unittest.TestCase):
    def test_glob_trop_large_sur_un_conteneur_refuse(self):
        # Un fallback « tout frontend/src/features » rendrait propriétaire
        # d'office un module NEUF : la règle (c) ne pourrait plus jamais tirer.
        texte = REGISTRE.replace(
            "      - frontend/src/ui/**\n",
            "      - frontend/src/ui/**\n"
            "      - frontend/src/features/**\n")
        erreurs, _ = co.verifier_registre(registre(texte), [])
        self.assertTrue(any("trop large" in e and "frontend/src/features/**" in e
                            for e in erreurs), erreurs)

    def test_plan_lie_a_un_proprietaire_inconnu_refuse(self):
        texte = REGISTRE.replace("docs/PLAN2.md: platform", "docs/PLAN2.md: fantome")
        erreurs, _ = co.verifier_registre(registre(texte), [])
        self.assertTrue(any("fantome" in e for e in erreurs), erreurs)

    def test_deux_proprietaires_ne_partagent_pas_un_plan(self):
        texte = REGISTRE.replace("plan: docs/plans/PLAN_FICHE.md",
                                 "plan: docs/plans/PLAN_CADENCE.md")
        erreurs, _ = co.verifier_registre(registre(texte), [])
        self.assertTrue(any("PLAN_CADENCE.md" in e for e in erreurs), erreurs)

    def test_apps_parquees_lues_depuis_core_parked(self):
        # La liste des apps parquées n'existe qu'UNE fois (core/parked.py) :
        # le registre la LIT, il ne la recopie pas.
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            parked = racine / "backend" / "django_core" / "core" / "parked.py"
            parked.parent.mkdir(parents=True)
            parked.write_text("APPS_PARQUEES = (\n    'rh',\n    'paie',\n)\n",
                              encoding="utf-8")
            reg = registre(racine=racine)
            self.assertEqual(co.proprietaire(
                reg, "backend/django_core/apps/rh/migrations/0001_initial.py"), "parked")
            self.assertEqual(co.proprietaire(
                reg, "backend/django_core/apps/paie/models.py"), "parked")
            self.assertIsNone(co.proprietaire(
                reg, "backend/django_core/apps/stock/models.py"))


class PlansTests(unittest.TestCase):
    def setUp(self):
        self.reg = registre()

    def test_tache_hors_proprietaire_refusee(self):
        plans = {"docs/plans/PLAN_DEVIS.md": textwrap.dedent("""\
            ## BUILD QUEUE
            - [ ] SPL1 — **Déplacer** : x. Files: `backend/django_core/apps/ventes/views/devis.py`, `backend/django_core/apps/crm/cadence_temps.py`. (ROUTINE)
            """)}
        erreurs = co.verifier_plans(self.reg, plans)
        self.assertEqual(len(erreurs), 1, erreurs)
        e = erreurs[0]
        self.assertIn("SPL1", e)
        self.assertIn("cadence_temps.py", e)
        self.assertIn("cadence", e)
        self.assertIn("PLAN_TRANSVERSE.md", e)
        self.assertIn("PLAN_DEVIS.md:2", e)

    def test_surface_append_only_toleree(self):
        plans = {"docs/plans/PLAN_DEVIS.md": textwrap.dedent("""\
            - [ ] SPL2 — x. Files: `backend/django_core/apps/ventes/views/devis.py`, `frontend/src/router/index.jsx`, `backend/django_core/apps/crm/migrations/0200_x.py`. (ROUTINE)
            """)}
        self.assertEqual(co.verifier_plans(self.reg, plans), [])

    def test_plans_transverse_et_plateforme_exemptes(self):
        ligne = ("- [ ] SPL3 — x. Files: `backend/django_core/apps/ventes/views/devis.py`, "
                 "`backend/django_core/apps/crm/cadence_temps.py`. (ROUTINE)\n")
        plans = {"docs/plans/PLAN_TRANSVERSE.md": ligne, "docs/PLAN2.md": ligne}
        self.assertEqual(co.verifier_plans(self.reg, plans), [])

    def test_plan_exempte_garde_les_regles_a_et_c(self):
        # Exempté de la règle (b) seulement : un fichier déclaré par une tâche
        # transverse doit quand même avoir UN propriétaire (sinon il naîtra
        # orphelin, ou doublement possédé, à sa création).
        ligne = ("- [ ] SPL12 — x. Files: `backend/django_core/apps/ventes/views/devis.py`, "
                 "`frontend/src/features/neuf/Neuf.jsx`. (ROUTINE)\n")
        erreurs = co.verifier_plans(self.reg, {"docs/plans/PLAN_TRANSVERSE.md": ligne})
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("sans propriétaire", erreurs[0])
        # … mais pas les files parquées (backlog hors périmètre).
        self.assertEqual(co.verifier_plans(
            self.reg, {"docs/backlog/PHASE2_PLAN.md": ligne}), [])

    def test_taches_non_constructibles_ignorees(self):
        hors = "Files: `backend/django_core/apps/crm/cadence_temps.py`. (ROUTINE)"
        plans = {"docs/plans/PLAN_DEVIS.md": textwrap.dedent(f"""\
            - [x] SPL4 — fait. {hors}
            - [BLOCKED: attend X] SPL5 — bloqué. {hors}
            - [ ] SPL6 [BLOCKED: hors périmètre] — bloqué en ligne. {hors}
            ### GATED — attend le fondateur
            - [ ] SPL7 — porte fondateur. {hors}
            """)}
        self.assertEqual(co.verifier_plans(self.reg, plans), [])

    def test_chemins_courts_normalises(self):
        self.assertEqual(co.normaliser("apps/ventes/views/devis.py"),
                         "backend/django_core/apps/ventes/views/devis.py")
        self.assertEqual(co.normaliser("core/events.py"),
                         "backend/django_core/core/events.py")
        self.assertEqual(co.normaliser("features/crm/stages.js"),
                         "frontend/src/features/crm/stages.js")
        self.assertEqual(co.normaliser("apps/web/src/lib/lead.ts"),
                         "apps/web/src/lib/lead.ts")
        self.assertEqual(co.normaliser("src/lib/lead.ts", web=True),
                         "apps/web/src/lib/lead.ts")
        self.assertEqual(co.normaliser("apps/yanbow-web/src/pages/index.astro"),
                         "apps/yanbow-web/src/pages/index.astro")
        self.assertIsNone(co.normaliser("views.py"))
        plans = {"docs/plans/PLAN_DEVIS.md":
                 "- [ ] SPL8 — x. Files: `apps/crm/cadence_temps.py`. (ROUTINE)\n"}
        erreurs = co.verifier_plans(self.reg, plans)
        self.assertEqual(len(erreurs), 1)
        self.assertIn("backend/django_core/apps/crm/cadence_temps.py", erreurs[0])

    def test_plan_multi_proprietaires_accepte_son_union(self):
        plans = {"docs/plans/PLAN_CRM_VENTES.md": textwrap.dedent("""\
            - [ ] NTX1 — x. Files: `backend/django_core/apps/crm/cadence_temps.py`, `backend/django_core/apps/ventes/views/devis.py`. (ROUTINE)
            - [ ] NTX2 — x. Files: `apps/web/src/lib/lead.ts`. (ROUTINE)
            """)}
        erreurs = co.verifier_plans(self.reg, plans)
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("NTX2", erreurs[0])

    def test_fichier_declare_sans_proprietaire_refuse(self):
        # Règle (c) au moment où la tâche est ÉCRITE : elle crée un fichier
        # que personne ne possède encore.
        plans = {"docs/plans/PLAN_DEVIS.md":
                 "- [ ] SPL9 — x. Files: `frontend/src/features/neuf/Neuf.jsx`. (ROUTINE)\n"}
        erreurs = co.verifier_plans(self.reg, plans)
        self.assertEqual(len(erreurs), 1)
        self.assertIn("sans propriétaire", erreurs[0])
        self.assertIn("docs/ownership.yml", erreurs[0])

    def test_plan_non_lie_refuse(self):
        plans = {"docs/plans/PLAN_INCONNU.md": "- [ ] Z1 — x. Files: `apps/web/a.ts`.\n"}
        erreurs = co.verifier_plans(self.reg, plans)
        self.assertEqual(len(erreurs), 1)
        self.assertIn("PLAN_INCONNU.md", erreurs[0])
        self.assertIn("aucun propriétaire", erreurs[0])


class FormesDeFilesTests(unittest.TestCase):
    """Critique finale OWN (F1/F4) : toute forme de `Files:` est lue."""

    def setUp(self):
        self.reg = registre()
        self.fichiers = [
            "backend/django_core/apps/ventes/views/devis.py",
            "backend/django_core/apps/ventes/views/facture.py",
            "backend/django_core/apps/crm/cadence_temps.py",
        ]

    def _refus(self, ligne, plan="docs/plans/PLAN_DEVIS.md"):
        return co.verifier_plans(self.reg, {plan: ligne}, fichiers=self.fichiers)

    def test_extensions_completes_et_json_non_tronque(self):
        chemins = co.chemins_declares(
            "x. Files: `apps/ventes/contract_samples/calepinage_options.json`, "
            "`apps/web/src/pages/proposition/[...token].astro`, `frontend/src/a.scss`.")
        self.assertIn("apps/ventes/contract_samples/calepinage_options.json", chemins)
        self.assertNotIn("apps/ventes/contract_samples/calepinage_options.js", chemins)
        self.assertIn("apps/web/src/pages/proposition/[...token].astro", chemins)
        self.assertIn("frontend/src/a.scss", chemins)

    def test_accolades_antislash_glob_et_dossier(self):
        for decl in ("`backend/django_core/apps/{ventes/views/devis,crm/cadence_temps}.py`",
                     "`backend\\django_core\\apps\\crm\\cadence_temps.py`",
                     "`backend/django_core/apps/crm/*.py`",
                     "`backend/django_core/apps/crm/`"):
            with self.subTest(decl=decl):
                erreurs = self._refus(f"- [ ] SPL20 — x. Files: {decl}. (ROUTINE)\n")
                self.assertTrue(any("cadence" in e for e in erreurs), erreurs)

    def test_files_en_ligne_de_continuation_et_fichiers(self):
        for texte in ("- [ ] SPL21 — x : constat long.\n"
                      "  Files: `backend/django_core/apps/crm/cadence_temps.py`. (ROUTINE)\n",
                      "- [ ] SPL22 — x. Fichiers : `backend/django_core/apps/crm/cadence_temps.py`.\n"):
            with self.subTest(texte=texte[:20]):
                erreurs = self._refus(texte)
                self.assertEqual(len(erreurs), 1, erreurs)
                self.assertIn("cadence", erreurs[0])

    def test_ligne_de_tache_mal_formee_avec_files_refusee(self):
        erreurs = self._refus(
            "- [ ] SPL23 - tiret court. Files: `backend/django_core/apps/ventes/views/devis.py`.\n")
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("mal formée", erreurs[0])


class RegistreDoublonsTests(unittest.TestCase):
    def test_cle_de_proprietaire_dupliquee_refusee(self):
        # F5 : le mini-YAML garde silencieusement le DERNIER bloc d'une clé.
        texte = REGISTRE.replace(
            "  transverse:\n",
            "  cadence:\n"
            "    plan: docs/plans/PLAN_CADENCE_BIS.md\n"
            "  transverse:\n")
        erreurs, _ = co.verifier_registre(registre(texte), [])
        self.assertTrue(any("deux fois" in e and "cadence" in e for e in erreurs), erreurs)


class MesureConflitsTests(unittest.TestCase):
    """F8 : la mesure du brief (étape 1) est reproductible par la garde."""

    def test_classement_par_cout_taches_x_proprietaires_x_lignes(self):
        reg = registre()
        devis = "backend/django_core/apps/ventes/views/devis.py"
        cadence = "backend/django_core/apps/crm/cadence_temps.py"
        taches = {
            "QJR1": {"prefixe": "QJR", "fichiers": {devis}},
            "QJR2": {"prefixe": "QJR", "fichiers": {devis}},
            "CAD1": {"prefixe": "CAD", "fichiers": {cadence, devis}},
            "CAD2": {"prefixe": "CAD", "fichiers": {cadence}},
        }
        commits = [({"QJR1"}, {devis}), ({"CAD1"}, {cadence})]
        lignes = {devis: 100, cadence: 10}
        lignes_classees = co.classer_conflits(reg, taches, commits, lignes)
        tete = lignes_classees[0]
        self.assertEqual(tete["fichier"], devis)
        self.assertEqual(tete["proprietaire"], "devis")
        self.assertEqual(tete["taches"], 3)
        self.assertEqual(sorted(tete["parcours"]), ["cadence", "devis"])
        self.assertEqual(tete["cout"], 3 * 2 * 100)
        self.assertEqual([r["fichier"] for r in lignes_classees if len(r["parcours"]) >= 2],
                         [devis])


class NouveauxFichiersTests(unittest.TestCase):
    def test_nouveau_fichier_sans_proprietaire_nomme(self):
        reg = registre()
        erreurs = co.verifier_nouveaux(reg, [
            "frontend/src/features/neuf/Neuf.jsx",
            "backend/django_core/apps/crm/cadence_neuve.py",
            "docs/hors_racines.md",
        ])
        self.assertEqual(len(erreurs), 1)
        self.assertIn("nouveau fichier", erreurs[0])
        self.assertIn("frontend/src/features/neuf/Neuf.jsx", erreurs[0])


class PlanLanesIntegrationTests(unittest.TestCase):
    """``plan_lanes.py`` lit le registre pour la disjonction des lanes."""

    def setUp(self):
        self._avant = pl.utiliser_registre(registre())

    def tearDown(self):
        pl.utiliser_registre(self._avant)

    def test_append_only_du_registre_ne_force_pas_de_fusion(self):
        # backend/.../crm/migrations/** est append-only DANS LE REGISTRE
        # seulement (aucun suffixe codé en dur ne le couvre).
        self.assertTrue(pl._is_append_only(
            "backend/django_core/apps/crm/migrations/0200_x.py"))
        self.assertFalse(pl._is_append_only(
            "backend/django_core/apps/crm/views.py"))

    def test_proprietaires_annotes_par_tache(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "PLAN_DEVIS.md"
            plan.write_text(textwrap.dedent("""\
                ## BUILD QUEUE
                - [ ] SPL10 — a. Files: `backend/django_core/apps/ventes/views/devis.py`. (ROUTINE) (@lane: a)
                - [ ] SPL11 — b. Files: `backend/django_core/apps/ventes/views/devis.py`, `backend/django_core/apps/crm/cadence_temps.py`. (ROUTINE) (@lane: b)
                """), encoding="utf-8")
            taches = {t["id"]: t for t in pl.parse_tasks(plan)}
        self.assertEqual(taches["SPL10"]["owners"], ["devis"])
        self.assertEqual(taches["SPL11"]["owners"], ["cadence", "devis"])

    def test_after_vers_une_tache_ouverte_d_un_autre_plan_bloque(self):
        # F3 : un @after vers une tâche d'un AUTRE fichier plan était ignoré —
        # un déplacement pouvait partir avant la capture de son golden.
        taches = [
            {"id": "SPL3", "deps": ["SPL1"], "lane": "a"},
            {"id": "SPL4", "deps": ["QJR500"], "lane": "a"},
            {"id": "SPL5", "deps": ["SPL4"], "lane": "a"},
        ]
        index = {"SPL1": ("", "docs/plans/PLAN_AUDIT_LEAD.md", 12),
                 "QJR500": ("x", "docs/PLAN2.md", 1183)}
        ok, refusees = pl.apply_external_after_gate(taches, index)
        self.assertEqual([t["id"] for t in ok], ["SPL4", "SPL5"])
        self.assertEqual(refusees[0]["id"], "SPL3")
        self.assertIn("SPL1", refusees[0]["after_block_reasons"][0])
        self.assertIn("PLAN_AUDIT_LEAD.md", refusees[0]["after_block_reasons"][0])
        ok, refusees = pl.apply_external_after_gate(taches, index, force_wave=True)
        self.assertEqual(refusees, [])

    def test_refus_after_externe_transitif(self):
        # Critique finale OWN (F8) : SPL47 retenue par un @after externe, SPL48
        # (@after SPL47, même plan) partait quand même — le planificateur ne
        # retient que sur une dépendance PRÉSENTE dans le run.
        taches = [
            {"id": "SPL47", "deps": ["SPL46"], "lane": "a"},
            {"id": "SPL48", "deps": ["SPL47"], "lane": "a"},
            {"id": "SPL49", "deps": ["SPL48"], "lane": "a"},
            {"id": "SPL52", "deps": [], "lane": "b"},
        ]
        index = {"SPL46": ("", "docs/plans/PLAN_AUDIT_TRANSVERSE.md", 40)}
        ok, refusees = pl.apply_external_after_gate(taches, index)
        self.assertEqual([t["id"] for t in ok], ["SPL52"])
        self.assertEqual(sorted(t["id"] for t in refusees), ["SPL47", "SPL48", "SPL49"])
        motif = next(t for t in refusees if t["id"] == "SPL49")["after_block_reasons"][0]
        self.assertIn("SPL48", motif)

    def test_sans_registre_comportement_inchange(self):
        pl.utiliser_registre(None)
        self.assertFalse(pl._is_append_only(
            "backend/django_core/apps/crm/migrations/0200_x.py"))
        self.assertTrue(pl._is_append_only("frontend/src/index.css"))


class RegistreReelTests(unittest.TestCase):
    """Le registre du dépôt lui-même."""

    def test_le_registre_du_depot_se_charge(self):
        reg = co.charger_registre()
        self.assertIn("transverse", reg.owners)
        self.assertIn("platform", reg.owners)
        self.assertEqual(reg.owners["transverse"]["paths"], [])

    def test_les_surfaces_append_only_historiques_sont_au_registre(self):
        # Les suffixes codés en dur de plan_lanes (CALX2, index.css…) ne
        # peuvent pas diverger du registre : chacun doit y être déclaré.
        reg = co.charger_registre()
        for suffixe in pl._APPEND_ONLY_SUFFIXES:
            with self.subTest(suffixe=suffixe):
                self.assertTrue(
                    any(s["path"].endswith(suffixe) for s in reg.append_only),
                    f"{suffixe} absent de append_only dans docs/ownership.yml")


class SurfacesRegistresRestreintesTests(unittest.TestCase):
    """SPL308 — l'append-only ne couvre plus des fichiers ENTIERS : seulement les
    quatre modules-registres (D-REG-1). Les quatre anciens fichiers retombent chez
    leur propriétaire seul, donc une tâche qui les réécrit est refusée par la
    règle (b) et sérialisée par plan_lanes. Registre RÉEL du dépôt, rien de mocké.
    """

    REGISTRES = (
        "backend/django_core/apps/roles/permissions_registre.py",
        "backend/django_core/apps/notifications/types_evenements.py",
        "backend/django_core/apps/audit/modeles_suivis.py",
        "backend/django_core/apps/publicapi/portees.py",
        "backend/django_core/apps/notifications/module_map.py",
    )
    ANCIENS = (
        ("backend/django_core/apps/roles/models.py", "securite"),
        ("backend/django_core/apps/notifications/models.py", "parametres"),
        ("backend/django_core/apps/audit/signals.py", "securite"),
        ("backend/django_core/apps/publicapi/constants.py", "analyse"),
    )
    NOUVEAUX = {
        "backend/django_core/apps/roles/models.py":
            "backend/django_core/apps/roles/permissions_registre.py",
        "backend/django_core/apps/notifications/models.py":
            "backend/django_core/apps/notifications/types_evenements.py",
    }

    @classmethod
    def setUpClass(cls):
        cls.reg = co.charger_registre()

    def test_append_only_limite_aux_modules_registres(self):
        for chemin in self.REGISTRES:
            with self.subTest(chemin=chemin):
                self.assertTrue(self.reg.est_append_only(chemin))
        for chemin, _ in self.ANCIENS:
            with self.subTest(chemin=chemin):
                self.assertFalse(self.reg.est_append_only(chemin))

    def test_regle_b_refuse_l_ancien_fichier_accepte_le_registre(self):
        plan = "docs/plans/PLAN_AUDIT_STOCK.md"

        def erreurs(chemin):
            texte = ("## BUILD QUEUE\n- [ ] SPL1 — x. Files: `%s`. (ROUTINE)\n"
                     % chemin)
            return co.verifier_plans(self.reg, {plan: texte})

        for ancien, proprio in self.ANCIENS:
            with self.subTest(ancien=ancien):
                e = erreurs(ancien)
                self.assertEqual(len(e), 1, e)
                self.assertIn(f"appartient à « {proprio} »", e[0])
        for ancien, nouveau in self.NOUVEAUX.items():
            with self.subTest(nouveau=nouveau):
                self.assertEqual(erreurs(nouveau), [])

    def test_plan_lanes_garde_l_ancien_chemin_et_retire_le_registre(self):
        for ancien, _ in self.ANCIENS:
            with self.subTest(ancien=ancien):
                self.assertIn(ancien, pl._task_files(f"x. Files: `{ancien}`."))
        for nouveau in self.NOUVEAUX.values():
            with self.subTest(nouveau=nouveau):
                self.assertNotIn(nouveau, pl._task_files(f"x. Files: `{nouveau}`."))

    def test_memoire_partagee_dit_la_meme_regle_que_le_registre(self):
        # Jumeau (leçon 6) : la mémoire propriete-fichiers cite le module-registre
        # des droits, plus l'ancien roles/models.py comme surface append-only.
        memoire = (ROOT / "docs" / "claude-memory" / "propriete-fichiers.md"
                   ).read_text(encoding="utf-8")
        self.assertIn("roles/permissions_registre.py", memoire)
        self.assertNotIn("core/events.py, roles/models.py", memoire)


class TransverseTests(unittest.TestCase):
    """AMET96 — règle (d) : le plan transverse n'accepte qu'une tâche
    `(@atomique: <propriétaires>)` dont le tag égale EXACTEMENT les
    propriétaires de ses `Files:` (déplacement construit en UN commit)."""

    FILES = ("Files: `backend/django_core/apps/ventes/views/devis.py`, "
             "`backend/django_core/apps/crm/cadence_temps.py`, "
             "`frontend/src/router/index.jsx`. (ROUTINE)")

    def setUp(self):
        self.reg = registre()

    def _refus(self, *taches):
        texte = "## BUILD QUEUE\n" + "".join(
            f"- [ ] {tid} — déplacement. {self.FILES}{tag}\n" for tid, tag in taches)
        return co.verifier_transverse(
            self.reg, {"docs/plans/PLAN_TRANSVERSE.md": texte,
                       "docs/plans/PLAN_DEVIS.md": texte})

    def test_tache_sans_atomique_refusee_et_tag_exact_accepte(self):
        erreurs = self._refus(("SPL1", ""), ("SPL2", " (@atomique: devis, cadence)"))
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn("PLAN_TRANSVERSE.md:2 SPL1", erreurs[0])
        self.assertIn("tâche multi-propriétaires : à scinder, contrat d'abord",
                      erreurs[0])
        # Ordre et séparateurs libres ; la surface append-only ne compte pas.
        self.assertEqual(self._refus(("SPL3", " (@atomique: cadence/devis)")), [])
        # Mutant « accepter un tag partiel » : un propriétaire omis = refus.
        partiel = self._refus(("SPL4", " (@atomique: devis)"))
        self.assertEqual(len(partiel), 1, partiel)
        self.assertIn("le tag doit les nommer EXACTEMENT", partiel[0])

    def test_tag_partiel_ou_en_trop_refuse(self):
        for tag in (" (@atomique: devis)", " (@atomique: devis, cadence, fiche)"):
            erreurs = self._refus(("SPL4", tag))
            self.assertEqual(len(erreurs), 1, (tag, erreurs))
            self.assertIn("cadence, devis", erreurs[0])

    def test_seul_le_plan_transverse_et_les_taches_ouvertes(self):
        texte = ("- [x] SPL5 — fait. " + self.FILES + "\n"
                 "- [BLOCKED: attend X] SPL6 — bloqué. " + self.FILES + "\n")
        self.assertEqual(co.verifier_transverse(
            self.reg, {"docs/plans/PLAN_TRANSVERSE.md": texte}), [])

    def test_le_tag_est_lu_par_plan_lanes(self):
        self.assertEqual(pl.proprietaires_atomiques(
            "x (@atomique: crm, devis) (@lane: a)"), {"crm", "devis"})
        self.assertIsNone(pl.proprietaires_atomiques("x (@lane: a)"))
        # Cité en prose (backticks), ce n'est pas un tag.
        self.assertIsNone(pl.proprietaires_atomiques(
            "Tag `(@atomique: <propriétaires>)` ; une tâche `@atomique: crm, devis`"))


if __name__ == "__main__":
    unittest.main()
