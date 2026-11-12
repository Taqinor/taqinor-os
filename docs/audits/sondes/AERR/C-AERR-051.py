"""Constat C-AERR-051 (lead, S2, C13) : pages/visites/VisiteWizardPage.jsx::VisiteWizardPage (`recharger` + rendu). Une relecture en échec
(après photo, mesure, « Terminer » raté) pose l'erreur collante « Visite introuvable ou inaccessible » ; le rendu `if (erreur || !visite)
return` démonte alors tout l'écran (mesures non enregistrées perdues). Le détecteur cherche le catch inconditionnel ET ce retour anticipé."""
SONDE = {"constat": "C-AERR-051", "sha": "3acfee471",
         "attendu": 'recharger : .catch(() => setErreur(...)) sans condition sur une visite déjà chargée ; rendu `if (erreur || !visite) return`'}
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
    t = lire("pages/visites/VisiteWizardPage.jsx")
    page = corps(t, "VisiteWizardPage") if t else None
    r = corps(page, "recharger") if page else None
    if r is None:
        return rendu(False, ["pages/visites/VisiteWizardPage.jsx::recharger"])
    direct = [c for c in catchs(r) if "setErreur(" in c and not re.search(r"\bif\b|\bvisite\b|\bprev\b|\?", c)]
    remplace = re.search(r"if\s*\(\s*erreur\s*\|\|[^\n]*\)\s*return", page)
    return rendu(direct and remplace, [], catch_pose_erreur_sans_condition=len(direct),
                 retour_anticipe_sur_erreur_demonte_l_ecran=bool(remplace),
                 erreur_remise_a_zero=bool(re.search(r"setErreur\(\s*(?:null|''|\"\"|false)\s*\)", page)))

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
