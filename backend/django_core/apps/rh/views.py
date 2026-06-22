"""Vues des Ressources humaines (toutes scopées société, admin-gated).

Le module RH est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``). Les
viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la société
côté serveur ; le ``cout_horaire`` (paie/marge) ne quitte jamais cette API.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import Departement, DossierEmploye
from .serializers import DepartementSerializer, DossierEmployeSerializer


class _RhBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class DepartementViewSet(_RhBaseViewSet):
    """Départements de la société. Recherche par nom/code."""
    queryset = Departement.objects.all()
    serializer_class = DepartementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'code']
    ordering_fields = ['nom']


class DossierEmployeViewSet(_RhBaseViewSet):
    """Dossiers employés (DC29). Recherche par matricule/nom/prénom."""
    queryset = DossierEmploye.objects.select_related('departement', 'user').all()
    serializer_class = DossierEmployeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['matricule', 'nom', 'prenom', 'cin', 'email']
    ordering_fields = ['nom', 'prenom', 'matricule', 'date_embauche']

    @action(detail=False, methods=['get'], url_path='cdd-a-echeance')
    def cdd_a_echeance(self, request):
        """Alerte fin de CDD : dossiers en CDD dont la fin de contrat tombe
        dans les ``?within=`` prochains jours (défaut 30), scopés société.

        Exclut les CDI (et tout autre type), les CDD sans date de fin, ceux
        déjà expirés et ceux dont la fin dépasse la fenêtre. La société est
        garantie par ``get_queryset`` (TenantMixin) — jamais lue du corps.
        """
        try:
            within = int(request.query_params.get('within', 30))
        except (TypeError, ValueError):
            within = 30
        if within < 0:
            within = 0
        today = timezone.localdate()
        limite = today + timedelta(days=within)
        qs = self.get_queryset().filter(
            type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin__isnull=False,
            contrat_date_fin__gte=today,
            contrat_date_fin__lte=limite,
        ).order_by('contrat_date_fin')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
