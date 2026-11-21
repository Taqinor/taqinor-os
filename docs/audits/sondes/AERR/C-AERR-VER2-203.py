"""Contre-visite AERR de clôture (VER2-203, SAV, S2 ; tâches AERR159 puis AERR184 ; correctifs e53e778f21, 13047c82d1) :
pages/sav/TicketsPage.jsx::TicketDetailCorps. Les brouillons de la fiche (note `noteBody`, compte rendu `interv`, pièce
`pieceForm`, retrait `retirerForm`, motif `motif`) doivent nourrir la garde de sortie. Le détecteur lit le CORRECTIF :
l'argument de `useDirtyGuard(…)` ET celui de la confirmation du `onOpenChange` du `<Sheet>` (un nom comme
`brouillonEnCours` est résolu par sa déclaration `const`) citent les cinq brouillons. repro = l'une des deux gardes en omet
un. Réécrite le 20/11/2026 : l'ancienne règle lisait un motif périmé."""
SONDE = {"constat": "C-AERR-VER2-203", "sha": "d986bb9bc",
         "attendu": "useDirtyGuard(…) ou la garde du onOpenChange du <Sheet> n'inclut pas noteBody, interv, pieceForm, retirerForm et motif"}
import os, pathlib, re
# AUDIT_RACINE (optionnel) : racine d'un autre arbre (témoin négatif sur l'arbre d'avant le correctif).
RACINE = pathlib.Path(os.environ.get("AUDIT_RACINE") or pathlib.Path(__file__).resolve().parents[4])
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


def corps_de(s, motif):
    m = re.search(motif, s)
    return (apparier(s, m.end() - 1) or "") if m else ""


BROUILLONS = ("noteBody", "interv", "pieceForm", "retirerForm", "motif")


def resoudre(corps, expr):
    """Un identifiant seul est remplacé par l'expression de sa déclaration `const nom = …` (jusqu'à la fin de ligne)."""
    expr = (expr or "").strip()
    if re.fullmatch(r"\w+", expr):
        m = re.search(r"const\s+" + expr + r"\s*=\s*([^\n]*)", corps)
        if m:
            return m.group(1)
    return expr


def cites(expr):
    return {b: bool(re.search(r"\b%s\b" % b, expr)) for b in BROUILLONS}


def sonde(ctx=None):
    rel = "pages/sav/TicketsPage.jsx"
    s = lire(rel)
    if s is None:
        return {"repro": False, "observe": {"introuvable": [rel]}, "methode": "lecture écran"}
    m = re.search(r"function\s+TicketDetailCorps\s*\([^)]*\)\s*\{", s)
    corps = (apparier(s, m.end() - 1) or "") if m else ""
    if not corps:
        return {"repro": False, "observe": {"introuvable": [rel + "::TicketDetailCorps"]}, "methode": "lecture écran"}
    mg = re.search(r"\buseDirtyGuard\(", corps)
    garde = resoudre(corps, apparier(corps, mg.end() - 1, "(", ")")) if mg else ""
    sheet = ""
    msh = re.search(r"<Sheet\b", corps)
    if msh:
        mo = re.search(r"onOpenChange=\{", corps[msh.end():msh.end() + 300])
        if mo:
            h = apparier(corps, msh.end() + mo.end() - 1) or ""
            mc = re.search(r"\bconfirm\w*\(", h)
            sheet = resoudre(corps, apparier(h, mc.end() - 1, "(", ")")) if mc else ""
    dg, ds = cites(garde), cites(sheet)
    repro = not all(dg.values()) or not all(ds.values())
    return {"repro": repro,
            "observe": {"brouillons_dans_useDirtyGuard": dg, "brouillons_dans_la_garde_du_Sheet": ds,
                        "Sheet_trouve": bool(msh)},
            "methode": "lecture écran"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
