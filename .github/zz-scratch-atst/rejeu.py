# flake8: noqa
"""ESSAI TEMPORAIRE (13/11/2026) — rejeu sur runner GitHub des preuves en direct du groupe ATST
(parcours PF7 « tests qui ne prouvent rien », docs/audits/2026-11-11-parcours-PF7.md).

Lancé par `.github/workflows/zz-scratch-acceptation-atst.yml` ; supprimé avec lui au dernier commit
(il reste lisible dans l'historique git, au sha rejoué).

    python .github/zz-scratch-atst/rejeu.py hote   <dossier_sortie>   # ATST41-53 (gardes scripts/check_*.py)
    python .github/zz-scratch-atst/rejeu.py django <dossier_sortie>   # ATST21-23 (tests Django, image CI)

Chaque étape = la clause « Preuve en direct » de sa tâche, jouée telle quelle :
  * sonde hôte du constat rejouée ⇒ `repro` False ;
  * module de test nommé lancé sur le dépôt ⇒ vert ; garde lancée sur le dépôt réel ⇒ 0 ;
  * mutants de la tâche appliqués sur une COPIE du dépôt (jamais l'arbre du checkout) ⇒ module ROUGE
    par un échec de test (`FAILED (failures|errors=…)`, jamais une erreur de syntaxe du mutant) ;
    contrôle : le même module sur la copie NON mutée ⇒ vert.
Sortie : <dossier_sortie>/etapes.json (liste {id, taches, verdict, notes, log}) + un journal par étape.
Rien n'est affaibli : une vérification qui échoue rend l'étape FAIL et le job rouge.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
SECTION, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable
DJ = Path("backend/django_core")
_COPIE = []


def sh(cmd, cwd=ROOT, env=None, timeout=2400):
    e = dict(os.environ)
    e.update(env or {})
    e.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        p = subprocess.run(cmd, cwd=str(cwd), env=e, shell=isinstance(cmd, str), capture_output=True,
                           text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as exc:
        return 124, f"TIMEOUT {exc}"


def copie():
    """Copie du dépôt (hors node_modules/dist/caches) — les mutants ne touchent JAMAIS le checkout."""
    if not _COPIE:
        dest = Path(tempfile.mkdtemp(prefix="atst-copie-")) / "depot"
        shutil.copytree(ROOT, dest, symlinks=True, ignore=shutil.ignore_patterns(
            "node_modules", "dist", "playwright-report", "test-results", "__pycache__", ".pytest_cache"))
        _COPIE.append(dest)
    return _COPIE[0]


class Etape:
    def __init__(self, ident, taches):
        self.id, self.taches, self.ok, self.lignes, self.resume = ident, taches, True, [], []

    def log(self, texte):
        self.lignes.append(texte)

    def verifie(self, libelle, cond, detail=""):
        cond = bool(cond)
        self.ok &= cond
        self.resume.append(("OK " if cond else "ÉCHEC ") + libelle)
        self.log(f"==> {'OK' if cond else 'ECHEC'} : {libelle}{(' — ' + detail) if detail else ''}\n")
        return cond

    def cmd(self, libelle, cmd, cwd=ROOT, env=None, rouge=False, motif=None, sans=None):
        rc, out = sh(cmd, cwd, env)
        lisible = cmd if isinstance(cmd, str) else " ".join(cmd)
        ou = "copie" if _COPIE and str(cwd).startswith(str(_COPIE[0])) else "checkout"
        self.log(f"$ {lisible}    [{ou}: {Path(cwd).name}]  rc={rc}\n{out[-30000:]}\n")
        if rouge:  # un mutant doit rougir par un ÉCHEC DE TEST, pas par sa propre syntaxe
            cond = rc != 0 and re.search(r"FAILED \((failures|errors)=", out) \
                and not re.search(r"SyntaxError|IndentationError", out)
            echecs = sorted(set(re.findall(r"^(?:FAIL|ERROR): (\S+ \([^)]*\))", out, re.M)))
            self.verifie(f"{libelle} (rc={rc})", cond, "tests rouges : " + "; ".join(echecs[:6]))
        else:
            cond = rc == 0
            if motif:
                cond = cond and re.search(motif, out, re.M)
            if sans:
                cond = cond and not re.search(sans, out, re.M)
            self.verifie(f"{libelle} (rc={rc})", cond)
        return rc, out

    def sonde(self, constat):
        code = ('import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); '
                'print("@@S" + json.dumps(ns["sonde"](), default=str, ensure_ascii=False))')
        chemin = f"docs/audits/sondes/ATST/{constat}.py"
        rc, out = sh([PY, "-I", "-c", code, chemin])
        self.log(f"$ sonde {chemin}  rc={rc}\n{out[-8000:]}\n")
        ligne = next((x for x in out.splitlines() if x.startswith("@@S")), None)
        res = json.loads(ligne[3:]) if ligne else {}
        self.verifie(f"sonde {constat} rejouée ⇒ repro False (repro={res.get('repro')!r})",
                     ligne is not None and res.get("repro") is False)

    def mutants(self, test_cmd, mutants, cwd_rel="."):
        """Contrôle sur la copie non mutée (vert) puis chaque mutant (rouge), fichier restauré après."""
        base = copie()
        self.cmd("contrôle : copie NON mutée ⇒ vert", test_cmd, cwd=base / cwd_rel)
        for rel, ancien, nouveau, ancre, desc in mutants:
            f = base / rel
            src = f.read_text(encoding="utf-8")
            motif = re.compile(("^" if ancre else "") + re.escape(ancien), re.M)
            n = len(motif.findall(src))
            if n != 1:
                self.verifie(f"mutant « {desc} » appliqué", False, f"{n} occurrence(s) de {ancien!r} dans {rel}")
                continue
            f.write_text(motif.sub(lambda m: nouveau, src, count=1), encoding="utf-8")
            self.log(f"--- mutant « {desc} » : {rel}\n    - {ancien!r}\n    + {nouveau!r}\n")
            try:
                self.cmd(f"mutant « {desc} » sur la copie ⇒ module ROUGE", test_cmd, cwd=base / cwd_rel, rouge=True)
            finally:
                f.write_text(src, encoding="utf-8")

    def fin(self):
        nom = f"{self.id}.txt"
        (OUT / nom).write_text("\n".join(self.lignes), encoding="utf-8")
        return {"id": self.id, "taches": self.taches, "verdict": "PASS" if self.ok else "FAIL",
                "notes": " ; ".join(self.resume), "log": nom}


def ok_re(nom):
    """Ligne unittest -v d'un test vert (docstring éventuelle sur la ligne suivante)."""
    return "^" + re.escape(nom) + r" \([^)]*\)(?:\n[^\n]*?)? \.\.\. ok$"


def ut(module):
    return [PY, "-m", "unittest", module, "-v"]


# ── HÔTE : ATST41-53 (gardes de dépôt) ────────────────────────────────────────────────────────────────
def m(rel, ancien, nouveau, desc, ancre=True):
    return (rel, ancien, nouveau, ancre, desc)


GARDES = [
    # id, tâche, module(s) de test, garde sur le dépôt réel, mutants (sur copie)
    ("ATST41", "scripts.tests.test_check_company_fk", "scripts/check_company_fk.py", [
        m("scripts/check_company_fk.py", "        if not ok and key not in exempt:", "        if False:",
          "if not ok and key not in exempt → if False"),
        m("scripts/check_company_fk.py",
          "    changed = True\n    while changed:\n        changed = False\n        for key, info in graph.items():",
          "    changed = False\n    while changed:\n        changed = False\n        for key, info in graph.items():",
          "point fixe de resolve_has_company retiré")]),
    ("ATST43", "scripts.tests.test_check_read_modify_write", "scripts/check_read_modify_write.py", [
        m("scripts/check_read_modify_write.py", "            if _function_saves_var(node, varname):",
          "            if False:", "check_file : if _function_saves_var(...) → if False"),
        m("scripts/check_read_modify_write.py", "    if offenders:", "    if False:", "main : if offenders → if False")]),
    ("ATST44", "scripts.tests.test_check_invariants", "scripts/check_invariants.py", [
        m("scripts/check_invariants.py", "        if not _find_method_in_class(tree, class_name, method_name):",
          "        if False:", "main : if not _find_method_in_class(...) → if False")]),
    ("ATST45", "scripts.tests.test_check_tests_sautes_environnement", "scripts/check_tests_sautes_environnement.py", [
        m("scripts/check_tests_sautes_environnement.py", "    non_signes = sorted(set(trouves) - signes)",
          "    non_signes = []", "non_signes = []"),
        m("scripts/check_tests_sautes_environnement.py", '{"skipTest", "skip"}', '{"skip"}',
          '{"skipTest", "skip"} → {"skip"}', ancre=False)]),
    ("ATST46", "scripts.tests.test_check_odoo_writes", "scripts/check_odoo_writes.py", [
        m("scripts/check_odoo_writes.py", "    _verifier_appels(textes, echecs)\n", "    pass\n",
          "main sans _verifier_appels"),
        m("scripts/check_odoo_writes.py", "    _verifier_allowlist_execution(textes, echecs)\n", "    pass\n",
          "main sans _verifier_allowlist_execution"),
        m("scripts/check_odoo_writes.py", "    _verifier_transports_declares(textes, echecs)\n", "    pass\n",
          "main sans _verifier_transports_declares"),
        m("scripts/check_odoo_writes.py", "    _verifier_module_dormant(textes, echecs)\n", "    pass\n",
          "main sans _verifier_module_dormant"),
        m("scripts/check_odoo_writes.py", "    if echecs:", "    if False:", "main : if echecs → if False")]),
    ("ATST47", "scripts.tests.test_check_unique_scoping", "scripts/check_unique_scoping.py", [
        m("scripts/check_unique_scoping.py", "    if offenders:", "    if False:", "if offenders → if False"),
        m("scripts/check_unique_scoping.py", "    for path in _iter_models_files():", "    for path in []:",
          "for path in []"),
        m("scripts/check_unique_scoping.py", "            if _autorise(key, allow):", "            if True:",
          "if True: continue")]),
    ("ATST48", "scripts.tests.test_check_action_permission_override", "scripts/check_action_permission_override.py", [
        m("scripts/check_action_permission_override.py", "    if offenders:", "    if False:", "if offenders → if False"),
        m("scripts/check_action_permission_override.py", "    for path in _iter_source_files():", "    for path in []:",
          "for path in []"),
        m("scripts/check_action_permission_override.py",
          "        if len(raison) < RAISON_MIN or RAISON_COLLECTIVE in raison.lower():",
          "        if RAISON_COLLECTIVE in raison.lower():", "contrôle RAISON_MIN neutralisé")]),
    ("ATST49", "scripts.tests.test_check_money_rounding", "scripts/check_money_rounding.py", [
        m("scripts/check_money_rounding.py", "    if offenders:", "    if False:", "if offenders → if False"),
        m("scripts/check_money_rounding.py", "    sites = scan()", "    sites = []", "sites = scan() → sites = []")]),
    ("ATST50", "scripts.tests.test_check_mouvement_stock_service", "scripts/check_mouvement_stock_service.py", [
        m("scripts/check_mouvement_stock_service.py", "    if offenders:", "    if False:", "if offenders → if False"),
        m("scripts/check_mouvement_stock_service.py", "    for path in _iter_source_files():", "    for path in []:",
          "for path in _iter_source_files() → for path in []")]),
    ("ATST52", "scripts.tests.test_check_no_anon_snapshot", "scripts/check_no_anon_snapshot.py", [
        m("scripts/check_no_anon_snapshot.py", "    bad = []\n    for p in paths:",
          "    return []\n    bad = []\n    for p in paths:", "offending rend []"),
        m("scripts/check_no_anon_snapshot.py", "        return 1\n    paths = [p for p",
          "        return 0\n    paths = [p for p", "except qui rend 0")]),
    ("ATST53", "scripts.tests.test_check_tests_source_regex", "scripts/check_tests_source_regex.py", [
        m("scripts/check_tests_source_regex.py",
          "    trouves = []\n    for rel, arbre in _fichiers_test_backend(_candidat_source):",
          "    return []\n    trouves = []\n    for rel, arbre in _fichiers_test_backend(_candidat_source):",
          "scan_backend rend []"),
        m("scripts/check_tests_source_regex.py", "if code not in codes and not RE_CODE_DYNAMIQUE.match(code)",
          "if False and code not in codes and not RE_CODE_DYNAMIQUE.match(code)", "tout code admis", ancre=False)]),
]


def gh_json(args):
    rc, out = sh(["gh"] + args)
    try:
        return rc, json.loads(out) if rc == 0 else None, out
    except ValueError:
        return rc, None, out


def atst42():
    e = Etape("PF7.4-ATST42", ["ATST42"])
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    e.cmd("tests de la garde (scripts.tests.test_nightly_alert_gate)", ut("scripts.tests.test_nightly_alert_gate"))
    e.cmd("tests du workflow (scripts.tests.test_release_verify_workflow)", ut("scripts.tests.test_release_verify_workflow"))
    rc, data, out = gh_json(["issue", "view", "726", "--repo", repo, "--json", "comments"])
    e.log(f"$ gh issue view 726 --json comments  rc={rc}\n")
    if not e.verifie("lecture seule de l'issue #726", data is not None, out[-500:]):
        return e.fin()
    dernier = data["comments"][-1]
    e.log(f"--- dernier commentaire ({dernier.get('createdAt')}) :\n{dernier.get('body')}\n")
    corps = dernier.get("body") or ""
    run_id = (re.search(r"actions/runs/(\d+)", corps) or [None, None])[1]
    nommes = re.search(r"Jobs non verts\s*:\s*(.+)", corps)
    e.verifie("le dernier commentaire nomme les jobs rouges (« Jobs non verts : … »)", nommes is not None)
    rc, run, out = gh_json(["run", "view", str(run_id), "--repo", repo, "--json", "jobs,headSha,event,createdAt,conclusion"])
    if not e.verifie(f"run nocturne {run_id} lu", run is not None, out[-500:]):
        return e.fin()
    six = ["ci-image-check", "backend-full", "frontend-full", "e2e-full", "web-full", "fastapi-tests"]
    concl = {j["name"]: j["conclusion"] for j in run["jobs"]}
    e.log(f"--- run {run_id} ({run['event']}, {run['createdAt']}, sha {run['headSha']}) jobs : {json.dumps(concl)}\n")
    rouges = {n for n in six if concl.get(n) != "success"}
    listes = {x.strip(" `.") for x in re.split(r"[,\s]+", nommes.group(1)) if x.strip(" `.")} if nommes else set()
    e.verifie(f"jobs nommés {sorted(listes)} == jobs non verts du run {sorted(rouges)}", listes == rouges and rouges)
    e.verifie("run planifié (schedule)", run["event"] == "schedule")
    rc, cmp_, out = gh_json(["api", f"repos/{repo}/compare/e1bb12cca2157f5cc9527b4a56f00988fc895ec0...{run['headSha']}"])
    statut = (cmp_ or {}).get("status")
    e.log(f"--- compare e1bb12cca (commit ATST42)...{run['headSha']} : {statut}\n")
    e.verifie(f"le nocturne lu contient le commit ATST42 e1bb12cca (compare : {statut})", statut in ("ahead", "identical"))
    return e.fin()


def atst51():
    e = Etape("PF7.4-ATST51", ["ATST51"])
    rc, out = sh([PY, "-c", "import django"])
    e.verifie("Django NON importable sur ce runner (comme le job stage-names)", rc != 0, out.strip()[-200:])
    e.cmd("test_table_django_figee « ok », pas « skipped », sans Django",
          ut("scripts.tests.test_check_test_tenant_distinctness"),
          motif=ok_re("test_table_django_figee"), sans=r"test_table_django_figee .*skipped")
    e.cmd("garde sur le dépôt réel ⇒ 0", [PY, "scripts/check_test_tenant_distinctness.py"])
    e.mutants(ut("scripts.tests.test_check_test_tenant_distinctness"), [
        m("scripts/check_test_tenant_distinctness.py", '.strip("-_")', '.strip("-")', '.strip("-_") → .strip("-")', ancre=False)])
    # Journal du job `stage-names` d'une fusion réelle sur main (lecture seule).
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    rc, runs, out = gh_json(["run", "list", "--repo", repo, "--workflow", "ci.yml", "--branch", "main", "--event", "push",
                             "--status", "success", "--limit", "1", "--json", "databaseId,headSha,createdAt"])
    if e.verifie("dernière fusion verte de main lue", bool(runs), out[-300:]):
        r = runs[0]
        rc, run, out = gh_json(["run", "view", str(r["databaseId"]), "--repo", repo, "--json", "jobs"])
        jid = next((j["databaseId"] for j in (run or {}).get("jobs", []) if j["name"] == "stage-names"), None)
        rc, log = sh(["gh", "run", "view", "--repo", repo, "--job", str(jid), "--log"])
        lignes = [x for x in log.splitlines() if "test_table_django_figee" in x]
        e.log(f"--- fusion {r['databaseId']} ({r['createdAt']}, sha {r['headSha']}), job stage-names {jid} :\n"
              + "\n".join(lignes) + "\n")
        e.verifie("journal stage-names de la fusion : test_table_django_figee « ok », pas « skipped »",
                  any(x.rstrip().endswith("... ok") for x in lignes) and not any("skipped" in x for x in lignes))
    return e.fin()


def hote():
    etapes = []
    for ident, module, garde, muts in GARDES:
        e = Etape(f"PF7.4-{ident}", [ident])
        if ident == "ATST41":
            e.sonde("C-ATST-006")
            e.cmd("garde branchée : scripts.tests.test_ci_guards.ToutEstBrancheTests",
                  ut("scripts.tests.test_ci_guards.ToutEstBrancheTests"))
        if ident == "ATST52":
            e.cmd("garde branchée : scripts.tests.test_ci_guards.ToutEstBrancheTests",
                  ut("scripts.tests.test_ci_guards.ToutEstBrancheTests"))
        e.cmd(f"module {module} sur le dépôt ⇒ vert", ut(module))
        rc, out = e.cmd(f"garde {garde} sur le dépôt réel ⇒ 0", [PY, garde])
        if ident == "ATST53":
            compte = re.search(r"stock gele : (\d+) test\(s\) front, (\d+) test\(s\) back, (\d+) code", out)
            bases = {}
            for nom in ("scripts/tests_source_regex_allow.txt", "scripts/tests_permissions_hors_registre_allow.txt"):
                t = Path(nom).read_text(encoding="utf-8") if Path(nom).is_file() else ""
                bases[nom] = sum(1 for x in t.splitlines() if x.strip() and not x.lstrip().startswith("#"))
            e.log(f"--- décomptes imprimés : {compte.groups() if compte else None} ; entrées des bases : {bases}\n")
            e.verifie(f"décomptes imprimés (front, back, codes) = {compte.groups() if compte else None} ; bases {bases}",
                      compte is not None)
        e.mutants(ut(module), muts)
        etapes.append(e.fin())
        if ident == "ATST41":
            etapes.append(atst42())
        if ident == "ATST50":
            etapes.append(atst51())
    return etapes


# ── DJANGO : ATST21-23 (tests non tagués joués à chaque fusion) ───────────────────────────────────────
def dj(*labels):
    return [PY, "manage.py", "test", *labels, "--keepdb", "--noinput", "-v", "2",
            "--exclude-tag=pdf", "--exclude-tag=slow"]


def django():
    etapes = []
    e = Etape("PF7.1-ATST21", ["ATST21"])
    e.sonde("C-ATST-003")
    mod = "apps.ventes.tests.test_qg9_variante_pct"
    e.cmd("module joué comme un shard de fusion ⇒ vert, test_commercial_et_viewer_livres_refuses ok", dj(mod), cwd=DJ,
          motif=ok_re("test_commercial_et_viewer_livres_refuses"))
    e.mutants(dj(mod + ".VarianteConfigEndpointTests"), [
        m(str(DJ / "apps/ventes/views/devis.py"), "or role_nom in ('Directeur', 'Commercial responsable')",
          "or role_nom in ('Directeur', 'Commercial responsable', 'Commercial')",
          "« Commercial » ajouté au tuple de la garde par nom", ancre=False)], cwd_rel=str(DJ))
    etapes.append(e.fin())

    e = Etape("PF7.3-ATST22", ["ATST22"])
    e.sonde("C-ATST-004")
    mod = "apps.ventes.tests.test_moteur_zero_invention"
    e.cmd("module joué comme un shard de fusion ⇒ vert, test_economies_decochees_aucun_montant_au_html ok", dj(mod),
          cwd=DJ, motif=ok_re("test_economies_decochees_aucun_montant_au_html"))
    e.mutants(dj(mod + ".M10SectionsMasqueesHtmlTests"), [
        m(str(DJ / "apps/ventes/quote_engine/etude_chiffrage.py"),
          'masquer_economies |= "economies" in opts.get("sections_masquees", ())', "pass  # mutant ATST22",
          "ligne masquer_economies |= … sections_masquees supprimée", ancre=False)], cwd_rel=str(DJ))
    etapes.append(e.fin())

    e = Etape("PF7.3-ATST23", ["ATST23"])
    e.sonde("C-ATST-005")
    mod = "apps.ventes.tests.test_remise_par_ligne"
    e.cmd("module joué comme un shard de fusion ⇒ vert, test_premium_et_une_page_… ok", dj(mod), cwd=DJ,
          motif=ok_re("test_premium_et_une_page_montrent_le_prix_barre_et_le_prix_remise"))
    e.mutants(dj(mod + ".TestHtmlRemiseParLigne"), [
        m(str(DJ / "apps/ventes/quote_engine/generate_devis_premium.py"),
          "_cellule_prix_remise(pu_ht, _item_pu_ht_remise(it))", "_cellule_prix_remise(pu_ht, pu_ht)",
          "premium (equip_rows) : _cellule_prix_remise(pu_ht, pu_ht)", ancre=False),
        m(str(DJ / "apps/ventes/quote_engine/legacy_onepage.py"),
          "_g._cellule_prix_remise(pu_ht, _g._item_pu_ht_remise(it))", "_g._cellule_prix_remise(pu_ht, pu_ht)",
          "une-page (page_onepage) : _cellule_prix_remise(pu_ht, pu_ht)", ancre=False)], cwd_rel=str(DJ))
    etapes.append(e.fin())
    return etapes


if __name__ == "__main__":
    etapes = hote() if SECTION == "hote" else django()
    (OUT / "etapes.json").write_text(json.dumps(etapes, ensure_ascii=False, indent=1), encoding="utf-8")
    for x in etapes:
        print(f"{x['verdict']}  {x['id']}  {x['notes']}")
    sys.exit(0 if all(x["verdict"] == "PASS" for x in etapes) else 1)
