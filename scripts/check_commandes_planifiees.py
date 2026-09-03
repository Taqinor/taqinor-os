#!/usr/bin/env python3
"""AUD231 — garde CI : une commande de gestion qui SE DIT « cron / Celery beat »
doit être RÉELLEMENT planifiée.

POURQUOI CETTE GARDE EXISTE
---------------------------
Le mode de défaillance dominant du dépôt, mesuré deux fois : un balayage est
ÉCRIT, TESTÉ, documenté « Plannifiable par Celery beat » — et n'est ajouté à
AUCUN ``beat_schedule``. Il ne tourne donc jamais. WIR25 l'avait corrigé pour
deux commandes comptables/fiscales ; AUD231 a retrouvé HUIT autres cas, dont
``pos.liberer_reservations_expirees`` : une réservation Click & Collect expirée
n'était jamais libérée, son stock restant réservé indéfiniment, alors que
``apps/pos/models.py`` AFFIRMAIT le contraire en commentaire.

Le garde QX11 (``apps/ventes/tests/test_qx11_beat_reachability.py``) couvre la
moitié du problème : tout ``@shared_task`` doit être planifié ou explicitement
« à la demande ». Il est AVEUGLE à une commande de gestion qui n'a AUCUNE tâche
Celery — exactement les huit cas d'AUD231. Ce script couvre cette moitié-là,
sur TOUTES les apps (compta, contrats, ged, rh comprises), pas seulement
stock/POS.

CE QU'ELLE FAIT (analyse statique pure, sans base de données, sans Django)
-------------------------------------------------------------------------
1. Parcourt ``backend/django_core/apps/*/management/commands/*.py`` et lit la
   docstring de module + le ``help`` de la classe ``Command`` (AST, jamais
   d'import).
2. Une commande qui se DÉCLARE planifiable (motif ``cron`` / ``celery beat`` /
   ``planificateur`` / ``plannifiable``…) doit avoir une entrée de
   ``beat_schedule`` dont le nom de tâche est ``<app>.<nom_de_commande>``
   (la convention que l'ERP suit déjà : ``compta.generer_ecritures_recurrentes``,
   ``fiscal.rappels_fiscaux``, ``crm.recycler_leads_non_travailles``…).
3. Sinon, elle doit figurer dans ``scripts/commandes_planifiees_allow.txt``,
   la BASE DE RÉFÉRENCE — qui NE PEUT QUE RÉTRÉCIR : une entrée qui n'existe
   plus, ou qui est désormais planifiée, fait ÉCHOUER le script (elle doit être
   retirée), et une NOUVELLE commande non planifiée échoue tout court.

PRINCIPE ANTI-FAUX-POSITIF : la détection se fait sur ce que la commande DIT
d'elle-même. Une commande qui ne parle ni de cron ni de beat n'est jamais
examinée — c'est un outil manuel, et c'est légitime.

Usage :
    python scripts/check_commandes_planifiees.py
    python scripts/check_commandes_planifiees.py --write-baseline
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
BEAT_FILE = DJANGO_CORE / "erp_agentique" / "celery.py"
BASELINE_PATH = ROOT / "scripts" / "commandes_planifiees_allow.txt"

#: Ce qu'une commande dit d'elle-même quand elle se veut périodique.
PLANIFIABLE_RE = re.compile(
    r"celery\s*beat|\bbeat\b|\bcron\b|planificateur|plannifiable|planifiable",
    re.IGNORECASE,
)

BASELINE_HEADER = """\
# AUD231 — commandes de gestion qui se DÉCLARENT « cron / Celery beat » sans
# entrée correspondante dans `erp_agentique/celery.py` (convention de nom :
# `<app>.<nom_de_commande>`).
#
# CE FICHIER EST UNE DETTE, PAS UNE APPROBATION. Chaque ligne est un balayage
# qui NE TOURNE PAS aujourd'hui. La liste NE PEUT QUE RÉTRÉCIR : planifier la
# commande (tâche Celery + entrée beat + route `scheduled`) puis retirer sa
# ligne. Ajouter une ligne pour faire passer une NOUVELLE commande non
# planifiée est exactement ce que ce garde interdit.
#
# Format : <app>.<nom_de_commande>    # raison / renvoi
"""


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def taches_planifiees(source: str | None = None) -> set:
    """Noms de tâches présents dans le ``beat_schedule`` (lecture textuelle du
    fichier, comme le fait déjà le garde QX11 — aucun import de Django)."""
    if source is None:
        source = BEAT_FILE.read_text(encoding="utf-8")
    return set(re.findall(r"'task':\s*'([^']+)'", source))


def _help_de_commande(tree: ast.AST) -> str:
    """Valeur littérale de ``Command.help`` (concaténations incluses)."""
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "Command"):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            cibles = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            if "help" not in cibles:
                continue
            try:
                valeur = ast.literal_eval(stmt.value)
            except (ValueError, SyntaxError):
                return ""
            return valeur if isinstance(valeur, str) else ""
    return ""


def se_declare_planifiable(source: str) -> bool:
    """Vrai si la commande annonce elle-même être périodique (docstring de
    module ou ``Command.help``)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    texte = (ast.get_docstring(tree) or "") + "\n" + _help_de_commande(tree)
    return bool(PLANIFIABLE_RE.search(texte))


def _iter_commandes():
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        commands_dir = app_dir / "management" / "commands"
        if not commands_dir.is_dir():
            continue
        for path in sorted(commands_dir.glob("*.py")):
            if path.name == "__init__.py":
                continue
            yield app_dir.name, path.stem, path


def collecter_manquantes(planifiees: set):
    """``[(cle, chemin_relatif)]`` des commandes qui se déclarent planifiables
    sans entrée de beat correspondante, triées."""
    manquantes = []
    for app, nom, path in _iter_commandes():
        source = path.read_text(encoding="utf-8", errors="ignore")
        if not se_declare_planifiable(source):
            continue
        if f"{app}.{nom}" in planifiees:
            continue
        manquantes.append((f"{app}.{nom}", _rel(path)))
    return manquantes


def _lire_baseline():
    if not BASELINE_PATH.exists():
        return set()
    entrees = set()
    for ligne in BASELINE_PATH.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne:
            entrees.add(ligne)
    return entrees


def _ecrire_baseline(manquantes):
    lignes = [BASELINE_HEADER]
    for cle, rel in manquantes:
        lignes.append(f"{cle}    # {rel}")
    BASELINE_PATH.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args(argv)

    planifiees = taches_planifiees()
    manquantes = collecter_manquantes(planifiees)

    if args.write_baseline:
        _ecrire_baseline(manquantes)
        print(f"check_commandes_planifiees: base de reference regeneree "
              f"({len(manquantes)} entree(s)) -> {_rel(BASELINE_PATH)}")
        return 0

    baseline = _lire_baseline()
    cles_manquantes = {cle for cle, _rel in manquantes}

    nouvelles = sorted(cles_manquantes - baseline)
    perimees = sorted(baseline - cles_manquantes)

    print(f"check_commandes_planifiees: {len(cles_manquantes)} commande(s) "
          f"« cron/beat » non planifiee(s) ({len(baseline)} en base de "
          f"reference).")

    if nouvelles:
        print("\ncheck_commandes_planifiees: commande(s) qui se declarent "
              "planifiables SANS entree de beat :")
        for cle in nouvelles:
            print(f"  - {cle} : ajouter la tache Celery + l'entree "
                  f"beat_schedule '{cle}' + sa route 'scheduled'.")
    if perimees:
        print("\ncheck_commandes_planifiees: entree(s) de base de reference "
              "a RETIRER (commande disparue ou desormais planifiee) :")
        for cle in perimees:
            print(f"  - {cle}")

    if nouvelles or perimees:
        return 1
    print("check_commandes_planifiees: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
