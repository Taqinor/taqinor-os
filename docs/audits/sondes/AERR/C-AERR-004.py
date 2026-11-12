"""Constat C-AERR-004 (facturation, S2, C13) : pages/ventes/RelancesPage.jsx::load avale l'échec (`.catch(() => {})`) puis le rendu affiche
l'état festif « Aucune facture impayée » quand rows est vide : une panne ressemble à une bonne nouvelle. Le détecteur cherche un `.catch`
sans état dans load ET l'absence de toute branche d'erreur avant `rows.length === 0 ? (<EmptyState`."""
SONDE = {"constat": "C-AERR-004", "sha": "3acfee471",
         "attendu": "load : .catch sans aucun set*(...) ; rendu `rows.length === 0 ? (` sans variable d'erreur dans la chaîne de conditions"}
import pathlib, re
RACINE = pathlib.Path(__file__).resolve().parents[4]
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

def sonde(ctx=None):
    t = lire("pages/ventes/RelancesPage.jsx")
    c = corps(t, "load") if t else None
    if c is None:
        return rendu(False, ["pages/ventes/RelancesPage.jsx::load"])
    catch_vide = [not re.search(r"\bset[A-Z]\w*\(", x) for x in catchs(c)]
    m = re.search(r"rows\.length\s*===\s*0\s*\?\s*\(", t)
    if not m:
        return rendu(False, ["RelancesPage::rendu `rows.length === 0 ? (`"], catch_vide_dans_load=catch_vide)
    fenetre = t[max(0, m.start() - 600):m.start()]
    erreur_dans_la_chaine = bool(re.search(r"erreur|\berr\b|error|echec|échec", fenetre, re.I))
    repro = bool(catch_vide) and all(catch_vide) and not erreur_dans_la_chaine
    cf = re.search(r"changerFile\s*=\s*\(\w*\)\s*=>\s*\{([^}]*)\}", t)
    return rendu(repro, [], catch_vide_dans_load=catch_vide, erreur_dans_la_chaine_de_rendu=erreur_dans_la_chaine,
                 changerFile=(cf.group(1).strip() if cf else None),
                 garde_d_ordre_dans_load=bool(re.search(r"runId|seq|requestId|ignore|cancel|active", c)))


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
