"""Constat C-AERR-092 (analyse, S2, C13) : features/offlinesync/mobile/AFaireAujourdhui.jsx::AFaireAujourdhui lit en suppressErrorToast puis .catch(() => []) et affiche
« Rien d'urgent aujourd'hui » sans variable d'erreur ; CommercialHome.jsx::CommercialHome vide leads/événements sur échec. Le détecteur cherche ces motifs."""
SONDE = {"constat": "C-AERR-092", "sha": "3acfee471",
         "attendu": "suppressErrorToast + .catch(() => []) + « Rien d'urgent » sans variable d'erreur ; CommercialHome .catch avec setLeads([])/setEvents([])"}
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

ERR = r"set\w*(?:err|erreur|echec|fail)\w*|\b(?:erreur|echec|loadError|isError|hasError|failed)\b"


def sonde(ctx=None):
    a = lire("features/offlinesync/mobile/AFaireAujourdhui.jsx")
    c = lire("features/offlinesync/mobile/CommercialHome.jsx")
    intr = [x for x, t in (("AFaireAujourdhui.jsx", a), ("CommercialHome.jsx", c)) if t is None]
    rest, det = [], {}
    if a is not None:
        sec = section(a, "AFaireAujourdhui") or ""
        vide = any(re.fullmatch(r"\s*\(\s*\)\s*=>\s*\[\s*\]\s*", x) for x in catchs(sec))
        sil = bool(re.search(r"suppressErrorToast\s*:\s*true", a))
        vu = "Rien d'urgent" in sec
        sans = not re.search(ERR, re.sub(r"suppressErrorToast", "", sec), re.I)
        det["AFaireAujourdhui"] = {"catch_vide": vide, "lectures_silencieuses": sil, "message_rien_d_urgent": vu, "sans_variable_d_erreur": sans}
        if vide and sil and vu and sans:
            rest.append("AFaireAujourdhui")
    if c is not None:
        sec = section(c, "CommercialHome") or ""
        vid = [x for x in catchs(sec) if re.search(r"set(?:Leads|Events)\(\s*\[\s*\]\s*\)", x)]
        det["CommercialHome"] = {"catch_qui_vide_la_liste": len(vid)}
        if vid:
            rest.append("CommercialHome")
    return rendu(rest, intr, ecrans_ou_une_panne_ressemble_a_un_vide=rest, **det)


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
