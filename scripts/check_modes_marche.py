#!/usr/bin/env python3
"""QJR231 — UNE énumération des modes de marché, et une garde de parité.

LE DÉFAUT QUE CETTE GARDE FERME
--------------------------------
Au moins SIX énumérations indépendantes des quatre marchés (résidentiel /
industriel / commercial / agricole) coexistent dans le dépôt, sans aucune
garde qui les compare :

  * réducteur          — `frontend/src/features/ventes/quote/sizingReducer.js`
                          (`export const MODES = [...]`) ;
  * panneaux            — `frontend/src/pages/ventes/DevisGenerator.jsx`
                          (`const MODE_OPTIONS = [...]`, sélecteur écran) ;
  * classifieurs         — `backend/django_core/apps/ventes/domain/creation.py`
                          (`MODES_INSTALLATION = (...)`) ;
  * backend (Devis)      — `backend/django_core/apps/ventes/models.py`
                          (`Devis.ModeInstallation`, Django `TextChoices`) ;
  * backend (Lead)       — `backend/django_core/apps/crm/models.py`
                          (`Lead.TypeInstallation`, Django `TextChoices`) ;
  * quote_engine (photos) — `backend/django_core/apps/ventes/quote_engine/
                          installations.py` (`_MODES = (...)`).

Un cinquième marché ajouté correctement dans certaines et oublié dans
d'autres ne fait rougir AUCUN test existant.

CE QUE LA GARDE COMPARE
------------------------
Le porteur partagé est le contrat committé `apps/ventes/contracts/
modes_marche.json` (QJR231, PACT10) — sa liste `modes` fait foi. Cette garde
lit les SIX sites (AST pour les fichiers Python, une extraction ciblée par
regex pour les deux fichiers JS/JSX — aucun des deux tableaux visés n'est
imbriqué, une regex simple suffit et reste plus honnête qu'un vrai parseur JS
absent de ce dépôt) et compare chaque ENSEMBLE de valeurs au contrat. Un
mode absent d'un site, ou un mode surnuméraire qu'aucun site ne devrait
porter, fait ROUGIR — en NOMMANT le site et le mode en cause.

CE QUI EST HORS PÉRIMÈTRE (voir `notes.hors_perimetre` du contrat)
--------------------------------------------------------------------
`apps/web` (contrat et garde séparés, Groupe QJW) et les énumérations à
TROIS entrées qui fusionnent délibérément `commercial` dans `industriel`
(`apps.installations`, `apps.compta`, `apps.gestion_projet`) — ce sont des
vocabulaires différents documentés comme tels, pas des divergences.

Usage : `python scripts/check_modes_marche.py`
Stdlib pure : ni base de données, ni docker, ni Django, ni node.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRAT = (ROOT / "backend" / "django_core" / "apps" / "ventes"
           / "contracts" / "modes_marche.json")
SIZING_REDUCER = (ROOT / "frontend" / "src" / "features" / "ventes"
                  / "quote" / "sizingReducer.js")
DEVIS_GENERATOR = ROOT / "frontend" / "src" / "pages" / "ventes" / "DevisGenerator.jsx"
CREATION_PY = ROOT / "backend" / "django_core" / "apps" / "ventes" / "domain" / "creation.py"
VENTES_MODELS = ROOT / "backend" / "django_core" / "apps" / "ventes" / "models.py"
CRM_MODELS = ROOT / "backend" / "django_core" / "apps" / "crm" / "models.py"
INSTALLATIONS_PY = (ROOT / "backend" / "django_core" / "apps" / "ventes"
                    / "quote_engine" / "installations.py")


def _relatif(chemin: Path) -> str:
    try:
        return str(chemin.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(chemin)


def charger_contrat(chemin: Path) -> set[str]:
    data = json.loads(chemin.read_text(encoding="utf-8"))
    modes = data.get("modes")
    if not isinstance(modes, list) or not modes:
        raise ValueError("le contrat ne porte aucune clé « modes » (liste non vide attendue)")
    return set(modes)


def _extraire_tuple_module(source: str, nom: str) -> set[str] | None:
    """AST : valeurs d'une affectation module-level `nom = ('a', 'b', ...)`
    (tuple OU liste de chaînes littérales)."""
    arbre = ast.parse(source)
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign):
            continue
        cibles = [c.id for c in noeud.targets if isinstance(c, ast.Name)]
        if nom not in cibles:
            continue
        valeur = noeud.value
        if isinstance(valeur, (ast.Tuple, ast.List)):
            return {
                elt.value for elt in valeur.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
    return None


def _extraire_text_choices(source: str, classe_parente: str, classe_choix: str) -> set[str] | None:
    """AST : les VALEURS (premier élément du tuple `'valeur', 'Libellé'`) des
    membres d'une `models.TextChoices` imbriquée dans `classe_parente`."""
    arbre = ast.parse(source)
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.ClassDef) and noeud.name == classe_parente):
            continue
        for enfant in noeud.body:
            if not (isinstance(enfant, ast.ClassDef) and enfant.name == classe_choix):
                continue
            valeurs: set[str] = set()
            for membre in enfant.body:
                if not isinstance(membre, ast.Assign):
                    continue
                cible = membre.value
                # `RESIDENTIEL = 'residentiel', 'Résidentiel'` -> Tuple(Constant, Constant)
                if isinstance(cible, ast.Tuple) and cible.elts:
                    premier = cible.elts[0]
                    if isinstance(premier, ast.Constant) and isinstance(premier.value, str):
                        valeurs.add(premier.value)
            return valeurs
    return None


def _extraire_js_array(source: str, nom_const: str) -> set[str] | None:
    """Extraction ciblée (pas d'imbrication dans les deux sites visés) :
    trouve `(export )?const <nom_const> = [ ... ]` et rend l'ensemble des
    chaînes littérales `'...'`/`"..."` du bloc entre crochets."""
    motif = re.compile(
        r"const\s+" + re.escape(nom_const) + r"\s*=\s*\[(.*?)\]",
        re.DOTALL,
    )
    m = motif.search(source)
    if not m:
        return None
    bloc = m.group(1)
    return set(re.findall(r"""['"]([a-z_]+)['"]""", bloc))


def _extraire_mode_options_values(source: str) -> set[str] | None:
    """`MODE_OPTIONS` est un tableau d'objets `{ value: '...', label: '...' }` :
    seul le champ `value` est une clé machine — `label` porte un libellé FR
    avec emoji, jamais comparable au contrat."""
    motif = re.compile(r"const\s+MODE_OPTIONS\s*=\s*\[(.*?)\n\]", re.DOTALL)
    m = motif.search(source)
    if not m:
        return None
    bloc = m.group(1)
    return set(re.findall(r"""value:\s*['"]([a-z_]+)['"]""", bloc))


#: Un site = (étiquette FR, chemin par défaut, extracteur(source) -> set|None).
SITES = [
    ("reducteur", SIZING_REDUCER,
     lambda src: _extraire_js_array(src, "MODES")),
    ("panneaux", DEVIS_GENERATOR,
     _extraire_mode_options_values),
    ("classifieurs", CREATION_PY,
     lambda src: _extraire_tuple_module(src, "MODES_INSTALLATION")),
    ("backend_devis", VENTES_MODELS,
     lambda src: _extraire_text_choices(src, "Devis", "ModeInstallation")),
    ("backend_lead", CRM_MODELS,
     lambda src: _extraire_text_choices(src, "Lead", "TypeInstallation")),
    ("quote_engine_photos", INSTALLATIONS_PY,
     lambda src: _extraire_tuple_module(src, "_MODES")),
]


def constats(canonique: set[str], chemins: dict[str, Path]) -> list[tuple[str, str]]:
    """Rend une liste de `(site, motif)` — vide si les six sites sont en
    parité EXACTE (ensemble égal, ni manquant ni surnuméraire) avec le contrat."""
    trouves: list[tuple[str, str]] = []
    for etiquette, chemin_defaut, extracteur in SITES:
        chemin = chemins.get(etiquette, chemin_defaut)
        try:
            source = chemin.read_text(encoding="utf-8")
        except OSError as erreur:
            trouves.append((etiquette, f"illisible ({chemin}) : {erreur}"))
            continue
        valeurs = extracteur(source)
        if valeurs is None:
            trouves.append((etiquette, f"énumération introuvable dans {chemin}"))
            continue
        manquants = canonique - valeurs
        surnumeraires = valeurs - canonique
        if manquants:
            trouves.append((
                etiquette,
                f"mode(s) absent(s) de ce site : {', '.join(sorted(manquants))}",
            ))
        if surnumeraires:
            trouves.append((
                etiquette,
                f"mode(s) hors contrat sur ce site : {', '.join(sorted(surnumeraires))}",
            ))
    return trouves


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Parité des six énumérations de modes de marché contre le contrat QJR231.")
    parser.add_argument("--contrat", default=str(CONTRAT))
    for etiquette, chemin_defaut, _ in SITES:
        parser.add_argument(f"--{etiquette.replace('_', '-')}", default=str(chemin_defaut))
    args = parser.parse_args(argv)

    try:
        canonique = charger_contrat(Path(args.contrat))
    except (OSError, ValueError) as erreur:
        print(f"ECHEC : contrat illisible ({args.contrat}) : {erreur}")
        return 1

    chemins = {
        etiquette: Path(getattr(args, etiquette))
        for etiquette, _, _ in SITES
    }

    trouves = constats(canonique, chemins)
    if trouves:
        print(f"\n[check_modes_marche] ECHEC : {len(trouves)} site(s) hors "
              "parité avec le contrat des modes de marché.\n")
        for etiquette, motif in trouves:
            print(f"  {etiquette} : {motif}")
        print(f"\nLe porteur partagé est {_relatif(CONTRAT)} — un mode ajouté "
              "à un site doit d'abord être ajouté là (décision fondateur), "
              "puis répercuté sur les six sites. Ne désactivez pas cette garde.")
        return 1

    print(f"[check_modes_marche] OK : les six sites sont en parité avec "
          f"{sorted(canonique)} ({_relatif(CONTRAT)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
