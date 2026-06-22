"""Vues QHSE (scopées société, accès Administrateur/Responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; la non-conformité enregistre aussi son signaleur
(``signale_par``) côté serveur.
"""
from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import (
    ActionCorrectivePreventive, NonConformite, PlanInspectionChantier,
    PlanInspectionModele, PointControleModele, ReleveControle, ReleveCourbeIV,
)
from .serializers import (
    ActionCorrectivePreventiveSerializer, NonConformiteSerializer,
    PlanInspectionChantierSerializer, PlanInspectionModeleSerializer,
    PointControleModeleSerializer, ReleveControleSerializer,
    ReleveCourbeIVSerializer,
)
from .selectors import courbes_iv_for_chantier, hold_points_status
from .services import instancier_plan_chantier


class _QhseBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class NonConformiteViewSet(_QhseBaseViewSet):
    """Fiches de non-conformité (QHSE9). Recherche par référence/titre/origine."""
    queryset = NonConformite.objects.all()
    serializer_class = NonConformiteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'origine']
    ordering_fields = ['id', 'date_detection', 'date_creation']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            signale_par=self.request.user)


class ActionCorrectivePreventiveViewSet(_QhseBaseViewSet):
    """Actions correctives / préventives (CAPA — QHSE10)."""
    queryset = ActionCorrectivePreventive.objects.select_related(
        'non_conformite').all()
    serializer_class = ActionCorrectivePreventiveSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'cause_racine']
    ordering_fields = ['id', 'echeance', 'date_creation']


class PlanInspectionModeleViewSet(_QhseBaseViewSet):
    """Modèles de plan d'inspection (ITP — QHSE2). Recherche par code/nom."""
    queryset = PlanInspectionModele.objects.all()
    serializer_class = PlanInspectionModeleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom', 'description']
    ordering_fields = ['id', 'nom', 'date_creation']


class PointControleModeleViewSet(_QhseBaseViewSet):
    """Points de contrôle d'un modèle de plan d'inspection (ITP — QHSE2)."""
    queryset = PointControleModele.objects.select_related('plan').all()
    serializer_class = PointControleModeleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule', 'phase', 'description']
    ordering_fields = ['id', 'ordre', 'date_creation']


class PlanInspectionChantierViewSet(_QhseBaseViewSet):
    """Plans d'inspection appliqués à un chantier (ITP instancié — QHSE4).

    ``POST instancier`` ouvre un plan à partir d'un modèle + un ``chantier_id``
    et matérialise un relevé par point du modèle (idempotent).
    """
    queryset = PlanInspectionChantier.objects.select_related('modele').all()
    serializer_class = PlanInspectionChantierSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_ouverture', 'date_creation']

    @action(detail=False, methods=['post'])
    def instancier(self, request):
        """Ouvre un plan chantier depuis un modèle ITP + un chantier_id.

        Société posée côté serveur ; le modèle doit appartenir à la société
        de l'utilisateur (sinon 404). Idempotent.
        """
        company = request.user.company
        modele_id = request.data.get('modele')
        chantier_id = request.data.get('chantier_id')
        if not modele_id or chantier_id in (None, ''):
            return Response(
                {'detail': 'modele et chantier_id sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        # Scopé société : un modèle d'une autre société renvoie 404.
        modele = get_object_or_404(
            PlanInspectionModele, pk=modele_id, company=company)
        plan = instancier_plan_chantier(
            modele=modele,
            chantier_id=chantier_id,
            company=company,
            date_ouverture=request.data.get('date_ouverture') or None,
        )
        data = self.get_serializer(plan).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='hold-points')
    def hold_points(self, request, pk=None):
        """État de gating des points d'arrêt (QHSE6) du plan chantier.

        Renvoie ``peut_avancer`` et la liste des points d'arrêt bloquants (relevé
        absent ou non conforme). ``get_object`` est scopé société (TenantMixin),
        donc un plan d'une autre société renvoie 404. Lecture seule : ne mute
        jamais l'état du chantier — c'est une porte que l'appelant consulte.
        """
        plan = self.get_object()
        return Response(hold_points_status(plan))


class ReleveControleViewSet(_QhseBaseViewSet):
    """Relevés de contrôle d'un plan d'inspection chantier (QHSE4).

    À la création/maj d'un relevé, ``releve_par`` est posé côté serveur.
    """
    queryset = ReleveControle.objects.select_related(
        'plan_chantier', 'point').all()
    serializer_class = ReleveControleSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'date_releve', 'date_creation']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            releve_par=self.request.user)


class ReleveCourbeIVViewSet(_QhseBaseViewSet):
    """Relevés de courbe I-V par string PV à la mise en service (QHSE7).

    À la création, ``releve_par`` est posé côté serveur. Filtre optionnel par
    ``?chantier_id=`` (référence lâche au chantier). ``releves`` (action) liste
    les courbes I-V d'un chantier donné via le sélecteur dédié, scopé société.
    """
    queryset = ReleveCourbeIV.objects.select_related('plan_chantier').all()
    serializer_class = ReleveCourbeIVSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['string_id', 'notes']
    ordering_fields = ['id', 'string_id', 'date_releve', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        chantier_id = self.request.query_params.get('chantier_id')
        if chantier_id not in (None, ''):
            qs = qs.filter(chantier_id=chantier_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            releve_par=self.request.user)

    @action(detail=False, methods=['get'], url_path='par-chantier')
    def par_chantier(self, request):
        """Courbes I-V d'un chantier (``?chantier_id=``), scopées société.

        Lecture seule : délègue au sélecteur ``courbes_iv_for_chantier`` qui ne
        renvoie que les relevés de la société de l'utilisateur.
        """
        chantier_id = request.query_params.get('chantier_id')
        if chantier_id in (None, ''):
            return Response(
                {'detail': 'chantier_id est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        qs = courbes_iv_for_chantier(request.user.company, chantier_id)
        return Response(self.get_serializer(qs, many=True).data)
