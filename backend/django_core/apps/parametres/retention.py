"""FG26 — purge de rétention du Journal d'activité (RGPD).

Au-delà de ``CompanyProfile.audit_retention_days`` (par société), les lignes du
Journal d'activité (``audit.AuditLog``) et du Journal d'audit des Paramètres
(``SettingsAuditLog``) peuvent être supprimées. 0 jour = conservation
illimitée (défaut) : aucune purge tant qu'une société ne fixe pas de fenêtre.

Best-effort et idempotent : relancer ne supprime que ce qui dépasse encore la
fenêtre. Réutilise l'import paresseux d'``audit`` pour rester sans cycle.
"""
from django.utils import timezone

from .models import CompanyProfile, SettingsAuditLog


def purge_company_audit(company):
    """Purge les journaux de ``company`` au-delà de sa fenêtre de rétention.

    Retourne ``(supprimees_audit, supprimees_settings)``. (0, 0) si la société
    n'a pas fixé de fenêtre (rétention illimitée)."""
    if company is None:
        return (0, 0)
    profile = CompanyProfile.objects.filter(company=company).first()
    days = getattr(profile, 'audit_retention_days', 0) or 0
    if days <= 0:
        return (0, 0)
    cutoff = timezone.now() - timezone.timedelta(days=days)
    audit_deleted = 0
    try:
        from apps.audit.models import AuditLog
        audit_deleted = AuditLog.objects.filter(
            company=company, timestamp__lt=cutoff).delete()[0]
    except Exception:
        audit_deleted = 0
    settings_deleted = SettingsAuditLog.objects.filter(
        company=company, timestamp__lt=cutoff).delete()[0]
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
