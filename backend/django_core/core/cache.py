"""NTPLT22 — Clés de cache PAR TENANT + invalidation par événement.

Deux besoins de fondation, réunis ici sans aucune dépendance d'app métier
(``core`` reste une couche de base — contrat import-linter) :

1. ``tenant_key(company_id, name)`` — préfixe TOUTE clé de cache par
   ``t:{company_id}:`` pour qu'aucune société ne puisse jamais lire l'entrée
   d'une autre. Deux tenants qui mettent en cache ``"canaux"`` obtiennent des
   clés physiquement distinctes.

2. ``invalidate_on(model, names)`` — enregistre qu'à chaque ``post_save`` /
   ``post_delete`` d'un ``model``, les clés ``names`` de la société de
   l'instance (le champ ``company``) doivent être invalidées. Le registre est
   branché sur les signaux Django au premier enregistrement : modifier UN
   référentiel n'invalide que la clé de CE tenant, jamais celles des autres.

``core`` ne connaît AUCUN modèle métier : c'est chaque app qui appelle
``invalidate_on(SonModele, [...])`` dans son ``apps.py`` ``ready()`` — même
pattern que ``core.retention`` / ``core.search_registry``. Le module tolère
une panne du backend de cache (best-effort : une invalidation qui échoue ne
casse jamais un ``save()``).
"""
from __future__ import annotations

import logging

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save

logger = logging.getLogger(__name__)

# Préfixe de toutes les clés multi-tenant : ``t:{company_id}:{name}``.
_PREFIX = 't'

# Registre {model_dotted_path -> set(names)} peuplé par ``invalidate_on``.
# On garde le CHEMIN (app_label.ModelName) plutôt que la classe pour éviter
# toute résolution prématurée de modèle au moment de l'enregistrement.
_INVALIDATION: dict = {}

# Garde-fou : on ne connecte les récepteurs de signaux qu'une seule fois.
_CONNECTED = False


def tenant_key(company_id, name: str) -> str:
    """Clé de cache scopée société : ``t:{company_id}:{name}``.

    ``company_id`` peut être ``None`` (entrée système transverse) — la clé
    devient ``t:sys:{name}``, distincte de toute clé société.
    """
    scope = company_id if company_id is not None else 'sys'
    return f'{_PREFIX}:{scope}:{name}'


def get(company_id, name: str, default=None):
    """Lecture scopée société (best-effort, jamais d'exception propagée)."""
    try:
        return cache.get(tenant_key(company_id, name), default)
    except Exception:  # noqa: BLE001 — backend cache indisponible → défaut
        return default


def set(company_id, name: str, value, timeout=None):  # noqa: A001
    """Écriture scopée société (best-effort)."""
    try:
        cache.set(tenant_key(company_id, name), value, timeout)
    except Exception:  # noqa: BLE001 — backend cache indisponible → no-op
        logger.warning('tenant cache set KO: %s/%s', company_id, name)


def invalidate(company_id, names) -> None:
    """Supprime les clés ``names`` d'une société (best-effort)."""
    if isinstance(names, str):
        names = [names]
    for name in names:
        try:
            cache.delete(tenant_key(company_id, name))
        except Exception:  # noqa: BLE001 — une suppression KO n'arrête rien
            logger.warning('tenant cache delete KO: %s/%s', company_id, name)


def invalidate_on(model, names) -> None:
    """Enregistre que sauvegarder/supprimer ``model`` invalide ``names`` pour
    la société de l'instance.

    À appeler dans le ``ready()`` de l'app propriétaire du modèle. Les signaux
    ``post_save``/``post_delete`` sont branchés paresseusement (une seule fois)
    au premier enregistrement. ``names`` peut être une chaîne ou un itérable.
    """
    if isinstance(names, str):
        names = [names]
    label = f'{model._meta.app_label}.{model._meta.model_name}'
    bucket = _INVALIDATION.setdefault(label, set())
    bucket.update(names)
    _ensure_connected()


def _ensure_connected() -> None:
    global _CONNECTED
    if _CONNECTED:
        return
    post_save.connect(_on_change, dispatch_uid='core_cache_invalidate_save')
    post_delete.connect(_on_change, dispatch_uid='core_cache_invalidate_del')
    _CONNECTED = True


def _on_change(sender, instance, **kwargs):
    """Récepteur générique : invalide les clés du tenant de l'instance.

    On résout les ``names`` par le chemin du ``sender`` : un modèle non
    enregistré ne déclenche rien (coût quasi nul sur les autres ``save()``).
    """
    try:
        label = f'{sender._meta.app_label}.{sender._meta.model_name}'
    except Exception:  # noqa: BLE001 — sender atypique → ignore
        return
    names = _INVALIDATION.get(label)
    if not names:
        return
    company_id = getattr(instance, 'company_id', None)
    invalidate(company_id, names)


def _reset_for_tests() -> None:
    """Réinitialise le registre (tests uniquement — jamais en usage normal)."""
    _INVALIDATION.clear()
