"""QJR6 -- garde ADVISORY : un chemin du REGISTRE D'OVERRIDE ne s'ecrit que
dans les modules sanctionnes.

L'audit L3 du 29/08/2026 a trouve QUATRE mecanismes de surcharge incompatibles
(le mecanisme `saisie_manuelle` noms-seuls, des attributs epars poses
directement sur `Devis.etude_params`, des recalculs silencieux a chaque
lecture, et rien du tout pour d'autres champs). Le registre unique
(`Devis.overrides`, QJR58) les remplace tous ; cette garde existe pour qu'AUCUN
nouveau site epars n'apparaisse pendant la transition.

Elle signale trois familles d'ecritures :

  (A) une ecriture sur `etude_params` qui touche un CHEMIN DU REGISTRE --
      `etude_params['scenario'] = ...`, `etude_params['taille']['kwc'] = ...`,
      `etude_params.update({'scenario': ...})`, `setdefault`/`pop`, ou une
      ecriture a CLE DYNAMIQUE (`etude_params[k] = ...`, qui pourrait etre
      n'importe quel chemin) ;
  (B) une ecriture de `LigneDevis.quantite` / `.prix_unitaire` dans
      `apps/ventes` -- affectation d'attribut (`ligne.quantite = ...`) ou
      `.update(quantite=...)` sur un queryset ;
  (C) QJR105 -- un REMPLACEMENT EN BLOC de `etude_params` :
      `devis.etude_params = <n'importe quoi>` (dict litteral ou variable) ou
      `.update(etude_params=...)` sur un queryset, hors du SEUL ecrivain
      sanctionne `apps/ventes/domain/etude_schema.py`.

POURQUOI LA FAMILLE (C) EXISTE. Le bug qu'elle empeche de revenir est celui
que QJR62 a ferme : l'ecran sauvegardait le devis en RECONSTRUISANT
`etude_params` de zero, si bien que chaque cle qu'il ne reconstruit pas
lui-meme -- `factures_mensuelles_reelles`, `gamme`, et tout ce que les quatre
rafraichisseurs du serveur avaient ecrit -- DISPARAISSAIT a la sauvegarde
suivante. Une affectation en bloc est une SUPPRESSION SILENCIEUSE de tout ce
que l'ecrivain ne reconstruit pas : c'est `etude_schema.ecrire` (fusion cle a
cle, proprietaire declare) qui doit ecrire, et lui seul. La garde vaut cote
BACKEND comme cote SERIALISEUR -- elle scanne toute la surface de production,
sans exception de couche.

Les modules SANCTIONNES (`apps/ventes/domain/overrides.py`,
`apps/ventes/domain/lignes.py`) sont exemptes des familles (A) et (B) : ce sont
eux, a terme, les seuls ecrivains. `apps/ventes/domain/etude_schema.py` est
exempte de la SEULE famille (C) -- il reste scanne pour (A) et (B).

LES CHEMINS DU REGISTRE NE SONT JAMAIS RECOPIES ICI : ils sont lus a chaque
execution dans le contrat PACT10 QJR1
(`apps/ventes/contract_samples/devis_overrides.json`, cle
`notes.chemins_autorises`). Ajouter un chemin au contrat elargit donc la garde
sans toucher ce script -- et un chemin retire du contrat cesse d'etre garde,
volontairement : le contrat est la seule source de verite de la liste blanche
(decision fondateur D12 du 29/08/2026).

DB-free, AST seul (patron de `scripts/check_read_modify_write.py` pour la
mecanique de scan, de `scripts/check_money_rounding.py` pour la CLE D'IDENTITE
DE CONTENU et le format de la base).

    <chemin>::<qualname englobant>::<famille>::<cible>

  * `chemin`   -- chemin POSIX relatif a la racine du depot ;
  * `qualname` -- marche des parents AST (`Classe.methode`) ; `<module>` au
    niveau module ;
  * `famille`  -- `etude_params`, `ligne` ou `etude_params_bloc` ;
  * `cible`    -- le chemin ecrit (`scenario`, `taille.kwc`,
    `profil.equipements.piscine`, `<clef dynamique>`) ou `obj.attribut`.

Jamais un numero de ligne : inserer du code en amont ne perime pas la base
(l'ancienne base file:line de `check_money_rounding` a coute dix recalages
manuels sur le seul mois d'aout 2026). Deux sites identiques dans la meme
fonction sont departages par `#1` / `#2` dans l'ordre du source.

v1 ADVISORY : chaque site present dans l'arbre au moment de la capture est
inscrit dans `scripts/override_registry_allow.txt` avec sa raison humaine. La
garde echoue uniquement sur un site NOUVEAU, c.-a-d. jamais relu.

Usage:
    python scripts/check_override_registry.py              # controle (CI)
    python scripts/check_override_registry.py --list       # tous les sites vus
    python scripts/check_override_registry.py --regenerate # reecrit la base
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
VENTES = APPS_DIR / "ventes"
CONTRACT_PATH = VENTES / "contract_samples" / "devis_overrides.json"
ALLOWLIST_PATH = ROOT / "scripts" / "override_registry_allow.txt"

MODULE_QUALNAME = "<module>"
SEPARATOR = "|"
NEW_SITE_REASON = "A RELIRE -- capture par --regenerate, raison a completer."

#: Le champ JSON qui porte les surcharges eparses d'aujourd'hui.
ETUDE_PARAMS = "etude_params"
#: Les deux champs de ligne qu'un override de ligne pilote (QJR59).
LIGNE_ATTRS = ("quantite", "prix_unitaire")
#: Cible affichee quand la clef ecrite n'est pas une constante lisible.
DYNAMIC_TARGET = "<clef dynamique>"
#: Motif du chemin a joker du contrat (`profil.equipements.<clef>`).
WILDCARD = "<clef>"

FAMILY_ETUDE = "etude_params"
FAMILY_LIGNE = "ligne"
#: QJR105 -- le REMPLACEMENT EN BLOC de `etude_params`.
FAMILY_BLOC = "etude_params_bloc"

#: Les seuls modules autorises a ecrire un chemin du registre (M3/M5 les
#: posent ; ils n'existent pas encore, la garde les exempte d'avance).
SANCTIONED = (
    "backend/django_core/apps/ventes/domain/overrides.py",
    "backend/django_core/apps/ventes/domain/lignes.py",
)

#: QJR105 -- le SEUL ecrivain autorise a REMPLACER `etude_params` en bloc.
#: Il n'est PAS dans `SANCTIONED` : il reste scanne pour les familles (A) et
#: (B), seule la famille (C) l'exempte. Une exemption plus large lui donnerait
#: le droit d'ecrire des chemins du registre a la main -- ce n'est pas son
#: role, et personne ne le verrait.
SANCTIONED_BLOC = (
    "backend/django_core/apps/ventes/domain/etude_schema.py",
)


class Site:
    """Un site d'ecriture retenu par le detecteur."""

    __slots__ = ("path", "lineno", "qualname", "family", "target", "key")

    def __init__(self, path, lineno, qualname, family, target, key):
        self.path = path
        self.lineno = lineno
        self.qualname = qualname
        self.family = family
        self.target = target
        self.key = key

    def __repr__(self):  # pragma: no cover - confort de debogage
        return f"<Site {self.key} ligne {self.lineno}>"


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


# --------------------------------------------------------------------------
# Les chemins du registre : LUS dans le contrat QJR1, jamais recopies.
# --------------------------------------------------------------------------


def load_registry_paths(path: Path = CONTRACT_PATH):
    """Rend la liste des chemins du registre declares par le contrat QJR1.

    Leve `FileNotFoundError` / `KeyError` si le contrat manque ou a perdu sa
    cle : c'est une panne de configuration, pas un site a signaler.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    chemins = data["notes"]["chemins_autorises"]
    if not isinstance(chemins, list) or not chemins:
        raise KeyError("notes.chemins_autorises est vide")
    return [str(c) for c in chemins]


def _wildcard_base(chemin: str) -> str:
    """`profil.equipements.<clef>` -> `profil.equipements` (sinon inchange)."""
    marker = "." + WILDCARD
    if chemin.endswith(marker):
        return chemin[: -len(marker)]
    return chemin


def path_touches_registry(written: str, registry_paths) -> bool:
    """True si l'ecriture du chemin `written` touche un chemin du registre.

    Trois relations comptent, toutes des ecritures reelles du chemin garde :

      * egalite            -- `scenario` ecrit `scenario` ;
      * `written` en amont -- `taille` ecrit tout le sous-arbre, donc
        `taille.nb_panneaux` ;
      * `written` en aval  -- `profil.equipements.piscine.puissance_kw` ecrit
        a l'interieur de `profil.equipements.<clef>`.
    """
    if not written:
        return False
    for chemin in registry_paths:
        base = _wildcard_base(chemin)
        if written == base:
            return True
        if written.startswith(base + "."):
            return True
        if base.startswith(written + "."):
            return True
    return False


# --------------------------------------------------------------------------
# Mecanique AST
# --------------------------------------------------------------------------


def _base_name(node):
    """Nom terminal d'une base : `etude_params` ou `devis.etude_params`."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _subscript_chain(node):
    """Rend (nom de base, [clefs]) pour `a['x']['y']`; clef inconnue = None."""
    keys = []
    cur = node
    while isinstance(cur, ast.Subscript):
        sl = cur.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            keys.append(sl.value)
        else:
            keys.append(None)
        cur = cur.value
    keys.reverse()
    return _base_name(cur), keys


def _written_path(keys):
    """Chemin pointe ecrit par une chaine de clefs, arretee a la 1re dynamique.

    Rend `None` si la toute premiere clef est dynamique : on ne sait alors
    RIEN du chemin ecrit (il pourrait etre n'importe lequel du registre) --
    l'appelant le signale comme `<clef dynamique>`.
    """
    parts = []
    for key in keys:
        if key is None:
            break
        parts.append(key)
    if not parts:
        return None
    return ".".join(parts)


def _keyword_names(call):
    return [kw.arg for kw in call.keywords if kw.arg]


def _dict_string_keys(node):
    """Clefs constantes d'un litteral dict ; `None` marque une clef dynamique."""
    if not isinstance(node, ast.Dict):
        return []
    out = []
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            out.append(key.value)
        else:
            out.append(None)
    return out


def _iter_nodes_with_qualname(tree):
    """Rend (noeud, qualname englobant) pour chaque noeud de l'arbre."""
    found = []

    def visit(node, stack):
        for child in ast.iter_child_nodes(node):
            qual = ".".join(stack) if stack else MODULE_QUALNAME
            found.append((child, qual))
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                visit(child, stack + [child.name])
            else:
                visit(child, stack)

    visit(tree, [])
    return found


def _assign_targets(node):
    if isinstance(node, ast.Assign):
        return list(node.targets)
    if isinstance(node, (ast.AugAssign, ast.AnnAssign)):
        return [node.target]
    return []


def _etude_params_sites(node, qualname, registry_paths):
    """Sites de la famille (A) portes par ce noeud."""
    out = []
    for target in _assign_targets(node):
        if not isinstance(target, ast.Subscript):
            continue
        base, keys = _subscript_chain(target)
        if base != ETUDE_PARAMS:
            continue
        written = _written_path(keys)
        if written is None:
            out.append((FAMILY_ETUDE, DYNAMIC_TARGET))
        elif path_touches_registry(written, registry_paths):
            out.append((FAMILY_ETUDE, written))

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        method = node.func.attr
        if (method in ("update", "setdefault", "pop")
                and _base_name(node.func.value) == ETUDE_PARAMS):
            candidates = []
            if method == "update":
                for arg in node.args:
                    candidates.extend(_dict_string_keys(arg))
                candidates.extend(_keyword_names(node))
            else:  # setdefault / pop : la clef est le 1er argument
                if node.args:
                    first = node.args[0]
                    if (isinstance(first, ast.Constant)
                            and isinstance(first.value, str)):
                        candidates.append(first.value)
                    else:
                        candidates.append(None)
            for cand in candidates:
                if cand is None:
                    out.append((FAMILY_ETUDE, DYNAMIC_TARGET))
                elif path_touches_registry(cand, registry_paths):
                    out.append((FAMILY_ETUDE, cand))
    return out


def _ligne_sites(node):
    """Sites de la famille (B) portes par ce noeud."""
    out = []
    for target in _assign_targets(node):
        if isinstance(target, ast.Attribute) and target.attr in LIGNE_ATTRS:
            holder = _base_name(target.value) or "?"
            out.append((FAMILY_LIGNE, f"{holder}.{target.attr}"))

    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "update":
            for name in _keyword_names(node):
                if name in LIGNE_ATTRS:
                    out.append((FAMILY_LIGNE, f"update({name}=...)"))
    return out


def _bloc_sites(node):
    """Sites de la famille (C) portes par ce noeud -- QJR105.

    Deux formes, et deux seulement :

      * `<porteur>.etude_params = <quoi que ce soit>` -- affectation
        d'ATTRIBUT (jamais un `Subscript`, qui est la famille (A) : ecrire UNE
        cle n'est pas remplacer le bloc) ;
      * `.update(etude_params=...)` sur un queryset -- le meme remplacement,
        en masse et sans passer par l'instance.

    LE CONTENU DE LA DROITE N'EST PAS REGARDE, ET C'EST VOULU. `etude_schema.
    ecrire` ne rend RIEN a affecter : il ecrit lui-meme, cle a cle, avec un
    proprietaire declare. Toute affectation en bloc hors de lui est donc, par
    construction, une reconstruction -- litterale ou depuis une variable, le
    resultat pour les cles absentes est le meme : elles disparaissent.
    """
    out = []
    for target in _assign_targets(node):
        if isinstance(target, ast.Attribute) and target.attr == ETUDE_PARAMS:
            holder = _base_name(target.value) or "?"
            out.append((FAMILY_BLOC, f"{holder}.{ETUDE_PARAMS}"))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if (node.func.attr == "update"
                and ETUDE_PARAMS in _keyword_names(node)):
            out.append((FAMILY_BLOC, f"update({ETUDE_PARAMS}=...)"))
    return out


def collect_sites_in_source(source, rel, registry_paths, scan_lignes=True,
                            scan_bloc=True):
    """Rend les Site trouves dans ce source, en ordre de source."""
    tree = ast.parse(source)
    raw = []
    for node, qualname in _iter_nodes_with_qualname(tree):
        hits = _etude_params_sites(node, qualname, registry_paths)
        if scan_lignes:
            hits = hits + _ligne_sites(node)
        if scan_bloc:
            hits = hits + _bloc_sites(node)
        for family, target in hits:
            raw.append((getattr(node, "lineno", 0),
                        getattr(node, "col_offset", 0),
                        qualname, family, target))
    raw.sort()

    counts = Counter((q, f, t) for _, _, q, f, t in raw)
    seen = Counter()
    sites = []
    for lineno, _col, qualname, family, target in raw:
        base = f"{rel}::{qualname}::{family}::{target}"
        if counts[(qualname, family, target)] > 1:
            seen[(qualname, family, target)] += 1
            key = f"{base}#{seen[(qualname, family, target)]}"
        else:
            key = base
        sites.append(Site(rel, lineno, qualname, family, target, key))
    return sites


# --------------------------------------------------------------------------
# Surface scannee
# --------------------------------------------------------------------------


def _is_test_file(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return ("/tests/" in rel or name == "tests.py"
            or name.startswith("test_") or name.startswith("tests_")
            or name.endswith("_tests.py"))


def _skip(rel: str) -> bool:
    return ("/migrations/" in rel or _is_test_file(rel)
            or rel in SANCTIONED)


def iter_scanned_files():
    """Rend (chemin, scan_lignes, scan_bloc) pour chaque module scanne.

    Famille (A) : tout `apps/**` (le champ `etude_params` est lu et ecrit
    au-dela de `ventes`). Famille (B) : `apps/ventes/**` seulement -- c'est la
    ou vit `LigneDevis` ; les `.quantite` de `stock`/`installations` sont un
    AUTRE modele et n'ont rien a voir avec le registre. Famille (C) : tout
    `apps/**` SAUF l'ecrivain sanctionne -- un remplacement en bloc de
    `etude_params` est aussi dangereux depuis `crm` ou `contrats` que depuis
    `ventes`.
    """
    if not APPS_DIR.is_dir():
        return
    for path in sorted(APPS_DIR.rglob("*.py")):
        rel = _rel(path)
        if _skip(rel):
            continue
        yield (path,
               rel.startswith("backend/django_core/apps/ventes/"),
               rel not in SANCTIONED_BLOC)


def collect_sites_in_file(path: Path, registry_paths, scan_lignes,
                          scan_bloc=True):
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        return collect_sites_in_source(source, _rel(path), registry_paths,
                                       scan_lignes=scan_lignes,
                                       scan_bloc=scan_bloc)
    except SyntaxError as exc:  # pragma: no cover - fichier casse
        print(f"check_override_registry: {_rel(path)} illisible ({exc})")
        return []


def scan(registry_paths=None):
    """Scanne la surface de production et rend la liste des sites."""
    if registry_paths is None:
        registry_paths = load_registry_paths()
    sites = []
    for path, scan_lignes, scan_bloc in iter_scanned_files():
        sites.extend(collect_sites_in_file(path, registry_paths, scan_lignes,
                                           scan_bloc))
    return sites


# --------------------------------------------------------------------------
# Base de reference
# --------------------------------------------------------------------------


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
# Base de reference de scripts/check_override_registry.py (QJR6).
#
# FORMAT : une cle par ligne, puis une colonne de raison humaine separee par
# `|` (patron de scripts/money_rounding_allow.txt). Les lignes vides et celles
# commencant par `#` sont ignorees.
#
#   <chemin>::<qualname englobant>::<famille>::<cible> | raison
#
# La cle est une IDENTITE DE CONTENU, jamais un numero de ligne : inserer du
# code en amont ne perime pas la base. Renommer la fonction englobante ou
# changer la cible change la cle -- c'est voulu, ce sont les deux evenements
# qu'un humain doit relire.
#
# La garde est ADVISORY (v1) : les sites ci-dessous sont l'existant releve au
# moment de la capture. Un site NOUVEAU fait echouer backend-lint, le temps
# qu'un humain ecrive sa raison ici -- ou, mieux, passe l'ecriture par
# apps/ventes/domain/overrides.py / lignes.py (familles A et B) ou par
# apps/ventes/domain/etude_schema.ecrire (famille C, QJR105 : `etude_params`
# ne se remplace jamais en bloc).
#
# Les chemins gardes viennent du contrat QJR1
# (apps/ventes/contract_samples/devis_overrides.json), jamais de ce fichier.
#
# Regenerer apres une revue :
#   python scripts/check_override_registry.py --regenerate
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Garde advisory sur les ecritures de chemins du registre "
                    "d'override.")
    parser.add_argument("--list", action="store_true", dest="list_mode",
                        help="imprime chaque site vu, avec sa cle")
    parser.add_argument("--regenerate", action="store_true",
                        help="reecrit scripts/override_registry_allow.txt "
                             "depuis l'arbre courant (raisons conservees)")
    args = parser.parse_args(argv)

    try:
        registry_paths = load_registry_paths()
    except (OSError, ValueError, KeyError) as exc:
        print("check_override_registry: contrat QJR1 illisible "
              f"({_rel(CONTRACT_PATH)}) : {exc}")
        print("  Les chemins gardes sont LUS dans ce contrat, jamais "
              "recopies dans le script.")
        return 1

    sites = scan(registry_paths)

    if args.list_mode:
        for site in sites:
            print(f"{site.key} | {site.path}:{site.lineno}")
        return 0

    if args.regenerate:
        existing = load_allowlist()
        ALLOWLIST_PATH.write_text(render_allowlist(sites, existing),
                                  encoding="utf-8")
        print(f"check_override_registry: {len(sites)} site(s) ecrit(s) dans "
              f"{_rel(ALLOWLIST_PATH)}.")
        print("  ATTENTION : la base a ete REECRITE. Les raisons par cle sont "
              "conservees, mais les BLOCS DE COMMENTAIRE libres du fichier "
              "(les notes de re-clage QJR76/QJR95/QJR97, la note de la "
              "famille C) sont PERDUS -- relire le diff avant de commettre.")
        return 0

    allowed = load_allowlist()
    offenders, orphans = evaluate(sites, allowed)

    print(f"check_override_registry: {len(registry_paths)} chemin(s) du "
          f"registre lus dans {_rel(CONTRACT_PATH)} ; {len(sites)} site(s) "
          "d'ecriture dans la surface de production.")
    for site in sites:
        print(f"  {site.path}:{site.lineno}  {site.qualname}  "
              f"[{site.family}] {site.target}")

    if orphans:
        print("\ncheck_override_registry: entree(s) ORPHELINE(S) dans "
              f"{_rel(ALLOWLIST_PATH)} (le site n'existe plus ou sa cible a "
              "change) -- signale, ne bloque pas :")
        for key in orphans:
            print(f"  - {key}")
        print("  Nettoyer avec: python scripts/check_override_registry.py "
              "--regenerate")

    if offenders:
        print("\ncheck_override_registry: site(s) NOUVEAU(X) absent(s) de "
              f"{_rel(ALLOWLIST_PATH)} :")
        for site in offenders:
            print(f"  - {site.path}:{site.lineno} ({site.qualname}) "
                  f"[{site.family}] {site.target}")
            print(f"    cle: {site.key}")
        print("\nUn chemin du registre d'override s'ecrit dans "
              "apps/ventes/domain/overrides.py (ou lignes.py pour "
              "quantite/prix_unitaire) -- jamais ailleurs.")
        if any(site.family == FAMILY_BLOC for site in offenders):
            print("`etude_params` ne se REMPLACE JAMAIS EN BLOC (QJR105) : "
                  "une affectation `devis.etude_params = <bloc>` SUPPRIME "
                  "en silence toutes les cles que l'ecrivain ne reconstruit "
                  "pas. Passer par apps/ventes/domain/etude_schema.ecrire "
                  "(fusion cle a cle, proprietaire declare).")
        print("Si ce site est legitime pendant la transition, ajouter sa cle "
              f"et sa raison dans {_rel(ALLOWLIST_PATH)} (ou --regenerate "
              "puis ecrire la raison).")
        return 1

    print("\ncheck_override_registry: OK (advisory -- tous les sites sont "
          "dans la base).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
