"""Endpoints Passkeys / WebAuthn (NTSEC8).

* ``auth/webauthn/register/begin|complete/`` — enregistrement (attestation),
  utilisateur authentifié.
* ``auth/webauthn/login/begin|complete/`` — connexion sans mot de passe
  (assertion). Vérifie ``sign_count`` monotone (anti-clone) ; un passkey validé
  émet le cookie JWT + crée une ``UserSession``.

Dégradent en 501 sans la lib ``webauthn`` (passkey strictement opt-in : sans
lib/sans passkey, le login local est inchangé).
"""
import base64
import logging
import secrets

from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from . import webauthn_util
from .models import CustomUser, WebAuthnChallenge, WebAuthnCredential

logger = logging.getLogger(__name__)


class WebAuthnCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebAuthnCredential
        fields = ['id', 'nom_appareil', 'created_at', 'last_used_at']
        read_only_fields = fields


class WebAuthnCredentialViewSet(viewsets.ModelViewSet):
    """Liste / suppression des passkeys de l'utilisateur courant (NTSEC8)."""

    serializer_class = WebAuthnCredentialSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'delete', 'head', 'options']

    def get_queryset(self):
        return WebAuthnCredential.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        user = instance.user
        instance.delete()
        _audit(user, 'PASSKEY_REMOVED', 'Passkey retiré')


def _b64url(raw_bytes):
    return base64.urlsafe_b64encode(raw_bytes).rstrip(b'=').decode('ascii')


def _new_challenge(purpose, user=None):
    raw = _b64url(secrets.token_bytes(32))
    WebAuthnChallenge.objects.create(
        challenge=raw, purpose=purpose, user=user)
    return raw


def _consume_challenge(purpose, challenge, user=None):
    """Récupère et invalide (usage unique) un défi valide, ou None."""
    qs = WebAuthnChallenge.objects.filter(
        purpose=purpose, challenge=challenge, used=False)
    if user is not None:
        qs = qs.filter(user=user)
    obj = qs.first()
    if obj is None:
        return None
    obj.used = True
    obj.save(update_fields=['used'])
    return obj


def _unavailable():
    return Response(
        {'detail': 'WebAuthn non disponible (dépendance non installée).'},
        status=status.HTTP_501_NOT_IMPLEMENTED)


class WebAuthnRegisterBeginView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not webauthn_util.webauthn_available():
            return _unavailable()
        user = request.user
        challenge = _new_challenge(
            WebAuthnChallenge.PURPOSE_REGISTER, user=user)
        try:
            from webauthn import generate_registration_options, options_to_json
            from webauthn.helpers.structs import (
                PublicKeyCredentialDescriptor,
            )
            existing = [
                PublicKeyCredentialDescriptor(id=_b64url_decode(c.credential_id))
                for c in user.webauthn_credentials.all()
            ]
            options = generate_registration_options(
                rp_id=webauthn_util.rp_id(request),
                rp_name=webauthn_util.rp_name(),
                user_name=user.username,
                user_id=str(user.pk).encode('utf-8'),
                exclude_credentials=existing,
                challenge=_b64url_decode(challenge),
            )
            import json
            return Response(json.loads(options_to_json(options)))
        except Exception:  # noqa: BLE001
            logger.exception('WebAuthn register begin failed')
            return Response(
                {'detail': "Échec de l'initialisation WebAuthn."},
                status=status.HTTP_400_BAD_REQUEST)


class WebAuthnRegisterCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not webauthn_util.webauthn_available():
            return _unavailable()
        user = request.user
        data = request.data or {}
        challenge = data.get('challenge')
        chal = _consume_challenge(
            WebAuthnChallenge.PURPOSE_REGISTER, challenge, user=user)
        if chal is None:
            return Response(
                {'detail': 'Défi WebAuthn invalide ou expiré.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            from webauthn import verify_registration_response
            verification = verify_registration_response(
                credential=data.get('credential'),
                expected_challenge=_b64url_decode(challenge),
                expected_rp_id=webauthn_util.rp_id(request),
                expected_origin=webauthn_util.origin(request),
            )
            cred = WebAuthnCredential.objects.create(
                user=user,
                credential_id=_b64url(verification.credential_id),
                public_key=_b64url(verification.credential_public_key),
                sign_count=verification.sign_count,
                nom_appareil=(data.get('nom_appareil') or '')[:120],
            )
            _audit(user, 'PASSKEY_ADDED', 'Passkey ajouté')
            return Response(
                {'id': cred.id, 'credential_id': cred.credential_id},
                status=status.HTTP_201_CREATED)
        except Exception:  # noqa: BLE001
            logger.exception('WebAuthn register complete failed')
            return Response(
                {'detail': "Échec de l'enregistrement du passkey."},
                status=status.HTTP_400_BAD_REQUEST)


class WebAuthnLoginBeginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        if not webauthn_util.webauthn_available():
            return _unavailable()
        username = (request.data.get('username') or '').strip()
        user = CustomUser.objects.filter(
            username__iexact=username).first() if username else None
        challenge = _new_challenge(
            WebAuthnChallenge.PURPOSE_LOGIN, user=user)
        try:
            from webauthn import (
                generate_authentication_options, options_to_json,
            )
            from webauthn.helpers.structs import (
                PublicKeyCredentialDescriptor,
            )
            allow = []
            if user is not None:
                allow = [
                    PublicKeyCredentialDescriptor(
                        id=_b64url_decode(c.credential_id))
                    for c in user.webauthn_credentials.all()
                ]
            options = generate_authentication_options(
                rp_id=webauthn_util.rp_id(request),
                challenge=_b64url_decode(challenge),
                allow_credentials=allow,
            )
            import json
            return Response(json.loads(options_to_json(options)))
        except Exception:  # noqa: BLE001
            logger.exception('WebAuthn login begin failed')
            return Response(
                {'detail': "Échec de l'initialisation WebAuthn."},
                status=status.HTTP_400_BAD_REQUEST)


class WebAuthnLoginCompleteView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        if not webauthn_util.webauthn_available():
            return _unavailable()
        data = request.data or {}
        challenge = data.get('challenge')
        chal = _consume_challenge(
            WebAuthnChallenge.PURPOSE_LOGIN, challenge)
        if chal is None:
            return Response(
                {'detail': 'Défi WebAuthn invalide ou expiré.'},
                status=status.HTTP_400_BAD_REQUEST)
        credential = data.get('credential') or {}
        cred_id = credential.get('id') or credential.get('rawId')
        cred = WebAuthnCredential.objects.filter(
            credential_id=cred_id).first() if cred_id else None
        if cred is None:
            return Response(
                {'detail': 'Passkey inconnu.'},
                status=status.HTTP_401_UNAUTHORIZED)
        try:
            from webauthn import verify_authentication_response
            verification = verify_authentication_response(
                credential=credential,
                expected_challenge=_b64url_decode(challenge),
                expected_rp_id=webauthn_util.rp_id(request),
                expected_origin=webauthn_util.origin(request),
                credential_public_key=_b64url_decode(cred.public_key),
                credential_current_sign_count=cred.sign_count,
            )
        except Exception:  # noqa: BLE001
            logger.exception('WebAuthn assertion verification failed')
            return Response(
                {'detail': 'Assertion WebAuthn invalide.'},
                status=status.HTTP_401_UNAUTHORIZED)

        # Anti-clone : le compteur de signatures doit croître (0/0 toléré).
        new_count = verification.new_sign_count
        if webauthn_util.sign_count_regressed(cred.sign_count, new_count):
            return Response(
                {'detail': 'Compteur de signatures régressé — passkey cloné '
                           'suspecté, connexion refusée.'},
                status=status.HTTP_401_UNAUTHORIZED)

        cred.sign_count = max(new_count, cred.sign_count)
        cred.last_used_at = timezone.now()
        cred.save(update_fields=['sign_count', 'last_used_at'])
        return _finalize_passkey_login(request, cred.user)


def _finalize_passkey_login(request, user):
    from .serializers import CustomTokenObtainPairSerializer
    from .views import _record_session, _set_auth_cookies
    if user is None or not user.is_active:
        return Response(
            {'detail': 'Compte indisponible.'},
            status=status.HTTP_403_FORBIDDEN)
    refresh = CustomTokenObtainPairSerializer.get_token(user)
    access = refresh.access_token
    response = Response({'detail': 'Connexion par passkey réussie.',
                         'username': user.username})
    _set_auth_cookies(response, str(access), str(refresh))
    _record_session(user, str(refresh), request)
    _audit(user, 'LOGIN', 'Connexion par passkey')
    return response


def _b64url_decode(value):
    if isinstance(value, bytes):
        return value
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _audit(user, action_name, detail):
    try:
        from apps.audit.models import AuditLog
        from apps.audit.recorder import record
        # Les actions typées PASSKEY_* arrivent avec NTSEC18 ; en attendant, un
        # repli propre (UPDATE) est utilisé — best-effort, jamais bloquant.
        action = getattr(
            AuditLog.Action, action_name, AuditLog.Action.UPDATE)
        record(action, user=user, actor_username=user.username,
               company=getattr(user, 'company', None), detail=detail)
    except Exception:  # noqa: BLE001
        logger.debug('webauthn audit failed', exc_info=True)
