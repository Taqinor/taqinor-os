"""Contre-visite AERR (VER1-161, lead, S2, appelant de la brique AERR71 ; défaut antérieur, déjà présent avant AERR117
qui a seulement remplacé le toast local par un console.warn) :
pages/crm/leads/LeadsPage.jsx::reassign avale le refus (`catch { console.warn(...) }`, sans relancer),
or pages/crm/leads/views/KanbanView.jsx::reassignAvecUndo le passe comme `apply` à lib/mutateWithUndo.js::mutateWithUndo,
qui ne sait qu'un échec QUE si `apply` rejette. Un refus serveur de réassignation sur le kanban affiche donc le toast
d'erreur global PUIS le toast de succès « Responsable modifié. » avec « Annuler » : l'écran dit les deux, la carte
garde l'ancien responsable. Le détecteur vérifie : (1) le catch de `reassign` ne relance pas (`throw`), (2) KanbanView
passe `onReassign` comme `apply` de mutateWithUndo, (3) LeadsPage transmet `reassign` comme `onReassign`."""
SONDE = {"constat": "C-AERR-VER1-161", "sha": "47f925be1",
         "attendu": "catch de reassign sans throw + apply: () => onReassign(...) dans mutateWithUndo + onReassign: reassign"}
import pathlib, re
RACINE = pathlib.Path(__file__).resolve().parents[4]
SRC = RACINE / "frontend/src"


def nettoyer(s):
    """Retire les commentaires // et /* */ ; les chaînes sont respectées."""
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


def sonde(ctx=None):
    page = lire("pages/crm/leads/LeadsPage.jsx")
    kanban = lire("pages/crm/leads/views/KanbanView.jsx")
    introuvable = [r for r, t in (("pages/crm/leads/LeadsPage.jsx", page),
                                  ("pages/crm/leads/views/KanbanView.jsx", kanban)) if t is None]
    if introuvable:
        return {"repro": False, "observe": {"introuvable": introuvable}, "methode": "lecture écran"}
    m = re.search(r"const\s+reassign\s*=\s*useCallback\(\s*async\s*\([^)]*\)\s*=>\s*\{", page)
    corps = apparier(page, m.end() - 1) if m else None
    catchs = [apparier(corps, x.end() - 1) or "" for x in re.finditer(r"catch\s*(?:\([^)]*\))?\s*\{", corps or "")]
    avale = bool(catchs) and all(not re.search(r"\bthrow\b", c) for c in catchs)
    apply_kanban = bool(re.search(r"mutateWithUndo\(\s*\{[^}]*apply\s*:\s*\(\)\s*=>\s*onReassign\(", kanban, re.S))
    transmis = bool(re.search(r"onReassign\s*:\s*reassign\b|onReassign=\{reassign\}", page))
    return {"repro": avale and apply_kanban and transmis,
            "observe": {"introuvable": [] if m else ["LeadsPage.jsx::reassign"], "catch_reassign": len(catchs),
                        "catch_sans_throw": avale, "kanban_apply_onReassign": apply_kanban,
                        "leadspage_transmet_reassign": transmis},
            "methode": "lecture écran"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
