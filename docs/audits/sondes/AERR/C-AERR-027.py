"""Constat C-AERR-027 (parametres/securite, S2, C2) : pages/parametres/DocumentsSection.jsx::DocumentsSection, pages/parametres/TarificationSection.jsx::
TarificationSection, pages/admin/SecuriteIdentitePage.jsx::BanniereTab : un chargement raté pose un formulaire vide/par défaut éditable (le .catch
du chargement ne pose aucun drapeau d'échec), puis « Enregistrer » écrase la vraie configuration. Le détecteur lit le premier .catch de chaque composant."""
SONDE = {"constat": "C-AERR-027", "sha": "3acfee471",
         "attendu": ".catch du chargement sans drapeau d'échec (ni setForm(null)) dans les 3 composants"}
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

FLAG = r"set\w*(?:err|erreur|echec|fail|echoue)\w*|\b\w*(?:erreur|echec|echoue|loadError|loadFailed)\w*\b"


def sonde(ctx=None):
    rest, intr, det = [], [], {}
    for rel, comp in (("pages/parametres/DocumentsSection.jsx", "DocumentsSection"),
                      ("pages/parametres/TarificationSection.jsx", "TarificationSection"),
                      ("pages/admin/SecuriteIdentitePage.jsx", "BanniereTab")):
        t = lire(rel)
        sec = section(t, comp) if t else None
        cs = catchs(sec) if sec else []
        if not cs:
            intr.append(rel + "::" + comp + " (chargement .catch)"); continue
        drapeau = bool(re.search(FLAG, cs[0], re.I)) or "setForm(null)" in cs[0]
        sv = corps(sec, "save")
        det[comp] = {"catch_pose_un_drapeau_d_echec": drapeau,
                     "catch": " ".join(cs[0].split())[:90],
                     "save_teste_un_drapeau": bool(sv and re.search(r"if\s*\([^)]*(?:" + FLAG + r")[^)]*\)\s*return", sv, re.I))}
        if not drapeau:
            rest.append(comp)
    return rendu(rest, intr, composants_ou_un_chargement_rate_ouvre_un_formulaire_enregistrable=rest, **det)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
