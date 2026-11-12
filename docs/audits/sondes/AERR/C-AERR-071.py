"""Constat C-AERR-071 (chantiers, C13, S2) : pages/interventions/InterventionsPage.jsx::InterventionsPage : `fetchData` pose `setError` en échec et le rendu fait
`if (error) return …` inconditionnel : après un changement de statut, une réaffectation ou un tirer-pour-actualiser raté, l'erreur remplace la
liste. Le détecteur cherche le `.catch(() => setError(` et un retour sur error sans test sur les lignes."""
SONDE = {"constat": "C-AERR-071", "sha": "3acfee471",
         "attendu": '.catch(() => setError( dans fetchData et if (error) return sans test sur items/filtered'}
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


REL = "pages/interventions/InterventionsPage.jsx"


def sonde(ctx=None):
    s = lire(REL)
    c = corps(s, "InterventionsPage") if s else None
    if c is None:
        return rendu(False, [REL + "::InterventionsPage"])
    fd = (re.search(r"const fetchData[\s\S]*?\n  const reload", c) or [""])[0]
    pose = any("setError(" in x for x in appels(fd, r"\.catch"))
    m = re.search(r"if\s*\(\s*(error[^)]*)\)\s*\{?\s*return", c)
    if not m:
        return rendu(False, [REL + "::`if (error) return`"], catch_pose_setError=pose)
    sans_test = not re.search(r"length|items|filtered|rows", m.group(1))
    return rendu(pose and sans_test, [], catch_pose_setError=pose, condition=m.group(1).strip(), teste_les_lignes=not sans_test)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
