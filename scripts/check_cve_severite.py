#!/usr/bin/env python3
"""ENF12 — garde CVE BLOQUANTE des dépendances backend (rapport pip-audit).

``pip-audit`` ne donne PAS la sévérité d'une vulnérabilité. Ce script lit son
rapport JSON (``pip-audit -f json``), demande la sévérité de chaque
vulnérabilité à OSV (``https://api.osv.dev/v1/vulns/<id>``, champ
``database_specific.severity`` des avis GHSA : LOW / MODERATE / HIGH /
CRITICAL) et rend 1 dès qu'une vulnérabilité HIGH ou CRITICAL est présente.

Seuil (règle fondateur du 09/10/2026, docs/claude-memory/enforce-all-checks.md)
: HIGH et CRITICAL bloquent ; LOW / MODERATE sont listées sans bloquer.
FERMÉ PAR DÉFAUT : une sévérité introuvable (avis sans GHSA, OSV injoignable)
compte comme bloquante — jamais un « vert » faute d'information.

Usage : python scripts/check_cve_severite.py pip-audit.json
"""
from __future__ import annotations

import json
import sys
import urllib.request

BLOQUANTES = {"HIGH", "CRITICAL"}
OSV = "https://api.osv.dev/v1/vulns/"


def vulnerabilites(rapport: dict) -> list[tuple[str, str, str, list[str], list[str]]]:
    """(paquet, version, id, alias, versions correctives) — dédoublonné."""
    vues = set()
    sortie = []
    for dep in rapport.get("dependencies", []):
        for v in dep.get("vulns", []) or []:
            cle = (dep.get("name"), v.get("id"))
            if cle in vues:
                continue
            vues.add(cle)
            sortie.append((dep.get("name", "?"), dep.get("version", "?"), v.get("id", "?"),
                           list(v.get("aliases") or []), list(v.get("fix_versions") or [])))
    return sortie


def identifiant_ghsa(vid: str, alias: list[str]) -> str | None:
    for i in [vid] + alias:
        if i.startswith("GHSA-"):
            return i
    return None


def severite_osv(ghsa: str, lire=None) -> str | None:
    """Sévérité GHSA via OSV (None si introuvable)."""
    lire = lire or (lambda url: json.load(urllib.request.urlopen(url, timeout=30)))
    try:
        avis = lire(OSV + ghsa)
    except (OSError, ValueError):  # injoignable / illisible = sévérité inconnue (bloquante)
        return None
    sev = (avis.get("database_specific") or {}).get("severity")
    return str(sev).upper() if sev else None


def evaluer(rapport: dict, lire=None) -> tuple[list[str], list[str]]:
    """(lignes bloquantes, lignes informatives)."""
    bloquantes, infos = [], []
    for nom, version, vid, alias, correctifs in vulnerabilites(rapport):
        ghsa = identifiant_ghsa(vid, alias)
        sev = severite_osv(ghsa, lire) if ghsa else None
        ligne = (f"{nom} {version} {vid} ({ghsa or 'sans GHSA'}) "
                 f"sévérité={sev or 'INCONNUE'} corrigé en {', '.join(correctifs) or '?'}")
        if sev is None or sev in BLOQUANTES:
            bloquantes.append(ligne)
        else:
            infos.append(ligne)
    return bloquantes, infos


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        rapport = json.load(fh)
    bloquantes, infos = evaluer(rapport)
    for ligne in infos:
        print("INFO   " + ligne)
    for ligne in bloquantes:
        print("ECHEC  " + ligne)
    if bloquantes:
        print(f"{len(bloquantes)} vulnérabilité(s) HIGH/CRITICAL (ou de sévérité inconnue) : "
              "montez la dépendance à une version corrigée.")
        return 1
    print(f"OK — aucune vulnérabilité HIGH/CRITICAL ({len(infos)} de sévérité inférieure).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
