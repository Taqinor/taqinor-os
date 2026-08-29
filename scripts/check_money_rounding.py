"""YDATA8 / QJR4 -- garde ADVISORY : un `round()` sur une valeur d'apparence
monetaire, dans un module qui publie du prix, devrait passer par
`core.money.quantize_mad` (voir docs/money-convention.md).

DB-free, AST seul. La garde ne bloque JAMAIS sur l'existant : chaque site
present dans l'arbre au moment de la capture est inscrit dans
``scripts/money_rounding_allow.txt`` avec sa raison humaine. Elle echoue
uniquement sur un site NOUVEAU, c.-a-d. jamais relu par un humain.

CLE D'IDENTITE DE CONTENU (QJR4, 29/08/2026) -- pourquoi ce n'est plus
``fichier.py:LIGNE``. L'ancienne cle etait un numero de ligne : toute
insertion en amont perimait la base et il fallait la recaler a la main. Le
seul mois d'aout a coute DIX recalages manuels documentes, dont deux faux
(deux lanes qui recalent le meme fichier chacune dans son worktree se
contredisent a la fusion). Pire : une entree devenue morte n'est pas neutre,
elle PRE-AUTORISE en silence un futur `round(total_ht, 2)` insere a cette
ligne -- exactement ce que la garde existe pour faire relire.

La cle est donc :

    <chemin>::<qualname englobant>::<sha1(expression normalisee)[:12]>

  * ``chemin``   -- chemin POSIX relatif a la racine du depot ;
  * ``qualname`` -- marche des parents AST (``Classe.methode``,
    ``fonction.interne``) ; au niveau module : ``<module>`` ;
  * ``sha1``     -- 12 hex du texte ``ast.unparse`` du PREMIER argument de
    ``round()``, espaces normalises (c'est deja ce que le script calculait
    pour son message d'erreur).

Deux `round()` a l'expression IDENTIQUE dans la meme fonction sont
departages par un suffixe ``#1`` / ``#2`` dans l'ordre du source.

Consequence voulue : deplacer du code ne touche pas la base ; renommer la
fonction englobante ou changer l'expression, si -- ce sont justement les deux
evenements qu'un humain doit relire.

Usage:
    python scripts/check_money_rounding.py              # controle (CI)
    python scripts/check_money_rounding.py --list       # tous les sites vus
    python scripts/check_money_rounding.py --regenerate # reecrit la base
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
VENTES = DJANGO_CORE / "apps" / "ventes"
ALLOWLIST_PATH = ROOT / "scripts" / "money_rounding_allow.txt"

MODULE_QUALNAME = "<module>"
SEPARATOR = "|"
NEW_SITE_REASON = "A RELIRE -- capture par --regenerate, raison a completer."

# Modules scannes : ceux qui calculent OU publient un montant client-facing.
# QJR4 elargit la liste d'origine (services/builder/compta) aux cinq modules
# ventes qui rendent aussi de l'argent au client et n'etaient pas scannes.
TARGET_FILES = [
    VENTES / "services.py",
    VENTES / "quote_engine" / "builder.py",
    VENTES / "public_views.py",
    VENTES / "offres_tailles.py",
    VENTES / "taille_detail.py",
    VENTES / "utils" / "options.py",
    VENTES / "selectors.py",
    DJANGO_CORE / "apps" / "compta" / "services.py",
]

MONEY_NAME_RE = re.compile(
    r"(prix|montant|total|_ht|_ttc|tva|remise|acompte|solde|amount|price|"
    r"cost|cout|honoraire|penalite)",
    re.IGNORECASE,
)


class Site:
    """Un site de `round()` retenu par le detecteur."""

    __slots__ = ("path", "lineno", "qualname", "expr", "key")

    def __init__(self, path, lineno, qualname, expr, key):
        self.path = path
        self.lineno = lineno
        self.qualname = qualname
        self.expr = expr
        self.key = key

    def __repr__(self):  # pragma: no cover - confort de debogage
        return f"<Site {self.key} ligne {self.lineno}>"


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _arg_source(node) -> str:
    """Forme textuelle, au mieux, du premier argument de `round()`."""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def normalize_expr(src: str) -> str:
    """Normalise les espaces : un retour a la ligne ne change pas l'identite."""
    return " ".join(src.split())


def content_sha(expr_norm: str) -> str:
    return hashlib.sha1(expr_norm.encode("utf-8")).hexdigest()[:12]


def _iter_round_calls(tree):
    """Rend (noeud Call, qualname englobant) pour chaque appel a `round()`.

    Le qualname vient d'une marche des parents AST : au niveau module il vaut
    ``<module>``, sinon la chaine des `def`/`class` englobants jointe par un
    point.
    """
    found = []

    def visit(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                visit(child, stack + [child.name])
                continue
            if (isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "round"):
                found.append((child, ".".join(stack) if stack
                              else MODULE_QUALNAME))
            visit(child, stack)

    visit(tree, [])
    return found


def collect_sites(source: str, rel: str):
    """Rend la liste des Site retenus dans ce source, en ordre de source."""
    tree = ast.parse(source)
    raw = []
    for node, qualname in _iter_round_calls(tree):
        if not node.args:
            continue
        expr = normalize_expr(_arg_source(node.args[0]))
        if not expr or not MONEY_NAME_RE.search(expr):
            continue
        raw.append((node.lineno, node.col_offset, qualname, expr))
    raw.sort()

    counts = Counter((qualname, expr) for _, _, qualname, expr in raw)
    seen = Counter()
    sites = []
    for lineno, _col, qualname, expr in raw:
        base = f"{rel}::{qualname}::{content_sha(expr)}"
        if counts[(qualname, expr)] > 1:
            seen[(qualname, expr)] += 1
            key = f"{base}#{seen[(qualname, expr)]}"
        else:
            key = base
        sites.append(Site(rel, lineno, qualname, expr, key))
    return sites


def collect_sites_in_file(path: Path):
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        return collect_sites(source, _rel(path))
    except SyntaxError as exc:  # pragma: no cover - fichier casse
        print(f"check_money_rounding: {_rel(path)} illisible ({exc})")
        return []


def scan(paths=None):
    """Scanne TARGET_FILES (ou `paths`) et rend la liste des sites."""
    sites = []
    for path in (TARGET_FILES if paths is None else paths):
        if path.exists():
            sites.extend(collect_sites_in_file(path))
    return sites


def load_allowlist(path: Path = ALLOWLIST_PATH):
    """Rend {cle: raison} dans l'ordre du fichier. Ligne = `cle | raison`."""
    entries = {}
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if SEPARATOR in stripped:
            key, reason = stripped.split(SEPARATOR, 1)
        else:
            key, reason = stripped, ""
        key = key.strip()
        if key:
            entries[key] = reason.strip()
    return entries


def evaluate(sites, allowed_keys):
    """Rend (sites nouveaux, cles orphelines) pour un scan COMPLET."""
    live = {site.key for site in sites}
    offenders = [site for site in sites if site.key not in allowed_keys]
    orphans = [key for key in allowed_keys if key not in live]
    return offenders, orphans


HEADER = """\
# Base de reference de scripts/check_money_rounding.py (YDATA8 / QJR4).
#
# FORMAT : une cle par ligne, puis une colonne de raison humaine separee par
# `|` (patron de scripts/read_modify_write_allow.txt). Les lignes vides et
# celles commencant par `#` sont ignorees.
#
#   <chemin>::<qualname englobant>::<sha1(expression normalisee)[:12]> | raison
#
# La cle est une IDENTITE DE CONTENU, jamais un numero de ligne : inserer du
# code en amont ne perime plus la base (l'ancienne base file:line a coute dix
# recalages manuels sur le seul mois d'aout 2026, dont deux faux). Renommer la
# fonction englobante ou changer l'expression change la cle -- c'est voulu :
# ce sont les deux evenements qu'un humain doit relire.
#
# La garde est ADVISORY : le moteur de devis travaille en float de bout en
# bout, `quantize_mad` est la convention des MODELES. Un site inscrit ici a
# ete relu ; un site NOUVEAU fait echouer backend-lint, le temps qu'un humain
# ecrive sa raison ici (ou corrige le calcul).
#
# Regenerer apres une revue : python scripts/check_money_rounding.py --regenerate
"""


def render_allowlist(sites, existing_reasons=None):
    """Rend le texte complet du fichier de base pour ces sites."""
    existing_reasons = existing_reasons or {}
    lines = [HEADER.rstrip("\n")]
    current_file = None
    for site in sites:
        if site.path != current_file:
            current_file = site.path
            lines.append("")
            lines.append(f"# --- {current_file}")
        reason = existing_reasons.get(site.key) or NEW_SITE_REASON
        lines.append(f"{site.key} {SEPARATOR} {reason}")
    return "\n".join(lines) + "\n"


def _print_sites(sites):
    for site in sites:
        print(f"  {site.path}:{site.lineno}  {site.qualname}  "
              f"round({site.expr[:60]})")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Garde advisory sur les round() monetaires.")
    parser.add_argument("--list", action="store_true", dest="list_mode",
                        help="imprime chaque site vu, avec sa cle")
    parser.add_argument("--regenerate", action="store_true",
                        help="reecrit scripts/money_rounding_allow.txt "
                             "depuis l'arbre courant (raisons conservees)")
    args = parser.parse_args(argv)

    sites = scan()

    if args.list_mode:
        for site in sites:
            print(f"{site.key} | {site.path}:{site.lineno} "
                  f"round({site.expr})")
        return 0

    if args.regenerate:
        existing = load_allowlist()
        ALLOWLIST_PATH.write_text(render_allowlist(sites, existing),
                                  encoding="utf-8")
        print(f"check_money_rounding: {len(sites)} site(s) ecrit(s) dans "
              f"{_rel(ALLOWLIST_PATH)}.")
        return 0

    allowed = load_allowlist()
    offenders, orphans = evaluate(sites, allowed)

    print(f"check_money_rounding: {len(sites)} site(s) round() sur une valeur "
          "d'apparence monetaire dans les modules de prix/taxe.")
    _print_sites(sites)

    if orphans:
        print("\ncheck_money_rounding: entree(s) ORPHELINE(S) dans "
              f"{_rel(ALLOWLIST_PATH)} (le site n'existe plus ou son "
              "expression a change) -- signale, ne bloque pas :")
        for key in orphans:
            print(f"  - {key}")
        print("  Nettoyer avec: python scripts/check_money_rounding.py "
              "--regenerate")

    if offenders:
        print("\ncheck_money_rounding: site(s) NOUVEAU(X) absent(s) de "
              f"{_rel(ALLOWLIST_PATH)} :")
        for site in offenders:
            print(f"  - {site.path}:{site.lineno} ({site.qualname}) "
                  f"round({site.expr[:60]})")
            print(f"    cle: {site.key}")
        print("\nPreferer core.money.quantize_mad() (docs/money-convention.md) "
              "pour un montant persiste. Si l'arrondi est un AFFICHAGE relu, "
              "ajouter la cle et sa raison dans "
              f"{_rel(ALLOWLIST_PATH)} (ou --regenerate puis ecrire la "
              "raison).")
        return 1

    print("\ncheck_money_rounding: OK (advisory -- tous les sites sont dans "
          "la base).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
