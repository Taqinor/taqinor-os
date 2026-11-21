"""Constat C-AERR-047 (lead, S2, C13 ; tâches AERR103, AERR156 ; correctif 2d75044d29) : features/crm/CallLogPopover.jsx::submit.
Un échec du report de relance après un appel journalisé ne doit ni dire « l'appel n'a pas pu être journalisé » ni créer un
second journal au nouvel essai. Le détecteur lit le CORRECTIF : `logInteraction(` est dans un `if` gardé par la reprise
(`!reprise` / `!appelJournalise`), le message « Appel journalisé ; la relance n'a pas pu être planifiée » existe, et le
message générique « L'appel n'a pas pu être journalisé » n'est atteint qu'après un test de l'étape (`… !== 'journal'`).
repro = l'un manque. Réécrite le 20/11/2026 : l'ancienne règle lisait un motif périmé."""
SONDE = {"constat": "C-AERR-047", "sha": "3acfee471",
         "attendu": "logInteraction( non gardé par la reprise, message « Appel journalisé ; la relance n'a pas pu être planifiée » absent, ou message générique non borné à l'étape journal"}
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


def catchs(s):
    """Arguments de chaque `.catch(...)` du texte."""
    return [apparier(s, m.end() - 1, "(", ")") or "" for m in re.finditer(r"\.catch\s*\(", s or "")]


def rendu(repro_, introuvable, **details):
    return {"repro": bool(repro_), "observe": {"introuvable": introuvable, **details}, "methode": "lecture écran"}


GENERIQUE = "L'appel n'a pas pu être journalisé"
ETAPE = "Appel journalisé ; la relance n'a pas pu être planifiée"


def sonde(ctx=None):
    t = lire("features/crm/CallLogPopover.jsx")
    b = corps(t, "submit") if t else None
    if b is None:
        return rendu(False, ["features/crm/CallLogPopover.jsx::submit"])
    garde = False
    for m in re.finditer(r"\bif\s*\(", b):
        cond = apparier(b, m.end() - 1, "(", ")")
        if cond is None:
            continue
        k = m.end() + len(cond) + 1
        mm = re.match(r"\s*\{", b[k:])
        bloc = apparier(b, k + mm.end() - 1) if mm else None
        if bloc and "logInteraction(" in bloc and re.search(r"!\s*(?:reprise|appelJournalise)\b", cond):
            garde = True
    msg = ETAPE in b
    mc = re.search(r"\bcatch\s*(?:\(\s*\w*\s*\))?\s*\{", b)
    capt = (apparier(b, mc.end() - 1) or "") if mc else ""
    pg = capt.find(GENERIQUE)
    borne = pg < 0 or bool(re.search(r"\w+\s*[!=]==?\s*['\"]journal['\"]", capt[:pg]))
    return rendu(not (garde and msg and borne), [], journal_garde_par_la_reprise=garde,
                 message_etape_relance_present=msg, message_generique_borne_a_l_etape_journal=borne)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
