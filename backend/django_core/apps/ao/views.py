"""Vues du module Appels d'offres (``apps.ao``).

AOF1 — le CORPS des 8 ViewSets AO vit désormais ICI (il vivait encore dans
``apps.compta.views`` malgré la sortie ODX11 des modèles). ``apps.compta.views``
porte maintenant un shim de ré-export **INVERSE** (``from apps.ao.views import
…``) pour que ni les routes ``/api/django/compta/…`` ni les imports historiques
ne cassent.

ODX22 (`docs/PLAN.md`) reste OUVERT et n'est PAS atterri ici : il demande le
RETRAIT des shims transitoires — AOF1 en a seulement INVERSÉ le sens (compta →
ao devient ao → compta), ce qui est à prendre en compte le jour de son
déblocage.

Socle : ``_AoBaseViewSet`` est un ``core.viewsets.CompanyScopedModelViewSet``
(scoping ``request.user.company`` + ``company`` forcée côté serveur) qui
CONSERVE explicitement la garde historique ``IsResponsableOrAdmin`` — le
comportement d'accès est donc BYTE-IDENTIQUE à l'ancien ``_ComptaBaseViewSet``.
AOF3 remplacera cette base par ``apps.ao.viewsets.AoBaseViewSet`` (chatter
``records`` + permissions fines ``ao_voir``/``ao_gerer``).
"""

from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from . import services
from .models import (
    AppelOffre,
    BordereauPrix,
    CautionSoumission,
    DossierSoumission,
    EcheanceAO,
    LigneBordereau,
    PieceSoumission,
    ResultatAO,
)
from .serializers import (
    AppelOffreSerializer,
    BordereauPrixSerializer,
    CautionSoumissionSerializer,
    DossierSoumissionSerializer,
    EcheanceAOSerializer,
    LigneBordereauSerializer,
    PieceSoumissionSerializer,
    ResultatAOSerializer,
)


class _AoBaseViewSet(CompanyScopedModelViewSet):
    """Base transitoire : société scopée + accès Administrateur/Responsable.

    Identique en comportement à l'ancien ``_ComptaBaseViewSet`` de compta
    (``TenantMixin`` + ``ModelViewSet`` + ``IsResponsableOrAdmin``) ; seule la
    base change (``CompanyScopedModelViewSet``, socle ARC2). AOF3 la remplace
    par ``apps.ao.viewsets.AoBaseViewSet``.
    """
    permission_classes = [IsResponsableOrAdmin]


# ── FG222 — Gestion des appels d'offres ────────────────────────────────────

class AppelOffreViewSet(_AoBaseViewSet):
    """Objets appels d'offres public/privé (FG222)."""
    queryset = AppelOffre.objects.all()
    serializer_class = AppelOffreSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet', 'acheteur', 'lot']
    ordering_fields = ['date_creation', 'date_limite', 'statut']


# ── FG223 — Bordereau des prix (BOQ) ───────────────────────────────────────

class BordereauPrixViewSet(_AoBaseViewSet):
    """Bordereaux des prix (BOQ) d'AO (FG223), séparés du devis client."""
    queryset = BordereauPrix.objects.prefetch_related('lignes').all()
    serializer_class = BordereauPrixSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']


class LigneBordereauViewSet(_AoBaseViewSet):
    """Lignes chiffrées d'un BOQ (FG223)."""
    queryset = LigneBordereau.objects.all()
    serializer_class = LigneBordereauSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero']


# ── FG224 — Cautions & garanties de soumission ─────────────────────────────

class CautionSoumissionViewSet(_AoBaseViewSet):
    """Cautions de soumission (provisoires/définitives) d'AO (FG224)."""
    queryset = CautionSoumission.objects.all()
    serializer_class = CautionSoumissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'date_echeance', 'statut']


# ── FG225 — Dossier de soumission (pièces administratives) ─────────────────

class DossierSoumissionViewSet(_AoBaseViewSet):
    """Dossiers de soumission d'AO (FG225) : checklist des pièces."""
    queryset = DossierSoumission.objects.prefetch_related('pieces').all()
    serializer_class = DossierSoumissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']


class PieceSoumissionViewSet(_AoBaseViewSet):
    """Pièces administratives d'un dossier de soumission (FG225)."""
    queryset = PieceSoumission.objects.all()
    serializer_class = PieceSoumissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['libelle']


# ── FG226 — Échéancier & alertes de deadline d'AO ──────────────────────────

class EcheanceAOViewSet(_AoBaseViewSet):
    """Dates clés d'un AO avec rappels (FG226). L'action ``dues`` liste les
    échéances dont le rappel est échu et non traité."""
    queryset = EcheanceAO.objects.all()
    serializer_class = EcheanceAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_echeance', 'date_creation']

    @action(detail=False, methods=['get'])
    def dues(self, request):
        dues = services.echeances_ao_dues(request.user.company)
        return Response(EcheanceAOSerializer(dues, many=True).data)


# ── FG227 — Analyse gagné/perdu des appels d'offres ────────────────────────

class ResultatAOViewSet(_AoBaseViewSet):
    """Résultats d'AO pour l'analyse gagné/perdu (FG227). L'action ``stats``
    renvoie le taux de réussite consolidé."""
    queryset = ResultatAO.objects.all()
    serializer_class = ResultatAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'date_resultat']

    @action(detail=False, methods=['get'])
    def stats(self, request):
        return Response(services.taux_reussite_ao(request.user.company))
