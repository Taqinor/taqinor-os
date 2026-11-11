"""Constat C-AERR-066 (chantiers, S2, C2) : pages/interventions/InterventionsPage.jsx::KanbanView (`handleDragEnd`) appelle `onChangeStatus` (= `patchStatus`)
dès le dépôt, sans confirmation ni Annuler et sans contrainte de pas ; Terminée/Validée résout le ticket SAV lié. Le détecteur lit
handleDragEnd et patchStatus à la recherche d'une confirmation ou d'un Annuler."""
SONDE = {"constat": "C-AERR-066", "sha": "3acfee471",
         "attendu": 'handleDragEnd -> onChangeStatus( sans confirmation, patchStatus sans confirmation ni Annuler'}
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


REL = "pages/interventions/InterventionsPage.jsx"


def sonde(ctx=None):
    s = lire(REL)
    kb = corps(s, "KanbanView") if s else None
    h = corps(kb, "handleDragEnd") if kb else None
    p = corps(s, "patchStatus") if s else None
    if h is None or p is None:
        return rendu(False, [n for n, v in ((REL + "::KanbanView.handleDragEnd", h), (REL + "::patchStatus", p)) if v is None])
    a = re.search(r"onChangeStatus\??\.?\(", h)
    drag = bool(a) and not re.search(CONFIRME, h[:a.start()], re.I)
    patch = not re.search(CONFIRME, p, re.I)
    return rendu(drag and patch, [], depot_appelle_onChangeStatus_sans_confirmation=drag, patchStatus_sans_confirmation_ni_annuler=patch,
                 contrainte_de_pas_dans_handleDragEnd=bool(re.search(r"canMove|adjacent", h, re.I)))


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
