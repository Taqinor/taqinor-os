"""Constat C-AERR-073 (chantiers, C13, S2) : pages/interventions/MaJourneePage.jsx::MaJourneePage (`load`) : sans cache, une tournée illisible devient
`setRows([])` puis « Aucune intervention aujourd'hui » (le technicien croit sa journée vide). Le détecteur lit `load` : chemin d'échec avec
`setRows([])` et aucun état d'erreur posé."""
SONDE = {"constat": "C-AERR-073", "sha": "3acfee471",
         "attendu": "load : chemin d'échec setRows([]) sans setError/setErreur, rendu EmptyState « Aucune intervention aujourd'hui »"}
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


def jusqua(s, nom, fin):
    """Texte de `const nom` jusqu'à la première occurrence de la regex `fin` (déclaration suivante)."""
    m = re.search(r"(?:function\s+|(?:const|let)\s+)" + re.escape(nom) + r"\b", s or "")
    if not m:
        return None
    e = re.search(fin, s[m.end():])
    return s[m.start():m.end() + e.start()] if e else s[m.start():]


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


REL = "pages/interventions/MaJourneePage.jsx"


def sonde(ctx=None):
    s = lire(REL)
    t = jusqua(s, "load", r"\n  useEffect\(") if s else None
    if t is None:
        return rendu(False, [REL + "::load"])
    vide = len(re.findall(r"setRows\(\s*\[\s*\]\s*\)", t))
    etat_erreur = re.findall(r"set\w*(?:Err|Echec|Fail)\w*\(", t)
    return rendu(vide > 0 and not etat_erreur, [], chemins_setRows_vide=vide, etat_erreur_pose=etat_erreur,
                 rendu_aucune_intervention="Aucune intervention aujourd'hui" in s)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
