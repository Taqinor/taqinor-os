"""Contre-visite AERR (VER4-400, jumeaux de VER3-300 / VER3-301, élargie à TOUTES les sorties) : dans chaque composant
.jsx de `frontend/src` (hors tests) qui enregistre une garde de saisie (`useDirtyGuard(<A>)`, ou `useFormSafety(...)` qui
l'enregistre), toute sortie volontaire doit passer par `confirmLeaveIfDirty(<A>)` (ou `isAnyFormDirty()`, ou
`guardedClose`). Le détecteur relève, composant par composant :
  (1) `nue` : un `onClick` / `onCancel` lié directement à `onClose` (`={onClose}`, `={() => onClose()}`,
      `={() => onClose?.()}`) — le bouton « Fermer » / « Annuler » / « Retour » ferme sans demande (VER3-300 ne cherchait
      que « Fermer » écrit juste après `onClick={onClose}>`) ;
  (2) `onOpenChange_nu` : un `onOpenChange` qui appelle `onClose` sans `confirmLeaveIfDirty` ni `guardedClose`
      (Échap, croix, voile) ;
  (3) `booleen_different` : un `confirmLeaveIfDirty(<X>)` dont `<X>` n'est ni `<A>` ni `isAnyFormDirty()` (VER3-301 :
      le tiroir lisait `dirty` quand la garde comptait aussi les brouillons) — à juger : un calcul frais plus large est
      juste, un sous-ensemble de `<A>` ne l'est pas.
Témoins : les sept sites corrigés par AERR160 et AERR181 à AERR184 ne doivent sortir dans aucune des trois listes."""
SONDE = {"constat": "C-AERR-VER4-400", "sha": "5a77c93d99",
         "attendu": "aucun composant gardé avec une sortie nue ; booleen_different seulement là où le calcul est frais et plus large"}
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
            j = s.find("*/", i + 2); k = n if j < 0 else j + 2
            out.append(" " + "\n" * s.count("\n", i, k)); i = k; continue  # garde les numéros de ligne
        else:
            out.append(c)
        i += 1
    return "".join(out)


def fin_appariee(s, i, o, f):
    """Index de la fermeture qui apparie s[i] (== o), chaînes respectées ; -1 sinon."""
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


def composants(s):
    for m in re.finditer(r"^(?:export\s+)?(?:default\s+)?function\s+([A-Z]\w*)\s*\(", s, re.M):
        fp = fin_appariee(s, m.end() - 1, "(", ")")
        if fp < 0:
            continue
        ob = s.find("{", fp)
        fb = fin_appariee(s, ob, "{", "}") if ob >= 0 else -1
        if fb > 0:
            yield m.group(1), s[ob:fb]


def norm(x):
    return re.sub(r"\s+", "", x or "")


def arguments(corps, nom):
    """Premier argument de chaque appel `nom(` dans le corps."""
    for m in re.finditer(re.escape(nom) + r"\(", corps):
        fp = fin_appariee(corps, m.end() - 1, "(", ")")
        if fp < 0:
            continue
        brut = corps[m.end():fp]
        d, k = 0, 0
        for k, c in enumerate(brut):  # coupe au premier « , » de niveau 0
            if c in "([{":
                d += 1
            elif c in ")]}":
                d -= 1
            elif c == "," and d == 0:
                brut = brut[:k]
                break
        yield m.start(), brut.strip()


NUE = re.compile(r"\b(onClick|onCancel)=\{\s*(?:\(\)\s*=>\s*)?onClose(?:\?\.)?(?:\(\))?\s*\}")
LIBELLE = re.compile(r">\s*([^<{]{1,40}?)\s*<")


def ligne_de(texte, idx):
    return texte.count("\n", 0, idx) + 1


def sonde(ctx=None):
    nues, ooc_nus, differents, gardes, temoins_ok = [], [], [], [], []
    for p in sorted(SRC.rglob("*.jsx")):
        if ".test." in p.name:
            continue
        brut = p.read_text(encoding="utf-8")
        s = nettoyer(brut)
        if "useDirtyGuard(" not in s and "useFormSafety(" not in s:
            continue
        rel = p.relative_to(SRC).as_posix()
        for nom, corps in composants(s):
            debut = s.find(corps)
            gardes_A = [norm(a) for _, a in arguments(corps, "useDirtyGuard")]
            if "useFormSafety(" in corps:
                gardes_A.append("dirty")  # useFormSafety enregistre useDirtyGuard(dirty) et offre guardedClose
            if not gardes_A:
                continue
            site = f"{rel}::{nom}"
            gardes.append(f"{site} — useDirtyGuard({' | '.join(gardes_A)})")
            for m in NUE.finditer(corps):
                fin_balise = corps.find(">", m.end())
                lib = LIBELLE.search(corps, fin_balise - 1, fin_balise + 120) if fin_balise > 0 else None
                nues.append(f"{site} l.{ligne_de(s, debut + m.start())} {m.group(0)} « {lib.group(1).strip() if lib else '?'} »")
            for m in re.finditer(r"onOpenChange=\{", corps):
                fb = fin_appariee(corps, m.end() - 1, "{", "}")
                h = corps[m.end():fb]
                if re.search(r"\bonClose\b", h) and "confirmLeaveIfDirty" not in h and "guardedClose" not in h:
                    ooc_nus.append(f"{site} l.{ligne_de(s, debut + m.start())} onOpenChange={{{norm(h)}}}")
            for pos, x in arguments(corps, "confirmLeaveIfDirty"):
                nx = norm(x)
                if nx in gardes_A or nx == "isAnyFormDirty()":
                    temoins_ok.append(f"{site} l.{ligne_de(s, debut + pos)} confirmLeaveIfDirty({nx})")
                else:
                    differents.append(f"{site} l.{ligne_de(s, debut + pos)} confirmLeaveIfDirty({nx}) ≠ garde {gardes_A}")
    return {"repro": bool(nues or ooc_nus),
            "observe": {"composants_gardes": gardes, "sorties_nues": nues, "onOpenChange_nus": ooc_nus,
                        "booleen_different_a_juger": differents, "sorties_gardees": temoins_ok},
            "methode": "lecture écran"}


if __name__ == "__main__":
    import json, sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
