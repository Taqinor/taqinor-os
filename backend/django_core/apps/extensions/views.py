from rest_framework import generics

from authentication.permissions import IsAnyRole
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
