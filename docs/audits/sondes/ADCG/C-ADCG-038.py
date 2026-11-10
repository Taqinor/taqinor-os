"""est_allege juge « allégé » le journal d'un run PR COMPLET, parce que GitHub y recopie le script de l'étape detect."""
SONDE = {"constat": "C-ADCG-038", "sha": "ce4e5fc4f",
         "attendu": "est_allege(journal d'un run complet, script recopié) == True"}

import importlib.util
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[4]
CI = RACINE / ".github/workflows/ci.yml"
REUSE = RACINE / "scripts/ci_merge_group_reuse.py"
HORO = "2026-11-10T02:37:40.9445364Z "


def sonde(ctx=None):
    spec = importlib.util.spec_from_file_location("ci_merge_group_reuse_sonde", REUSE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    wf = yaml.safe_load(CI.read_text(encoding="utf-8"))
    detect = next(s for s in wf["jobs"]["changes"]["steps"] if s.get("id") == "detect")
    lignes = detect["run"].splitlines()
    # Journal tel que GitHub l'écrit : en-tête « ##[group]Run <1re ligne> », puis chaque
    # ligne du script recopiée (couleurs déjà retirées par _journal), puis les sorties
    # d'un run NON allégé (branche hors claude/* : aucun « Run allege … » imprimé).
    journal = [HORO + "##[group]Run " + lignes[0]] + [HORO + l for l in lignes[1:]]
    journal += [HORO + "##[endgroup]",
                HORO + "Resolved -> backend=true frontend=true web=false yanbow=false "
                       "fastapi=false e2e(code)=true",
                HORO + "Paquets d'API modifiés (fuzz PR) : aucun"]
    texte = "\n".join(journal) + "\n"
    coupables = [l.strip() for l in texte.splitlines() if "allege=true" in l and "$" not in l]
    juge = mod.est_allege(texte)
    return {"repro": bool(juge),
            "observe": f"est_allege={juge} sur un run complet ; lignes recopiées retenues : "
                       f"{[c[len(HORO.strip()):].strip() for c in coupables]}"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
