"""Vues du module ``apps.datarooms`` (groupe NTDOC, P2).

Tout est scopé société (``CompanyScopedModelViewSet``, ARC2 : queryset filtré
sur ``request.user.company`` + ``company`` forcée côté serveur dans
``perform_create``). Aucun import de ``ged.models`` : la GED est lue via
``apps.ged.selectors`` (encapsulé par ``selectors.py`` de cette app).
"""
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from . import selectors, services
from .models import SalleDeDonnees, SalleDeDonneesDocument
from .serializers import (
    SalleDeDonneesDocumentSerializer, SalleDeDonneesSerializer,
)


class SalleDeDonneesViewSet(CompanyScopedModelViewSet):
    """CRUD des salles de données de la société (NTDOC11)."""

    queryset = SalleDeDonnees.objects.select_related(
        'company', 'dossier_source', 'created_by').all()
    serializer_class = SalleDeDonneesSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description', 'deal_type']
    ordering_fields = ['id', 'nom', 'created_at', 'statut']
    read_permission = 'datarooms_voir'
    write_permission = 'datarooms_gerer'

    def get_queryset(self):
        """Scope société (ARC2) + filtres optionnels ``?statut=``/``?deal_type=``."""
        qs = super().get_queryset()
        params = self.request.query_params
        for champ in ('statut', 'deal_type'):
            valeur = params.get(champ)
            if valeur:
                qs = qs.filter(**{champ: valeur})
        return qs

    def perform_create(self, serializer):
        """Société ET auteur posés côté serveur (jamais lus du corps)."""
        serializer.save(company=self.request.user.company,
                        created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """Contenu de la salle, dans l'ordre d'affichage."""
        salle = self.get_object()
        lignes = selectors.documents_de_salle(salle)
        return Response(
            SalleDeDonneesDocumentSerializer(lignes, many=True).data)

    @action(detail=True, methods=['post'], url_path='ajouter-documents')
    def ajouter_documents(self, request, pk=None):
        """Ajoute plusieurs documents GED existants à la salle, en un appel.

        Les ids sont résolus DANS la société de la salle : un id d'une autre
        société est simplement absent de la résolution (jamais un oracle)."""
        salle = self.get_object()
        ids = request.data.get('documents') or []
        if not isinstance(ids, list):
            return Response(
                {'detail': "« documents » doit être une liste d'identifiants."},
                status=status.HTTP_400_BAD_REQUEST)
        documents = list(
            selectors.documents_ged_disponibles(salle.company).filter(
                pk__in=[i for i in ids if str(i).isdigit()]))
        try:
            creees = services.ajouter_documents(salle, documents)
        except services.SalleFermee as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'ajoutes': len(creees),
             'ignores': max(len(ids) - len(creees), 0),
             'total': SalleDeDonneesDocument.objects.filter(
                 salle=salle).count()},
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='retirer-document')
    def retirer_document(self, request, pk=None):
        """Retire UN document de la salle — sans jamais le supprimer de la GED."""
        salle = self.get_object()
        document_id = request.data.get('document')
        document = selectors.documents_ged_disponibles(
            salle.company).filter(pk=document_id).first()
        if document is None:
            return Response(
                {'detail': "Ce document est introuvable dans votre société."},
                status=status.HTTP_404_NOT_FOUND)
        try:
            retire = services.retirer_document(salle, document)
        except services.SalleFermee as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'retire': retire}, status=status.HTTP_200_OK)


class SalleDeDonneesDocumentViewSet(CompanyScopedModelViewSet):
    """CRUD fin des appartenances document ↔ salle (ordre, visibilité)."""

    queryset = SalleDeDonneesDocument.objects.select_related(
        'company', 'salle', 'document').all()
    serializer_class = SalleDeDonneesDocumentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'ordre']
    read_permission = 'datarooms_voir'
    write_permission = 'datarooms_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        salle = self.request.query_params.get('salle')
        if salle:
            qs = qs.filter(salle_id=salle)
        return qs
