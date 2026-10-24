#!/usr/bin/env python3
"""Garde statique des tables de parcours (AMET98, C-AMET-025, critère C15) — job stage-names.

Lit chaque ``backend/django_core/apps/<pilote>/parcours/PA*.json`` (METHODE §D.1), sans base
ni import de Django, et ÉCHOUE si :
  1. une étape PRÉSENTE n'a pas 1 déclencheur (objet ``type`` + ``source``), 1 fonction
     d'entrée ``fichier::symbole``, 1 checkpoint (objet avec ``persistance``) et ≥ 1 règle aval ;
  2. une référence ``fichier::symbole`` ne résout pas (``declencheur.source``,
     ``fonction_entree``, ``checkpoint.persistance``, ``source`` d'une règle aval) ;
  3. une table au schéma §D.1 (étapes à ``regle_aval``) ne passe pas EN ENTIER le contrôle de
     ``core/parcours.py`` (vocabulaires fermés, ``nom``, ``proprietaire``, checkpoint complet,
     ``portes[]`` non vide) ;
  4. une table déclare ``portes`` vide, ou deux étapes partagent un id.
Une étape ``manquante: true`` est RAPPORTÉE (``rejouer_parcours.py`` ne la joue jamais) ; ses
références présentes restent résolues.

Dialecte des gardes par pilote : les tables écrites avec ``libelle`` / ``regles_aval`` et les
types ``signal|tache|http|manuel`` (PA1, PA5, PA6, PA7 au 24/10/2026) passent la même règle
que leur garde ``apps/<pilote>/…test_parcours_pa<n>.py`` (points 1, 2 et 4) ; la sortie nomme
le schéma de chaque table. Résolution des symboles : la seule implémentation du dépôt,
``core/parcours.py`` (aucune seconde).

Usage : python scripts/check_parcours.py [--racine CHEMIN]   (exit 1 si une table échoue)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "django_core"))

from core import parcours as cp  # noqa: E402 — après sys.path (D-ENF22)

MOTIF = "backend/django_core/apps/*/parcours/PA*.json"


def tables(racine: Path = ROOT) -> list:
    return sorted(Path(racine).glob(MOTIF), key=lambda chemin: chemin.stem)


def regles_aval(etape: dict):
    """Règles aval d'une étape : ``regle_aval`` (§D.1) ou ``regles_aval`` (dialecte par pilote)."""
    return etape.get("regle_aval", etape.get("regles_aval"))


def _objet(valeur) -> dict:
    return valeur if isinstance(valeur, dict) else {}


def references(etape: dict) -> list:
    """[(champ, référence)] des symboles que l'étape nomme."""
    paires = [("declencheur.source", _objet(etape.get("declencheur")).get("source")),
              ("fonction_entree", etape.get("fonction_entree")),
              ("checkpoint.persistance", _objet(etape.get("checkpoint")).get("persistance"))]
    regles = regles_aval(etape)
    for n, regle in enumerate(regles if isinstance(regles, list) else [], 1):
        paires.append((f"règle aval {n}.source", _objet(regle).get("source")))
    return [(champ, ref) for champ, ref in paires if cp.est_une_reference(ref)]


def non_resolues(etape: dict, champs=None) -> list:
    ident = etape.get("id") or "?"
    return [f"{ident} : {champ} — {motif}" for champ, ref in references(etape)
            if (champs is None or champ not in champs)
            for ok, motif in [cp.resoudre_symbole(ref)] if not ok]


def problemes_essentiels(etape: dict) -> list:
    """Les 4 champs obligatoires d'une étape présente + ses références (dialecte indifférent)."""
    ident = etape.get("id") or "?"
    erreurs = []
    decl = etape.get("declencheur")
    if not isinstance(decl, dict) or not decl.get("type") or not decl.get("source"):
        erreurs.append(f"{ident} : déclencheur manquant (objet `type` + `source`)")
    elif decl["type"] != "manuel" and not cp.est_une_reference(decl["source"]):
        erreurs.append(f"{ident} : declencheur.source doit être `fichier::symbole`")
    if not cp.est_une_reference(etape.get("fonction_entree")):
        erreurs.append(f"{ident} : fonction d'entrée manquante (`fichier::symbole`)")
    if not _objet(etape.get("checkpoint")).get("persistance"):
        erreurs.append(f"{ident} : checkpoint manquant (objet avec `persistance`)")
    regles = regles_aval(etape)
    if not isinstance(regles, list) or not regles:
        erreurs.append(f"{ident} : au moins une règle aval (`regle_aval`)")
    return erreurs + non_resolues(etape)


def schema_d1(presentes: list) -> bool:
    return bool(presentes) and all("regle_aval" in e for e in presentes)


def problemes(table: dict) -> list:
    """Tous les manquements d'une table (liste vide = table valide)."""
    liste = cp.etapes(table)
    presentes = [e for e in liste if not e.get("manquante")]
    erreurs = [] if presentes else ["table sans étape présente"]
    ids = [e.get("id") for e in liste]
    erreurs += [f"{i} : identifiant en double" for i in sorted({i for i in ids if ids.count(i) > 1}, key=str)]
    if schema_d1(presentes):
        erreurs += cp.problemes_de_la_table(dict(table, etapes=presentes))
        deja = {"declencheur.source", "fonction_entree", "checkpoint.persistance"}
        erreurs += [m for e in presentes for m in non_resolues(e, deja)]
    else:
        erreurs += [m for e in presentes for m in problemes_essentiels(e)]
    erreurs += [m for e in liste if e.get("manquante") for m in non_resolues(e)]
    if "portes" in table and not table["portes"]:
        erreurs.append("`portes[]` déclaré vide : lister les entrées de création du parcours")
    return list(dict.fromkeys(erreurs))


def _ligne(chemin: Path, table: dict, racine: Path) -> str:
    liste = cp.etapes(table)
    manquantes = [e.get("id") or "?" for e in liste if e.get("manquante")]
    presentes = [e for e in liste if not e.get("manquante")]
    schema = "§D.1" if schema_d1(presentes) else "dialecte de la garde par pilote"
    detail = f" dont {len(manquantes)} manquante(s) rapportée(s) ({', '.join(manquantes)})" if manquantes else ""
    sans_portes = "" if "portes" in table else ", sans `portes[]`"
    return (f"{chemin.stem} ({chemin.relative_to(racine).as_posix()}) : {len(liste)} étape(s){detail}, "
            f"schéma {schema}{sans_portes}")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover — flux sans reconfigure (tests)
        pass
    ap = argparse.ArgumentParser(description="Garde statique des tables de parcours (AMET98).")
    ap.add_argument("--racine", default=str(ROOT), help="racine du dépôt (défaut : ce dépôt)")
    racine = Path(ap.parse_args(argv).racine)
    chemins = tables(racine)
    if not chemins:
        print(f"ÉCHEC — aucune table {MOTIF} sous {racine}")
        return 1
    echecs = 0
    for chemin in chemins:
        try:
            table = cp.charger_table(chemin)
        except (OSError, ValueError) as exc:
            echecs += 1
            print(f"{chemin.stem} : ÉCHEC — table illisible ({exc})")
            continue
        erreurs = problemes(table)
        print(_ligne(chemin, table, racine) + (" — OK" if not erreurs else f" — ÉCHEC ({len(erreurs)})"))
        for message in erreurs:
            print(f"  - {message}")
        echecs += bool(erreurs)
    if echecs:
        print(f"\nÉCHEC — {echecs} table(s) de parcours invalide(s) sur {len(chemins)} (METHODE §D.1).")
        return 1
    print(f"\nOK — {len(chemins)} table(s) de parcours : 1 déclencheur, 1 fonction d'entrée, "
          "1 checkpoint et ≥ 1 règle aval par étape, symboles résolus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
