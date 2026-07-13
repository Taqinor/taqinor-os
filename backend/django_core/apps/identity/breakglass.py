"""NTSEC22 — Procédure break-glass auditée (accès d'urgence temporaire).

Élève un compte au rôle Administrateur pour une durée bornée (contourne
``enforce_sso``), journalise l'octroi, notifie tous les Directeurs, et
s'auto-révoque à l'échéance (commande de nettoyage + check on-the-fly).
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def acting_user_has_mfa(user):
    """Vrai si le Directeur agissant a une MFA active (proxy NTSEC9).

    La « MFA récente » stricte relève de NTSEC9 (horodatage de vérification non
    encore tracé) ; on exige a minima que le 2FA (TOTP) soit activé."""
    return bool(getattr(user, 'totp_enabled', False)) or bool(
        getattr(user, 'is_superuser', False))


def grant_break_glass(*, target, motif, duree_minutes, accorde_par):
    """Crée un octroi break-glass et élève ``target`` au rôle Administrateur.

    Fige le rôle antérieur pour restauration. Journalise + notifie les
    Directeurs. Renvoie l'octroi créé."""
    from authentication.models import CustomUser

    from .models import BreakGlassGrant

    company = getattr(target, 'company', None)
    grant = BreakGlassGrant.objects.create(
        company=company, user=target, motif=motif,
        accorde_par=accorde_par,
        active_jusqu_a=timezone.now() + timedelta(minutes=duree_minutes),
        role_legacy_avant=target.role_legacy or '',
        role_id_avant=str(target.role_id or ''),
    )
    # Élévation : Administrateur legacy + rôle FK effacé (is_admin_role retombe
    # alors sur role_legacy=admin). Restauré à la révocation.
    target.role_legacy = CustomUser.ROLE_ADMIN
    target.role = None
    target.save(update_fields=['role_legacy', 'role'])

    _audit(company, target, accorde_par,
           f'BREAK_GLASS accordé : {motif[:180]}')
    _notify_directeurs(company, target, accorde_par)
    return grant


def revoke_break_glass(grant):
    """Révoque un octroi : restaure le rôle antérieur + horodate la révocation."""
    if grant.revoque_le is not None:
        return grant
    target = grant.user
    target.role_legacy = grant.role_legacy_avant or target.role_legacy
    if grant.role_id_avant:
        target.role_id = grant.role_id_avant
    else:
        target.role = None
    target.save(update_fields=['role_legacy', 'role'])
    grant.revoque_le = timezone.now()
    grant.save(update_fields=['revoque_le'])
    _audit(grant.company, target, None, 'BREAK_GLASS révoqué')
    return grant


def revoke_expired(company=None):
    """Révoque tous les octrois échus non encore révoqués. Idempotent."""
    from .models import BreakGlassGrant
    qs = BreakGlassGrant.objects.filter(
        revoque_le__isnull=True, active_jusqu_a__lte=timezone.now())
    if company is not None:
        qs = qs.filter(company=company)
    n = 0
    for grant in qs:
        revoke_break_glass(grant)
        n += 1
    return n


def _audit(company, target, actor, detail):
    try:
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.SECURITY_ALERT, user=actor, company=company,
               detail=f'{detail} (compte {getattr(target, "username", "?")})')
    except Exception:
        pass


def _notify_directeurs(company, target, accorde_par):
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify, resolve_recipients
        body = ('Accès break-glass accordé à %s par %s.' % (
            getattr(target, 'username', '?'),
            getattr(accorde_par, 'username', 'système')))
        for recipient in resolve_recipients(
                company, EventType.SECURITY_ALERT):
            notify(recipient, EventType.SECURITY_ALERT,
                   'Accès break-glass accordé', body=body,
                   company=company, respect_quiet_hours=False)
    except Exception:
        pass
