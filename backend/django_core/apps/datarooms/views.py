"""Vues du module ``apps.datarooms`` (groupe NTDOC, P2).

Tout est scopé société (``CompanyScopedModelViewSet``, ARC2 : queryset filtré
sur ``request.user.company`` + ``company`` forcée côté serveur dans
``perform_create``). Aucun import de ``ged.models`` : la GED est lue via
``apps.ged.selectors`` (encapsulé par ``selectors.py`` de cette app).
"""
from rest_framework import filters, status
from rest_framework.decorators import (
    action, api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from core.viewsets import CompanyScopedModelViewSet

from . import selectors, services
from .models import AccesSalleDonnees, SalleDeDonnees, SalleDeDonneesDocument
from .serializers import (
    AccesSalleDonneesSerializer, SalleDeDonneesDocumentSerializer,
    SalleDeDonneesSerializer,
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


class AccesSalleDonneesViewSet(CompanyScopedModelViewSet):
    """NTDOC12 — Gestion des accès viewer d'une salle (jamais public)."""

    queryset = AccesSalleDonnees.objects.select_related(
        'company', 'salle', 'created_by').all()
    serializer_class = AccesSalleDonneesSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'email']
    ordering_fields = ['id', 'nom', 'expires_at', 'derniere_consultation']
    read_permission = 'datarooms_voir'
    write_permission = 'datarooms_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        salle = self.request.query_params.get('salle')
        if salle:
            qs = qs.filter(salle_id=salle)
        return qs

    def perform_create(self, serializer):
        """Société ET auteur posés côté serveur ; jeton généré par le modèle."""
        serializer.save(company=self.request.user.company,
                        created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def revoquer(self, request, pk=None):
        """Révoque CET accès — les autres viewers de la salle ne bougent pas."""
        acces = self.get_object()
        services.revoquer_acces(acces)
        return Response(self.get_serializer(acces).data,
                        status=status.HTTP_200_OK)


# ── NTDOC12 — Accès PUBLIC (sans login) à une salle, par jeton viewer ───────

class PublicSalleRateThrottle(SimpleRateThrottle):
    """Limite le débit de l'accès public par IP + jeton.

    Même motif que `ged.PublicPartageRateThrottle` : décourage le balayage de
    jetons sans gêner un viewer légitime."""

    scope = 'public_dataroom'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (getattr(view, 'kwargs', None) or {}).get('token', '')
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{self.get_ident(request)}:{token}',
        }


def _dataroom_noindex(response):
    """Marque une réponse publique comme non-indexable par les moteurs."""
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _reponse_acces_introuvable():
    return _dataroom_noindex(Response(
        {'detail': "Ce lien d'accès est introuvable ou a été révoqué."},
        status=status.HTTP_404_NOT_FOUND))


def _reponse_acces_expire():
    return _dataroom_noindex(Response(
        {'detail': "Ce lien d'accès a expiré ou la salle a été fermée."},
        status=status.HTTP_410_GONE))


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicSalleRateThrottle])
def public_salle(request, token):
    """NTDOC12 — Sommaire d'une salle de données pour UN viewer (sans login).

    `GET /api/django/datarooms/public/<token>/`. Le jeton est l'UNIQUE secret :
    aucune identité ni société n'est lue de la requête, et il n'existe AUCUN
    listing (on ne résout QUE par jeton exact).

    Codes : 404 jeton inconnu OU révoqué (indistinct, pas de fuite) ; 410 lien
    expiré ou salle fermée ; 200 sommaire de la salle + documents VISIBLES.
    """
    statut, acces = services.resoudre_acces_public(token)
    if statut == services.ACCES_INTROUVABLE:
        return _reponse_acces_introuvable()
    if statut == services.ACCES_EXPIRE:
        return _reponse_acces_expire()

    services.marquer_consultation(acces)
    salle = acces.salle
    lignes = selectors.documents_de_salle(salle, visibles_seulement=True)
    return _dataroom_noindex(Response({
        'salle': {'nom': salle.nom, 'description': salle.description,
                  'deal_type': salle.deal_type},
        'viewer': {'nom': acces.nom, 'expires_at': acces.expires_at},
        'documents': [
            {'id': ligne.document_id,
             'nom': getattr(ligne.document, 'nom', '') or '',
             'ordre': ligne.ordre}
            for ligne in lignes
        ],
    }, status=status.HTTP_200_OK))
