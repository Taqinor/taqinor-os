"""FG26 — purge de rétention du Journal d'activité (RGPD).

Au-delà de la rétention EFFECTIVE de la société, les lignes du Journal
d'activité (``audit.AuditLog``) et du Journal d'audit des Paramètres
(``SettingsAuditLog``) peuvent être supprimées. 0 jour = conservation
illimitée (défaut) : aucune purge tant qu'une société ne fixe pas de fenêtre.

APAR3 — la fenêtre n'est JAMAIS la valeur brute ``audit_retention_days`` : elle
passe par ``apps.audit.selectors.effective_retention_days`` (plancher légal de
365 j, le même que la commande ``purge_audit_log``). Chaque purge est elle-même
journalisée (``SettingsAuditLog`` section ``audit``, champ ``purge_retention`` :
QUI a purgé et combien) et ces lignes de trace ne sont jamais purgées. Une
erreur de suppression n'est plus avalée : elle remonte (500 journalisé).

Idempotent : relancer ne supprime que ce qui dépasse encore la fenêtre.
"""
import logging

from django.db import transaction
from django.utils import timezone

from .models import CompanyProfile, SettingsAuditLog

logger = logging.getLogger(__name__)

# Trace d'une purge de rétention — jamais purgée elle-même.
PURGE_SECTION = 'audit'
PURGE_FIELD = 'purge_retention'


def purge_company_audit(company, user=None):
    """Purge les journaux de ``company`` au-delà de sa rétention effective.

    Retourne ``(supprimees_audit, supprimees_settings)``. (0, 0) si la société
    n'a pas fixé de fenêtre (rétention illimitée). La fenêtre ne descend jamais
    sous le plancher légal (``effective_retention_days``)."""
    if company is None:
        return (0, 0)
    from apps.audit.selectors import effective_retention_days
    profile = CompanyProfile.objects.filter(company=company).first()
    configured = getattr(profile, 'audit_retention_days', 0) or 0
    days = effective_retention_days(configured)
    if days <= 0:
        return (0, 0)
    cutoff = timezone.now() - timezone.timedelta(days=days)
    from apps.audit.models import AuditLog
    try:
        with transaction.atomic():
            audit_deleted = AuditLog.objects.filter(
                company=company, timestamp__lt=cutoff).delete()[0]
            settings_deleted = SettingsAuditLog.objects.filter(
                company=company, timestamp__lt=cutoff,
            ).exclude(
                section=PURGE_SECTION, field=PURGE_FIELD,
            ).delete()[0]
            SettingsAuditLog.objects.create(
                company=company,
                user=user if getattr(user, 'pk', None) else None,
                section=PURGE_SECTION,
                field=PURGE_FIELD,
                field_label='Purge de rétention du journal',
                old_value=f'rétention configurée {configured} j, effective {days} j',
                new_value=(
                    f'audit_deleted={audit_deleted} '
                    f'settings_deleted={settings_deleted}'),
            )
    except Exception:
        logger.exception(
            'Purge de rétention du journal en échec (société %s)',
            getattr(company, 'pk', None))
        raise
    return (audit_deleted, settings_deleted)


def purge_all_companies():
    """Purge toutes les sociétés ayant fixé une fenêtre de rétention (>0).

    Pratique pour une commande planifiée. Retourne un dict de totaux."""
    from authentication.models import Company
    total_audit = total_settings = 0
    company_ids = CompanyProfile.objects.filter(
        audit_retention_days__gt=0).values_list('company_id', flat=True)
    for company in Company.objects.filter(id__in=list(company_ids)):
        a, s = purge_company_audit(company)
        total_audit += a
        total_settings += s
    return {'audit_deleted': total_audit, 'settings_deleted': total_settings}
