"""Vues de la Base de connaissances (scopées société, accès admin/responsable).

La base est INTERNE : les viewsets filtrent par ``request.user.company``
(TenantMixin) et posent la société + l'auteur côté serveur (jamais du corps de
requête). Les versions d'article sont des instantanés numérotés côté serveur
(``services.snapshot_article`` — max(version)+1, JAMAIS count()+1).
"""
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import services
from .models import KbArticle, KbArticleVersion
from .serializers import KbArticleSerializer, KbArticleVersionSerializer


class _KbBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class KbArticleViewSet(_KbBaseViewSet):
    """Articles de la base de connaissances. Recherche plein texte."""
    queryset = KbArticle.objects.select_related('auteur').all()
    serializer_class = KbArticleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['titre', 'corps', 'categorie', 'tags']
    ordering_fields = ['id', 'titre', 'date_modification']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)

    def perform_update(self, serializer):
        # Sauvegarde l'article (société re-posée côté serveur) puis fige un
        # instantané versionné du nouvel état.
        article = serializer.save(company=self.request.user.company)
        services.snapshot_article(article, auteur=self.request.user)

    @action(detail=True, methods=['post'], url_path='publier')
    def publier(self, request, pk=None):
        """Passe le statut à ``publie`` et fige une version (instantané)."""
        article = self.get_object()
        article.statut = KbArticle.Statut.PUBLIE
        article.save(update_fields=['statut', 'date_modification'])
        services.snapshot_article(article, auteur=request.user)
        return Response(
            self.get_serializer(article).data)

    @action(detail=True, methods=['post'], url_path='nouvelle-version')
    def nouvelle_version(self, request, pk=None):
        """Fige explicitement une nouvelle version sans changer le statut."""
        article = self.get_object()
        version = services.snapshot_article(article, auteur=request.user)
        return Response(
            KbArticleVersionSerializer(
                version, context={'request': request}).data)


class KbArticleVersionViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Historique des versions d'article (lecture seule). Filtrable par
    ``?article=<id>``. Société scopée côté serveur."""
    queryset = KbArticleVersion.objects.select_related(
        'article', 'auteur').all()
    serializer_class = KbArticleVersionSerializer
    permission_classes = [IsResponsableOrAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['version', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        article = self.request.query_params.get('article')
        if article:
            qs = qs.filter(article_id=article)
        return qs
