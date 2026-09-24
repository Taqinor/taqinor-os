#!/usr/bin/env python3
"""GARDE CI (stage-names) — CALX385 : un échantillon de contrat a bien ses
DEUX moitiés.

CONSTAT (l'incident du 03/08/2026, en tête de `scripts/check_api_shapes.py`) :
un contrat qui ne vit QUE d'un côté (serveur ou client) peut diverger sans
qu'aucun diff de PR ne le montre — c'est exactement ce que PACT10 devait
fermer en committant les échantillons `apps/calepinage/contract_samples/*.json`
AVANT toute lane productrice. Mesuré ce jour : les 39 échantillons du module
sont TOUS cités par au moins un fichier de `apps/calepinage/**` (moitié
serveur), mais 6 ne sont cités par AUCUN fichier de `frontend/src/**` ni
`apps/web/src/**` (moitié cliente) — `check_api_shapes.py` s'abstient
sciemment de cette question par principe anti-faux-positif (son en-tête :
« un doute ne rougit JAMAIS »), donc un contrat à moitié morte peut vivre
indéfiniment sans qu'aucune garde ne le remarque.

CE QUE CETTE GARDE FAIT. Pour chaque `contract_samples/*.json`, exige une
citation littérale de son NOM DE FICHIER (ex. `calepinage_resultat.json`) —
dans un fichier de `apps/calepinage/**` (hors le dossier `contract_samples/`
lui-même, qui ne se cite jamais) ET dans un fichier de `frontend/src/**` ou
`apps/web/src/**`. Passif figé dans
`scripts/contrats_calepinage_allow.txt`, UNE raison DATÉE par ligne, liste
qui ne peut que RÉTRÉCIR ; un échantillon NEUF n'a jamais droit au passif
(il doit naître avec ses deux moitiés, ou être documenté EXPLICITEMENT le
jour de sa création — jamais par accumulation silencieuse).

Usage
-----
    python scripts/check_contrats_calepinage_deux_moities.py
    python scripts/check_contrats_calepinage_deux_moities.py --write-baseline
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALEPINAGE_DIR = ROOT / "backend" / "django_core" / "apps" / "calepinage"
SAMPLES_DIR = CALEPINAGE_DIR / "contract_samples"
FRONTEND_ROOTS = (ROOT / "frontend" / "src", ROOT / "apps" / "web" / "src")
BASELINE_PATH = ROOT / "scripts" / "contrats_calepinage_allow.txt"

BACKEND_EXT = (".py",)
FRONTEND_EXT = (".js", ".jsx", ".mjs", ".ts", ".tsx")


def _texte_de(racine: Path, extensions: tuple, exclure: Path | None = None) -> str:
    if not racine.is_dir():
        return ""
    morceaux = []
    for chemin in racine.rglob("*"):
        if not chemin.is_file() or chemin.suffix not in extensions:
            continue
        if "node_modules" in chemin.parts:
            continue
        if exclure is not None:
            try:
                chemin.relative_to(exclure)
                continue  # sous `exclure` : jamais lu (ex. contract_samples lui-même)
            except ValueError:
                pass
        try:
            morceaux.append(chemin.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(morceaux)


def echantillons() -> list:
    if not SAMPLES_DIR.is_dir():
        return []
    return sorted(SAMPLES_DIR.glob("*.json"))


def analyse() -> dict:
    """{'sans_moitie_serveur': [...], 'sans_moitie_cliente': [...]} — noms de
    fichier (pas de chemin) des échantillons qui manquent une moitié."""
    texte_backend = _texte_de(CALEPINAGE_DIR, BACKEND_EXT, exclure=SAMPLES_DIR)
    texte_frontend = "\n".join(
        _texte_de(racine, FRONTEND_EXT) for racine in FRONTEND_ROOTS
    )

    sans_serveur, sans_cliente = [], []
    for sample in echantillons():
        nom = sample.name
        if nom not in texte_backend:
            sans_serveur.append(nom)
        if nom not in texte_frontend:
            sans_cliente.append(nom)
    return {"sans_moitie_serveur": sans_serveur, "sans_moitie_cliente": sans_cliente}


# ===========================================================================
# Base de reference — UNIQUEMENT la moitié cliente (la moitié serveur est
# TOUJOURS enforcee sans passif : un contrat committé sans AUCUN consommateur
# backend n'a jamais existé sur ce dépôt et ne devrait jamais y naître).
# ===========================================================================

ENTETE_BASE = """\
# Base de reference de check_contrats_calepinage_deux_moities.py — DETTE
# HISTORIQUE, RIEN D'AUTRE (CALX385).
#
# Chaque ligne est le nom d'un `contract_samples/*.json` du module calepinage
# qu'AUCUN fichier de frontend/src/** ni apps/web/src/** ne cite par son nom
# de fichier — la moitié CLIENTE du contrat n'existe pas (encore, ou jamais).
# Cette liste gele l'etat du jour : la garde empeche la RECIDIVE (un
# echantillon NEUF n'a jamais droit au passif), elle ne repare pas le passif
# — chaque ligne drainee est un echantillon qui a enfin gagne sa moitie
# cliente, ou ete retire du depot.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - citer l'echantillon cote client puis `python
#     scripts/check_contrats_calepinage_deux_moities.py --write-baseline`
#     retire sa ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Ajouter une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur, visible en revue.
#
# Format : `<nom_de_fichier.json>  # <raison datee>`.
"""

_LIGNE_BASE = re.compile(r"^(?P<nom>\S+\.json)\s*(?:#.*)?$")


def charger_base(path: Path | None = None) -> set:
    path = path or BASELINE_PATH
    if not path.is_file():
        return set()
    base = set()
    for ligne in path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        m = _LIGNE_BASE.match(ligne)
        if m:
            base.add(m.group("nom"))
    return base


def ecrire_base(noms: set, path: Path | None = None):
    path = path or BASELINE_PATH
    corps = "\n".join(
        f"{nom}  # sans moitié cliente au 23/09/2026 (CALX385)" for nom in sorted(noms)
    )
    path.write_text(
        ENTETE_BASE + (corps + "\n" if corps else ""),
        encoding="utf-8", newline="\n",
    )


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Garde « contrat calepinage à une seule moitié » (CALX385).")
    parser.add_argument(
        "--write-baseline", action="store_true",
        help="retire de la base les échantillons désormais cités côté client",
    )
    parser.add_argument(
        "--autoriser-croissance", action="store_true",
        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes",
    )
    args = parser.parse_args(argv)

    tous = echantillons()
    if not tous:
        print("\nECHEC : aucun échantillon trouvé dans "
              "apps/calepinage/contract_samples/. Soit le chemin analysé a "
              "bougé, soit la lecture a cessé de fonctionner — dans les deux "
              "cas la garde a cessé de garder.")
        return 1

    resultat = analyse()
    echec = False

    # La moitié SERVEUR n'a JAMAIS de passif : un contrat committé sans
    # aucune trace côté backend serait un échantillon jamais raccroché à sa
    # vue — la faute inverse de PACT10, qui mérite un rouge immédiat.
    if resultat["sans_moitie_serveur"]:
        echec = True
        print("\nECHEC : échantillon(s) SANS AUCUNE citation dans "
              "apps/calepinage/** (moitié serveur manquante) :")
        for nom in resultat["sans_moitie_serveur"]:
            print(f"  {nom}")

    base = charger_base()
    sans_cliente = set(resultat["sans_moitie_cliente"])

    if args.write_baseline:
        ajouts = sans_cliente - base
        amorce = not BASELINE_PATH.is_file()
        if ajouts and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            print(f"{len(ajouts)} nouvelle(s) dette(s) voudraient y entrer :")
            for nom in sorted(ajouts)[:20]:
                print(f"  + {nom}")
            print("Citez l'échantillon côté client, ou assumez la dette avec "
                  "--autoriser-croissance.")
            return 1
        ecrire_base(sans_cliente)
        print(f"Base de reference reecrite : {BASELINE_PATH} "
              f"({len(sans_cliente)} entree(s), "
              f"{len(base - sans_cliente)} retiree(s)).")
        return 0 if not echec else 1

    nouveaux = sans_cliente - base
    corriges = base - sans_cliente

    if nouveaux:
        echec = True
        print(f"\nECHEC : {len(nouveaux)} échantillon(s) SANS moitié cliente "
              f"(hors base de référence) :")
        for nom in sorted(nouveaux):
            print(f"  {nom}")
        print("\nQUE FAIRE :")
        print("  - citez le nom du fichier depuis un écran/test frontend qui "
              "consomme réellement ce contrat ;")
        print("  - ou, dette assumee a drainer plus tard, "
              "`--write-baseline --autoriser-croissance` (fondateur).")

    if corriges:
        # Une ligne de passif devenue inutile ROUGIT — cette garde existe
        # précisément pour qu'un contrat à moitié morte ne vive JAMAIS en
        # silence, y compris dans sa propre base de dette : la laisser trainer
        # une fois corrigée rendrait la base menteuse (« encore sans moitié
        # cliente ») pour un échantillon qui en a désormais une.
        echec = True
        print(f"\nECHEC : {len(corriges)} ligne(s) de passif DEVENUE(S) "
              f"INUTILE(S) (l'échantillon a gagné sa moitié cliente) — "
              f"à retirer :")
        for nom in sorted(corriges):
            print(f"  {nom}")
        print("Retirez la ligne : "
              "python scripts/check_contrats_calepinage_deux_moities.py --write-baseline")

    if echec:
        return 1

    print(f"OK : {len(tous)} échantillon(s) lu(s), tous cités côté serveur, "
          f"aucun échantillon sans moitié cliente hors base à jour "
          f"({len(base)} dette(s) historique(s) gelée(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
