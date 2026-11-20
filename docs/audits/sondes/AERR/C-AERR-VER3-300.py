"""Contre-visite AERR des correctifs (VER3-300, S2, jumeaux oubliés d'AERR160) : un bouton « Fermer » qui appelle
`onClose` nu dans un composant qui enregistre `useDirtyGuard(...)` et garde la fermeture de sa boîte / son tiroir par
`confirmLeaveIfDirty(...)`. AERR160 a corrigé la recette de pompage et la fiche ticket ; sa clause Jumeaux (« ces 2 sites
dans des boîtes gardées ») a manqué les autres. Le détecteur parcourt tous les .jsx de `frontend/src` (hors tests),
découpe chaque composant `function Nom(...) { ... }` de premier niveau et retient ceux dont le corps contient À LA FOIS
`useDirtyGuard(`, `confirmLeaveIfDirty(` et `onClick={onClose}>Fermer<` (Échap / clic extérieur demandent, « Fermer »
perd la saisie sans demande)."""
SONDE = {"constat": "C-AERR-VER3-300", "sha": "c5aa18788f",
         "attendu": "au moins un composant gardé (useDirtyGuard + confirmLeaveIfDirty) avec un « Fermer » à onClick={onClose} nu"}
import pathlib, re
RACINE = pathlib.Path(__file__).resolve().parents[4]
SRC = RACINE / "frontend/src"


def nettoyer(s):
    """Retire les commentaires // et /* */ ; les chaînes sont respectées."""
    out, i, n, q = [], 0, len(s), None
    while i < n:
        c = s[i]
        if q:
            out.append(c)
            if c == "\\" and i + 1 < n:
                i += 1; out.append(s[i])
            elif c == q or (c == "\n" and q != "`"):
                q = None
        elif c in "'\"`":
            q = c; out.append(c)
        elif s.startswith("//", i):
            while i < n and s[i] != "\n":
                i += 1
            continue
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2); i = n if j < 0 else j + 2; out.append(" "); continue
        else:
            out.append(c)
        i += 1
    return "".join(out)


def fin_appariee(s, i, o, f):
    """Index de la fermeture qui apparie s[i] (== o), chaînes respectées ; -1 sinon."""
    d, q, j = 0, None, i
    while j < len(s):
        c = s[j]
        if q:
            if c == "\\":
                j += 1
            elif c == q or (c == "\n" and q != "`"):
                q = None
        elif c in "'\"`":
            q = c
        elif c == o:
            d += 1
        elif c == f:
            d -= 1
            if d == 0:
                return j
        j += 1
    return -1


def composants(s):
    for m in re.finditer(r"^(?:export\s+)?(?:default\s+)?function\s+([A-Z]\w*)\s*\(", s, re.M):
        fp = fin_appariee(s, m.end() - 1, "(", ")")
        if fp < 0:
            continue
        ob = s.find("{", fp)
        fb = fin_appariee(s, ob, "{", "}") if ob >= 0 else -1
        if fb > 0:
            yield m.group(1), s[ob:fb]


FERMER_NU = re.compile(r"onClick=\{onClose\}\s*>\s*Fermer\s*<")


def sonde(ctx=None):
    trouves = []
    for p in sorted(SRC.rglob("*.jsx")):
        if ".test." in p.name:
            continue
        s = nettoyer(p.read_text(encoding="utf-8"))
        if "useDirtyGuard(" not in s or "Fermer" not in s:
            continue
        for nom, corps in composants(s):
            if "useDirtyGuard(" in corps and "confirmLeaveIfDirty(" in corps and FERMER_NU.search(corps):
                trouves.append(f"{p.relative_to(SRC).as_posix()}::{nom}")
    return {"repro": bool(trouves), "observe": {"composants_gardes_avec_Fermer_nu": trouves},
            "methode": "lecture écran"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
