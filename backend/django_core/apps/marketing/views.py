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

from .models import ArcJourney, NoeudJourney
from .serializers import ArcJourneySerializer, NoeudJourneySerializer


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
