"""Constat C-AERR-063 (sav, S1, C2) : pages/sav/TicketsPage.jsx::TicketDetail garde l'état du ticket A (`useState(ticket)`) quand la sélection passe
au ticket B, car `<TicketDetail ticket={detailTicket}` est rendu sans `key` : « Mettre à jour » écrit les champs de A sur B. Le détecteur cherche
l'état copié de la prop, l'absence d'effet de réinitialisation et un site de rendu sans `key`."""
SONDE = {"constat": "C-AERR-063", "sha": "3acfee471",
         "attendu": 'TicketDetail : useState(ticket) sans effet de réinitialisation ET <TicketDetail ticket={detailTicket} sans key='}
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


def appels(s, motif):
    """Arguments de chaque appel `motif(` (ex. `.catch`, `useEffect`) du texte."""
    return [apparier(s, m.end() - 1, "(", ")") or "" for m in re.finditer(motif + r"\s*\(", s or "")]


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


REL = "pages/sav/TicketsPage.jsx"


def sonde(ctx=None):
    s = lire(REL)
    c = corps(s, "TicketDetail") if s else None
    if c is None:
        return rendu(False, [REL + "::TicketDetail"])
    init = bool(re.search(r"useState\(\s*ticket\s*\)", c))
    reset = [e[:60] for e in appels(c, r"useEffect") if re.search(r"setCurrent\(\s*ticket\b|setFields\(", e)]
    sites = []
    for m in re.finditer(r"<TicketDetail\b", s):
        fin = s.find("/>", m.end())
        attrs = s[m.end():fin if fin > 0 else m.end() + 400]
        avant = s[max(0, m.start() - 120):m.start()]
        sites.append(bool(re.search(r"\bkey=", attrs) or re.search(r"key=\{[^}]*\}\s*>\s*$", avant)))
    sans_key = sites.count(False)
    clic = bool(re.search(r"onRowClick=\{[^}]*setSelected\(", s))
    return rendu(init and not reset and sans_key > 0, [], etat_copie_de_la_prop=init, effet_de_reinitialisation=reset,
                 sites_de_rendu=len(sites), sites_sans_key=sans_key, clic_ligne_change_la_selection=clic)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
