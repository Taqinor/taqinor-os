#!/usr/bin/env python3
"""GARDE CI (stage-names) — AGNR41 : un champ visible a un consommateur.

CLASSE C-AGNR-018 « champ visible sans consommateur » : un état d'écran du
générateur de devis (`const [x, setX] = useState` de `DevisGenerator.jsx` et des
`generator/*.jsx`) dont le setter est branché sur un `onChange` mais dont la
valeur n'est lue, hors de sa déclaration, que par l'INSTANTANÉ du brouillon, sa
RESTAURATION ou un `value=` de champ, est un champ qui ne change RIEN au devis
(`pompeHeures` : saisi, sauvegardé, jamais utilisé ; correctifs locaux AGNR26,
AGNR44).

Lecture structurelle du JSX (commentaires retirés), jamais un test « regex sur le
code » d'un test produit : pour chaque état, on classe ses lectures —

  * NEUTRES : la déclaration ; le bloc `draftSnapshot` (littéral d'objet + tableau
    de dépendances du `useMemo`) ; `value={x}` / `checked={x}` ; le passage
    `x={x}` à un composant enfant ; les lectures de `d.x` (restauration) ;
  * CONSOMMATRICES : toute autre lecture (un calcul, `etatEcran()`, une
    condition d'affichage, un appel).

Un état câblé (`onChange` / prop `={setX}`) sans AUCUNE lecture consommatrice
est signalé. Liste figée PAR FICHIER des sites existants (`SITES_FIGES`, une
raison par entrée) : elle ne peut que RÉTRÉCIR — une entrée morte (l'état a
maintenant un consommateur, ou n'existe plus) fait échouer la garde.

Usage : python scripts/check_champs_ecran_sans_consommateur.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENTES = Path("frontend") / "src" / "pages" / "ventes"
FICHIERS = ("DevisGenerator.jsx",)
DOSSIER_GENERATOR = "generator"
# fichier -> {variable: raison}. Ne peut que rétrécir (cliquet).
SITES_FIGES: dict = {
    "frontend/src/pages/ventes/DevisGenerator.jsx": {
        "pompeHeures":
            "AGNR26 : heures de pompage saisies mais ni lues par un calcul ni "
            "envoyees dans etape_params (instantane + value= seulement) ; "
            "retirer la ligne une fois AGNR26 faite.",
        "multiAccordionOpen":
            "etat d'affichage (accordeon) lu par le composant enfant recevant "
            "multiAccordionOpen={...} : consommateur hors fichier, "
            "non verifiable par cette lecture.",
    },
}

_RE_STATE = re.compile(r"\bconst\s*\[\s*(\w+)\s*,\s*(set\w+)\s*\]\s*=\s*useState\b")


def _sans_commentaires(texte: str) -> str:
    """Retire /* */ et // en conservant les retours à la ligne."""
    texte = re.sub(r"/\*[\s\S]*?\*/", lambda m: chr(10) * m.group(0).count(chr(10)), texte)
    return re.sub(r"(?m)(?<![:'\"`])//.*$", "", texte)


def _bloc_snapshot(lignes: list) -> set:
    """Indices de lignes du bloc `draftSnapshot` (de sa déclaration à la
    fermeture `])` de son tableau de dépendances)."""
    debut = next((i for i, l in enumerate(lignes) if re.search(r"\bconst\s+draftSnapshot\b", l)), None)
    if debut is None:
        return set()
    for fin in range(debut, len(lignes)):
        if re.match(r"\s*\]\)", lignes[fin]):
            return set(range(debut, fin + 1))
    return set(range(debut, len(lignes)))


def etats_sans_consommateur(source: str) -> dict:
    """{variable: ligne de déclaration} des états câblés sans consommateur."""
    lignes = _sans_commentaires(source).splitlines()
    snapshot = _bloc_snapshot(lignes)
    sortie = {}
    for i, ligne in enumerate(lignes):
        m = _RE_STATE.search(ligne)
        if not m:
            continue
        nom, setter = m.group(1), m.group(2)
        lecture = re.compile(r"(?<![\w.$])" + re.escape(nom) + r"(?![\w$])")
        cablage = re.compile(
            r"\b" + re.escape(setter) + r"\b(?=.*\bonChange\b)|\bonChange\b.*\b"
            + re.escape(setter) + r"\b|=\{\s*" + re.escape(setter) + r"\s*\}|\b"
            + re.escape(setter) + r"\s*\}\s*(?:/?>|$)")
        cable = False
        consomme = False
        for j, autre in enumerate(lignes):
            if j != i and cablage.search(autre):
                cable = True
            if j == i or j in snapshot:
                continue
            for lec in lecture.finditer(autre):
                contexte = autre[max(0, lec.start() - 8):lec.end() + 1]
                if re.search(r"(?:value|checked)=\{\s*" + re.escape(nom) + r"\b", autre):
                    continue  # value=/checked= d'un champ
                if re.search(r"\b" + re.escape(nom) + r"=\{\s*" + re.escape(nom) + r"\s*\}", autre):
                    continue  # passage x={x} à un enfant
                del contexte
                consomme = True
                break
            if consomme:
                break
        if cable and not consomme:
            sortie[nom] = i + 1
    return sortie


def _fichiers(root: Path) -> list:
    base = root / VENTES
    sortie = [base / n for n in FICHIERS if (base / n).is_file()]
    dossier = base / DOSSIER_GENERATOR
    if dossier.is_dir():
        sortie += [p for p in sorted(dossier.glob("*.jsx")) if ".test." not in p.name]
    return sortie


def analyser(root: Path = ROOT) -> dict:
    """{'fichier::variable': ligne}."""
    trouves = {}
    for p in _fichiers(root):
        source = p.read_text(encoding="utf-8")
        for nom, ligne in etats_sans_consommateur(source).items():
            trouves[f"{p.relative_to(root).as_posix()}::{nom}"] = ligne
    return trouves


def verifier(trouves: dict, figes: dict | None = None) -> list:
    figes = SITES_FIGES if figes is None else figes
    attendus = {f"{fichier}::{nom}" for fichier, noms in figes.items() for nom in noms}
    erreurs = []
    for cle, ligne in sorted(trouves.items()):
        if cle not in attendus:
            fichier, nom = cle.split("::", 1)
            erreurs.append(f"{fichier}:{ligne} — l'état `{nom}` est saisi (onChange) mais sa "
                           "valeur n'est lue que par l'instantané du brouillon, sa restauration "
                           "ou un value= : champ visible sans consommateur.")
    for cle in sorted(attendus - set(trouves)):
        erreurs.append(f"entrée MORTE de SITES_FIGES : {cle} a maintenant un consommateur "
                       "(ou n'existe plus) — retirez-la.")
    return erreurs


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    trouves = analyser()
    erreurs = verifier(trouves)
    if erreurs:
        print("check_champs_ecran_sans_consommateur: ÉCHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_champs_ecran_sans_consommateur: OK — {len(trouves)} champ(s) "
          "gelé(s), aucun nouveau.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
