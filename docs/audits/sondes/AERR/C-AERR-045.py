"""Constat C-AERR-045 (lead, S2, C13) : pages/crm/RelancesDuJourWidget.jsx (charger + rendu) et pages/crm/ControleSuiviPanel.jsx (effet de
chargement). Widget : `.catch(() => setError(true))`, `error` jamais remis à faux, rendu `error ? « Indisponible »` à la place de la file.
Panneau : le `.catch` pose `donnees: null` (les données affichées sont jetées). Le détecteur liste ceux des deux où le motif subsiste."""
SONDE = {"constat": "C-AERR-045", "sha": "3acfee471",
         "attendu": 'Widget : setError(true) sans jamais setError(false) ET `error ? (` à la place de la file ; Panneau : catch avec donnees: null'}
import pathlib, re
RACINE = pathlib.Path(__file__).resolve().parents[4]
SRC = RACINE / "frontend/src"


def nettoyer(s):
    """Retire les commentaires // et /* */ ; les chaînes sont respectées (' et " s'arrêtent en fin de ligne)."""
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


def lire(rel):
    p = SRC / rel
    return nettoyer(p.read_text(encoding="utf-8")) if p.is_file() else None


def apparier(s, i, o="{", f="}"):
    """Texte entre le délimiteur ouvrant en position i et son fermant apparié (chaînes ignorées)."""
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
                return s[i + 1:j]
        j += 1
    return None


def corps(s, nom):
    """Corps `{...}` de `function nom` / `const nom = (...) =>` (premier `{` précédé de `>` ou `)`)."""
    m = re.search(r"(?:function\s+|(?:const|let)\s+)" + re.escape(nom) + r"\b", s or "")
    if not m:
        return None
    for h in re.finditer(r"\{", s[m.end():]):
        p = m.end() + h.start()
        if s[:p].rstrip()[-1:] in ">)":
            return apparier(s, p)
    return None


def catchs(s):
    """Arguments de chaque `.catch(...)` du texte."""
    return [apparier(s, m.end() - 1, "(", ")") or "" for m in re.finditer(r"\.catch\s*\(", s or "")]


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}

def sonde(ctx=None):
    manque, restants = [], []
    w = lire("pages/crm/RelancesDuJourWidget.jsx")
    if w is None:
        manque.append("pages/crm/RelancesDuJourWidget.jsx")
    else:
        colle = re.search(r"setError\(\s*true\s*\)", w) and not re.search(r"setError\(\s*(?:false|null)\s*\)", w)
        remplace = re.search(r"\)\s*:\s*error\s*\?\s*\(", w)
        if colle and remplace:
            restants.append("RelancesDuJourWidget.jsx::charger (erreur collante qui remplace la file)")
    p = lire("pages/crm/ControleSuiviPanel.jsx")
    if p is None:
        manque.append("pages/crm/ControleSuiviPanel.jsx")
    else:
        jette = [c for c in catchs(p) if "setResultat(" in c and re.search(r"donnees\s*:\s*null", c)]
        if jette:
            restants.append("ControleSuiviPanel.jsx (catch du chargement : donnees: null)")
    return rendu(restants, manque, emplacements_ou_le_motif_subsiste=restants)

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
