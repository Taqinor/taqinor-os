"""Constat C-AERR-046 (lead, S2, C13) : features/crm/workspace/sections/CadenceFrise.jsx (effet de chargement) → IdentityRail.jsx. Un échec de
lecture des étapes pose `setLeadLu(leadId); setEtapes([])` et l'effet qui appelle `onEtapes(...)` (fenêtre Appel) publie alors `[]` =
« Aucune étape de suivi ouverte ». Le détecteur cherche ce `.catch` ET l'absence de toute lecture de `erreur` dans l'effet `onEtapes`."""
SONDE = {"constat": "C-AERR-046", "sha": "3acfee471",
         "attendu": "catch contenant setLeadLu(leadId) et setEtapes([]), et l'effet qui appelle onEtapes( ne regarde pas `erreur`"}
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
    t = lire("features/crm/workspace/sections/CadenceFrise.jsx")
    if t is None:
        return rendu(False, ["features/crm/workspace/sections/CadenceFrise.jsx"])
    vide = [c for c in catchs(t) if "setLeadLu(leadId)" in c and re.search(r"setEtapes\(\s*\[\s*\]\s*\)", c)]
    m = re.search(r"(?<![!\w.])onEtapes\(", t)
    if m is None:
        return rendu(False, ["appel onEtapes( dans CadenceFrise.jsx"])
    debut = t.rfind("useEffect(", 0, m.start())
    fin = t.find("useEffect(", m.end())
    effet = t[debut:fin if fin > 0 else len(t)]
    garde = bool(re.search(r"\berreur\b", effet))
    return rendu(vide and not garde, [], catch_qui_publie_une_liste_vide=len(vide),
                 effet_onEtapes_lit_erreur=garde)

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
