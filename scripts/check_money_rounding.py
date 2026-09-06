"""YDATA8 / QJR4 / AUD189 -- garde ADVISORY : une valeur d'apparence monetaire
arrondie hors politique, dans un module qui calcule ou publie du prix, devrait
passer par `core.money.quantize_mad` (voir docs/money-convention.md).

DEUX DETECTEURS, UNE SEULE POLITIQUE (AUD189, 03/09/2026) :

  1. `round(x)` sur une expression d'apparence monetaire (detecteur d'origine) ;
  2. `x.quantize(...)` SANS mot-cle `rounding=`, donc en arrondi bancaire
     ROUND_HALF_EVEN -- le defaut de `Decimal`. `docs/money-convention.md`
     ecrit noir sur blanc que ce n'est PAS « la politique moitie-vers-le-haut
     attendue en comptabilite marocaine », et la garde ne voyait pourtant que
     `round()` : la classe entiere lui etait invisible, et la CI restait verte
     en laissant croire que la convention etait tenue partout (`12.505` rendait
     12.50 au lieu de 12.51, `0.125` rendait 0.12 au lieu de 0.13, sur une
     dotation d'amortissement comme sur une ligne de regie).

Garde SEMANTIQUE (lecon OR3) : elle regarde la FORME de l'appel, jamais un
nombre de sites epingle.

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
# AUD189 -- REPRISE. Les sites `quantize` sans `rounding=` presents dans
# l'arbre au moment ou le second detecteur est ne sont inscrits d'office :
# la garde protege contre une REINTRODUCTION des aujourd'hui, la reprise de
# l'existant se fait fichier par fichier ensuite. Un site quantize NOUVEAU
# fait echouer backend-lint.
QUANTIZE_REPRISE_REASON = (
    "AUD189 reprise -- quantize sans rounding= present a la capture ; "
    "A RELIRE (ROUND_HALF_UP via core.money.quantize_mad)."
)

# Modules scannes : ceux qui calculent OU publient un montant client-facing.
# QJR4 elargit la liste d'origine (services/builder/compta) aux cinq modules
# ventes qui rendent aussi de l'argent au client et n'etaient pas scannes.
#
# QJR72 AJOUTE TOUT `apps/ventes/domain/` -- SANS CELA LA GARDE SE VIDE TOUTE
# SEULE. La vague M3 deplace le corps de `services.py` vers `domain/`, un
# domaine par tache : `extract_roof_config` (2 sites) est parti en QJR72,
# `composition_residentielle` part en QJR74, `sync_devis_from_layout` en QJR76.
# A la fin de la vague, `services.py` est une pure facade -- zero `round()` --
# et une liste figee sur ce seul fichier ne surveillerait plus RIEN dans ventes
# tout en restant verte. Le sous-paquet entier est donc scanne : un module de
# `domain/` cree demain est couvert d'office.
#
# QJR143 AJOUTE LES MODULES PDF -- l'audit du 29/08 a montre que la liste
# ci-dessus ne couvrait AUCUN module qui IMPRIME l'argent au client (87
# sites `round()` hors garde, repartis sur ces six fichiers). Le moteur
# calcule dans `builder.py`/`pricing.py`/`bareme.py` puis les paquets par
# marche (agricole/industriel/commercial) et le rendu premium mettent le
# chiffre en page -- les deux bouts de la chaine sont desormais scannes.
TARGET_FILES = [
    VENTES / "services.py",
    VENTES / "quote_engine" / "builder.py",
    VENTES / "quote_engine" / "generate_devis_premium.py",
    VENTES / "quote_engine" / "pricing.py",
    VENTES / "quote_engine" / "bareme.py",
    VENTES / "quote_engine" / "agricole" / "economics.py",
    VENTES / "quote_engine" / "industriel" / "finance.py",
    VENTES / "quote_engine" / "commercial" / "equip.py",
    VENTES / "public_views.py",
    VENTES / "offres_tailles.py",
    VENTES / "taille_detail.py",
    VENTES / "utils" / "options.py",
    VENTES / "selectors.py",
    DJANGO_CORE / "apps" / "compta" / "services.py",
    # AUD189 ELARGIT LE PERIMETRE. La liste ci-dessus ne couvrait NI le rendu
    # legataire des documents client (`ventes/utils/pdf.py` -- la facture,
    # l'avoir et la note de debit y sont mis en page) NI aucune des apps du
    # perimetre R1 nommees par le constat : facturation (la chaine d'argent
    # canonique des documents !), portail, credit, frais, einvoice, plus
    # `compta/selectors.py` et `gestion_projet/services.py`. Un fichier qui
    # calcule ou publie un montant DOIT etre scanne, sans quoi la CI reste
    # verte en laissant croire que la convention est tenue partout.
    VENTES / "utils" / "pdf.py",
    DJANGO_CORE / "apps" / "compta" / "selectors.py",
    DJANGO_CORE / "apps" / "gestion_projet" / "services.py",
    DJANGO_CORE / "apps" / "facturation" / "models.py",
    DJANGO_CORE / "apps" / "facturation" / "totaux.py",
    DJANGO_CORE / "apps" / "facturation" / "services.py",
    DJANGO_CORE / "apps" / "facturation" / "selectors.py",
    DJANGO_CORE / "apps" / "portail" / "services.py",
    DJANGO_CORE / "apps" / "portail" / "selectors.py",
    DJANGO_CORE / "apps" / "credit" / "services.py",
    DJANGO_CORE / "apps" / "credit" / "selectors.py",
    DJANGO_CORE / "apps" / "frais" / "services.py",
    DJANGO_CORE / "apps" / "frais" / "selectors.py",
    DJANGO_CORE / "apps" / "einvoice" / "services.py",
] + sorted(p for p in (VENTES / "domain").glob("*.py"))

MONEY_NAME_RE = re.compile(
    r"(prix|montant|total|_ht|_ttc|tva|remise|acompte|solde|amount|price|"
    r"cost|cout|honoraire|penalite)",
    re.IGNORECASE,
)


class Site:
    """Un site d'arrondi retenu par l'un des deux detecteurs.

    ``kind`` vaut ``'round'`` (detecteur d'origine YDATA8/QJR4) ou
    ``'quantize'`` (AUD189 : un `.quantize(...)` SANS mot-cle `rounding=`,
    donc en arrondi bancaire ROUND_HALF_EVEN -- pas la politique
    moitie-vers-le-haut que `docs/money-convention.md` impose).
    """

    __slots__ = ("path", "lineno", "qualname", "expr", "key", "kind")

    def __init__(self, path, lineno, qualname, expr, key, kind="round"):
        self.path = path
        self.lineno = lineno
        self.qualname = qualname
        self.expr = expr
        self.key = key
        self.kind = kind

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


def _iter_quantize_calls(tree):
    """AUD189 -- rend (noeud Call, qualname) pour chaque `X.quantize(...)`
    appele SANS mot-cle `rounding=`.

    POURQUOI CE SECOND DETECTEUR. `docs/money-convention.md` impose
    `quantize_mad()` = `quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)` et
    explique noir sur blanc que l'arrondi bancaire (le DEFAUT de `Decimal`,
    ROUND_HALF_EVEN) « n'est pas la politique moitie-vers-le-haut attendue en
    comptabilite marocaine ». Le detecteur d'origine ne voyait QUE les appels a
    `round()` : la classe entiere des `quantize` sans mode lui etait invisible,
    et la CI restait verte en laissant croire que la convention etait tenue
    partout. Garde SEMANTIQUE (lecon OR3) : on regarde la FORME de l'appel,
    jamais un nombre de sites epingle.
    """
    found = []

    def visit(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                visit(child, stack + [child.name])
                continue
            if (isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "quantize"
                    and not any(kw.arg == "rounding"
                                for kw in child.keywords)):
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
        raw.append((node.lineno, node.col_offset, qualname, expr, "round"))
    for node, qualname in _iter_quantize_calls(tree):
        # L'expression d'identite est le RECEVEUR (`x` dans `x.quantize(...)`) :
        # c'est lui que l'arrondi transforme, et c'est lui qu'un humain relit.
        expr = normalize_expr(_arg_source(node.func.value))
        if not expr:
            continue
        raw.append((node.lineno, node.col_offset, qualname, expr, "quantize"))
    raw.sort(key=lambda item: (item[0], item[1], item[4]))

    counts = Counter((kind, qualname, expr)
                     for _, _, qualname, expr, kind in raw)
    seen = Counter()
    sites = []
    for lineno, _col, qualname, expr, kind in raw:
        # La cle des sites `round()` reste EXACTEMENT celle d'avant AUD189 :
        # la base de reference livree (170 lignes) ne se perime pas. Les sites
        # `quantize` prennent un sel de type, pour qu'un `round(x)` et un
        # `x.quantize(...)` sur la MEME expression ne se confondent jamais.
        graine = expr if kind == "round" else f"{kind}:{expr}"
        base = f"{rel}::{qualname}::{content_sha(graine)}"
        if counts[(kind, qualname, expr)] > 1:
            seen[(kind, qualname, expr)] += 1
            key = f"{base}#{seen[(kind, qualname, expr)]}"
        else:
            key = base
        sites.append(Site(rel, lineno, qualname, expr, key, kind))
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
# AUD189 -- DEUX DETECTEURS alimentent cette base : `round(x)` sur une valeur
# d'apparence monetaire, et `x.quantize(...)` SANS `rounding=` (arrondi
# bancaire par defaut, contraire a la convention marocaine). Les entrees
# « AUD189 reprise » sont l'existant capture le jour ou le second detecteur est
# ne : la garde protege contre une REINTRODUCTION des aujourd'hui, la reprise
# se fait fichier par fichier ensuite.
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
        defaut = (QUANTIZE_REPRISE_REASON if site.kind == "quantize"
                  else NEW_SITE_REASON)
        reason = existing_reasons.get(site.key) or defaut
        lines.append(f"{site.key} {SEPARATOR} {reason}")
    return "\n".join(lines) + "\n"


def _forme(site):
    """Rendu lisible du site, selon le detecteur qui l'a vu."""
    if site.kind == "quantize":
        return f"{site.expr[:60]}.quantize(...)  # sans rounding="
    return f"round({site.expr[:60]})"


def _print_sites(sites):
    for site in sites:
        print(f"  {site.path}:{site.lineno}  {site.qualname}  "
              f"{_forme(site)}")


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
                  f"{_forme(site)}")
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

    n_round = sum(1 for s in sites if s.kind == "round")
    n_quantize = len(sites) - n_round
    print(f"check_money_rounding: {n_round} site(s) round() sur une valeur "
          f"d'apparence monetaire et {n_quantize} site(s) quantize() sans "
          "rounding= dans les modules de prix/taxe/rendu.")
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
                  f"{_forme(site)}")
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
