"""Contre-visite AERR des correctifs (VER3-301, SAV, S2, jumeau oublié d'AERR159) :
`pages/sav/TicketsPage.jsx::TicketDetailCorps`. AERR159 a fait entrer la note, le compte rendu, la pièce, le retrait et
le motif dans la garde ENREGISTRÉE (`useDirtyGuard(dirty || !!(noteBody… || motif))`), lue par `isAnyFormDirty()` (clic
d'un autre ticket, J/K, « Fermer »). Mais le tiroir `<Sheet>` affiché sous 1 280 px ferme par
`onOpenChange={(o) => { if (!o) confirmLeaveIfDirty(dirty)… onClose() }}` : il lit `dirty` (les seuls `initialFields`),
pas les brouillons. Sur tablette/mobile, une note tapée puis Échap, la croix du tiroir ou un clic sur le voile ferme la
fiche et perd la note sans demande. Le détecteur vérifie : (1) l'argument de `useDirtyGuard` cite `noteBody`, (2) le
`useMemo` de `dirty` ne cite pas `noteBody`, (3) le `onOpenChange` du `<Sheet` passe `confirmLeaveIfDirty(dirty)` et non
`isAnyFormDirty()` ni un booléen qui inclut les brouillons."""
SONDE = {"constat": "C-AERR-VER3-301", "sha": "c5aa18788f",
         "attendu": "useDirtyGuard cite noteBody ; dirty ne le cite pas ; le Sheet ferme par confirmLeaveIfDirty(dirty)"}
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


def fin_appariee(s, i, o, f):
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
                return j
        j += 1
    return -1


def corps_composant(s, nom):
    m = re.search(r"^function\s+" + nom + r"\s*\(", s, re.M)
    if not m:
        return None
    fp = fin_appariee(s, m.end() - 1, "(", ")")
    ob = s.find("{", fp)
    fb = fin_appariee(s, ob, "{", "}")
    return s[ob:fb] if fb > 0 else None


def sonde(ctx=None):
    p = SRC / "pages/sav/TicketsPage.jsx"
    if not p.is_file():
        return {"repro": False, "observe": {"introuvable": str(p)}, "methode": "lecture écran"}
    corps = corps_composant(nettoyer(p.read_text(encoding="utf-8")), "TicketDetailCorps")
    if corps is None:
        return {"repro": False, "observe": {"TicketDetailCorps_trouve": False}, "methode": "lecture écran"}
    g = re.search(r"useDirtyGuard\(", corps)
    arg_garde = corps[g.end() - 1:fin_appariee(corps, g.end() - 1, "(", ")") + 1] if g else ""
    md = re.search(r"const\s+dirty\s*=\s*useMemo\(", corps)
    corps_dirty = corps[md.end() - 1:fin_appariee(corps, md.end() - 1, "(", ")") + 1] if md else ""
    sheet = re.search(r"<Sheet\b[^>]*onOpenChange=\{(.*?)\}\s*>", corps, re.S)
    garde_sheet = sheet.group(1) if sheet else ""
    obs = {
        "useDirtyGuard_cite_noteBody": "noteBody" in arg_garde,
        "dirty_cite_noteBody": "noteBody" in corps_dirty,
        "Sheet_trouve": bool(sheet),
        "Sheet_ferme_par_confirmLeaveIfDirty_dirty": bool(re.search(r"confirmLeaveIfDirty\(\s*dirty\s*\)", garde_sheet)),
        "Sheet_lit_isAnyFormDirty": "isAnyFormDirty" in garde_sheet,
    }
    repro = (obs["useDirtyGuard_cite_noteBody"] and not obs["dirty_cite_noteBody"]
             and obs["Sheet_ferme_par_confirmLeaveIfDirty_dirty"] and not obs["Sheet_lit_isAnyFormDirty"])
    return {"repro": repro, "observe": obs, "methode": "lecture écran"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
