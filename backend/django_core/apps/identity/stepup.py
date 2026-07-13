"""NTSEC9 — MFA « step-up » par sensibilité d'action (fondation réutilisable).

Fournit ``require_recent_mfa(action, minutes)`` : une FABRIQUE de permission DRF
qui exige, pour une action jugée sensible par la société, une ré-authentification
MFA (TOTP/passkey) datant de moins de ``minutes``. Sans MFA récente → 403.

Défaut INERTE : une action n'est « sensible » que si la société l'a explicitement
listée dans ``CompanyProfile.step_up_actions`` (JSON). Liste vide (défaut) ⇒ le
step-up ne s'active jamais et le comportement reste strictement inchangé.

Câblage : la fraîcheur MFA est portée par ``UserSession.last_mfa_at``, horodaté à
la connexion quand un second facteur a été vérifié (voir
``authentication.views._record_session``). La session courante est résolue depuis
le cookie ``refresh_token`` (son claim ``jti``), comme le fait la vue des sessions.

Exemple d'usage sur une vue à risque (paie run, création IdP, break-glass…) ::

    class PayrollRunView(APIView):
        permission_classes = [IsAdminRole, require_recent_mfa('paie_run', 5)]

Sécurité : DEFAULT-DENY. Un utilisateur non authentifié, une action listée sans
MFA récente, ou une session introuvable ⇒ refus. Jamais d'élargissement d'accès.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.permissions import BasePermission


def _current_session_mfa_at(request):
    """``last_mfa_at`` de la session courante (ou None), best-effort.

    Résout la session par le ``jti`` du cookie ``refresh_token`` et la borne à
    l'utilisateur authentifié (jamais la session d'un autre compte). Toute erreur
    (jeton absent/invalide, table indisponible) ⇒ None ⇒ traité comme « pas de
    MFA récente » côté appelant (default-deny).
    """
    try:
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        raw = request.COOKIES.get('refresh_token')
        if not raw:
            return None
        try:
            jti = RefreshToken(raw).get('jti')
        except TokenError:
            return None
        if not jti:
            return None
        from authentication.models import UserSession
        session = (
            UserSession.objects
            .filter(jti=jti, revoked=False, user=request.user)
            .only('last_mfa_at')
            .first()
        )
        return getattr(session, 'last_mfa_at', None) if session else None
    except Exception:  # noqa: BLE001 - jamais casser le pipeline permission
        return None


def _step_up_actions(company):
    """Liste des clés d'action sensibles configurées pour ``company`` (ou [])."""
    if company is None:
        return []
    try:
        from apps.parametres.models_company import CompanyProfile
        profile = (
            CompanyProfile.objects
            .filter(company=company)
            .only('step_up_actions')
            .first()
        )
        actions = getattr(profile, 'step_up_actions', None) if profile else None
        return actions if isinstance(actions, (list, tuple)) else []
    except Exception:  # noqa: BLE001
        return []


def require_recent_mfa(action, minutes=5):
    """Fabrique une permission DRF exigeant une MFA récente pour ``action``.

    * ``action``  — clé d'action (str) comparée à ``step_up_actions`` de la
      société. Si la société ne l'a pas listée → permission INERTE (autorise).
    * ``minutes`` — fenêtre de fraîcheur MFA (défaut 5).
    """

    class _RequireRecentMfa(BasePermission):
        message = 'Ré-authentification MFA requise.'

        def has_permission(self, request, view):
            user = getattr(request, 'user', None)
            if user is None or not getattr(user, 'is_authenticated', False):
                # Default-deny : jamais d'accès à une action sensible sans compte.
                return False

            company = getattr(user, 'company', None)
            if action not in _step_up_actions(company):
                # La société n'a pas marqué cette action sensible → inactif.
                return True

            mfa_at = _current_session_mfa_at(request)
            if mfa_at is None:
                return False
            return (timezone.now() - mfa_at) <= timedelta(minutes=minutes)

    _RequireRecentMfa.__name__ = f'RequireRecentMfa_{action}'
    return _RequireRecentMfa
