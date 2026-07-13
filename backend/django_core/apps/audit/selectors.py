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


# ---------------------------------------------------------------------------
# NTSEC17 — vérification du chaînage d'inviolabilité + rétention plancher.
# ---------------------------------------------------------------------------

# Plancher légal de rétention du journal d'audit (jours) : la purge n'efface
# JAMAIS en-deçà, même si une société configure un délai plus court.
AUDIT_RETENTION_FLOOR_DAYS = 365


def verify_audit_chain(company_id):
    """Recalcule et vérifie le chaînage hash d'une société.

    Renvoie ``{'ok': bool, 'checked': int, 'broken_pk': pk|None}``. Ne
    considère que les lignes chaînées (``entry_hash`` non vide) ; les lignes
    legacy non chaînées sont ignorées. Company-scopé."""
    from .models import AuditLog, compute_entry_hash
    rows = list(
        AuditLog.objects.filter(company_id=company_id, entry_hash__gt='')
        .order_by('id'))
    prev_hash = ''
    checked = 0
    for row in rows:
        expected = compute_entry_hash(
            prev_hash=prev_hash,
            company_id=company_id,
            action=row.action,
            actor_username=row.actor_username,
            object_id=row.object_id,
            object_repr=row.object_repr,
            detail=row.detail,
            timestamp=row.timestamp,
        )
        if expected != row.entry_hash or row.prev_hash != prev_hash:
            return {'ok': False, 'checked': checked, 'broken_pk': row.pk}
        prev_hash = row.entry_hash
        checked += 1
    return {'ok': True, 'checked': checked, 'broken_pk': None}


def effective_retention_days(configured_days):
    """Rétention effective = max(config, plancher légal) ; 0 = illimité.

    Une société qui n'a PAS armé de rétention (0) conserve indéfiniment ; sinon
    la fenêtre ne descend jamais sous ``AUDIT_RETENTION_FLOOR_DAYS``."""
    days = configured_days or 0
    if days <= 0:
        return 0
    return max(days, AUDIT_RETENTION_FLOOR_DAYS)
