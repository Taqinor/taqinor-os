"""Vues des Réclamations & litiges (scopées société, accès admin/responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société + le créateur côté serveur (jamais du corps de requête).

Cycle de vie d'une réclamation — machine à états appliquée côté serveur :

    ouverte ─prendre_en_charge→ en_traitement ─resoudre→ resolue
       │                              │
       └──────── rejeter ─────────────┴──→ rejetee

Règles : on ne peut prendre en charge qu'une réclamation ``ouverte`` ; on ne
résout qu'une réclamation ``en_traitement`` ; on rejette une réclamation
``ouverte`` ou ``en_traitement``. Une réclamation déjà ``resolue`` ou
``rejetee`` est terminale — toute transition est refusée (400). Chaque
transition journalise automatiquement une entrée de chatter (ancien → nouveau
statut, auteur côté serveur).
"""
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import Reclamation, ReclamationActivity
from .serializers import ReclamationActivitySerializer, ReclamationSerializer


class _LitigesBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class ReclamationViewSet(_LitigesBaseViewSet):
    """Réclamations & litiges. Recherche par référence/objet/description."""
    queryset = Reclamation.objects.select_related('created_by').all()
    serializer_class = ReclamationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet', 'description']
    ordering_fields = ['id', 'gravite', 'date_creation']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    # ── Machine à états + chatter ────────────────────────────────────────────
    def _transition(self, request, *, allowed_from, target):
        """Applique une transition de statut si elle est légale, sinon 400.

        Journalise automatiquement le changement dans le chatter (auteur et
        société posés côté serveur).
        """
        reclamation = self.get_object()
        if reclamation.statut not in allowed_from:
            return Response(
                {'statut': (
                    f"Transition invalide depuis « "
                    f"{reclamation.get_statut_display()} » vers « "
                    f"{Reclamation.Statut(target).label} ».")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        old = reclamation.statut
        reclamation.statut = target
        reclamation.save(update_fields=['statut'])
        ReclamationActivity.objects.create(
            company=request.user.company,
            reclamation=reclamation,
            type=ReclamationActivity.Kind.LOG,
            old_value=old,
            new_value=target,
            auteur=request.user,
        )
        return Response(ReclamationSerializer(reclamation).data)

    @action(detail=True, methods=['post'], url_path='prendre-en-charge')
    def prendre_en_charge(self, request, pk=None):
        """ouverte → en_traitement."""
        return self._transition(
            request,
            allowed_from={Reclamation.Statut.OUVERTE},
            target=Reclamation.Statut.EN_TRAITEMENT,
        )

    @action(detail=True, methods=['post'], url_path='resoudre')
    def resoudre(self, request, pk=None):
        """en_traitement → resolue."""
        return self._transition(
            request,
            allowed_from={Reclamation.Statut.EN_TRAITEMENT},
            target=Reclamation.Statut.RESOLUE,
        )

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        """ouverte | en_traitement → rejetee."""
        return self._transition(
            request,
            allowed_from={
                Reclamation.Statut.OUVERTE,
                Reclamation.Statut.EN_TRAITEMENT,
            },
            target=Reclamation.Statut.REJETEE,
        )

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """Timeline chatter (auto + notes), du plus récent au plus ancien."""
        reclamation = self.get_object()
        return Response(
            ReclamationActivitySerializer(
                reclamation.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter')
    def noter(self, request, pk=None):
        """Note manuelle libre — auteur et société posés côté serveur."""
        reclamation = self.get_object()
        message = (request.data.get('message') or '').strip()
        if not message:
            return Response(
                {'message': 'Note vide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        act = ReclamationActivity.objects.create(
            company=request.user.company,
            reclamation=reclamation,
            type=ReclamationActivity.Kind.NOTE,
            message=message,
            auteur=request.user,
        )
        return Response(
            ReclamationActivitySerializer(act).data,
            status=status.HTTP_201_CREATED,
        )
