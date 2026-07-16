from rest_framework import generics

from authentication.permissions import IsAnyRole
from .models import ExtensionPackage
from .serializers import ExtensionPackageSerializer


class ExtensionPackageCatalogueView(generics.ListAPIView):
    """NTEXT13 — catalogue des packages d'extension installables (marketplace
    interne). READ-ONLY : seuls les packages GLOBAUX (``company=None``)
    apparaissent ici — un package du catalogue est un gabarit, jamais lié à
    une société."""
    serializer_class = ExtensionPackageSerializer
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        return ExtensionPackage.objects.filter(company__isnull=True)
