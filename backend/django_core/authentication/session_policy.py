"""NTSEC10 — Politique de session par société (durée absolue / inactivité /
sessions concurrentes).

La CONFIGURATION vit sur ``parametres.CompanyProfile`` (champs additifs, tous à
0 par défaut = inerte). Ce module — dans ``authentication``, la couche qui LIT
ces champs — porte l'APPLICATION runtime : refus de rafraîchissement au-delà de
la durée absolue / d'inactivité, et éviction de la session la plus ancienne
au-delà de la limite concurrente.

Tout est best-effort et FAIL-OPEN : profil absent, valeurs à 0, ou erreur →
comportement historique strictement inchangé (aucune session existante affectée).
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def _policy(company):
    if company is None:
        return None
    try:
        from apps.parametres.models import CompanyProfile
        return CompanyProfile.objects.filter(company=company).first()
    except Exception:
        return None


def _revoke(session):
    """Révoque une session (marque + blackliste son jeton). Best-effort."""
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken, OutstandingToken,
        )
        outstanding = OutstandingToken.objects.filter(jti=session.jti).first()
        if outstanding is not None:
            BlacklistedToken.objects.get_or_create(token=outstanding)
    except Exception:
        pass
    session.revoked = True
    try:
        session.save(update_fields=['revoked'])
    except Exception:
        pass


def refresh_allowed(refresh_raw, user=None):
    """Vrai si le rafraîchissement est autorisé par la politique de session.

    Applique la durée absolue (depuis ``created_at``) et l'inactivité (depuis
    ``last_seen_at``). En cas de dépassement, la session est révoquée et la
    fonction renvoie ``False``. FAIL-OPEN : sans session tracée, sans profil,
    ou avec des seuils à 0, renvoie toujours ``True``.
    """
    try:
        from rest_framework_simplejwt.tokens import RefreshToken

        from authentication.models import UserSession

        token = RefreshToken(refresh_raw)
        jti = token.get('jti')
        if not jti:
            return True
        session = UserSession.objects.filter(
            jti=jti, revoked=False).select_related('company').first()
        if session is None:
            return True
        company = session.company or getattr(user, 'company', None)
        profile = _policy(company)
        if profile is None:
            return True
        now = timezone.now()
        abs_hours = getattr(profile, 'session_absolute_hours', 0) or 0
        idle_min = getattr(profile, 'session_idle_minutes', 0) or 0
        if abs_hours and session.created_at and \
                now > session.created_at + timedelta(hours=abs_hours):
            _revoke(session)
            return False
        if idle_min and session.last_seen_at and \
                now > session.last_seen_at + timedelta(minutes=idle_min):
            _revoke(session)
            return False
        # Activité valide : rafraîchir l'horodatage d'inactivité (auto_now).
        try:
            session.save(update_fields=['last_seen_at'])
        except Exception:
            pass
        return True
    except Exception:
        # Tout imprévu → ne jamais casser le rafraîchissement (fail-open).
        return True


def enforce_concurrent_limit(user):
    """Éviction : au-delà de ``max_concurrent_sessions``, révoque les plus
    anciennes sessions actives de ``user`` (best-effort, no-op si 0).
    """
    try:
        if user is None or not getattr(user, 'pk', None):
            return
        profile = _policy(getattr(user, 'company', None))
        limit = getattr(profile, 'max_concurrent_sessions', 0) or 0
        if not limit:
            return
        from authentication.models import UserSession
        active = list(UserSession.objects.filter(
            user=user, revoked=False).order_by('created_at'))
        surplus = len(active) - limit
        for session in active[:max(surplus, 0)]:
            _revoke(session)
    except Exception:
        pass
