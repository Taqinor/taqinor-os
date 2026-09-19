"""NTI18N31 — Vue de l'assistant « Onboarding pays ».

Un seul appel POST configure devise/fuseau/langue de secours et enchaîne le
seed des jours fériés (voir ``onboarding_pays.provisionner_localisation`` —
sa docstring documente la dépendance non résolue sur NTI18N13/NTI18N16 pour
les étapes « Pays »/« Pack pays » persistées).

Écriture d'un réglage de société : réservé Administrateur/Responsable promu,
même patron de permission que le reste de l'app (``views_profile``,
``views_config``)."""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier

from .onboarding_pays import SEEDERS_FERIES_PAR_PAYS, provisionner_localisation
from .serializers_company import CompanyProfileSerializer
from .views_common import _audit_company


@api_view(['POST'])
@permission_classes([IsAdminOrResponsableTier])
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
