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

AUD816 — deux manques de socle corrigés
---------------------------------------
1. **Palier de rôle.** L'endpoint ``/core/bulk-edit/appliquer/`` était gardé par
   ``IsAuthenticated`` SEUL : un compte en lecture seule pouvait désactiver 200
   lignes d'un coup. Le palier par défaut est désormais responsable/admin, et
   une cible peut DÉCLARER sa propre garde (``permission=`` de
   ``register_bulk_target``) — chaque app reste maîtresse de qui édite SES
   données.
2. **Traçabilité.** ``queryset.update()`` court-circuite ``Model.save()``,
   ``full_clean()`` et TOUS les signaux : l'audit générique
   (``apps.audit.signals.TRACKED_MODELS``) ne voit rien passer, et
   ``updated_at`` n'est pas touché. ``apply_bulk_edit`` émet donc UN
   ``core.events.bulk_edit_applied`` par lot réellement appliqué ;
   ``apps/audit/receivers.py`` en écrit la ligne de journal. ``core`` reste une
   couche de FONDATION : il n'importe pas ``apps.audit``, il émet.
"""
from __future__ import annotations

# Registre en mémoire :
# { target_name: {label, fields, provider, permission} }.
_TARGETS: dict[str, dict] = {}


class CibleInconnue(Exception):
    """Cible d'édition en masse non enregistrée."""


class ChampNonModifiable(Exception):
    """Champ hors de la liste blanche modifiable de la cible."""


def register_bulk_target(name, label, fields, queryset_provider,
                         permission=None):
    """Enregistre une cible éditable en masse (idempotent).

    ``fields`` = liste blanche des champs modifiables. ``queryset_provider`` =
    callable ``(company, user) -> QuerySet`` déjà scopé société.

    AUD816 — ``permission`` (optionnel) : classe de permission DRF (ou liste de
    classes) exigée pour appliquer une édition en masse SUR CETTE CIBLE. Sans
    déclaration, l'endpoint applique le palier par défaut du socle
    (responsable/admin) : l'app propriétaire peut donc resserrer (ex. une
    permission ERP fine) sans jamais élargir en dessous d'un palier de rôle.
    """
    if not name or not callable(queryset_provider):
        raise ValueError('Cible bulk : nom + queryset_provider requis.')
    if permission is None:
        perms = []
    elif isinstance(permission, (list, tuple)):
        perms = list(permission)
    else:
        perms = [permission]
    _TARGETS[name] = {
        'label': label or name,
        'fields': list(fields or []),
        'provider': queryset_provider,
        'permission': perms,
    }


def target_permissions(name):
    """AUD816 — permissions DÉCLARÉES par la cible ``name``, ou ``None``.

    ``None`` = la cible n'en déclare aucune (l'appelant applique son palier par
    défaut) ; une cible inconnue rend ``None`` aussi — la vue traduit alors
    l'inconnue en 404 APRÈS la garde par défaut, jamais en fuite d'information.
    """
    spec = _TARGETS.get(name)
    if not spec:
        return None
    return [p() for p in spec.get('permission') or []] or None


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

    AUD816 — traçabilité : ``queryset.update()`` ne déclenche AUCUN signal CRUD,
    donc un lot passait sans une ligne de journal. Un ``bulk_edit_applied`` est
    émis pour chaque lot RÉELLEMENT appliqué (jamais si 0 ligne) ; l'émission
    est best-effort (un abonné en erreur ne fait jamais échouer l'écriture, qui
    est déjà commitée).
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
    count = qs.update(**changes)
    if count:
        _emettre_journal(target, spec, sorted(changes), count, company, user)
    return count


def _emettre_journal(target, spec, fields, count, company, user):
    """AUD816 — un lot appliqué = un ``bulk_edit_applied`` (best-effort)."""
    import logging

    from core import events

    try:
        events.bulk_edit_applied.send(
            sender='core.bulk_edit',
            target=target,
            label=spec.get('label') or target,
            fields=list(fields),
            count=count,
            company=company,
            user=user,
        )
    except Exception:  # noqa: BLE001 — jamais casser une écriture commitée
        logging.getLogger(__name__).warning(
            "bulk_edit_applied non journalisé pour la cible %r", target,
            exc_info=True)
