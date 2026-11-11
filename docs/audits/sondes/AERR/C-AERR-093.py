"""Constat C-AERR-093 (lead, S2, C13) : features/crm/relances/RelanceEtapeRow.jsx::chargerMotifs : un échec de lecture des motifs de perte fait setMotifs([]) (« Aucun motif
de perte n'est paramétré ») et la ref motifsDemandes reste vraie, donc aucune relecture. Le détecteur lit le .catch de chargerMotifs."""
SONDE = {"constat": "C-AERR-093", "sha": "3acfee471",
         "attendu": "dans chargerMotifs, .catch qui pose setMotifs([]) sans remettre motifsDemandes.current à false"}
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

def sonde(ctx=None):
    t = lire("features/crm/relances/RelanceEtapeRow.jsx")
    c = corps(t, "chargerMotifs") if t else None
    if c is None:
        return rendu(False, ["features/crm/relances/RelanceEtapeRow.jsx::chargerMotifs"])
    cs = catchs(c)
    vide = [bool(re.search(r"setMotifs\(\s*\[\s*\]\s*\)", x)) for x in cs]
    relu = [bool(re.search(r"motifsDemandes\.current\s*=\s*false", x)) for x in cs]
    return rendu(any(v and not r for v, r in zip(vide, relu)), [], catch_dans_chargerMotifs=len(cs),
                 catch_qui_vide_la_liste=vide, catch_qui_remet_la_garde_a_faux=relu,
                 garde_remise_a_faux_ailleurs=bool(re.search(r"motifsDemandes\.current\s*=\s*false", c)))


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
