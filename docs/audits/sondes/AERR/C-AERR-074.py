"""Constat C-AERR-074 (stock, C2, S2) : pages/stock/ReceptionsFournisseur.jsx::NouvelleReception et pages/stock/BonsCommandeFournisseur.jsx (BcfDetail,
AchatsHorsContratModal) : `<Dialog open onOpenChange={(o) => { if (!o) onClose() }}>` ferme au clic extérieur et à Échap sans garde de saisie.
Le détecteur parcourt les 3 dialogues et liste ceux sans confirmLeaveIfDirty / onInteractOutside / onEscapeKeyDown / garde dans le gestionnaire."""
SONDE = {"constat": "C-AERR-074", "sha": "3acfee471",
         "attendu": 'onOpenChange qui appelle onClose() sans confirmLeaveIfDirty ni garde (3 dialogues)'}
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


CIBLES = (("pages/stock/ReceptionsFournisseur.jsx", "NouvelleReception"),
          ("pages/stock/BonsCommandeFournisseur.jsx", "BcfDetail"),
          ("pages/stock/BonsCommandeFournisseur.jsx", "AchatsHorsContratModal"))
GLOBAL = r"confirmLeaveIfDirty|onInteractOutside|onEscapeKeyDown|onPointerDownOutside"


def sonde(ctx=None):
    intr, rest = [], []
    for rel, nom in CIBLES:
        c = corps(lire(rel), nom)
        if c is None:
            intr.append(rel + "::" + nom); continue
        gestionnaires = [apparier(c, m.end() - 1) or "" for m in re.finditer(r"onOpenChange=\{", c)]
        ferme = [h for h in gestionnaires if re.search(r"onClose\(", h)]
        if not ferme:
            intr.append(rel + "::" + nom + " (onOpenChange->onClose)"); continue
        if not re.search(GLOBAL, c) and not any(re.search(r"dirty|confirm", h, re.I) for h in ferme):
            rest.append(rel.split("/")[-1] + "::" + nom)
    return rendu(rest, intr, dialogues_sans_garde=rest, dialogues_controles=len(CIBLES) - len(intr))


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
