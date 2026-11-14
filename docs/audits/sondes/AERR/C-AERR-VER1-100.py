"""Contre-visite AERR (VER1-100, facturation, S2, régression d'AERR21) : pages/ventes/NoteDebitDialog.jsx::NoteDebitDialog.
AERR21 a remplacé `.catch(() => setNotes([]))` par `.catch(() => setLectureKo(true))` et n'affiche l'erreur que si
`notes.length === 0`. Or la boîte est montée EN PERMANENCE dans FactureList.jsx (sans `key`, seule la prop `facture`
change) et `notes` n'est jamais remis à zéro à l'ouverture ni au changement de facture : ouvrir « Notes de débit » sur la
facture A (notes lues), fermer, l'ouvrir sur B avec une lecture rejetée ⇒ la boîte titrée « Notes de débit — B » liste les
notes de A, sans aucune erreur, avec leurs boutons « Annuler » (admin) et « PDF ». Le détecteur vérifie les trois
conditions dans le source."""
SONDE = {"constat": "C-AERR-VER1-100", "sha": "47f925be1",
         "attendu": "catch sans setNotes + alerte masquée si notes non vide + boîte montée en permanence sans key ni remise à zéro de notes"}
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


def apparier(s, i, o="(", f=")"):
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


def sonde(ctx=None):
    nd = lire("pages/ventes/NoteDebitDialog.jsx")
    fl = lire("pages/ventes/FactureList.jsx")
    if nd is None or fl is None:
        return rendu(False, [x for x, v in (("NoteDebitDialog.jsx", nd), ("FactureList.jsx", fl)) if v is None])
    m = re.search(r"getNotesDebit", nd)
    if not m:
        return rendu(False, ["NoteDebitDialog::getNotesDebit"])
    # 1) Le catch de la lecture ne vide plus `notes`.
    c = re.search(r"\.catch\s*\(", nd[m.end():])
    arg_catch = apparier(nd, m.end() + c.end() - 1) if c else ""
    catch_vide_notes = bool(re.search(r"setNotes\(", arg_catch or ""))
    # 2) `notes` remis à zéro à l'ouverture / au changement de facture ? (hors `.then` de la lecture et hors création)
    then = re.search(r"\.then\s*\(", nd[m.end():])
    arg_then = apparier(nd, m.end() + then.end() - 1) if then else ""
    autres_set = [x.start() for x in re.finditer(r"setNotes\(\s*\[\s*\]\s*\)", nd)]
    reset_ouverture = bool(re.search(r"if\s*\(\s*open\s*\)\s*\{[^}]*setNotes\(", nd))
    # 3) L'alerte d'échec n'est rendue que si `notes` est vide.
    alerte_masquee = bool(re.search(r"lectureKo\s*&&\s*notes\.length\s*===\s*0", nd))
    # 4) La boîte est montée en permanence dans FactureList (pas de rendu conditionnel, pas de key).
    mt = re.search(r"<NoteDebitDialog\b", fl)
    if not mt:
        return rendu(False, ["FactureList.jsx <NoteDebitDialog"])
    avant = fl[max(0, mt.start() - 40):mt.start()]
    balise = fl[mt.start():fl.find("/>", mt.start())]
    montee_permanente = "&&" not in avant and not re.search(r"\bkey=", balise)
    repro = (not catch_vide_notes) and not reset_ouverture and not autres_set and alerte_masquee and montee_permanente
    return rendu(repro, [], catch_vide_notes=catch_vide_notes, remise_a_zero_a_l_ouverture=reset_ouverture,
                 setNotes_vide_ailleurs=len(autres_set), alerte_seulement_si_notes_vide=alerte_masquee,
                 boite_montee_en_permanence_sans_key=montee_permanente,
                 then_lit=" ".join((arg_then or "").split())[:80])


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
