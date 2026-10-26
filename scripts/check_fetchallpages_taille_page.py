#!/usr/bin/env python3
"""APRF29 (C-APRF-030) — garde « toute lecture complète transmet sa taille de page ».

CLASSE GARDÉE. ``utils/fetchAllPages`` (APRF26) fournit à chaque appelant la taille
de page voulue (200 = ``max_page_size`` serveur, ``core/pagination.py``) dans le
second argument de ``fetchPage(page, { page_size })`` — mais c'est l'APPELANT qui la
met dans sa requête. Un appelant qui écrit ``api.getX({ page })`` l'ignore et le
serveur répond 50 par page : le Dashboard faisait 210 requêtes au lieu de 60
(banc V_VB).

CE QUE LA GARDE FAIT. Dans ``frontend/src`` (hors tests, commentaires masqués),
tout appel ``fetchAllPages(`` doit transmettre ``page_size`` à sa requête :
  · le texte de l'appel contient ``page_size`` (``{ page, page_size }``,
    ``page_size: 200``, ``(page, { page_size: pageSize })``), ou
  · son lambda prend un second paramètre nommé et le répand
    (``(page, o) => api({ page, ...o })``).
Sinon : exit 1 avec ``fichier:ligne``.

EXCEPTIONS. ``EXCEPTIONS`` : ``fichier`` -> (date ISO, raison, nombre d'appels
tolérés). Sans date valide, sans raison, ou si le fichier n'a plus autant d'appels
fautifs (liste périmée), la garde échoue : la liste ne peut que RÉTRÉCIR et un
NOUVEL appel non listé est rouge. Les corrections appartiennent aux propriétaires
des fichiers (jamais à cette garde).

Usage :
    python scripts/check_fetchallpages_taille_page.py [--racine DIR] [--list]
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONT = Path("frontend") / "src"
DEFINITION = "frontend/src/utils/fetchAllPages.js"
_EXT = {".js", ".jsx", ".mjs", ".ts", ".tsx"}
_RE_TEST = re.compile(r"(\.test\.|\.spec\.|/__tests__/|/test/|\.stories\.)")
_RE_SECOND = re.compile(r"\(\s*\w+\s*,\s*(\w+)\s*\)\s*=>")
_RE_PAGE_SIZE = re.compile(r"page_size")

#: ``fichier`` -> (date ISO, raison motivée, nombre d'appels tolérés). Ne peut que
#: rétrécir ; chaque entrée est à convertir par le propriétaire du fichier.
RAISON = (
    "appel hors du périmètre d'APRF25 (lecture à 50 par page) : à convertir vers "
    "`(page, { page_size: pageSize } = {})` par le propriétaire du fichier")
EXCEPTIONS: dict = {
    'frontend/src/features/adminops/ConfigPackagesPage.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adminops/SandboxPage.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/ActionsLogScreen.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/features/adsengine/AlertCenter.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/ApprovalsScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/BacklogScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/BrandKitScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/CampaignsScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/ConnectionScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/ConsentScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/CreativeLibraryScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/ExperimentsScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/FactTableScreen.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/features/adsengine/FlightPlanScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/ManualActionComposer.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/RulesScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/VeilleAnnonceurs.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/VeilleDecouverte.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/adsengine/VeilleScreen.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/crm/workspace/useEnvoiDevis.js': ('2026-10-26', RAISON, 1),
    'frontend/src/features/parametres/CustomObjectRecordsPage.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/features/parametres/useStatutConfig.js': ('2026-10-26', RAISON, 1),
    'frontend/src/features/uxviews/useServerSavedViews.js': ('2026-10-26', RAISON, 1),
    'frontend/src/features/ventes/quote/hooks/usePersistanceDevis.js': ('2026-10-26', RAISON, 2),
    'frontend/src/pages/admin/RolesManagement.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/pages/admin/UsersManagement.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/pages/crm/WebsiteLeadPayloadsPage.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/pages/parametres/toutesLesPages.js': ('2026-10-26', RAISON, 1),
    'frontend/src/pages/stock/BonsCommandeFournisseur.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/pages/stock/CategoriesStock.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/pages/stock/ConditionnementsProduit.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/pages/stock/FacturesFournisseur.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/pages/stock/FournisseurFiche360.jsx': ('2026-10-26', RAISON, 4),
    'frontend/src/pages/stock/FournisseursStock.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/pages/stock/InventairesAnnuels.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/pages/stock/LotsEntrepot.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/pages/stock/ModelesBcf.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/pages/stock/MouvementsPage.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/pages/stock/ProfilsSaisonniersSection.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/pages/stock/ReceptionsFournisseur.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/pages/stock/RetoursFournisseur.jsx': ('2026-10-26', RAISON, 1),
    'frontend/src/pages/stock/RevalorisationsStock.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/pages/tiers/TiersPage.jsx': ('2026-10-26', RAISON, 2),
    'frontend/src/pages/ventes/ListesPrixPage.jsx': ('2026-10-26', RAISON, 2),
}


def _masquer_commentaires(src: str) -> str:
    """Remplace les commentaires par des espaces (offsets/lignes conservés)."""
    sortie = list(src)
    i, n = 0, len(src)
    chaine = None
    while i < n:
        c = src[i]
        if chaine:
            if c == "\\":
                i += 2
                continue
            if c == chaine:
                chaine = None
        elif c in "'\"`":
            chaine = c
        elif src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                sortie[k] = " "
            i = j
            continue
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if src[k] != "\n":
                    sortie[k] = " "
            i = j
            continue
        i += 1
    return "".join(sortie)


def _appels(src: str):
    """[(ligne, texte de l'appel)] pour chaque ``fetchAllPages(``."""
    masque = _masquer_commentaires(src)
    out = []
    for m in re.finditer(r"\bfetchAllPages\s*\(", masque):
        profondeur, j = 0, m.end() - 1
        while j < len(masque):
            if masque[j] == "(":
                profondeur += 1
            elif masque[j] == ")":
                profondeur -= 1
                if profondeur == 0:
                    break
            j += 1
        out.append((masque.count("\n", 0, m.start()) + 1, masque[m.start():j + 1]))
    return out


def transmet_la_taille(appel: str) -> bool:
    """Vrai si l'appel met ``page_size`` dans sa requête (directement ou en
    répandant le second argument du lambda)."""
    if _RE_PAGE_SIZE.search(appel):
        return True
    second = _RE_SECOND.search(appel)
    return bool(second and re.search(r"\.\.\." + re.escape(second.group(1)) + r"\b", appel))


def _fichiers(racine: Path):
    base = racine / FRONT
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        if path.suffix not in _EXT or not path.is_file():
            continue
        rel = path.relative_to(racine).as_posix()
        if rel == DEFINITION or _RE_TEST.search("/" + rel):
            continue
        yield rel, path


def analyser(racine: Path):
    """-> {fichier: [ligne, ...]} des appels qui ne transmettent pas la taille."""
    fautifs = {}
    for rel, path in _fichiers(racine):
        try:
            src = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lignes = [ligne for ligne, appel in _appels(src) if not transmet_la_taille(appel)]
        if lignes:
            fautifs[rel] = lignes
    return fautifs


def _date_valide(valeur) -> bool:
    try:
        datetime.date.fromisoformat(str(valeur))
        return True
    except ValueError:
        return False


def evaluer(racine: Path, exceptions: dict):
    fautifs = analyser(racine)
    erreurs = []
    for rel, lignes in sorted(fautifs.items()):
        toleres = 0
        if rel in exceptions:
            try:
                toleres = int(exceptions[rel][2])
            except (TypeError, ValueError, IndexError):
                toleres = 0
        for ligne in lignes[toleres:]:
            erreurs.append(
                f"{rel}:{ligne} — fetchAllPages sans page_size : mettre "
                "`(page, { page_size: pageSize } = {})` puis `page_size: pageSize` "
                "dans la requête (200 par page au lieu de 50)")
    for rel, valeur in sorted(exceptions.items()):
        try:
            date, raison, nombre = valeur
        except (TypeError, ValueError):
            erreurs.append(f"{rel} — exception mal formée (date, raison, nombre)")
            continue
        if not _date_valide(date):
            erreurs.append(f"{rel} — exception sans date ISO valide")
        if not str(raison).strip():
            erreurs.append(f"{rel} — exception sans raison")
        if len(fautifs.get(rel, [])) < int(nombre):
            erreurs.append(
                f"{rel} — exception périmée ({len(fautifs.get(rel, []))} appel(s) "
                f"fautif(s) pour {nombre} toléré(s)) : la réduire ou la retirer")
    return erreurs, fautifs


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    racine, exceptions = ROOT, EXCEPTIONS
    if "--racine" in argv:
        # Arbre de fixtures : les exceptions du dépôt ne le concernent pas.
        racine, exceptions = Path(argv[argv.index("--racine") + 1]), {}
    erreurs, fautifs = evaluer(racine, exceptions)
    if "--list" in argv:
        for rel, lignes in sorted(fautifs.items()):
            print(f"{rel}: {lignes}")
        return 0
    if erreurs:
        print("check_fetchallpages_taille_page : ECHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_fetchallpages_taille_page : OK ({sum(map(len, fautifs.values()))} "
          "appel(s) en exception datée)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
