"""Validateur v2 : comme valide_lot.py, mais le proprietaire attendu suit la ligne `## → <plan>` (sinon calepinage).
Usage : python v2.py [--root R] fichier... ; n'imprime que les KO + un total par fichier."""
import re, sys, os
from pathlib import Path
args = sys.argv[1:]
ROOT = Path(r"C:/dev/taqinor-os/.claude/worktrees/calpinage-module-enhance-04bba5")
if args and args[0] == "--root":
    ROOT = Path(args[1]); args = args[2:]
args = [str(Path(a).resolve()) for a in args]
sys.path.insert(0, str(ROOT / "scripts")); os.chdir(ROOT)
import yaml
import check_taches_cablage as ctc, check_ancres_taches as cat, check_ownership as co
reg = co.charger_registre()
own = yaml.safe_load(open("docs/ownership.yml", encoding="utf-8"))["owners"]
plan2owner = {v.get("plan"): k for k, v in own.items() if isinstance(v, dict) and v.get("plan")}
tot = 0
for chemin in args:
    texte = Path(chemin).read_text(encoding="utf-8")
    attendu = "calepinage"; nb = ko = 0
    for numero, ligne in enumerate(texte.splitlines(), 1):
        mp = re.match(r"^## → (\S+)", ligne)
        if mp:
            attendu = plan2owner.get(mp.group(1), "?" + mp.group(1)); continue
        m = ctc._TACHE.match(ligne)
        if not m:
            if ligne.strip().startswith("- ["):
                print(f"{Path(chemin).name} L{numero}: case non reconnue"); ko += 1
            continue
        reste = ctc._CROCHETS_RESIDUELS.sub("", m.group("reste"))
        ident = ctc._IDENTIFIANT.match(reste)
        if not ident:
            print(f"L{numero}: id illisible"); ko += 1; continue
        nb += 1
        t = ctc.Tache("docs/plans/PLAN_AUDIT_CALEPINAGE.md", numero, m.group("etat"), ident.group("id"), reste)
        pb = []
        gated = "[GATED" in ligne[:200]
        manq = ctc.clauses_manquantes(t.normalise, "v3")
        if manq: pb.append(f"clauses {manq}")
        if not re.search(r"\(@model:\s*(haiku|sonnet|opus)\)", ligne): pb.append("@model absent")
        if not re.search(r"\((ROUTINE|SCHEMA|ARCH|DECISION|AUTH|COST)\)", ligne): pb.append("categorie absente")
        if re.search(r":\s*n/a\s*(\.|;|$|[A-Z])", ligne): pb.append("n/a nu")
        res, _ = cat.analyser_tache(t, False, ROOT)
        for _id, a, r in res: pb.append(f"ancre {a} - {r}")
        ch = co.chemins_declares(reste)
        if not ch: pb.append("Files vide")
        for c in ch:
            if "*" in c: continue
            p = co.proprietaire(reg, c)
            if p != attendu: pb.append(f"owner {c}={p} (attendu {attendu})")
        try:
            if t.exige_atteignabilite() and not t.fichier_de_montage(): pb.append("montage absent")
        except Exception as e: pb.append(f"montage? {e}")
        if pb:
            ko += 1; print(f"KO {t.identifiant} ({Path(chemin).name}) : " + " | ".join(pb))
    print(f"--- {Path(chemin).name}: {nb} taches, {ko} KO"); tot += ko
sys.exit(1 if tot else 0)
