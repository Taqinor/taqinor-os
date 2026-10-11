#!/usr/bin/env python3
"""Cle de cache testdb (WOW8) d'un arbre git, calculee comme `hashFiles` de GitHub Actions.

Pourquoi (11/10/2026) : sur une PR, `actions/cache/restore` cherche d'abord les
dumps de la PR elle-meme (sa propre portee), et seulement ensuite ceux de main.
Un vieux dump de la PR (sauve avant qu'une migration ait ete editee en place sur
main) etait donc prefere au dump FRAIS de main : le garde `ci_testdb_manifest_diff`
le refusait a bon droit, et chaque run repayait la reconstruction a froid (~70 min),
que le push suivant annulait avant la sauvegarde. Remede : donner a `restore-keys`
la cle EXACTE de main en premier — elle vit dans la portee de main, lisible par
toute PR, et ne porte que des migrations deja fusionnees : le delta se reduit aux
migrations propres a la PR.

Algorithme = celui du runner (actions/runner, hashFiles.ts) : pour chaque fichier
retenu, dans l'ordre de parcours, sha256 du contenu ; la cle = sha256 de la
concatenation des empreintes brutes. Les motifs sont ceux de ci.yml :
`backend/django_core/**/migrations/*.py` puis `backend/django_core/requirements.txt`.
Verifie sur deux cles reelles imprimees par la CI (voir le test).

Usage : python scripts/ci_testdb_main_key.py [<tree-ish>]   (defaut : origin/main)
Imprime `testdb-v1-<hex>` sur stdout.
"""
from __future__ import annotations

import hashlib
import io
import re
import subprocess
import sys

PREFIXE = "testdb-v1-"
RACINE = "backend/django_core/"
MOTIF_MIGRATION = re.compile(r"^backend/django_core/(?:.+/)?migrations/[^/]+\.py$")
REQUIREMENTS = "backend/django_core/requirements.txt"


def _git(*args: str, entree: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True, input=entree).stdout


def _entrees(tree: str) -> list[tuple[str, str]]:
    """(chemin, blob) retenus par les deux motifs de ci.yml, dans l'ordre du runner."""
    lignes = _git("ls-tree", "-r", tree, "--", RACINE).decode("utf-8").splitlines()
    blobs: dict[str, str] = {}
    for ligne in lignes:
        meta, chemin = ligne.split("\t", 1)
        blobs[chemin] = meta.split()[2]
    migrations = sorted(c for c in blobs if MOTIF_MIGRATION.match(c))
    requirements = [c for c in blobs if c == REQUIREMENTS]
    return [(c, blobs[c]) for c in migrations + requirements]


def fichiers_retenus(tree: str) -> list[str]:
    return [c for c, _ in _entrees(tree)]


def cle_testdb(tree: str = "origin/main") -> str:
    """Cle `testdb-v1-<sha256>` de l'arbre `tree`, identique a hashFiles() en CI."""
    entrees = _entrees(tree)
    # Un seul processus git : les blobs sont lus en flux (`cat-file --batch`).
    demande = "".join(blob + "\n" for _, blob in entrees).encode("ascii")
    flux = io.BytesIO(_git("cat-file", "--batch", entree=demande))
    total = hashlib.sha256()
    for _, blob in entrees:
        entete = flux.readline().split()
        if len(entete) != 3 or entete[0].decode() != blob:
            raise RuntimeError(f"blob inattendu dans le flux git : {entete!r}")
        contenu = flux.read(int(entete[2]))
        flux.read(1)  # le saut de ligne qui suit chaque objet
        total.update(hashlib.sha256(contenu).digest())
    return PREFIXE + total.hexdigest()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    print(cle_testdb(args[0] if args else "origin/main"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
