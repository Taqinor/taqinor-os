"""NTSEC27 — Tableau de bord posture de sécurité par société.

Sélecteur fondation ``security_posture(company)`` agrégeant, en LECTURE SEULE et
company-scopé, les signaux de sécurité livrés par la vague NTSEC : MFA, SSO,
sessions actives, comptes dormants, violations SoD, campagnes de revue en
retard, secrets échus (YHARD5), allowlist IP. Chaque métrique est best-effort :
une dépendance absente contribue de façon NEUTRE (jamais d'exception remontée).
Une note pondérée « prêt SOC 2 / ISO 27001 » synthétise l'ensemble.
"""
from __future__ import annotations


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def _mfa_pct(company):
    from authentication.models import CustomUser
    actifs = CustomUser.objects.filter(company=company, is_active=True)
    total = actifs.count()
    if not total:
        return 0.0
    avec_mfa = actifs.filter(totp_enabled=True).count()
    return round(100.0 * avec_mfa / total, 1)


def _sso_configured(company):
    from .models import IdentityProvider
    return IdentityProvider.objects.filter(
        company=company, actif=True).exists()


def _active_sessions(company):
    from authentication.models import UserSession
    return UserSession.objects.filter(company=company, revoked=False).count()


def _dormant_accounts(company):
    from authentication.selectors import comptes_dormants
    seuil = 90
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
        seuil = (getattr(profile, 'dormant_days', 0) or 90)
    except Exception:
        pass
    return comptes_dormants(company, seuil).count()


def _sod_open(company):
    from apps.accessreview.sod import sod_violations
    return len(sod_violations(company))


def _overdue_campaigns(company):
    from django.utils import timezone

    from apps.accessreview.models import AccessReviewCampaign
    today = timezone.now().date()
    return AccessReviewCampaign.objects.filter(
        company=company,
        statut=AccessReviewCampaign.Statut.OUVERTE,
        date_fin__isnull=False, date_fin__lt=today).count()


def _expired_secrets(company):
    from core.integrations import secrets_due_for_rotation
    return len(list(secrets_due_for_rotation(company)))


def _ip_allowlist_active(company):
    from .models import NetworkPolicy
    return NetworkPolicy.objects.filter(
        company=company).exclude(mode=NetworkPolicy.Mode.OFF).exists()


def security_posture(company):
    """Agrège la posture de sécurité d'une société (lecture seule).

    Renvoie un dict de métriques + une note ``score`` (0–100) et la liste des
    ``items_faibles`` à corriger."""
    if company is None:
        return {}
    mfa_pct = _safe(lambda: _mfa_pct(company), 0.0)
    sso = _safe(lambda: _sso_configured(company), False)
    active_sessions = _safe(lambda: _active_sessions(company), 0)
    dormant = _safe(lambda: _dormant_accounts(company), 0)
    sod_open = _safe(lambda: _sod_open(company), 0)
    overdue = _safe(lambda: _overdue_campaigns(company), 0)
    expired_secrets = _safe(lambda: _expired_secrets(company), 0)
    ip_allowlist = _safe(lambda: _ip_allowlist_active(company), False)

    # Score pondéré (best-effort, indicatif « prêt SOC 2 / ISO 27001 »).
    score = 0
    faibles = []
    # MFA (30 pts, proportionnel).
    score += round(30 * mfa_pct / 100.0)
    if mfa_pct < 80:
        faibles.append('Couverture MFA insuffisante (%s%%)' % mfa_pct)
    # SSO configuré (20 pts).
    if sso:
        score += 20
    else:
        faibles.append('SSO non configuré')
    # Pas de comptes dormants (15 pts).
    if not dormant:
        score += 15
    else:
        faibles.append('%d compte(s) dormant(s)' % dormant)
    # Pas de violation SoD ouverte (15 pts).
    if not sod_open:
        score += 15
    else:
        faibles.append('%d violation(s) SoD ouverte(s)' % sod_open)
    # Pas de campagne de revue en retard (10 pts).
    if not overdue:
        score += 10
    else:
        faibles.append('%d campagne(s) de revue en retard' % overdue)
    # Pas de secret échu (10 pts).
    if not expired_secrets:
        score += 10
    else:
        faibles.append('%d secret(s) à faire tourner' % expired_secrets)

    return {
        'mfa_pct': mfa_pct,
        'sso_configured': sso,
        'active_sessions': active_sessions,
        'dormant_accounts': dormant,
        'sod_open_violations': sod_open,
        'overdue_review_campaigns': overdue,
        'expired_secrets': expired_secrets,
        'ip_allowlist_active': ip_allowlist,
        'score': min(score, 100),
        'soc2_iso27001_ready': score >= 80,
        'items_faibles': faibles,
    }
