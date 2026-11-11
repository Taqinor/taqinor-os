"""Constat C-AERR-075 (chantiers, C2, S2) : pages/installations/RecettePompageDialog.jsx : même motif que C-AERR-074, la recette de pompage (mesures) se ferme
au clic extérieur et à Échap (`onOpenChange={(o) => { if (!o) onClose() }}`) sans garde de saisie. Le détecteur cherche onClose() dans
onOpenChange sans confirmLeaveIfDirty / onInteractOutside / onEscapeKeyDown / garde dans le gestionnaire."""
SONDE = {"constat": "C-AERR-075", "sha": "3acfee471",
         "attendu": 'onOpenChange qui appelle onClose() sans confirmLeaveIfDirty ni garde'}
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


REL = "pages/installations/RecettePompageDialog.jsx"
GLOBAL = r"confirmLeaveIfDirty|onInteractOutside|onEscapeKeyDown|onPointerDownOutside"


def sonde(ctx=None):
    c = corps(lire(REL), "RecettePompageDialog")
    if c is None:
        return rendu(False, [REL + "::RecettePompageDialog"])
    gestionnaires = [apparier(c, m.end() - 1) or "" for m in re.finditer(r"onOpenChange=\{", c)]
    ferme = [h.strip() for h in gestionnaires if re.search(r"onClose\(", h)]
    if not ferme:
        return rendu(False, [REL + "::onOpenChange->onClose"])
    global_ = re.findall(GLOBAL, c)
    garde = bool(global_) or any(re.search(r"dirty|confirm", h, re.I) for h in ferme)
    return rendu(not garde, [], gestionnaires=ferme, gardes_trouvees=global_)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
