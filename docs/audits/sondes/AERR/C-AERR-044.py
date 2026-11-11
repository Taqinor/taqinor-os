"""Constat C-AERR-044 (lead, S2, C13) : pages/crm/leads/LeadsPage.jsx::LeadsPage. `if (error) return <StateBlock>` sans garde sur
la liste déjà chargée (la liste ET la fiche ouverte sont démontées, aucun Réessayer) ; `onSaved = () => refetch()` relit toute la liste à
chaque autosauvegarde. Le détecteur lit le corps de LeadsPage : retour anticipé sur `error` seul, et `onSaved` qui ne fait que refetch."""
SONDE = {"constat": "C-AERR-044", "sha": "3acfee471",
         "attendu": 'retour anticipé `if (error) return <StateBlock …>` sans condition sur la liste, OU `const onSaved = () => refetch()`'}
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
    t = lire("pages/crm/leads/LeadsPage.jsx")
    b = corps(t, "LeadsPage") if t else None
    if b is None:
        return rendu(False, ["pages/crm/leads/LeadsPage.jsx::LeadsPage"])
    remplace = re.search(r"if\s*\(\s*error\s*\)\s*(?:\{\s*)?return\s*\(?\s*<StateBlock", b)
    onsaved = re.search(r"\bonSaved\s*=\s*\(\s*\)\s*=>\s*refetch\s*\(\s*\)", b)
    return rendu(remplace or onsaved, [],
                 erreur_remplace_liste_et_fiche_sans_garde_leads=bool(remplace),
                 onSaved_relit_toute_la_liste=bool(onsaved),
                 onRetry_dans_StateBlock="onRetry" in (b[remplace.start():remplace.start() + 300] if remplace else ""))

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
