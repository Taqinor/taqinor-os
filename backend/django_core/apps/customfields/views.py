from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsAdminRole

from .models import (
    CustomFieldDefinition, HiddenStandardField, MODULE_KEYS,
)
from .serializers import (
    CustomFieldDefinitionSerializer, HiddenStandardFieldSerializer,
)


class CustomFieldDefinitionViewSet(TenantMixin, viewsets.ModelViewSet):
    """CRUD des définitions de champs personnalisés (admin uniquement).

    Lecture ouverte à tout utilisateur authentifié (les formulaires en ont
    besoin) ; écritures réservées à l'admin. Tout est scopé société par le
    TenantMixin (queryset filtré + company forcé au create/update).
    """
    queryset = CustomFieldDefinition.objects.all()
    serializer_class = CustomFieldDefinitionSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        module = self.request.query_params.get('module')
        if module in MODULE_KEYS:
            qs = qs.filter(module=module)
        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsAdminRole])
    def reorder(self, request):
        """Réordonne une liste de définitions : body {ids: [...]} dans l'ordre
        voulu. Scopé société (on n'agit que sur les définitions de la société).
        """
        ids = request.data.get('ids') or []
        company = request.user.company
        qs = CustomFieldDefinition.objects.filter(company=company, id__in=ids)
        by_id = {d.id: d for d in qs}
        to_update = []
        for order, pk in enumerate(ids):
            d = by_id.get(pk)
            if d is not None:
                d.order = order
                to_update.append(d)
        if to_update:
            CustomFieldDefinition.objects.bulk_update(to_update, ['order'])
        return Response({'ok': True, 'count': len(to_update)})


class HiddenStandardFieldViewSet(TenantMixin, viewsets.ModelViewSet):
    """Gestion des champs standard masqués (admin uniquement)."""
    queryset = HiddenStandardField.objects.all()
    serializer_class = HiddenStandardFieldSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = super().get_queryset()
        module = self.request.query_params.get('module')
        if module in MODULE_KEYS:
            qs = qs.filter(module=module)
        return qs


@api_view(['GET'])
@permission_classes([IsAnyRole])
def module_schema(request, module):
    """Schéma d'affichage d'un module : définitions actives + clés standard
    masquées. Utilisé par les formulaires/listes frontend. Scopé société."""
    if module not in MODULE_KEYS:
        return Response({'detail': 'Module inconnu.'},
                        status=status.HTTP_404_NOT_FOUND)
    company = request.user.company
    if company is None and not request.user.is_superuser:
        return Response({'module': module, 'definitions': [], 'hidden_standard': []})

    defs = CustomFieldDefinition.objects.filter(module=module, active=True)
    hidden = HiddenStandardField.objects.filter(module=module)
    if company is not None:
        defs = defs.filter(company=company)
        hidden = hidden.filter(company=company)
    defs = defs.order_by('order', 'id')

    return Response({
        'module': module,
        'definitions': CustomFieldDefinitionSerializer(
            defs, many=True, context={'request': request}).data,
        'hidden_standard': list(hidden.values_list('field_key', flat=True)),
    })


@api_view(['POST'])
@permission_classes([IsAdminRole])
def restore_defaults(request, module):
    """Réinitialise un module par défaut pour la société : ré-affiche les champs
    standard masqués et désactive (archive — jamais supprime) les champs
    personnalisés. Les valeurs déjà saisies restent en base."""
    if module not in MODULE_KEYS:
        return Response({'detail': 'Module inconnu.'},
                        status=status.HTTP_404_NOT_FOUND)
    company = request.user.company
    if company is None:
        return Response({'detail': 'Société requise.'},
                        status=status.HTTP_400_BAD_REQUEST)

    hidden_removed = HiddenStandardField.objects.filter(
        company=company, module=module).delete()[0]
    custom_archived = CustomFieldDefinition.objects.filter(
        company=company, module=module, active=True).update(active=False)

    return Response({
        'ok': True,
        'unhidden_standard': hidden_removed,
        'archived_custom': custom_archived,
    })
