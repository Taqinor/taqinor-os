"""API onboarding (NTDMO13/WIR59) — checklist « Premiers pas » de l'utilisateur.

Endpoints (company + user scopés côté serveur, jamais lus du corps) :

* ``GET  /api/django/onboarding/progress/`` — checklist résolue + résumé ;
* ``POST /api/django/onboarding/progress/{item_id}/ignorer/`` — masque un item ;
* ``POST /api/django/onboarding/progress/ignorer-tout/`` — masque tout le reste ;
* ``POST /api/django/onboarding/progress/{item_id}/marquer-fait/`` — WIR59,
  coche manuellement un item SANS ``event_key`` (aucun déclencheur
  automatique adapté sans importer une app métier — alternative explicite).
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .selectors import resume_pour_utilisateur, tours_pour_utilisateur


# Classe PARTAGEE (fabriquee UNE SEULE fois) : appeler inline_serializer() a
# nouveau creerait une deuxieme classe Python de meme nom, vue par
# drf-spectacular comme un composant en collision (« identical names,
# different identities »). Les 3 endpoints (list/vu/revoir) renvoient tous
# une liste (many=True) de la MEME classe.
_ProductTourSerializer = inline_serializer('ProductTour', {
    'tour_key': drf_serializers.CharField(),
    'ecran_cible': drf_serializers.CharField(),
    'vu': drf_serializers.BooleanField(),
    'vu_le': drf_serializers.DateTimeField(allow_null=True),
    'etapes': drf_serializers.ListField(child=inline_serializer(
        'ProductTourEtape', {
            'ordre': drf_serializers.IntegerField(),
            'selecteur': drf_serializers.CharField(),
            'titre': drf_serializers.CharField(),
            'texte': drf_serializers.CharField(),
        })),
}).__class__


class OnboardingProgressViewSet(viewsets.ViewSet):
    """Checklist « Premiers pas » de l'utilisateur courant (company-scopée)."""
    permission_classes = [IsAuthenticated]

    def _company(self, request):
        return getattr(request.user, 'company', None)

    def list(self, request):
        resume = resume_pour_utilisateur(
            self._company(request), request.user)
        return Response(resume)

    @action(detail=True, methods=['post'], url_path='ignorer',
            permission_classes=[IsAuthenticated])
    def ignorer(self, request, pk=None):
        services.ignorer_item(self._company(request), request.user, pk)
        return Response(
            resume_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='ignorer-tout',
            permission_classes=[IsAuthenticated])
    def ignorer_tout(self, request):
        services.ignorer_tout(self._company(request), request.user)
        return Response(
            resume_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='marquer-fait',
            permission_classes=[IsAuthenticated])
    def marquer_fait(self, request, pk=None):
        """WIR59 — coche manuellement un item (alternative à l'auto-
        complétion par événement quand aucun jalon de bus n'existe)."""
        services.marquer_fait_manuel(self._company(request), request.user, pk)
        return Response(
            resume_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)


class ProductTourViewSet(viewsets.ViewSet):
    """NTDMO14/15/16 — catalogue des visites guidées (« product tours »),
    company + user scopés côté serveur (jamais lus du corps).

    * ``GET  /api/django/onboarding/tours/`` — catalogue des 6 tours + statut
      vu/non-vu pour l'utilisateur courant (un seul appel réseau) ;
    * ``POST /api/django/onboarding/tours/{key}/vu/`` — marque un tour
      vu/fermé (idempotent) ;
    * ``POST /api/django/onboarding/tours/{key}/revoir/`` — NTDMO16, remet le
      tour à zéro pour l'utilisateur courant SEULEMENT (bouton « Revoir » des
      Paramètres)."""
    permission_classes = [IsAuthenticated]

    def _company(self, request):
        return getattr(request.user, 'company', None)

    @extend_schema(responses=_ProductTourSerializer(many=True))
    def list(self, request):
        return Response(tours_pour_utilisateur(self._company(request), request.user))

    @extend_schema(request=None, responses=_ProductTourSerializer(many=True))
    @action(detail=True, methods=['post'], url_path='vu',
            permission_classes=[IsAuthenticated])
    def vu(self, request, pk=None):
        services.marquer_tour_vu(self._company(request), request.user, pk)
        return Response(
            tours_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)

    @extend_schema(request=None, responses=_ProductTourSerializer(many=True))
    @action(detail=True, methods=['post'], url_path='revoir',
            permission_classes=[IsAuthenticated])
    def revoir(self, request, pk=None):
        services.reinitialiser_tour(self._company(request), request.user, pk)
        return Response(
            tours_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)
