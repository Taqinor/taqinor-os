"""Constat C-AERR-011 (devis, S2, C2) : features/ventes/quote/hooks/useChargeurEdition.js::rechargerDevisRecompose efface le brouillon (clear())
et recharge le générateur ; « Ajouter le BOQ électrique » (AjouterBoqElectrique::ajouter) et « Créer un lot multi-sites » (LotsMultiSites::creer)
l'appellent sans test de `dirty` ni confirmation. Le détecteur cherche ce garde dans les trois fonctions."""
SONDE = {"constat": "C-AERR-011", "sha": "3acfee471",
         "attendu": 'clear() dans rechargerDevisRecompose sans dirty/confirm ; ajouter et creer sans dirty/confirm'}
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
    h = lire("features/ventes/quote/hooks/useChargeurEdition.js")
    c = corps(h, "rechargerDevisRecompose") if h else None
    if c is None:
        return rendu(False, ["useChargeurEdition.js::rechargerDevisRecompose"])
    garde = lambda s: bool(re.search(r"dirty|confirm", s, re.I))
    appelants, intr = {}, []
    for rel, fn in (("features/ventes/AjouterBoqElectrique.jsx", "ajouter"), ("features/ventes/LotsMultiSites.jsx", "creer")):
        s = lire(rel)
        cc = corps(s, fn) if s else None
        if cc is None:
            intr.append(rel + "::" + fn)
        else:
            appelants[rel.split("/")[-1] + "::" + fn] = garde(cc)
    efface = "clear(" in c
    repro = efface and not garde(c) and not any(appelants.values())
    return rendu(repro, intr, efface_le_brouillon=efface, garde_dans_rechargerDevisRecompose=garde(c),
                 garde_dans_les_appelants=appelants)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
