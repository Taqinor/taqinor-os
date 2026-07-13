"""YHARD3 — reconstruction générique « à une date » (as-of) + diff structuré.

L'historique riche existant (chatter CRM ``crm.LeadActivity``, piste comptable
hash-chaînée ``compta.PisteAuditComptable``, valorisation stock XSTK13) reste
inchangé et hors périmètre. Ce module ajoute un sélecteur FONDATION générique,
purement en lecture, qui rejoue le champ ``AuditLog.changes`` (diff structuré
best-effort, voir ``recorder.record``) pour reconstruire l'état des champs
suivis d'un objet à une date passée.

Dégradation : les lignes historiques SANS ``changes`` (tout le legacy) sont
ignorées pour la reconstruction champ-par-champ mais n'empêchent jamais le
calcul — le résultat reflète simplement les diffs disponibles. Aucune app
métier n'est importée ici (fondation, cf. ``core``/``audit``).
"""
from __future__ import annotations

from typing import Any, Dict

from django.contrib.contenttypes.models import ContentType

from .models import AuditLog


def reconstruct_as_of(instance_or_ct, object_id=None, dt=None, *, company=None):
    """Reconstruit les valeurs de champs suivis d'un objet à la date ``dt``.

    Deux formes d'appel :
      * ``reconstruct_as_of(instance, dt=...)`` — content_type/object_id
        dérivés de l'instance ;
      * ``reconstruct_as_of(content_type, object_id, dt=...)`` — utile en
        lecture seule sans charger l'objet (ex. objet déjà supprimé).

    Renvoie un dict ``{"as_of": dt, "fields": {field: value, ...},
    "covered_changes": int}`` — ``fields`` ne contient que les champs pour
    lesquels au moins un diff structuré a été trouvé ≤ ``dt``. Company-scopé
    quand ``company`` est fourni (ou dérivée de l'instance) : une entrée
    d'une autre société n'est jamais utilisée.
    """
    if dt is None:
        from django.utils import timezone
        dt = timezone.now()

    if isinstance(instance_or_ct, ContentType):
        content_type = instance_or_ct
    else:
        instance = instance_or_ct
        content_type = ContentType.objects.get_for_model(instance.__class__)
        if object_id is None:
            object_id = str(getattr(instance, 'pk', '') or '')
        if company is None:
            company = getattr(instance, 'company', None)

    qs = AuditLog.objects.filter(
        content_type=content_type,
        object_id=str(object_id),
        timestamp__lte=dt,
    ).exclude(changes__isnull=True).order_by('timestamp')

    if company is not None:
        qs = qs.filter(company=company)

    fields: Dict[str, Any] = {}
    covered = 0
    for entry in qs:
        changes = entry.changes
        if not changes:
            continue
        for change in changes:
            try:
                field = change.get('field')
                new = change.get('new')
            except AttributeError:
                continue
            if not field:
                continue
            fields[field] = new
            covered += 1

    return {
        'as_of': dt,
        'fields': fields,
        'covered_changes': covered,
    }


# ---------------------------------------------------------------------------
# NTSEC15 — Journal de sécurité dédié & exportable.
#
# Sélecteur FONDATION lecture seule : filtre ``AuditLog`` sur les actions de
# sécurité (connexion/déconnexion/échec/alerte — les évènements SSO/SCIM/break-
# glass typés arriveront via NTSEC18 et sont déjà couverts tant qu'ils émettent
# ``security_alert``). Company-scopé : jamais les évènements d'une autre société.
# ---------------------------------------------------------------------------

SECURITY_ACTION_VALUES = [
    'login', 'logout', 'login_failed', 'security_alert',
]


def security_events(company, since=None, until=None):
    """Queryset des évènements de sécurité d'une société sur une fenêtre.

    ``company`` obligatoire (scope strict) ; ``since``/``until`` optionnels
    (datetimes). Ordonné du plus récent au plus ancien."""
    from .models import AuditLog
    if company is None:
        return AuditLog.objects.none()
    qs = AuditLog.objects.filter(
        company=company, action__in=SECURITY_ACTION_VALUES)
    if since is not None:
        qs = qs.filter(timestamp__gte=since)
    if until is not None:
        qs = qs.filter(timestamp__lte=until)
    return qs.order_by('-timestamp')
