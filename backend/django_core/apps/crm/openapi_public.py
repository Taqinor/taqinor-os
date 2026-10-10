"""ENF — forme d'erreur des routes PUBLIQUES du CRM (garde PACT7 : jamais de
forme vide). Ces vues répondent ``{"detail": "<message>"}`` sur leurs refus."""
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

PUBLIC_DETAIL = inline_serializer('CrmPublicDetail', {
    'detail': serializers.CharField(),
})
