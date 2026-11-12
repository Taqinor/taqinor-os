"""Constat C-AERR-078 (chantiers, C13, S2) : features/installations/InterventionCapturePanels.jsx : SerialsPanel, MemosPanel, ReservesPanel et ToolReturnPanel
chargent avec `.catch(() => setRows([]))` : une lecture en échec rend « aucun n° de série / aucune réserve » sur la fiche terrain. Le
détecteur liste les panneaux dont un `.catch` vide les lignes sans poser d'état d'erreur."""
SONDE = {"constat": "C-AERR-078", "sha": "3acfee471",
         "attendu": ".catch(() => setRows([])) sans état d'erreur dans les 4 panneaux"}
import pathlib, re
RACINE = pathlib.Path(__file__).resolve().parents[4]
SRC = RACINE / "frontend/src"
CONFIRME = r"confirm|alertdialog|toastwithundo|undo|annuler|pending|dialog"


def nettoyer(s):
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
    """Corps `{...}` de `function nom` / `const nom = (...) =>`, ou, sans accolade, le texte jusqu'à la prochaine déclaration."""
    m = re.search(r"(?:function\s+|(?:const|let)\s+)" + re.escape(nom) + r"\b", s or "")
    if not m:
        return None
    for h in re.finditer(r"\{", s[m.end():]):
        p = m.end() + h.start()
        if s[:p].rstrip()[-1:] in ">)":
            return apparier(s, p)
    return None


def appels(s, motif):
    """Arguments de chaque appel `motif(` (ex. `.catch`, `useEffect`) du texte."""
    return [apparier(s, m.end() - 1, "(", ")") or "" for m in re.finditer(motif + r"\s*\(", s or "")]


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


REL = "features/installations/InterventionCapturePanels.jsx"
PANNEAUX = ("SerialsPanel", "MemosPanel", "ReservesPanel", "ToolReturnPanel")


def sonde(ctx=None):
    s = lire(REL)
    intr, rest = [], []
    for nom in PANNEAUX:
        c = corps(s, nom) if s else None
        if c is None:
            intr.append(REL + "::" + nom); continue
        for x in appels(c, r"\.catch"):
            if re.search(r"setRows\(\s*\[\s*\]\s*\)", x) and not re.search(r"set\w*(?:Err|Echec|Fail)\w*\(", x):
                rest.append(nom + " : lecture en échec rendue comme liste vide"); break
    return rendu(rest, intr, defaut_encore_present=rest, panneaux_controles=len(PANNEAUX) - len(intr))


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
