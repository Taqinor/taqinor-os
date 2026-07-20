"""Vues du moteur publicitaire Meta Ads (Groupe ENG).

ENG1 n'expose qu'un endpoint de liveness ``status/`` (``{ok: true}``) — les
ViewSets métier (connexion, garde-fous, actions) atterrissent aux tâches
suivantes de la lane et sont tous basés sur
``core.viewsets.CompanyScopedModelViewSet`` (scoping société garanti).
"""
import logging
import os

from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import HasPermissionOrLegacy
from core.permissions import _user_has_or_legacy
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    AdCampaignMirror, AdEngineActivity,
    Annotation, AnomalyEvent, ArmDailyStat, AssumptionNode,
    BrandKit, CommentMirror,
    CompetitorAdObservation, CompetitorPage, ConsentRecord,
    CreativeAsset, CreativeBacklogItem, CreativeGenerationBatch,
    CreativePolicy, DecisionLog, EngineAction, EngineAlert, Experiment,
    ExperimentArm, FactEntry, FactTable, FlightPhase, FlightPlan,
    GuardrailConfig,
    InstagramCommentMirror, InstagramMediaMirror, InstagramPublishJob,
    MetaConnection, ProposalTemplate, ReconciliationSnapshot, RulePolicy,
    WeeklyBrief,
)
from .serializers import (
    AdCampaignMirrorSerializer, AnnotationSerializer, AnomalyEventSerializer,
    ArmDailyStatSerializer,
    AssumptionNodeSerializer, BrandKitSerializer,
    CompetitorAdObservationSerializer, CompetitorPageSerializer,
    CommentMirrorSerializer, ConsentRecordSerializer, CreativeAssetSerializer,
    CreativeBacklogItemSerializer, CreativeGenerationBatchSerializer,
    CreativePolicySerializer, DecisionLogSerializer, EngineActionSerializer,
    EngineAlertSerializer, ExperimentArmSerializer, ExperimentSerializer,
    FactEntrySerializer, FactTableSerializer,
    FlightPhaseSerializer, FlightPlanSerializer, GuardrailConfigSerializer,
    InstagramCommentMirrorSerializer, InstagramMediaMirrorSerializer,
    MetaConnectionSerializer, ProposalTemplateSerializer,
    ReconciliationSnapshotSerializer, RulePolicySerializer,
)

logger = logging.getLogger(__name__)


class StatusView(APIView):
    """ENG1 — Liveness du module publicitaire.

    ``GET /api/django/adsengine/status/`` renvoie ``{"ok": true}`` pour un
    utilisateur authentifié. Ne divulgue aucun secret ni aucune donnée société ;
    sert seulement à confirmer que l'app est installée et routée.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'ok': True})


# ENG12 — clés d'environnement dont l'endpoint santé rapporte la PRÉSENCE (jamais
# la valeur). Lead Ads (webhook), CAPI (conversions serveur), fabrique créative.
# PUB29 — étendu aux familles de clés jusque-là INVISIBLES de l'écran santé :
# CAPI CRM-stage (ADSENG32), CAPI CRM Dataset/signatures Odoo (ADSDEEP27-29),
# connecteur Odoo lecture seule (ADSENG-ODOO), webhook WhatsApp Cloud (ADSDEEP24)
# — chacune une boucle déjà codée et testée qui attend juste sa clé.
WIRING_ENV_KEYS = (
    'META_LEAD_ADS_APP_SECRET',
    'META_LEAD_ADS_VERIFY_TOKEN',
    'META_CAPI_ACCESS_TOKEN',
    'META_CAPI_PIXEL_ID',
    'ZAPCAP_API_KEY',
    'FAL_API_KEY',
    'TEMPLATED_API_KEY',
    'ELEVENLABS_API_KEY',
    'JSON2VIDEO_API_KEY',
    # PUB29 — CAPI par étape du pipeline CRM (Conversion Leads, ADSENG32).
    'META_CRM_STAGE_CAPI_ENABLED',
    # PUB29 — CAPI CRM Dataset (signatures Odoo, ADSDEEP27-29).
    'CAPI_CRM_DATASET_ID',
    'CAPI_CRM_ACCESS_TOKEN',
    # PUB29 — connecteur Odoo lecture seule (coût-par-signature réel).
    'ODOO_URL',
    'ODOO_DB',
    'ODOO_USERNAME',
    'ODOO_API_KEY',
    # PUB29 — webhook WhatsApp Cloud API (attribution CTWA, ADSDEEP24).
    'WHATSAPP_CLOUD_VERIFY_TOKEN',
    'WHATSAPP_CLOUD_APP_SECRET',
    'WHATSAPP_CLOUD_COMPANY_ID',
)


# ADSDEEP16 — message FR actionnable quand la lecture d'un post de Page échoue
# (piège n°1 : un System User sans l'asset Page assigné, dossier creative §4).
_PAGE_ASSET_FIX_FR = (
    "Le token n'a pas accès à l'asset Page. Correctif : Business Settings → "
    "Comptes → Pages → sélectionner la Page → « Attribuer des personnes » (ou "
    "« Assign Assets ») → ajouter le System User avec la tâche « Gérer la Page ». "
    "Avoir le scope dans le token NE SUFFIT PAS — l'asset Page doit être assigné "
    "au System User (piège fréquent des ads CTWA)."
)


def _page_asset_probe(company, conn):
    """ADSDEEP16 — Teste la lecture d'un ``effective_object_story_id`` (post de
    Page réellement diffusé). Renvoie ``{status, message}`` avec ``status`` ∈
    ``ok``/``error``/``inconnu`` : ``ok`` (vert) si un post se lit, ``error``
    (rouge) + correctif FR exact si Meta refuse (typiquement asset Page non
    assigné au System User), ``inconnu`` si rien à sonder (no-op propre)."""
    if conn is None or not conn.is_live:
        return {'status': 'inconnu',
                'message': "Connexion Meta inactive — sonde non exécutée."}

    from .models import AdCreativeMirror

    story_id = (AdCreativeMirror.objects
                .filter(company=company)
                .exclude(effective_object_story_id='')
                .values_list('effective_object_story_id', flat=True)
                .first())
    if not story_id:
        return {'status': 'inconnu',
                'message': "Aucun post de Page diffusé à sonder pour l'instant."}

    from .meta_client import MetaClient, MetaError

    try:
        client = MetaClient.from_connection(conn)
        client._request('GET', str(story_id), params={'fields': 'id'})
    except MetaError:
        return {'status': 'error', 'message': _PAGE_ASSET_FIX_FR}
    except Exception:  # noqa: BLE001 — jamais casser la santé sur un imprévu
        return {'status': 'error', 'message': _PAGE_ASSET_FIX_FR}
    return {'status': 'ok',
            'message': "Accès à l'asset Page confirmé (post lisible)."}


class WiringHealthView(APIView):
    """ENG12 — Santé du câblage publicitaire (pour le dashboard ENG23).

    ``GET /api/django/adsengine/wiring-health/`` — company-scopé, gaté par
    ``adsengine_view``. Rapporte la seule PRÉSENCE (booléen) de chaque clé
    d'environnement (Lead Ads / CAPI / fabrique) — **jamais la valeur** — plus la
    présence d'un token de connexion, la dernière synchro réussie, et (non encore
    câblés) le dernier webhook Lead Ads / événement CAPI. Aucun secret ne fuit.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _user_has_or_legacy(request.user, 'adsengine_view'):
            return Response({'detail': 'Permission refusée.'}, status=403)
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)

        from .models import InsightSnapshot

        # PRÉSENCE uniquement — jamais la valeur du secret.
        keys = {name: bool(os.environ.get(name)) for name in WIRING_ENV_KEYS}

        conn = MetaConnection.objects.filter(company=company).first()
        connection = {
            'exists': conn is not None,
            'enabled': bool(conn and conn.enabled),
            'has_token': bool(conn and conn.has_token),  # présence, pas le token
        }

        last_snap = (InsightSnapshot.objects
                     .filter(company=company)
                     .order_by('-updated_at')
                     .values_list('updated_at', flat=True)
                     .first())

        # ADSENG17 — santé du Gardien : heartbeat de l'évaluateur de règles
        # (le watchdog détecte un beat/worker Celery arrêté). Aucun secret.
        from .watchdog import health as guardian_health

        # ADSDEEP5 — % d'usage rate-limit Meta observé sur la dernière réponse
        # (backoff préventif avant le 613). None si aucune synchro récente.
        from .meta_client import rate_limit_status
        rate_limit = rate_limit_status(conn.ad_account_id) if conn else None

        # PUB29 — boucles déjà codées/testées qui attendent SEULEMENT leur clé
        # (le fondateur ne pouvait pas les voir avant) : ON/OFF + remédiation FR
        # exacte par boucle. Panneau ConnectionScreen « Boucles en attente
        # d'activation » (frontend, lane console) consomme ce même payload.
        from .audit import pending_activation_loops

        return Response({
            'keys': keys,
            'connection': connection,
            'last_successful_sync': (
                last_snap.isoformat() if last_snap else None),
            # Câblés par les groupes Meta Lead Ads / CAPI (gated) — non encore
            # disponibles : rapportés None honnêtement, jamais fabriqués.
            'last_lead_ads_webhook': None,
            'last_capi_event': None,
            'guardian': guardian_health(company),
            # ADSDEEP5 — santé du débit Meta (% d'usage, palier, drapeau throttled).
            'rate_limit': rate_limit,
            # ADSDEEP16 — sonde d'accès à l'asset Page (lecture d'un post diffusé).
            'page_asset_access': _page_asset_probe(company, conn),
            # PUB29 — boucles en attente d'activation (ON/OFF + remédiation FR).
            'boucles_en_attente': pending_activation_loops(),
        })


class CostPerSignatureView(APIView):
    """ENG10 — Métrique coût-par-signature (héro-chiffre du dashboard).

    ``GET /api/django/adsengine/metrics/cout-par-signature/`` — company-scopé
    (jamais d'autre société), gaté par ``adsengine_view``. Renvoie l'agrégat +
    le détail par campagne AVEC les ids de leads derrière chaque chiffre
    (traçabilité). Aucun secret exposé.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _user_has_or_legacy(request.user, 'adsengine_view'):
            return Response({'detail': 'Permission refusée.'}, status=403)
        from .metrics import cost_per_signature_summary
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        return Response(cost_per_signature_summary(company))


class EngagementAudienceView(APIView):
    """ADSDEEP59 — Audiences d'engagement (picker du composeur d'adset).

    ``GET  /api/django/adsengine/audiences/engagement/`` — catalogue des presets
    (openers/dropoff/submitted, page_engaged, IG engaged) + rétention (dossier
    §3). Gaté ``adsengine_view``.
    ``POST /api/django/adsengine/audiences/engagement/`` — crée une audience
    d'engagement (``{preset_key, name?, source_id?}``). Gaté ``adsengine_manage``.

    NON gated par le consentement Custom Audience : une audience d'engagement est
    un objet Meta-side (interactions formulaire/Page/IG) — AUCUNE donnée CRM n'est
    envoyée. Company-scopé (le client Meta est résolu depuis la connexion de la
    société de l'utilisateur).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _user_has_or_legacy(request.user, 'adsengine_view'):
            return Response({'detail': 'Permission refusée.'}, status=403)
        from .audiences import engagement_preset_catalog
        return Response({'presets': engagement_preset_catalog()})

    def post(self, request):
        if not _user_has_or_legacy(request.user, 'adsengine_manage'):
            return Response({'detail': 'Permission refusée.'}, status=403)
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        preset_key = (request.data or {}).get('preset_key')
        if not preset_key:
            return Response({'detail': 'preset_key requis.'}, status=400)
        from .audiences import create_engagement_audience
        try:
            result = create_engagement_audience(
                company, preset_key=preset_key,
                name=(request.data or {}).get('name'),
                source_id=(request.data or {}).get('source_id'))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(result)


class GroundedGenerationView(APIView):
    """PUB16 — Déclenche la génération IA ANCRÉE (AGEN2), câblée depuis
    BacklogScreen / CreativeLibrary (« Générer des variantes ancrées »).

    ``POST /api/django/adsengine/generation/variantes-ancrees/`` avec
    ``{seed_brief, components?, max_variants?}`` → tâche async qui produit un LOT
    de variantes dont CHAQUE chiffre cite une ``FactEntry`` publiée (assets nés
    PENDING, lot EN_ATTENTE d'approbation humaine — l'IA produit des ASSETS,
    jamais des décisions). Key-gated : sans ``ADSENGINE_GEN_API_KEY``, message
    clair (200, ``enabled=False``) et AUCUN lot créé (zéro crash). Gaté
    ``adsengine_manage`` ; company-scopé.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _user_has_or_legacy(request.user, 'adsengine_manage'):
            return Response({'detail': 'Permission refusée.'}, status=403)
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        seed_brief = str((request.data or {}).get('seed_brief', '') or '')
        if not seed_brief.strip():
            return Response({'detail': 'seed_brief requis.'}, status=400)
        components = (request.data or {}).get('components') or []
        # Key-gated : message clair AVANT dispatch (pas de tâche inutile ni de
        # lot créé sans clé — zéro crash).
        from .generation import GEN_ENV_KEY
        if not os.environ.get(GEN_ENV_KEY):
            return Response({
                'enabled': False,
                'detail': ('Génération IA désactivée : la clé '
                           f"{GEN_ENV_KEY} n'est pas configurée. Aucun lot créé."),
            }, status=200)
        from .tasks import generate_grounded_variants
        generate_grounded_variants.delay(
            company.id, seed_brief, components=components)
        return Response({
            'enabled': True,
            'detail': ('Génération lancée : le lot de variantes ancrées '
                       'apparaîtra dans le backlog pour approbation.'),
        }, status=202)


class AudienceDeliveryEstimateView(APIView):
    """ADSDEEP59 — Estimation d'audience AVANT usage (dossier §5), montrée dans le
    picker avant de créer/utiliser une audience.

    ``POST /api/django/adsengine/audiences/delivery-estimate/`` avec
    ``{targeting_spec, optimization_goal?}`` — LECTURE SEULE (aucune mutation,
    aucune donnée CRM) → gaté ``adsengine_view``. Company-scopé.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _user_has_or_legacy(request.user, 'adsengine_view'):
            return Response({'detail': 'Permission refusée.'}, status=403)
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        targeting_spec = (request.data or {}).get('targeting_spec')
        if not targeting_spec:
            return Response({'detail': 'targeting_spec requis.'}, status=400)
        from .audiences import engagement_delivery_estimate
        result = engagement_delivery_estimate(
            company, targeting_spec=targeting_spec,
            optimization_goal=(
                (request.data or {}).get('optimization_goal') or 'REACH'))
        return Response(result)


class AdsengineViewSet(CompanyScopedModelViewSet):
    """Base des ViewSets du moteur publicitaire.

    Hérite de ``CompanyScopedModelViewSet`` (scoping ``request.user.company`` +
    forçage société côté serveur garantis, SCA4). Gate lecture/écriture par les
    permissions fines ``adsengine_view`` / ``adsengine_manage`` (lues par
    ``ScopedPermission`` selon la méthode HTTP). L'approbation (``adsengine_approve``)
    est une permission DISTINCTE, portée par les actions concernées (ENG7).
    """

    read_permission = 'adsengine_view'
    write_permission = 'adsengine_manage'


class MetaConnectionViewSet(AdsengineViewSet):
    """ENG2 — CRUD de la connexion Meta (une par société).

    ``credentials`` est write-only (jamais relu) ; ``company`` est posée côté
    serveur. Aucun secret ne fuit dans une réponse GET.
    """

    queryset = MetaConnection.objects.all()
    serializer_class = MetaConnectionSerializer


class GuardrailConfigViewSet(AdsengineViewSet):
    """ENG3 — CRUD des garde-fous publicitaires (un jeu par société).

    ``company`` posée côté serveur. L'activation d'une campagne n'est aucun
    champ ici : elle reste interdite en dur au niveau service
    (``guardrails.enforce``).
    """

    queryset = GuardrailConfig.objects.all()
    serializer_class = GuardrailConfigSerializer


# PUB2 — Contexte MDE/coût par défaut de la file VoI. ``delta_plausible``/``p``/
# ``cost`` ne sont PAS stockés sur le nœud (ils dépendent des volumes du test) :
# un contexte documenté et UNIFORME sur les candidats laisse le classement être
# piloté par S·U·R RÉELS du nœud (enjeux/incertitude/pertinence). Révisés
# trimestriellement ; aucune migration. (Miroir de ``simulator._TESTABLE_CTX``.)
VOI_DEFAULT_BASE_RATE = 0.02        # p — taux de base (conversion lien)
VOI_DEFAULT_DELTA_PLAUSIBLE = 0.5   # effet plausible relatif par défaut
VOI_DEFAULT_TEST_N = 25200          # essais/bras (volume hebdo typique)
VOI_DEFAULT_COST = 1.0              # coût unitaire neutre (ranking par S·U·R·T)


class AssumptionNodeViewSet(AdsengineViewSet):
    """ASG1 — CRUD des nœuds de l'Assumption Engine (dd-assumption-engine
    §3.1), company-scopé. ``company`` posée côté serveur ; ``parent`` et
    ``invalidation_links`` isolés à la MÊME société côté serializer.

    PUB2 — trois actions LECTURE que « L'Arbre » (TreeScreen) appelle :
    ``file-voi`` (classement VoI réel via ``voi.rank_candidates``), ``<id>/tests``
    (historique des décisions/tests du nœud) et ``tests/<id>/leads`` (drill leads
    réels derrière un test, via les sélecteurs CRM — jamais un import cross-app)."""

    queryset = AssumptionNode.objects.all()
    serializer_class = AssumptionNodeSerializer

    @action(detail=False, methods=['get'], url_path='file-voi',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def file_voi(self, request):
        """ASG3 — File de priorité VoI (argmax S·U·R·T/C) de la société. Sortie
        RÉELLE de ``voi.rank_candidates`` (nœuds non-retirés), classée décroissante
        avec le RANG déjà calculé côté serveur (l'écran n'en recalcule rien)."""
        from . import voi

        company = request.user.company
        ctx = {
            'delta_plausible': VOI_DEFAULT_DELTA_PLAUSIBLE,
            'p': VOI_DEFAULT_BASE_RATE,
            'n': VOI_DEFAULT_TEST_N,
            'cost': VOI_DEFAULT_COST,
        }
        candidates = (AssumptionNode.objects
                      .filter(company=company)
                      .exclude(statut=AssumptionNode.Statut.RETIRED))
        params = {node.pk: ctx for node in candidates}
        ranking = voi.rank_candidates(company, params)
        rows = []
        for rang, (node, score) in enumerate(ranking, 1):
            rows.append({
                'node_id': node.pk,
                'enonce_fr': node.enonce_fr,
                'classe': node.classe,
                'classe_display': node.get_classe_display(),
                'voi': round(float(score['voi']), 6),
                'rang': rang,
                'S': round(float(score['S']), 4),
                'U': round(float(score['U']), 4),
                'R': round(float(score['R']), 4),
                'T': round(float(score['T']), 4),
                'C': round(float(score['C']), 4),
            })
        return Response(rows)

    @action(detail=True, methods=['get'],
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def tests(self, request, pk=None):
        """Historique de tests d'un nœud = les DÉCISIONS (``DecisionLog``) qui ont
        ouvert un slot POUR ce nœud (``allocations.winner_node_id``) — « l'arbre à
        travers le temps ». Chaque ligne porte l'expérience contenante + le résumé
        FR de la décision. Company-scopé (``get_object`` borne déjà à la société)."""
        node = self.get_object()
        company = request.user.company
        logs = (DecisionLog.objects
                .filter(company=company, allocations__winner_node_id=node.pk)
                .select_related('experiment')
                .order_by('-created_at'))
        rows = []
        for log in logs:
            exp = log.experiment
            rows.append({
                'id': log.pk,
                'nom': (exp.name if exp else f'Décision #{log.pk}'),
                'statut_display': (exp.get_status_display() if exp else '—'),
                'verdict_display': (log.summary_fr or '')[:160],
                'quand': log.created_at.date().isoformat(),
            })
        return Response(rows)

    @action(detail=False, methods=['get'],
            url_path=r'tests/(?P<test_id>[^/.]+)/leads',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def test_leads(self, request, test_id=None):
        """Leads RÉELS derrière un test = leads attribués aux ads des bras de
        l'expérience de cette décision (jointure ``ExperimentArm.ad_id`` ↔
        ``meta_ad_id`` du lead). Lecture CRM UNIQUEMENT via ``apps.crm.selectors``
        (contrat cross-app). Company-scopé : une décision d'autrui → 404."""
        company = request.user.company
        log = (DecisionLog.objects
               .filter(company=company, pk=test_id)
               .select_related('experiment')
               .first())
        if log is None:
            return Response({'detail': 'Test introuvable.'}, status=404)
        exp = log.experiment
        ad_ids = set()
        if exp is not None:
            ad_ids = set(
                ExperimentArm.objects
                .filter(company=company, experiment=exp)
                .exclude(ad_id='')
                .values_list('ad_id', flat=True))
        if not ad_ids:
            return Response([])

        from apps.crm.selectors import attribution_lead_rows, lead_card

        rows = []
        for row in attribution_lead_rows(company):
            if row.get('meta_ad_id') and row['meta_ad_id'] in ad_ids:
                card = lead_card(row['id'], company)
                if card is None:
                    continue
                rows.append({
                    'id': row['id'],
                    'nom': card['label'],
                    'stage_label': card['subtitle'],
                    'url': card['url'],
                })
        return Response(rows)


class AnnotationViewSet(AdsengineViewSet):
    """PUB49 — CRUD des annotations de courbe (notes de décision épinglées à une
    date), company-scopées. ``company`` posée côté serveur ; le front les affiche
    en surimpression sur les courbes Dashboard/Reporting (overlay = lane console).
    """

    queryset = Annotation.objects.all()
    serializer_class = AnnotationSerializer


class FactTableViewSet(AdsengineViewSet):
    """AGEN1 — CRUD des tables de faits versionnées + publication.

    ``POST`` crée toujours un nouveau BROUILLON (version calculée côté
    serveur, ``FactTable.create_draft``) ; ``publish`` dépublie toute autre
    table publiée de la société et publie celle-ci (une seule active à la
    fois)."""

    queryset = FactTable.objects.all()
    serializer_class = FactTableSerializer

    @action(detail=True, methods=['post'],
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def publish(self, request, pk=None):
        table = self.get_object()
        table.publish()
        return Response(self.get_serializer(table).data)


class FactEntryViewSet(AdsengineViewSet):
    """AGEN1 — CRUD des entrées de table de faits (une clé → une valeur
    vérifiée). ``table`` isolée à la même société côté serializer."""

    queryset = FactEntry.objects.all()
    serializer_class = FactEntrySerializer


class ConsentRecordViewSet(AdsengineViewSet):
    """PUB75 — CRUD du registre de consentement image/témoignage (CNDP loi 09-08).

    Company-scopé (hérité) ; ``company`` posée côté serveur. La révocation passe
    par l'action dédiée ``revoquer`` (jamais un PATCH direct de ``revoked_at``) :
    elle retire aussitôt de la rotation les assets liés (``policy.revoke_consent``).
    L'UI de collecte simple (lien WhatsApp signable) enregistre ici le
    consentement recueilli.
    """

    queryset = ConsentRecord.objects.all()
    serializer_class = ConsentRecordSerializer

    @action(detail=True, methods=['post'],
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def revoquer(self, request, pk=None):
        """PUB75 — Révoque le consentement : les assets « client réel » qui le
        citent sont immédiatement retirés de la rotation (policy passed=False)."""
        consent = self.get_object()
        retires = consent.revoke()
        data = self.get_serializer(consent).data
        data['assets_retires'] = retires
        return Response(data)


class CompetitorPageViewSet(AdsengineViewSet):
    """PUB70 — CRUD des Pages concurrentes suivies (veille manuelle outillée).

    Company-scopé ; ``company`` posée côté serveur. Un ``GET veille/`` agrégé
    (finding API + cadence + matière de brief) est exposé en action ``veille``.
    ZÉRO scraping — aucun appel réseau côté serveur."""

    queryset = CompetitorPage.objects.all()
    serializer_class = CompetitorPageSerializer

    @action(detail=False, methods=['get'],
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def veille(self, request):
        """PUB70 — Tableau de veille : le finding API (couverture commerciale =
        NON), la cadence par concurrent, et la matière de brief (hooks/angles
        saisis). Lecture seule, company-scopé."""
        from . import competitor_intel as ci

        company = request.user.company
        return Response({
            'finding': ci.AD_LIBRARY_API_FINDING,
            'cadence': ci.cadence_timeline(company),
            'brief_material': ci.observations_as_brief_material(company),
        })


class CompetitorAdObservationViewSet(AdsengineViewSet):
    """PUB70 — CRUD des observations manuelles (hooks/angles reformulés). Company-
    scopé ; ``competitor_page`` contrainte à la même société côté serializer."""

    queryset = CompetitorAdObservation.objects.all()
    serializer_class = CompetitorAdObservationSerializer


class AdChatterView(APIView):
    """PUB55 — Fil de chatter par entité (campagne / ad set / ad).

    ``GET ?entity_type=&entity_id=`` renvoie le fil FUSIONNÉ (notes manuelles +
    actions appliquées + alertes, le plus récent d'abord). ``POST {entity_type,
    entity_id, body}`` pose une note manuelle — acteur + société côté serveur
    (jamais lus du corps), pattern ``crm.LeadActivity``. Company-scopé."""

    _ENTITIES = {'campaign', 'adset', 'ad'}

    def _resolve(self, request, perm):
        return _adseng_company_gate(request, perm)

    def get(self, request):
        company, err = self._resolve(request, 'adsengine_view')
        if err is not None:
            return err
        entity_type = request.query_params.get('entity_type')
        entity_id = request.query_params.get('entity_id')
        if entity_type not in self._ENTITIES or not entity_id:
            return Response(
                {'detail': 'entity_type (campaign/adset/ad) et entity_id requis.'},
                status=400)
        from . import chatter
        return Response(chatter.build_timeline(company, entity_type, entity_id))

    def post(self, request):
        company, err = self._resolve(request, 'adsengine_manage')
        if err is not None:
            return err
        body = request.data or {}
        entity_type = body.get('entity_type')
        entity_id = body.get('entity_id')
        text = (body.get('body') or '').strip()
        if entity_type not in self._ENTITIES or not entity_id:
            return Response(
                {'detail': 'entity_type (campaign/adset/ad) et entity_id requis.'},
                status=400)
        if not text:
            return Response({'detail': 'Une note (body) est requise.'}, status=400)
        note = AdEngineActivity.objects.create(
            company=company, entity_type=entity_type,
            entity_meta_id=str(entity_id), body=text, user=request.user)
        return Response({
            'id': note.id, 'kind': 'note', 'body': note.body,
            'at': note.created_at.isoformat(),
            'author': request.user.username, 'source': 'note',
        }, status=201)


class ImportChantierPhotoView(APIView):
    """PUB73 — Importe une photo de chantier dans la créathèque
    (``CreativeAsset(source_lane='chantier')``).

    Corps : ``{chantier_id, attachment_id, client_id, puissance_kwc?, ville?,
    note?, auto_flagged?}``. Écriture ``adsengine_manage`` ; company-scopé.
    BLOQUÉ (400) sans consentement photo client actif (PUB75) — refus expliqué."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        body = request.data or {}
        chantier_id = body.get('chantier_id')
        attachment_id = body.get('attachment_id')
        client_id = body.get('client_id')
        if not (chantier_id and attachment_id):
            return Response(
                {'detail': 'chantier_id et attachment_id requis.'}, status=400)
        from . import creative_factory as cf
        result = cf.import_chantier_photo(
            company, chantier_id=chantier_id, attachment_id=attachment_id,
            client_id=client_id, puissance_kwc=body.get('puissance_kwc'),
            ville=body.get('ville'), note=body.get('note', ''),
            auto_flagged=bool(body.get('auto_flagged')))
        if not result['imported']:
            return Response(
                {'detail': result['message'],
                 'blocked_reason': result['blocked_reason']}, status=400)
        return Response({
            'imported': True, 'asset_id': result['asset'].id,
            'message': result['message'],
        }, status=201)


class ProposalTemplateViewSet(AdsengineViewSet):
    """PUB50 — CRUD des gabarits de proposition réutilisables. Company-scopé ;
    ``company`` posée côté serveur. Appliquer un gabarit (côté front) ne fait que
    PRÉ-REMPLIR un composeur — aucune action n'est exécutée depuis ce viewset."""

    queryset = ProposalTemplate.objects.all()
    serializer_class = ProposalTemplateSerializer

    def get_queryset(self):
        # Filtre optionnel par ``kind`` (le composeur ne charge que ses gabarits).
        qs = super().get_queryset()
        kind = self.request.query_params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        return qs


class BrandKitViewSet(AdsengineViewSet):
    """PUB83 — CRUD du kit de marque (une par société, ``OneToOne``).

    Company-scopé (hérité) ; ``company`` posée côté serveur. Le
    ``TemplatedAdapter`` lit ce kit persistant au lieu d'un payload de marque
    ad hoc à chaque génération."""

    queryset = BrandKit.objects.all()
    serializer_class = BrandKitSerializer


class EngineAlertViewSet(AdsengineViewSet):
    """ENG13 — Liste (lecture seule) des alertes moteur pour le dashboard.

    Company-scopé (hérité) + gaté ``adsengine_view``. Restreint à GET : les
    alertes sont créées par le moteur (ENG9), jamais par un client API. Comme la
    ressource est en lecture seule (``http_method_names`` GET-only), on ne pose
    AUCUNE permission d'écriture (``write_permission = None``) : une écriture est
    structurellement impossible et DRF renvoie 405 (méthode non autorisée) au
    dispatch, plutôt que 403 en amont dans ``check_permissions`` (qui exigerait
    ``adsengine_manage`` sur une méthode qui ne s'exécute jamais).
    """

    queryset = EngineAlert.objects.all()
    serializer_class = EngineAlertSerializer
    http_method_names = ['get', 'head', 'options']
    write_permission = None

    def get_queryset(self):
        # PUB48 — la liste ACTIVE (``list()``, consommée par le bandeau
        # Dashboard + la cloche console) masque une alerte REPORTÉE
        # (``alerts.snooze_alert``) jusqu'à son échéance : « une alerte
        # snoozée ne re-notifie pas avant l'échéance ». ``history()``/
        # ``retrieve()`` restent sur la queryset COMPLÈTE (rien n'est
        # jamais supprimé, l'historique reste consultable).
        qs = super().get_queryset()
        if self.action == 'list':
            from . import alerts as alerts_module
            from django.utils import timezone
            today = timezone.now().date().isoformat()
            snoozed_ids = [
                a.id for a in qs if alerts_module.is_snoozed(a, today=today)]
            if snoozed_ids:
                qs = qs.exclude(id__in=snoozed_ids)
        return qs

    @action(detail=False, methods=['get'], url_path='history',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def history(self, request):
        """ENG43 — Historique des alertes (passées/résolues, ET reportées
        (snooze) — PUB48, jamais masquées ici) pour l'écran Règles & anomalies
        + la cloche console. Company-scopé (``get_queryset`` hérité) ; le
        filtre snooze de ``get_queryset`` ne s'applique QU'à l'action
        ``list`` (``self.action == 'history'`` ici) — l'historique reste
        donc TOUJOURS complet. Lecture ``adsengine_view`` ; même sérialiseur
        (aucun secret exposé)."""
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)


class AlertSnoozeView(APIView):
    """PUB48 — Reporte UNE alerte jusqu'à une date (``{"until": "YYYY-MM-DD"}``) :
    n'affecte QUE la liste ACTIVE (``alertes/``, ``EngineAlertViewSet.list``) —
    ``history()`` et l'entité liée restent inchangés (rien n'est jamais
    supprimé ni ré-émis). Écriture ``adsengine_manage`` ; company-scopé
    (l'alerte d'une autre société → 404)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, alert_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        alert = EngineAlert.objects.filter(company=company, pk=alert_id).first()
        if alert is None:
            return Response({'detail': 'Alerte introuvable.'}, status=404)
        until = (request.data or {}).get('until')
        if not until:
            return Response(
                {'detail': "'until' requis (YYYY-MM-DD)."}, status=400)
        from . import alerts as alerts_module
        alerts_module.snooze_alert(alert, until)
        return Response(EngineAlertSerializer(alert).data)


class CreativeAssetViewSet(AdsengineViewSet):
    """ENG15 — CRUD des assets créatifs + upload MinIO.

    Company-scopé (hérité) ; lecture ``adsengine_view`` / écriture
    ``adsengine_manage``. ``file_key`` / ``policy_stamp`` / ``perf`` sont posés
    côté serveur (upload / check-list ENG16 / insights), jamais par le client.
    """

    queryset = CreativeAsset.objects.all()
    serializer_class = CreativeAssetSerializer

    @action(detail=False, methods=['post'],
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def upload(self, request):
        """Téléverse un fichier statique (image) dans MinIO et crée l'asset en
        attente de check-list policy (``policy_stamp`` vide → non validé).

        Réutilise le pipeline de stockage de fondation (``records.storage`` —
        clé préfixée société, SCA42). Les reels/explainers vidéo passent par la
        fabrique créative (ENG17), pas par cet upload d'image."""
        from apps.records.storage import store_attachment

        f = request.FILES.get('file')
        if f is None:
            return Response({'detail': 'Fichier requis.'}, status=400)
        company = getattr(request.user, 'company', None)
        stored, err = store_attachment(f, company=company)
        if err:
            return Response({'detail': err}, status=400)
        asset = CreativeAsset.objects.create(
            company=company,
            asset_type=request.data.get(
                'asset_type', CreativeAsset.AssetType.STATIC),
            file_key=stored['file_key'],
            source_lane='upload',
            cost_cents=int(request.data.get('cost_cents') or 0),
        )
        return Response(self.get_serializer(asset).data, status=201)

    @action(detail=False, methods=['get'],
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def checklist(self, request):
        """ENG16 — Renvoie la check-list policy à confirmer par l'humain."""
        from .policy import build_checklist
        company = getattr(request.user, 'company', None)
        return Response(build_checklist(company))

    @action(detail=True, methods=['post'], url_path='policy-check',
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def policy_check(self, request, pk=None):
        """ENG16 — Enregistre la confirmation HUMAINE règle par règle (le système
        ne juge jamais seul). ``passed`` ne devient vrai que si toutes les règles
        interdites sont confirmées. Écriture → ``adsengine_manage``."""
        from .policy import record_policy_check
        asset = self.get_object()
        confirmed = request.data.get('confirmed_keys') or []
        record_policy_check(
            asset, confirmed_keys=confirmed, checked_by=request.user)
        return Response(self.get_serializer(asset).data)

    @action(detail=True, methods=['post'], url_path='variantes',
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def variantes(self, request, pk=None):
        """ENG18 — Génère 2-3 variantes statiques d'un asset de base (à la
        demande). Délègue à la tâche ``generate_creative_variants`` (gated
        fal/Templated — NO-OP propre sans clé) ; les variantes naissent en
        policy PENDING, liées au parent. Écriture → ``adsengine_manage``."""
        from .tasks import generate_creative_variants
        asset = self.get_object()  # borné société
        result = generate_creative_variants(asset.id)
        return Response(result, status=202)


class CreativePolicyViewSet(AdsengineViewSet):
    """ENG16 — CRUD de la policy créative (une par société)."""

    queryset = CreativePolicy.objects.all()
    serializer_class = CreativePolicySerializer


class ExperimentViewSet(AdsengineViewSet):
    """ADSENG3 — CRUD des expériences (tests A/B/n). Company-scopé (hérité) ;
    lecture ``adsengine_view`` / écriture ``adsengine_manage``."""

    queryset = Experiment.objects.all()
    serializer_class = ExperimentSerializer

    @action(detail=True, methods=['get'], url_path='decisions',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def decisions(self, request, pk=None):
        """ENG12/ENG39 — Journal de décision (« pourquoi le moteur a fait X »)
        d'UNE expérience. Filtre ``DecisionLog`` sur l'expérience (elle-même
        déjà bornée société via ``get_object``). Lecture → ``adsengine_view``."""
        experiment = self.get_object()  # borné société
        logs = (DecisionLog.objects
                .filter(company=experiment.company, experiment=experiment)
                .order_by('-created_at', '-id'))
        return Response(DecisionLogSerializer(logs, many=True).data)

    @action(detail=True, methods=['post'], url_path='conclure',
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def conclure(self, request, pk=None):
        """PUB18 (hook production) — Clôture HUMAINE d'une expérience avec
        verdict : ``{"validated": true|false}``. Déplace le posterior du nœud
        d'hypothèse lié via ``evidence.record_experiment_outcome`` (idempotent
        par expérience — re-clôturer ne double jamais l'évidence). L'opérateur
        décide, la machine enregistre — jamais l'inverse."""
        from .evidence import record_experiment_outcome

        experiment = self.get_object()  # borné société
        validated = request.data.get('validated')
        if not isinstance(validated, bool):
            return Response(
                {'detail': "Champ « validated » (booléen) requis : la clôture "
                           "porte un verdict explicite, jamais implicite."},
                status=400)
        node, log = record_experiment_outcome(experiment, validated=validated)
        if node is None:
            return Response(
                {'detail': "Aucun nœud d'hypothèse rattaché à cette "
                           "expérience — verdict enregistré nulle part.",
                 'node': None}, status=200)
        return Response({'node': node.pk, 'decision_log': log.pk if log else None,
                         'validated': validated}, status=200)

    @action(detail=True, methods=['post'], url_path='sync-ad-study',
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def sync_ad_study(self, request, pk=None):
        """ADSDEEP34 — Lit (LECTURE SEULE côté Meta) les résultats de l'étude
        A/B native liée à cette expérience (``experiment.meta_study_id``) et
        journalise un ``DecisionLog``. Écriture → ``adsengine_manage`` (hérité :
        cette action DÉCLENCHE un appel externe même si Meta n'y écrit rien).
        404 structuré si l'expérience ne porte encore aucun ``meta_study_id``."""
        from .meta_client import MetaClient
        from .models import MetaConnection
        from .serializers import DecisionLogSerializer as _DLS
        from .services import sync_ad_study_results

        experiment = self.get_object()  # borné société
        if not experiment.meta_study_id:
            return Response(
                {'detail': "Aucune étude native (meta_study_id) liée à cette "
                           "expérience."}, status=404)
        connection = MetaConnection.objects.filter(
            company=experiment.company, enabled=True).first()
        if connection is None:
            return Response(
                {'detail': 'Aucune connexion Meta active.'}, status=400)
        client = MetaClient.from_connection(connection)
        try:
            log = sync_ad_study_results(experiment, client=client)
        except Exception as exc:  # panne réseau/API Meta → jamais une 500 nue
            return Response({'detail': str(exc)}, status=502)
        if log is None:
            return Response(
                {'detail': "Aucune étude native liée."}, status=404)
        return Response(_DLS(log).data)


class ExperimentArmViewSet(AdsengineViewSet):
    """ADSENG3 — CRUD des bras d'expérience (créatifs candidats)."""

    queryset = ExperimentArm.objects.all()
    serializer_class = ExperimentArmSerializer


class ArmDailyStatViewSet(AdsengineViewSet):
    """ADSENG3 — CRUD des stats quotidiennes de bras (données du bandit).

    Alimentées surtout par la sync (ENG6 étendue) via
    ``ArmDailyStat.upsert`` — l'API reste disponible pour lecture/saisie
    manuelle, company-scopée."""

    queryset = ArmDailyStat.objects.all()
    serializer_class = ArmDailyStatSerializer


class DecisionLogViewSet(AdsengineViewSet):
    """ADSENG3 — Liste (lecture seule) des journaux de décision de la science.

    Company-scopé (hérité) + gaté ``adsengine_view``. Restreint à GET : les
    décisions sont écrites par le moteur (P1), jamais par un client API."""

    queryset = DecisionLog.objects.all()
    serializer_class = DecisionLogSerializer
    http_method_names = ['get', 'head', 'options']


class RulePolicyViewSet(AdsengineViewSet):
    """ADSENG4 — CRUD des règles de garde-fou (le fondateur configure).

    Company-scopé (hérité) ; ``created_by`` posé côté serveur. Défaut sûr : une
    règle naît ``enabled=False`` + ``dry_run=True`` (aucun effet tant que le
    fondateur n'a pas explicitement activé + quitté la simulation)."""

    queryset = RulePolicy.objects.all()
    serializer_class = RulePolicySerializer

    def perform_create(self, serializer):
        # ``company`` forcée par la base (TenantMixin) ; ``created_by`` posé ici.
        super().perform_create(serializer)
        if serializer.instance.created_by_id is None:
            serializer.instance.created_by = self.request.user
            serializer.instance.save(update_fields=['created_by'])

    def perform_update(self, serializer):
        # PUB23 — « armer/désarmer » une règle depuis la console EST une mise à
        # jour de ``enabled`` via ce même CRUD (aucune route dédiée) : on trace
        # le basculement dans le journal UNIFIÉ de l'ERP (``audit.recorder``,
        # ARC16 — même funnel que le reste de l'app, jamais un second système).
        old_enabled = serializer.instance.enabled
        super().perform_update(serializer)
        instance = serializer.instance
        if instance.enabled != old_enabled:
            from apps.audit.recorder import record_field_change
            record_field_change(
                instance, 'enabled', old_enabled, instance.enabled,
                field_label='Règle armée' if instance.enabled else 'Règle désarmée',
                detail=(
                    f'Règle « {instance.template_key} » armée '
                    f'(cadence {instance.cadence_hours} h).' if instance.enabled
                    else f'Règle « {instance.template_key} » désarmée.'))

    # PUB91 — backtest de la règle sur l'historique RÉEL (dry-run avant armement).
    # Lecture seule (adsengine_view) : AUCUNE EngineAction n'est créée. ``?jours=``
    # borne la fenêtre (défaut 90 = dernier trimestre).
    @action(detail=True, methods=['get'],
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def backtest(self, request, pk=None):
        """PUB91 — « Qu'aurait fait cette règle sur votre dernier trimestre ? »
        Rejoue la règle jour par jour sur les snapshots réels et liste les
        actions qu'elle AURAIT proposées (jamais exécutées)."""
        from .rule_backtest import DEFAULT_BACKTEST_DAYS, backtest_rule
        policy = self.get_object()
        try:
            days = int(request.query_params.get('jours', DEFAULT_BACKTEST_DAYS))
        except (TypeError, ValueError):
            days = DEFAULT_BACKTEST_DAYS
        return Response(backtest_rule(policy, days=days))

    # ADSENG14 — catalogue FIXE (lecture) : le front rend la liste des templates
    # (style STAGES.py) sans que le fondateur puisse en inventer un (pas de
    # builder libre). GET → permission de LECTURE (adsengine_view) héritée.
    @action(detail=False, methods=['get'],
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def catalogue(self, request):
        """Liste des templates du catalogue fixe (clé, libellé, sévérité,
        cadence, action par défaut, params éditables + défauts). Aucune donnée
        société — c'est de la métadonnée statique."""
        from . import rule_templates as rt
        # ADSENGINT — libellés FR d'action (pour le picker RulesScreen).
        action_fr_map = {
            'pause': 'Mise en pause proposée (approbation requise).',
            'rotate_creative': 'Rotation créative proposée.',
            'rebalance_budget': 'Rééquilibrage de budget proposé.',
        }
        items = []
        for key, tpl in rt.RULE_TEMPLATES.items():
            ak = rt.action_kind(key)
            items.append({
                'template_key': key,
                # ADSENGINT — clés attendues par ``normalizeRuleTemplate`` du
                # front (picker « SI condition → ALORS action »), en plus des
                # clés historiques (rétro-compat + test catalogue inchangé).
                'key': key,
                'nom': tpl['label_fr'],
                'condition_fr': tpl['label_fr'],
                'action_fr': action_fr_map.get(
                    ak, "Alerte seule (le moteur n'active jamais)."),
                'label_fr': tpl['label_fr'],
                'severity': tpl['severity'],
                'cadence': tpl['cadence'],
                'scope': tpl['scope'],
                'actionable': rt.is_actionable(key),
                'action_kind': ak,
                'editable_params': tpl['editable_params'],
                'default_params': tpl['default_params'],
            })
        # ``templates`` (historique/test) + ``results`` (extraction front DRF).
        return Response({'templates': items, 'results': items})

    # ADSENG14 — seed du catalogue fixe pour la société (idempotent). Chaque
    # règle naît OFF + dry-run (défaut sûr). POST → permission d'ÉCRITURE
    # (adsengine_manage) héritée du mapping méthode→permission.
    @action(detail=False, methods=['post'],
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def seed(self, request):
        """Seed idempotent des ``RulePolicy`` du catalogue pour la société de
        l'appelant — jamais un doublon (get_or_create sur (company, template)).
        Renvoie le nombre créé + le total présent."""
        from . import rule_templates as rt
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        created = rt.seed_default_policies(company, created_by=request.user)
        total = RulePolicy.objects.filter(company=company).count()
        return Response(
            {'created': len(created), 'total': total}, status=200)

    # ADSENG43 — Dry-run d'un gabarit : PROJECTION lecture-seule des objets que
    # la règle SURVEILLE + l'effet qu'elle proposerait si elle se déclenchait,
    # SANS jamais évaluer/appliquer (les évaluateurs réels écrivent des
    # ``AnomalyEvent`` — un dry-run ne doit rien muter). Le ``template`` vient du
    # corps. Lecture → ``adsengine_view``.
    @action(detail=False, methods=['post'], url_path='dry-run',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def dry_run(self, request):
        from . import rule_templates as rt
        from .models import AdCampaignMirror, AdSetMirror
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        template_key = request.data.get('template') or ''
        tpl = rt.get_template(template_key)
        if tpl is None:  # get_template renvoie None (ne lève pas) pour une clé inconnue
            return Response(
                {'detail': f"Gabarit inconnu : {template_key!r}."}, status=400)

        scope = tpl.get('scope', 'account')
        kind = rt.action_kind(template_key)
        effet_map = {
            'pause': 'Mise en pause proposée (jamais appliquée sans '
                     'approbation humaine).',
            'rotate_creative': 'Rotation créative proposée.',
            'rebalance_budget': 'Rééquilibrage de budget proposé (dans la '
                                'bande).',
        }
        effet_fr = effet_map.get(
            kind, 'Alerte émise (aucune action automatique).')

        objets = []
        if scope == 'campaign':
            objets = list(AdCampaignMirror.objects.filter(company=company))
        elif scope == 'adset':
            objets = list(AdSetMirror.objects.filter(company=company))
        objets_touches = [
            {'id': o.pk, 'nom': o.name or o.meta_id, 'effet_fr': effet_fr}
            for o in objets
        ]
        if scope == 'account':
            objets_touches = [
                {'id': company.pk, 'nom': 'Compte publicitaire',
                 'effet_fr': effet_fr}]

        resume_fr = (
            f"{tpl['label_fr']} — surveille {len(objets_touches)} objet(s) "
            f"({scope}). Simulation : rien n'est appliqué.")
        return Response(
            {'resume_fr': resume_fr, 'objets_touches': objets_touches})

    # ADSDEEP43 — Journal d'exécution ENRICHI des règles de la société : pour
    # chaque règle, la dernière passe avec — par entité surveillée — le verdict de
    # condition (valeurs comparées, ``condition_fr``) et le delta de l'action
    # proposée (``action``) — le « pourquoi » de chaque déclenchement, rendu sur
    # l'écran Règles. Lecture ``adsengine_view``.
    @action(detail=False, methods=['get'],
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def journal(self, request):
        from . import rule_templates as rt
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        items = []
        policies = (RulePolicy.objects
                    .filter(company=company)
                    .order_by('-last_evaluated_at', 'template_key'))
        for p in policies:
            tpl = rt.get_template(p.template_key)
            lr = p.last_result or {}
            items.append({
                'id': p.pk,
                'template_key': p.template_key,
                'label_fr': tpl['label_fr'] if tpl else p.template_key,
                'enabled': p.enabled,
                'dry_run': p.dry_run,
                'last_evaluated_at': p.last_evaluated_at,
                'evaluated': lr.get('evaluated', False),
                'fired': lr.get('fired', False),
                'findings': lr.get('findings', []),
            })
        return Response({'results': items})


class AnomalyEventViewSet(AdsengineViewSet):
    """ADSENG4 — Liste (lecture seule) des anomalies + PUB90 : feedback
    utile/faux-positif et précision par détecteur."""

    queryset = AnomalyEvent.objects.all()
    serializer_class = AnomalyEventSerializer
    # POST est activé UNIQUEMENT pour l'action ``feedback`` (PUB90) ; la création
    # d'anomalie par API reste interdite (les anomalies naissent du gardien).
    http_method_names = ['get', 'post', 'head', 'options']

    def create(self, request, *args, **kwargs):
        """La création d'anomalie par API est interdite (405) : une anomalie est
        matérialisée par le moteur (ENG9), jamais par un client."""
        return Response(status=405)

    @action(detail=True, methods=['post'],
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def feedback(self, request, pk=None):
        """PUB90 — Vote utile/faux-positif sur une anomalie (acteur + horodatage
        posés côté serveur). ``{"vote": "useful"|"false_positive"}``. Alimente la
        précision par détecteur + le throttle brake-only. Idempotent (re-voter
        remplace le vote)."""
        from django.utils import timezone
        anomaly_event = self.get_object()
        vote = request.data.get('vote')
        valid = {c[0] for c in AnomalyEvent.Feedback.choices}
        if vote not in valid:
            return Response(
                {'detail': 'Vote attendu : useful ou false_positive.'},
                status=400)
        anomaly_event.feedback = vote
        anomaly_event.feedback_at = timezone.now()
        anomaly_event.feedback_by = request.user
        anomaly_event.save(
            update_fields=['feedback', 'feedback_at', 'feedback_by',
                           'updated_at'])
        return Response(self.get_serializer(anomaly_event).data)

    @action(detail=False, methods=['get'], url_path='detecteurs',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def detectors(self, request):
        """PUB90 — Précision + état de throttle PAR DÉTECTEUR (visible dans
        l'UI). Company-scopé (queryset hérité). Un détecteur constamment inutile
        (≥ 5 faux positifs) apparaît ``throttled`` (cadence réduite)."""
        from . import anomaly as anomaly_mod
        company = request.user.company
        return Response({'detecteurs': anomaly_mod.all_detector_stats(company)})


class CreativeGenerationBatchViewSet(AdsengineViewSet):
    """ADSENG5 — CRUD des lots de génération créative + approbation par LOT.

    L'approbation est BATCH-level (jamais par variante) : une seule action
    approuve/rejette le lot entier. ``adsengine_manage`` gate l'écriture."""

    queryset = CreativeGenerationBatch.objects.all()
    serializer_class = CreativeGenerationBatchSerializer

    @action(detail=True, methods=['post'],
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def approve(self, request, pk=None):
        """Approuve le LOT ENTIER (acteur + horodatage posés côté serveur)."""
        from django.utils import timezone
        batch = self.get_object()
        batch.status = CreativeGenerationBatch.Statut.APPROUVEE
        batch.approved_by = request.user
        batch.approved_at = timezone.now()
        batch.save(update_fields=['status', 'approved_by', 'approved_at'])
        return Response(self.get_serializer(batch).data)

    @action(detail=True, methods=['post'],
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def reject(self, request, pk=None):
        """Rejette le LOT ENTIER."""
        from django.utils import timezone
        batch = self.get_object()
        batch.status = CreativeGenerationBatch.Statut.REJETEE
        batch.approved_by = request.user
        batch.approved_at = timezone.now()
        batch.save(update_fields=['status', 'approved_by', 'approved_at'])
        return Response(self.get_serializer(batch).data)


class CreativeBacklogItemViewSet(AdsengineViewSet):
    """ADSENG5 — CRUD des items de backlog créatif (file de publication)."""

    queryset = CreativeBacklogItem.objects.all()
    serializer_class = CreativeBacklogItemSerializer


class FlightPlanViewSet(AdsengineViewSet):
    """ADSENG5 — CRUD des plans de vol (feuille de route 3-6 mois comme data)."""

    queryset = FlightPlan.objects.all()
    serializer_class = FlightPlanSerializer

    @action(detail=False, methods=['get'], url_path='templates',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def templates(self, request):
        """ENG38/ENG40 — Gabarits de lancement (``launch_templates``) enrichis de
        la séquence de phases canonique (``flightplan.default_phase_specs``).
        Métadonnée statique, aucune donnée société. Lecture ``adsengine_view``."""
        from . import flightplan as fp
        from . import launch_templates as lt
        phases = [
            {'key': (s.get('tested_variable') or s.get('name') or ''),
             'label': s.get('name') or s.get('tested_variable') or '',
             'duree_mois': round((s.get('week_span') or 0) / 4.0, 2)}
            for s in fp.default_phase_specs()
        ]
        items = [
            {'key': t['key'], 'nom': t['label'], 'phases': phases}
            for t in lt.list_templates()
        ]
        return Response(items)

    @action(detail=False, methods=['get'], url_path='backlog-arms',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def backlog_arms(self, request):
        """ENG40/ENG41 — Bras disponibles depuis le backlog (items EN FILE prêts
        à programmer). Company-scopé ; lecture ``adsengine_view``."""
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        items = (CreativeBacklogItem.objects
                 .filter(company=company,
                         status=CreativeBacklogItem.Statut.EN_FILE)
                 .select_related('asset')
                 .order_by('earliest_date', 'id'))
        arms = []
        for it in items:
            asset = it.asset
            nom = ''
            if asset is not None:
                nom = (asset.hook_text or asset.hook_id
                       or f'Créatif {asset.id}')
            arms.append({'id': it.pk, 'nom': nom or f'Bras {it.pk}'})
        return Response(arms)

    @action(detail=False, methods=['get'], url_path='preflight',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def preflight(self, request):
        """ENG38 — Préflight d'autonomie : agrège TOUTES les portes go-live
        (connexion, garde-fous, alertes, backlog, diversité, plan, simulation,
        tests terrain). Lecture seule ; company-scopé ; ``adsengine_view``."""
        from . import preflight as pf
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        st = pf.status(company)
        portes = [
            {'key': g['key'], 'label': g['label_fr'], 'ok': g['ok'],
             'detail': g['detail_fr']}
            for g in st['gates']
        ]
        return Response({'pret': st['ready'], 'portes': portes})

    @action(detail=False, methods=['post'], url_path='validate',
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def validate(self, request):
        """ENG40 — Valide un plan composé → ``{ok, raisons}`` (refus structuré
        avec raisons FR). Réutilise ``flightplan.preflight`` (backlog/diversité/
        garde-fous/alertes + sanité des phases). N'écrit RIEN. ``adsengine_manage``."""
        from . import flightplan as fp
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        payload = request.data if isinstance(request.data, dict) else {}
        phases_in = payload.get('phases') or []
        bras = payload.get('bras') or []
        num_arms = min(max(len(bras) or fp.PHASE_ARMS_MIN, fp.PHASE_ARMS_MIN),
                       fp.PHASE_ARMS_MAX)
        specs = []
        for p in phases_in:
            key = (p or {}).get('key') or ''
            specs.append({
                'name': key or 'Phase',
                'tested_variable': key or 'hook',
                'num_arms': num_arms,
                # Bornes valides par construction (3-4 sem.) : la validation
                # MÉTIER porte sur le backlog/diversité/garde-fous, pas sur une
                # durée saisie hors bornes.
                'week_span': fp.PHASE_WEEKS_MIN,
                'launch_template': payload.get('template', ''),
                'budget_mad': 0,
            })
        if not specs:
            specs = fp.default_phase_specs()
        result = fp.preflight(company, specs)
        return Response({'ok': result.ok, 'raisons': result.reasons_fr})

    @action(detail=False, methods=['post'], url_path='simulate',
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def simulate(self, request):
        """ENG44 — Rapport de simulation d'un plan composé. Renvoie le SHELL du
        scénario demandé (verdict attendu + structure de rejeu). Le rejeu LIVE
        du moteur (``simulator.simulate``) écrit des miroirs synthétiques dans la
        société et POLLUERAIT les métriques réelles — il n'est donc pas déclenché
        depuis la console (voir ``_simulation_report_shell``). ``adsengine_manage``."""
        payload = request.data if isinstance(request.data, dict) else {}
        scenario = payload.get('scenario') or 'clear_winner'
        return Response(_simulation_report_shell(scenario))


class FlightPhaseViewSet(AdsengineViewSet):
    """ADSENG5 — CRUD des phases de vol (2-4 bras, 1-8 semaines)."""

    queryset = FlightPhase.objects.all()
    serializer_class = FlightPhaseSerializer


class ReconciliationSnapshotViewSet(AdsengineViewSet):
    """ADSENG5 — Liste (lecture seule) des instantanés de réconciliation."""

    queryset = ReconciliationSnapshot.objects.all()
    serializer_class = ReconciliationSnapshotSerializer
    http_method_names = ['get', 'head', 'options']


class HasAdsengineApprove(BasePermission):
    """ENG7 — Permission d'APPROBATION (distincte de la proposition).

    Approuver / appliquer une ``EngineAction`` exige ``adsengine_approve`` —
    une permission SÉPARÉE de ``adsengine_manage`` (proposer). Réutilise le
    repli légacy commun (``_user_has_or_legacy``) pour rester cohérent avec le
    reste du gating de l'app.
    """

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        return _user_has_or_legacy(user, 'adsengine_approve')


class EngineActionViewSet(AdsengineViewSet):
    """ENG7 — Boucle propose→approuve→applique.

    Proposer (POST) exige ``adsengine_manage`` ; approuver / rejeter / appliquer
    exigent ``adsengine_approve`` (permission DISTINCTE). Une action ne s'applique
    qu'une fois APPROUVÉE — ``services.apply_action`` refuse tout le reste (le
    client Meta n'est jamais atteint). Aucun PATCH direct de ``status`` (champ en
    lecture seule au serializer).

    PUB40 — ``GET .../actions/?debut=&fin=`` (dates ISO, optionnelles) borne
    la liste (Journal d'actions) à ``created_at`` dans ``[debut, fin]`` ;
    omises, comportement inchangé (tout l'historique).
    """

    queryset = EngineAction.objects.all()
    serializer_class = EngineActionSerializer

    _APPROVE_ACTIONS = ('approve', 'reject', 'apply')

    def get_permissions(self):
        if getattr(self, 'action', None) in self._APPROVE_ACTIONS:
            return [HasAdsengineApprove()]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        debut = _adseng_parse_date(self.request.query_params.get('debut'))
        fin = _adseng_parse_date(self.request.query_params.get('fin'))
        if debut is not None:
            qs = qs.filter(created_at__date__gte=debut)
        if fin is not None:
            qs = qs.filter(created_at__date__lte=fin)
        return qs

    def perform_create(self, serializer):
        """ENGFIX2 — Garde policy créative sur le chemin de création API.

        ``assert_creative_ok_for_ad`` n'était appelé que par
        ``services.propose_action`` / ``execute_auto_action`` : un POST direct
        (``create_ad`` référençant un ``CreativeAsset`` non estampillé policy)
        passait outre. On réenclenche ICI le même contrôle AVANT ``save`` — la
        société est forcée côté serveur (jamais lue du corps). Une violation
        (``CreativePolicyNotPassed``, sous-classe de ``ValueError``) est traduite
        en ``ValidationError`` (400), jamais une 500."""
        from rest_framework import serializers as drf_serializers

        from .services import (
            ActionPayloadInvalid, CreativePolicyNotPassed,
            assert_creative_ok_for_ad, validate_manual_payload)
        company = self.request.user.company
        kind = serializer.validated_data.get('kind')
        payload = serializer.validated_data.get('payload') or {}
        try:
            assert_creative_ok_for_ad(company, kind, payload)
        except CreativePolicyNotPassed as exc:
            raise drf_serializers.ValidationError(
                {'creative_asset_id': str(exc)})
        # PUB22 — validation de payload par kind pour les kinds atteignables par
        # POST brut sans producteur curé (create_ad / set_spend_cap / rename) :
        # un POST direct ne passe pas par ``propose_action``, on ré-enclenche donc
        # ICI le même contrôle avant ``save`` (jamais une action inapplicable).
        try:
            validate_manual_payload(kind, payload)
        except ActionPayloadInvalid:
            logger.warning('PUB22: payload manuel invalide (kind=%s)', kind,
                           exc_info=True)
            raise drf_serializers.ValidationError(
                {'payload': "Données de l'action invalides."})
        # PUB103 — proposeur posé côté serveur (support du garde-fou quatre yeux).
        # ``serializer.save(company=…)`` force la société exactement comme
        # ``TenantMixin.perform_create`` ; on ajoute seulement ``proposed_by``.
        serializer.save(company=company, proposed_by=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve l'action (acteur posé côté serveur).

        PUB103 — un proposeur qui approuve sa propre action alors que la double
        validation est active reçoit 403 (``FourEyesViolation``)."""
        from .services import FourEyesViolation, approve_action
        instance = self.get_object()
        try:
            approve_action(instance, user=request.user)
        except FourEyesViolation as exc:
            return Response({'detail': str(exc)}, status=403)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Rejette l'action (jamais applicable ensuite)."""
        from .services import reject_action
        instance = self.get_object()
        try:
            reject_action(
                instance, user=request.user,
                commentaire=request.data.get('commentaire', ''))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Applique l'action — UNIQUEMENT si elle est approuvée."""
        from .services import ActionNotApproved, apply_action
        instance = self.get_object()
        try:
            apply_action(instance)
        except ActionNotApproved as exc:
            return Response({'detail': str(exc)}, status=409)
        except Exception as exc:  # échec Meta → action déjà passée « echouee »
            return Response({'detail': str(exc)}, status=502)
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """PUB45 — Annule une action APPLIQUÉE en PROPOSANT son inverse (rétablir
        le budget mémorisé, restaurer le texte…) via le circuit propose→approuve
        normal — JAMAIS un write direct. Kind non inversible (création, pause
        non ré-activable) → 422 + explication FR. Proposer exige ``adsengine_manage``
        (hérité : ``annuler`` n'est pas une action d'approbation)."""
        from .services import (
            ActionNotInvertible, non_invertible_reason_fr,
            propose_inverse_action)
        instance = self.get_object()
        try:
            inverse = propose_inverse_action(
                instance, reason_fr=request.data.get('reason_fr'))
        except ActionNotInvertible:
            logger.warning('PUB45: annulation refusée — action %s non '
                           'inversible', instance.pk, exc_info=True)
            return Response(
                {'detail': non_invertible_reason_fr(instance),
                 'invertible': False}, status=422)
        except ValueError:
            logger.warning('PUB45: annulation impossible — action %s',
                           instance.pk, exc_info=True)
            return Response(
                {'detail': "Impossible d'annuler cette action."}, status=400)
        return Response(self.get_serializer(inverse).data, status=201)


class ProposeCuratedActionView(APIView):
    """PUB22 — Propose une action CURÉE (``duplicate`` / ``set_schedule`` /
    ``create_ad_study``) via son producteur backend (résolution + validation),
    toujours à travers ``propose_action``. Ces kinds ne peuvent PAS être proposés
    par POST brut (ils exigent une résolution DB, ex. le créatif LIVE d'une
    duplication) — d'où cet endpoint dédié.

    ``POST /api/django/adsengine/actions/proposer/<kind>/`` avec le corps propre
    au kind (ex. ``{adset_id, name_suffix?, reason_fr?}`` pour ``duplicate``).
    Company-scopé, gaté ``adsengine_manage``. Naissance PAUSED intacte (aucune
    activation). Une entrée invalide → 400, jamais une 500."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, kind):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        from .services import propose_manual_curated
        body = request.data or {}
        reason_fr = body.get('reason_fr')
        params = {k: v for k, v in body.items() if k != 'reason_fr'}
        try:
            action = propose_manual_curated(
                company, kind=kind, params=params, reason_fr=reason_fr)
        except ValueError:
            logger.warning('PUB22: proposition curée refusée (kind=%s)', kind,
                           exc_info=True)
            return Response(
                {'detail': "Proposition d'action invalide."}, status=400)
        return Response(EngineActionSerializer(action).data, status=201)


# ── ADSENG33 — Drill-downs de reporting (dd-attribution part d) ───────────────
# Endpoints LECTURE SEULE, company-scopés, gatés ``adsengine_view`` : table par
# variante, entonnoir par campagne, cohortes de signature, export CSV. Les
# calculs vivent dans ``reporting.py`` (le CRM y est lu via ``crm.selectors``).

def _adseng_reporting_company(request):
    """(company, error_response) : gate ``adsengine_view`` + société présente.
    ``error_response`` est None quand tout est bon."""
    if not _user_has_or_legacy(request.user, 'adsengine_view'):
        return None, Response({'detail': 'Permission refusée.'}, status=403)
    company = getattr(request.user, 'company', None)
    if company is None:
        return None, Response({'detail': 'Aucune société.'}, status=400)
    return company, None


def _median_lag_days(cohort):
    """Estime le lag médian (jours) d'une cohorte de signature depuis ses buckets
    CUMULATIFS (``lag_buckets``) : le plus petit ``lag_weeks`` dont le nombre de
    signés couvre la moitié du total. None si aucune signature (jamais 0 trompeur)."""
    total = cohort.get('signed_total') or 0
    if total <= 0:
        return None
    half = (total + 1) // 2
    for bucket in cohort.get('lag_buckets', []):
        if (bucket.get('signed') or 0) >= half:
            return bucket['lag_weeks'] * 7
    return None


def _adseng_parse_date(value):
    """``date`` ISO (YYYY-MM-DD) ou None (jamais une 500 sur une entrée libre)."""
    import datetime
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class VariantReportView(APIView):
    """ADSENG33 — Table par variante (spend/conv/CPL-qualifié/coût-signature +
    ids de leads). Company-scopé, gaté ``adsengine_view``."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import variant_table
        data = variant_table(company)
        # ADSENGINT — clés attendues par ``normalizeVariants`` du front (en plus
        # du contrat ENG33 historique). ``leads`` = conversions attribuées
        # (réponses CTWA) ; ``impressions`` non stocké → None (jamais fabriqué).
        data['variantes'] = [
            {'id': v['meta_id'], 'nom': v['name'], 'impressions': None,
             'reponses_whatsapp': v['leads'], 'cout_mad': v['spend'],
             'cout_par_reponse': v['cost_per_lead']}
            for v in data['variants']
        ]
        return Response(data)


class CampaignFunnelView(APIView):
    """ADSENG33 — Entonnoir par campagne (NEW→SIGNED cumulatif ; COLD/perdu à
    côté). ``?debut=&fin=`` (dates ISO) bornent la création."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import campaign_funnel
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        funnel = campaign_funnel(company, date_start=debut, date_end=fin)
        # ADSENGINT — ``etapes`` : entonnoir AGRÉGÉ (somme des « atteint » par
        # étape sur toutes les campagnes) pour ``normalizeFunnel`` du front, en
        # plus du détail par campagne (contrat ENG33). Les clés d'étape viennent
        # de campaign_funnel (donc de STAGES.py via le sélecteur) — jamais codées.
        agg, order = {}, []
        for camp in funnel:
            for step in camp['funnel']:
                s = step['stage']
                if s not in agg:
                    agg[s] = 0
                    order.append(s)
                agg[s] += step['reached']
        etapes = [{'key': s, 'label': s, 'valeur': agg[s]} for s in order]
        return Response({'etapes': etapes, 'campaigns': funnel})


class AttributionBilanView(APIView):
    """DATAPUB2 — Bilan d'attribution des leads Odoo : total lu, répartition par
    palier (téléphone/formulaire/nom/date) et NON-attribués listés par nom de
    source. Company-scopé, gaté ``adsengine_view``. ``?debut=`` (date ISO) borne
    la lecture. ``GET /api/django/adsengine/reporting/attribution-bilan/``."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import attribution_bilan
        debut = _adseng_parse_date(request.query_params.get('debut'))
        return Response(attribution_bilan(company, date_start=debut))


class LeadsTimeseriesView(APIView):
    """DATAPUB3 — Leads Odoo dans le temps (par jour/semaine) avec l'attribué et
    la dépense en overlay. ``?granularite=jour|semaine&ad=<meta_id>&debut=&fin=``.
    Company-scopé, gaté ``adsengine_view``.
    ``GET /api/django/adsengine/reporting/leads-timeseries/``."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import leads_timeseries
        gran = ('week'
                if request.query_params.get('granularite') == 'semaine'
                else 'day')
        ad = request.query_params.get('ad') or None
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        return Response(leads_timeseries(
            company, granularity=gran, ad_meta_id=ad,
            date_start=debut, date_end=fin))


class AudienceView(APIView):
    """DATAPUB4 — Audience (démographie) : reach(—)/impressions/clics/résultats/
    dépense agrégés par GENRE et par ÂGE (ventilations age_gender) + couverture
    par dimension (âge×genre/placement/région/horaire). ``?ad=<meta_id>`` draille
    sur une annonce. Company-scopé, gaté ``adsengine_view``.
    ``GET /api/django/adsengine/reporting/audience/``."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import audience_breakdown
        ad = request.query_params.get('ad') or None
        return Response(audience_breakdown(company, ad_meta_id=ad))


class VariantFunnelView(APIView):
    """PUB36 — Entonnoir de décrochage par étape, PAR VARIANTE (ad) — à quelle
    étape STAGES.py chaque annonce perd ses leads (COLD/perdu à côté)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import variant_funnel
        funnel = variant_funnel(company)
        return Response(funnel)


class CohortReportView(APIView):
    """ADSENG33 — Cohortes de signature (leads/semaine → lag). ``?debut=&fin=``
    bornent la création ; cohortes non écoulées marquées incomplètes."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import signature_cohorts
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        cohorts = signature_cohorts(company, date_start=debut, date_end=fin)
        # ADSENGINT — clés attendues par ``normalizeCohorts`` du front (ajoutées
        # aux items du contrat ENG33). Le lag médian est ESTIMÉ depuis les
        # buckets cumulatifs (plus petit lag couvrant la moitié des signatures).
        for c in cohorts:
            c['cohorte'] = c['cohort_week']
            c['taille'] = c['total_leads']
            c['signatures'] = c['signed_total']
            c['lag_jours_median'] = _median_lag_days(c)
        return Response(cohorts)


class ReportExportView(APIView):
    """ADSENG33 — Export CSV. ``?table=variantes`` (défaut) ou
    ``?table=reconciliation`` (``&date=`` ISO pour le jour réconcilié)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from django.http import HttpResponse

        from .reporting import reconciliation_csv, variant_table_csv
        table = request.query_params.get('table', 'variantes')
        if table == 'reconciliation':
            day = _adseng_parse_date(request.query_params.get('date'))
            csv_text = reconciliation_csv(company, day=day)
            filename = 'reconciliation.csv'
        else:
            csv_text = variant_table_csv(company)
            filename = 'variantes.csv'
        resp = HttpResponse(csv_text, content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp


# ══ ADSENGINT1/ADSENGINT2 — Endpoints console (câblage front↔back) ════════════
# Vues MINCES sur la logique DÉJÀ construite (aucun nouveau modèle, aucun recalcul
# métier ré-implémenté). Company-scopées + gatées ``adsengine_view`` (lecture) /
# ``adsengine_manage`` (écriture). Le secret Meta n'est JAMAIS relu (write-only)
# et l'invariant PAUSED reste intact (aucune de ces vues n'active rien côté Meta).


def _adseng_company_gate(request, permission):
    """(company, error_response) : gate permission fine + société présente.
    ``error_response`` est None quand tout est bon (variante paramétrable de
    ``_adseng_reporting_company``)."""
    if not _user_has_or_legacy(request.user, permission):
        return None, Response({'detail': 'Permission refusée.'}, status=403)
    company = getattr(request.user, 'company', None)
    if company is None:
        return None, Response({'detail': 'Aucune société.'}, status=400)
    return company, None


def _mask_account_id(value):
    """Masque un ID de compte publicitaire pour l'affichage (jamais un secret) :
    seulement les 4 derniers caractères survivent."""
    if not value:
        return ''
    v = str(value)
    return ('••' + v) if len(v) <= 4 else f'••••{v[-4:]}'


# ── ENG22 — Connexion Meta (statut + enregistrement write-only) ───────────────
_CONN_CRED_KEYS = ('app_id', 'app_secret', 'access_token')
_CONN_COLUMN_KEYS = ('ad_account_id', 'page_id', 'pixel_id')


class CreativeLeaderboardView(APIView):
    """ADSDEEP47 — Classement créatif spend-weighted par ``?dimension=`` (hook
    par défaut, angle/format sinon). ``?debut=&fin=`` (dates ISO) bornent la
    période (défaut : 30 jours glissants)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import creative_leaderboard
        dimension = request.query_params.get('dimension', 'hook')
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        data = creative_leaderboard(
            company, dimension=dimension, date_start=debut, date_end=fin)
        return Response(data)


class RegretRegistryView(APIView):
    """PUB86 — Registre de qualité des décisions (regret réalisé, MAD laissés sur
    la table) PAR TYPE DE DÉCISION. Company-scopé, gaté ``adsengine_view``.
    ``?debut=&fin=`` (dates ISO) bornent la fenêtre. Peu de données → intervalle
    honnête (``insufficient_data`` + ``interval``), jamais un chiffre sec."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .decision_quality import regret_registry
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        return Response(regret_registry(
            company, date_start=debut, date_end=fin))


def _adseng_parse_float(value, default=None):
    """``float`` d'une entrée libre, ou ``default`` (jamais une 500)."""
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class MdeCalculatorView(APIView):
    """PUB87 — Calculateur MDE / puissance opérateur : vue MINCE sur ``mde.py``
    (aucun recalcul métier ré-implémenté). À la création d'une expérience,
    répond « avec votre volume, ~X jours pour détecter +20 % » de façon
    interactive. Company-scopé, gaté ``adsengine_view``.

    ``?p=`` taux de base (proportion, 0<p<1), ``?volume=`` essais/bras/jour
    (>0), ``?cible=`` effet relatif visé (fraction, défaut 0,20 = +20 %). Toute
    entrée invalide → 400 explicite en FR (jamais une 500)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from . import mde

        p = _adseng_parse_float(request.query_params.get('p'))
        volume = _adseng_parse_float(request.query_params.get('volume'))
        cible = _adseng_parse_float(request.query_params.get('cible'), 0.20)

        if p is None or not (0.0 < p < 1.0):
            return Response(
                {'detail': 'Taux de base p attendu dans ]0 ; 1[.'}, status=400)
        if volume is None or volume <= 0:
            return Response(
                {'detail': 'Volume (essais/bras/jour) strictement positif '
                           'attendu.'}, status=400)
        if cible <= 0:
            return Response(
                {'detail': 'Effet relatif cible strictement positif attendu.'},
                status=400)

        jours = mde.days_to_detect(p, cible, volume)
        by_h = mde.mde_by_horizon(p, volume)
        mde_par_horizon = [
            {'jours': d,
             'mde_relatif_pct': (round(v * 100, 1)
                                 if v != float('inf') else None)}
            for d, v in sorted(by_h.items())]
        phrase = (
            f"Avec votre volume (~{volume:g} essais/bras/jour), il faut "
            f"~{jours} jour(s) pour détecter un effet de "
            f"+{cible * 100:g} % de façon fiable.")
        return Response({
            'p': p, 'volume': volume, 'cible_relative': cible,
            'jours_pour_cible': jours, 'phrase_fr': phrase,
            'mde_par_horizon': mde_par_horizon,
        })


class ExplorationLedgerView(APIView):
    """PUB88 — Livre de compte MENSUEL exploration vs exploitation (MAD dépensés
    à explorer vs sur le gagnant confirmé). Company-scopé, gaté
    ``adsengine_view``. ``?debut=&fin=`` (dates ISO) bornent la fenêtre."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import exploration_ledger
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        return Response({'mois': exploration_ledger(
            company, date_start=debut, date_end=fin)})


class CreativeScatterView(APIView):
    """ADSDEEP47 — Nuage de points hook rate × dépense (quadrants FR « pépites
    cachées »/« gouffres »/« gagnants confirmés »/« à surveiller »).
    ``?debut=&fin=`` bornent la période (défaut : 30 jours glissants)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import creative_scatter
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        data = creative_scatter(company, date_start=debut, date_end=fin)
        return Response(data)


class AccountAuditView(APIView):
    """ADSDEEP63 — Audit de compte à la demande (Madgicx-style, FR) :
    structure/naming, fragmentation budgétaire, fatigue créative, tracking
    (pixel/CAPI/UTM), fenêtres de données. 100 % LECTURE, company-scopé, gaté
    ``adsengine_view`` (même permission que les autres vues reporting)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .audit import account_audit_score, run_account_audit
        data = run_account_audit(company)
        # PUB57 — tuile Dashboard : score transparent (dérivé des 5 sections
        # ci-dessus) + delta hebdo, additif (les 5 sections restent inchangées).
        data['score_tile'] = account_audit_score(company, audit=data)
        return Response(data)


class CommentFaqView(APIView):
    """PUB71 — Mine de questions des commentaires : thèmes agrégés (prix/
    garantie/subvention/durée) + candidats ``seed_brief`` pour la génération
    ancrée. 100 % LECTURE, company-scopé, gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .comment_mining import mine_comment_questions
        return Response(mine_comment_questions(company))


class AdObjectionsView(APIView):
    """PUB72 — Top objections PAR VARIANTE d'annonce (motif_perte + notes de
    chatter CRM, tags mots-clés purs) + angles suggérés en backlog. 100 %
    LECTURE, company-scopé, gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .comment_mining import mine_ad_objections
        return Response(mine_ad_objections(company))


class VisualFatigueView(APIView):
    """PUB74 — Fatigue au niveau du VISUEL (``visual_asset_key`` réutilisé sur
    N créas malgré des hooks différents, + déclin CTR cross-ads). 100 %
    LECTURE, company-scopé, gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .metrics import visual_fatigue_report
        return Response(visual_fatigue_report(company))


class WeatherTriggerView(APIView):
    """PUB79 — Déclencheur météo (canicule ⇒ angle pompage/climatisation),
    suggestions de backlog SEULEMENT (jamais une action automatique). 100 %
    LECTURE, company-scopé, gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .weather_trigger import canicule_backlog_suggestions
        return Response({'suggestions': canicule_backlog_suggestions(company)})


class CoverageReportView(APIView):
    """PUB80 — Rapport « trous de couverture » : formats Meta jamais couverts
    + segments démographiques à forte dépense sans créa dédiée. 100 %
    LECTURE, company-scopé, gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .coverage import coverage_report
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        return Response(
            coverage_report(company, date_start=debut, date_end=fin))


class FactoryLaneRoiView(APIView):
    """PUB81 — ROI par LANE de fabrique créative (coût-par-résultat par
    ``source_lane`` : zapcap/fal/templated/elevenlabs/json2video/chantier/
    ugc/manuel). 100 % LECTURE, company-scopé, gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_reporting_company(request)
        if err is not None:
            return err
        from .reporting import factory_lane_roi
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        return Response(
            factory_lane_roi(company, date_start=debut, date_end=fin))


class MetaConnectionStatusView(APIView):
    """ENG22 — Statut de connexion (GET) + enregistrement des identifiants
    (POST). Les identifiants sont **write-only** : un GET ne renvoie JAMAIS un
    secret, seulement ``connected`` (présence d'un jeton) + un ID de compte
    masqué. L'enregistrement N'ACTIVE JAMAIS la connexion (aucune activation
    depuis l'ERP) — ``enabled`` reste tel quel."""

    permission_classes = [IsAuthenticated]  # affiné par get_permissions

    def get_permissions(self):
        _w = self.request.method in ('POST', 'PATCH', 'PUT', 'DELETE')
        return [HasPermissionOrLegacy('adsengine_manage' if _w else 'adsengine_view')()]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        conn = MetaConnection.objects.filter(company=company).first()
        return Response({
            'connected': bool(conn and conn.has_token),
            'ad_account_id_masque': _mask_account_id(
                conn.ad_account_id if conn else ''),
            # Devise du compte publicitaire (lue par la synchro) — 'MAD' en repli.
            'currency': (conn.currency if conn else '') or 'MAD',
        })

    def post(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        data = request.data if isinstance(request.data, dict) else {}
        conn, _ = MetaConnection.objects.get_or_create(company=company)
        creds = dict(conn.credentials or {})
        for k in _CONN_CRED_KEYS:
            v = data.get(k)
            if v not in (None, ''):
                creds[k] = v
        conn.credentials = creds
        for k in _CONN_COLUMN_KEYS:
            v = data.get(k)
            if v not in (None, ''):
                setattr(conn, k, str(v))
        # Activer la connexion en LECTURE dès qu'un jeton valide est présent :
        # cela autorise seulement la synchro/lecture Meta (miroirs + insights),
        # JAMAIS une dépense. L'invariant #3 (toute campagne/adset/ad naît PAUSED,
        # aucune ACTIVATION de campagne possible) reste garanti côté meta_client,
        # inchangé ici — activer la connexion ≠ activer une campagne.
        conn.enabled = bool(conn.has_token)
        conn.save()
        return Response({
            'connected': bool(conn.has_token),
            'ad_account_id_masque': _mask_account_id(conn.ad_account_id),
        })


class MetaConnectionHealthView(APIView):
    """ENG12/ENG22 — Santé du câblage sous forme de statuts affichables
    (``{statuses: [{key, ok, detail}]}``). Rapporte la seule PRÉSENCE (jamais la
    valeur) : jeton, compte pub, page, pixel, CAPI (clés serveur), et l'état « en
    pause par design ». Aucun secret ne fuit. Lecture ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        conn = MetaConnection.objects.filter(company=company).first()
        has_token = bool(conn and conn.has_token)
        capi_ok = bool(os.environ.get('META_CAPI_ACCESS_TOKEN')
                       and os.environ.get('META_CAPI_PIXEL_ID'))
        statuses = [
            {'key': 'token', 'ok': has_token,
             'detail': '' if has_token else 'Aucun jeton enregistré.'},
            {'key': 'ad_account', 'ok': bool(conn and conn.ad_account_id),
             'detail': ''},
            {'key': 'page', 'ok': bool(conn and conn.page_id), 'detail': ''},
            {'key': 'pixel', 'ok': bool(conn and conn.pixel_id), 'detail': ''},
            {'key': 'capi', 'ok': capi_ok,
             'detail': '' if capi_ok else 'Clé serveur CAPI absente.'},
            {'key': 'paused', 'ok': True,
             'detail': 'Le client naît en pause (règle de sécurité).'},
        ]
        # PUB97 — tuile solde prépayé Meta : lit la dernière alerte trésorerie
        # non résolue (posée par la synchro), sans jamais appeler l'API en direct.
        bal_alert = (EngineAlert.objects
                     .filter(company=company, entity_key='prepaid_balance',
                             resolved=False)
                     .order_by('-created_at').first())
        bal_detail = (bal_alert.detail or {}) if bal_alert else {}
        statuses.append({
            'key': 'prepaid_balance',
            # OK tant qu'aucune alerte de solde bas n'est ouverte ; None-safe.
            'ok': bal_alert is None or bal_alert.severity == 'info',
            'detail': (bal_alert.message if bal_alert else ''),
            'days_runway': bal_detail.get('days_runway'),
            'balance': bal_detail.get('balance'),
            'currency': bal_detail.get('currency', ''),
        })
        return Response({'statuses': statuses})


class SyncStatusView(APIView):
    """PUB41 — Fraîcheur de synchro PAR TYPE (dernier sync OK + âge minutes +
    ``stale``), pour le bandeau global « Meta ne répond plus depuis X… » et
    les horodatages discrets par tuile. Vue MINCE — dérivée de
    ``metrics.sync_status`` (aucune nouvelle colonne, aucun effet de bord).
    Lecture ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from .metrics import sync_status
        return Response(sync_status(company))


class TodayQueueView(APIView):
    """PUB42 — File « Aujourd'hui » unifiée (écran d'accueil ``/publicite``) :
    garde-fous > alertes > approbations > commentaires > digest en UNE liste
    classée par priorité. Vue MINCE — dérivée de ``metrics.today_queue``
    (reshape de lignes déjà existantes, aucun recalcul métier). Lecture
    ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from .metrics import today_queue
        items = today_queue(company)
        return Response({'items': items, 'total': len(items)})


class GuardrailSingletonView(APIView):
    """ENG3/ENG22 — Garde-fous d'UNE société vus comme un singleton (GET/PATCH
    sans id). Mappe les libellés d'écran HISTORIQUES (``max_daily_budget_mad``
    / ``max_monthly_budget_mad``) sur les 2 champs modèle correspondants
    (``daily_budget_ceiling_mad`` / ``monthly_budget_ceiling_mad``).

    PUB9 — TOUS les AUTRES champs de ``GuardrailConfig`` (weekly_change_pct_
    max, anomaly_window_hours, les 2 bascules ENG8, pacing/exploration
    ADSENG4, les 4 poids santé SIG1) voyagent désormais aussi, sous leur nom
    modèle DIRECT (identique à ``GuardrailConfigSerializer``/``garde-fous/``
    — même donnée, deux surfaces) : avant cette tâche, ce singleton n'exposait
    QUE les 2 plafonds budget, et ``ConnectionScreen`` n'en éditait donc que 2.
    Company-scopé ; lecture ``adsengine_view`` / écriture ``adsengine_manage``.
    """

    permission_classes = [IsAuthenticated]  # affiné par get_permissions

    def get_permissions(self):
        _w = self.request.method in ('POST', 'PATCH', 'PUT', 'DELETE')
        return [HasPermissionOrLegacy('adsengine_manage' if _w else 'adsengine_view')()]

    # Alias HISTORIQUES (nom écran ≠ nom modèle) — seuls les 2 plafonds budget.
    _ALIASED_FIELDS = {
        'max_daily_budget_mad': 'daily_budget_ceiling_mad',
        'max_monthly_budget_mad': 'monthly_budget_ceiling_mad',
    }
    # PUB9 — le reste de GuardrailConfig, sous son nom modèle DIRECT.
    _DIRECT_FIELDS = (
        'weekly_change_pct_max', 'anomaly_window_hours',
        'auto_rotate_creative', 'auto_rebalance_within_band',
        'pacing_band_pct', 'exploration_floor_mad', 'exploration_floor_pct',
        'health_creative_weight_ctr', 'health_creative_weight_freshness',
        'health_ops_weight_cpl', 'health_ops_weight_delivery',
    )
    _BOOL_FIELDS = {'auto_rotate_creative', 'auto_rebalance_within_band'}

    @classmethod
    def _payload(cls, cfg):
        data = {screen_key: getattr(cfg, model_field)
                for screen_key, model_field in cls._ALIASED_FIELDS.items()}
        for field in cls._DIRECT_FIELDS:
            data[field] = getattr(cfg, field)
        # Aucun champ de stockage pour la bande d'approbation (aucune
        # migration ajoutée) : exposée None. GAP documenté.
        data['require_approval_above_mad'] = None
        return data

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        cfg, _ = GuardrailConfig.objects.get_or_create(company=company)
        return Response(self._payload(cfg))

    def patch(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        cfg, _ = GuardrailConfig.objects.get_or_create(company=company)
        data = request.data if isinstance(request.data, dict) else {}
        changed = []
        for src, field in self._ALIASED_FIELDS.items():
            if src in data and data[src] not in (None, ''):
                try:
                    setattr(cfg, field, int(float(data[src])))
                except (TypeError, ValueError):
                    return Response(
                        {'detail': f'Valeur invalide pour {src}.'}, status=400)
                changed.append(field)
        for field in self._DIRECT_FIELDS:
            if field not in data:
                continue
            value = data[field]
            if field in self._BOOL_FIELDS:
                setattr(cfg, field, bool(value))
                changed.append(field)
                continue
            if value in (None, ''):
                continue
            try:
                setattr(cfg, field, int(float(value)))
            except (TypeError, ValueError):
                return Response(
                    {'detail': f'Valeur invalide pour {field}.'}, status=400)
            changed.append(field)
        if changed:
            cfg.save(update_fields=changed + ['updated_at'])
        return Response(self._payload(cfg))


def _dashboard_spend_window(company, ct, debut, fin):
    """PUB40 — Agrégat ``{spend, cpl, frequency}`` (Decimal/None) sur
    ``InsightSnapshot`` de campagne, borné à ``[debut, fin]`` quand fournis
    (bornes ``None`` = pas de filtre sur ce côté, comportement historique)."""
    from decimal import Decimal

    from django.db.models import Avg, Sum

    from .models import InsightSnapshot as Snap

    qs = Snap.objects.filter(company=company, content_type=ct)
    if debut is not None:
        qs = qs.filter(date__gte=debut)
    if fin is not None:
        qs = qs.filter(date__lte=fin)
    agg = qs.aggregate(
        spend=Sum('spend'), results=Sum('results'), freq=Avg('frequency'))
    spend = agg['spend'] or Decimal('0')
    results = agg['results'] or 0
    cpl = (spend / results) if results else None
    return {'spend': spend, 'cpl': cpl, 'frequency': agg['freq']}


# ── ENG10/ENG23 — Dashboard « un chiffre » + drill-down leads + pacing ────────
class MetricsDashboardView(APIView):
    """ENG23 — Chiffres du dashboard : coût-par-signature (héro), dépense totale,
    CPL global, fréquence moyenne. Agrégats LECTURE SEULE sur les
    ``InsightSnapshot`` de campagne + ``metrics.cost_per_signature_summary``.
    Lecture ``adsengine_view``.

    PUB40 — ``?debut=&fin=`` (dates ISO, optionnelles) bornent dépense/CPL/
    fréquence sur la période choisie par le sélecteur de date de la console ;
    omis, comportement inchangé (tout l'historique). ``?compare=1`` (exige
    ``debut``+``fin``) ajoute un bloc ``previous`` (mêmes 3 chiffres sur la
    période de comparaison PUB40 — « hier vs même jour semaine passée » pour
    un jour unique, sinon la période équivalente précédente). Le héro
    (coût-par-signature/signatures) reste GLOBAL — une signature CRM/Odoo
    n'est pas horodatée de façon fiable au jour près, jamais de chiffre
    fenêtré fabriqué à partir d'une donnée qui ne l'est pas."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from django.contrib.contenttypes.models import ContentType

        from .metrics import cost_per_signature_summary, previous_period

        summary = cost_per_signature_summary(company)
        cps = summary['cost_per_signature']
        signatures = summary.get('total_signed') or 0
        signatures_source = 'crm'
        # ADSENG-ODOO — quand le connecteur Odoo est configuré, les signatures
        # RÉELLES vivent dans Odoo (le CRM ERP peut être vide). Le héro-chiffre
        # reflète alors le coût-par-signature adossé à Odoo. Best-effort et
        # jamais bloquant : Odoo indispo / 0 signature -> on garde le CRM (la vue
        # ``odoo_cost_per_signature`` ne lève jamais, cf. #417).
        try:
            from .odoo_client import is_configured as _odoo_configured
            if _odoo_configured():
                from .odoo_metrics import odoo_cost_per_signature
                odoo = odoo_cost_per_signature(company)
                if odoo.get('signatures'):
                    cps = odoo['cost_per_signature']
                    signatures = odoo['signatures']
                    signatures_source = 'odoo'
        except Exception:  # noqa: BLE001 — le dashboard ne casse jamais sur Odoo
            pass
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        window = _dashboard_spend_window(company, ct, debut, fin)
        spend, cpl = window['spend'], window['cpl']
        # Devise du compte Meta (les montants dépense/CPL/coût-par-signature sont
        # dans CETTE devise, pas forcément en MAD). 'MAD' en repli tant que la
        # synchro ne l'a pas lue.
        conn = MetaConnection.objects.filter(company=company).first()
        currency = (conn.currency if conn else '') or 'MAD'
        payload = {
            'cost_per_signature': cps,
            'signatures': signatures,
            'signatures_source': signatures_source,
            'currency': currency,
            'spend': str(spend),
            'cpl': (str(cpl) if cpl is not None else None),
            'frequency': (str(window['frequency'])
                          if window['frequency'] is not None else None),
        }
        compare = _truthy_param(request.query_params.get('compare'))
        if compare and debut is not None and fin is not None:
            prev_debut, prev_fin = previous_period(debut, fin)
            prev_window = _dashboard_spend_window(
                company, ct, prev_debut, prev_fin)
            payload['previous'] = {
                'debut': prev_debut.isoformat(), 'fin': prev_fin.isoformat(),
                'spend': str(prev_window['spend']),
                'cpl': (str(prev_window['cpl'])
                        if prev_window['cpl'] is not None else None),
                'frequency': (str(prev_window['frequency'])
                              if prev_window['frequency'] is not None
                              else None),
            }
        return Response(payload)


class MetricsLeadsView(APIView):
    """ENG10/ENG23 — Drill-down : les leads RÉELS derrière le héro-chiffre
    (traçabilité). Résout les leads SIGNÉS attribués via ``metrics`` +
    ``crm.selectors.lead_card`` (jamais un import de ``crm.models``). Lecture
    ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from apps.crm.selectors import lead_card

        from .metrics import cost_per_signature

        ids = []
        for row in cost_per_signature(company):
            ids.extend(row['signed_lead_ids'])
        seen = set()
        leads = []
        for lid in ids:
            if lid in seen:
                continue
            seen.add(lid)
            card = lead_card(lid, company)
            if card is None:
                continue
            leads.append({
                'id': lid,
                'nom': card['label'],
                'etape': card['subtitle'],
                'url': card['url'],
            })
        # ADSENG-ODOO — le drill « signature » liste AUSSI les deals signés Odoo
        # (là où vivent les vraies signatures du fondateur) : sans cela, le héro
        # affiche un chiffre Odoo mais « Voir les leads » restait vide (CRM ERP
        # vide). ``id: None`` : un deal Odoo n'a pas de fiche CRM ERP à ouvrir.
        # Montants Odoo en MAD (jamais la devise Meta). Best-effort (#417 :
        # jamais un 500) ; les autres métriques (spend/lead/frequency) gardent
        # la liste CRM historique inchangée.
        metric = (request.query_params.get('metric') or '').strip()
        if metric in ('', 'signature', 'cost_per_signature'):
            try:
                from .odoo_client import is_configured as _odoo_ok
                if _odoo_ok():
                    from .odoo_selectors import signed_deals
                    origin_fr = {'sale_order': 'Commande confirmée (Odoo)',
                                 'won_lead': 'Lead gagné (Odoo)'}
                    for deal in signed_deals():
                        leads.append({
                            'id': None,
                            'nom': (deal.get('source_name')
                                    or deal.get('phone_norm') or 'Deal Odoo'),
                            'etape': origin_fr.get(
                                deal.get('origin'), 'Signé (Odoo)'),
                            'montant': float(deal.get('amount_mad') or 0),
                            'source': 'odoo',
                        })
            except Exception:  # noqa: BLE001 — le drill ne casse jamais sur Odoo
                pass
        return Response(leads)


class MetricsPacingView(APIView):
    """ENG20/ENG42 — Pacing mensuel : enveloppe, dépense, projection, jours
    restants, état. Dérivé (aucune écriture) via
    ``pacing.compute_pacing_for_company``. Lecture ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from . import pacing as pacing_mod

        r = pacing_mod.compute_pacing_for_company(company)
        state_fr = {
            pacing_mod.STATE_ON_TRACK: 'Dans le rythme',
            pacing_mod.STATE_UNDER_PACING: 'Sous le rythme',
            pacing_mod.STATE_OVER_PACING: 'Au-dessus du rythme',
            pacing_mod.STATE_BREACH_IMMINENT: 'Dépassement imminent',
            pacing_mod.STATE_PAUSED_FOR_MONTH: 'En pause pour le mois',
        }
        return Response({
            'enveloppe_mad': r.monthly_ceiling,
            'depense_mad': r.spend_to_date,
            'projection_mad': r.forecast_spend,
            'jours_restants': r.days_remaining,
            'etat': r.state,
            'etat_display': state_fr.get(r.state, r.state),
            'lignes': [
                {'id': 'attendu', 'label': 'Dépense attendue à ce jour',
                 'montant_mad': r.expected_spend_to_date},
            ],
        })


class MetricsDashboardV2View(APIView):
    """ADSDEEP61 — Tuiles du « Dashboard v2 » : conversations WhatsApp RÉELLES
    (CTWA) + MER mixte (dépense Meta vs CA signé Odoo, DEUX devises côte à
    côte — jamais convertie), chacune avec une sparkline quotidienne sur 14
    jours. Dérivé (aucune écriture) via ``metrics.dashboard_v2_metrics``.
    Lecture ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from .metrics import dashboard_v2_metrics
        return Response(dashboard_v2_metrics(company))


class ReconciliationListView(APIView):
    """ENG31/ENG42 — Liste des instantanés de réconciliation (Meta vs ERP).
    Company-scopé ; lecture ``adsengine_view``. Les chiffres sont des comptes de
    LEADS (la réconciliation compare des leads, pas des MAD) surfacés via le
    canal numérique générique de l'écran."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        status_fr = {
            ReconciliationSnapshot.Statut.OK: 'Réconcilié',
            ReconciliationSnapshot.Statut.ECART: 'Écart',
            ReconciliationSnapshot.Statut.A_VERIFIER: 'À vérifier',
        }
        snaps = (ReconciliationSnapshot.objects
                 .filter(company=company)
                 .select_related('campaign')
                 .order_by('-date', 'campaign_id'))
        rows = []
        for s in snaps:
            detail = s.detail if isinstance(s.detail, dict) else {}
            ratio = detail.get('ratio')
            camp = s.campaign
            rows.append({
                'id': s.pk,
                'campagne': ((camp.name or camp.meta_id) if camp else '—'),
                'meta_mad': s.meta_leads,
                'erp_mad': s.erp_leads,
                'ecart_mad': s.delta_leads,
                'ecart_pct': (round(ratio * 100, 1)
                              if isinstance(ratio, (int, float)) else None),
                'statut': s.status,
                'statut_display': status_fr.get(s.status, s.status),
                'lignes': [],
            })
        return Response(rows)


class ReconciliationBackfillView(APIView):
    """PUB105 — Bouton « rattraper » depuis l'alerte de divergence.

    Déclenche un backfill CIBLÉ (leads via pull-sync + insights de la campagne)
    quand une divergence « webhook non reçu » a été flaggée. Accepte soit
    ``alert_id`` (on lit ``campaign_meta_id``/``date`` dans le détail de
    l'``EngineAlert`` de divergence), soit ``campaign_meta_id`` + ``date``
    directement. Société forcée serveur. Écriture ``adsengine_manage``.
    Idempotent (rejouable)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        data = request.data if isinstance(request.data, dict) else {}
        campaign_meta_id = str(data.get('campaign_meta_id') or '')
        day = data.get('date') or None

        alert_id = data.get('alert_id')
        if alert_id:
            alert = EngineAlert.objects.filter(
                company=company, pk=alert_id).first()
            if alert is None:
                return Response({'detail': 'Alerte introuvable.'}, status=404)
            detail = alert.detail if isinstance(alert.detail, dict) else {}
            campaign_meta_id = campaign_meta_id or str(
                detail.get('campaign_meta_id') or '')
            day = day or detail.get('date')

        parsed_day = None
        if day:
            import datetime as _dt
            try:
                parsed_day = _dt.date.fromisoformat(str(day))
            except (ValueError, TypeError):
                parsed_day = None

        from .tasks import backfill_after_divergence
        summary = backfill_after_divergence(
            company, campaign_meta_id=campaign_meta_id, day=parsed_day)
        return Response(summary)


def _brief_payload(brief):
    """Reshape un ``WeeklyBrief`` (data déterministe) vers le contrat de l'écran
    (``{periode, resume, items:[{quoi, pourquoi, suggestion, action_id}]}``).
    ``brief`` None → structure vide (jamais une 500)."""
    if brief is None:
        return {'periode': '', 'resume': '', 'items': []}
    data = brief.data if isinstance(brief.data, dict) else {}
    per = data.get('periode') or {}
    periode = ''
    if per.get('debut') and per.get('fin'):
        periode = f"{per['debut']} → {per['fin']}"
    items = []
    cps = data.get('cout_par_signature_cumule')
    if cps is not None:
        items.append({
            'id': 'cps', 'quoi': 'Coût par signature (cumulé)',
            'pourquoi': f"{data.get('signatures_cumulees', 0)} signature(s).",
            'suggestion': f"{cps} MAD par signature.", 'action_id': None})
    for p in (data.get('propositions') or []):
        items.append({
            'id': f"prop-{p.get('id')}",
            'quoi': p.get('reason_fr', ''),
            'pourquoi': '', 'suggestion': '', 'action_id': p.get('id')})
    return {
        'periode': periode,
        'resume': (f"Brief hebdomadaire {periode}").strip(),
        'items': items,
    }


class BriefLatestView(APIView):
    """ENG11/ENG26 — Dernier brief hebdomadaire de la société. Company-scopé ;
    lecture ``adsengine_view``. Aucun texte LLM (déterministe, v1)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        brief = (WeeklyBrief.objects
                 .filter(company=company)
                 .order_by('-period_start', '-created_at')
                 .first())
        return Response(_brief_payload(brief))


class AdCampaignMirrorViewSet(AdsengineViewSet):
    """ENG5/ENG24 — Liste (lecture) des miroirs de campagne + synchro à la
    demande + classement par créatif. Les miroirs sont écrits par la SYNCHRO
    (jamais créés via l'API — ``create`` renvoie 405). Company-scopé (hérité).

    PUB40 — ``GET .../campaigns/?debut=&fin=`` (dates ISO, optionnelles)
    bornent ``depense_mad``/``nb_leads`` sur la période choisie par le
    sélecteur de date de l'écran Campagnes (propagées au serializer via le
    contexte) ; omises, comportement inchangé (tout l'historique)."""

    queryset = AdCampaignMirror.objects.all()
    serializer_class = AdCampaignMirrorSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['debut'] = _adseng_parse_date(
            self.request.query_params.get('debut'))
        context['fin'] = _adseng_parse_date(
            self.request.query_params.get('fin'))
        return context

    def create(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed('POST')

    @action(detail=False, methods=['post'], url_path='sync-now',
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def sync_now(self, request):
        """ENG6 — Déclenche la synchro des miroirs+insights depuis Meta. NO-OP
        propre (200) tant que la connexion n'est pas active + tokenisée.
        Écriture → ``adsengine_manage``."""
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        conn = (MetaConnection.objects
                .filter(company=company, enabled=True).first())
        if conn is None or not conn.is_live:
            return Response({
                'synced': False,
                'detail': 'Connexion Meta non active — synchronisation '
                          'impossible.'})
        from .tasks import _sync_company
        try:
            _sync_company(conn)
        except Exception as exc:  # échec réseau/Meta → jamais une 500
            return Response({'synced': False, 'detail': str(exc)}, status=502)
        return Response({
            'synced': True,
            'campaigns': AdCampaignMirror.objects.filter(
                company=company).count()})

    @action(detail=False, methods=['post'], url_path='backfill-complet',
            permission_classes=[HasPermissionOrLegacy('adsengine_manage')])
    def backfill_complet(self, request):
        """FIXPUB3 — Lance le rattrapage COMPLET « tout l'historique » (insights
        niveau ad + ventilations + créatifs live + leads lead-form) pour la
        société de l'utilisateur, en tâche de fond. Réponse 202 immédiate ; le
        travail (best-effort, NO-OP propre sans connexion Meta active) tourne en
        async. Écriture → ``adsengine_manage``."""
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        from .tasks import backfill_complet as backfill_task
        backfill_task.delay(company.id)
        return Response({
            'queued': True,
            'detail': ('Rattrapage complet lancé : insights, ventilations, '
                       'créatifs et leads seront resynchronisés en arrière-plan.'),
        }, status=202)

    @action(detail=False, methods=['get'], url_path='creative-ranking',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def creative_ranking(self, request):
        """ENG24 — Classement par créatif (réponses attribuées / dépense).
        Réutilise ``reporting.variant_table`` (CRM lu via selectors). Lecture
        ``adsengine_view``."""
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Aucune société.'}, status=400)
        from .reporting import variant_table
        data = variant_table(company)
        items = [
            {'id': v['meta_id'], 'nom': v['name'],
             'reponses_whatsapp': v['leads'], 'cout_mad': v['spend']}
            for v in data['variants']
        ]
        return Response(items)

    @action(detail=True, methods=['get'], url_path='hierarchie',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def hierarchy(self, request, pk=None):
        """ADSDEEP60 — Hiérarchie navigable Campagne → Ad sets → Ads (3
        niveaux) pour l'écran Campagnes : statuts/budgets/dépenses/leads par
        niveau + badge d'apprentissage par ad set (ADSDEEP32). ``get_object``
        hérité borne déjà la campagne à la société de l'utilisateur (404 sinon)
        — lecture ``adsengine_view``, aucune écriture."""
        campaign = self.get_object()
        from .models import AdMirror, AdSetMirror
        from .serializers import AdMirrorSerializer, AdSetMirrorSerializer

        adsets = list(AdSetMirror.objects.filter(
            company_id=campaign.company_id, campaign=campaign)
            .order_by('-created_at'))
        ads = list(AdMirror.objects.filter(
            company_id=campaign.company_id, adset__in=adsets)
            .order_by('-created_at')) if adsets else []
        ads_by_adset = {}
        for ad in ads:
            ads_by_adset.setdefault(ad.adset_id, []).append(ad)

        data = AdCampaignMirrorSerializer(campaign).data
        data['adsets'] = []
        for adset in adsets:
            adset_data = AdSetMirrorSerializer(adset).data
            adset_data['ads'] = AdMirrorSerializer(
                ads_by_adset.get(adset.id, []), many=True).data
            data['adsets'].append(adset_data)
        return Response(data)


# ── ENG36/ENG44 — Simulations (rejeu visuel — SHELL de scénario) ──────────────
_SIM_SCENARIO_LABELS = {
    'clear_winner': 'Gagnant net',
    'noisy_tie': 'Égalité bruitée',
    'mid_flight_drift': 'Dérive en cours de vol',
    'delivery_collapse': 'Effondrement de diffusion',
}
_SIM_VERDICT_LABELS = {
    'converged': 'Convergé — gagnant décisif',
    'no_signal': 'Aucun signal',
    'drift_detected': 'Dérive détectée',
    'collapse_handled': 'Effondrement géré',
}


def _simulation_report_shell(scenario):
    """SHELL de rapport de simulation (métadonnée du scénario + verdict attendu),
    SANS exécuter ``simulator.simulate`` — ce dernier écrit des miroirs
    synthétiques dans la société RÉELLE et fausserait les métriques (héro coût-
    par-signature, réconciliation). Structure conforme à ``normalizeSimReport``
    du front ; le rejeu détaillé (allocations/décisions dans le temps) reste un
    GAP tant qu'aucune société synthétique isolée n'existe."""
    from .simulator import EXPECTED_VERDICT
    label = _SIM_SCENARIO_LABELS.get(scenario, scenario)
    verdict = EXPECTED_VERDICT.get(scenario, '')
    vdisp = _SIM_VERDICT_LABELS.get(verdict, verdict or '—')
    return {
        'id': scenario,
        'nom': label,
        'cree_le': '',
        'scenarios': [{
            'key': scenario, 'nom': label, 'verdict': verdict,
            'verdict_display': vdisp,
            'resume_fr': (f"Scénario « {label} » — verdict attendu : {vdisp}. "
                          "Rejeu détaillé non exécuté depuis la console."),
        }],
        'allocations': [],
        'decisions': [],
    }


class SimulationListView(APIView):
    """ENG44 — Catalogue des scénarios de simulation disponibles
    (``[{id, nom, cree_le}]``). Métadonnée statique ; lecture ``adsengine_view``.
    Aucun effet de bord (le moteur n'est pas exécuté)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from .simulator import EXPECTED_VERDICT
        items = [
            {'id': k, 'nom': _SIM_SCENARIO_LABELS.get(k, k), 'cree_le': ''}
            for k in EXPECTED_VERDICT
        ]
        return Response(items)


class SimulationDetailView(APIView):
    """ENG44 — Rapport (shell) d'un scénario de simulation. Lecture
    ``adsengine_view`` ; company-scopé ; aucun effet de bord."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request, key):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from .simulator import EXPECTED_VERDICT
        if key not in EXPECTED_VERDICT:
            return Response({'detail': 'Scénario inconnu.'}, status=404)
        return Response(_simulation_report_shell(key))


# ── ENG27/ENG41 — Backlog par campagne (runway + diversité + lots) ────────────
class BacklogListView(APIView):
    """ENG41 — File créative PAR campagne : runway (jours), diversité d'accroches,
    et lots de recombinaison (chacun approuvable). Lecture ``adsengine_view`` ;
    company-scopé. Chiffres LECTURE SEULE via ``backlog.py``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from . import backlog as backlog_mod

        diversity = backlog_mod.hook_diversity(company)
        target_weeks = backlog_mod.LOW_BACKLOG_WEEKS
        rows = []
        for camp in AdCampaignMirror.objects.filter(company=company):
            runway_weeks = backlog_mod.compute_runway(company, campaign=camp)
            items = backlog_mod.queue_for_campaign(company, camp)
            lots_map = {}
            for it in items:
                batch = it.batch
                if batch is None:
                    continue
                slot = lots_map.setdefault(
                    batch.pk, {'batch': batch, 'items': []})
                slot['items'].append(it)
            lots = []
            for slot in lots_map.values():
                b = slot['batch']
                assets = []
                for it in slot['items']:
                    a = it.asset
                    if a is None:
                        continue
                    assets.append({
                        'id': a.id,
                        'designation': (a.hook_text or a.hook_id
                                        or f'Créatif {a.id}')})
                lots.append({
                    'id': b.pk,
                    'nom': (b.note or f'Lot {b.pk}'),
                    'statut': b.status,
                    'statut_display': b.get_status_display(),
                    'nb_hooks': len(assets),
                    'assets': assets,
                })
            rows.append({
                'id': camp.pk,
                'campagne': (camp.name or camp.meta_id),
                'runway_jours': round(runway_weeks * 7, 1),
                'runway_cible': target_weeks * 7,
                'diversite_hooks': diversity,
                'lots': lots,
            })
        return Response(rows)


class BacklogLotApproveView(APIView):
    """ENG41 — Approuve un LOT de recombinaison (par lot, jamais par variante).
    Réutilise ``recombine.approve_lot``. Écriture ``adsengine_manage`` ;
    company-scopé (le lot d'une autre société → 404)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, lot_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        batch = (CreativeGenerationBatch.objects
                 .filter(company=company, pk=lot_id).first())
        if batch is None:
            return Response({'detail': 'Lot introuvable.'}, status=404)
        from . import recombine
        try:
            recombine.approve_lot(batch, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(CreativeGenerationBatchSerializer(batch).data)


class BacklogDropAssetView(APIView):
    """ENG41 — Dépose un asset (image) dans le backlog d'une campagne. Réutilise
    le stockage de fondation (``records.storage``) puis crée un
    ``CreativeBacklogItem`` EN FILE. Écriture ``adsengine_manage`` ;
    company-scopé (campagne d'une autre société → 404)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, campagne_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        camp = (AdCampaignMirror.objects
                .filter(company=company, pk=campagne_id).first())
        if camp is None:
            return Response({'detail': 'Campagne introuvable.'}, status=404)
        f = request.FILES.get('file')
        if f is None:
            return Response({'detail': 'Fichier requis.'}, status=400)
        from apps.records.storage import store_attachment
        stored, serr = store_attachment(f, company=company)
        if serr:
            return Response({'detail': serr}, status=400)
        asset = CreativeAsset.objects.create(
            company=company,
            asset_type=request.data.get(
                'asset_type', CreativeAsset.AssetType.STATIC),
            file_key=stored['file_key'], source_lane='upload')
        item = CreativeBacklogItem.objects.create(
            company=company, asset=asset, target_campaign=camp,
            source=CreativeBacklogItem.Source.MANUEL,
            status=CreativeBacklogItem.Statut.EN_FILE)
        return Response(
            CreativeBacklogItemSerializer(item).data, status=201)


# ── ADSDEEP9 — Endpoints breakdowns (audience & diffusion) ────────────────────
_BREAKDOWN_MIRROR_TYPES = {
    'campaign': 'AdCampaignMirror',
    'adset': 'AdSetMirror',
    'ad': 'AdMirror',
}


class BreakdownsView(APIView):
    """ADSDEEP9 — Ventilations (démo/placement/région/horaire) d'un objet
    publicitaire, company-scopées et gatées ``adsengine_view``.

    ``GET /api/django/adsengine/breakdowns/?object_type=campaign&object_id=<pk>
    &dimension=age_gender&since=YYYY-MM-DD`` — ``object_type`` ∈ campaign/adset/
    ad ; ``dimension`` et ``since`` optionnels (filtres). L'objet est résolu
    DANS la société de l'appelant : un id d'une autre société renvoie 404 (jamais
    de fuite cross-tenant). Aucun secret."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err

        from django.contrib.contenttypes.models import ContentType

        from . import models as m
        from .models import InsightBreakdown
        from .serializers import InsightBreakdownSerializer

        object_type = (request.query_params.get('object_type') or '').strip()
        object_id = request.query_params.get('object_id')
        model_name = _BREAKDOWN_MIRROR_TYPES.get(object_type)
        if model_name is None or not object_id:
            return Response(
                {'detail': "Paramètres object_type (campaign/adset/ad) et "
                           "object_id requis."}, status=400)
        mirror_model = getattr(m, model_name)
        # Résolution company-scopée : un objet d'une autre société → 404.
        target = mirror_model.objects.filter(
            company=company, pk=object_id).first()
        if target is None:
            return Response({'detail': 'Objet introuvable.'}, status=404)

        ct = ContentType.objects.get_for_model(mirror_model)
        qs = InsightBreakdown.objects.filter(
            company=company, content_type=ct, object_id=target.pk)
        dimension = (request.query_params.get('dimension') or '').strip()
        if dimension:
            qs = qs.filter(dimension=dimension)
        since = (request.query_params.get('since') or '').strip()
        if since:
            qs = qs.filter(date__gte=since)
        return Response(InsightBreakdownSerializer(qs, many=True).data)


class MediaResolveView(APIView):
    """ADSDEEP12 — Résolveur de médias FRAIS d'un créatif.

    ``GET /api/django/adsengine/media/<ref>/?kind=video|image`` — fetch à la
    volée l'URL JOUABLE d'une vidéo (``/<video_id>?fields=source`` — expire
    ~1 h) ou l'URL PERMANENTE d'une image (``adimages`` ``permalink_url``). Le
    résultat est mis en cache Redis ≤30 min et n'est JAMAIS persisté en base (les
    URLs CDN expirent). 404 propre sans média / sans connexion Meta live.
    Company-scopé + gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]
    # Durée de cache (s) — < durée de vie CDN (~1 h). Jamais persisté en base.
    CACHE_TTL = 1800

    def get(self, request, ref):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        kind = (request.query_params.get('kind') or 'video').strip().lower()
        if kind not in ('video', 'image'):
            return Response({'detail': 'kind invalide (video|image).'},
                            status=400)

        from django.core.cache import cache

        cache_key = f'adsengine-media:{company.pk}:{kind}:{ref}'
        cached = cache.get(cache_key)
        if cached is not None:
            # FIXPUB7 — rétro-compat : une entrée de cache ancienne est une URL
            # brute (str) ; la nouvelle est un dict ``{url, picture}``.
            if isinstance(cached, dict):
                payload = dict(cached)
            else:
                payload = {'url': cached, 'picture': ''}
            payload['cached'] = True
            return Response(payload)

        conn = MetaConnection.objects.filter(
            company=company, enabled=True).first()
        if conn is None or not conn.is_live:
            return Response({'detail': 'Connexion Meta indisponible.'},
                            status=404)

        from .meta_client import MetaClient, MetaError

        client = MetaClient.from_connection(conn)
        picture = ''
        try:
            if kind == 'video':
                data = client.get_video_source(ref)
                url = (data or {}).get('source') or ''
                # FIXPUB7 — Meta peut REFUSER la source mp4 (Page non assignée au
                # System User) : la ``picture`` (miniature) reste servie pour que
                # le front bascule sur l'image au lieu d'une vidéo cassée.
                picture = (data or {}).get('picture') or ''
            else:
                data = client.get_ad_image(ref)
                url = (data or {}).get('permalink_url') or ''
        except MetaError:
            return Response({'detail': 'Média introuvable.'}, status=404)
        if not url and not picture:
            return Response({'detail': 'Média introuvable.'}, status=404)
        # Cache l'URL + la miniature (Redis, ≤30 min) — JAMAIS d'écriture en base.
        cache.set(cache_key, {'url': url, 'picture': picture}, self.CACHE_TTL)
        return Response({'url': url, 'picture': picture, 'cached': False})


# ── ADSDEEP13 — Proxy previews (aperçus rendus par Meta) ──────────────────────
# Formats d'aperçu whitelistés (dossier creative-retrieval §5). L'iframe n'est
# valide que 24 h ⇒ jamais stockée, refetch par affichage.
PREVIEW_FORMATS = (
    'MOBILE_FEED_STANDARD', 'INSTAGRAM_STANDARD',
    'FACEBOOK_REELS_MOBILE', 'INSTAGRAM_STORY',
)


class AdPreviewsView(APIView):
    """ADSDEEP13 — Snippet iframe d'aperçu Meta d'une ad, pour un format
    whitelisté.

    ``GET /api/django/adsengine/ads/<ad_meta_id>/previews/?format=<FORMAT>`` —
    l'ad doit appartenir à la société de l'appelant (isolation). L'iframe (valide
    24 h) n'est JAMAIS persistée : refetch à chaque affichage. Company-scopé +
    gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request, ad_meta_id):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        # NB : le paramètre s'appelle ``ad_format`` (PAS ``format``) — ``format``
        # est réservé par DRF pour la négociation de contenu (``?format=json``) et
        # un ``?format=INSTAGRAM_STORY`` renverrait un 404 avant même la vue.
        ad_format = (request.query_params.get('ad_format')
                     or 'MOBILE_FEED_STANDARD').strip()
        if ad_format not in PREVIEW_FORMATS:
            return Response(
                {'detail': 'Format non autorisé.',
                 'formats': list(PREVIEW_FORMATS)}, status=400)

        from .models import AdMirror

        ad = AdMirror.objects.filter(
            company=company, meta_id=ad_meta_id).first()
        if ad is None:
            return Response({'detail': 'Ad introuvable.'}, status=404)

        conn = MetaConnection.objects.filter(
            company=company, enabled=True).first()
        if conn is None or not conn.is_live:
            return Response({'detail': 'Connexion Meta indisponible.'},
                            status=404)

        from .meta_client import MetaClient, MetaError

        client = MetaClient.from_connection(conn)
        try:
            body = client.get_ad_previews(ad_meta_id, ad_format)
        except MetaError:
            return Response({'detail': 'Aperçu indisponible.'}, status=404)
        # iframe NON persistée (valide 24 h) — rendue telle quelle à l'affichage.
        return Response({'format': ad_format, 'body': body})


class AdFullStoryView(APIView):
    """PUB44 — Fiche « histoire complète » d'une ad (créatif + métriques +
    actions passées + commentaires + règles + expériences + ventilations)
    en UNE requête — aujourd'hui éclaté sur 6 écrans. Vue MINCE, dérivée de
    ``metrics.ad_full_story`` (réutilise ``ads_cockpit_rows`` + les mêmes
    filtres que ``BreakdownsView``/``CommentListView`` — aucun recalcul
    métier). ``GET /api/django/adsengine/ads/<meta_id>/histoire/`` — company-
    scopé (un id d'une autre société → 404, jamais de fuite cross-tenant),
    gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request, meta_id):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from .metrics import ad_full_story
        story = ad_full_story(company, meta_id)
        if story is None:
            return Response({'detail': 'Ad introuvable.'}, status=404)
        return Response(story)


class RealLeadsView(APIView):
    """ADSDEEP19 — Comptes de leads RÉELS par ad / par campagne (MetaLeadMirror).

    ``GET /api/django/adsengine/metrics/real-leads/`` — company-scopé, gaté
    ``adsengine_view``. Remplace le « Leads: 0 » des insights par le vrai nombre
    de leads capturés (webhook + pull, dédupliqués). Aucun secret."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from .metrics import real_lead_counts
        return Response(real_lead_counts(company))


class AdsCockpitView(APIView):
    """ADSDEEP22 — Cockpit par ad (écran-console quotidien du fondateur) :
    une ligne par ad combinant miniature créatif, dépense, conversations,
    leads réels, CPL, signatures + coût/signature (Odoo), fréquence, badge de
    fatigue (ADSDEEP45) et statut + apprentissage (ADSDEEP32).

    ``GET /api/django/adsengine/metrics/ads-cockpit/?debut=&fin=`` — company-
    scopé, gaté ``adsengine_view``. Dérivé (aucune écriture) via
    ``metrics.ads_cockpit_rows``, qui ne fait que COMBINER les métriques déjà
    construites (ADSDEEP19/20/25/32/44/45) — aucune logique métier réécrite.
    PUB40 — ``debut``/``fin`` (dates ISO, optionnelles) fenêtrent la
    dépense/leads/CPL/fréquence sur la période choisie par le sélecteur de
    date de la console ; omis, le comportement reste inchangé (tout
    l'historique)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from .metrics import ads_cockpit_rows
        debut = _adseng_parse_date(request.query_params.get('debut'))
        fin = _adseng_parse_date(request.query_params.get('fin'))
        return Response(
            ads_cockpit_rows(company, as_of=fin, start_date=debut))


# ══ ADSDEEP53/54 — Boîte de réception des commentaires (câblage front↔back) ═══
# Vues MINCES : lecture des miroirs company-scopée + chaque action inline ne
# fait que PROPOSER une ``EngineAction`` via les fonctions ``propose_*`` DÉJÀ
# construites de ``services.py`` (règle #3 — jamais d'écriture directe Meta ici).

def _truthy_param(value):
    """``?flag=1|true|yes`` → bool ; absent/vide → None (filtre non appliqué)."""
    if value is None or value == '':
        return None
    return str(value).strip().lower() in ('1', 'true', 'yes', 'oui')


class CommentListView(APIView):
    """ADSDEEP53 — Liste des commentaires (posts + dark posts) miroités.

    ``GET /api/django/adsengine/commentaires/?ad_id=&post_id=&hidden=&unanswered=``
    — company-scopé, gaté ``adsengine_view``. ``ad_id``/``post_id`` filtrent sur
    l'objet commenté (``object_meta_id`` + ``source`` associée) ; ``hidden`` et
    ``unanswered`` sont des booléens optionnels."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        qs = CommentMirror.objects.filter(company=company)
        ad_id = request.query_params.get('ad_id')
        if ad_id:
            qs = qs.filter(object_meta_id=ad_id, source=CommentMirror.Source.AD)
        post_id = request.query_params.get('post_id')
        if post_id:
            qs = qs.filter(
                object_meta_id=post_id, source=CommentMirror.Source.POST)
        hidden = _truthy_param(request.query_params.get('hidden'))
        if hidden is not None:
            qs = qs.filter(is_hidden=hidden)
        unanswered = _truthy_param(request.query_params.get('unanswered'))
        if unanswered:
            qs = qs.filter(answered=False)
        # PUB44 — lien croisé vers la fiche « histoire complète » de l'ad :
        # UNE requête pour toute la société (jamais une par commentaire).
        from .models import AdCreativeMirror
        story_to_ad = dict(
            AdCreativeMirror.objects.filter(company=company)
            .exclude(effective_object_story_id='')
            .values_list('effective_object_story_id', 'ad__meta_id'))
        return Response(CommentMirrorSerializer(
            qs, many=True, context={'story_to_ad': story_to_ad}).data)


class CommentCountsView(APIView):
    """ADSDEEP53 — Compteurs pour le cockpit : totaux + détail PAR objet commenté
    (masqués, non répondus). Company-scopé, gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        qs = CommentMirror.objects.filter(company=company)
        total = qs.count()
        hidden = qs.filter(is_hidden=True).count()
        unanswered = qs.filter(answered=False, is_hidden=False).count()
        par_objet_map = {}
        for c in qs:
            key = c.object_meta_id or ''
            slot = par_objet_map.setdefault(key, {
                'object_meta_id': key, 'source': c.source,
                'total': 0, 'hidden': 0, 'unanswered': 0,
            })
            slot['total'] += 1
            if c.is_hidden:
                slot['hidden'] += 1
            if not c.answered and not c.is_hidden:
                slot['unanswered'] += 1
        return Response({
            'total': total, 'hidden': hidden, 'unanswered': unanswered,
            'par_objet': list(par_objet_map.values()),
        })


def _get_comment_or_404(company, comment_id):
    return CommentMirror.objects.filter(company=company, pk=comment_id).first()


class CommentHideView(APIView):
    """ADSDEEP53 — Propose de masquer/démasquer un commentaire. Réutilise
    ``services.propose_hide_comment``. Écriture ``adsengine_manage`` ;
    company-scopé (un commentaire d'une autre société → 404)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, comment_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        comment = _get_comment_or_404(company, comment_id)
        if comment is None:
            return Response({'detail': 'Commentaire introuvable.'}, status=404)
        from .services import propose_hide_comment
        hidden = request.data.get('hidden', True)
        try:
            action = propose_hide_comment(
                company, comment=comment, hidden=bool(hidden))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EngineActionSerializer(action).data, status=201)


class CommentReplyView(APIView):
    """ADSDEEP53 — Propose une réponse PUBLIQUE. Réutilise
    ``services.propose_reply_comment``. Écriture ``adsengine_manage`` ;
    company-scopé."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, comment_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        comment = _get_comment_or_404(company, comment_id)
        if comment is None:
            return Response({'detail': 'Commentaire introuvable.'}, status=404)
        from .services import propose_reply_comment
        try:
            action = propose_reply_comment(
                company, comment=comment,
                message=request.data.get('message', ''))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EngineActionSerializer(action).data, status=201)


class CommentDeleteView(APIView):
    """ADSDEEP53 — Propose la SUPPRESSION d'un commentaire. Réutilise
    ``services.propose_delete_comment``. Écriture ``adsengine_manage`` ;
    company-scopé."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, comment_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        comment = _get_comment_or_404(company, comment_id)
        if comment is None:
            return Response({'detail': 'Commentaire introuvable.'}, status=404)
        from .services import propose_delete_comment
        try:
            action = propose_delete_comment(company, comment=comment)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EngineActionSerializer(action).data, status=201)


class CommentPrivateReplyView(APIView):
    """ADSDEEP53 — Propose une réponse PRIVÉE (DM). Réutilise
    ``services.propose_private_reply`` (garde-fou 1/commentaire/7 jours déjà
    appliqué côté service). Écriture ``adsengine_manage`` ; company-scopé."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, comment_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        comment = _get_comment_or_404(company, comment_id)
        if comment is None:
            return Response({'detail': 'Commentaire introuvable.'}, status=404)
        from .services import propose_private_reply
        try:
            action = propose_private_reply(
                company, comment=comment,
                message=request.data.get('message', ''))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EngineActionSerializer(action).data, status=201)


# ══ ADSDEEP55/56 — Instagram (câblage front↔back) ═════════════════════════════

class InstagramMediaListView(APIView):
    """ADSDEEP55/56 — Liste des médias Instagram miroités. Company-scopé, gaté
    ``adsengine_view``. La ``caption`` reste LECTURE SEULE (immuable)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        qs = InstagramMediaMirror.objects.filter(company=company)
        return Response(InstagramMediaMirrorSerializer(qs, many=True).data)


class InstagramQuotaView(APIView):
    """ADSDEEP56 — État du quota de publication IG (50/24 h), lu depuis le
    DERNIER ``InstagramPublishJob`` journalisé (jamais un appel Meta live —
    lecture seule de l'état déjà connu, dossier organic-posts-ig §4).
    Company-scopé, gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        latest = (InstagramPublishJob.objects
                  .filter(company=company, quota_total__isnull=False)
                  .order_by('-created_at')
                  .first())
        used = latest.quota_used if latest else None
        total = latest.quota_total if latest else None
        remaining = (
            max(total - used, 0)
            if (isinstance(used, int) and isinstance(total, int)) else None)
        return Response({'used': used, 'total': total, 'remaining': remaining})


class InstagramPublishView(APIView):
    """ADSDEEP55 — Propose la PUBLICATION d'un média Instagram (flux container).
    Réutilise ``services.propose_publish_ig``. Écriture ``adsengine_manage``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        from .services import propose_publish_ig
        data = request.data if isinstance(request.data, dict) else {}
        try:
            action = propose_publish_ig(
                company,
                media_type=data.get('media_type', ''),
                image_url=data.get('image_url', '') or '',
                video_url=data.get('video_url', '') or '',
                caption=data.get('caption', '') or '',
                alt_text=data.get('alt_text', '') or '',
                scheduled_at=data.get('scheduled_at'))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EngineActionSerializer(action).data, status=201)


class InstagramCommentListView(APIView):
    """ADSDEEP55 — Liste des commentaires Instagram miroités. ``?media_id=``
    filtre optionnellement sur un média. Company-scopé, gaté ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        qs = InstagramCommentMirror.objects.filter(company=company)
        media_id = request.query_params.get('media_id')
        if media_id:
            qs = qs.filter(media_meta_id=media_id)
        return Response(InstagramCommentMirrorSerializer(qs, many=True).data)


def _get_ig_comment_or_404(company, comment_id):
    return InstagramCommentMirror.objects.filter(
        company=company, pk=comment_id).first()


class InstagramCommentHideView(APIView):
    """ADSDEEP55 — Propose de masquer/démasquer un commentaire Instagram.
    Réutilise ``services.propose_hide_ig_comment``. Écriture
    ``adsengine_manage`` ; company-scopé."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, comment_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        comment = _get_ig_comment_or_404(company, comment_id)
        if comment is None:
            return Response({'detail': 'Commentaire introuvable.'}, status=404)
        from .services import propose_hide_ig_comment
        hidden = request.data.get('hidden', True)
        try:
            action = propose_hide_ig_comment(
                company, comment=comment, hidden=bool(hidden))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EngineActionSerializer(action).data, status=201)


class InstagramCommentReplyView(APIView):
    """ADSDEEP55 — Propose une réponse à un commentaire Instagram. Réutilise
    ``services.propose_reply_ig_comment``. Écriture ``adsengine_manage`` ;
    company-scopé."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, comment_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        comment = _get_ig_comment_or_404(company, comment_id)
        if comment is None:
            return Response({'detail': 'Commentaire introuvable.'}, status=404)
        from .services import propose_reply_ig_comment
        try:
            action = propose_reply_ig_comment(
                company, comment=comment,
                message=request.data.get('message', ''))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EngineActionSerializer(action).data, status=201)


class InstagramCommentDeleteView(APIView):
    """ADSDEEP55 — Propose la suppression d'un commentaire Instagram. Réutilise
    ``services.propose_delete_ig_comment``. Écriture ``adsengine_manage`` ;
    company-scopé."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, comment_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        comment = _get_ig_comment_or_404(company, comment_id)
        if comment is None:
            return Response({'detail': 'Commentaire introuvable.'}, status=404)
        from .services import propose_delete_ig_comment
        try:
            action = propose_delete_ig_comment(company, comment=comment)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EngineActionSerializer(action).data, status=201)


class InstagramMediaToggleCommentsView(APIView):
    """ADSDEEP55 — Propose de couper/rouvrir les commentaires d'un média IG
    (SEUL champ écrivable d'un média). Réutilise
    ``services.propose_toggle_ig_comments``. Écriture ``adsengine_manage`` ;
    company-scopé (média d'une autre société → 404).

    ``media_meta_id`` est l'ID Meta du média (``InstagramMediaMirror.meta_id``,
    tel que le front l'envoie — ``m.meta_id``), jamais la pk locale."""

    permission_classes = [HasPermissionOrLegacy('adsengine_manage')]

    def post(self, request, media_meta_id):
        company, err = _adseng_company_gate(request, 'adsengine_manage')
        if err is not None:
            return err
        media = InstagramMediaMirror.objects.filter(
            company=company, meta_id=media_meta_id).first()
        if media is None:
            return Response({'detail': 'Média introuvable.'}, status=404)
        from .services import propose_toggle_ig_comments
        enabled = request.data.get('enabled', True)
        try:
            action = propose_toggle_ig_comments(
                company, media=media, enabled=bool(enabled))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EngineActionSerializer(action).data, status=201)


# ── SIG4 — Console de signaux : vues MINCES sur les trois modules PURS
# (``health.py`` deux scores, ``signal_guards.py`` le quadrant, ``cohorts.py`` le
# filigrane de maturation). Elles AGRÈGENT les InsightSnapshot RÉELS de la société
# et les font passer par ces modules — c'est ce qui débranche les modules « morts »
# (aucun consommateur de prod avant SIG4). Un score/verdict de signal est
# AFFICHAGE/ALERTE SEULEMENT : il n'entre JAMAIS dans le bandit/l'allocation (§11),
# invariant tenu par ``test_health.py``/``test_signal_guards.py`` (le bandit
# n'importe pas ces modules ; ces vues, oui — c'est le câblage intentionnel).
#
# Constantes de RÉFÉRENCE de normalisation — révisées TRIMESTRIELLEMENT (même
# doctrine que ``signal_guards.py``), lues via ``getattr`` sur la config si un
# champ futur les porte, sinon la constante de module. AUCUNE migration ici.
SIGNAL_WINDOW_DAYS = 30            # fenêtre glissante d'agrégation des insights
SIGNAL_CTR_HEALTHY = 0.02         # CTR lien « sain » ≈ score créatif plein (1.0)
SIGNAL_CPL_HEALTHY_MAD = 100.0    # CPL de référence ≈ score opérations plein (1.0)

_SIGNAL_BAND_VERT = 0.66
_SIGNAL_BAND_ORANGE = 0.40

# Libellés FR (clé stable / label) des quatre garde-fous du quadrant (SIG2). La
# clé mappe le nom interne du garde-fou (``signal_guards``) vers la clé UI.
_GUARD_LABELS = {
    'frequency': ('frequence', 'Fréquence'),
    'quality_ranking': ('classement_qualite', 'Classement qualité'),
    'cpl': ('cpl', 'CPL'),
    'account_quality': ('qualite_compte', 'Qualité du compte'),
}


def _signal_clamp01(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))


def _signal_band(score):
    """Bande FR ``(cle, libelle)`` d'un score de santé 0..1 (affichage/alerte)."""
    if score >= _SIGNAL_BAND_VERT:
        return 'vert', 'Vert'
    if score >= _SIGNAL_BAND_ORANGE:
        return 'orange', 'Orange'
    return 'rouge', 'Rouge'


def _gather_signal_inputs(company, config):
    """Agrège les InsightSnapshot de CAMPAGNE de la société sur la fenêtre
    glissante et dérive les signaux NORMALISÉS 0..1 (1 = meilleur) consommés par
    ``health.py`` / ``signal_guards.py``, plus les nombres bruts et l'âge de
    cohorte (filigrane ``cohorts.py``). LECTURE SEULE, company-scopé — jamais une
    autre société."""
    import datetime

    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Avg, Sum
    from django.utils import timezone

    from . import cohorts as cohorts_mod
    from . import signal_guards
    from .models import InsightSnapshot as Snap

    today = timezone.now().date()
    start = today - datetime.timedelta(days=SIGNAL_WINDOW_DAYS)
    ct = ContentType.objects.get_for_model(AdCampaignMirror)
    qs = Snap.objects.filter(
        company=company, content_type=ct, date__gte=start)
    agg = qs.aggregate(
        spend=Sum('spend'), results=Sum('results'),
        impressions=Sum('impressions'), clicks=Sum('clicks'),
        freq=Avg('frequency'))
    spend = float(agg['spend'] or 0)
    results = int(agg['results'] or 0)
    impressions = int(agg['impressions'] or 0)
    clicks = int(agg['clicks'] or 0)
    avg_freq = float(agg['freq']) if agg['freq'] is not None else None

    ctr = (clicks / impressions) if impressions else None
    cpl = (spend / results) if results else None

    ctr_healthy = float(getattr(config, 'signal_ctr_healthy', None)
                        or SIGNAL_CTR_HEALTHY)
    cpl_healthy = float(getattr(config, 'signal_cpl_healthy_mad', None)
                        or SIGNAL_CPL_HEALTHY_MAD)
    freq_cap = float(getattr(config, 'frequency_cap', None)
                     or signal_guards.DEFAULT_FREQUENCY_CAP)

    # Normalisation (documentée) — chaque valeur reste DÉRIVÉE de données réelles.
    ctr_norm = _signal_clamp01(ctr / ctr_healthy) if ctr is not None else 0.0
    # Fraîcheur = proxy de fatigue inverse : fréquence 0 → 1.0, ≥ plafond → 0.0.
    freshness_norm = (
        _signal_clamp01((freq_cap - avg_freq) / freq_cap)
        if avg_freq is not None and freq_cap > 0 else 0.0)
    # CPL normalisé = INVERSE du coût (un CPL bas → proche de 1).
    cpl_norm = (_signal_clamp01(cpl_healthy / cpl)
                if cpl and cpl > 0 else 0.0)
    # Livraison = régularité de diffusion (part des jours de la fenêtre avec
    # dépense > 0) — mesure réelle, sans cible arbitraire.
    days_with_spend = (qs.filter(spend__gt=0)
                       .values('date').distinct().count())
    delivery_norm = _signal_clamp01(days_with_spend / float(SIGNAL_WINDOW_DAYS))

    # Âge de cohorte = ancienneté (jours) du plus VIEIL insight de la fenêtre
    # (via ``cohorts.cohort_age_days``) — filigrane de maturation + garde-fou CPL.
    oldest = qs.order_by('date').values_list('date', flat=True).first()
    cohort_age = cohorts_mod.cohort_age_days(oldest, today) if oldest else 0

    return {
        'creative_signals': {'ctr': ctr_norm, 'freshness': freshness_norm},
        'ops_signals': {'cpl': cpl_norm, 'delivery': delivery_norm},
        'guard_signals': {
            'frequency': avg_freq,
            'cpl': cpl,
            'cpl_target': cpl_healthy,
            'cohort_age_days': cohort_age,
            'impressions': impressions,
            # Non synchronisés dans l'InsightSnapshot aujourd'hui : rapportés
            # honnêtement (aucun garde-fou ne freine sur une absence de donnée).
            'quality_ranking': None,
            'account_quality_dropped': False,
        },
        'raw': {
            'ctr': ctr, 'cpl': cpl, 'frequency': avg_freq,
            'impressions': impressions, 'clicks': clicks, 'spend': spend,
            'results': results, 'delivery_ratio': delivery_norm,
            'cohort_age_days': cohort_age, 'window_days': SIGNAL_WINDOW_DAYS,
        },
    }


def _guardrail_quadrant(guard_signals, config):
    """Exécute les QUATRE garde-fous (``signal_guards.GUARDS``) — déclenchés OU
    non — et rend une ligne UI par garde-fou : ``{key, label, valeur, seuil,
    freine, statut_display, raison}``. Contrairement à ``evaluate_guards`` (qui ne
    rend QUE les déclenchés), le quadrant montre les quatre, même « OK »."""
    from . import signal_guards

    rows = []
    for guard in signal_guards.GUARDS:
        verdict = guard(guard_signals, config)
        key, label = _GUARD_LABELS.get(verdict.guard, (verdict.guard, verdict.guard))
        computed = verdict.computed or {}
        if verdict.guard == 'frequency':
            valeur, seuil = computed.get('frequency'), computed.get('cap')
        elif verdict.guard == 'cpl':
            target = computed.get('cpl_target')
            mult = computed.get('multiplier')
            valeur = computed.get('cpl')
            seuil = (float(target) * float(mult)
                     if target not in (None, 0) and mult else None)
        elif verdict.guard == 'quality_ranking':
            valeur, seuil = computed.get('quality_ranking'), 'below_average'
        else:  # account_quality
            valeur, seuil = computed.get('account_quality'), None
        if verdict.triggered:
            statut_display = 'Freine'
        elif valeur is None:
            statut_display = 'Indisponible'
        else:
            statut_display = 'OK'
        rows.append({
            'key': key,
            'label': label,
            'valeur': (float(valeur)
                       if isinstance(valeur, (int, float)) else valeur),
            'seuil': (float(seuil)
                      if isinstance(seuil, (int, float)) else seuil),
            'freine': bool(verdict.triggered),
            'statut_display': statut_display,
            'raison': verdict.reason or '',
        })
    return rows


class SignalsView(APIView):
    """SIG4 — Deux scores de santé (créatif/opérations) + quadrant de garde-fous
    durs, sur données RÉELLES de la société. ``GET /adsengine/signaux/`` —
    company-scopé, gaté ``adsengine_view``. LECTURE SEULE. Vue mince sur
    ``health.py`` (scores) + ``signal_guards.py`` (quadrant)."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from . import health

        config = GuardrailConfig.objects.filter(company=company).first()
        data = _gather_signal_inputs(company, config)
        creatif = health.creative_health(data['creative_signals'], config)
        operations = health.operations_health(data['ops_signals'], config)
        band_c = _signal_band(creatif)
        band_o = _signal_band(operations)
        return Response({
            'creatif': {
                'score': round(creatif, 4),
                'bande': band_c[0], 'bande_display': band_c[1],
            },
            'operations': {
                'score': round(operations, 4),
                'bande': band_o[0], 'bande_display': band_o[1],
            },
            'guardrails': _guardrail_quadrant(data['guard_signals'], config),
            'fenetre_jours': SIGNAL_WINDOW_DAYS,
        })


# Filigrane de maturation par groupe de signal (SIG3/``cohorts.py``) : chaque
# ligne = une fenêtre de maturation RÉELLE (``cohorts.MATURATION_DAYS``) + la
# valeur normalisée du signal correspondant, évaluée contre l'âge réel des
# données. ``value_key`` pointe la valeur normalisée dans le dict agrégé.
_COHORT_DRILL = {
    'creatif': [
        ('ctr', 'CTR — proxy immédiat', 'creative_signals', 'ctr'),
        ('ctwa_conversations', 'Conversations 7j', 'ops_signals', 'delivery'),
    ],
    'operations': [
        ('cpl', 'CPL 14-28j', 'ops_signals', 'cpl'),
        ('signature', 'Signature 60-90j', None, None),
    ],
}


class SignalCohortView(APIView):
    """SIG4/SIG3 — Drill-down par cohorte d'un signal (``?signal=creatif`` ou
    ``operations``) : le filigrane de maturation (``cohorts.py``) évalué contre
    l'âge RÉEL des données de la société. ``GET /adsengine/signaux/cohorte/`` —
    company-scopé, gaté ``adsengine_view``. LECTURE SEULE."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from . import cohorts as cohorts_mod

        signal = (request.query_params.get('signal') or 'creatif').strip()
        windows = _COHORT_DRILL.get(signal)
        if windows is None:
            return Response({'detail': 'Signal inconnu.'}, status=400)
        config = GuardrailConfig.objects.filter(company=company).first()
        data = _gather_signal_inputs(company, config)
        age = int(data['raw']['cohort_age_days'])

        rows = []
        for idx, (signal_key, fenetre, group, value_key) in enumerate(windows, 1):
            maturation = cohorts_mod.maturation_of(signal_key)
            mature = cohorts_mod.is_mature(signal_key, age)
            if mature:
                maturite_display = 'Mûr'
            elif maturation != cohorts_mod.UNKNOWN_MATURATION_DAYS \
                    and age >= float(maturation) / 2.0:
                maturite_display = 'En maturation'
            else:
                maturite_display = 'Précoce'
            valeur = (data[group][value_key]
                      if group is not None else None)
            rows.append({
                'id': idx,
                'fenetre': fenetre,
                'valeur': (round(float(valeur), 4) if valeur is not None
                           else None),
                'maturite_display': maturite_display,
                'mure': bool(mature),
                'maturation_jours': (None
                                     if maturation == cohorts_mod.UNKNOWN_MATURATION_DAYS
                                     else int(maturation)),
            })
        return Response(rows)
