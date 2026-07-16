"""NTSEC13 — Détection nouvel appareil / navigateur inconnu.

À chaque connexion réussie, on calcule une empreinte d'appareil (hash du
``user_agent`` + plateforme) posée sur la ``UserSession``. À la PREMIÈRE
apparition d'une empreinte pour un utilisateur, une ``SECURITY_ALERT`` est
journalisée et l'utilisateur est notifié (« nouvelle connexion depuis un
appareil inconnu »). Best-effort : ne bloque jamais la connexion.
"""
from __future__ import annotations

import hashlib


def compute_fingerprint(user_agent, platform=''):
    """Empreinte stable (SHA-256 hex) d'un appareil depuis son UA + plateforme."""
    basis = f'{(user_agent or "").strip()}|{(platform or "").strip()}'.lower()
    if not basis.strip('|'):
        return ''
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()


def note_login_device(user, session, request=None):
    """Pose l'empreinte sur ``session`` et alerte si l'appareil est inconnu.

    Renvoie ``True`` si une alerte « appareil inconnu » a été levée. No-op si
    l'empreinte est vide ou déjà connue pour cet utilisateur.
    """
    try:
        if user is None or session is None:
            return False
        ua = getattr(session, 'user_agent', '') or ''
        platform = ''
        if request is not None:
            platform = request.META.get('HTTP_SEC_CH_UA_PLATFORM', '') or ''
        fp = compute_fingerprint(ua, platform)
        if not fp:
            return False
        from authentication.models import UserSession
        # Empreinte déjà vue sur une AUTRE session de cet utilisateur ?
        known = UserSession.objects.filter(
            user=user, device_fingerprint=fp,
        ).exclude(pk=session.pk).exists()
        session.device_fingerprint = fp
        try:
            session.save(update_fields=['device_fingerprint'])
        except Exception:
            pass
        if known:
            return False
        _alert_new_device(user, session)
        return True
    except Exception:
        return False


def _alert_new_device(user, session):
    company = getattr(user, 'company', None)
    detail = ('Nouvelle connexion depuis un appareil inconnu : %s'
              % (getattr(session, 'user_agent', '') or 'appareil inconnu')[:180])
    try:
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.SECURITY_ALERT, user=user, company=company,
               detail=detail)
    except Exception:
        pass
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        notify(user, EventType.SECURITY_ALERT,
               'Nouvelle connexion depuis un appareil inconnu',
               body=detail, company=company, respect_quiet_hours=False)
    except Exception:
        pass
