#!/usr/bin/env python3
"""APRF28 (C-APRF-028) — garde « tout export est borné ».

CLASSE GARDÉE. Un export XLSX/ZIP qui matérialise TOUT un queryset en
mémoire n'a pas de plafond : 3 137 lignes → 3,9 s / 17 Mo, 15 137 lignes →
20,5 s / 80 Mo, réponse 200 (ni 413 ni 202). ``records.storage.
should_async_export`` (NTPLT30) existe mais n'avait aucun appelant.

CE QUE LA GARDE FAIT. Toute FONCTION hors tests — vue OU service (les exports
stock passent par ``stock/services.export_*`` appelés depuis les vues) — qui
appelle ``build_xlsx_response(``, ``workbook_bytes(``, ``build_backup_zip(``
ou construit un ``openpyxl.Workbook(`` direct doit :

  · appeler ``should_async_export`` (directement, ou via un APPELANT qui le
    fait — un service borné par sa vue), ou
  · refuser une sélection d'ids vide (``if not ids: ...``),

sauf entrée de ``EXCEPTIONS`` : ``fichier::fonction`` -> (date ISO, raison).
Une exception sans date valide ou sans raison échoue ; une clé qui n'apparie
plus aucun site échoue (la liste ne peut que RÉTRÉCIR). Les corrections
appartiennent aux propriétaires des fichiers (jamais à cette garde).

DB-free, AST-only. Usage :
    python scripts/check_exports_bornes.py [--racine DIR] [--list]
"""
from __future__ import annotations

import ast
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DECLENCHEURS = {"build_xlsx_response", "workbook_bytes", "build_backup_zip"}
BORNE = "should_async_export"
RACINES = ("apps", "core", "authentication")

#: ``fichier::fonction`` -> (date ISO, raison motivée). Ne peut que rétrécir.
EXCEPTIONS: dict = {
    "backend/django_core/apps/crm/exports.py::export_clients_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de crm"),
    "backend/django_core/apps/crm/exports.py::export_defi_classement_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de crm"),
    "backend/django_core/apps/dataimport/export_views.py::sauvegarde": (
        "2026-10-09",
        "sauvegarde ZIP complète de la société, réservée à l'admin : à passer en asynchrone (job) par le propriétaire dataimport"),
    "backend/django_core/apps/dataimport/management/commands/export_company_data.py::Command.handle": (
        "2026-10-09",
        "commande de gestion lancée à la main, hors requête HTTP : aucun délai de requête ni mémoire de worker à protéger"),
    "backend/django_core/apps/entites/views.py::EntiteViewSet.export": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de entites"),
    "backend/django_core/apps/parametres/glossaire_export.py::construire_classeur": (
        "2026-10-09",
        "glossaire de paramètres : volume fixe borné par le code, indépendant des données de la société"),
    "backend/django_core/apps/records/xlsx.py::build_workbook": (
        "2026-10-09",
        "primitive générique de construction de classeur : la borne appartient à ses appelants (listés ici un par un)"),
    "backend/django_core/apps/reporting/archive.py::_xlsx_export": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/balance_export.py::balance_agee_export": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/insights.py::_maybe_xlsx": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/rapport_abonnements.py::rendre_abonnement": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/rapport_builder.py::RapportDefinitionViewSet.export": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/reports.py::_maybe_xlsx": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/reports_field.py::field_service_report": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/sav_pivot.py::sav_tickets_pivot": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/sav_sla.py::_maybe_xlsx": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/scheduled_reports.py::_rendre_legacy": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/scheduled_reports.py::_rendre_saved_query": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/technicien_scorecard.py::technicien_scorecard": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/reporting/views.py::dashboard": (
        "2026-10-09",
        "rapport/agrégat de reporting : borne par période NON vérifiée au build ; à borner ou justifier par le propriétaire reporting"),
    "backend/django_core/apps/sav/views.py::sav_fcr_insight": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de sav"),
    "backend/django_core/apps/sav/views.py::sav_performance_agent_insight": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de sav"),
    "backend/django_core/apps/stock/services.py::export_analyse_achats_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de stock"),
    "backend/django_core/apps/stock/services.py::export_inventaire_annuel_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de stock"),
    "backend/django_core/apps/stock/services.py::export_mouvements_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de stock"),
    "backend/django_core/apps/stock/services.py::export_prix_fournisseur_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de stock"),
    "backend/django_core/apps/stock/services.py::export_ras_tva_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de stock"),
    "backend/django_core/apps/stock/services.py::export_valorisation_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de stock"),
    "backend/django_core/apps/stock/views/fournisseur.py::FournisseurViewSet.export_conformite": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de stock"),
    "backend/django_core/apps/stock/views/mouvement.py::MouvementStockViewSet.agregation": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de stock"),
    "backend/django_core/apps/ventes/exports.py::export_comptable_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de ventes"),
    "backend/django_core/apps/ventes/exports.py::export_grand_livre_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de ventes"),
    "backend/django_core/apps/ventes/exports.py::export_journal_ventes": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de ventes"),
    "backend/django_core/authentication/views.py::CompanyViewSet.demo_kit_export_xlsx": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de authentication"),
    "backend/django_core/core/views.py::_conformite_xlsx_response": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de core"),
    "backend/django_core/core/views.py::_couts_xlsx_response": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de core"),
    "backend/django_core/core/views.py::_sla_export_xlsx_response": (
        "2026-10-09",
        "export sans plafond ni sélection d'ids constaté au build ; à borner (should_async_export) par le propriétaire de core"),
}


def _est_test(path: Path) -> bool:
    p = path.parts
    if any(x in ("tests", "migrations") for x in p):
        return True
    n = path.name
    return n.startswith(("test_", "tests_")) or n == "tests.py"


def _fichiers(racine: Path):
    base = racine / "backend" / "django_core"
    for r in RACINES:
        d = base / r
        if not d.is_dir():
            continue
        for path in sorted(d.rglob("*.py")):
            if not _est_test(path):
                yield path


def _nom(f):
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _declenche(call: ast.Call) -> bool:
    f = call.func
    n = _nom(f)
    if n in DECLENCHEURS:
        return True
    return n == "Workbook" and (
        isinstance(f, ast.Name)
        or (isinstance(f, ast.Attribute) and ast.unparse(f.value) == "openpyxl"))


def _refuse_ids_vides(fn) -> bool:
    for n in ast.walk(fn):
        if (isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not)
                and "ids" in ast.unparse(n.operand).lower()):
            return True
    return False


def _fonctions(tree):
    """[(qualname, FunctionDef)] — fonctions de plus haut niveau et méthodes."""
    out = []

    def visite(node, pile):
        for enfant in ast.iter_child_nodes(node):
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.append((".".join(pile + [enfant.name]), enfant))
                continue  # les fonctions imbriquées appartiennent à leur parent
            if isinstance(enfant, ast.ClassDef):
                visite(enfant, pile + [enfant.name])
            else:
                visite(enfant, pile)

    visite(tree, [])
    return out


def analyser(racine: Path):
    """-> ({cle: ligne} des exports non bornés, {cle: ligne} de tous)."""
    declencheurs, appels_borne, appelants = {}, set(), {}
    for path in _fichiers(racine):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(racine)).replace("\\", "/")
        for qual, fn in _fonctions(tree):
            cle = f"{rel}::{qual}"
            appelle = set()
            declenche = False
            for n in ast.walk(fn):
                if isinstance(n, ast.Call):
                    nom = _nom(n.func)
                    if nom:
                        appelle.add(nom)
                    if _declenche(n):
                        declenche = True
            if declenche:
                declencheurs[cle] = (fn.lineno, fn.name)
            if BORNE in appelle or _refuse_ids_vides(fn):
                appels_borne.add(fn.name)
                appels_borne.add(cle)
            for nom in appelle:
                appelants.setdefault(nom, set()).add((cle, fn.name))
    # fixpoint : une fonction est bornée si un APPELANT (par nom) l'est.
    bornes = {c for c in appels_borne if "::" in c}
    noms_bornes = {c for c in appels_borne if "::" not in c}
    change = True
    while change:
        change = False
        for nom, liste in appelants.items():
            if nom in noms_bornes:
                continue
            if any(c in bornes for c, _ in liste):
                noms_bornes.add(nom)
                change = True
        for cle in list(declencheurs):
            if cle not in bornes and declencheurs[cle][1] in noms_bornes:
                bornes.add(cle)
                change = True
    non_bornes = {c: l for c, (l, _n) in declencheurs.items() if c not in bornes}
    return non_bornes, {c: l for c, (l, _n) in declencheurs.items()}


def _date_valide(valeur) -> bool:
    try:
        datetime.date.fromisoformat(str(valeur))
        return True
    except ValueError:
        return False


def evaluer(racine: Path, exceptions: dict):
    non_bornes, _tous = analyser(racine)
    erreurs = []
    for cle, ligne in sorted(non_bornes.items()):
        if cle not in exceptions:
            erreurs.append(
                f"{cle} (ligne {ligne}) — export non borné : appeler "
                f"{BORNE}(...) ou refuser une sélection d'ids vide")
    for cle, valeur in sorted(exceptions.items()):
        try:
            date, raison = valeur
        except (TypeError, ValueError):
            erreurs.append(f"{cle} — exception mal formée (date, raison)")
            continue
        if not _date_valide(date):
            erreurs.append(f"{cle} — exception sans date ISO valide")
        if not str(raison).strip():
            erreurs.append(f"{cle} — exception sans raison")
        if cle not in non_bornes:
            erreurs.append(f"{cle} — exception morte (site borné ou disparu) "
                           ": la retirer")
    return erreurs, non_bornes


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    racine = ROOT
    if "--racine" in argv:
        racine = Path(argv[argv.index("--racine") + 1])
    # --racine : arbre de fixture, la liste d'exceptions du dépôt ne le vise pas.
    erreurs, non_bornes = evaluer(
        racine, EXCEPTIONS if racine == ROOT else {})
    if "--list" in argv:
        for cle, ligne in sorted(non_bornes.items()):
            print(f"{cle}  (ligne {ligne})")
        return 0
    if erreurs:
        print("check_exports_bornes : exports non bornés / exceptions "
              "invalides :")
        for e in erreurs:
            print(f"  - {e}")
        return 1
    print(f"check_exports_bornes : OK — {len(non_bornes)} export(s) listé(s) "
          "en exception datée, aucun nouveau non borné.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
