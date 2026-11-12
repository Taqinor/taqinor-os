"""Constat C-AERR-065 (chantiers, S1, C2) : pages/installations/views/KanbanView.jsx::handleDragEnd appelle `onChangeStatus(` dès le dépôt, sans
confirmation ni Annuler ; canMoveStatus (features/installations/statuses.js) autorise un pas, donc « Installé », « Réceptionné » et « Clôturé »
sont atteignables d'un seul dépôt. Le détecteur lit le corps de handleDragEnd, le gestionnaire du parent et la règle de pas."""
SONDE = {"constat": "C-AERR-065", "sha": "3acfee471",
         "attendu": "handleDragEnd appelle onChangeStatus( sans confirmation avant l'appel, le parent aussi, et cloture/receptionne atteignables en un dépôt"}
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


def jusqua(s, nom, fin):
    """Texte de `const nom` jusqu'à la première occurrence de la regex `fin` (déclaration suivante)."""
    m = re.search(r"(?:function\s+|(?:const|let)\s+)" + re.escape(nom) + r"\b", s or "")
    if not m:
        return None
    e = re.search(fin, s[m.end():])
    return s[m.start():m.end() + e.start()] if e else s[m.start():]


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


def sonde(ctx=None):
    k = lire("pages/installations/views/KanbanView.jsx")
    ip = lire("pages/installations/InstallationsPage.jsx")
    st = lire("features/installations/statuses.js")
    h = corps(k, "handleDragEnd") if k else None
    p = jusqua(ip, "onChangeStatus", r"\n  const ") if ip else None
    f = corps(st, "canMoveStatus") if st else None
    if h is None or p is None or f is None:
        return rendu(False, [n for n, v in (("KanbanView::handleDragEnd", h), ("InstallationsPage::onChangeStatus", p),
                                            ("statuses.js::canMoveStatus", f)) if v is None])
    a = re.search(r"onChangeStatus\??\.?\(", h)
    kanban = bool(a) and not re.search(CONFIRME, h[:a.start()], re.I)
    parent = not re.search(CONFIRME, p, re.I)
    ordre = re.findall(r"'(\w+)'", (re.search(r"INSTALLATION_STATUSES\s*=\s*\[(.*?)\]", st, re.S) or [0, ""])[1])
    pas = bool(re.search(r"Math\.abs\(a - b\)\s*<=\s*1", f))
    atteignables = [x for x in ("installe", "receptionne", "cloture") if x in ordre and pas and ordre.index(x) > 0]
    return rendu(kanban and parent and {"receptionne", "cloture"} <= set(atteignables), [],
                 depot_appelle_onChangeStatus_sans_confirmation=kanban, parent_sans_confirmation=parent,
                 statuts_atteignables_d_un_depot=atteignables)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
