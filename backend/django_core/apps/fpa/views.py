from rest_framework import filters, viewsets
from rest_framework.response import Response

from core.mixins import TenantMixin

from .models import Departement
from .serializers import DepartementSerializer


class DepartementViewSet(TenantMixin, viewsets.ModelViewSet):
    """NTFPA1 — CRUD des départements FP&A, scopé société."""

    queryset = Departement.objects.select_related('responsable', 'parent').all()
    serializer_class = DepartementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom']
    ordering_fields = ['nom', 'code']

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai'))
        return qs

    def _to_node(self, dept, by_parent):
        enfants = by_parent.get(dept.pk, [])
        return {
            **DepartementSerializer(dept).data,
            'enfants': [self._to_node(e, by_parent) for e in enfants],
        }

    def list(self, request, *args, **kwargs):
        if request.query_params.get('tree') == '1':
            qs = list(self.filter_queryset(self.get_queryset()))
            by_parent = {}
            for d in qs:
                by_parent.setdefault(d.parent_id, []).append(d)
            racines = by_parent.get(None, [])
            return Response([self._to_node(d, by_parent) for d in racines])
        return super().list(request, *args, **kwargs)
