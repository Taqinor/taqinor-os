"""Constat C-AERR-002 (devis, S2, C13 ; tâche AERR2, correctif 2ff2465dee) : pages/ventes/DevisList.jsx::DevisList.
Une relecture ratée ou en cours ne doit plus démonter la liste. Le détecteur lit le CORRECTIF : les deux retours anticipés
(`if (loading && …)` / `if (error && …)`) portent la condition `devis.length === 0`, et la liste gardée affiche l'avis
« Liste pas à jour » (`data-testid="devis-pas-a-jour"`) avec « Réessayer ». repro = l'un des trois manque.
Réécrite le 20/11/2026 : l'ancienne règle lisait un motif périmé."""
SONDE = {"constat": "C-AERR-002", "sha": "3acfee471",
         "attendu": "un retour anticipé `if (loading…)` / `if (error…)` sans `devis.length === 0`, ou pas d'avis devis-pas-a-jour avec « Réessayer »"}
import os, pathlib, re
# AUDIT_RACINE (optionnel) : racine d'un autre arbre (témoin négatif sur l'arbre d'avant le correctif).
RACINE = pathlib.Path(os.environ.get("AUDIT_RACINE") or pathlib.Path(__file__).resolve().parents[4])
SRC = RACINE / "frontend/src"


def nettoyer(s):
    """Retire les commentaires // et /* */ ; les chaînes sont respectées (' et " s'arrêtent en fin de ligne)."""
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
    """Texte entre le délimiteur ouvrant en position i et son fermant apparié (chaînes ignorées)."""
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
    """Corps `{...}` de `function nom` / `const nom = (...) =>` (premier `{` précédé de `>` ou `)`)."""
    m = re.search(r"(?:function\s+|(?:const|let)\s+)" + re.escape(nom) + r"\b", s or "")
    if not m:
        return None
    for h in re.finditer(r"\{", s[m.end():]):
        p = m.end() + h.start()
        if s[:p].rstrip()[-1:] in ">)":
            return apparier(s, p)
    return None


def section(s, nom):
    """Du début de `function nom` / `const nom` à la prochaine déclaration en colonne 0 (robuste au JSX)."""
    m = re.search(r"(?:function\s+|(?:const|let)\s+)" + re.escape(nom) + r"\b", s or "")
    if not m:
        return None
    n = re.search(r"\n(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|const|let)\s", s[m.end():])
    return s[m.start():m.end() + n.start()] if n else s[m.start():]


def catchs(s):
    """Arguments de chaque `.catch(...)` du texte."""
    return [apparier(s, m.end() - 1, "(", ")") or "" for m in re.finditer(r"\.catch\s*\(", s or "")]


def confirme(src, nom, portee=None):
    """(corps_confirme, [appel_confirme...]) : confirmation dans le corps de `nom`, ou juste avant chacun de ses appels."""
    c = corps(src, nom)
    if c is None:
        return None
    t = portee if portee is not None else src
    return bool(re.search(r"confirm", c, re.I)), [bool(re.search(r"confirm", t[max(0, m.start() - 220):m.start()], re.I))
                                                  for m in re.finditer(r"(?<![\w.])" + re.escape(nom) + r"\(", t)]


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


LIGNES = r"devis\.length\s*===?\s*0|!\s*devis\.length\b"


def sonde(ctx=None):
    intr, rest, det = [], [], {}
    dl = lire("pages/ventes/DevisList.jsx")
    sec = section(dl, "DevisList") if dl else None
    if sec is None:
        return rendu(False, ["pages/ventes/DevisList.jsx::DevisList"])
    for nom, mot in (("retour_chargement", "loading"), ("retour_erreur", "error")):
        m = re.search(r"if\s*\(\s*(" + mot + r"\b[^)]*)\)\s*\{\s*return", sec)
        if not m:
            intr.append("DevisList::" + nom); continue
        garde = bool(re.search(LIGNES, m.group(1)))
        det[nom] = {"condition": m.group(1).strip(), "garde_sur_les_lignes": garde}
        if not garde:
            rest.append("DevisList::%s sans devis.length === 0" % nom)
    i = sec.find('data-testid="devis-pas-a-jour"')
    avis = i >= 0 and "Réessayer" in sec[i:i + 900]
    det["avis_pas_a_jour_avec_reessayer"] = avis
    if not avis:
        rest.append("DevisList : avis « Liste pas à jour » + « Réessayer » absent")
    return rendu(rest, intr, defaut_encore_present=rest, **det)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
