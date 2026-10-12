"""ENF10 — schéma OpenAPI des APIView de ``authentication/views.py``.

``views.py`` dépasse 2 000 lignes (C20 : il ne grossit pas) ; les
déclarations ``@extend_schema`` de ses APIView sans sérialiseur vivent donc
ici et sont appliquées au chargement de l'app (``AuthenticationConfig.ready``).
Les erreurs 4xx sont couvertes par le hook ``ErreurApi``.
"""
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, inline_serializer,
)
from rest_framework import serializers


def declarer_schemas_apiview():
    from . import views

    extend_schema_view(post=extend_schema(
        request=None,
        responses=inline_serializer('TwoFactorSetupReponse', {
            'secret': serializers.CharField(),
            'otpauth_uri': serializers.CharField(),
            'qr_svg': serializers.CharField(),
            'issuer': serializers.CharField(),
            'label': serializers.CharField(),
        })))(views.TwoFactorSetupView)

    extend_schema_view(get=extend_schema(
        responses=inline_serializer('TwoFactorStatutReponse', {
            'enabled': serializers.BooleanField(),
            'recovery_codes_remaining': serializers.IntegerField(),
        })))(views.TwoFactorStatusView)

    extend_schema_view(post=extend_schema(
        request=None,
        responses=inline_serializer('SessionRevoqueeReponse', {
            'detail': serializers.CharField()}),
    ))(views.SessionRevokeView)

    extend_schema_view(post=extend_schema(
        request=inline_serializer('ChangePasswordRequete', {
            'current_password': serializers.CharField(),
            'new_password': serializers.CharField(),
        }),
        responses=inline_serializer('ChangePasswordReponse', {
            'detail': serializers.CharField(),
            'sessions_revoked': serializers.IntegerField(),
        })))(views.ChangePasswordView)
