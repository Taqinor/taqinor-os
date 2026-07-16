"""Vue XFSM10 — astreinte / rotation après-heures.

``AstreinteViewSet`` : CRUD du roster d'astreinte (responsable/admin), lecture
tout rôle. Multi-tenant via ``TenantMixin`` : queryset filtré sur la société de
l'utilisateur, société + ``created_by`` posés côté serveur. Le technicien
assigné doit appartenir à la société de l'utilisateur."""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import Astreinte
from ..serializers import AstreinteSerializer

READ_ACTIONS = ['list', 'retrieve']


def _check_target_tenant(serializer, company):
    cid = getattr(company, 'id', None)
    technicien = serializer.validated_data.get('technicien')
    if technicien is not None and getattr(technicien, 'company_id', None) != cid:
        raise ValidationError({'technicien': 'Technicien inconnu.'})


class AstreinteViewSet(CompanyScopedModelViewSet):
    """XFSM10 — roster d'astreinte (nuits/week-ends). Lecture tout rôle,
    écriture responsable/admin. Société + `created_by` posés côté serveur ;
    une seule astreinte active par période/société (garde `clean()` du
    modèle, remontée en 400)."""
    queryset = Astreinte.objects.select_related('technicien', 'created_by').all()
    serializer_class = AstreinteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        technicien = params.get('technicien')
        if technicien:
            qs = qs.filter(technicien_id=technicien)
        debut = params.get('debut')
        fin = params.get('fin')
        if debut:
            qs = qs.filter(date_fin__gte=debut)
        if fin:
            qs = qs.filter(date_debut__lte=fin)
        return qs

    @staticmethod
    def _full_clean_or_400(instance):
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise ValidationError({'non_field_errors': exc.messages})

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_target_tenant(serializer, company)
        instance = serializer.save(company=company, created_by=self.request.user)
        self._full_clean_or_400(instance)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_target_tenant(serializer, company)
        instance = serializer.save(company=company)
        self._full_clean_or_400(instance)
