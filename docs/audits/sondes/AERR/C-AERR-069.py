"""Constat C-AERR-069 (sav, C13, S2) : pages/sav/TicketsPage.jsx et pages/sav/EquipementsPage.jsx rendent `loading ? squelette : error ? erreur : liste` sans test
sur les lignes, et `onSaved={reload}` relit toute la liste après chaque enregistrement : squelette puis, en échec, l'erreur remplace la liste.
Le détecteur lit les deux conditions du rendu et le câblage `onSaved`."""
SONDE = {"constat": "C-AERR-069", "sha": "3acfee471",
         "attendu": 'loading ? … : error ? … sans test sur les lignes, et onSaved={reload}'}
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


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


FICHIERS = ("pages/sav/TicketsPage.jsx", "pages/sav/EquipementsPage.jsx")


def sonde(ctx=None):
    intr, rest, det = [], [], {}
    for rel in FICHIERS:
        s = lire(rel)
        m1 = re.search(r"\{\s*(loading[^{}?\n]*?)\s*\?\s*\(", s or "")
        m2 = re.search(r":\s*(error[^{}?:\n]*?)\s*\?\s*\(", s[m1.end():]) if m1 else None
        if not m2:
            intr.append(rel + "::rendu loading ? … : error ? …"); continue
        sans_test = [c for c in (m1.group(1), m2.group(1)) if not re.search(r"length|rows|items", c)]
        relit = "onSaved={reload}" in s
        det[rel] = {"conditions": [m1.group(1), m2.group(1)], "sans_test_sur_les_lignes": sans_test, "onSaved_reload": relit}
        if sans_test and relit:
            rest.append(rel)
    return rendu(rest, intr, defaut_encore_present=rest, **det)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
