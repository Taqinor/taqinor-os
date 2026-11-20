"""Constat C-AERR-005 (devis, S2, C2 ; tâches AERR5, AERR162, AERR120 ; correctifs dd9fd93542, 2042deebda) :
pages/ventes/DevisList.jsx::submitAccept. La modale qui se ferme au clic est un choix du fondateur (la fête part au clic) ;
le défaut est la saisie perdue sur un refus. Le détecteur lit le CORRECTIF dans le `catch` de submitAccept : la branche
400 rouvre la modale (`setAcceptTarget(d)`) et lit `champ` ; la branche finale (panne / générique) rouvre aussi la modale ;
et `openAcceptModal` est le SEUL endroit qui remet à zéro `setAcceptNom` / `setAcceptEntreprise` (la saisie survit à la
réouverture). repro = l'un manque. Réécrite le 20/11/2026 : l'ancienne règle lisait un motif périmé."""
SONDE = {"constat": "C-AERR-005", "sha": "3acfee471",
         "attendu": "catch de submitAccept sans setAcceptTarget(d) sur 400 ou sur la panne, `champ` non lu, ou remise à zéro de la saisie hors openAcceptModal"}
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


def bloc_apres(s, j):
    """(corps, fin) du bloc `{...}` qui suit la position j (espaces sautés), sinon (None, j)."""
    m = re.match(r"\s*\{", s[j:])
    if not m:
        return None, j
    o = j + m.end() - 1
    b = apparier(s, o)
    return (b, o + len(b) + 2) if b is not None else (None, j)


def branche_400(capt):
    """(corps de la branche dont la condition cite 400, fin, corps de la DERNIÈRE branche de la même chaîne)."""
    for m in re.finditer(r"\bif\s*\(", capt):
        cond = apparier(capt, m.end() - 1, "(", ")")
        if cond is None or not re.search(r"===?\s*400\b", cond):
            continue
        b, fin = bloc_apres(capt, m.end() + len(cond) + 1)
        if b is None:
            continue
        dernier = None
        while True:
            e = re.match(r"\s*else\s*", capt[fin:])
            if not e:
                break
            k = fin + e.end()
            if re.match(r"if\s*\(", capt[k:]):
                p = k + capt[k:].index("(")
                c2 = apparier(capt, p, "(", ")") or ""
                b2, fin2 = bloc_apres(capt, p + len(c2) + 2)
            else:
                b2, fin2 = bloc_apres(capt, k)
            if b2 is None:
                break
            dernier, fin = b2, fin2
        return b, dernier
    return None, None


ROUVRE = r"setAcceptTarget\(\s*(?!null\b)\w+\s*\)"
REMISE = r"setAcceptNom\(\s*(?!e\.target)|setAcceptEntreprise\("


def sonde(ctx=None):
    t = lire("pages/ventes/DevisList.jsx")
    c = corps(t, "submitAccept") if t else None
    o = corps(t, "openAcceptModal") if t else None
    if c is None or o is None:
        return rendu(False, ["pages/ventes/DevisList.jsx::submitAccept/openAcceptModal"])
    m = re.search(r"\bcatch\s*(?:\(\s*\w*\s*\))?\s*\{", c)
    capt = apparier(c, m.end() - 1) if m else ""
    b400, generique = branche_400(capt or "")
    rouvre_400 = bool(b400 and re.search(ROUVRE, b400))
    champ_lu = bool(b400 and re.search(r"\bchamp\b", b400))
    rouvre_panne = bool(generique and re.search(ROUVRE, generique))
    remises_hors = len(re.findall(REMISE, t)) - len(re.findall(REMISE, o))
    repro = not (rouvre_400 and champ_lu and rouvre_panne) or remises_hors > 0
    return rendu(repro, [], branche_400_trouvee=b400 is not None, rouvre_sur_400=rouvre_400, champ_lu_sur_400=champ_lu,
                 rouvre_sur_panne=rouvre_panne, remises_de_saisie_hors_openAcceptModal=remises_hors)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
