from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import ContactClient
from .serializers import ContactClientSerializer


class ContactClientViewSet(CompanyScopedModelViewSet):
    queryset = ContactClient.objects.select_related('client')
    serializer_class = ContactClientSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        client_id = self.request.query_params.get('client')
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs
