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


if __name__ == "__main__":
    unittest.main()
