#!/usr/bin/env python3
"""Garde des decisions fondateur lisibles par machine (AMET94, METHODE v3 §B.6).

Regle : une tache ne dit JAMAIS « Si (a) : ... ; si (b) : ... » sur une decision
deja repondue. `docs/audits/decisions.yml` est la source unique ; quand la
reponse arrive, `scripts/decisions.py appliquer` reecrit les dependants.

Trois controles, sortie en francais, code 1 au moindre echec :
  1. une tache OUVERTE (`[ ]`, GATED, BLOCKED) des `docs/plans/PLAN_AUDIT_*.md`
     portant `Si (a) :` / `Si (b) :` (toute cle) sur une decision REPONDUE echoue ;
     sur une decision encore `ouverte`, elle n'est que signalee, a condition
     d'etre GATED et de nommer son D-id ;
  2. chaque tag `(@decision: D-x=a)` reference une decision existante dont
     l'option `a` existe ET est la reponse retenue ;
  3. une tache GATED sur une decision (« [GATED: decision ... ] ») nomme un D-id
     (les autres portes GATED : code, autre tache, geste du fondateur, ne sont pas visees).

Une tache depend d'une decision si son id figure dans la liste `taches` de la
decision, ou si l'en-tete de la tache cite le D-id. Pur stdlib ; reutilise
`check_taches_cablage.lire_taches` et `plan_lanes._MiniYamlParser`.
"""
from __future__ import annotations

import re
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_taches_cablage as ctc  # noqa: E402
import plan_lanes  # noqa: E402

DECISIONS = "docs/audits/decisions.yml"
GLOB_PLANS = "PLAN_AUDIT_*.md"
OUVERTE = "ouverte"

CONDITIONNEL = re.compile(r"(?i)\bsi \(([a-d])\)\s*:")
TAG = re.compile(r"\(@decision:\s*([^)]*)\)")
D_ID = re.compile(r"\bD-[A-Z0-9]+(?:-[A-Za-z0-9]+)+")
GATED = re.compile(r"\*\*\s*\[GATED\b")
GATED_SUR_DECISION = re.compile(r"\*\*\s*\[GATED[^\]]*(?:d[ée]cision|r[ée]ponse)", re.I)
# Dette gelee (ne fait que retrecir) : taches GATED sur une decision SANS D-id, dans des
# fichiers de plan dont une autre lane est proprietaire (AMET94 ne les edite pas).
GATED_SANS_ID_TOLERES = frozenset({"AANA51", "ACRM56"})
CODE = re.compile(r"`[^`]*`")


def nettoyer(texte: str) -> str:
    """Retire les segments `code` : ils CITENT la syntaxe, ils ne l'emploient pas."""
    return CODE.sub("", texte)


@contextmanager
def _racine(racine: Path):
    ancien = ctc.ROOT
    ctc.ROOT = racine
    try:
        yield
    finally:
        ctc.ROOT = ancien


def charger_decisions(racine: Path = ROOT) -> dict:
    """{id: {options: {cle: texte}, reponse, taches, date}} depuis decisions.yml."""
    chemin = racine / DECISIONS
    donnees = plan_lanes._MiniYamlParser(chemin.read_text(encoding="utf-8")).parse()
    sortie = {}
    for brut in donnees.get("decisions") or []:
        options = {}
        for opt in brut.get("options") or []:
            if isinstance(opt, dict) and opt.get("cle") is not None:
                options[str(opt["cle"]).lower()] = opt.get("texte") or ""
        sortie[str(brut["id"])] = {
            "id": str(brut["id"]),
            "options": options,
            "reponse": str(brut.get("reponse", OUVERTE)).strip().lower(),
            "taches": [str(t) for t in (brut.get("taches") or [])],
            "date": str(brut.get("date", "")),
        }
    return sortie


def lire_taches_audit(racine: Path = ROOT) -> list:
    plans = sorted((racine / "docs" / "plans").glob(GLOB_PLANS))
    rel = [p.relative_to(racine).as_posix() for p in plans]
    with _racine(racine):
        return ctc.lire_taches(rel)


def est_ouverte(tache) -> bool:
    return not tache.etat.strip().lower().startswith("x")


def est_gated(tache) -> bool:
    return bool(GATED.search(tache.texte[:300])) or "GATED" in tache.etat.upper()


def ids_cites(tache) -> list:
    """D-id nommes dans l'en-tete de la tache (400 premiers caracteres)."""
    return D_ID.findall(nettoyer(tache.texte[:400]))


def decisions_de_tache(tache, decisions: dict) -> list:
    """Decisions dont depend la tache : liste `taches` du registre ou D-id cite."""
    trouvees = [d for d in decisions.values() if tache.identifiant in d["taches"]]
    for did in ids_cites(tache):
        if did in decisions and decisions[did] not in trouvees:
            trouvees.append(decisions[did])
    return trouvees


def est_repondue(decision: dict) -> bool:
    return decision["reponse"] != OUVERTE


def _controle_conditionnel(t, lieu, cles, decisions, echecs, avertissements):
    liees = decisions_de_tache(t, decisions)
    repondues = [d for d in liees if est_repondue(d)]
    if repondues:
        d = repondues[0]
        echecs.append(
            f"{t.identifiant} ({lieu}) : texte conditionnel « Si ({cles[0]}) » "
            f"sur la decision repondue {d['id']} = ({d['reponse']}) ; "
            f"lancer `python scripts/decisions.py appliquer`.")
    elif liees and est_gated(t) and ids_cites(t):
        avertissements.append(
            f"{t.identifiant} ({lieu}) : conditionnelle sur la decision "
            f"ouverte {liees[0]['id']} (GATED, tolere).")
    else:
        echecs.append(
            f"{t.identifiant} ({lieu}) : texte conditionnel « Si ({cles[0]}) » "
            f"sans decision connue de decisions.yml (une tache par option, "
            f"GATED + D-id tant que la decision est ouverte).")


def _controle_tag(t, lieu, paire, decisions, echecs):
    did, _, cle = paire.partition("=")
    did, cle = did.strip(), cle.strip().lower()
    d = decisions.get(did)
    if d is None:
        echecs.append(f"{t.identifiant} ({lieu}) : tag @decision orphelin, "
                      f"{did} absente de decisions.yml.")
    elif cle not in d["options"]:
        echecs.append(f"{t.identifiant} ({lieu}) : @decision {did}={cle}, option "
                      f"inexistante (options : {', '.join(sorted(d['options'])) or 'aucune'}).")
    elif d["reponse"] != cle:
        echecs.append(f"{t.identifiant} ({lieu}) : @decision {did}={cle} "
                      f"mais la reponse enregistree est ({d['reponse']}).")


def analyser(taches: list, decisions: dict) -> tuple:
    echecs, avertissements = [], []
    for t in taches:
        lieu = f"{t.fichier}:{t.ligne}"
        propre = nettoyer(t.texte)
        if est_ouverte(t):
            cles = sorted({m.group(1).lower() for m in CONDITIONNEL.finditer(propre)})
            if cles:
                _controle_conditionnel(t, lieu, cles, decisions, echecs, avertissements)
            if (GATED_SUR_DECISION.search(t.texte[:300]) and not ids_cites(t)
                    and t.identifiant not in GATED_SANS_ID_TOLERES):
                echecs.append(f"{t.identifiant} ({lieu}) : tache GATED sur une decision sans "
                              f"D-id nomme (attendu `D-XXX-n` dans l'en-tete).")
        for m in TAG.finditer(propre):
            for paire in [p.strip() for p in m.group(1).split(",") if p.strip()]:
                _controle_tag(t, lieu, paire, decisions, echecs)
    return echecs, avertissements


def verifier(racine: Path = ROOT) -> tuple:
    return analyser(lire_taches_audit(racine), charger_decisions(racine))


def main(argv=None) -> int:
    echecs, avertissements = verifier(ROOT)
    for a in avertissements:
        print(f"AVERTISSEMENT {a}")
    for e in echecs:
        print(f"ECHEC {e}")
    if echecs:
        print(f"\n{len(echecs)} echec(s) : decisions.yml et les taches se contredisent.")
        return 1
    print(f"OK : decisions coherentes avec les taches ({len(avertissements)} signalement(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
