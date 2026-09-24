#!/usr/bin/env python3
"""SOLMVP54 (21/09/2026) — les gardes hote de `stage-names` et `backend-lint-fast`
tournent EN PARALLELE, dans UN SEUL processus runner, au lieu d'une etape GitHub
Actions chacune.

POURQUOI. Mesure sur le run 35601218482 (main, apres le merge SOLMVP) :
`stage-names` = 3 min 07 s pour 42 etapes `run:` executees l'une apres l'autre,
chacune un processus Python de 0,5 a 23 s ; `backend-lint-fast` = 2 min 04 s pour
45 etapes. Sur un runner a 4 vCPU, trois coeurs dormaient pendant que la garde
courante tournait. Ces gardes sont des analyses STATIQUES independantes (aucune
n'ecrit dans le depot, aucune ne depend du resultat d'une autre) : elles se
parallelisent sans changer leur verdict. Ce runner lance N gardes a la fois
(N = nombre de coeurs), capture la sortie de chacune, et la rejoue dans un bloc
`::group::` par garde, avec un tableau des durees a la fin.

CE QUI NE CHANGE PAS. La LISTE des gardes (nom, commande, repertoire) vit ici,
dans `GARDES`, une seule fois — c'est la meme liste que ci.yml portait etape par
etape, transposee telle quelle le 21/09/2026 (41 + 44 commandes, puis 44 + 44
avec les gardes CALX56/57 arrivees sur main le meme jour). Les deux
`pip install` de preparation restent des etapes ci.yml (elles doivent PRECEDER
les gardes et `scripts/ci_fast_gate_steps.py` les connait). `scripts/preflight.ps1`
continue de voir chaque garde individuellement : `ci_fast_gate_steps.py` DEVELOPPE
l'etape `python scripts/ci_guards.py <job>` en ses entrees (une par garde), donc
un preflight vert implique toujours un job vert, et une garde ajoutee ICI est
reprise par preflight sans rien recopier. `scripts/tests/test_ci_guards.py`
verifie que chaque commande pointe sur un script/module existant, qu'aucune n'est
en double, que ci.yml appelle bien ce runner, et que le developpement preflight
rend une entree par garde.

REGLE POUR AJOUTER UNE GARDE : une ligne dans `GARDES[<job>]`, jamais une etape
`run: python scripts/check_*.py` dans ci.yml (elle tournerait en serie, hors du
tableau des durees — et ce serait une seconde liste a tenir).

Usage
-----
    python scripts/ci_guards.py <job> [--jobs N] [--only MOTIF] [--list]

    <job>      stage-names | backend-lint-fast
    --jobs N   processus simultanes (defaut : nombre de coeurs, au moins 2)
    --only     n'executer que les gardes dont le nom ou la commande contient MOTIF
    --list     imprimer les gardes (nom, repertoire, commande) et sortir

Code de sortie : 0 si toutes les gardes passent, 1 sinon (les gardes en echec
sont nommees en fin de sortie avec leur code). Une commande introuvable ou un
plantage du runner lui-meme est un echec, jamais un vert silencieux.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (nom affiche, commande shell, repertoire de travail relatif a la racine du depot)
GARDES = {
    'stage-names': [
        ('Check pipeline stage names against STAGES.py',
         'python scripts/check_stages.py',
         '.'),
        ('Check module registry <-> frontend consistency (ODX21)',
         'python scripts/check_modules.py',
         '.'),
        ('Check apps parquées (SOLMVP53 — aucun import/FK/url/beat vers une app sortie)',
         'python scripts/check_parked_apps.py',
         '.'),
        ('Tests de la garde apps parquées (SOLMVP53)',
         'python -m unittest scripts.tests.test_check_parked_apps -v',
         '.'),
        ('Check front<->back API contract (aucun appel vers une route inexistante)',
         'python scripts/check_api_contract.py',
         '.'),
        ('Test the API-contract checker itself',
         'python -m unittest scripts.tests.test_check_api_contract -v',
         '.'),
        ('Check API response shapes (aucun mock ne contredit le serveur)',
         'python scripts/check_api_shapes.py',
         '.'),
        ('Test the API-shapes checker itself',
         'python -m unittest scripts.tests.test_check_api_shapes -v',
         '.'),
        ("Check parité tunnel <-> webhook CRM (aucune clé perdue à l'arrivée)",
         'python scripts/check_lead_webhook_parite.py',
         '.'),
        ('Test the lead-webhook parity checker itself (QJR230)',
         'python -m unittest scripts.tests.test_check_lead_webhook_parite -v',
         '.'),
        ('Check OpenAPI response shapes (aucun agrégat ne se déclare « un objet »)',
         'python scripts/check_openapi_shapes.py',
         '.'),
        ('Test the OpenAPI-shapes checker itself (PACT7)',
         'python -m unittest scripts.tests.test_check_openapi_shapes -v',
         '.'),
        ('Check listes de choix à source déclarée (PACT159)',
         'python scripts/check_choices_declares.py',
         '.'),
        ('Test the declared-choices checker itself (PACT159)',
         'python -m unittest scripts.tests.test_check_choices_declares -v',
         '.'),
        ('Check miroirs du vocabulaire de rôles (STKCAT2)',
         'python scripts/check_roles_mirror.py',
         '.'),
        ('Check écrans atteignables (aucun écran livré hors du menu)',
         'python scripts/check_ecrans_atteignables.py',
         '.'),
        ('Test the reachable-screens checker itself',
         'python -m unittest scripts.tests.test_check_ecrans_atteignables -v',
         '.'),
        # CALX56/57 (lots CALX merges le 21/09/2026 pendant la construction de ce
        # runner — PR #706/#708) : chemins parametres atteignables, et services
        # backend livres sans appelant (passif fige dans
        # scripts/services_appeles_allow.txt). Ici pour la meme raison que
        # check_ecrans_atteignables : un consommateur peut disparaitre depuis
        # n'importe ou, seul le job non gate les voit.
        ('Test the parameterized-path reachability rule (CALX56)',
         'python -m unittest scripts.tests.test_check_ecrans_parametres -v',
         '.'),
        ('Check services appelés (aucun service livré sans appelant)',
         'python scripts/check_services_appeles.py',
         '.'),
        ('Test the orphan-service checker itself (CALX57)',
         'python -m unittest scripts.tests.test_check_services_appeles -v',
         '.'),
        # CALX250 (lot 4, 21/09/2026) — aucun seuil électrique sans source :
        # un littéral numérique NEUF de core/electrique/*.py ou des services
        # électriques de calepinage sans commentaire de provenance fait échouer
        # la CI ; passif gelé dans scripts/seuils_electriques_exceptions.txt.
        ('Check seuils électriques (aucun seuil sans source, CALX250)',
         'python scripts/check_seuils_electriques.py',
         '.'),
        ('Test the electrical-threshold-source checker itself (CALX250)',
         'python -m unittest scripts.tests.test_check_seuils_electriques -v',
         '.'),
        ('Check tâches de plan (aucune ne commande du travail mort)',
         'python scripts/check_taches_cablage.py',
         '.'),
        ('Check tâches mixtes (une moitié livrée ne peut pas être cochée)',
         'python scripts/check_plan_taches_mixtes.py',
         '.'),
        ('Test the mixed-task checker itself (PACT12)',
         'python -m unittest scripts.tests.test_check_plan_taches_mixtes -v',
         '.'),
        ('Test the plan-task wiring checker itself',
         'python -m unittest scripts.tests.test_check_taches_cablage -v',
         '.'),
        ('Check no raw JSON / bare error object is shown to the user (EZ16)',
         'python scripts/check_frontend_errors.py',
         '.'),
        ('Test the anti-jargon checker itself (EZ16)',
         'python -m unittest scripts.tests.test_check_frontend_errors -v',
         '.'),
        ('Check test determinism (no sleeps / unfrozen live-clock assertions)',
         'python scripts/check_test_determinism.py',
         '.'),
        ('Check tenant distinctness (a "second tenant" in a test must be a real second row)',
         'python scripts/check_test_tenant_distinctness.py',
         '.'),
        ('Test the tenant-distinctness checker itself',
         'python -m unittest scripts.tests.test_check_test_tenant_distinctness -v',
         '.'),
        ('Check heavy tests carry a @tag (WOW5 — keep the fast tier fast)',
         'python scripts/check_test_tags.py',
         '.'),
        ('Check invariant registry (docs/invariants.md still points at real tests)',
         'python scripts/check_invariants.py',
         '.'),
        ('Check CODEMAP structural fingerprint',
         'python scripts/codemap_fingerprint.py --check',
         '.'),
        ('Check for unsafe migration DDL patterns (YOPSB4)',
         'python scripts/check_safe_migrations.py',
         '.'),
        ('Test the safe-migrations checker itself (YOPSB4)',
         'python -m unittest scripts.tests.test_check_safe_migrations -v',
         '.'),
        ('Validate docs/BUILD_ORDER.yml (SCA5 — acyclic DAG, parseable thresholds, no orphaned plan prefix)',
         'python scripts/check_build_order.py',
         '.'),
        ('Test the BUILD_ORDER.yml checker itself (SCA5)',
         'python -m unittest scripts.tests.test_check_build_order -v',
         '.'),
        ('Check écritures Odoo (règle',
         'python scripts/check_odoo_writes.py',
         '.'),
        ('Test the Odoo-writes checker itself (CRX11)',
         'python -m unittest scripts.tests.test_check_odoo_writes -v',
         '.'),
        ('Test the testdb-cache safety guard itself (WOW8 — a wrong DELTA verdict false-greens a stale schema)',
         'python -m unittest scripts.tests.test_ci_testdb_manifest_diff -v',
         '.'),
        ('Test the backend-test shard split itself (WOW-CI2 — completude du decoupage)',
         'python -m unittest scripts.tests.test_ci_shard -v',
         '.'),
        ('Test the frontend-test lane split itself (WOW-CI4 — completude du decoupage)',
         'python -m unittest scripts.tests.test_ci_frontend_shard -v',
         '.'),
        ('Test the ci.yml changes filter itself (AUD826 — scripts/ est une surface backend)',
         'python -m unittest scripts.tests.test_ci_changes_filter -v',
         '.'),
        ('Check query-budget test coverage (endpoints "enforced" doivent avoir un test de budget)',
         'python scripts/check_query_budgets.py',
         '.'),
        ('Test the query-budgets checker itself (AUD831)',
         'python -m unittest scripts.tests.test_check_query_budgets -v',
         '.'),
        # CALX329 (lot 6, 23/09/2026) — meme famille que check_ecrans_
        # atteignables/check_services_appeles : un document DECLARE dans
        # SPEC_PIECES/PIECES_PRODUITES/l'inventaire `documents` du
        # calepinage doit avoir un RENDU (le defaut de CALX309 — 4 pieces
        # declarees, 2 rendues, invisible avant qu'un humain ouvre l'ecran).
        ('Check documents calepinage (un document déclaré a un rendu, CALX329)',
         'python scripts/check_documents_calepinage.py',
         '.'),
        ('Test the declared-document-renders checker itself (CALX329)',
         'python -m unittest scripts.tests.test_check_documents_calepinage -v',
         '.'),
        # CALX381 (lot 8, 23/09/2026) — meme famille que check_services_appeles/
        # check_ecrans_atteignables : rapport_backend_sombre.py ecarte EXPRES
        # les sous-routes @action de son perimetre (« une @action n'est pas
        # une ressource ») — angle mort total sur les 71 @action calepinage,
        # dont 21 sans aucun consommateur au 23/09/2026.
        ('Check actions calepinage consommées (aucune @action sans appelant, CALX381)',
         'python scripts/check_calepinage_actions_consommees.py',
         '.'),
        ('Test the calepinage-actions-consumed checker itself (CALX381)',
         'python -m unittest scripts.tests.test_check_calepinage_actions_consommees -v',
         '.'),
        # CALX383 (lot 8, 23/09/2026) — le registre atelier/onglets.js (CALX1)
        # n'obligeait mecaniquement aucun onglet a porter un test ; mesure :
        # 5 des 27 onglets (panneaux « Site » anterieurs a CALX1) n'en ont
        # aucun, passif gele dans onglets_calepinage_sans_test_allow.txt.
        ('Check onglets calepinage testés (un onglet du rail arrive avec son test, CALX383)',
         'python scripts/check_onglets_calepinage_testes.py',
         '.'),
        ('Test the onglets-tested checker itself (CALX383)',
         'python -m unittest scripts.tests.test_check_onglets_calepinage_testes -v',
         '.'),
    ],
    'backend-lint-fast': [
        ('Byte-compile on prod Python (catches 3.11-only SyntaxErrors, incl. in flake8-noqa files)',
         'python -m compileall -q backend/django_core/apps backend/django_core/erp_agentique backend/fastapi_ia',
         '.'),
        ('Lint backend (flake8)',
         'flake8 backend --max-line-length=120 --extend-ignore=E501 --exclude=migrations,parked',
         '.'),
        ('Lint imports (import-linter contracts — M3)',
         'lint-imports',
         'backend/django_core'),
        ('Platform-kernel guards (check_platform — ARC8/26/11/6)',
         'python scripts/check_platform.py',
         '.'),
        ('Check on_delete completeness/justification (YDATA1/3)',
         'python scripts/check_on_delete.py',
         '.'),
        ('Check financial-target on_delete sweep (YDATA2)',
         'python scripts/check_on_delete.py --financial',
         '.'),
        ('Check multi-tenant company-FK completeness (YDATA4)',
         'python scripts/check_company_fk.py',
         '.'),
        ('Check money fields are DecimalField (YDATA6)',
         'python scripts/check_money_fields.py',
         '.'),
        ('Check money DecimalField max_digits/decimal_places (YDATA7)',
         'python scripts/check_money_fields.py --decimal-places',
         '.'),
        ('Check money rounding convention (YDATA8/QJR4, advisory)',
         'python scripts/check_money_rounding.py',
         '.'),
        ('Test the money-rounding checker itself (QJR4)',
         'python -m unittest scripts.tests.test_check_money_rounding -v',
         '.'),
        ('Check statut read_only on state-machine models (AUD515)',
         'python scripts/check_machine_etats_statut_readonly.py',
         '.'),
        ('Test the state-machine statut checker itself (AUD515)',
         'python -m unittest scripts.tests.test_check_machine_etats_statut_readonly -v',
         '.'),
        ('Check override-registry write sites (QJR6, advisory)',
         'python scripts/check_override_registry.py',
         '.'),
        ('Test the override-registry checker itself (QJR6)',
         'python -m unittest scripts.tests.test_check_override_registry -v',
         '.'),
        ('Check market-mode enumeration parity (QJR231)',
         'python scripts/check_modes_marche.py',
         '.'),
        ('Test the market-mode parity checker itself (QJR231)',
         'python -m unittest scripts.tests.test_check_modes_marche -v',
         '.'),
        ('Check for new source-regex tests (QJR239)',
         'python scripts/check_tests_source_regex.py',
         '.'),
        ('Test the source-regex checker itself (QJR239)',
         'python -m unittest scripts.tests.test_check_tests_source_regex -v',
         '.'),
        ('Check for naive datetime / DateField timestamps (YDATA10/11)',
         'python scripts/check_naive_datetime.py',
         '.'),
        ('Check Celery task signatures (YDATA14, advisory)',
         'python scripts/check_celery_tasks.py',
         '.'),
        ('Check scheduled management commands (AUD231)',
         'python scripts/check_commandes_planifiees.py',
         '.'),
        ('Test the scheduled-commands checker itself (AUD231)',
         'python -m unittest scripts.tests.test_check_commandes_planifiees -v',
         '.'),
        ('Check get_or_create/update_or_create audit (YDATA15, advisory)',
         'python scripts/check_get_or_create.py',
         '.'),
        ('Currency mono-devise sweep (check_money_monodevise — YDATA22, advisory)',
         'python scripts/check_money_monodevise.py',
         '.'),
        ('Check read-modify-write locking on shared counters (YDATA16)',
         'python scripts/check_read_modify_write.py',
         '.'),
        ('Test the read-modify-write checker itself (YDATA16)',
         'python -m unittest scripts.tests.test_check_read_modify_write -v',
         '.'),
        ('Check MouvementStock passe par son service unique (AUD223)',
         'python scripts/check_mouvement_stock_service.py',
         '.'),
        ('Test the MouvementStock-service checker itself (AUD223)',
         'python -m unittest scripts.tests.test_check_mouvement_stock_service -v',
         '.'),
        ('Check fan-outs beat scopés aux sociétés actives (AUD415)',
         'python scripts/check_beat_active_companies.py',
         '.'),
        ('Test the beat-active-companies checker itself (AUD415)',
         'python -m unittest scripts.tests.test_check_beat_active_companies -v',
         '.'),
        ('Check unique constraints are tenant-scoped (YDATA18)',
         'python scripts/check_unique_scoping.py',
         '.'),
        ('Test the unique-scoping checker itself (YDATA18)',
         'python -m unittest scripts.tests.test_check_unique_scoping -v',
         '.'),
        ('Check migration safety — 3-step constraints + name drift (YDATA20)',
         'python scripts/check_migration_safety.py',
         '.'),
        ('Test the migration-safety checker itself (YDATA20)',
         'python -m unittest scripts.tests.test_check_migration_safety -v',
         '.'),
        ('Check multi-tenant view isolation (YDATA21)',
         'python scripts/check_tenant_isolation.py',
         '.'),
        ('Test the tenant-isolation checker itself (YDATA21)',
         'python -m unittest scripts.tests.test_check_tenant_isolation -v',
         '.'),
        ('Check viewset tenant base vs model scope (AUD834)',
         'python scripts/check_viewset_model_scope.py',
         '.'),
        ('Test the viewset-model-scope checker itself (AUD834)',
         'python -m unittest scripts.tests.test_check_viewset_model_scope -v',
         '.'),
        ('Check @action permissions are never silently overridden (AUD421)',
         'python scripts/check_action_permission_override.py',
         '.'),
        ('Test the action-permission checker itself (AUD421)',
         'python -m unittest scripts.tests.test_check_action_permission_override -v',
         '.'),
        ('Check cross-app FK serializer scoping (AUD601)',
         'python scripts/check_fk_scoping.py',
         '.'),
        ('Test the FK-scoping checker itself (AUD601)',
         'python -m unittest scripts.tests.test_check_fk_scoping -v',
         '.'),
        ('Check ao API contract — frontend calls vs registered routes',
         'python scripts/check_ao_api_contract.py',
         '.'),
    ],
}


def gardes_de(job: str, only: str | None = None) -> list[tuple[str, str, str]]:
    """Les gardes du job, filtrees par `only` (sous-chaine du nom ou de la commande)."""
    if job not in GARDES:
        raise SystemExit(
            f"ci_guards: job inconnu '{job}' — jobs connus : {', '.join(sorted(GARDES))}"
        )
    rows = GARDES[job]
    if only:
        rows = [r for r in rows if only in r[0] or only in r[1]]
        if not rows:
            raise SystemExit(f"ci_guards: aucune garde de '{job}' ne contient '{only}'")
    return list(rows)


def _executer(garde: tuple[str, str, str], repo_root: str = REPO_ROOT) -> dict:
    """Lance UNE garde, sortie capturee ; ne leve jamais (un plantage = echec)."""
    nom, commande, wd = garde
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUNBUFFERED", "1")
    debut = time.monotonic()
    try:
        proc = subprocess.run(
            commande, shell=True, cwd=os.path.join(repo_root, wd), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        code, sortie = proc.returncode, proc.stdout.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 — un runner qui plante est un rouge, pas un vert
        code, sortie = 99, f"ci_guards: impossible de lancer la garde ({exc!r})\n"
    return {"nom": nom, "commande": commande, "wd": wd, "code": code,
            "sortie": sortie, "duree": time.monotonic() - debut}


def _afficher(res: dict, gh: bool) -> None:
    etat = "OK   " if res["code"] == 0 else "ECHEC"
    titre = f"{etat} {res['duree']:5.1f}s  {res['nom']}"
    print(f"::group::{titre}" if gh else f"===== {titre}")
    suffixe = f"   (cd {res['wd']})" if res["wd"] not in (".", "") else ""
    print(f"$ {res['commande']}{suffixe}")
    if res["sortie"].strip():
        print(res["sortie"].rstrip("\n"))
    if res["code"] != 0:
        print(f"ci_guards: code de sortie {res['code']}")
    if gh:
        print("::endgroup::")
    sys.stdout.flush()


def run_guards(gardes: list[tuple[str, str, str]], jobs: int,
               repo_root: str = REPO_ROOT, gh: bool | None = None) -> list[dict]:
    """Execute les gardes en parallele ; rend la liste des resultats en ECHEC.

    Les blocs sont imprimes au fil des fins d'execution (progression visible
    dans un journal long) ; le tableau final, lui, est trie par duree decroissante
    pour designer la prochaine garde a optimiser.
    """
    if gh is None:
        gh = bool(os.environ.get("GITHUB_ACTIONS"))
    resultats: list[dict] = []
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futurs = {pool.submit(_executer, g, repo_root): g for g in gardes}
        for futur in as_completed(futurs):
            res = futur.result()
            resultats.append(res)
            _afficher(res, gh)
    mur = time.monotonic() - t0
    echecs = [r for r in resultats if r["code"] != 0]
    print()
    print(f"ci_guards: {len(resultats)} garde(s), {jobs} processus, "
          f"temps de mur {mur:.1f}s, somme des durees "
          f"{sum(r['duree'] for r in resultats):.1f}s")
    print("  les plus longues :")
    for r in sorted(resultats, key=lambda r: -r["duree"])[:8]:
        print(f"    {r['duree']:6.1f}s  {r['nom']}")
    if echecs:
        print()
        print(f"ci_guards: {len(echecs)} garde(s) en ECHEC :")
        for r in sorted(echecs, key=lambda r: r["nom"]):
            print(f"  - {r['nom']}  (code {r['code']})  $ {r['commande']}")
            if gh:
                print(f"::error title=Garde en echec::{r['nom']} — code {r['code']}")
    sys.stdout.flush()
    return echecs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("job", choices=sorted(GARDES))
    parser.add_argument("--jobs", type=int, default=max(2, os.cpu_count() or 2))
    parser.add_argument("--only", default=None)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    gardes = gardes_de(args.job, args.only)
    if args.list:
        for nom, commande, wd in gardes:
            print(f"[{wd}] {nom}\n    $ {commande}")
        return 0
    print(f"ci_guards: {args.job} — {len(gardes)} garde(s) sur {args.jobs} processus")
    sys.stdout.flush()
    return 1 if run_guards(gardes, args.jobs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
