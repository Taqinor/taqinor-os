# flake8: noqa  (sonde ATST, DÉTECTEUR hôte stdlib : lecture seule, ni node ni vitest — rejouable à la main)
"""PF7 / ATST : les tests `apps/web` de la proposition publique prouvent la PAGE en cherchant des chaînes dans le source
`.astro` ; un seul rend un composant (`ChainePrix.astro`). Le CÂBLAGE « valeur → case affichée » n'est donc prouvé par
rien : deux mutants du 11/11 restent verts sur les 337 fichiers de test (simulation statique : aucun littéral ni regex
d'un test qui lit la page ne change) — `SectionAgricole.astro` « Économie nette, année 1 » affiche
`argent.economies.depenseActuelleMadAn` (le client lit 32 871 au lieu de 32 271 MAD) ; `[...token].astro` `stickyTtc` prend
`'sans_batterie'` au lieu de `reco ?? 'sans_batterie'` (barre collante : 0 MAD ou l'autre option tant que le script ne
réécrit pas). Les e2e `/proposition` exigent `WEB_URL`, qu'aucun workflow ne pose ; `figures-parite` lit le JSON, pas la
page. Détecteur : `repro` vrai tant qu'aucun test ne rend ces deux fichiers ET qu'aucun test de source ne tue un mutant."""
SONDE = {"constat": "C-ATST-009", "sha": "ae5a7ae4c",
         "attendu": "0 test qui rend SectionAgricole.astro ou [...token].astro, 0 littéral/regex tueur pour les 2 mutants, WEB_URL absent des workflows -> repro True ; un rendu (AstroContainer) ou une assertion de câblage -> False"}
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[4]
if not (RACINE / "apps/web").is_dir():
    RACINE = Path.cwd()
WEB = RACINE / "apps/web"
AGRI = WEB / "src/components/proposition/agricole/SectionAgricole.astro"
PAGE = WEB / "src/pages/proposition/[...token].astro"
MUTANTS = {
    "SectionAgricole.astro:economieNetteAn1": (AGRI, "{formatMAD(argent.economies.economieNetteAn1)}",
                                              "{formatMAD(argent.economies.depenseActuelleMadAn)}"),
    "[...token].astro:stickyTtc": (PAGE, "const stickyTtc = ok && heroHasRealPrice\n  ? optionTtc(data!, reco ?? 'sans_batterie')",
                                  "const stickyTtc = ok && heroHasRealPrice\n  ? optionTtc(data!, 'sans_batterie')"),
}
LIT_PAGE = re.compile(r"lirePageProposition|lireAstroAvecBlocs|\[\.\.\.token\]|SectionAgricole|proposition/agricole")
RE_STR = re.compile(r"'((?:[^'\\\n]|\\.){4,})'|\"((?:[^\"\\\n]|\\.){4,})\"|`((?:[^`\\$]|\\.){4,})`")
RE_RX = re.compile(r"expect\(([^;]*?)\)(\.not)?\.toMatch\(\s*/((?:[^/\\\n]|\\.)+)/([gimsuy]*)\s*\)")
APPEL = re.compile(r"^\s*[A-Za-z_]\w*\(")  # sujet = sortie d'une fonction de lib, pas le source de la page
RENDU = re.compile(r"AstroContainer|renderToString")


def fichiers_test():
    for p in sorted(WEB.rglob("*")):
        if p.is_file() and "node_modules" not in p.parts and re.search(r"\.(test|spec)\.(ts|tsx|js|mjs)$", p.name):
            yield p


def sonde(ctx=None):
    for f in (AGRI, PAGE):
        if not f.is_file():
            return {"repro": False, "raison": "fichier absent : " + f.relative_to(RACINE).as_posix()}
    sources = {f: f.read_text(encoding="utf-8").replace("\r\n", "\n") for f in (AGRI, PAGE)}
    mutes = {}
    for nom, (f, avant, apres) in MUTANTS.items():
        if sources[f].count(avant) != 1:
            return {"repro": False, "raison": "site du mutant introuvable (code changé) : " + nom}
        mutes[nom] = (sources[f], sources[f].replace(avant, apres))
    rendus, lecteurs, lits, rxs = [], [], [], []
    for p in fichiers_test():
        t = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(RACINE).as_posix()
        if RENDU.search(t) and re.search(r"SectionAgricole\.astro|\[\.\.\.token\]\.astro|pages/proposition", t):
            rendus.append(rel)
        if not LIT_PAGE.search(t):
            continue
        lecteurs.append(rel)
        for m in RE_STR.finditer(t):
            s = next(g for g in m.groups() if g is not None)
            lits.append((rel, s.replace("\\'", "'").replace('\\"', '"').replace("\\\\", "\\")))
        for m in RE_RX.finditer(t):
            if not APPEL.match(m.group(1)):
                rxs.append((rel, bool(m.group(2)), m.group(3), m.group(4)))
    tueurs = {}
    for nom, (orig, mut) in mutes.items():
        k = [f"{f} | {s[:80]}" for f, s in lits if orig.count(s) != mut.count(s)]
        for f, neg, pat, fl in rxs:
            try:
                r = re.compile(pat, (re.I if "i" in fl else 0) | (re.M if "m" in fl else 0) | (re.S if "s" in fl else 0))
            except re.error:
                continue
            a, b = len(r.findall(orig)), len(r.findall(mut))
            if (neg and b > a) or (not neg and b < a):  # seul sens qui peut faire rougir l'assertion
                k.append(f"{f} | /{pat[:60]}/")
        tueurs[nom] = k
    wf = RACINE / ".github/workflows"
    web_url_ci = any("WEB_URL" in p.read_text(encoding="utf-8", errors="replace") for p in wf.glob("*.yml")) if wf.is_dir() else False
    repro = not rendus and all(not v for v in tueurs.values())
    return {"repro": repro, "tests_qui_rendent_ces_fichiers": rendus, "tests_qui_lisent_la_page": len(lecteurs),
            "tueurs_par_mutant": tueurs, "WEB_URL_dans_un_workflow": web_url_ci}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
