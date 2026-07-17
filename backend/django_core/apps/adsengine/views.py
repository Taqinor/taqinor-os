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

from authentication.permissions import HasPermissionOrLegacy
from core.permissions import _user_has_or_legacy
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    AdCampaignMirror, AnomalyEvent, ArmDailyStat, CreativeAsset,
    CreativeBacklogItem, CreativeGenerationBatch, CreativePolicy, DecisionLog,
    EngineAction, EngineAlert, Experiment, ExperimentArm, FlightPhase,
    FlightPlan, GuardrailConfig, MetaConnection, PacingState,
    ReconciliationSnapshot, RulePolicy, WeeklyBrief,
)
from .serializers import (
    AdCampaignMirrorSerializer, AnomalyEventSerializer, ArmDailyStatSerializer,
    CreativeAssetSerializer, CreativeBacklogItemSerializer,
    CreativeGenerationBatchSerializer, CreativePolicySerializer,
    DecisionLogSerializer, EngineActionSerializer, EngineAlertSerializer,
    ExperimentArmSerializer, ExperimentSerializer, FlightPhaseSerializer,
    FlightPlanSerializer, GuardrailConfigSerializer, MetaConnectionSerializer,
    PacingStateSerializer, ReconciliationSnapshotSerializer,
    RulePolicySerializer,
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

        # ADSENG17 — santé du Gardien : heartbeat de l'évaluateur de règles
        # (le watchdog détecte un beat/worker Celery arrêté). Aucun secret.
        from .watchdog import health as guardian_health

        # ADSDEEP5 — % d'usage rate-limit Meta observé sur la dernière réponse
        # (backoff préventif avant le 613). None si aucune synchro récente.
        from .meta_client import rate_limit_status
        rate_limit = rate_limit_status(conn.ad_account_id) if conn else None

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

    @action(detail=False, methods=['get'], url_path='history',
            permission_classes=[HasPermissionOrLegacy('adsengine_view')])
    def history(self, request):
        """ENG43 — Historique des alertes (passées/résolues incluses) pour
        l'écran Règles & anomalies. Company-scopé (queryset hérité) ; lecture
        ``adsengine_view``. Même sérialiseur (aucun secret exposé)."""
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)


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
        return Response({'statuses': statuses})


class GuardrailSingletonView(APIView):
    """ENG3/ENG22 — Garde-fous d'UNE société vus comme un singleton (GET/PATCH
    sans id). Mappe les libellés d'écran (``max_daily_budget_mad`` /
    ``max_monthly_budget_mad``) sur les champs modèle
    (``daily_budget_ceiling_mad`` / ``monthly_budget_ceiling_mad``). Company-
    scopé ; lecture ``adsengine_view`` / écriture ``adsengine_manage``."""

    permission_classes = [IsAuthenticated]  # affiné par get_permissions

    def get_permissions(self):
        _w = self.request.method in ('POST', 'PATCH', 'PUT', 'DELETE')
        return [HasPermissionOrLegacy('adsengine_manage' if _w else 'adsengine_view')()]

    @staticmethod
    def _payload(cfg):
        return {
            'max_daily_budget_mad': cfg.daily_budget_ceiling_mad,
            'max_monthly_budget_mad': cfg.monthly_budget_ceiling_mad,
            # Aucun champ de stockage pour la bande d'approbation (aucune
            # migration ajoutée) : exposée None. GAP documenté.
            'require_approval_above_mad': None,
        }

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
        mapping = {
            'max_daily_budget_mad': 'daily_budget_ceiling_mad',
            'max_monthly_budget_mad': 'monthly_budget_ceiling_mad',
        }
        changed = []
        for src, field in mapping.items():
            if src in data and data[src] not in (None, ''):
                try:
                    setattr(cfg, field, int(float(data[src])))
                except (TypeError, ValueError):
                    return Response(
                        {'detail': f'Valeur invalide pour {src}.'}, status=400)
                changed.append(field)
        if changed:
            cfg.save(update_fields=changed + ['updated_at'])
        return Response(self._payload(cfg))


# ── ENG10/ENG23 — Dashboard « un chiffre » + drill-down leads + pacing ────────
class MetricsDashboardView(APIView):
    """ENG23 — Chiffres du dashboard : coût-par-signature (héro), dépense totale,
    CPL global, fréquence moyenne. Agrégats LECTURE SEULE sur les
    ``InsightSnapshot`` de campagne + ``metrics.cost_per_signature_summary``.
    Lecture ``adsengine_view``."""

    permission_classes = [HasPermissionOrLegacy('adsengine_view')]

    def get(self, request):
        company, err = _adseng_company_gate(request, 'adsengine_view')
        if err is not None:
            return err
        from decimal import Decimal

        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Avg, Sum

        from .metrics import cost_per_signature_summary
        from .models import InsightSnapshot as Snap

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
        agg = (Snap.objects
               .filter(company=company, content_type=ct)
               .aggregate(spend=Sum('spend'), results=Sum('results'),
                          freq=Avg('frequency')))
        spend = agg['spend'] or Decimal('0')
        results = agg['results'] or 0
        cpl = (spend / results) if results else None
        # Devise du compte Meta (les montants dépense/CPL/coût-par-signature sont
        # dans CETTE devise, pas forcément en MAD). 'MAD' en repli tant que la
        # synchro ne l'a pas lue.
        conn = MetaConnection.objects.filter(company=company).first()
        currency = (conn.currency if conn else '') or 'MAD'
        return Response({
            'cost_per_signature': cps,
            'signatures': signatures,
            'signatures_source': signatures_source,
            'currency': currency,
            'spend': str(spend),
            'cpl': (str(cpl) if cpl is not None else None),
            'frequency': (str(agg['freq']) if agg['freq'] is not None else None),
        })


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
    (jamais créés via l'API — ``create`` renvoie 405). Company-scopé (hérité)."""

    queryset = AdCampaignMirror.objects.all()
    serializer_class = AdCampaignMirrorSerializer
    http_method_names = ['get', 'post', 'head', 'options']

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
