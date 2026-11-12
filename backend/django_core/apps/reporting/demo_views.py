"""NTDMO21/41/42 — endpoints reporting liés à l'onboarding produit."""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAuthenticatedInterne

from . import demo_resume, onboarding_kpi


@extend_schema(responses=inline_serializer('DemoResumeReponse', {
    'mois': drf_serializers.CharField(),
    'devis_envoyes': drf_serializers.IntegerField(),
    'chantiers_receptionnes': drf_serializers.IntegerField(),
    'ca_facture_ht': drf_serializers.FloatField(),
    'phrase': drf_serializers.CharField(),
}))
@api_view(['GET'])
@permission_classes([IsAuthenticatedInterne])  # ASEC51 : jamais un compte portail
def demo_resume_view(request):
    """NTDMO21 — résumé du mois, société DÉMO uniquement (404 sinon : le
    widget n'existe tout simplement pas pour une société réelle)."""
    resume = demo_resume.resume_pour_societe(request.user.company)
    if resume is None:
        return Response({'detail': 'Introuvable.'}, status=404)
    return Response(resume)


@extend_schema(responses=inline_serializer('KpiOnboardingInterneReponse', {
    'temps_jusqua_valeur': drf_serializers.DictField(),
    'adoption_tours': drf_serializers.ListField(
        child=drf_serializers.DictField()),
    'fin_vs_passe_raison': drf_serializers.CharField(allow_null=True),
}))
@api_view(['GET'])
@permission_classes([IsAuthenticatedInterne])  # ASEC51 : jamais un compte portail
def kpi_onboarding_interne(request):
    """NTDMO41/42 — donnée interne d'exploitation produit : super-admin
    de l'opérateur plateforme uniquement, jamais exposée à un tenant client."""
    if not request.user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)
    return Response(onboarding_kpi.depuis_cache())
