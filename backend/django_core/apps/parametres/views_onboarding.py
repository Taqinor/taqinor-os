"""NTI18N31 — Vue de l'assistant « Onboarding pays ».

Un seul appel POST configure devise/fuseau/langue de secours et enchaîne le
seed des jours fériés (voir ``onboarding_pays.provisionner_localisation`` —
sa docstring documente la dépendance non résolue sur NTI18N13/NTI18N16 pour
les étapes « Pays »/« Pack pays » persistées).

Écriture d'un réglage de société : réservé Administrateur/Responsable promu,
même patron de permission que le reste de l'app (``views_profile``,
``views_config``), ET porteur de ``localisation_gerer`` (NTI18N40) — c'est un
réglage de LOCALISATION, pas un réglage de société quelconque."""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier

from .localisation import PeutGererLocalisation
from .onboarding_pays import SEEDERS_FERIES_PAR_PAYS, provisionner_localisation
from .serializers_company import CompanyProfileSerializer
from .views_common import _audit_company

# NTI18N31 — forme réelle du corps (tout optionnel, ``pays`` défaut ``'MA'``
# côté vue) et de la réponse (miroir exact du dict renvoyé par
# ``provisionner_localisation`` : profile/pays/feries_seedes/seeder_utilise).
ONBOARDING_LOCALISATION_REQUEST = inline_serializer(
    'OnboardingLocalisationRequest', {
        'pays': serializers.CharField(required=False),
        'devise': serializers.CharField(required=False, allow_null=True),
        'fuseau_horaire': serializers.CharField(
            required=False, allow_null=True),
        'langue_repli': serializers.CharField(
            required=False, allow_null=True),
    })


class _CompanyProfileSchema(CompanyProfileSerializer):
    """Forme OpenAPI de ``CompanyProfileSerializer`` — DOCS UNIQUEMENT, jamais
    instanciée pour sérialiser une vraie réponse (la vue continue d'appeler
    ``CompanyProfileSerializer`` telle quelle, inchangée).

    ``CompanyProfileSerializer`` (``apps/parametres/serializers_company.py``,
    hors périmètre de ce lot) déclare 3 ``SerializerMethodField`` sans
    annotation de type sur leurs ``get_*`` (``logo_url``, ``signature_url``,
    ``benchmarking_opt_in``) : drf-spectacular ne peut deviner leur type et
    échoue dès la première fois que ce sérialiseur est exposé à un
    ``@extend_schema`` — ce que cette vue est la première à faire. Les 3
    champs sont donc redéclarés ici avec leur type RÉEL (``str`` nullable
    pour les deux URLs, ``bool`` pour le consentement) ; tous les 120+ autres
    champs (``fields = '__all__'`` du modèle ``CompanyProfile``) restent
    hérités tels quels.
    """
    logo_url = serializers.CharField(read_only=True, allow_null=True)
    signature_url = serializers.CharField(read_only=True, allow_null=True)
    benchmarking_opt_in = serializers.BooleanField(read_only=True)


ONBOARDING_LOCALISATION_RESPONSE = inline_serializer(
    'OnboardingLocalisationResponse', {
        'profile': _CompanyProfileSchema(),
        'pays': serializers.CharField(),
        'feries_seedes': serializers.BooleanField(),
        'seeder_utilise': serializers.CharField(allow_null=True),
    })


@extend_schema(request=ONBOARDING_LOCALISATION_REQUEST,
               responses=ONBOARDING_LOCALISATION_RESPONSE)
@api_view(['POST'])
@permission_classes([IsAdminOrResponsableTier, PeutGererLocalisation])
def onboarding_localisation(request):
    """POST /parametres/onboarding-localisation/.

    Corps optionnel : ``{"pays": "MA", "devise": "MAD",
    "fuseau_horaire": "Africa/Casablanca", "langue_repli": "fr"}``. ``pays``
    défaut ``'MA'`` (seul pays actionnable aujourd'hui — voir la docstring
    du module ``onboarding_pays``)."""
    company = _audit_company(request)
    if company is None:
        return Response(
            {'detail': 'Aucune société associée à ce compte.'},
            status=status.HTTP_400_BAD_REQUEST)

    pays = (request.data.get('pays') or 'MA').upper()
    if pays not in SEEDERS_FERIES_PAR_PAYS:
        return Response(
            {'detail': f"Pays inconnu : « {pays} »."},
            status=status.HTTP_400_BAD_REQUEST)

    resultat = provisionner_localisation(
        company,
        pays=pays,
        devise=request.data.get('devise'),
        fuseau_horaire=request.data.get('fuseau_horaire'),
        langue_repli=request.data.get('langue_repli'),
    )
    return Response({
        'profile': CompanyProfileSerializer(resultat['profile']).data,
        'pays': resultat['pays'],
        'feries_seedes': resultat['feries_seedes'],
        'seeder_utilise': resultat['seeder_utilise'],
    })
