"""API onboarding (NTDMO13/WIR59) — checklist « Premiers pas » de l'utilisateur.

Endpoints (company + user scopés côté serveur, jamais lus du corps) :

* ``GET  /api/django/onboarding/progress/`` — checklist résolue + résumé ;
* ``POST /api/django/onboarding/progress/{item_id}/ignorer/`` — masque un item ;
* ``POST /api/django/onboarding/progress/ignorer-tout/`` — masque tout le reste ;
* ``POST /api/django/onboarding/progress/{item_id}/marquer-fait/`` — WIR59,
  coche manuellement un item SANS ``event_key`` (aucun déclencheur
  automatique adapté sans importer une app métier — alternative explicite).
"""
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers as drf_serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import (
    IsAdminOrResponsableTier, IsAdminRole, est_operateur_plateforme,
)
from core.openapi_operations import SchemaObjetUnique

from apps.publicapi.auth import (
    ApiKeyAuthentication, ApiKeyRateThrottle, HasApiScope,
)
from apps.publicapi.portees import SCOPE_READ_LICENCE

from . import services, textes_csv
from .selectors import (
    items_masquables_pour_societe, pourcentage_activation_societe,
    resume_pour_utilisateur, tours_pour_utilisateur,
)


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


# ERR-ENF11-FUZZ-ONBOARDING — champs TYPES du résumé (``selectors.
# resume_pour_utilisateur``) : des ``JSONField(allow_null=True)`` sans type
# donnaient un schéma ``nullable`` sans ``type`` que la réponse réelle
# (liste / entiers / booléens) ne satisfaisait pas pour le contrôle api-fuzz.
_CHAMPS_RESUME_PROGRESSION = {
    'items': drf_serializers.ListField(child=drf_serializers.DictField()),
    'faits': drf_serializers.IntegerField(),
    'total': drf_serializers.IntegerField(),
    'pourcentage': drf_serializers.IntegerField(),
    'termine': drf_serializers.BooleanField(),
    'assistant_demarrage_auto': drf_serializers.BooleanField(),
}


_VIEWS_ONBOARDING_PROGRESS_VIEW_SET_MARQUER_FAIT_REPONSE = inline_serializer(
    'ViewsOnboardingProgressViewSetMarquerFaitReponse',
    {
        **_CHAMPS_RESUME_PROGRESSION,
    })


_VIEWS_ONBOARDING_PROGRESS_VIEW_SET_IGNORER_TOUT_REPONSE = inline_serializer(
    'ViewsOnboardingProgressViewSetIgnorerToutReponse',
    {
        **_CHAMPS_RESUME_PROGRESSION,
    })


_VIEWS_ONBOARDING_PROGRESS_VIEW_SET_IGNORER_REPONSE = inline_serializer(
    'ViewsOnboardingProgressViewSetIgnorerReponse',
    {
        **_CHAMPS_RESUME_PROGRESSION,
    })


_VIEWS_ONBOARDING_PROGRESS_VIEW_SET_LIST_REPONSE = inline_serializer('ViewsOnboardingProgressViewSetListReponse', {
    **_CHAMPS_RESUME_PROGRESSION,
})


#: ENF11 — paramètres de chemin des deux ``ViewSet`` sans queryset ci-dessous
#: (drf-spectacular ne peut pas les typer seul) : l'item de la checklist est
#: désigné par sa PK entière, un tour guidé par sa CLÉ texte.
_ID_ITEM_CHECKLIST = [OpenApiParameter(
    'id', OpenApiTypes.INT, OpenApiParameter.PATH,
    description="Identifiant de l'item de la checklist « Premiers pas ».")]
_CLE_TOUR = [OpenApiParameter(
    'id', OpenApiTypes.STR, OpenApiParameter.PATH,
    description='Clé du tour guidé (ex. « devis »).')]


class OnboardingProgressViewSet(viewsets.ViewSet):
    """Checklist « Premiers pas » de l'utilisateur courant (company-scopée)."""
    permission_classes = [IsAuthenticated]
    #: NTDMO35 — scope lu par ``HasApiScope`` pour l'action ``resume`` seule
    #: (statut d'adoption agrégé de la société : même famille que le statut
    #: de licence, ``read:licence`` ; aucun nouveau scope dans le registre).
    required_scope = SCOPE_READ_LICENCE
    #: ``list`` rend le résumé (UN objet), pas un tableau d'items.
    schema = SchemaObjetUnique()

    def _company(self, request):
        return getattr(request.user, 'company', None)

    @extend_schema(responses=inline_serializer('OnboardingResumePublic', {
        'pourcentage': drf_serializers.IntegerField()}))
    @action(detail=False, methods=['get'], url_path='resume',
            authentication_classes=[ApiKeyAuthentication],
            permission_classes=[HasApiScope],
            throttle_classes=[ApiKeyRateThrottle])
    def resume(self, request):
        """NTDMO35 — ``GET onboarding/progress/resume/`` : pourcentage
        d'activation AGRÉGÉ de la société de la clé, pour un badge externe.
        Authentifié par clé d'API (``publicapi.ApiKey``, jamais un nouveau
        mécanisme) ; 401 sans clé, 403 sans le scope. Lecture seule, un
        entier — jamais le détail des items ni de PII."""
        return Response({
            'pourcentage': pourcentage_activation_societe(
                request.auth.company)})

    @extend_schema(responses=_VIEWS_ONBOARDING_PROGRESS_VIEW_SET_LIST_REPONSE)
    def list(self, request):
        resume = resume_pour_utilisateur(
            self._company(request), request.user)
        return Response(resume)

    @extend_schema(request=None, parameters=_ID_ITEM_CHECKLIST,
                   responses=_VIEWS_ONBOARDING_PROGRESS_VIEW_SET_IGNORER_REPONSE)
    @action(detail=True, methods=['post'], url_path='ignorer',
            permission_classes=[IsAuthenticated])
    def ignorer(self, request, pk=None):
        services.ignorer_item(self._company(request), request.user, pk)
        return Response(
            resume_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)

    @extend_schema(request=None, responses=_VIEWS_ONBOARDING_PROGRESS_VIEW_SET_IGNORER_TOUT_REPONSE)
    @action(detail=False, methods=['post'], url_path='ignorer-tout',
            permission_classes=[IsAuthenticated])
    def ignorer_tout(self, request):
        services.ignorer_tout(self._company(request), request.user)
        return Response(
            resume_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)

    @extend_schema(request=None, parameters=_ID_ITEM_CHECKLIST,
                   responses=_VIEWS_ONBOARDING_PROGRESS_VIEW_SET_MARQUER_FAIT_REPONSE)
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

    @extend_schema(request=None, parameters=_CLE_TOUR,
                   responses=_ProductTourSerializer(many=True))
    @action(detail=True, methods=['post'], url_path='vu',
            permission_classes=[IsAuthenticated])
    def vu(self, request, pk=None):
        services.marquer_tour_vu(self._company(request), request.user, pk)
        return Response(
            tours_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)

    @extend_schema(request=None, parameters=_CLE_TOUR,
                   responses=_ProductTourSerializer(many=True))
    @action(detail=True, methods=['post'], url_path='revoir',
            permission_classes=[IsAuthenticated])
    def revoir(self, request, pk=None):
        services.reinitialiser_tour(self._company(request), request.user, pk)
        return Response(
            tours_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)


_ItemMasquableSerializer = inline_serializer('OnboardingItemMasquable', {
    'id': drf_serializers.IntegerField(),
    'key': drf_serializers.CharField(),
    'libelle': drf_serializers.CharField(),
    'masque': drf_serializers.BooleanField(),
}).__class__

# ``OnboardingItemsMasquesViewSet`` est un ``viewsets.ViewSet`` SANS queryset
# (le catalogue vient de ``OnboardingChecklistItem`` via le sélecteur, jamais
# une queryset de vue) : drf-spectacular ne peut donc pas déduire seul le
# type du paramètre de chemin ``id`` des actions ``detail=True`` — annoté ici
# explicitement (entier, pk de ``OnboardingChecklistItem``) plutôt que laissé
# en avertissement.
_ID_PATH_PARAMETER = [OpenApiParameter(
    'id', OpenApiTypes.INT, OpenApiParameter.PATH,
    description="Identifiant de l'item du catalogue « Premiers pas ».")]


class OnboardingItemsMasquesViewSet(viewsets.ViewSet):
    """NTDMO28 — masquage PAR SOCIÉTÉ d'items du catalogue « Premiers pas »
    (jamais une suppression du catalogue global — réversible, admin
    uniquement, Paramètres → Démo & Onboarding).

    * ``GET  /api/django/onboarding/items-masques/`` — catalogue global +
      statut masqué/visible pour la société courante ;
    * ``POST /api/django/onboarding/items-masques/{id}/masquer/`` ;
    * ``POST /api/django/onboarding/items-masques/{id}/demasquer/``.
    """
    permission_classes = [IsAdminOrResponsableTier]

    def _company(self, request):
        return getattr(request.user, 'company', None)

    @extend_schema(responses=_ItemMasquableSerializer(many=True))
    def list(self, request):
        return Response(items_masquables_pour_societe(self._company(request)))

    @extend_schema(request=None, responses=_ItemMasquableSerializer(many=True),
                   parameters=_ID_PATH_PARAMETER)
    @action(detail=True, methods=['post'], url_path='masquer',
            permission_classes=[IsAdminOrResponsableTier])
    def masquer(self, request, pk=None):
        services.masquer_item_pour_societe(self._company(request), pk)
        return Response(
            items_masquables_pour_societe(self._company(request)),
            status=status.HTTP_200_OK)

    @extend_schema(request=None, responses=_ItemMasquableSerializer(many=True),
                   parameters=_ID_PATH_PARAMETER)
    @action(detail=True, methods=['post'], url_path='demasquer',
            permission_classes=[IsAdminOrResponsableTier])
    def demasquer(self, request, pk=None):
        services.demasquer_item_pour_societe(self._company(request), pk)
        return Response(
            items_masquables_pour_societe(self._company(request)),
            status=status.HTTP_200_OK)


# NTDMO36 — export/réimport CSV des textes FR (admin société uniquement).
class OnboardingTextesExportView(APIView):
    """``GET /api/django/onboarding/export-textes.csv`` — libellés FR des tours
    et de la checklist (clé stable, écran cible, texte FR)."""
    permission_classes = [IsAdminRole]

    @extend_schema(responses={(200, "text/csv"): OpenApiTypes.STR})
    def get(self, request):
        reponse = HttpResponse(
            textes_csv.exporter_csv(request.user.company),
            content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = (
            "attachment; filename=\"onboarding-textes.csv\"")
        return reponse


class OnboardingTextesImportView(APIView):
    """``POST /api/django/onboarding/import-textes.csv`` (multipart, champ
    ``fichier``) — met à jour les textes existants par clé stable, sans doublon
    ni création. Les lignes du catalogue global exigent l'opérateur plateforme."""
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser]

    @extend_schema(request=inline_serializer("OnboardingTextesImport", {
        "fichier": drf_serializers.FileField()}),
        responses=inline_serializer("OnboardingTextesImportReponse", {
            "mis_a_jour": drf_serializers.IntegerField(),
            "inchanges": drf_serializers.IntegerField(),
            "ignorees": drf_serializers.IntegerField(),
            "inconnues": drf_serializers.ListField(
                child=drf_serializers.CharField())}))
    def post(self, request):
        fichier = request.FILES.get("fichier")
        if fichier is None:
            return Response(
                {"detail": "Fichier CSV manquant (champ « fichier »)."},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            res = textes_csv.importer_csv(
                fichier.read(), request.user.company,
                peut_ecrire_global=est_operateur_plateforme(request.user))
        except (ValueError, UnicodeDecodeError) as exc:
            return Response({"detail": str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(res)
