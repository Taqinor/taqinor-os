"""Constat C-AERR-050 (lead, S2, C2) : pages/visites/VisiteWizardPage.jsx::SlotTile (`supprimer`). La croix de 20 px sur le coin de la
vignette appelle `deleteVisitePhoto` (suppression définitive côté serveur) sans confirmation ni Annuler. Le détecteur cherche l'appel
dans `supprimer` sans confirmation dans son corps ni devant chacun de ses sites d'appel."""
SONDE = {"constat": "C-AERR-050", "sha": "3acfee471",
         "attendu": "supprimer (dans SlotTile) appelle deleteVisitePhoto( sans confirm( / ConfirmDialog / mutateWithUndo / undo, corps ou site d'appel"}
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

SUR = re.compile(r"\bconfirm\s*\(|useConfirmDialog|ConfirmDialog|setConfirm\w*\(|mutateWithUndo|\bundo\b", re.I)


def sonde(ctx=None):
    t = lire("pages/visites/VisiteWizardPage.jsx")
    tuile = corps(t, "SlotTile") if t else None
    s = corps(tuile, "supprimer") if tuile else None
    if s is None:
        return rendu(False, ["pages/visites/VisiteWizardPage.jsx::SlotTile::supprimer"])
    supprime = "deleteVisitePhoto(" in s
    sites = [bool(SUR.search(tuile[max(0, m.start() - 220):m.start()])) for m in re.finditer(r"(?<![\w.])supprimer\(", tuile)]
    sur_corps = bool(SUR.search(s))
    return rendu(supprime and not sur_corps and not (sites and all(sites)), [],
                 supprime_la_photo=supprime, confirmation_dans_le_corps=sur_corps,
                 sites_d_appel=len(sites), sites_d_appel_confirmes=sum(sites))

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
