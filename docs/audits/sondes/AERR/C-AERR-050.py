"""Constat C-AERR-050 (lead, S2, C2 ; tâche AERR106, correctif a2c1fe22a7) : pages/visites/VisiteWizardPage.jsx::SlotTile
(`supprimer`). La croix de la vignette supprime définitivement la photo (`deleteVisitePhoto`). Le détecteur lit le CORRECTIF
dans le corps de `supprimer` : une confirmation attendue (`await confirm…(`, p. ex. `confirmDelete`) puis `if (!ok) return`
AVANT l'appel `deleteVisitePhoto(`. repro = suppression sans cette confirmation gardée. Réécrite le 20/11/2026 : l'ancienne règle lisait un motif périmé."""
SONDE = {"constat": "C-AERR-050", "sha": "3acfee471",
         "attendu": "supprimer (dans SlotTile) appelle deleteVisitePhoto( sans `await confirm…(` suivi de `if (!ok) return` avant l'appel"}
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


def sonde(ctx=None):
    t = lire("pages/visites/VisiteWizardPage.jsx")
    tuile = corps(t, "SlotTile") if t else None
    s = corps(tuile, "supprimer") if tuile else None
    if s is None:
        return rendu(False, ["pages/visites/VisiteWizardPage.jsx::SlotTile::supprimer"])
    i_del = s.find("deleteVisitePhoto(")
    if i_del < 0:
        return rendu(False, ["SlotTile::supprimer::deleteVisitePhoto("])
    avant = s[:i_del]
    m = re.search(r"(?:const|let)\s+(\w+)\s*=\s*await\s+confirm\w*\s*\(", avant)
    garde = bool(m and re.search(r"if\s*\(\s*!\s*" + re.escape(m.group(1)) + r"\s*\)\s*return\b", avant[m.end():]))
    garde = garde or bool(re.search(r"if\s*\(\s*!\s*\(?\s*await\s+confirm\w*\s*\(", avant))
    return rendu(not garde, [], confirmation_attendue=bool(m), suppression_gardee_par_la_confirmation=garde)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
