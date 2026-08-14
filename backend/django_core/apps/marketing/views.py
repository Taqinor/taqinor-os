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
from rest_framework.permissions import IsAuthenticated
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
    serializer = ParametresMarketingSerializer(
        parametres, data=request.data, partial=(request.method == 'PATCH'))
    serializer.is_valid(raise_exception=True)
    serializer.save()
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

@extend_schema(responses={200: OpenApiTypes.OBJECT})
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
