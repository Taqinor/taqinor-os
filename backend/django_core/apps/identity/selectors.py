"""Sélecteurs de FONDATION de l'app identité (lecture seule, sans app métier).

Exposés pour que ``authentication`` (app de fondation) puisse consulter l'état
SSO d'une société SANS importer les modèles ``apps.identity`` au niveau module
(import paresseux depuis les vues). Tout est best-effort et FAIL-OPEN : la
moindre incertitude renvoie « ne pas bloquer », pour ne jamais casser un login.
"""
from __future__ import annotations


def is_break_glass_active(user) -> bool:
    """Vrai si ``user`` bénéficie d'un accès break-glass en cours (NTSEC22).

    Contourne l'enforce-SSO. Tolère l'absence du modèle ``BreakGlassGrant``
    (livré par NTSEC22) : renvoie alors ``False`` sans jamais lever.
    """
    if user is None or not getattr(user, 'pk', None):
        return False
    # Drapeau simple éventuel (compat) — jamais requis.
    if getattr(user, 'is_break_glass', False):
        return True
    try:
        from django.utils import timezone

        from .models import BreakGlassGrant
    except Exception:
        return False
    try:
        now = timezone.now()
        return BreakGlassGrant.objects.filter(
            user_id=user.pk,
            company_id=getattr(user, 'company_id', None),
            revoque_le__isnull=True,
            active_jusqu_a__gt=now,
        ).exists()
    except Exception:
        return False


def local_password_login_blocked(user) -> bool:
    """Vrai si l'utilisateur DOIT passer par le SSO (login local interdit).

    Conditions pour BLOQUER (toutes requises) :
      * ``user`` résolu et NON super-admin ;
      * pas d'accès break-glass en cours ;
      * la société de l'utilisateur a un ``IdentityProvider`` actif avec
        ``enforce_sso=True``.

    FAIL-OPEN : utilisateur inconnu, société sans IdP, ou toute erreur →
    ``False`` (login local inchangé). Aucune société sans SSO n'est affectée.
    """
    if user is None or not getattr(user, 'pk', None):
        return False
    if getattr(user, 'is_superuser', False):
        return False
    if is_break_glass_active(user):
        return False
    company_id = getattr(user, 'company_id', None)
    if not company_id:
        return False
    try:
        from .models import IdentityProvider
        return IdentityProvider.objects.filter(
            company_id=company_id, actif=True, enforce_sso=True,
        ).exists()
    except Exception:
        return False
