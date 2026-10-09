"""Aide commune des gardes à passif gelé qui ne peut que RÉTRÉCIR (cliquet).

Format du fichier de base : une clé par ligne, ``clé  # raison`` ; les lignes
vides et ``#`` sont ignorées. Utilisé par les gardes de la lane « gardes de
classe » (ACAL322, ACAL343, ACAL348, ACAL341, AFAC94, ACAL337, ...).
"""
from __future__ import annotations

from pathlib import Path


def charger(path: Path) -> set:
    if not path.is_file():
        return set()
    out = set()
    for ligne in path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne:
            out.add(ligne.split()[0] if " " in ligne else ligne)
    return out


def ecrire(path: Path, cles, entete: str, raison: str, *,
           autoriser_croissance: bool = False) -> None:
    """Réécrit la base. Refuse d'AJOUTER une clé (sauf amorçage = fichier absent
    ou ``autoriser_croissance``, réservé au fondateur)."""
    cles = set(cles)
    ajouts = cles - charger(path)
    if ajouts and path.is_file() and not autoriser_croissance:
        raise ValueError("la base ne peut que RETRECIR ; ajouts refusés : "
                         + ", ".join(sorted(ajouts)))
    corps = "".join(f"{c}  # {raison}\n" for c in sorted(cles))
    path.write_text(entete + corps, encoding="utf-8", newline="\n")


def comparer(trouves, base, *, nom_fichier: str, decrire) -> list:
    """Messages d'échec : clés NEUVES (``decrire(clé)``) et clés MORTES."""
    trouves = set(trouves)
    erreurs = [decrire(c) for c in sorted(trouves - base)]
    erreurs += [f"entrée MORTE de {nom_fichier} : {c} (n'est plus signalée — "
                "relancez --write-baseline)" for c in sorted(base - trouves)]
    return erreurs
