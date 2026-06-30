"""FG389 — Édition en masse partout (bulk edit), fondation générique.

Couche de FONDATION : généralise l'édition d'un champ en masse sur les écrans
liste, SANS que ``core`` n'importe une app métier (contrat import-linter
``core-foundation-is-a-base-layer``). Chaque app métier ENREGISTRE une cible
éditable :

  * un nom logique (ex. ``« crm.lead »``) ;
  * la liste BLANCHE des champs modifiables en masse (jamais un champ hors
    liste → aucune écriture sauvage) ;
  * un ``queryset_provider(company, user) -> QuerySet`` DÉJÀ scopé société (la
    sécurité multi-tenant reste chez l'app propriétaire).

``apply_bulk_edit(target, company, user, ids, changes)`` applique ``changes``
(dict champ→valeur, restreint à la liste blanche) aux enregistrements ``ids`` du
queryset scopé. Renvoie le nombre de lignes modifiées. Aucune écriture hors du
queryset fourni : un id d'une autre société est simplement ignoré.
"""
from __future__ import annotations

# Registre en mémoire : { target_name: {label, fields, provider} }.
_TARGETS: dict[str, dict] = {}


class CibleInconnue(Exception):
    """Cible d'édition en masse non enregistrée."""


class ChampNonModifiable(Exception):
    """Champ hors de la liste blanche modifiable de la cible."""


def register_bulk_target(name, label, fields, queryset_provider):
    """Enregistre une cible éditable en masse (idempotent).

    ``fields`` = liste blanche des champs modifiables. ``queryset_provider`` =
    callable ``(company, user) -> QuerySet`` déjà scopé société.
    """
    if not name or not callable(queryset_provider):
        raise ValueError('Cible bulk : nom + queryset_provider requis.')
    _TARGETS[name] = {
        'label': label or name,
        'fields': list(fields or []),
        'provider': queryset_provider,
    }


def list_bulk_targets():
    """Catalogue normalisé des cibles éditables (rendu stable)."""
    out = [
        {'name': name, 'label': d['label'], 'fields': list(d['fields'])}
        for name, d in _TARGETS.items()
    ]
    out.sort(key=lambda d: d['name'])
    return out


def get_bulk_target(name):
    d = _TARGETS.get(name)
    if d is None:
        raise CibleInconnue(f'Cible inconnue : {name!r}')
    return d


def apply_bulk_edit(target, company, user, ids, changes):
    """Applique ``changes`` aux ``ids`` du queryset scopé. Renvoie le nb modifié.

    Sécurité :
      * seuls les champs de la liste blanche sont autorisés
        (``ChampNonModifiable`` sinon) ;
      * l'écriture est BORNÉE au queryset scopé société du fournisseur — un id
        hors scope est ignoré (jamais de fuite cross-société).
    """
    spec = get_bulk_target(target)
    allowed = set(spec['fields'])
    changes = dict(changes or {})
    if not changes:
        return 0
    for field in changes:
        if field not in allowed:
            raise ChampNonModifiable(f'Champ non modifiable : {field!r}')
    ids = [i for i in (ids or [])]
    if not ids:
        return 0
    qs = spec['provider'](company, user).filter(pk__in=ids)
    return qs.update(**changes)
