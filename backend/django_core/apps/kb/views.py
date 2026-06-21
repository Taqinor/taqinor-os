"""Vues de la Base de connaissances (scopées société, accès admin/responsable).

La base est INTERNE : les viewsets filtrent par ``request.user.company``
(TenantMixin) et posent la société + l'auteur côté serveur (jamais du corps de
requête).
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import KbArticle
from .serializers import KbArticleSerializer


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
