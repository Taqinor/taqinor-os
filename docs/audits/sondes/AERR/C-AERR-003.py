"""Constat C-AERR-003 (facturation, S2, C13) : les tuiles d'argent de pages/ventes/FactureList.jsx (encaissé du mois, total dû, impayées, en retard)
viennent de ventesSlice.js::fetchFacturesKpis, appelé UNE fois au montage et écrit par UN seul réducteur : aucun geste ne les met à jour.
Le détecteur compte les appels et les écritures du jeu de tuiles dans frontend/src (hors tests)."""
SONDE = {"constat": "C-AERR-003", "sha": "3acfee471",
         "attendu": 'un seul appel fetchFacturesKpis(), dans un useEffect de montage `[dispatch]`, et un seul réducteur qui écrit state.facturesKpis'}
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
    appels, ecritures, montage, intr = [], [], 0, []
    for p in sorted(SRC.rglob("*.js*")):
        rel = p.relative_to(SRC).as_posix()
        if ".test." in rel or "/__tests__/" in rel or p.suffix not in (".js", ".jsx"):
            continue
        if "acturesKpis" not in p.read_text(encoding="utf-8", errors="replace"):
            continue
        t = lire(rel)
        for m in re.finditer(r"fetchFacturesKpis\s*\(\s*\)", t):
            if t[max(0, m.start() - 30):m.start()].rstrip().endswith("="):
                continue
            appels.append(rel)
            if re.search(r"useEffect\(\s*\(\)\s*=>\s*\{?\s*dispatch\(\s*$", t[max(0, m.start() - 60):m.start()]) and \
               re.match(r"\s*\)\s*\}?\s*,\s*\[\s*dispatch\s*\]\s*\)", t[m.end():m.end() + 30]):
                montage += 1
        ecritures += [rel] * len(re.findall(r"\bfacturesKpis\s*=(?!=)", t))
    if not appels:
        intr.append("aucun appel de fetchFacturesKpis() trouvé sous frontend/src")
    ecr_reducteur = [e for e in ecritures if e.endswith("ventesSlice.js")]
    repro = bool(appels) and len(appels) == montage and len(ecr_reducteur) <= 2
    return rendu(repro, intr, appels=appels, appels_en_effet_de_montage=montage,
                 ecritures_de_facturesKpis=ecritures,
                 lecture="tuiles figées après un paiement/émission/annulation" if repro else "tuiles relues ou mises à jour par un geste")


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
