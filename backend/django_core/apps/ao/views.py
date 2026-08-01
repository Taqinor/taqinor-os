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

Socle (AOF3) : les 8 ViewSets héritent de ``apps.ao.viewsets.AoBaseViewSet`` =
``core.viewsets.CompanyScopedModelViewSet`` (scoping ``request.user.company`` +
``company`` forcée côté serveur, détection par le sweep d'isolation
multi-tenant) + chatter générique ``records``, gardé par ``ao_voir`` (lecture)
et ``ao_gerer`` (écriture). L'ancienne garde grossière ``IsResponsableOrAdmin``
héritée de ``_ComptaBaseViewSet`` est ABANDONNÉE : elle ouvrait tout le dossier
d'appel d'offres au palier Responsable (cf. AOF2).
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import (
    AppelOffre,
    BordereauPrix,
    CautionSoumission,
    DossierSoumission,
    EcheanceAO,
    ExigenceCPS,
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
    ExigenceCPSSerializer,
    LigneBordereauSerializer,
    PieceSoumissionSerializer,
    ResultatAOSerializer,
)
from .viewsets import AoBaseViewSet


def _filtres_exacts(queryset, params, champs):
    """Applique les filtres d'égalité ``?champ=valeur`` présents dans l'URL.

    ``DjangoFilterBackend`` n'est PAS monté dans ce projet : le filtrage des
    listes AO se fait explicitement, avec les mêmes noms que les champs du
    modèle (voir le contrat d'API publié par AOF31).
    """
    for champ in champs:
        valeur = params.get(champ)
        if valeur in (None, ''):
            continue
        queryset = queryset.filter(**{champ: valeur})
    return queryset


# ── FG222 — Gestion des appels d'offres ────────────────────────────────────

class AppelOffreViewSet(AoBaseViewSet):
    """Objets appels d'offres public/privé (FG222)."""
    queryset = AppelOffre.objects.all()
    serializer_class = AppelOffreSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'reference_acheteur', 'objet', 'acheteur',
                     'maitre_ouvrage', 'soumissionnaire', 'reference_cps',
                     'lot']
    ordering_fields = ['date_creation', 'date_limite', 'date_ouverture_plis',
                       'statut']
    #: AOF12 — filtres d'égalité exposés en paramètres de requête.
    FILTRES_EXACTS = ('statut', 'type_marche', 'mode_passation')

    def get_queryset(self):
        qs = _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            self.FILTRES_EXACTS)
        groupement = self.request.query_params.get('groupement')
        if groupement not in (None, ''):
            qs = qs.filter(
                groupement=groupement.lower() in ('1', 'true', 'vrai', 'oui'))
        return qs

    def perform_create(self, serializer):
        """AOF5 — référence auto ``AO-YYYYMM-0001`` quand elle n'est pas fournie.

        La société reste posée CÔTÉ SERVEUR dans les deux branches (jamais lue
        du corps de requête) : ``super()`` pour la branche « référence
        fournie », ``serializer.save(company=…)`` dans la fabrique de référence
        pour l'autre.
        """
        if (serializer.validated_data.get('reference') or '').strip():
            return super().perform_create(serializer)
        societe = self.request.user.company
        services.creer_appel_offre_avec_reference(
            societe,
            lambda reference: serializer.save(
                company=societe, reference=reference),
        )

    @action(detail=True, methods=['post'], url_path='changer-statut')
    def changer_statut(self, request, pk=None):
        """AOF13 — SEUL chemin HTTP de mutation du statut d'un AO.

        Une transition interdite par ``services.TRANSITIONS_AO`` répond 400
        avec un message en français listant les statuts atteignables.
        """
        appel_offre = self.get_object()
        try:
            services.changer_statut_ao(
                appel_offre, request.data.get('statut'), user=request.user,
                motif=(request.data.get('motif') or ''))
        except DjangoValidationError as exc:
            return Response(exc.message_dict if hasattr(exc, 'message_dict')
                            else {'statut': exc.messages},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(appel_offre).data)

    @action(detail=True, methods=['get'], url_path='transitions')
    def transitions(self, request, pk=None):
        """Statuts atteignables depuis l'état courant (pilote l'UI)."""
        appel_offre = self.get_object()
        libelles = dict(AppelOffre.Statut.choices)
        cibles = services.transitions_possibles(appel_offre.statut)
        return Response({
            'statut': appel_offre.statut,
            'statut_display': libelles.get(appel_offre.statut, ''),
            'transitions': [
                {'valeur': s, 'libelle': libelles[s]} for s in cibles
            ],
        })


# ── AOF14 — Exigences du CPS ───────────────────────────────────────────────

class ExigenceCPSViewSet(AoBaseViewSet):
    """Clauses chiffrées du CPS d'un AO (AOF14). Aucune exigence d'ASSURANCE
    ici : elles vivent dans ``apps.assurances`` (``ExigenceAssuranceMarche``,
    rattachée par sa string-FK ``marche_ref``)."""
    queryset = ExigenceCPS.objects.all()
    serializer_class = ExigenceCPSSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle', 'valeur_texte']
    ordering_fields = ['code', 'type_exigence', 'bloquant']

    def get_queryset(self):
        return _filtres_exacts(
            super().get_queryset(), self.request.query_params,
            ('appel_offre', 'type_exigence', 'bloquant'))


# ── FG223 — Bordereau des prix (BOQ) ───────────────────────────────────────

class BordereauPrixViewSet(AoBaseViewSet):
    """Bordereaux des prix (BOQ) d'AO (FG223), séparés du devis client."""
    queryset = BordereauPrix.objects.prefetch_related('lignes').all()
    serializer_class = BordereauPrixSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']


class LigneBordereauViewSet(AoBaseViewSet):
    """Lignes chiffrées d'un BOQ (FG223)."""
    queryset = LigneBordereau.objects.all()
    serializer_class = LigneBordereauSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero']


# ── FG224 — Cautions & garanties de soumission ─────────────────────────────

class CautionSoumissionViewSet(AoBaseViewSet):
    """Cautions de soumission (provisoires/définitives) d'AO (FG224)."""
    queryset = CautionSoumission.objects.all()
    serializer_class = CautionSoumissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'date_echeance', 'statut']


# ── FG225 — Dossier de soumission (pièces administratives) ─────────────────

class DossierSoumissionViewSet(AoBaseViewSet):
    """Dossiers de soumission d'AO (FG225) : checklist des pièces."""
    queryset = DossierSoumission.objects.prefetch_related('pieces').all()
    serializer_class = DossierSoumissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']


class PieceSoumissionViewSet(AoBaseViewSet):
    """Pièces administratives d'un dossier de soumission (FG225)."""
    queryset = PieceSoumission.objects.all()
    serializer_class = PieceSoumissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['libelle']


# ── FG226 — Échéancier & alertes de deadline d'AO ──────────────────────────

class EcheanceAOViewSet(AoBaseViewSet):
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

class ResultatAOViewSet(AoBaseViewSet):
    """Résultats d'AO pour l'analyse gagné/perdu (FG227). L'action ``stats``
    renvoie le taux de réussite consolidé."""
    queryset = ResultatAO.objects.all()
    serializer_class = ResultatAOSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'date_resultat']

    @action(detail=False, methods=['get'])
    def stats(self, request):
        return Response(services.taux_reussite_ao(request.user.company))
