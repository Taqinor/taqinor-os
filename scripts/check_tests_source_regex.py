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

CRX41 - CLIQUET CRM : meme mecanique, seconde famille. `CRM_ALLOWLIST` gele
le STOCK actuel (50 fichiers) des tests `pages/crm`+`features/crm` qui
utilisent encore le patron regex-sur-source (aucune contrainte de prefixe de
nom, contrairement a `FAMILY_PREFIXES` cote ventes) ; `scan_crm()` interdit
tout NOUVEAU fichier du meme genre sous ces deux arbres. C'est un CLIQUET
SEUL : aucun des 50 fichiers geles n'est reecrit ici - la reecriture en
tests comportementaux (montage DOM) est CRXB7 (gated, hors de cette garde).

Usage :  python scripts/check_tests_source_regex.py
Sortie :  0 si propre, 1 sinon (fichiers fautifs listes).
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier` ou `fichier::symbole` (jamais un numero de ligne)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _cliquet  # noqa: E402 — après sys.path/setup() (D-ENF22)

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
# SPL42 — le lecteur unique du source du generateur (`DevisGeneratorSource.js`)
# est une lecture de source au meme titre que readFileSync.
RE_READFILESYNC = re.compile(r"\b(?:readFileSync|lireSourceGenerateur|lireSourceCoquille)\s*\(")
RE_REGEX_ASSERT = re.compile(r"assert\.match\(|\.match\(\s*/")

# Allowlist NOMINATIVE — chaque entree porte sa raison (une ligne). Les 14
# tests ci-dessous datent du programme QJR108/QJR109 (createAutoQuote et
# DevisGenerator.jsx ne sont pas des modules purs importables sous
# `node --test` : dependance dispatch Redux reelle / composant React) et ne
# sont PAS reconvertis dans QJR239 — une conversion est une autre tache.
# `solar.test.mjs` est le seul cas different : lecteur de MARKUP legitime
# (noValidate/step="any"), explicitement exclu par l'enonce de QJR239.
ALLOWLIST: dict[str, str] = {
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
    "frontend/src/pages/ventes/DevisGeneratorCartesValeurSignee.test.mjs":
        "QJR426 (2026-09-02) - meme contrainte que l'entree Offgrid : "
        "DevisGenerator.jsx non importable pur sous node --test ; verrouille "
        "que les 13 CarteMetrique passent la prop signee valeur= (DR5) par "
        "lecture de SOURCE, en attendant la conversion DOM (CRXB7-style).",
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

# ── CRX41 : cliquet CRM (seconde famille, meme mecanique) ───────────────────
# Contrairement a `SCAN_ROOT`/`FAMILY_PREFIXES` (portee : nom de fichier dans
# tout `frontend/src`), la portee CRM est par ARBRE : tout fichier de test
# sous `pages/crm` ou `features/crm`, quel que soit son nom. `CRM_ALLOWLIST`
# gele le STOCK actuel (50 fichiers, recense le 2026-09-02) qui utilise
# encore le patron readFileSync+regex - composants React (workspace lead,
# vues Kanban/Liste, popovers...) non importables purs sous `node --test`
# (wiring Redux/API/Router reel), meme contrainte que la famille
# DevisGenerator* ci-dessus. Aucun n'est reecrit ici : la reecriture en
# tests comportementaux (montage DOM) est CRXB7 (GATED - fondateur seul).
CRM_SCAN_ROOTS: tuple[Path, ...] = (
    ROOT / "frontend" / "src" / "pages" / "crm",
    ROOT / "frontend" / "src" / "features" / "crm",
)

_CRM_RAISON_GELEE = (
    "CRX41 (2026-09-02) - cliquet du STOCK CRM existant : composant React "
    "sous pages/crm ou features/crm non importable pur sous node --test "
    "(wiring Redux/API/Router reel) - verifie son cablage par lecture de "
    "SOURCE ; reecriture en montage DOM = CRXB7 (GATED), jamais ici."
)

CRM_ALLOWLIST: dict[str, str] = {
    "frontend/src/pages/crm/CrmIdentity.apx10.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/AppointmentBooker.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/ConvertirClientDialog.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/FilterBar.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadDevisPanel.wiring.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsBoardChrome.apx3.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsBoardColumns.apx4.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageBulkFloat.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageBulkFloatScrollbar.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageExpressMobile.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageKanbanEmptyStateWire.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageMarkPerdu.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageMemoStability.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageNoOverfetch.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPagePlanifierRelance.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageSelectionPruning.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageSkeletonShell.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageUrlFilters.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageVX147EmptyState.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/LeadsPageVX45Emojis.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/PerduPopover.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/PlanActiviteDialog.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/SigneDialog.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/ForecastView.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/KanbanActivityBar.apx6.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/KanbanViewCollapse.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/KanbanViewColumns.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/KanbanViewFocusRestore.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/LeadCardDensity.apx2.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/LeadCardMenu.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/LeadCardReadinessChips.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/LeadCardSelectionActive.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/LeadCardSwipeAction.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/LeadCardTouchAnatomy.apx7.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/LeadCardVX24.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/LeadCard.mry16.test.mjs":
        "MRY16 (2026-09-06) - LeadCard.jsx (composant React/JSX, imports "
        "Radix/router) non importable pur sous node --test, meme contrainte "
        "que les onze LeadCard*.test.mjs geles ; le test EXTRAIT les deux "
        "fonctions pures estAujourdhuiCasa/heureToucheFr du source et les "
        "EXECUTE (6 cas : nul/invalide, aujourd'hui = heure seule, autre "
        "jour = jour court + heure) - jamais une assertion regex sur le code.",
    "frontend/src/pages/crm/leads/views/ListViewCallReady.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/ListViewColumnChooser.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/ListViewDensity.apx5.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/ListViewGroupByStage.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/ListViewKeyboardRow.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/ListViewStageGuard.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/ListViewSticky.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/views/RenderCap.apx9.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/ViewSwitcherSegmented.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/VX95ForgivenessKanbanArchive.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/pages/crm/leads/WIR229_bulk_whatsapp.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/features/crm/workspace/devisAutoKwc.ez5.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/features/crm/workspace/DevisTabKwcPalier.test.mjs": _CRM_RAISON_GELEE,
    "frontend/src/features/crm/workspace/NoteComposerSize.test.mjs": _CRM_RAISON_GELEE,
}


def uses_pattern(path: Path) -> bool:
    """Un fichier « utilise le patron » s'il lit un module source via
    readFileSync ET asserte par regex sur le texte lu (fixture JSON seule,
    sans assertion regex derriere, n'est PAS ce patron)."""
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
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


def scan_crm() -> list[str]:
    """CRX41 - meme mecanique que `scan()`, portee par ARBRE (pages/crm,
    features/crm) plutot que par prefixe de nom : le STOCK actuel est gele
    dans `CRM_ALLOWLIST`, tout NOUVEAU fichier qui adopterait le patron
    readFileSync+regex sous ces deux arbres fait ROUGIR la garde."""
    offenders: list[str] = []
    for scan_root in CRM_SCAN_ROOTS:
        if not scan_root.exists():
            continue
        for path in sorted(scan_root.rglob("*")):
            if not path.is_file():
                continue
            name = path.name
            if not any(name.endswith(suf) for suf in TEST_SUFFIXES):
                continue
            if not uses_pattern(path):
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel in CRM_ALLOWLIST:
                continue
            offenders.append(
                f"{rel} - NOUVEAU test sous pages/crm ou features/crm qui "
                f"lit du code source (readFileSync) et asserte par regex "
                f"dessus (cliquet CRX41 - stock gele, reecriture = CRXB7)")
    return offenders


def check_allowlist_reasons(
    allowlist: dict[str, str] | None = None,
    *,
    baseline: "frozenset[str] | None" = None,
    label: str = "QJR427",
) -> list[str]:
    """QJR427 - toute entree ALLOWLIST au-dela du socle gele (`baseline`,
    par defaut `_BASELINE_ALLOWLIST_KEYS`) doit porter une raison DATEE
    (AAAA-MM-JJ) et ATTRIBUEE (identifiant de tache type QJR427/CRX41, ou
    "PR #NNN") - sinon elle est un ajout MUET, exactement le mode de
    defaite que QJR303 a illustre (entree n. 21 ajoutee par le commit
    d'armement de cette garde, sans date ni tache dans sa raison, jamais
    mentionnee au DONE LOG). CRX41 reutilise cette meme fonction pour
    `CRM_ALLOWLIST` avec `baseline=frozenset()` (socle neuf, aucune entree
    grand-pere : les 50 sont dejaa datees/attribuees des leur creation)."""
    table = ALLOWLIST if allowlist is None else allowlist
    base = _BASELINE_ALLOWLIST_KEYS if baseline is None else baseline
    offenders: list[str] = []
    for rel, raison in table.items():
        if rel in base:
            continue
        if not REASON_DATE_RE.search(raison) or not REASON_ATTRIBUTION_RE.search(raison):
            offenders.append(
                f"{rel} - entree ALLOWLIST ajoutee sans raison DATEE et "
                f"ATTRIBUEE ({label}) : la raison doit citer une date "
                f"AAAA-MM-JJ et un identifiant de tache (ex. {label}) ou "
                f"'PR #NNN'")
    return offenders


# ── ATST53 : cliquet de TOUT le depot (front + back) et des codes inventes ───
# Les deux familles ci-dessus ne voyaient que 66 des 197 tests front qui lisent
# un source ; le backend (276 tests, recompte du 11/11) et les codes de
# permission inventes (role `['tickets_gerer']` : le test prouve un 403 qui
# vient d'ailleurs - lecon n. 5 de docs/claude-memory/lecons-construction-qjr5.md)
# n'avaient aucune garde. Bases gelees qui ne font que RETRECIR (`_cliquet`).
TOUS_SUFFIXES_TEST = (".test.mjs", ".test.jsx", ".test.js", ".test.ts", ".test.tsx")
BASELINE_SOURCE = ROOT / "scripts" / "tests_source_regex_allow.txt"
BASELINE_CODES = ROOT / "scripts" / "tests_permissions_hors_registre_allow.txt"
ENTETE_SOURCE = (
    "# Base de check_tests_source_regex.py (ATST53) : tests qui lisent un source de\n"
    "# production et l'assertent par motif. `fichier` (front) ou `fichier::Classe.test`\n"
    "# (back). DETTE gelee : ne peut que RETRECIR (--write-baseline refuse d'ajouter).\n")
ENTETE_CODES = (
    "# Base de check_tests_source_regex.py (ATST53) : codes de `permissions=[...]` de\n"
    "# tests absents du registre (`fichier::fonction::code`). Ne peut que RETRECIR.\n")
RE_CHEMIN_SOURCE = re.compile(r"\.(?:py|jsx?|mjs)\b")
LECTURES_SOURCE = {"read_text", "read_bytes", "open", "getsource"}
ASSERTIONS_MOTIF = {"assertIn", "assertNotIn", "assertRegex", "assertNotRegex"}
RE_CODE_DYNAMIQUE = re.compile(r"^custom_object\.[\w-]+\.\w+$")  # customfields/views.py


def _back_root() -> Path:
    return ROOT / "backend" / "django_core"


def scan_tout_frontend() -> list[str]:
    """Tout test front (5 suffixes) qui lit un source et l'asserte par regex,
    hors des deux listes nominatives ci-dessus (cle = fichier)."""
    racine = ROOT / "frontend" / "src"
    connus = set(ALLOWLIST) | set(CRM_ALLOWLIST)
    trouves = []
    for path in sorted(racine.rglob("*.test.*")) if racine.exists() else ():
        if path.is_file() and path.name.endswith(TOUS_SUFFIXES_TEST) and uses_pattern(path):
            rel = path.relative_to(ROOT).as_posix()
            if rel not in connus:
                trouves.append(rel)
    return trouves


#: Pre-filtres TEXTUELS (sur-ensembles des criteres AST) : seuls les fichiers
#: candidats sont parses (~4 000 modules de test, ast.parse est le cout dominant).
_PRE_LECTURE = re.compile(r"getsource|read_text|read_bytes|open\(|ast\.parse")
_PRE_CHEMIN = re.compile(r"""['"][^'"\n]*\.(?:py|jsx?|mjs)\b""")
_PRE_ASSERT = re.compile(r"assert(?:Not)?(?:In|Regex)\(|re\.(?:search|findall|match)\(")
_PRE_PERMISSIONS = re.compile(r"permissions\s*=\s*[\[({]")


def _candidat_source(texte) -> bool:
    return bool(_PRE_LECTURE.search(texte) and _PRE_ASSERT.search(texte)
                and ("getsource" in texte or _PRE_CHEMIN.search(texte)))


def _fichiers_test_backend(candidat=lambda texte: True):
    racine = _back_root()
    for path in sorted(racine.rglob("*.py")) if racine.exists() else ():
        parts = path.relative_to(racine).parts
        if "migrations" in parts or "node_modules" in parts:
            continue
        if path.name.startswith("test") or "tests" in parts[:-1]:
            try:
                texte = path.read_text(encoding="utf-8")
                if candidat(texte):
                    yield path.relative_to(ROOT).as_posix(), ast.parse(texte)
            except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
                continue


def _cite_un_source(noeud) -> bool:
    return isinstance(noeud, ast.Constant) and isinstance(noeud.value, str) and bool(
        RE_CHEMIN_SOURCE.search(noeud.value))


def _noms_source(corps) -> set:
    """Noms (module ou classe) assignes a une expression qui cite un chemin source."""
    noms = set()
    for noeud in corps:
        if isinstance(noeud, ast.Assign) and any(_cite_un_source(c) for c in ast.walk(noeud.value)):
            noms.update(t.id for t in noeud.targets if isinstance(t, ast.Name))
    return noms


def _lit_et_asserte(fonction, noms_source) -> bool:
    appels = [n.func for n in ast.walk(fonction) if isinstance(n, ast.Call)]
    attrs = {f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "") for f in appels}

    def _de(module, noms):
        return any(isinstance(f, ast.Attribute) and f.attr in noms
                   and getattr(f.value, "id", "") == module for f in appels)
    if not (attrs & ASSERTIONS_MOTIF or _de("re", ("search", "findall", "match"))):
        return False
    if "getsource" in attrs:
        return True
    if not (attrs & LECTURES_SOURCE or _de("ast", ("parse",))):
        return False
    return any(_cite_un_source(n) or (isinstance(n, ast.Name) and n.id in noms_source)
               or (isinstance(n, ast.Attribute) and n.attr in noms_source) for n in ast.walk(fonction))


def _fonctions_test(arbre):
    """(qualname, noeud, noms source de la classe) des fonctions d'un module."""
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield noeud.name, noeud, set()
        elif isinstance(noeud, ast.ClassDef):
            noms_classe = _noms_source(noeud.body)
            for f in noeud.body:
                if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{noeud.name}.{f.name}", f, noms_classe


def scan_backend() -> list[str]:
    """Fonctions `test_*` qui lisent un source (.py/.js/.jsx/.mjs) puis l'assertent
    par motif (cle = `fichier::Classe.test`)."""
    trouves = []
    for rel, arbre in _fichiers_test_backend(_candidat_source):
        noms_module = _noms_source(arbre.body)
        for qualname, fonction, noms_classe in _fonctions_test(arbre):
            if fonction.name.startswith("test") and _lit_et_asserte(fonction, noms_module | noms_classe):
                trouves.append(f"{rel}::{qualname}")
    return trouves


def _registre_permissions():
    """(codes, motif `app_*_voir`) lus par AST du registre - sans importer Django."""
    chemin = _back_root() / "apps" / "roles" / "permissions_registre.py"
    codes, motif = set(), None
    try:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return codes, motif
    for noeud in arbre.body:
        cible = noeud.targets[0] if isinstance(noeud, ast.Assign) and len(noeud.targets) == 1 else None
        nom = getattr(cible, "id", "")
        if nom == "ALL_PERMISSIONS" or re.fullmatch(r"PORTAIL_\w+_PERMISSIONS", nom):
            codes.update(c.value for c in ast.walk(noeud.value)
                         if isinstance(c, ast.Constant) and isinstance(c.value, str))
        elif nom == "EST_PERMISSION_APP" and isinstance(noeud.value, ast.Call) and noeud.value.args:
            motif = re.compile(ast.literal_eval(noeud.value.args[0]))
    return codes, motif


def _codes_cites(fonction):
    """Codes litteraux des `permissions=[...]` d'une fonction."""
    for appel in (n for n in ast.walk(fonction) if isinstance(n, ast.Call)):
        for kw in appel.keywords:
            if kw.arg == "permissions" and isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
                yield from (el.value for el in kw.value.elts
                            if isinstance(el, ast.Constant) and isinstance(el.value, str))


def codes_hors_registre() -> list[str]:
    """`permissions=[...]` d'un test citant un code absent du registre
    (cle = `fichier::fonction::code`) ; `app_*_voir` et `custom_object.<x>.<y>` admis."""
    codes, motif = _registre_permissions()
    trouves = set()
    for rel, arbre in _fichiers_test_backend(_PRE_PERMISSIONS.search):
        for qualname, fonction, _noms in _fonctions_test(arbre):
            for code in _codes_cites(fonction):
                if code not in codes and not RE_CODE_DYNAMIQUE.match(code) and not (motif and motif.match(code)):
                    trouves.add(f"{rel}::{qualname}::{code}")
    return sorted(trouves)


def _ecrire_bases(sources, codes, autoriser_croissance) -> int:
    for chemin, cles in ((BASELINE_SOURCE, sources), (BASELINE_CODES, codes)):
        ajouts = set(cles) - _cliquet.charger(chemin)
        if ajouts and chemin.is_file() and not autoriser_croissance:
            print(f"REFUS : {chemin.name} ne peut que RETRECIR ; ajouts refusés : " + ", ".join(sorted(ajouts)))
            return 1
    for chemin, cles, entete in ((BASELINE_SOURCE, sources, ENTETE_SOURCE), (BASELINE_CODES, codes, ENTETE_CODES)):
        _cliquet.ecrire(chemin, cles, entete, "ATST53 stock gele", autoriser_croissance=True)
    print(f"Bases réécrites ({len(sources)} test(s) source, {len(codes)} code(s) hors registre).")
    return 0


def _cliquets_atst53(front, back, codes) -> list[str]:
    erreurs = _cliquet.comparer(
        front + back, _cliquet.charger(BASELINE_SOURCE), nom_fichier=BASELINE_SOURCE.name,
        decrire=lambda c: f"{c} - NOUVEAU test qui lit un source de production et l'asserte par "
                          f"motif (ATST53) : executez le code au lieu de lire son texte")
    return erreurs + _cliquet.comparer(
        codes, _cliquet.charger(BASELINE_CODES), nom_fichier=BASELINE_CODES.name,
        decrire=lambda c: f"{c} - code de permission absent du registre (ATST53) : un role "
                          f"invente prouve un refus qui vient d'ailleurs ; jouez un role livre")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — flux sans reconfigure (tests)
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--autoriser-croissance", action="store_true", help="fondateur seulement")
    args = ap.parse_args([] if argv is None else argv)
    front, back, codes = scan_tout_frontend(), scan_backend(), codes_hors_registre()
    if args.write_baseline:
        return _ecrire_bases(front + back, codes, args.autoriser_croissance)
    offenders = scan()
    offenders += scan_crm()
    offenders += check_allowlist_reasons()
    offenders += check_allowlist_reasons(
        CRM_ALLOWLIST, baseline=frozenset(), label="CRX41")
    offenders += _cliquets_atst53(front, back, codes)
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
          f"{len(ALLOWLIST)} fichiers (famille DevisGenerator*/solar*/"
          f"autoQuote*) + {len(CRM_ALLOWLIST)} fichiers (cliquet CRM CRX41, "
          f"pages/crm+features/crm) - aucun NOUVEAU test 'regex sur code "
          f"source' dans les deux perimetres.")
    print(f"[check_tests_source_regex] ATST53 - stock gele : {len(front)} test(s) front, "
          f"{len(back)} test(s) back, {len(codes)} code(s) de permission hors registre.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
