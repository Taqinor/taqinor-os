"""Contre-visite AERR de clôture (VER2-202, paramètres, S2, constat C-AERR-VER1-160 fermé en partie par AERR134) :
pages/parametres/ParametresEntreprise.jsx::ParametresEntreprise. AERR134 a gardé montées (SectionGardee) les huit sections
nommées par sa tâche, mais « E-mail » et « Monitoring » sont encore rendues par `{tab === '…' && <… />}` : un aller-retour
d'onglet les démonte. `EmailSection.jsx` tient en état local les modèles d'e-mail modifiés (sujet et corps, en trois
langues, `setTemplateField`) jusqu'au clic « Enregistrer » (`saveTemplate`) ; `MonitoringSection.jsx` tient le seuil et
la création automatique de ticket (`setSettings`) jusqu'à « Enregistrer ». Un clic d'onglet perd la saisie, sans question.
La sonde VER1-160 dit `repro: false` parce que sa liste de noms de brouillon ne reconnaît ni `templates` ni `settings`.
Le détecteur vérifie : (1) les deux rendus conditionnels hors SectionGardee, (2) l'état local modifiable et la sauvegarde
explicite dans chacune des deux sections, (3) l'existence de SectionGardee dans la page (le survivant)."""
SONDE = {"constat": "C-AERR-VER2-202", "sha": "d986bb9bc",
         "attendu": "email et monitoring rendus par tab === … && hors SectionGardee + brouillon local à sauvegarde explicite dans les deux sections"}
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
    page = lire("pages/parametres/ParametresEntreprise.jsx")
    email = lire("pages/parametres/EmailSection.jsx")
    moni = lire("pages/parametres/MonitoringSection.jsx")
    introuvable = [r for r, t in (("ParametresEntreprise.jsx", page), ("EmailSection.jsx", email),
                                  ("MonitoringSection.jsx", moni)) if t is None]
    if introuvable:
        return {"repro": False, "observe": {"introuvable": introuvable}, "methode": "lecture écran"}
    survivant = bool(re.search(r"function\s+SectionGardee\s*\(", page))
    demonte = {cle: bool(re.search(r"\{\s*tab\s*===\s*'%s'\s*&&\s*<%s\s*/>\s*\}" % (cle, comp), page))
               for cle, comp in (("email", "EmailSection"), ("monitoring", "MonitoringSection"))}
    garde = {cle: bool(re.search(r"<SectionGardee\s+actif=\{tab\s*===\s*'%s'\}" % cle, page))
             for cle in ("email", "monitoring")}
    brouillon_email = bool(re.search(r"onChange=\{\s*e\s*=>\s*setTemplateField\(t\.cle,\s*'corps'", email))
    sauve_email = bool(re.search(r"onClick=\{\(\)\s*=>\s*saveTemplate\(t\)\}", email))
    brouillon_moni = bool(re.search(r"onChange=\{\(e\)\s*=>\s*setSettings\(", moni))
    sauve_moni = "Enregistrer" in moni
    repro = (survivant and all(demonte.values()) and not any(garde.values())
             and brouillon_email and sauve_email and brouillon_moni and sauve_moni)
    return {"repro": repro,
            "observe": {"SectionGardee_existe": survivant, "rendu_conditionnel_demonte": demonte,
                        "sous_SectionGardee": garde, "email_corps_modifiable_en_local": brouillon_email,
                        "email_sauvegarde_explicite": sauve_email, "monitoring_modifiable_en_local": brouillon_moni,
                        "monitoring_sauvegarde_explicite": sauve_moni},
            "methode": "lecture écran"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
