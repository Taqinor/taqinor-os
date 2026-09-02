"""ODX2 — Collecteur de manifests de modules (façon Odoo ``__manifest__.py``).

Chaque ``AppConfig`` déclare un attribut ``module_manifest`` (un dict) décrivant
son module : clé ``ModuleToggle``, libellé FR, icône, dépendances, installable,
catégorie. ``core`` collecte ces manifests de façon GÉNÉRIQUE via
``django.apps.get_app_configs()`` : il ne fait que LIRE un attribut sur chaque
``AppConfig``, sans importer aucun module métier — le contrat import-linter
``core-foundation-is-a-base-layer`` reste vert.

Un manifest a la forme ::

    module_manifest = {
        'key': 'sav',                 # clé ModuleToggle (unique, obligatoire)
        'label': 'Après-vente',       # libellé FR (obligatoire)
        'icone': 'wrench',            # réf. icône frontend (optionnel)
        'depends': ['crm'],           # clés d'autres modules (optionnel)
        'installable': True,          # activable/désactivable (défaut True)
        'description': '…',           # (optionnel)
        'categorie': 'Services',      # Ventes/Finance/RH/Stock/Services/…
        'sku': 'solar_core',          # SOL1 — appartenance à l'édition
    }

Les apps techniques/fondation (roles, records, customfields, parametres,
authentication, core, audit, publicapi, dataimport…) portent
``installable=False`` : elles apparaissent dans le graphe mais ne se
désactivent pas.

SOL1 — le champ ``sku``
-----------------------

``sku`` dit à quel TITRE le module fait partie du produit :

* ``solar_core``    — cœur du métier installateur solaire (devis, chantiers,
  stock, SAV…). Jamais parqué, jamais off par défaut.
* ``generic``       — ERP transverse utile à toute PME (compta, RH, GED…).
  Gardé actif dans l'édition solaire.
* ``optional``      — livré mais ``ModuleToggle`` OFF à la création d'un
  tenant (SOL8) : rare chez un installateur (POS, douane, transport, SCM…)
  ou dépendant du pack pays (facturation électronique, fiscal, paie).
* ``vertical_<x>``  — vertical métier non adaptable : SORTI du build de
  l'édition solaire (registre ``erp_agentique/settings/editions.py``).

La cohérence tags ↔ registre d'éditions est gardée par
``core/tests/test_editions_registre.py`` : tout module ``vertical_*`` est
parqué dans l'édition solaire, et réciproquement.
"""
from __future__ import annotations

# SOL1 — vocabulaire des « sku » de manifeste.
SKU_SOLAR_CORE = 'solar_core'
SKU_GENERIC = 'generic'
SKU_OPTIONAL = 'optional'
SKU_VERTICAL_PREFIX = 'vertical_'
#: sku sans suffixe (les verticaux portent ``vertical_<x>``).
SKUS_SIMPLES = frozenset({SKU_SOLAR_CORE, SKU_GENERIC, SKU_OPTIONAL})

CATEGORIES = {
    'Ventes', 'Finance', 'RH', 'Stock', 'Services', 'Marketing', 'Technique',
    # Regroupement commercial transverse (appels d'offres, marketing, portail
    # client) — modules ao/marketing/portail.
    'Commercial',
    # Verticaux métier (secteurs d'activité) — agriculture, hôtellerie,
    # BTP/chantier, immobilier, ESG…
    'Verticaux',
}


class ManifestError(ValueError):
    """Erreur de validation du graphe de manifests de modules."""


def sku_valide(sku):
    """Vrai si ``sku`` appartient au vocabulaire SOL1."""
    if not isinstance(sku, str) or not sku:
        return False
    if sku in SKUS_SIMPLES:
        return True
    return (
        sku.startswith(SKU_VERTICAL_PREFIX)
        and len(sku) > len(SKU_VERTICAL_PREFIX)
    )


def est_vertical(sku):
    """Vrai si ``sku`` désigne un vertical métier (``vertical_<x>``)."""
    return bool(sku) and str(sku).startswith(SKU_VERTICAL_PREFIX)


def _normaliser(app_config, manifest):
    """Renvoie une copie normalisée d'un manifest (défauts appliqués)."""
    key = manifest.get('key')
    # SOL1 — le sku est OPTIONNEL au runtime (défaut « generic », donc aucune
    # app neuve ne casse le boot en l'oubliant) mais sa VALEUR est validée, et
    # sa présence explicite est exigée par la garde de test.
    sku = manifest.get('sku', SKU_GENERIC)
    if not sku_valide(sku):
        raise ManifestError(
            f"Manifest de l'app « {app_config.label} » : sku « {sku} » "
            f"inconnu (attendu : {', '.join(sorted(SKUS_SIMPLES))} ou "
            f"« {SKU_VERTICAL_PREFIX}<x> »).")
    out = {
        'key': key,
        'label': manifest.get('label') or key or app_config.label,
        'icone': manifest.get('icone', ''),
        'depends': list(manifest.get('depends') or []),
        'installable': bool(manifest.get('installable', True)),
        'description': manifest.get('description', ''),
        'categorie': manifest.get('categorie', 'Technique'),
        'sku': sku,
        'app_label': app_config.label,
    }
    return out


def collect_manifests():
    """Collecte les manifests de toutes les apps installées.

    Renvoie ``{key: manifest_normalise}``. GÉNÉRIQUE : lit l'attribut
    ``module_manifest`` sur chaque ``AppConfig`` via ``get_app_configs()`` — zéro
    import d'app métier.
    """
    from django.apps import apps as django_apps

    out = {}
    for app_config in django_apps.get_app_configs():
        manifest = getattr(app_config, 'module_manifest', None)
        if not manifest:
            continue
        norm = _normaliser(app_config, manifest)
        key = norm['key']
        if not key:
            raise ManifestError(
                f"Manifest de l'app « {app_config.label} » sans clé « key ».")
        if key in out:
            raise ManifestError(
                f'Clé de module dupliquée : « {key} » (apps '
                f'{out[key]["app_label"]} et {norm["app_label"]}).')
        out[key] = norm
    return out


def valider_graphe(manifests=None):
    """Valide le graphe de manifests : dépendances existantes, pas de cycle.

    Lève ``ManifestError`` au premier problème. Renvoie ``manifests`` en cas de
    succès (pratique en test).
    """
    if manifests is None:
        manifests = collect_manifests()

    # (a) toute dépendance pointe vers un manifest existant.
    for key, manifest in manifests.items():
        for dep in manifest['depends']:
            if dep not in manifests:
                raise ManifestError(
                    f'Le module « {key} » dépend de « {dep} » qui n\'a pas de '
                    'manifest.')

    # (b) aucun cycle dans le graphe de dépendances (DFS 3 couleurs).
    WHITE, GRAY, BLACK = 0, 1, 2
    couleur = {key: WHITE for key in manifests}

    def visiter(key, pile):
        couleur[key] = GRAY
        pile.append(key)
        for dep in manifests[key]['depends']:
            if couleur[dep] == GRAY:
                cycle = ' → '.join(pile[pile.index(dep):] + [dep])
                raise ManifestError(
                    f'Cycle de dépendances entre modules : {cycle}.')
            if couleur[dep] == WHITE:
                visiter(dep, pile)
        pile.pop()
        couleur[key] = BLACK

    for key in manifests:
        if couleur[key] == WHITE:
            visiter(key, [])

    return manifests


def dependency_closure(key, manifests=None):
    """Fermeture transitive des dépendances d'un module (clé incluse exclue).

    Renvoie l'ensemble des clés dont ``key`` dépend, directement ou non.
    Suppose un graphe déjà validé (sans cycle).
    """
    if manifests is None:
        manifests = collect_manifests()
    out = set()
    pile = list(manifests.get(key, {}).get('depends', []))
    while pile:
        dep = pile.pop()
        if dep in out or dep not in manifests:
            continue
        out.add(dep)
        pile.extend(manifests[dep]['depends'])
    return out


def dependents(key, manifests=None):
    """Modules qui dépendent (directement) de ``key``."""
    if manifests is None:
        manifests = collect_manifests()
    return {
        other for other, manifest in manifests.items()
        if key in manifest['depends']
    }
