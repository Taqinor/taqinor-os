"""AMET98 (C-AMET-025) — validation statique de TOUTES les tables de parcours (module partagé).

Pas une garde de plus (C20 GARDE_NEUVE) : la garde d'acceptation l'exécute
(`python scripts/check_acceptation.py --parcours`, job stage-names) — un rejeu de parcours n'écrit
un enregistrement d'acceptation que sur une table valide — et `rejouer_parcours.py` refuse de jouer
une table invalide avec les MÊMES fonctions.

Lit chaque `backend/django_core/apps/<pilote>/parcours/PA*.json` (schéma METHODE §D.1) avec LE
résolveur du dépôt, `backend/django_core/core/parcours.py` (chargé par chemin, sans Django) —
aucune seconde implémentation :
  * table au schéma §D.1 (`nom`, `regle_aval`) : `parcours.problemes_de_la_table` tel quel —
    la même règle que les gardes par pilote (AMET8/10/11), exécutée une seconde fois, globalement ;
  * table au dialecte `libelle` / `regles_aval` (AMET13/15/18/24) : 1 déclencheur (`type` connu +
    1 référence `fichier::symbole`), 1 fonction d'entrée, 1 checkpoint (`persistance`), ≥ 1 règle
    aval `{regle, source}` ; une étape `manquante: true` porte `{"manquant": true}` en déclencheur
    et en entrée : rapportée, jamais résolue, jamais rejouée (`rejouer_parcours.py`) ;
  * dans les deux cas : CHAQUE référence de la table (portes, écrivains, tests nommés…) résout
    (`parcours.resoudre_symbole`), et `portes` est non vide.
Dette GELÉE `SANS_PORTES_GELEES` : tables arrivées sur main sans inventaire des portes ; elle ne
fait que rétrécir (une table listée qui gagne ses portes fait échouer la garde jusqu'à son retrait).
"""
from __future__ import annotations

import contextlib
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_ancres_taches as cat  # noqa: E402 — après sys.path/setup() (D-ENF22)

_SPEC = importlib.util.spec_from_file_location(
    "core_parcours", ROOT / "backend" / "django_core" / "core" / "parcours.py")
parcours = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(parcours)

MOTIF_TABLES = "backend/django_core/apps/*/parcours/PA*.json"
TYPES_DECLENCHEUR = set(parcours.TYPES_DECLENCHEUR) | {"http", "signal", "tache"}
TYPES_AUTO = {"evenement", "beat", "signal", "tache"}
# Dette gelée (26/10/2026, AMET98) : tables sans `portes` sur main ; ne fait que rétrécir.
SANS_PORTES_GELEES = {"PA5", "PA7"}
_RESOLUTION_CORE = re.compile(r"^\S+ : (?:declencheur\.source|fonction_entree|checkpoint\.persistance) — ")


def charger_tables(racine=ROOT) -> list:
    """[(rel, table)] triées ; une table illisible lève ValueError (ÉCHEC dans main)."""
    racine = Path(racine)
    return [(p.relative_to(racine).as_posix(), parcours.charger_table(p))
            for p in sorted(racine.glob(MOTIF_TABLES))]


def identifiant(table: dict) -> str:
    return str(table.get("parcours") or table.get("id") or "?")


def table_par_id(pa: str, racine=ROOT) -> tuple:
    for rel, table in charger_tables(racine):
        if identifiant(table) == pa:
            return rel, table
    raise SystemExit(f"table de parcours {pa} introuvable ({MOTIF_TABLES})")


def regles_aval(etape: dict) -> list:
    return etape.get("regle_aval", etape.get("regles_aval")) or []


def type_regle(regle) -> str:
    return regle if isinstance(regle, str) else str(regle.get("type") or "")


def est_manquante(etape: dict) -> bool:
    return etape.get("manquante") is True


def schema_d1(table: dict) -> bool:
    return any("regle_aval" in e or "nom" in e for e in parcours.etapes(table) if isinstance(e, dict))


def references(noeud):
    """Les chaînes `chemin/fichier[::symbole]` d'un nœud (lecteur de la garde PA3) ; un nom de
    fichier nu (`ecran.composant`: « DevisList.jsx ») est un libellé, pas une référence."""
    if isinstance(noeud, dict):
        for valeur in noeud.values():
            yield from references(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            yield from references(valeur)
    elif parcours.est_une_reference(noeud) and ("/" in noeud or "::" in noeud):
        yield noeud.strip()


def resoudre(ref: str, racine: Path) -> str:
    """'' si `ref` résout, sinon le motif : `core/parcours.resoudre_symbole`, puis l'index AST
    d'AMET80 (`check_ancres_taches.verifier_ancre`) pour les symboles imbriqués
    (`fonction._create`, `Classe.methode._interne`) que le premier ne descend pas."""
    ok, motif = parcours.resoudre_symbole(ref)
    fichier, _, symbole = ref.partition("::")
    if ok or not (symbole and fichier.endswith(".py")):
        return motif
    chemin = next((c for c in (fichier, f"backend/django_core/{fichier}") if (racine / c).is_file()), fichier)
    return motif if cat.verifier_ancre(chemin, symbole, racine) else ""


@contextlib.contextmanager
def _racine(racine: Path):
    """Le résolveur lit ses racines en globales : les pointer sur `racine` le temps d'un appel."""
    avant = parcours.RACINE_DEPOT, parcours.RACINE_DJANGO
    parcours.RACINE_DEPOT, parcours.RACINE_DJANGO = racine, racine / "backend" / "django_core"
    try:
        yield
    finally:
        parcours.RACINE_DEPOT, parcours.RACINE_DJANGO = avant


def _une_reference(valeur, quoi: str, err):
    if not parcours.est_une_reference(valeur):
        err(f"{quoi} : attendu 1 référence fichier::symbole ({valeur!r})")


def _problemes_dialecte(e: dict, err):
    """Étape au dialecte `libelle` / `regles_aval` : forme seulement (la résolution est globale)."""
    if est_manquante(e):
        for cle in ("declencheur", "fonction_entree"):
            if e.get(cle) != {"manquant": True}:
                err(f"{cle} d'une étape manquante : attendu {{\"manquant\": true}}")
    else:
        decl = e.get("declencheur")
        if not isinstance(decl, dict) or decl.get("type") not in TYPES_DECLENCHEUR:
            err(f"declencheur absent ou type hors de {sorted(TYPES_DECLENCHEUR)}")
        else:
            _une_reference(decl.get("source"), "declencheur.source", err)
        _une_reference(e.get("fonction_entree"), "fonction_entree", err)
    point = e.get("checkpoint")
    if not isinstance(point, dict) or not point.get("persistance"):
        err("checkpoint absent ou sans persistance")
    else:
        _une_reference(point["persistance"], "checkpoint.persistance", err)
    regles = e.get("regles_aval")
    if not isinstance(regles, list) or not regles:
        err("au moins une règle aval (regles_aval)")
    for r in regles if isinstance(regles, list) else []:
        if not (isinstance(r, dict) and str(r.get("regle") or "").strip()):
            err("règle aval sans texte `regle`")
        else:
            _une_reference(r.get("source"), "règle aval.source", err)


def verifier_table(rel: str, table: dict, racine=ROOT) -> tuple:
    """(échecs, ids d'étapes manquantes) d'une table."""
    pa, racine = identifiant(table), Path(racine)
    echecs = []
    with _racine(racine):
        if schema_d1(table):
            # Forme : core tel quel. Résolution : la boucle globale ci-dessous (même résolveur
            # d'abord, puis l'index AMET80 pour les symboles imbriqués) — jamais deux verdicts.
            echecs += [f"{pa} {p}" for p in parcours.problemes_de_la_table(table) if not _RESOLUTION_CORE.match(p)]
        else:
            liste, vus = parcours.etapes(table), set()
            if not liste:
                echecs.append(f"{pa} ({rel}) : aucune étape")
            for e in liste:
                ident = f"{pa} {e.get('id', '?') if isinstance(e, dict) else '?'}"
                if not isinstance(e, dict) or e.get("id") in vus:
                    echecs.append(f"{ident} : étape illisible ou identifiant en double")
                    continue
                vus.add(e.get("id"))
                _problemes_dialecte(e, lambda msg, ident=ident: echecs.append(f"{ident} : {msg}"))
            if not table.get("portes") and pa not in SANS_PORTES_GELEES:
                echecs.append(f"{pa} : `portes[]` vide : lister les entrées de création du parcours")
        if table.get("portes") and pa in SANS_PORTES_GELEES:
            echecs.append(f"{pa} : a désormais ses portes — retirez-la de SANS_PORTES_GELEES (dette gelée)")
        for ref in sorted(set(references(table))):
            if motif := resoudre(ref, racine):
                echecs.append(f"{pa} : {ref} — {motif}")
    return echecs, [str(e.get("id")) for e in parcours.etapes(table) if isinstance(e, dict) and est_manquante(e)]


def verifier_tout(racine=None) -> int:
    """Toutes les tables : 0 si vertes, 1 sinon (sortie française, une ligne par échec)."""
    racine = Path(racine or ROOT)
    try:
        tables = charger_tables(racine)
    except (OSError, ValueError) as exc:
        print(f"ÉCHEC : table de parcours illisible ({exc})")
        return 1
    echecs, nb = [], 0
    for rel, table in tables:
        res, manquantes = verifier_table(rel, table, racine)
        echecs, nb = echecs + res, nb + len(parcours.etapes(table))
        for m in manquantes:
            print(f"Étape manquante déclarée : {identifiant(table)} {m} (rapportée, jamais rejouée)")
    for e in echecs:
        print(f"ÉCHEC {e}")
    print(f"Tables de parcours : {len(tables)} table(s), {nb} étape(s), {len(echecs)} échec(s) ; "
          f"dette gelée sans portes : {', '.join(sorted(SANS_PORTES_GELEES)) or 'aucune'}.")
    return 1 if echecs or not tables else 0
