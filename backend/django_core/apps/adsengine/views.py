"""Vues du moteur publicitaire Meta Ads (Groupe ENG).

ENG1 n'expose qu'un endpoint de liveness ``status/`` (``{ok: true}``) — les
ViewSets métier (connexion, garde-fous, actions) atterrissent aux tâches
suivantes de la lane et sont tous basés sur
``core.viewsets.CompanyScopedModelViewSet`` (scoping société garanti).
"""
import os

from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import _user_has_or_legacy
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    AnomalyEvent, ArmDailyStat, CreativeAsset, CreativeBacklogItem,
    CreativeGenerationBatch, CreativePolicy, DecisionLog, EngineAction,
    EngineAlert, Experiment, ExperimentArm, FlightPhase, FlightPlan,
    GuardrailConfig, MetaConnection, PacingState, ReconciliationSnapshot,
    RulePolicy,
)
from .serializers import (
    AnomalyEventSerializer, ArmDailyStatSerializer, CreativeAssetSerializer,
    CreativeBacklogItemSerializer, CreativeGenerationBatchSerializer,
    CreativePolicySerializer, DecisionLogSerializer, EngineActionSerializer,
    EngineAlertSerializer, ExperimentArmSerializer, ExperimentSerializer,
    FlightPhaseSerializer, FlightPlanSerializer, GuardrailConfigSerializer,
    MetaConnectionSerializer, PacingStateSerializer,
    ReconciliationSnapshotSerializer, RulePolicySerializer,
)


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
)


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

        return Response({
            'keys': keys,
            'connection': connection,
            'last_successful_sync': (
                last_snap.isoformat() if last_snap else None),
            # Câblés par les groupes Meta Lead Ads / CAPI (gated) — non encore
            # disponibles : rapportés None honnêtement, jamais fabriqués.
            'last_lead_ads_webhook': None,
            'last_capi_event': None,
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


class EngineAlertViewSet(AdsengineViewSet):
    """ENG13 — Liste (lecture seule) des alertes moteur pour le dashboard.

    Company-scopé (hérité) + gaté ``adsengine_view``. Restreint à GET : les
    alertes sont créées par le moteur (ENG9), jamais par un client API.
    """

    queryset = EngineAlert.objects.all()
    serializer_class = EngineAlertSerializer
    http_method_names = ['get', 'head', 'options']


class CreativeAssetViewSet(AdsengineViewSet):
    """ENG15 — CRUD des assets créatifs + upload MinIO.

    Company-scopé (hérité) ; lecture ``adsengine_view`` / écriture
    ``adsengine_manage``. ``file_key`` / ``policy_stamp`` / ``perf`` sont posés
    côté serveur (upload / check-list ENG16 / insights), jamais par le client.
    """

    queryset = CreativeAsset.objects.all()
    serializer_class = CreativeAssetSerializer

    @action(detail=False, methods=['post'])
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

    @action(detail=False, methods=['get'])
    def checklist(self, request):
        """ENG16 — Renvoie la check-list policy à confirmer par l'humain."""
        from .policy import build_checklist
        company = getattr(request.user, 'company', None)
        return Response(build_checklist(company))

    @action(detail=True, methods=['post'], url_path='policy-check')
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


class CreativePolicyViewSet(AdsengineViewSet):
    """ENG16 — CRUD de la policy créative (une par société)."""

    queryset = CreativePolicy.objects.all()
    serializer_class = CreativePolicySerializer


class ExperimentViewSet(AdsengineViewSet):
    """ADSENG3 — CRUD des expériences (tests A/B/n). Company-scopé (hérité) ;
    lecture ``adsengine_view`` / écriture ``adsengine_manage``."""

    queryset = Experiment.objects.all()
    serializer_class = ExperimentSerializer


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

    # ADSENG14 — catalogue FIXE (lecture) : le front rend la liste des templates
    # (style STAGES.py) sans que le fondateur puisse en inventer un (pas de
    # builder libre). GET → permission de LECTURE (adsengine_view) héritée.
    @action(detail=False, methods=['get'])
    def catalogue(self, request):
        """Liste des templates du catalogue fixe (clé, libellé, sévérité,
        cadence, action par défaut, params éditables + défauts). Aucune donnée
        société — c'est de la métadonnée statique."""
        from . import rule_templates as rt
        items = [
            {
                'template_key': key,
                'label_fr': tpl['label_fr'],
                'severity': tpl['severity'],
                'cadence': tpl['cadence'],
                'scope': tpl['scope'],
                'actionable': rt.is_actionable(key),
                'action_kind': rt.action_kind(key),
                'editable_params': tpl['editable_params'],
                'default_params': tpl['default_params'],
            }
            for key, tpl in rt.RULE_TEMPLATES.items()
        ]
        return Response({'templates': items})

    # ADSENG14 — seed du catalogue fixe pour la société (idempotent). Chaque
    # règle naît OFF + dry-run (défaut sûr). POST → permission d'ÉCRITURE
    # (adsengine_manage) héritée du mapping méthode→permission.
    @action(detail=False, methods=['post'])
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


class AnomalyEventViewSet(AdsengineViewSet):
    """ADSENG4 — Liste (lecture seule) des anomalies détectées par le gardien."""

    queryset = AnomalyEvent.objects.all()
    serializer_class = AnomalyEventSerializer
    http_method_names = ['get', 'head', 'options']


class PacingStateViewSet(AdsengineViewSet):
    """ADSENG4 — Liste (lecture seule) des états de pacing mensuels."""

    queryset = PacingState.objects.all()
    serializer_class = PacingStateSerializer
    http_method_names = ['get', 'head', 'options']


class CreativeGenerationBatchViewSet(AdsengineViewSet):
    """ADSENG5 — CRUD des lots de génération créative + approbation par LOT.

    L'approbation est BATCH-level (jamais par variante) : une seule action
    approuve/rejette le lot entier. ``adsengine_manage`` gate l'écriture."""

    queryset = CreativeGenerationBatch.objects.all()
    serializer_class = CreativeGenerationBatchSerializer

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve le LOT ENTIER (acteur + horodatage posés côté serveur)."""
        from django.utils import timezone
        batch = self.get_object()
        batch.status = CreativeGenerationBatch.Statut.APPROUVEE
        batch.approved_by = request.user
        batch.approved_at = timezone.now()
        batch.save(update_fields=['status', 'approved_by', 'approved_at'])
        return Response(self.get_serializer(batch).data)

    @action(detail=True, methods=['post'])
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
    """

    queryset = EngineAction.objects.all()
    serializer_class = EngineActionSerializer

    _APPROVE_ACTIONS = ('approve', 'reject', 'apply')

    def get_permissions(self):
        if getattr(self, 'action', None) in self._APPROVE_ACTIONS:
            return [HasAdsengineApprove()]
        return super().get_permissions()

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

        from .services import CreativePolicyNotPassed, assert_creative_ok_for_ad
        company = self.request.user.company
        kind = serializer.validated_data.get('kind')
        payload = serializer.validated_data.get('payload') or {}
        try:
            assert_creative_ok_for_ad(company, kind, payload)
        except CreativePolicyNotPassed as exc:
            raise drf_serializers.ValidationError(
                {'creative_asset_id': str(exc)})
        super().perform_create(serializer)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approuve l'action (acteur posé côté serveur)."""
        from .services import approve_action
        instance = self.get_object()
        try:
            approve_action(instance, user=request.user)
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
