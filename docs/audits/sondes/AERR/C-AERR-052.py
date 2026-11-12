"""Constat C-AERR-052 (lead, S2, C2) : features/crm/workspace/useLeadDraft.js (+ LeadsPage.jsx::onOpenDuplicate / openNew). Aucune garde de
navigation dans l'application (seul `useDirtyGuard` = beforeunload) et aucun envoi quand la fiche se démonte : un raccourci, un clic de
menu, `?new=1` ou l'ouverture d'un doublon quittent la fiche sans question. Le détecteur cherche l'absence de garde de navigation ET de
`flush` dans tout nettoyage d'effet."""
SONDE = {"constat": "C-AERR-052", "sha": "3acfee471",
         "attendu": "useLeadDraft.js sans useNavigationGuard/useBlocker et aucun nettoyage d'effet qui appelle flush"}
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


def catchs(s):
    """Arguments de chaque `.catch(...)` du texte."""
    return [apparier(s, m.end() - 1, "(", ")") or "" for m in re.finditer(r"\.catch\s*\(", s or "")]


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}

def nettoyages(s):
    """Texte de chaque fonction de nettoyage d'effet (`return () => ...` et `() => () => ...`)."""
    out = []
    for m in re.finditer(r"(?:return|=>)\s*\(\s*\)\s*=>\s*", s):
        if s[m.end():m.end() + 1] == "{":
            out.append(apparier(s, m.end()) or "")
        else:
            out.append(s[m.end():s.find("\n", m.end())])
    return out


def sonde(ctx=None):
    t = lire("features/crm/workspace/useLeadDraft.js")
    if t is None:
        return rendu(False, ["features/crm/workspace/useLeadDraft.js"])
    garde = sorted(set(re.findall(r"useNavigationGuard|useBlocker|unstable_usePrompt", t)))
    flush_demontage = [n for n in nettoyages(t) if re.search(r"\bflush\w*\b", n)]
    ld = lire("pages/crm/leads/LeadsPage.jsx")
    dup = corps(ld, "onOpenDuplicate") if ld else None
    return rendu(not garde and not flush_demontage, [], garde_de_navigation=garde,
                 nettoyages_d_effet=len(nettoyages(t)), nettoyages_qui_envoient=len(flush_demontage),
                 useDirtyGuard_seul=("useDirtyGuard(" in t),
                 onOpenDuplicate_bascule_sans_leaveGuard=(dup is not None and "setEditLead" in dup and "leaveGuard" not in dup))

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
