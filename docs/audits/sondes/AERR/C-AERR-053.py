"""Constat C-AERR-053 (lead, S2, C13 ; tâche AERR109, correctif f7b29a80c0) : pages/CalendarPage.jsx::load.
Une lecture ratée ne doit plus afficher « Aucun évènement ce mois-ci ». Le détecteur lit le CORRECTIF : le `.catch` de
`load` pose un drapeau d'échec (`setX(true)` / setter d'erreur), ne vide les évènements (`setEvents([])`) que sous une
condition de plage (`if (… !== plage)`), et l'état vide « Aucun évènement » est conditionné par `!<drapeau>`.
repro = vidage inconditionnel, pas de drapeau, ou état vide non gardé. Réécrite le 20/11/2026 : l'ancienne règle lisait un motif périmé."""
SONDE = {"constat": "C-AERR-053", "sha": "3acfee471",
         "attendu": "catch de load avec setEvents([]) inconditionnel, sans drapeau d'échec, ou « Aucun évènement » non gardé par ce drapeau"}
import os, pathlib, re
# AUDIT_RACINE (optionnel) : racine d'un autre arbre (témoin négatif sur l'arbre d'avant le correctif).
RACINE = pathlib.Path(os.environ.get("AUDIT_RACINE") or pathlib.Path(__file__).resolve().parents[4])
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


def inconditionnel(capt, i):
    """Vrai si l'appel en position i n'est pas sous un `if (… !== …)` (forme ligne ou bloc)."""
    debut = max(capt.rfind(x, 0, i) + len(x) for x in ("\n", ";", "{", "=>")) if capt[:i] else 0
    pre = capt[debut:i].strip()
    m = re.fullmatch(r"if\s*\((.*)\)", pre, re.S)
    if m:
        return "!==" not in m.group(1)
    if not pre and capt.rfind("{", 0, i) + 1 == debut:
        avant = capt[:debut - 1].rstrip()
        k = avant.rfind("if")
        if k >= 0 and re.fullmatch(r"if\s*\(.*!==.*\)", avant[k:], re.S):
            return False
    return True


def sonde(ctx=None):
    t = lire("pages/CalendarPage.jsx")
    b = corps(t, "load") if t else None
    if b is None:
        return rendu(False, ["pages/CalendarPage.jsx::load"])
    cs = catchs(b)
    vidages = [inconditionnel(c, m.start()) for c in cs for m in re.finditer(r"setEvents\(\s*\[\s*\]\s*\)", c)]
    setters = [m.group(1) for c in cs for m in re.finditer(r"\b(set\w+)\(\s*(?:true\b|['\"`])", c)
               if m.group(1) not in ("setEvents", "setLoading")]
    var = None
    for st in setters:
        mv = re.search(r"const\s*\[\s*(\w+)\s*,\s*" + re.escape(st) + r"\s*\]", t)
        if mv:
            var = mv.group(1); break
    pos = t.find("Aucun évènement ce mois-ci")
    vide_garde = False
    if pos >= 0 and var:
        tag = t.rfind("<", 0, pos)
        cond = t[t.rfind("{", 0, tag):tag]
        vide_garde = bool(re.search(r"!\s*" + re.escape(var) + r"\b", cond))
    repro = any(vidages) or not var or not vide_garde
    return rendu(repro, [], vidages_inconditionnels=sum(vidages), drapeau_d_echec=var,
                 etat_vide_garde_par_le_drapeau=vide_garde)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
