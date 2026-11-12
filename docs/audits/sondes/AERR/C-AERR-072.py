"""Constat C-AERR-072 (stock, C13, S2) : pages/stock/BonsCommandeFournisseur.jsx::reload et pages/stock/ModelesBcf.jsx::reload font `.catch(() => setItems([]))`
après chaque fusion ou sauvegarde : la liste est vidée et l'écran affirme « Aucun bon de commande ». Le détecteur liste les `reload` dont un
`.catch` remet les éléments à vide."""
SONDE = {"constat": "C-AERR-072", "sha": "3acfee471",
         "attendu": '.catch(() => setItems([])) dans le reload des deux fichiers'}
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


FICHIERS = ("pages/stock/BonsCommandeFournisseur.jsx", "pages/stock/ModelesBcf.jsx")


def sonde(ctx=None):
    intr, rest = [], []
    for rel in FICHIERS:
        c = corps(lire(rel), "reload")
        if c is None:
            intr.append(rel + "::reload"); continue
        if any(re.search(r"setItems\(\s*\[\s*\]\s*\)", x) for x in appels(c, r"\.catch")):
            rest.append(rel + "::reload vide la liste en échec")
    return rendu(rest, intr, defaut_encore_present=rest)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
