from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole
from .journal import TYPES, journal_plateforme
from .models import ExtensionPackage
from .serializers import ExtensionPackageSerializer


class ExtensionPackageCatalogueView(generics.ListAPIView):
    """NTEXT13 — catalogue des packages d'extension installables (marketplace
    interne). READ-ONLY : un registre GLOBAL partagé de gabarits, jamais lié à
    une société."""
    serializer_class = ExtensionPackageSerializer
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        return ExtensionPackage.objects.all()


class JournalPlateformeView(APIView):
    """NTEXT25 — timeline unifiée des effets de la plateforme, PAR SOCIÉTÉ.

    ``GET extensions/journal/?type=automatisation&succes=1&limite=50``.
    ``type`` est répétable ; ``succes`` vaut 1/0 ; la société est TOUJOURS
    celle du demandeur (jamais lue de la requête). Réservé au palier
    administration/responsable : c'est un écran d'observabilité admin.
    """

    permission_classes = [IsAdminOrResponsableTier]

    def get(self, request):
        types = [t for t in request.query_params.getlist('type') if t]
        brut_succes = request.query_params.get('succes')
        succes = None
        if brut_succes not in (None, ''):
            succes = str(brut_succes).strip().lower() in ('1', 'true', 'vrai',
                                                          'oui', 'on')
        entrees = journal_plateforme(
            request.user.company, types=types or None, succes=succes,
            limite=request.query_params.get('limite') or 50)
        return Response({'entrees': entrees, 'types': list(TYPES)})
