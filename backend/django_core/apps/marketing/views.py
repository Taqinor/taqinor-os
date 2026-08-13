"""Vues du module Marketing (``apps.marketing``).

ODX10 — ré-export TRANSITOIRE des ViewSets et vues publiques marketing qui
vivent encore dans ``apps.compta.views`` (interleavés avec les ViewSets
comptables et adossés à ``_ComptaBaseViewSet`` = ``TenantMixin`` +
``ModelViewSet``, avec le scoping ``request.user.company`` et l'assignation
forcée de ``company`` en ``perform_create``). Ce module donne aux nouvelles
routes ``/api/django/marketing/…`` un point d'entrée ``apps.marketing.views``
stable ; les anciennes routes ``/api/django/compta/…`` continuent de servir les
MÊMES classes. ODX22 re-logera le corps ici.
"""

from apps.compta.views import (  # noqa: F401
    # ViewSets marketing (mailing, séquences, tracking, formulaires, appels).
    AbonnementListeViewSet,
    AppelTelephoniqueViewSet,
    ApprobationEnvoiCampagneViewSet,
    AvisClientViewSet,
    BilletEvenementViewSet,
    CampagneViewSet,
    CommunicationEvenementViewSet,
    CompteFideliteViewSet,
    DomaineEnvoiViewSet,
    EnqueteNPSViewSet,
    EnqueteViewSet,
    EnvoiCampagneViewSet,
    EtapeSequenceViewSet,
    EvenementMarketingViewSet,
    FormulaireIntakeViewSet,
    InscriptionEvenementViewSet,
    InscriptionSequenceViewSet,
    ListeDiffusionViewSet,
    MessageWhatsAppEntrantViewSet,
    MouvementFideliteViewSet,
    OuverturePartageViewSet,
    QuestionEvenementViewSet,
    RegleUpsellViewSet,
    RelanceDevisAbandonneViewSet,
    SegmentMarketingViewSet,
    SequenceRelanceViewSet,
    SupportOfflineViewSet,
    TypeEvenementViewSet,
    # Vues publiques (token, sans login) : désinscription, opt-in, redirection
    # de lien tracké, enquêtes publiques + certificat, inscription événement,
    # webhooks Brevo / STOP SMS.
    desinscription_publique,
    double_optin_confirmer,
    enquete_certificat_pdf,
    enquete_publique,
    enquete_soumettre,
    evenement_inscription_publique,
    redirection_lien_tracke,
    webhook_brevo_campagne,
    webhook_sms_stop,
)
from apps.compta.views import _ComptaBaseViewSet

from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin

from . import services as marketing_services
from .models import ArcJourney, ModeleJourney, NoeudJourney
from .serializers import (
    ArcJourneySerializer, ModeleJourneySerializer, NoeudJourneySerializer,
)


# ── NTMKT12 — Journey en graphe (nœuds + arcs) ──────────────────────────────
# Scoping société hérité de ``_ComptaBaseViewSet`` (= ``TenantMixin``) :
# queryset filtré sur ``request.user.company`` + ``company`` forcée en
# ``perform_create`` (jamais lue du corps).

class NoeudJourneyViewSet(_ComptaBaseViewSet):
    """Nœuds du graphe d'une séquence de relance (NTMKT12)."""
    queryset = NoeudJourney.objects.all()
    serializer_class = NoeudJourneySerializer
    # YAPIC2 — whitelist de tri explicite (jamais '__all__').
    ordering_fields = ['id', 'sequence', 'type_noeud']
    search_fields = ['libelle']

    def get_queryset(self):
        qs = super().get_queryset()
        sequence = self.request.query_params.get('sequence')
        if sequence:
            qs = qs.filter(sequence_id=sequence)
        return qs


class ArcJourneyViewSet(_ComptaBaseViewSet):
    """Arcs (arêtes conditionnelles) du graphe d'un journey (NTMKT12)."""
    queryset = ArcJourney.objects.all()
    serializer_class = ArcJourneySerializer
    ordering_fields = ['id', 'source', 'ordre']
    search_fields = ['valeur']

    def get_queryset(self):
        qs = super().get_queryset()
        sequence = self.request.query_params.get('sequence')
        if sequence:
            qs = qs.filter(source__sequence_id=sequence)
        return qs


class ModeleJourneyViewSet(_ComptaBaseViewSet):
    """NTMKT15 — bibliothèque de modèles de journeys + instanciation."""
    queryset = ModeleJourney.objects.all()
    serializer_class = ModeleJourneySerializer
    ordering_fields = ['id', 'nom', 'categorie', 'date_creation']
    search_fields = ['nom', 'categorie']

    # YRBAC4 — garde explicite sur l'action custom (jamais héritée en creux).
    @action(detail=True, methods=['post'], url_path='instancier',
            permission_classes=[IsResponsableOrAdmin])
    def instancier(self, request, pk=None):
        """« Utiliser ce modèle » : crée une séquence ÉDITABLE (désactivée)
        portant une copie du graphe. La société vient de l'utilisateur."""
        modele = self.get_object()
        sequence = marketing_services.instancier_modele_journey(
            request.user.company, modele,
            nom=(request.data or {}).get('nom') or None,
            stage_declencheur=(request.data or {}).get(
                'stage_declencheur') or '',
        )
        return Response(
            {'sequence_id': sequence.id, 'nom': sequence.nom}, status=201)
