"""Contre-visite AERR de clôture (VER2-200, lead, S2, résidu d'AERR103) : features/crm/CallLogPopover.jsx::CallLogPopover.
AERR103 a posé `appelJournalise = useRef(false)` pour ne pas rejouer `logInteraction` quand la relance échoue après un
appel journalisé. Le drapeau n'est remis à faux QUE par `reset()`, et `reset()` n'est appelé qu'au succès de `submit`.
Fermer la fenêtre (Échap, clic dehors) ou passer à un autre lead ne le remet pas à zéro ; la popover reste montée (une
par ligne de liste ou carte, et sans `key` dans `workspace/TimelineTab.jsx`). Le prochain appel journalisé depuis cette
popover (même lead plus tard, ou lead B) saute `logInteraction` (`reprise` vrai) et affiche « Relance planifiée. » :
l'appel n'est jamais écrit au journal, le succès affiché est faux. Le détecteur vérifie dans le source : (1) la seule
remise à faux est dans le corps de `reset`, (2) `reset()` n'a qu'un site d'appel, dans `submit`, (3) `setOpen` ne remet
rien à zéro et aucun `useEffect` ne dépend de `leadId` ni de l'ouverture, (4) `reprise` saute bien `logInteraction`."""
SONDE = {"constat": "C-AERR-VER2-200", "sha": "d986bb9bc",
         "attendu": "remise à faux seulement dans reset + reset appelé seulement au succès + aucune remise à la fermeture ni au changement de lead"}
import pathlib, re
RACINE = pathlib.Path(__file__).resolve().parents[4]
SRC = RACINE / "frontend/src"


def nettoyer(s):
    """Retire les commentaires // et /* */ ; les chaînes sont respectées."""
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


def corps_de(s, motif):
    m = re.search(motif, s)
    return (apparier(s, m.end() - 1) or "") if m else ""


def sonde(ctx=None):
    rel = "features/crm/CallLogPopover.jsx"
    s = lire(rel)
    if s is None:
        return {"repro": False, "observe": {"introuvable": [rel]}, "methode": "lecture écran"}
    # Le composant s'arrête avant le hook exporté qui le suit (useCallEndedNudge) : on borne au premier `return (`.
    debut = re.search(r"export\s+default\s+function\s+CallLogPopover\s*\(", s)
    fin = s.find("const Icon =", debut.end()) if debut else -1
    corps = s[debut.end():fin] if debut and fin > 0 else ""
    corps_reset = corps_de(corps, r"const\s+reset\s*=\s*\(\)\s*=>\s*\{")
    corps_submit = corps_de(corps, r"const\s+submit\s*=\s*async\s*\(\)\s*=>\s*\{")
    corps_setopen = corps_de(corps, r"const\s+setOpen\s*=\s*\([^)]*\)\s*=>\s*\{")
    remises = len(re.findall(r"appelJournalise\.current\s*=\s*false", corps))
    remise_dans_reset = bool(re.search(r"appelJournalise\.current\s*=\s*false", corps_reset))
    appels_reset = len(re.findall(r"(?<![\w.])reset\(\)", corps))
    reset_dans_submit = len(re.findall(r"(?<![\w.])reset\(\)", corps_submit))
    setopen_remet = bool(re.search(r"reset\(|appelJournalise", corps_setopen))
    effets = len(re.findall(r"\buseEffect\(", corps))
    saute = bool(re.search(r"if\s*\(\s*!planificationSeule\s*&&\s*!reprise\s*\)\s*\{\s*await\s+crmApi\.logInteraction",
                           corps_submit))
    toast_faux = bool(re.search(r"reprise\s*\?\s*'Relance planifi", corps_submit))
    repro = (remises == 1 and remise_dans_reset and appels_reset == 1 and reset_dans_submit == 1
             and not setopen_remet and effets == 0 and saute and toast_faux)
    return {"repro": repro,
            "observe": {"composant_trouve": bool(corps), "remises_a_faux": remises,
                        "remise_dans_reset": remise_dans_reset, "appels_reset": appels_reset,
                        "dont_dans_submit": reset_dans_submit, "setOpen_remet_a_zero": setopen_remet,
                        "useEffect_dans_le_composant": effets, "reprise_saute_logInteraction": saute,
                        "toast_relance_planifiee_sur_reprise": toast_faux},
            "methode": "lecture écran"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
