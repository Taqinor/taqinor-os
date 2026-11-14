"""Contre-visite AERR (VER1-160, parametres, S2, jumeau d'AERR72) : pages/parametres/ParametresEntreprise.jsx::ParametresEntreprise.
AERR72 a enveloppé 4 sections autonomes (documents, tarification, donnees, statuts) dans `SectionGardee` (montée puis
masquée), mais toutes les autres sections AUTONOMES (sans `{...ctx}`) restent rendues par `{tab === 'x' && <Section />}` :
changer d'onglet les démonte avec leur brouillon local. Exemples : ModelesBrandesSection (corps de modèle en cours
d'édition, état `dirty`), TraductionsSection (`drafts` non enregistrés), EmailSection, AutomatisationsSection… La garde
`useNavigationGuard(dirty)` ne suit que le formulaire de profil. Le détecteur liste les sections autonomes encore rendues
par `tab === … &&` dont le source tient un brouillon local (useState `draft`/`drafts`/`edit`/`dirty`/`form` + onChange)."""
SONDE = {"constat": "C-AERR-VER1-160", "sha": "47f925be1",
         "attendu": "au moins une section autonome à brouillon local encore rendue par `tab === … &&` (hors SectionGardee)"}
import pathlib, re
RACINE = pathlib.Path(__file__).resolve().parents[4]
SRC = RACINE / "frontend/src"
DOSSIER = SRC / "pages/parametres"


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


def lire(p):
    return nettoyer(p.read_text(encoding="utf-8")) if p.is_file() else None


BROUILLON = re.compile(r"const\s*\[\s*(draft|drafts|edit|dirty|form|brouillon|valeurs)\b\s*,\s*set\w+\s*\]\s*=\s*useState")


def sonde(ctx=None):
    hote = lire(DOSSIER / "ParametresEntreprise.jsx")
    if hote is None:
        return {"repro": False, "observe": {"introuvable": ["pages/parametres/ParametresEntreprise.jsx"]}, "methode": "lecture écran"}
    gardees = re.findall(r"<SectionGardee\s+actif=\{tab === '(\w+)'\}", hote)
    nues = re.findall(r"\{tab === '(\w+)'\s*&&\s*<(\w+)\s*/>\s*\}", hote)
    imports = dict((m.group(1), m.group(2)) for m in re.finditer(r"import\s+(\w+)\s+from\s+'\./(\w+)'", hote))
    exposees, sans_source = [], []
    for onglet, comp in nues:
        fichier = imports.get(comp)
        src = lire(DOSSIER / f"{fichier}.jsx") if fichier else None
        if src is None:
            sans_source.append(comp); continue
        etats = sorted(set(m.group(1) for m in BROUILLON.finditer(src)))
        if etats and "onChange" in src:
            exposees.append({"onglet": onglet, "section": comp, "etats_brouillon": etats})
    return {"repro": bool(exposees),
            "observe": {"introuvable": [], "sections_gardees": gardees,
                        "sections_autonomes_demontees_avec_brouillon": exposees,
                        "sections_sans_source_locale": sans_source},
            "methode": "lecture écran"}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
