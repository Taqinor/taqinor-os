"""ACRM51 (C-ACRM-006) — garde « version en vigueur » des lectures de devis.

CLASSE GARDÉE. Un devis révisé laisse sa V1 ``accepte`` mais INACTIVE
(``is_active=False``) : tout lecteur qui filtre ``statut == 'accepte'`` sans
regarder ``is_active`` compte la V1 ET la V2 (CA doublé, relance sur une
version remplacée). ``is_active`` est un 2ᵉ axe que les lecteurs ignorent.

CE QUE LA GARDE FAIT. Dans ``apps/crm/{selectors,services,views}.py`` et
``apps/ventes/scheduled.py``, toute lecture « devis accepté / envoyé » —
``statut == 'accepte'``, ``statut='accepte'``, ``devis__statut=...``, la
constante ``_DEVIS_STATUT_ACCEPTE`` — doit, DANS LA MÊME INSTRUCTION, passer
par le prédicat de version en vigueur (``_devis_compte_comme_signe``,
``devis_en_jeu``, ``devis_acceptes_actifs``…) ou porter ``is_active``. Sinon
elle figure en liste blanche MOTIVÉE (symbole ``fichier::fonction``, jamais un
numéro de ligne). Une clé de liste blanche qui n'apparie plus aucun site
échoue (cliquet décroissant).

RÈGLE #4. La garde LIT, elle n'écrit rien et ne touche à aucun statut.

DB-free, AST-only. Usage : ``python scripts/check_version_en_vigueur.py``.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS = ROOT / "backend" / "django_core" / "apps"

#: Fichiers du périmètre (chemin relatif au dépôt).
FICHIERS = [
    "backend/django_core/apps/crm/selectors.py",
    "backend/django_core/apps/crm/portee_selectors.py",  # SPL309/SPL83-SPL88 : morceaux de selectors.py
    "backend/django_core/apps/crm/cadence_selectors.py",  # SPL309/SPL83-SPL88 : morceaux de selectors.py
    "backend/django_core/apps/crm/leads_selectors.py",  # SPL309/SPL83-SPL88 : morceaux de selectors.py
    "backend/django_core/apps/crm/clients_selectors.py",  # SPL309/SPL83-SPL88 : morceaux de selectors.py
    "backend/django_core/apps/crm/devis_selectors.py",  # SPL309/SPL83-SPL88 : morceaux de selectors.py
    "backend/django_core/apps/crm/roof_selectors.py",  # SPL309/SPL83-SPL88 : morceaux de selectors.py
    "backend/django_core/apps/crm/stock_selectors.py",  # SPL309/SPL83-SPL88 : morceaux de selectors.py
    "backend/django_core/apps/crm/attribution_selectors.py",  # SPL309/SPL83-SPL88 : morceaux de selectors.py
    "backend/django_core/apps/crm/fiche_selectors.py",  # SPL89 : dernier morceau de selectors.py
    "backend/django_core/apps/crm/services.py",
    "backend/django_core/apps/crm/views.py",
    "backend/django_core/apps/ventes/scheduled.py",
]


def _modules_scission_crm() -> list:
    """SPL3-SPL26 : modules issus de la scission de crm/services.py (table du
    golden SPL1) — une lecture déplacée reste dans le périmètre de la garde."""
    golden = APPS / "crm" / "golden" / "services_split_ast.json"
    if not golden.is_file():
        return []
    cibles = {v["cible"] for v in json.loads(
        golden.read_text(encoding="utf-8"))["noms"].values()}
    return [f"backend/django_core/apps/crm/{c}.py" for c in sorted(cibles)
            if (APPS / "crm" / f"{c}.py").is_file()]


FICHIERS += _modules_scission_crm()
#: SPL74-SPL81 : modules de vues issus de la scission de crm/views.py — une
#: lecture déplacée reste dans le périmètre de la garde.
FICHIERS += [f"backend/django_core/apps/crm/{p.name}"
             for p in sorted((APPS / "crm").glob("*_views.py"))]

#: Statuts de devis dont la lecture exige la version en vigueur.
STATUTS = {"accepte", "envoye"}
ATTRS_STATUT = {"ACCEPTE", "ENVOYE"}
NOM_CONSTANTE = "_DEVIS_STATUT_ACCEPTE"

#: Jetons qui valent « version en vigueur » dans la même instruction.
PREDICATS = (
    "is_active", "_devis_compte_comme_signe", "devis_en_jeu",
    "devis_acceptes_actifs", "devis_acceptes_en_vigueur",
    "devis_en_vigueur", "instantane_accepte_en_vigueur",
)

#: Liste blanche MOTIVÉE : ``fichier::fonction`` -> raison propre.
ALLOWLIST = {
    "backend/django_core/apps/crm/attribution_selectors.py::reporting_lead_rows":
        "date de PREMIÈRE acceptation du lead (événement de signature) : une "
        "V1 remplacée a bien été acceptée, sa date compte",
    "backend/django_core/apps/crm/attribution_selectors.py::attribution_comparaison_devis":
        "attribution d'un devis donné (argument) : le caller fournit la "
        "version ; ne lit pas un ensemble de devis",
    "backend/django_core/apps/crm/fiche_selectors.py::leads_signes_sans_devis_accepte":
        "détecte un lead SIGNED dont AUCUN devis n'est accepté, toutes "
        "versions confondues (drapeau de cohérence, décidé par ACRM10)",
    "backend/django_core/apps/crm/fiche_funnel.py::lead_signe_sans_devis_actif":
        "drapeau dérivé « signé fantôme » décidé par ACRM10 : filtre statut "
        "puis archivage ; la version remplacée n'y est pas une erreur",
    "backend/django_core/apps/ventes/scheduled.py::_email_parti":
        "À CORRIGER (09/10, arrivé de main pendant ce build) : lecture d'un "
        "statut de devis sans is_active dans ventes/scheduled.py — à passer "
        "par le prédicat de version en vigueur par le propriétaire ventes ; la "
        "ligne tombe avec la correction",
    "backend/django_core/apps/ventes/scheduled.py::pre_echeance_reminders":
        "À CORRIGER (09/10, arrivé de main pendant ce build) : lecture d'un "
        "statut de devis sans is_active dans ventes/scheduled.py — à passer "
        "par le prédicat de version en vigueur par le propriétaire ventes ; la "
        "ligne tombe avec la correction",
    "backend/django_core/apps/ventes/scheduled.py::releve_mensuel_reminders":
        "À CORRIGER (09/10, arrivé de main pendant ce build) : lecture d'un "
        "statut de devis sans is_active dans ventes/scheduled.py — à passer "
        "par le prédicat de version en vigueur par le propriétaire ventes ; la "
        "ligne tombe avec la correction",
}


def _est_statut_devis(node) -> bool:
    """Le nœud désigne un statut de devis lu (chaîne, constante, enum)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value in STATUTS
    if isinstance(node, ast.Name) and node.id == NOM_CONSTANTE:
        return True
    if isinstance(node, ast.Attribute) and node.attr in ATTRS_STATUT:
        return True
    return False


def _est_champ_statut(node) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == "statut"
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "getattr":
        return (len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "statut")
    if isinstance(node, ast.Name):
        return node.id == "statut"
    return False


def _sites(tree):
    """[(ligne, nœud-instruction, qualname-fonction)] des lectures de statut."""
    resultats = []

    def visite(node, pile, stmt):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            pile = pile + [node.name]
        if isinstance(node, ast.stmt):
            stmt = node
        hit = False
        if isinstance(node, ast.Compare):
            termes = [node.left] + list(node.comparators)
            hit = (any(_est_champ_statut(t) for t in termes)
                   and any(_est_statut_devis(t) for t in termes))
        elif isinstance(node, ast.keyword):
            hit = (node.arg is not None
                   and (node.arg == "statut" or node.arg.endswith("__statut"))
                   and _est_statut_devis(node.value))
        elif (isinstance(node, ast.Name) and node.id == NOM_CONSTANTE
              and isinstance(node.ctx, ast.Load)):
            hit = True
        if hit and stmt is not None:
            resultats.append((getattr(node, "lineno", stmt.lineno), stmt,
                              ".".join(pile)))
        for enfant in ast.iter_child_nodes(node):
            visite(enfant, pile, stmt)

    visite(tree, [], None)
    return resultats


def _instruction_texte(stmt, source_lines):
    fin = getattr(stmt, "end_lineno", stmt.lineno)
    # Instruction composée (def/for/if…) : on ne lit que l'en-tête pour ne pas
    # créditer un prédicat situé dans un bloc voisin.
    corps = getattr(stmt, "body", None)
    if corps and isinstance(stmt, (ast.If, ast.For, ast.While, ast.With,
                                   ast.Try, ast.FunctionDef,
                                   ast.AsyncFunctionDef, ast.ClassDef)):
        fin = corps[0].lineno - 1
    return "\n".join(source_lines[stmt.lineno - 1:fin])


def analyser_source(source: str):
    """[(ligne, fonction)] des lectures SANS prédicat de version en vigueur."""
    tree = ast.parse(source)
    lignes = source.splitlines()
    fautifs = []
    for ligne, stmt, fonction in _sites(tree):
        texte = _instruction_texte(stmt, lignes)
        if not any(p in texte for p in PREDICATS):
            fautifs.append((ligne, fonction))
    return fautifs


def evaluer(sources: dict, allowlist: dict):
    """-> (violations, clés mortes). ``sources`` : {chemin relatif: texte}."""
    violations, vues = [], set()
    for rel, texte in sorted(sources.items()):
        for ligne, fonction in analyser_source(texte):
            cle = f"{rel}::{fonction}"
            vues.add(cle)
            if cle not in allowlist:
                violations.append(
                    f"{rel}:{ligne} dans {fonction or '<module>'} — lecture "
                    "d'un statut de devis sans prédicat de version en vigueur")
    mortes = sorted(c for c in allowlist if c not in vues)
    return violations, mortes


def main(argv=None) -> int:
    sources = {}
    for rel in FICHIERS:
        chemin = ROOT / rel
        if chemin.exists():
            sources[rel] = chemin.read_text(encoding="utf-8")
    violations, mortes = evaluer(sources, ALLOWLIST)
    if mortes:
        for cle in mortes:
            violations.append(f"{cle} — clé morte de la liste blanche "
                              "(site corrigé ou disparu) : la retirer")
    if violations:
        print("check_version_en_vigueur : lecture de devis sans la version "
              "en vigueur (is_active) :")
        for ligne in violations:
            print(f"  - {ligne}")
        print("\nPassez par le prédicat de version en vigueur (ACRM10 : "
              "_devis_compte_comme_signe / devis_en_jeu / "
              "devis_acceptes_actifs) ou ajoutez `is_active` à la même "
              "requête ; exception motivée : ALLOWLIST du script.")
        return 1
    print("check_version_en_vigueur : OK — toute lecture « devis accepté / "
          "envoyé » du périmètre passe par la version en vigueur.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
