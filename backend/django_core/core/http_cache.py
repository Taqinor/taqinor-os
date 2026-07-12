"""NTPLT23/25 — ETag/304 + Cache-Control pour les listes chaudes (fondation).

Couche de FONDATION réutilisable : n'importe aucune app métier. Fournit
  * un COMPTEUR DE VERSION par (tenant, modèle) dans le cache (Redis en prod),
    incrémenté par signaux post_save/post_delete ;
  * ``ETagListMixin`` — un mixin de viewset DRF qui dérive un ETag FAIBLE
    (compteur de version + query params normalisés) et répond ``304 Not
    Modified`` sur ``If-None-Match`` sans jamais toucher la base : le polling de
    la cloche de notifications et du chat devient quasi gratuit côté DB ;
  * ``CacheControlMixin`` (NTPLT25) — pose ``Cache-Control: private, max-age=…``
    sur les référentiels quasi-statiques.

Câblage par app de domaine (hors de cette couche) : appeler
``register_etag_versioning(Model)`` dans le ``ready()`` de l'app, et ajouter le
mixin au viewset concerné (leads, produits, notifications, catégories…). La
mécanique ci-dessous est entièrement testable sans aucune app métier.
"""
from __future__ import annotations

import hashlib

from django.core.cache import cache

_VERSION_PREFIX = 'etag:v'


def _version_key(model_label: str, company_id) -> str:
    return f'{_VERSION_PREFIX}:{model_label}:{company_id or 0}'


def get_version(model_label: str, company_id) -> int:
    """Version courante de (modèle, tenant). 0 si jamais écrite."""
    return int(cache.get(_version_key(model_label, company_id)) or 0)


def bump_version(model_label: str, company_id) -> int:
    """Incrémente la version (toute écriture invalide les ETags précédents)."""
    key = _version_key(model_label, company_id)
    try:
        return cache.incr(key)
    except ValueError:
        # Clé absente : l'initialiser puis repartir de 1 (course tolérée — un
        # ETag « manqué » ne fait qu'un aller-retour complet de plus, jamais un
        # cache empoisonné).
        cache.set(key, 1, None)
        return 1


def register_etag_versioning(model):
    """Connecte post_save/post_delete d'un modèle au bump de version.

    À appeler depuis le ``ready()`` de l'app propriétaire du modèle. Le modèle
    doit exposer un ``company_id`` (convention TenantModel) ; à défaut, la
    version est globale (company_id=None)."""
    from django.db.models.signals import post_delete, post_save

    label = model._meta.label_lower

    def _on_change(sender, instance, **kwargs):
        bump_version(label, getattr(instance, 'company_id', None))

    post_save.connect(_on_change, sender=model, weak=False,
                      dispatch_uid=f'etag_bump_save_{label}')
    post_delete.connect(_on_change, sender=model, weak=False,
                        dispatch_uid=f'etag_bump_delete_{label}')


def _company_id_of(request):
    user = getattr(request, 'user', None)
    company = getattr(user, 'company', None) if user is not None else None
    return getattr(company, 'pk', None) if company is not None else None


def compute_list_etag(model_label: str, company_id, query_params) -> str:
    """ETag FAIBLE = W/"<hash(model, tenant, version, query params normalisés)>"."""
    version = get_version(model_label, company_id)
    # Normalise les query params : tri stable (clé, valeurs triées).
    try:
        items = sorted(
            (k, ','.join(sorted(query_params.getlist(k))))
            for k in query_params.keys())
    except AttributeError:
        items = sorted(query_params.items())
    raw = f'{model_label}|{company_id or 0}|{version}|{items}'
    digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]
    return f'W/"{digest}"'


class ETagListMixin:
    """Mixin viewset DRF : 304 sur ``If-None-Match`` pour l'action ``list``.

    Le viewset expose ``etag_model_label`` (sinon dérivé du modèle du queryset).
    L'ETag est calculé AVANT toute requête : un client à jour reçoit 304 sans
    qu'aucune ligne ne soit lue."""

    etag_model_label: str = ''

    def _etag_label(self):
        if self.etag_model_label:
            return self.etag_model_label
        return self.get_queryset().model._meta.label_lower

    def list(self, request, *args, **kwargs):
        company_id = _company_id_of(request)
        params = getattr(request, 'query_params', None)
        if params is None:
            params = request.GET
        etag = compute_list_etag(self._etag_label(), company_id, params)
        if request.headers.get('If-None-Match') == etag:
            from rest_framework.response import Response
            resp = Response(status=304)
            resp['ETag'] = etag
            return resp
        response = super().list(request, *args, **kwargs)
        response['ETag'] = etag
        return response


class CacheControlMixin:
    """NTPLT25 — ``Cache-Control: private, max-age=<cache_control_max_age>``.

    Pour les référentiels quasi-statiques (catégories, marques, canaux, types…).
    Se combine avec ``ETagListMixin`` pour la revalidation."""

    cache_control_max_age: int = 300

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            response['Cache-Control'] = (
                f'private, max-age={self.cache_control_max_age}')
        return response
