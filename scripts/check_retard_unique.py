"""ALEA43 (C-ALEA-028) — garde « UNE définition de en retard ».

CLASSE GARDÉE. « En retard » pour une touche de relance (``RelanceEtape``)
se calcule en UN endroit — ``apps/crm/controle_suivi.py`` (jours ouvrés,
``seuil_retard``). Toute autre lecture qui compare ``due_date`` / ``due_at``
au calendrier (``due_date__lt=``, ``due_at__lt=``, ``due_date <``,
``due_at <``) recompose une deuxième définition (jours calendaires) : deux écrans
affichent alors deux comptes de retards différents.

CE QUE LA GARDE FAIT. Sur ``backend/django_core/apps`` (hors tests et
migrations), pour les fichiers qui lisent des ``RelanceEtape``, elle liste
chaque comparaison ``<`` / ``__lt`` sur ``due_date`` / ``due_at`` hors de la
source unique et échoue. Les exceptions sont des SYMBOLES nommés avec leur
raison (``fichier::fonction``), jamais des numéros de ligne ; une clé qui
n'apparie plus aucun site échoue (cliquet décroissant).

DB-free, AST-only. Usage : ``python scripts/check_retard_unique.py``.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS = ROOT / "backend" / "django_core" / "apps"

#: LA source unique de la définition de « en retard » (relatif au dépôt).
SOURCE_UNIQUE = "backend/django_core/apps/crm/controle_suivi.py"

CHAMPS = {"due_date", "due_at"}
KEYWORDS = {"due_date__lt", "due_at__lt"}
MARQUEUR = "RelanceEtape"

#: Exceptions : ``fichier::fonction`` -> raison propre (jamais un n° de ligne).
_C = "backend/django_core/apps/crm/"
EXCEPTIONS: dict = {
    _C + "cockpit_oracle_outils.py::Oracle._attendu":
        "oracle de test INDÉPENDANT par conception : recalcule le retard sans "
        "passer par controle_suivi pour pouvoir le contredire",
    _C + "management/commands/demarrer_cadences_existantes.py::"
    "demarrer_cadences_existantes":
        "comparaison d'INSTANT (due_at < maintenant) pour annuler des touches "
        "déjà dépassées à la reprise d'une cadence : pas un affichage de retard",
    _C + "selectors.py::_activites_en_retard":
        "lit des Activity (records), pas des RelanceEtape : autre définition, "
        "autre propriétaire",
    _C + "cadence_selectors.py::kpi_adherence":
        "À CORRIGER (constat ALEA43, hors Files de la garde) : due_date < "
        "aujourd'hui en jours calendaires ; devrait passer par seuil_retard "
        "(reste de C-ALEA-028 après ALEA32)",
    _C + "cadence_selectors.py::mes_stats_relance":
        "À CORRIGER (constat ALEA43, hors Files de la garde) : due_date < "
        "aujourd'hui en jours calendaires ; devrait passer par seuil_retard "
        "(reste de C-ALEA-028 après ALEA32)",
    _C + "cadence_selectors.py::_serie_jours_sans_retard":
        "borne de la FENÊTRE de jours écoulés de la série (due_date < "
        "aujourd'hui exclut le jour en cours), la qualification retard par "
        "jour est faite ensuite ; relu au build",
    _C + "cadence_selectors.py::cadences_echues_a_clore":
        "seuil de CLÔTURE de cadence (touche ouverte depuis plus de N jours), "
        "distinct du retard affiché ; N est un paramètre de la clôture",
    _C + "services.py::touche_traitee_en_avance":
        "mesure l'AVANCE (traitée avant l'échéance), c'est le complément du "
        "retard et non sa définition",
    _C + "services.py::_placer_cadence_positionnee":
        "comparaison d'INSTANT (due_at < maintenant) pour placer une cadence "
        "positionnée ; pas un affichage de retard",
}


def _est_test(path: Path) -> bool:
    p = path.parts
    n = path.name
    return (any(x in ("tests", "migrations") for x in p)
            or n.startswith(("test_", "tests_")) or n == "tests.py")


def _champ(node) -> bool:
    return isinstance(node, ast.Attribute) and node.attr in CHAMPS


def analyser_source(source: str):
    """[(ligne, fonction, forme)] des comparaisons de retard du fichier."""
    tree = ast.parse(source)
    out = []

    def visite(node, pile):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            pile = pile + [node.name]
        if isinstance(node, ast.keyword) and node.arg in KEYWORDS                 and not (ast.unparse(node.value) == "seuil"
                         or "seuil_retard" in ast.unparse(node.value)):
            out.append((node.value.lineno, ".".join(pile), f"{node.arg}="))
        elif isinstance(node, ast.Compare):
            termes = [node.left] + list(node.comparators)
            for i, op in enumerate(node.ops):
                if isinstance(op, ast.Lt) and (_champ(termes[i])
                                               or _champ(termes[i + 1])):
                    out.append((node.lineno, ".".join(pile), "due_* <"))
                    break
        for enfant in ast.iter_child_nodes(node):
            visite(enfant, pile)

    visite(tree, [])
    return out


def evaluer(sources: dict, exceptions: dict, source_unique=SOURCE_UNIQUE):
    """-> (violations, clés mortes). ``sources`` : {chemin relatif: texte}."""
    violations, vues = [], set()
    for rel, texte in sorted(sources.items()):
        if rel == source_unique or MARQUEUR not in texte:
            continue
        for ligne, fonction, forme in analyser_source(texte):
            cle = f"{rel}::{fonction}"
            vues.add(cle)
            if cle not in exceptions:
                violations.append(
                    f"{rel}:{ligne} dans {fonction or '<module>'} — {forme} : "
                    "deuxième définition de « en retard » hors de "
                    f"{source_unique.rsplit('/', 1)[-1]}")
    mortes = sorted(c for c in exceptions if c not in vues)
    return violations, mortes


def _sources():
    out = {}
    for path in sorted(APPS.rglob("*.py")):
        if _est_test(path):
            continue
        try:
            out[str(path.relative_to(ROOT)).replace("\\", "/")] = \
                path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return out


def main(argv=None) -> int:
    violations, mortes = evaluer(_sources(), EXCEPTIONS)
    violations += [f"{c} — exception morte (site corrigé ou disparu) : "
                   "la retirer" for c in mortes]
    if violations:
        print("check_retard_unique : comparaison calendaire de due_date/"
              "due_at hors de la source unique du retard :")
        for v in violations:
            print(f"  - {v}")
        print("\nLe retard d'une touche se lit via controle_suivi "
              "(seuil_retard, jours ouvrés). Exception motivée : EXCEPTIONS "
              "du script (symbole nommé + raison).")
        return 1
    print("check_retard_unique : OK — « en retard » n'est défini qu'en un "
          "seul endroit (controle_suivi.py).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
