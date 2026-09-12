"""NTUX33 — API publique LECTURE SEULE des favoris épinglés et des vues
sauvegardées (apps.uxviews), sous /api/public/v1/. Authentifiée par clé
d'API existante (`ApiKeyAuthentication`, jamais un nouveau mécanisme
d'auth), scopée à la société de la clé — jamais un paramètre client
(`PublicReadOnlyViewSet.get_queryset`, même socle que toutes les autres
ressources publiques).

CONSENTEMENT — une clé d'API n'a pas de notion de session utilisateur ; le
paramètre `?owner=<id>` en tient lieu explicitement :

  * ``favoris/`` REFUSE (400) sans `?owner=` — un favori est TOUJOURS
    strictement personnel (NTUX12, "un favori d'un collègue est invisible,
    même pour un Directeur") : il n'existe aucune vue "company-wide" sûre à
    renvoyer par défaut ;
  * ``saved-views/`` renvoie par défaut UNIQUEMENT les vues PARTAGÉES À
    L'ÉQUIPE (déjà visibles en interne par tout collaborateur de la société,
    cf. `apps.uxviews.views.SavedViewViewSet.get_queryset`) — jamais une vue
    personnelle d'un tiers sans son `?owner=`.

Dans les deux cas, `?owner=<id>` restreint STRICTEMENT aux lignes de CET
utilisateur (`owner_id=<id>`, scoping composé avec la société de la clé —
un id d'une autre société ne matche simplement aucune ligne, jamais une
fuite cross-tenant).
"""
from rest_framework.exceptions import ValidationError

from apps.uxviews.models import FavoriUtilisateur, SavedView

from .constants import SCOPE_READ_FAVORIS, SCOPE_READ_VUES
from .public_serializers import PublicFavoriSerializer, PublicSavedViewSerializer
from .public_views import PublicReadOnlyViewSet


class PublicFavoriViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_FAVORIS
    serializer_class = PublicFavoriSerializer
    queryset = FavoriUtilisateur.objects.select_related('content_type').order_by(
        'owner_id', 'ordre')
    filter_whitelist = ('owner',)
    ordering_fields = ('id', 'ordre')
    sync_field = 'updated_at'

    def get_queryset(self):
        if not self.request.query_params.get('owner'):
            raise ValidationError({'owner': (
                "Paramètre requis : un favori est strictement personnel, "
                "précisez l'utilisateur consentant via ?owner=<id>.")})
        return super().get_queryset()


class PublicSavedViewViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_VUES
    serializer_class = PublicSavedViewSerializer
    queryset = SavedView.objects.select_related('owner').order_by('ecran', 'nom')
    filter_whitelist = ('ecran', 'owner')
    ordering_fields = ('id', 'ecran', 'nom')
    sync_field = 'updated_at'

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.query_params.get('owner'):
            # Pas de consentement explicite d'un utilisateur précis : seules
            # les vues déjà visibles en interne de TOUTE la société (jamais
            # une vue personnelle d'un tiers).
            qs = qs.filter(visibilite=SavedView.Visibilite.EQUIPE)
        return qs
