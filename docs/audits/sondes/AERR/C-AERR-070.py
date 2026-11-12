"""Constat C-AERR-070 (stock, C13, S2) : pages/stock/StockList.jsx::StockList fait `if (error) return <EmptyState « Erreur de chargement »>` sans test « déjà
chargé » ni Réessayer ; les gestes relisent tout le catalogue (fetchProduits) et un échec remplace le catalogue par l'erreur. Le détecteur
lit la condition du retour anticipé sur error et son contenu."""
SONDE = {"constat": "C-AERR-070", "sha": "3acfee471",
         "attendu": 'if (error) return <EmptyState …> dont la condition ne teste pas les lignes (actifs.length)'}
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


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


REL = "pages/stock/StockList.jsx"


def sonde(ctx=None):
    s = lire(REL)
    c = corps(s, "StockList") if s else None
    m = re.search(r"if\s*\(\s*(error[^)]*)\)\s*(\{)\s*return", c or "")
    if not m:
        return rendu(False, [REL + "::StockList `if (error) return`"])
    bloc = apparier(c, m.start(2)) or ""
    sans_test = not re.search(r"length|actifs|produits", m.group(1))
    return rendu(sans_test, [], condition=m.group(1).strip(), teste_les_lignes=not sans_test,
                 bouton_reessayer=bool(re.search(r"onRetry|Réessayer|retry", bloc, re.I)),
                 relectures_fetchProduits=len(re.findall(r"dispatch\(\s*fetchProduits\(", s)))


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
