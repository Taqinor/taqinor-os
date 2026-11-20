"""Constat C-AERR-095 (stock, S2, C2 ; tâche AERR124, correctif ac12380d77) : pages/parametres/GammesMarquesPage.jsx (jumeau
de C-AERR-027) et AchatsParametresPage.jsx. Chargement raté -> formulaire vide éditable puis « Enregistrer » écrase ou reste
muet. Le détecteur lit le CORRECTIF : Gammes — le .catch du chargement pose un drapeau d'échec ou submit est gardé ;
Achats — le .catch pose un drapeau (`setX(true)`), l'avis « Réglages illisibles » avec « Réessayer » est affiché sous ce
drapeau, et le `disabled` de `<FormulaireReglages>` inclut ce drapeau. `if (!id) return` n'est plus compté.
Réécrite le 20/11/2026 : l'ancienne règle lisait un motif périmé."""
SONDE = {"constat": "C-AERR-095", "sha": "3acfee471",
         "attendu": ".catch du chargement sans drapeau d'échec et submit non gardé (Gammes) ; drapeau, avis « Réglages illisibles » + « Réessayer » ou disabled du formulaire manquant (Achats)"}
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


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


FLAG = r"set\w*(?:err|erreur|echec|fail|echoue)\w*|\b\w*(?:erreur|echec|echoue|loadError|loadFailed)\b"


def sonde(ctx=None):
    rest, intr, det = [], [], {}
    t = lire("pages/parametres/GammesMarquesPage.jsx")
    sec = section(t, "GammesMarquesPage") if t else None
    cs = catchs(sec) if sec else []
    if not cs:
        intr.append("pages/parametres/GammesMarquesPage.jsx::GammesMarquesPage (chargement .catch)")
    else:
        sv = corps(sec, "submit") or ""
        garde = bool(re.search(r"if\s*\([^)]*(?:" + FLAG + r")[^)]*\)\s*return", sv, re.I))
        drapeau = bool(re.search(FLAG, cs[0], re.I))
        det["GammesMarquesPage"] = {"catch_pose_un_drapeau_d_echec": drapeau, "submit_garde_par_le_drapeau": garde,
                                    "catch": " ".join(cs[0].split())[:90]}
        if not drapeau and not garde:
            rest.append("GammesMarquesPage")
    t = lire("pages/parametres/AchatsParametresPage.jsx")
    sec = section(t, "AchatsParametresPage") if t else None
    cs = catchs(sec) if sec else []
    if not cs:
        intr.append("pages/parametres/AchatsParametresPage.jsx::AchatsParametresPage (chargement .catch)")
    else:
        ms = re.search(r"\b(set\w+)\(\s*true\s*\)", cs[0])
        mv = re.search(r"const\s*\[\s*(\w+)\s*,\s*" + re.escape(ms.group(1)) + r"\s*\]", sec) if ms else None
        var = mv.group(1) if mv else None
        pos = sec.find("Réglages illisibles")
        avis = bool(var and pos >= 0 and "Réessayer" in sec[pos:pos + 500]
                    and re.search(r"\{\s*" + re.escape(var) + r"\s*&&", sec[max(0, pos - 300):pos]))
        md = re.search(r"<FormulaireReglages\b[^>]*?\bdisabled=\{([^}]*)\}", sec, re.S)
        bloque = bool(var and md and re.search(r"\b" + re.escape(var) + r"\b", md.group(1)))
        det["AchatsParametresPage"] = {"drapeau_d_echec": var, "avis_illisible_avec_reessayer": avis,
                                       "formulaire_desactive_par_le_drapeau": bloque}
        if not (var and avis and bloque):
            rest.append("AchatsParametresPage")
    return rendu(rest, intr, emplacements_fautifs=rest, **det)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
