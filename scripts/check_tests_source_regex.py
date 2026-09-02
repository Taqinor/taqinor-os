#!/usr/bin/env python3
"""QJR239 — garde CI : gele l'existant, interdit les NOUVEAUX tests
« regex sur code source ».

Contexte : le programme QJR108/QJR109 a converti une partie des tests de la
famille `DevisGenerator*`/`solar*`/`autoQuote*` qui assertaient encore par
`assert.match(<texte source>, /regex/)` sur un `.jsx`/`.js` lu via
`readFileSync` au lieu d'executer du code pur — un anti-patron fragile
(rougit sur un simple reformatage, reste vert sur une vraie regression). R3 a
classe le constat « directionnellement vrai mais numeriquement inverifiable »
(les chiffres 24/26/6/9 n'ont pas de base reproductible) : cette garde
n'essaie donc PAS de faire baisser un compteur, elle ARRETE L'HEMORRAGIE.

Mecanique : ALLOWLIST nominative (chaque entree porte sa raison — pourquoi le
fichier n'est pas convertible sans un chantier separe, ou pourquoi il est un
lecteur de MARKUP legitime comme `solar.test.mjs`) des fichiers qui utilisent
encore le patron aujourd'hui. Tout NOUVEAU fichier de la meme famille qui
adopterait ce patron (readFileSync sur un module source + assertion regex sur
le texte lu) fait ROUGIR la garde. Aucun test existant n'est reecrit ici —
une conversion est une autre tache.

QJR427 - la liste blanche ne doit plus grossir en silence : toute entree
NOUVELLE (au-dela du socle gele `_BASELINE_ALLOWLIST_KEYS`) doit porter une
raison DATEE (AAAA-MM-JJ) et ATTRIBUEE (identifiant de tache ou "PR #NNN"),
verifie par `check_allowlist_reasons()` - sinon la garde rougit.

Usage :  python scripts/check_tests_source_regex.py
Sortie :  0 si propre, 1 sinon (fichiers fautifs listes).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOT = ROOT / "frontend" / "src"

# Un fichier est de la famille visee par QJR239 s'il est un test ET que son
# nom commence par l'un de ces prefixes (DevisGenerator*/solar*/autoQuote*).
TEST_SUFFIXES = (".test.mjs", ".test.jsx")
FAMILY_PREFIXES = ("DevisGenerator", "solar", "autoQuote")

# Le patron interdit : lire un module source via readFileSync PUIS asserter
# par regex (assert.match / .match(/.../)) sur le texte lu — par opposition a
# executer le code pur, ou a lire un fixture JSON (JSON.parse(readFileSync)
# sans assertion regex derriere n'est PAS ce patron).
RE_READFILESYNC = re.compile(r"\breadFileSync\s*\(")
RE_REGEX_ASSERT = re.compile(r"assert\.match\(|\.match\(\s*/")

# Allowlist NOMINATIVE — chaque entree porte sa raison (une ligne). Les 14
# tests ci-dessous datent du programme QJR108/QJR109 (createAutoQuote et
# DevisGenerator.jsx ne sont pas des modules purs importables sous
# `node --test` : dependance dispatch Redux reelle / composant React) et ne
# sont PAS reconvertis dans QJR239 — une conversion est une autre tache.
# `solar.test.mjs` est le seul cas different : lecteur de MARKUP legitime
# (noValidate/step="any"), explicitement exclu par l'enonce de QJR239.
ALLOWLIST: dict[str, str] = {
    "frontend/src/features/ventes/autoQuote.paliers.test.mjs":
        "QJR109 verifie : 2 epingles lisent le SOURCE (garde de peremption "
        "avant createDevis + message de bandeau) - createAutoQuote n'est "
        "pas importable sous node --test (dispatch Redux reel).",
    "frontend/src/features/ventes/autoQuote.facturesReelles.test.mjs":
        "Verrouille par lecture de SOURCE la sequence "
        "factures_mensuelles_reelles de createAutoQuote (meme patron que "
        "autoQuote.ordre.test.mjs) - createAutoQuote non importable sous "
        "node --test.",
    "frontend/src/features/ventes/autoQuote.ordre.test.mjs":
        "PVORD : createAutoQuote non importable sous node --test (import "
        "relatif vers store/ventesSlice) - la garde d'ordre des lignes lit "
        "le SOURCE d'autoQuote.js.",
    "frontend/src/features/ventes/autoQuote.Panneaux900.test.mjs":
        "U3-900/U3-MOTEUR : verrouille par lecture de SOURCE la suppression "
        "de estimerPanneaux et la souverainete de la taille explicite - "
        "meme contrainte node --test que autoQuote.ordre.test.mjs.",
    "frontend/src/features/ventes/autoQuote.test.mjs":
        "QJR245 - autoQuote.js importe ventesSlice/ventesApi (non importable "
        "sous node --test) - noticePalierKwc est EXECUTEE (extraite du "
        "fichier reel) ; seule la preuve de cablage LeadDevisPanel.jsx/"
        "DevisTab.jsx (composants React non importables) lit leur SOURCE.",
    "frontend/src/features/ventes/solar.test.mjs":
        "Lecteur de MARKUP legitime (noValidate/step=\"any\" des 5 ecrans "
        "de saisie) - explicitement exclu par l'enonce de QJR239, pas une "
        "regression a geler.",
    "frontend/src/pages/ventes/DevisGeneratorApplySiteProfileMode.test.mjs":
        "DevisGenerator.jsx (composant React) non importable pur sous "
        "node --test - verifie le cablage applySiteProfile/applyLead par "
        "lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorBuildDimensionnementAvec.test.mjs":
        "DevisGenerator.jsx non importable pur sous node --test - verifie "
        "buildDimensionnementAvec par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorCompositionSourceLocale.test.mjs":
        "DevisGenerator.jsx non importable pur sous node --test - verifie "
        "le repli composeLocalement par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorEstimationExemple.test.mjs":
        "DevisGenerator.jsx + CarteMetrique.jsx non importables purs sous "
        "node --test - verifie l'exemple d'estimation par lecture de "
        "SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorEtudeConsoReelle.test.mjs":
        "DevisGenerator.jsx non importable pur sous node --test - verifie "
        "le bloc etude conso reelle par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorOrdreLignes.test.mjs":
        "DevisGenerator.jsx + autoQuote.js + LigneTable.jsx non "
        "importables purs sous node --test - verifie le cablage ordre des "
        "lignes par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorPrixManuel.test.mjs":
        "DevisGenerator.jsx non importable pur sous node --test - verifie "
        "le flag prixManuel par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorPrixManuelEdit.test.mjs":
        "DevisGenerator.jsx non importable pur sous node --test - verifie "
        "l'edition prixManuel par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorProductibleSociete.test.mjs":
        "DevisGenerator.jsx non importable pur sous node --test - verifie "
        "le productible par societe par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorRoundTripEtude.test.mjs":
        "DevisGenerator.jsx non importable pur sous node --test - verifie "
        "le round-trip etude_params par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorReplyLocal.test.mjs":
        "QJR211 - DevisGenerator.jsx non importable pur sous node --test - "
        "verifie que compositionSourceLocale s'efface sur CHAQUE succes "
        "(agricole/indus-commercial/residentiel) par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorProvenanceDV3.test.mjs":
        "QJR213/DV3 - DevisGenerator.jsx non importable pur sous node --test "
        "- verifie que les 4 cartes du miroir local (et SEULEMENT elles) "
        "portent la pastille estimation locale, par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorOverrides.test.mjs":
        "QJR215 - DevisGenerator.jsx non importable pur sous node --test - "
        "verifie le round-trip lire/poser/regenerer du registre d'overrides "
        "et l'affichage verbatim d'un refus 400, par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorQuantiteManuelle.test.mjs":
        "QJR218 - DevisGenerator.jsx non importable pur sous node --test - "
        "verifie le round-trip quantite_manuelle (enregistrement + ?edit=), "
        "meme patron que prix_manuel, par lecture de SOURCE.",
    "frontend/src/pages/ventes/DevisGeneratorOffgrid.test.mjs":
        "OFFGRID PR #604 (2026-09-01) - DevisGenerator.jsx (~5000 lignes, "
        "wiring API/Redux/Radix) non importable pur sous node --test - "
        "verifie le controle Raccordement/hors reseau par lecture de "
        "SOURCE, meme contrainte que les autres verrous DevisGenerator*.",
}

# QJR427 - cette entree (n. 21 ci-dessus) avait ete ajoutee par le commit
# d'armement de la garde lui-meme (QJR303, commit 41bdda58) SANS date ni
# identifiant de tache dans sa raison - un ajout muet que la garde dont le
# propos est d'empecher la proliferation de ce patron n'a pas su detecter
# sur elle-meme. QJR427 documente cette entree (date + attribution
# ci-dessus) et FIGE le reste de l'allowlist telle quelle : les entrees
# historiques ne sont pas retro-datees (elles etaient necessaires et
# documentees a leur niveau d'alors, cf. commentaire du bloc ALLOWLIST).
# A partir de ce socle, toute entree NOUVELLE doit porter une raison DATEE
# (AAAA-MM-JJ) et ATTRIBUEE (identifiant de tache type QJR427/CRX41, ou
# "PR #NNN") - voir check_allowlist_reasons() plus bas.
_BASELINE_ALLOWLIST_KEYS: frozenset[str] = frozenset(ALLOWLIST.keys())

REASON_DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
REASON_ATTRIBUTION_RE = re.compile(r"\b[A-Z]{2,}[0-9]+\b|PR #\d+")


def uses_pattern(path: Path) -> bool:
    """Un fichier « utilise le patron » s'il lit un module source via
    readFileSync ET asserte par regex sur le texte lu (fixture JSON seule,
    sans assertion regex derriere, n'est PAS ce patron)."""
    try:
        src = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return False
    return bool(RE_READFILESYNC.search(src) and RE_REGEX_ASSERT.search(src))


def scan() -> list[str]:
    offenders: list[str] = []
    if not SCAN_ROOT.exists():
        return offenders
    for path in sorted(SCAN_ROOT.rglob("*")):
        if not path.is_file():
            continue
        name = path.name
        if not any(name.endswith(suf) for suf in TEST_SUFFIXES):
            continue
        if not name.startswith(FAMILY_PREFIXES):
            continue
        if not uses_pattern(path):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWLIST:
            continue
        offenders.append(
            f"{rel} - NOUVEAU test de la famille DevisGenerator*/solar*/"
            f"autoQuote* qui lit du code source (readFileSync) et asserte "
            f"par regex dessus (anti-patron gele par QJR239)")
    return offenders


def check_allowlist_reasons(allowlist: dict[str, str] | None = None) -> list[str]:
    """QJR427 - toute entree ALLOWLIST au-dela du socle gele
    `_BASELINE_ALLOWLIST_KEYS` doit porter une raison DATEE (AAAA-MM-JJ) et
    ATTRIBUEE (identifiant de tache type QJR427/CRX41, ou "PR #NNN") - sinon
    elle est un ajout MUET, exactement le mode de defaite que QJR303 a
    illustre (entree n. 21 ajoutee par le commit d'armement de cette garde,
    sans date ni tache dans sa raison, jamais mentionnee au DONE LOG)."""
    table = ALLOWLIST if allowlist is None else allowlist
    offenders: list[str] = []
    for rel, raison in table.items():
        if rel in _BASELINE_ALLOWLIST_KEYS:
            continue
        if not REASON_DATE_RE.search(raison) or not REASON_ATTRIBUTION_RE.search(raison):
            offenders.append(
                f"{rel} - entree ALLOWLIST ajoutee sans raison DATEE et "
                f"ATTRIBUEE (QJR427) : la raison doit citer une date "
                f"AAAA-MM-JJ et un identifiant de tache (ex. QJR427) ou "
                f"'PR #NNN'")
    return offenders


def main() -> int:
    offenders = scan()
    offenders += check_allowlist_reasons()
    if offenders:
        print("[check_tests_source_regex] ECHEC - nouveau test "
              "'regex sur code source' hors allowlist :")
        for line in offenders:
            print(f"  - {line}")
        print()
        print("  Ajouter le fichier a ALLOWLIST avec sa raison (une ligne) "
              "SEULEMENT si le patron est reellement incontournable (module "
              "non pur sous node --test) - sinon ecrire un vrai test qui "
              "EXECUTE le code. Toute entree NOUVELLE doit citer une date "
              "AAAA-MM-JJ et un identifiant de tache (ou 'PR #NNN') - QJR427.")
        return 1
    print(f"[check_tests_source_regex] OK - allowlist gelee a "
          f"{len(ALLOWLIST)} fichiers, aucun NOUVEAU test 'regex sur code "
          f"source' dans la famille DevisGenerator*/solar*/autoQuote*.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
