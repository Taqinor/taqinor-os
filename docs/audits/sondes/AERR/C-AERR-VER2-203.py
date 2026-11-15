"""Contre-visite AERR de clôture (VER2-203, SAV, S2, AERR25 partiel) : pages/sav/TicketsPage.jsx::TicketDetailCorps.
AERR25 remonte la fiche par `key={ticket.id}` et fait passer toute sélection par `selectionner`, gardée par
`confirmLeaveIfDirty(isAnyFormDirty())`. Mais le `dirty` enregistré par la fiche (`useDirtyGuard(dirty)`) ne compare que
les champs de `initialFields` : la note tapée (`noteBody`), le compte rendu d'une intervention à créer (`interv`), la
pièce à poser (`pieceForm`), le retrait traçable (`retirerForm`) et le motif d'annulation (`motif`) n'y entrent pas. Un
clic sur un autre ticket, J ou K remonte la fiche et perd ces saisies sans aucune demande, contre la clause « un
changement de sélection avec saisie modifiée demande d'abord » d'AERR25. Le détecteur vérifie : (1) les cinq états
déclarés dans TicketDetailCorps, (2) le corps du `useMemo` de `dirty` ne cite que `initialFields`/`fields`, (3) un seul
`useDirtyGuard` dans la fiche, (4) `selectionner` gardé par `isAnyFormDirty` (le registre que ces saisies ne nourrissent
pas)."""
SONDE = {"constat": "C-AERR-VER2-203", "sha": "d986bb9bc",
         "attendu": "noteBody, interv, pieceForm, retirerForm, motif déclarés mais absents du dirty + un seul useDirtyGuard + selectionner gardé par isAnyFormDirty"}
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


def corps_de(s, motif):
    m = re.search(motif, s)
    return (apparier(s, m.end() - 1) or "") if m else ""


BROUILLONS = ("noteBody", "interv", "pieceForm", "retirerForm", "motif")


def sonde(ctx=None):
    rel = "pages/sav/TicketsPage.jsx"
    s = lire(rel)
    if s is None:
        return {"repro": False, "observe": {"introuvable": [rel]}, "methode": "lecture écran"}
    m = re.search(r"function\s+TicketDetailCorps\s*\([^)]*\)\s*\{", s)
    corps = (apparier(s, m.end() - 1) or "") if m else ""
    declares = {b: bool(re.search(r"const\s+\[%s,\s*set\w+\]\s*=\s*useState\(" % b, corps)) for b in BROUILLONS}
    md = re.search(r"const\s+dirty\s*=\s*useMemo\(", corps)
    memo = (apparier(corps, md.end() - 1, "(", ")") or "") if md else ""
    dans_dirty = {b: bool(re.search(r"\b%s\b" % b, memo)) for b in BROUILLONS}
    gardes = len(re.findall(r"\buseDirtyGuard\(", corps))
    ms = re.search(r"const\s+selectionner\s*=\s*useCallback\(", s)
    sel = (apparier(s, ms.end() - 1, "(", ")") or "") if ms else ""
    sel_garde = bool(re.search(r"confirmLeaveIfDirty\(\s*isAnyFormDirty\(\)\s*\)", sel))
    repro = (bool(corps) and all(declares.values()) and bool(memo) and "initialFields" in memo
             and not any(dans_dirty.values()) and gardes == 1 and sel_garde)
    return {"repro": repro,
            "observe": {"TicketDetailCorps_trouve": bool(corps), "brouillons_declares": declares,
                        "brouillons_dans_dirty": dans_dirty, "useDirtyGuard_dans_la_fiche": gardes,
                        "selectionner_garde_par_isAnyFormDirty": sel_garde},
            "methode": "lecture écran"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
