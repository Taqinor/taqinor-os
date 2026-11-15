"""Contre-visite AERR de clôture (VER2-204, chantiers + SAV, S2, AERR38 partiel et jumeau de la fiche ticket) :
le bouton « Fermer » contourne la garde de saisie que la boîte pose sur Échap et le clic extérieur.
`pages/installations/RecettePompageDialog.jsx::RecettePompageDialog` : `onOpenChange` passe par
`confirmLeaveIfDirty(dirty)` (AERR38), mais le pied de boîte rend `<Button … onClick={onClose}>Fermer</Button>` : un débit
mesuré saisi puis « Fermer » perd les mesures sans demande. `pages/sav/TicketsPage.jsx::TicketDetailCorps` : le tiroir
mobile et Échap passent par `confirmLeaveIfDirty`, le « Fermer » du panneau appelle `onClose` directement : une fiche
modifiée se ferme sans demande. Le détecteur vérifie, pour chaque fichier : (1) une garde `confirmLeaveIfDirty(dirty)` sur
la fermeture de la boîte, (2) un bouton « Fermer » dont le `onClick` est `onClose` nu."""
SONDE = {"constat": "C-AERR-VER2-204", "sha": "d986bb9bc",
         "attendu": "garde sur onOpenChange + bouton Fermer à onClick={onClose} nu dans RecettePompageDialog et TicketsPage"}
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


FICHIERS = ("pages/installations/RecettePompageDialog.jsx", "pages/sav/TicketsPage.jsx")


def sonde(ctx=None):
    obs, introuvable, tous = {}, [], True
    for rel in FICHIERS:
        s = lire(rel)
        if s is None:
            introuvable.append(rel)
            continue
        garde = bool(re.search(r"onOpenChange=\{\(o\)\s*=>\s*\{\s*if\s*\(!o\s*&&\s*confirmLeaveIfDirty\(dirty\)\)\s*onClose\(\)", s))
        fermer_nu = len(re.findall(r"onClick=\{onClose\}\s*>\s*Fermer\s*<", s))
        obs[rel] = {"garde_sur_la_fermeture_de_la_boite": garde, "boutons_Fermer_onClose_nu": fermer_nu}
        tous = tous and garde and fermer_nu >= 1
    if introuvable:
        return {"repro": False, "observe": {"introuvable": introuvable}, "methode": "lecture écran"}
    return {"repro": tous, "observe": obs, "methode": "lecture écran"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
