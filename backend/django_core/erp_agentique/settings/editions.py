"""SOL1 — Registre STATIQUE des éditions produit de TAQINOR OS.

Contexte (décision fondateur du 02/09/2026, plan V5b). TAQINOR OS se vend comme
ERP **spécialisé solaire**. Deux niveaux, jamais de suppression de code ni de
table :

* **ÉDITION (build)** — les verticaux non adaptables sortent du build de
  l'édition solaire. ``TAQINOR_EDITION`` filtre ``INSTALLED_APPS``, les
  ``include()`` d'urls et le bundle frontend. Les migrations et les tables
  restent intactes : réactiver une app parquée = re-flipper le profil.
* **MODULE OFF PAR DÉFAUT (runtime)** — ``ModuleToggle``, hors périmètre de ce
  fichier.

Pourquoi un registre **statique** et pas une lecture des ``AppConfig`` ? Parce
qu'une app parquée n'est PAS chargée : son ``AppConfig`` n'existe pas, donc son
``module_manifest`` (et son libellé) sont inatteignables. Le préflight de
bascule (SOL13), les messages d'erreur et les écrans d'administration doivent
malgré tout pouvoir NOMMER une app parquée — d'où les libellés FR figés
ci-dessous, volontairement indépendants des ``AppConfig``.

Ce module est du **pur Python sans Django** : il est importé par
``settings/base.py`` avant toute initialisation d'application, et par des
scripts hôte (gardes CI) qui n'ont pas de settings chargés.
"""
from __future__ import annotations

import os

# ─────────────────────────────────────────────────────────────────────────────
# Éditions connues
# ─────────────────────────────────────────────────────────────────────────────
EDITION_FULL = 'full'
EDITION_SOLAR = 'solar'

#: Édition par défaut — dev, tests et CI tournent en ``full`` (zéro churn
#: openapi/baselines). La PROD vise ``solar`` (bascule exécutée par le run qui
#: termine le groupe SOL, après le préflight SOL13).
DEFAULT_EDITION = EDITION_FULL

EDITIONS = (EDITION_FULL, EDITION_SOLAR)

#: Nom de la variable d'environnement qui sélectionne l'édition.
ENV_VAR = 'TAQINOR_EDITION'


# ─────────────────────────────────────────────────────────────────────────────
# Apps parquées par édition
# ─────────────────────────────────────────────────────────────────────────────
# Chemin d'app (tel qu'il apparaît dans INSTALLED_APPS) →
#   (clé de module ODX2, libellé FR figé).
#
# Les sept apps ci-dessous sont les VERTICAUX non adaptables à un installateur
# solaire. Elles portent toutes un ``sku`` ``vertical_*`` dans leur manifeste ;
# la cohérence tags ↔ registre est gardée par
# ``core/tests/test_editions_registre.py``.
_PARQUEES_SOLAR = {
    'apps.agriculture': ('agriculture', 'Agriculture'),
    'apps.ecommerce_connect': (
        'ecommerce_connect', 'Connecteurs e-commerce'),
    'apps.education': ('education', 'Éducation'),
    'apps.hospitality': ('hospitality', 'Hôtellerie & restauration'),
    'apps.immobilier': ('immobilier', 'Immobilier & facilities'),
    'apps.mrp': ('mrp', 'Production (MRP)'),
    'apps.sante': ('sante', 'Santé (cabinet/clinique)'),
}

#: édition → {chemin d'app: (clé de module, libellé FR)}
PARKED_APPS = {
    EDITION_FULL: {},
    EDITION_SOLAR: dict(_PARQUEES_SOLAR),
}


class EditionInconnue(ValueError):
    """``TAQINOR_EDITION`` porte une valeur qui n'est pas une édition connue."""


def normaliser_edition(valeur):
    """Normalise une valeur d'édition (``None``/vide → défaut).

    Lève ``EditionInconnue`` sur une valeur non vide inconnue : une coquille
    (``TAQINOR_EDITION=solaire``) doit ÉCHOUER au boot, jamais retomber
    silencieusement sur l'édition complète en production.
    """
    if valeur is None:
        return DEFAULT_EDITION
    valeur = str(valeur).strip().lower()
    if not valeur:
        return DEFAULT_EDITION
    if valeur not in EDITIONS:
        raise EditionInconnue(
            f'Édition « {valeur} » inconnue ({ENV_VAR}). '
            f'Éditions connues : {", ".join(EDITIONS)}.')
    return valeur


def edition_active(env=None):
    """Édition sélectionnée par l'environnement (défaut : ``full``)."""
    source = os.environ if env is None else env
    return normaliser_edition(source.get(ENV_VAR))


def apps_parquees(edition=None):
    """``{chemin d'app: libellé FR}`` des apps parquées par cette édition."""
    edition = normaliser_edition(edition) if edition is not None \
        else edition_active()
    return {
        chemin: libelle
        for chemin, (_cle, libelle) in PARKED_APPS.get(edition, {}).items()
    }


def modules_parques(edition=None):
    """Clés de module (manifeste ODX2) parquées par cette édition."""
    edition = normaliser_edition(edition) if edition is not None \
        else edition_active()
    return frozenset(
        cle for cle, _libelle in PARKED_APPS.get(edition, {}).values())


def est_app_parquee(chemin_app, edition=None):
    """Vrai si ``chemin_app`` (ex. ``apps.mrp``) est parqué par l'édition."""
    return chemin_app in apps_parquees(edition)


def est_module_parque(chemin_module, edition=None):
    """Vrai si un module Python appartient à une app parquée.

    ``chemin_module`` peut être l'app elle-même (``apps.mrp``) ou n'importe
    quel sous-module (``apps.mrp.urls``, ``apps.education.public_urls``).
    Utilisé par ``urls.py`` AVANT d'appeler ``include()`` : appeler
    ``include('apps.mrp.urls')`` importerait l'app parquée (donc ses modèles)
    et casserait le boot.
    """
    parquees = apps_parquees(edition)
    if chemin_module in parquees:
        return True
    return any(
        chemin_module.startswith(chemin + '.') for chemin in parquees)


def filtrer_installed_apps(installed_apps, edition=None):
    """Retire d'``INSTALLED_APPS`` les apps parquées par l'édition."""
    parquees = apps_parquees(edition)
    return [app for app in installed_apps if app not in parquees]


def filtrer_chemins(mapping, edition=None):
    """Retire d'un mapping ``{nom: 'apps.<x>.models…'}`` les apps parquées.

    Sert à ``SPECTACULAR_SETTINGS['ENUM_NAME_OVERRIDES']`` (SOL2d) : un
    override qui pointe vers une app non chargée ferait planter la génération
    de schéma.
    """
    return {
        nom: chemin for nom, chemin in mapping.items()
        if not est_module_parque(chemin, edition)
    }
