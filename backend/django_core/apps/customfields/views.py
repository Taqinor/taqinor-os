from rest_framework import viewsets
from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsAdminRole
from .models import CustomFieldDef
from .serializers import CustomFieldDefSerializer


class CustomFieldDefViewSet(TenantMixin, viewsets.ModelViewSet):
    """Définitions de champs personnalisés (Paramètres). Lecture tout rôle
    (les formulaires en ont besoin), écriture admin. Filtre ?module=lead."""
    queryset = CustomFieldDef.objects.all()
    serializer_class = CustomFieldDefSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        module = self.request.query_params.get('module')
        if module:
            qs = qs.filter(module=module)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAdminRole()]
