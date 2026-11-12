"""Constat C-AERR-047 (lead, S2, C13) : features/crm/CallLogPopover.jsx::submit. Journal d'appel (`logInteraction`), report de relance
(`updateLead`) et activité sont dans UN seul `try` ; un échec du report affiche « L'appel n'a pas pu être journalisé — réessayez » alors que
l'appel l'est, et réessayer en crée un second. Le détecteur cherche les deux appels dans le même `try` et le message unique."""
SONDE = {"constat": "C-AERR-047", "sha": "3acfee471",
         "attendu": "logInteraction( et updateLead( dans le même bloc try de submit + littéral « L'appel n'a pas pu être journalisé — réessayez. »"}
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

def sonde(ctx=None):
    t = lire("features/crm/CallLogPopover.jsx")
    b = corps(t, "submit") if t else None
    if b is None:
        return rendu(False, ["features/crm/CallLogPopover.jsx::submit"])
    m = re.search(r"\btry\s*\{", b)
    essai = apparier(b, m.end() - 1) if m else ""
    ensemble = "logInteraction(" in essai and "updateLead(" in essai
    msg = "L'appel n'a pas pu être journalisé" in b
    return rendu(ensemble and msg, [], journal_et_report_dans_le_meme_try=ensemble, message_unique_present=msg)

if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
