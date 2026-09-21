#!/usr/bin/env python3
"""SOLMVP37 — miroir SOURCE des 47 apps parquées vers ``backend/parked/<label>/``.

Objectif founder (« park, never delete ») : le code des apps sorties du MVP
solaire reste PHYSIQUEMENT visible dans le dépôt — comme ``frontend/parked/``
pour le frontend (SOLMVP40) — sans jamais entrer dans le PYTHONPATH, les
images Docker, les linters ou une garde CI.

Ce script lit la liste UNIQUE des 47 labels dans ``core.parked.APPS_PARQUEES``
(jamais recopiée ailleurs) et, pour chacun, extrait l'app ORIGINALE (avant
coquillage) depuis la branche/tag d'archive (``core.parked.ARCHIVE_REF`` par
défaut) vers ``backend/parked/<label>/`` — TOUT sauf ``migrations/`` (qui
reste, gelée et verbatim, sous
``backend/django_core/apps/<label>/migrations/`` : jamais dupliquée) et
``__pycache__`` (jamais suivi par git de toute façon, exclu par prudence).

``__init__.py``, ``apps.py`` et ``models.py`` SONT mirorés : ce sont les
versions ORIGINALES (avant coquillage), qui diffèrent des coquilles gardées
dans ``backend/django_core/apps/<label>/`` — il n'y a rien à fusionner, la
recette de retour (docs/parked-modules.md §5) remplace la coquille par ce
même fichier archivé.

Idempotent : chaque exécution VIDE puis réécrit ``backend/parked/<label>/``
depuis le tag, donc rejouer le script rafraîchit le miroir sans jamais
laisser de fichier périmé (une app retirée d'une future archive disparaît du
miroir au prochain run).

Usage :
    python scripts/parquer_miroir.py                  # les 47 labels
    python scripts/parquer_miroir.py --label frais     # un sous-ensemble
    python scripts/parquer_miroir.py --tag <autre-ref> # ancre différente

Stdlib uniquement (``subprocess`` pour ``git archive``, ``tarfile`` pour
l'extraction) — aucune dépendance externe, aucun besoin d'un ``tar`` système
(donc portable sur l'hôte Windows comme en CI Linux).
"""
from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DJANGO_APPS_PREFIX = "backend/django_core/apps"
PARKED_ROOT = REPO_ROOT / "backend" / "parked"

# Noms de segment de chemin jamais mirorés, où qu'ils apparaissent dans l'app
# archivée : la coquille garde `migrations/` verbatim (jamais dupliquée ici),
# et `__pycache__`/`*.pyc` ne sont de toute façon jamais suivis par git.
EXCLUDED_PARTS = {"migrations", "__pycache__"}


def _charger_registre():
    """Importe ``core.parked`` en pur Python, sans Django (comme les autres
    scripts hôte qui lisent APPS_PARQUEES hors contexte Django)."""
    django_core = str(REPO_ROOT / "backend" / "django_core")
    if django_core not in sys.path:
        sys.path.insert(0, django_core)
    import core.parked as parked  # noqa: PLC0415 — import tardif volontaire

    return parked


def _git_archive_bytes(tag: str, label: str) -> bytes:
    chemin = f"{DJANGO_APPS_PREFIX}/{label}"
    proc = subprocess.run(
        ["git", "archive", tag, "--", chemin],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        erreur = proc.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"git archive a échoué pour '{label}' : {erreur}")
    return proc.stdout


def _garder(reste: str) -> bool:
    composants = reste.split("/")
    if any(c in EXCLUDED_PARTS for c in composants):
        return False
    return not reste.endswith((".pyc", ".pyo"))


def _extraire_app(tag: str, label: str, dest: Path) -> int:
    """Extrait ``apps/<label>`` du tag vers ``dest``, hors migrations/pycache.

    Retourne le nombre de fichiers écrits.
    """
    data = _git_archive_bytes(tag, label)
    if not data:
        raise RuntimeError(
            f"archive vide pour '{label}' (label absent de {tag} ?)"
        )
    prefixe = f"{DJANGO_APPS_PREFIX}/{label}/"
    n_fichiers = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r") as tar:
        for membre in tar:
            if not membre.isfile():
                continue
            if not membre.name.startswith(prefixe):
                continue
            reste = membre.name[len(prefixe):]
            if not reste or not _garder(reste):
                continue
            cible = dest / reste
            cible.parent.mkdir(parents=True, exist_ok=True)
            extrait = tar.extractfile(membre)
            if extrait is None:
                continue
            with open(cible, "wb") as f:
                f.write(extrait.read())
            n_fichiers += 1
    return n_fichiers


def _vider(dest: Path) -> None:
    """Repart d'un dossier vide (idempotence : rafraîchit depuis le tag)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)


def miroir(tag: str, labels: list[str]) -> dict[str, int]:
    resultats: dict[str, int] = {}
    for label in labels:
        dest = PARKED_ROOT / label
        _vider(dest)
        n = _extraire_app(tag, label, dest)
        resultats[label] = n
        if n == 0:
            # Rien d'archivable hors migrations (ne devrait pas arriver pour
            # une vraie app applicative) : ne pas laisser un dossier vide.
            dest.rmdir()
    return resultats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag", default=None,
        help="Référence git de l'archive (défaut : core.parked.ARCHIVE_REF)",
    )
    parser.add_argument(
        "--label", action="append", default=None,
        help="Limiter le miroir à ce(s) label(s) (répétable ; défaut : les 47)",
    )
    args = parser.parse_args(argv)

    parked = _charger_registre()
    tag = args.tag or parked.ARCHIVE_REF
    labels = args.label or list(parked.APPS_PARQUEES)

    inconnus = [l for l in labels if l not in parked.APPS_PARQUEES_SET]
    if inconnus:
        print(
            f"parquer_miroir : label(s) absent(s) de APPS_PARQUEES : {inconnus}",
            file=sys.stderr,
        )
        return 1

    resultats = miroir(tag, labels)
    total = sum(resultats.values())
    print(
        f"parquer_miroir : {len(labels)} app(s), {total} fichier(s) "
        f"miroirés depuis {tag} vers {PARKED_ROOT.relative_to(REPO_ROOT)}/."
    )
    vides = [l for l, n in resultats.items() if n == 0]
    if vides:
        print(f"  (aucun fichier hors migrations pour : {', '.join(vides)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
