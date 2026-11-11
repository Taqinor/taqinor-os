"""Constat C-AERR-091 (lead, S2, C2) : pages/crm/leads/LeadDetailPage.jsx::LeadDetailPage monte <LeadWorkspace> sans onSigneRefuse alors que
features/crm/workspace/LeadWorkspace.jsx l'appelle sur un refus du serveur à « Signé » : la saisie est perdue (jumeau oublié d'ACVI68). Le détecteur lit le bloc
<LeadWorkspace ...> de la page et cherche la prop onSigneRefuse."""
SONDE = {"constat": "C-AERR-091", "sha": "3acfee471",
         "attendu": "le bloc <LeadWorkspace de LeadDetailPage sans onSigneRefuse= alors que LeadWorkspace.jsx appelle onSigneRefuse?.("}
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


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}

def bloc_jsx(s, balise):
    """Texte de la balise JSX `<balise ...` jusqu'au `>` fermant hors accolades."""
    m = re.search(r"<" + re.escape(balise) + r"\b", s or "")
    if not m:
        return None
    d, j = 0, m.end()
    while j < len(s):
        c = s[j]
        if c == "{":
            d += 1
        elif c == "}":
            d -= 1
        elif d == 0 and c == ">":
            return s[m.start():j + 1]
        j += 1
    return None


def sonde(ctx=None):
    page = lire("pages/crm/leads/LeadDetailPage.jsx")
    ws = lire("features/crm/workspace/LeadWorkspace.jsx")
    b = bloc_jsx(page, "LeadWorkspace")
    if b is None or ws is None:
        return rendu(False, ["pages/crm/leads/LeadDetailPage.jsx::<LeadWorkspace", "features/crm/workspace/LeadWorkspace.jsx"])
    appelle = bool(re.search(r"\bonSigneRefuse\s*\??\.?\s*\(", ws))
    passe = bool(re.search(r"\bonSigneRefuse\s*=", b))
    return rendu(appelle and not passe, [], workspace_appelle_onSigneRefuse=appelle, page_passe_onSigneRefuse=passe)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
