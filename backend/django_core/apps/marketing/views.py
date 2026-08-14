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

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin

from . import selectors as marketing_selectors
from . import services as marketing_services
from .models import (
    ArcJourney, BlocContenu, Campagne, ModeleJourney, NoeudJourney,
    VersionFormulaireIntake,
)
from .serializers import (
    ArcJourneySerializer, BlocContenuSerializer, ModeleJourneySerializer,
    NoeudJourneySerializer, ParametresMarketingSerializer,
    VersionFormulaireIntakeSerializer,
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


@extend_schema(responses={200: inline_serializer('HeatmapEngagement', {
    'cellules': drf_serializers.ListField(child=inline_serializer(
        'HeatmapEngagementCellule', {
            'jour': drf_serializers.IntegerField(),
            'heure': drf_serializers.IntegerField(),
            'envois': drf_serializers.IntegerField(),
            'ouvertures': drf_serializers.IntegerField(),
            'taux_ouverture': drf_serializers.FloatField(),
        })),
    'meilleur': inline_serializer('HeatmapEngagementMeilleur', {
        'jour': drf_serializers.IntegerField(),
        'heure': drf_serializers.IntegerField(),
        'envois': drf_serializers.IntegerField(),
        'ouvertures': drf_serializers.IntegerField(),
        'taux_ouverture': drf_serializers.FloatField(),
    }, required=False, allow_null=True),
    'total_envois': drf_serializers.IntegerField(),
})})
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsResponsableOrAdmin])
def heatmap_engagement_view(request):
    """NTMKT24 — heatmap jour × heure des taux d'ouverture de la société.

    LECTURE SEULE et purement informative (suggestion de moment d'envoi) : la
    société vient TOUJOURS de ``request.user``, jamais d'un paramètre.
    """
    try:
        jours = int(request.query_params.get('jours') or 180)
    except (TypeError, ValueError):
        jours = 180
    return Response(marketing_selectors.heatmap_engagement(
        request.user.company, jours=jours))


class BlocContenuViewSet(_ComptaBaseViewSet):
    """NTMKT23 — bibliothèque de blocs de contenu réutilisables."""
    queryset = BlocContenu.objects.all()
    serializer_class = BlocContenuSerializer
    ordering_fields = ['id', 'nom', 'type_bloc', 'date_creation']
    search_fields = ['nom', 'contenu']


class VersionFormulaireIntakeViewSet(_ComptaBaseViewSet):
    """NTMKT16 — versions éditoriales d'une landing page + publication."""
    queryset = VersionFormulaireIntake.objects.all()
    serializer_class = VersionFormulaireIntakeSerializer
    ordering_fields = ['id', 'version', 'date_creation']
    search_fields = ['titre']

    def get_queryset(self):
        qs = super().get_queryset()
        formulaire = self.request.query_params.get('formulaire')
        if formulaire:
            qs = qs.filter(formulaire_id=formulaire)
        return qs

    def perform_create(self, serializer):
        """Chaque édition crée une NOUVELLE version : le numéro est calculé
        côté serveur (jamais lu du corps), la société vient du formulaire."""
        formulaire = serializer.validated_data['formulaire']
        version = marketing_services.creer_version_formulaire(
            formulaire, serializer.validated_data)
        serializer.instance = version

    # YRBAC4 — garde explicite sur l'action custom.
    @action(detail=True, methods=['post'], url_path='publier',
            permission_classes=[IsResponsableOrAdmin])
    def publier(self, request, pk=None):
        """« Publier cette version » : la page publique bascule dessus."""
        version = self.get_object()
        marketing_services.publier_version_formulaire(version)
        return Response(self.get_serializer(version).data)


# ── NTMKT26 — Import de coûts publicitaires externes (CSV) ─────────────────

_IMPORT_COUTS_REQUEST = inline_serializer('ImporterCoutsPublicitairesRequest', {
    'fichier': drf_serializers.FileField(),
})
_IMPORT_COUTS_RESPONSE = inline_serializer('ImporterCoutsPublicitairesRapport', {
    'matched': drf_serializers.ListField(child=drf_serializers.DictField()),
    'unmatched': drf_serializers.ListField(child=drf_serializers.DictField()),
    'erreur': drf_serializers.CharField(required=False),
})


@extend_schema(request={'multipart/form-data': _IMPORT_COUTS_REQUEST},
               responses={200: _IMPORT_COUTS_RESPONSE})
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsResponsableOrAdmin])
def importer_couts_publicitaires_view(request):
    """Importe un CSV (export Meta Ads Manager/Google Ads) et réconcilie
    ``Campagne.cout_reel_mad`` par nom (NTMKT26). Aucun appel externe."""
    fichier = request.FILES.get('fichier')
    if fichier is None:
        return Response({'detail': 'fichier requis'}, status=400)
    rapport = marketing_services.importer_couts_publicitaires(
        request.user.company, fichier.read(), fichier.name)
    return Response(rapport)


# ── NTMKT27 — Bilan de campagne (PDF interne) ───────────────────────────────

@extend_schema(responses={200: OpenApiTypes.BINARY})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def campagne_rapport_pdf_view(request, pk=None):
    """Génère le bilan PDF interne d'une campagne (NTMKT27) — jamais
    ``Produit.prix_achat``, jamais le moteur ``quote_engine`` (règle #4)."""
    campagne = get_object_or_404(
        Campagne, pk=pk, company=request.user.company)
    pdf_bytes = marketing_services.rapport_campagne_pdf(campagne)
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'attachment; filename="bilan_campagne_{campagne.id}.pdf"')
    return resp


# ── NTMKT28 — Registre de consentement (export CNDP, PDF) ──────────────────

@extend_schema(responses={200: OpenApiTypes.BINARY})
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsResponsableOrAdmin])
def registre_consentement_export_pdf_view(request):
    """Export PDF du registre de consentement de la société (NTMKT28),
    filtrable par période/contact — lecture seule, jamais un second
    registre."""
    pdf_bytes = marketing_services.registre_consentement_pdf(
        request.user.company,
        date_debut=request.query_params.get('date_debut') or None,
        date_fin=request.query_params.get('date_fin') or None,
        contact=request.query_params.get('contact') or None,
    )
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = (
        'attachment; filename="registre_consentement.pdf"')
    return resp


# ── NTMKT31 — Réglages tenant « Marketing » ─────────────────────────────────

@extend_schema(request=ParametresMarketingSerializer,
               responses=ParametresMarketingSerializer)
@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated, IsResponsableOrAdmin])
def parametres_marketing_view(request):
    """Réglages société du module Marketing (NTMKT31) — singleton
    get_or_create, jamais un id passé par le client."""
    parametres = marketing_services.parametres_marketing_pour(
        request.user.company)
    if request.method == 'GET':
        return Response(ParametresMarketingSerializer(parametres).data)
    ancien_modele = parametres.modele_attribution
    serializer = ParametresMarketingSerializer(
        parametres, data=request.data, partial=(request.method == 'PATCH'))
    serializer.is_valid(raise_exception=True)
    serializer.save()
    # NTMKT45 — journalise UNIQUEMENT un changement RÉEL du modèle
    # d'attribution (NTMKT20), jamais un PATCH qui ne le touche pas.
    if serializer.instance.modele_attribution != ancien_modele:
        marketing_services.journaliser_modele_attribution(
            serializer.instance, request.user, ancien_modele)
    return Response(serializer.data)


# ── NTMKT18/19 — Score de maturité d'un lead (lecture, pour la fiche/kanban) ─

_SCORE_MATURITE_RESPONSE = inline_serializer('ScoreMaturiteLead', {
    'lead_id': drf_serializers.IntegerField(),
    'actif': drf_serializers.BooleanField(),
    'valeur': drf_serializers.IntegerField(),
    'historique': drf_serializers.ListField(child=inline_serializer(
        'VariationScoreMaturite', {
            'delta': drf_serializers.IntegerField(),
            'valeur_apres': drf_serializers.IntegerField(),
            'motif': drf_serializers.CharField(),
            'created_at': drf_serializers.DateTimeField(),
        })),
})


@extend_schema(responses={200: _SCORE_MATURITE_RESPONSE})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def score_maturite_lead_view(request, lead_id):
    """NTMKT18/19 — score de maturité courant + historique d'un lead
    (société toujours dérivée de ``request.user``, jamais du paramètre).
    ``actif=False`` (module désactivé pour la société) → ``valeur=0``,
    ``historique=[]``, jamais une erreur."""
    parametres = marketing_services.parametres_marketing_pour(
        request.user.company)
    if not parametres.score_maturite_actif:
        return Response({'lead_id': lead_id, 'actif': False, 'valeur': 0,
                         'historique': []})
    score = marketing_services.recalculer_score_maturite(
        request.user.company, lead_id)
    historique = marketing_services.historique_maturite(
        request.user.company, lead_id)
    return Response({
        'lead_id': lead_id,
        'actif': True,
        'valeur': score.valeur if score else 0,
        'historique': [
            {'delta': v.delta, 'valeur_apres': v.valeur_apres,
             'motif': v.motif, 'created_at': v.created_at}
            for v in historique
        ],
    })


# ── NTMKT20 — Comparaison des modèles d'attribution (?devis_id=) ───────────

def _forme_repartition_attribution(nom):
    """PACT7 — forme d'UNE répartition : la liste des points de contact du
    lead avec le revenu qui leur est attribué. Miroir EXACT de
    ``apps.crm.selectors._attribution_part`` (la source) et des colonnes lues
    par ``features/marketing/AttributionReport.jsx``. Une fabrique, pas une
    constante : chaque ``inline_serializer`` doit recevoir ses PROPRES
    instances de champs (un champ DRF se lie à un seul serializer)."""
    return inline_serializer(nom, {
        'point_contact_id': drf_serializers.IntegerField(),
        'canal': drf_serializers.CharField(),
        'canal_libelle': drf_serializers.CharField(),
        'date_contact': drf_serializers.DateTimeField(),
        'revenu_attribue': drf_serializers.CharField(),
    }, many=True)


# PACT7 — forme REELLE de la réponse (jamais « un objet » : une forme vide
# valide tout, donc elle ne protège rien). Les 4 clés de ``modeles`` sont
# celles de ``apps.crm.selectors.ATTRIBUTION_MODELES``, exactement celles que
# l'écran indexe (`donnees.modeles?.[modele]`).
@extend_schema(responses=inline_serializer('AttributionComparaison', {
    'devis_id': drf_serializers.IntegerField(),
    'lead_id': drf_serializers.IntegerField(),
    'total_revenu': drf_serializers.CharField(),
    'nb_points_contact': drf_serializers.IntegerField(),
    'modele_actuel': drf_serializers.CharField(),
    'modeles': inline_serializer('AttributionComparaisonModeles', {
        'dernier_touche': _forme_repartition_attribution(
            'AttributionPartDernierTouche'),
        'premier_touche': _forme_repartition_attribution(
            'AttributionPartPremierTouche'),
        'lineaire': _forme_repartition_attribution(
            'AttributionPartLineaire'),
        'pondere_temporel': _forme_repartition_attribution(
            'AttributionPartPondereTemporel'),
    }),
}))
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attribution_comparaison_view(request):
    """NTMKT20 — répartition du revenu d'un devis SIGNÉ entre ses points de
    contact, pour les 4 modèles d'attribution côte à côte (``?devis_id=``).
    404 propre si le devis n'existe pas / n'est pas accepté / hors société —
    jamais une fuite d'existence cross-société."""
    devis_id = request.query_params.get('devis_id')
    if not devis_id:
        return Response({'detail': 'devis_id requis.'}, status=400)
    resultat = marketing_services.attribution_comparaison(
        request.user.company, devis_id)
    if resultat is None:
        return Response(
            {'detail': 'Devis introuvable ou non accepté.'}, status=404)
    return Response(resultat)


# ── NTMKT39 — Export CSV/XLSX des campagnes et de leur trace d'envoi ───────

@extend_schema(responses={200: OpenApiTypes.BINARY})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_campagnes_xlsx_view(request):
    """NTMKT39 — export XLSX des campagnes filtrées (``?statut=&canal=``,
    mêmes colonnes que la liste)."""
    contenu = marketing_services.export_campagnes_xlsx(
        request.user.company,
        statut=request.query_params.get('statut') or None,
        canal=request.query_params.get('canal') or None,
    )
    # NTMKT45 — traçabilité RGPD des extractions.
    marketing_services.journaliser_export_marketing(
        request.user, request.user.company,
        detail='Export XLSX des campagnes.')
    resp = HttpResponse(
        contenu,
        content_type=(
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet'))
    resp['Content-Disposition'] = 'attachment; filename="campagnes.xlsx"'
    return resp


@extend_schema(responses={200: OpenApiTypes.BINARY})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_envois_campagne_csv_view(request, pk=None):
    """NTMKT39 — export CSV de la trace d'envoi (``EnvoiCampagne``) d'UNE
    campagne."""
    campagne = get_object_or_404(
        Campagne, pk=pk, company=request.user.company)
    contenu = marketing_services.export_envois_campagne_csv(campagne)
    # NTMKT45 — traçabilité RGPD des extractions.
    marketing_services.journaliser_export_marketing(
        request.user, request.user.company, instance=campagne,
        detail=f'Export CSV de la trace d\'envoi — campagne « {campagne.nom} ».')
    resp = HttpResponse(contenu, content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = (
        f'attachment; filename="envois_campagne_{pk}.csv"')
    return resp


# ── NTMKT40 — Export XLSX des segments et de leurs membres ─────────────────

@extend_schema(responses={200: OpenApiTypes.BINARY})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_membres_segment_xlsx_view(request, pk=None):
    """NTMKT40 — export XLSX des membres RÉSOLUS d'un segment marketing (au
    moment de l'export, audit RGPD/CNDP)."""
    from .models import SegmentMarketing

    segment = get_object_or_404(
        SegmentMarketing, pk=pk, company=request.user.company)
    contenu = marketing_services.export_membres_segment_xlsx(segment)
    # NTMKT45 — traçabilité RGPD des extractions.
    marketing_services.journaliser_export_marketing(
        request.user, request.user.company, instance=segment,
        detail=f'Export XLSX des membres — segment « {segment.nom} ».')
    resp = HttpResponse(
        contenu,
        content_type=(
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet'))
    resp['Content-Disposition'] = (
        f'attachment; filename="segment_{pk}_membres.xlsx"')
    return resp


# ── NTMKT41 — Import CSV de contacts d'événement (hors formulaire public) ──

_IMPORT_INSCRITS_REQUEST = inline_serializer(
    'ImporterInscritsEvenementRequest',
    {'fichier': drf_serializers.FileField()})
_IMPORT_INSCRITS_RESPONSE = inline_serializer(
    'ImporterInscritsEvenementRapport', {
        'crees': drf_serializers.IntegerField(),
        'doublons': drf_serializers.IntegerField(),
        'lignes_invalides': drf_serializers.IntegerField(),
        'total': drf_serializers.IntegerField(),
    })


@extend_schema(request={'multipart/form-data': _IMPORT_INSCRITS_REQUEST},
               responses={200: _IMPORT_INSCRITS_RESPONSE})
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsResponsableOrAdmin])
def importer_inscriptions_evenement_view(request, pk=None):
    """NTMKT41 — importe un CSV/XLSX de participants (ex. salon partenaire)
    en inscriptions en masse, sans passer par le formulaire public."""
    from .models import EvenementMarketing

    evenement = get_object_or_404(
        EvenementMarketing, pk=pk, company=request.user.company)
    fichier = request.FILES.get('fichier')
    if fichier is None:
        return Response({'detail': 'fichier requis.'}, status=400)
    rapport = marketing_services.importer_inscriptions_evenement(
        evenement, fichier.read(), fichier.name)
    return Response(rapport)


# ── NTMKT44 — Notifications internes sur événements marketing clés ─────────
# XMKT21 (seuil MQL) notifie déjà le commercial assigné
# (``apps.crm.services.maybe_assign_mql``, idempotent via
# ``Lead.mql_assigned_at``) — non dupliqué ici. Les deux compléments
# ci-dessous ENVELOPPENT les points d'entrée ``apps.compta`` existants SANS
# les modifier (jamais un import de leurs modèles, juste leur fonction
# publique), pour ajouter la notification sans toucher à un fichier hors
# périmètre CRM_VENTES.

class CampagneViewSetAudite(CampagneViewSet):
    """NTMKT45 — étend ``CampagneViewSet`` (``apps.compta.views``) SANS le
    modifier : journalise l'envoi RÉEL d'une campagne (qui/quand/combien de
    destinataires) dans ``apps.audit`` (jamais un second journal).
    Enregistrée à la place de la classe de base UNIQUEMENT dans le routeur
    marketing — la route legacy `/compta/…` continue de servir la classe de
    base inchangée, sans journalisation."""

    def envoyer(self, request, pk=None):
        response = super().envoyer(request, pk)
        if response.status_code == 200 and not response.data.get(
                'approbation_requise'):
            marketing_services.journaliser_envoi_campagne(
                self.get_object(), request.user)
        return response


class EnqueteNPSViewSetNotifiant(EnqueteNPSViewSet):
    """NTMKT44 — étend ``EnqueteNPSViewSet`` (``apps.compta.views``) SANS le
    modifier : notifie le commercial du lead sur une réponse détractrice.
    Enregistrée à la place de la classe de base UNIQUEMENT dans le routeur
    marketing (``apps.marketing.urls``) — la route legacy `/compta/…`
    continue de servir la classe de base inchangée."""

    def repondre(self, request, pk=None):
        response = super().repondre(request, pk)
        if response.status_code == 200:
            marketing_services.notifier_si_nps_detracteur(self.get_object())
        return response


@extend_schema(request=inline_serializer(
    'EvenementInscriptionNotifianteRequest', {
        'nom': drf_serializers.CharField(),
        'email': drf_serializers.CharField(required=False, allow_blank=True),
        'telephone': drf_serializers.CharField(
            required=False, allow_blank=True),
        'billet_id': drf_serializers.IntegerField(
            required=False, allow_null=True),
        'reponses_questions': drf_serializers.DictField(
            required=False, allow_null=True,
            help_text='Réponses aux questions de l\'événement, par id.'),
    }), responses={201: inline_serializer(
        'EvenementInscriptionNotifianteResponse', {
            'id': drf_serializers.IntegerField(),
            'qr_token': drf_serializers.CharField(),
        })})
@api_view(['POST'])
@permission_classes([AllowAny])
def evenement_inscription_publique_notifiante(request, evenement_id):
    """NTMKT44 — même contrat public que ``evenement_inscription_publique``
    (XMKT28, ``apps.compta.views``, jamais modifiée) : inscrit un
    participant à un événement SANS authentification, PUIS notifie le
    commercial du lead résolu. Validations dupliquées ici (nom requis,
    billet existant) plutôt que d'appeler la vue décorée d'origine (évite un
    double-dispatch DRF imbriqué sur une ``Request`` déjà convertie)."""
    from .models import BilletEvenement, EvenementMarketing

    evenement = EvenementMarketing.objects.filter(id=evenement_id).first()
    if not evenement:
        return Response({'detail': 'Événement introuvable.'}, status=404)
    nom = (request.data.get('nom') or '').strip()
    if not nom:
        return Response({'detail': 'nom requis.'}, status=400)
    billet = None
    billet_id = request.data.get('billet_id')
    if billet_id:
        billet = BilletEvenement.objects.filter(
            id=billet_id, evenement=evenement).first()
        if not billet:
            return Response({'detail': 'Billet introuvable.'}, status=404)
    try:
        inscription = marketing_services.inscrire_evenement_et_notifier(
            evenement, nom=nom,
            email=request.data.get('email', ''),
            telephone=request.data.get('telephone', ''), billet=billet,
            reponses_questions=request.data.get('reponses_questions'))
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    return Response(
        {'id': inscription.id, 'qr_token': inscription.qr_token}, status=201)
