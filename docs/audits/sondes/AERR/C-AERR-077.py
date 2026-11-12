"""Constat C-AERR-077 (chantiers, C2, S2) : features/installations/InterventionCapturePanels.jsx::ConsommationPanel, `valider` : le bouton « Valider la consommation »
appelle validerConsommation(id) en un clic (sorties de stock, consommation verrouillée, aucune route de dé-validation). Le détecteur cherche
le bouton relié directement à `valider` et une confirmation dans `valider`."""
SONDE = {"constat": "C-AERR-077", "sha": "3acfee471",
         "attendu": 'onClick={valider} et validerConsommation( dans valider sans confirmation'}
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


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


REL = "features/installations/InterventionCapturePanels.jsx"


def sonde(ctx=None):
    s = lire(REL)
    c = corps(s, "ConsommationPanel") if s else None
    v = corps(c, "valider") if c else None
    if v is None:
        return rendu(False, [REL + "::ConsommationPanel.valider"])
    direct = bool(re.search(r"onClick=\{\s*(?:valider|\(\)\s*=>\s*valider\(\))\s*\}", c))
    appelle = "validerConsommation(" in v
    conf = re.findall(CONFIRME, v, re.I)
    return rendu(direct and appelle and not conf, [], bouton_relie_directement_a_valider=direct,
                 valider_appelle_validerConsommation=appelle, confirmation_dans_valider=conf)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
