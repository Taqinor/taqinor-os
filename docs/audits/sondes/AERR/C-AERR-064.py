"""Constat C-AERR-064 (sav, S2, C2) : pages/sav/TicketsPage.jsx::TicketsPage, gestionnaire clavier `onKey` : Échap ferme la fiche (fermerDetail) et
J/K changent le ticket visé sans garde de boîte ouverte ni de saisie modifiée. Le détecteur isole le bloc `onKey` et cherche une garde
(dialogueParDessus, confirmLeaveIfDirty, defaultPrevented, [role=…], aria-modal)."""
SONDE = {"constat": "C-AERR-064", "sha": "3acfee471",
         "attendu": "bloc onKey contenant 'Escape' et fermerDetail()/closeDetail() sans dialogueParDessus/confirmLeaveIfDirty/defaultPrevented"}
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


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


REL = "pages/sav/TicketsPage.jsx"
GARDE = r"dialogueParDessus|confirmLeaveIfDirty|defaultPrevented|\[role=|aria-modal"


def sonde(ctx=None):
    s = lire(REL)
    m = re.search(r"const onKey\s*=\s*\(?\s*e\s*\)?\s*=>\s*\{", s or "")
    if not m:
        return rendu(False, [REL + "::onKey"])
    b = apparier(s, m.end() - 1)
    ferme = "'Escape'" in b and bool(re.search(r"fermerDetail\(|closeDetail\(", b))
    garde = re.findall(GARDE, b)
    jk = bool(re.search(r"deplacerSelection\(", b))
    return rendu(ferme and not garde, [], echap_ferme_la_fiche=ferme, gardes_trouvees=garde, jk_change_la_selection=jk)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
