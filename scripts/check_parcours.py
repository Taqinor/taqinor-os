#!/usr/bin/env python3
"""AMET98 (C-AMET-025) — garde statique GLOBALE des tables de parcours (job stage-names).

Lit chaque `backend/django_core/apps/<pilote>/parcours/PA*.json` (METHODE v3 §D.1) et vérifie que
chaque étape a 1 déclencheur, 1 fonction d'entrée, 1 checkpoint, ≥ 1 règle aval, symboles résolus,
et que la table liste ses `portes[]`. Même règle que les gardes par pilote (AMET8/10/11/13/15/18/24),
exécutée une seconde fois globalement : une table neuve sans garde est vue ici.

Deux dialectes existent sur main, tous deux lus sans base ni import du code visé :
- canonique (PA2, PA3, PA4) : `regle_aval[]` typé — validé par `core/parcours.py` (seule implémentation) ;
- compact (PA1, PA5, PA6, PA7) : `regles_aval[{regle, source}]`, déclencheur signal|tache|http|manuel —
  mêmes exigences, symboles résolus par `core.parcours.resoudre_symbole`.
Une étape `"manquante": true` (déclencheur et entrée `{"manquant": true}`, `raison` et `attendu`
renseignés) est déclarée, pas une erreur : elle est comptée et `rejouer_parcours.py` ne la joue jamais.

PORTES_NON_DECLAREES : tables dont `portes[]` manque encore (dette gelée par id de table, jamais par
ligne) ; elle ne fait que rétrécir — une table qui gagne ses portes doit en sortir (cliquet).

Usage : python scripts/check_parcours.py [table.json …]   (exit 1 = ÉCHEC, sortie en français)
"""
from __future__ import annotations

import sys
from pathlib import Path

TYPE_DE_CLE = "par_symbole"  # dette clé = id de table (PA5…), jamais un numéro de ligne

ROOT = Path(__file__).resolve().parent.parent
DJANGO = ROOT / "backend" / "django_core"
sys.path.insert(0, str(DJANGO))
from core import parcours as P  # noqa: E402

TYPES_COMPACTS = frozenset({"signal", "tache", "http", "manuel"})
PORTES_NON_DECLAREES = {
    "PA5": "chantiers (apps/installations) — entrées de création du chantier à lister",
    "PA7": "sav — entrées de l'abonnement / du parc à lister",
}


def tables(racine: Path = DJANGO) -> list:
    return sorted((racine / "apps").glob("*/parcours/PA*.json"))


def est_manquante(etape: dict) -> bool:
    return etape.get("manquante") is True


def _ref(ident, quoi, valeur, erreurs):
    if not (isinstance(valeur, str) and P.est_une_reference(valeur)):
        erreurs.append(f"{ident} : {quoi} doit être `fichier::symbole` ({valeur!r})")
        return
    ok, motif = P.resoudre_symbole(valeur)
    if not ok:
        erreurs.append(f"{ident} : {quoi} — {motif}")


def problemes_etape_compacte(etape: dict) -> list:
    ident = etape.get("id") or "?"
    erreurs: list = []
    for champ in ("id", "declencheur", "fonction_entree", "checkpoint", "regles_aval"):
        if not etape.get(champ):
            erreurs.append(f"{ident} : champ `{champ}` manquant")
    dec, entree = etape.get("declencheur"), etape.get("fonction_entree")
    if est_manquante(etape):
        if dec != {"manquant": True} or entree != {"manquant": True}:
            erreurs.append(f"{ident} : étape manquante — déclencheur et entrée doivent valoir {{\"manquant\": true}}")
        for champ in ("raison", "attendu"):
            if not str(etape.get(champ) or "").strip():
                erreurs.append(f"{ident} : étape manquante sans `{champ}`")
    elif isinstance(dec, dict):
        if dec.get("type") not in TYPES_COMPACTS:
            erreurs.append(f"{ident} : declencheur.type hors de {sorted(TYPES_COMPACTS)}")
        _ref(ident, "declencheur.source", dec.get("source"), erreurs)
        _ref(ident, "fonction_entree", entree, erreurs)
    cp = etape.get("checkpoint")
    if isinstance(cp, dict):
        _ref(ident, "checkpoint.persistance", cp.get("persistance"), erreurs)
    elif cp:
        erreurs.append(f"{ident} : checkpoint doit être un objet")
    for regle in etape.get("regles_aval") or []:
        if not isinstance(regle, dict) or not str(regle.get("regle") or "").strip():
            erreurs.append(f"{ident} : règle aval sans texte `regle`")
            continue
        _ref(ident, "règle aval", regle.get("source"), erreurs)
    return erreurs


def problemes(table: dict) -> list:
    """Manquements d'une table, quel que soit son dialecte (liste vide = table valide)."""
    liste = P.etapes(table)
    if not any("regles_aval" in e for e in liste):
        return P.problemes_de_la_table(table)
    erreurs = [] if liste else ["table sans étape"]
    ids = [e.get("id") for e in liste]
    erreurs += [f"{i} : identifiant en double" for i in sorted({i for i in ids if ids.count(i) > 1}, key=str)]
    for etape in liste:
        erreurs += problemes_etape_compacte(etape)
    if not table.get("portes"):
        erreurs.append("`portes[]` vide : lister les entrées de création du parcours")
    return erreurs


def verifier(chemins) -> tuple:
    """(lignes de sortie, nombre de tables en échec)."""
    lignes, echecs = [], 0
    for chemin in chemins:
        table = P.charger_table(chemin)
        pa = table.get("parcours") or table.get("id") or chemin.stem
        erreurs = problemes(table)
        sans_portes = [e for e in erreurs if e.startswith("`portes[]` vide")]
        dette = pa in PORTES_NON_DECLAREES
        if dette and not sans_portes:
            erreurs.append(f"{pa} a maintenant ses portes : le retirer de PORTES_NON_DECLAREES (cliquet)")
        elif dette:
            erreurs = [e for e in erreurs if e not in sans_portes]
        liste = P.etapes(table)
        manq = sum(1 for e in liste if est_manquante(e))
        note = f" ; portes[] en dette : {PORTES_NON_DECLAREES[pa]}" if dette and sans_portes else ""
        lignes.append(f"{'ÉCHEC' if erreurs else 'OK':5} {pa} ({chemin.name}) — "
                      f"{len(liste)} étapes dont {manq} manquante(s){note}")
        lignes += [f"      - {e}" for e in erreurs]
        echecs += bool(erreurs)
    return lignes, echecs


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    chemins = [Path(a).resolve() for a in (sys.argv[1:] if argv is None else argv)] or tables()
    if not chemins:
        print("check_parcours : ÉCHEC — aucune table apps/*/parcours/PA*.json trouvée")
        return 1
    lignes, echecs = verifier(chemins)
    print(f"check_parcours : {len(chemins)} table(s) de parcours")
    print("\n".join(lignes))
    print(f"check_parcours : {'ÉCHEC' if echecs else 'OK'} — {echecs} table(s) en échec sur {len(chemins)}")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
