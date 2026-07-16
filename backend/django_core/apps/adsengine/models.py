"""Modèles du moteur publicitaire Meta Ads (Groupe ENG).

ENG1 pose l'app satellite SANS modèle (le scaffold). Les modèles atterrissent
dans les tâches suivantes de la lane ``backend/adsengine`` :

  * ENG2 — ``MetaConnection`` (connexion Meta par société, credentials
    write-only) ;
  * ENG3 — ``GuardrailConfig`` (garde-fous par société ; l'activation d'une
    campagne n'est JAMAIS un champ — interdite en dur au niveau service) ;
  * ENG5 — miroirs ``AdCampaignMirror`` / ``AdSetMirror`` / ``AdMirror`` +
    ``InsightSnapshot`` ;
  * ENG7 — ``EngineAction`` (colonne vertébrale propose→approuve→applique).

Tout nouveau modèle métier hérite de ``core.models.TenantModel`` (FK société +
horodatage) et les ViewSets de ``core.viewsets.CompanyScopedModelViewSet``.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models

from core.models import TenantModel


class MetaConnection(TenantModel):
    """ENG2 — Connexion Meta (Marketing API) d'UNE société.

    Une société ↔ une connexion (``OneToOne``). ``credentials`` est un JSON
    write-only en API (jamais relu côté client) : il porte le **token System-User
    long-lived** (``{"access_token": "…"}``) — JAMAIS un token de session
    navigateur, qui expire vite et ne convient pas à un service serveur. Tant que
    ``enabled`` est faux ou que le token manque, tout le moteur no-ope.

    Hérite de ``TenantModel`` (socle multi-tenant) mais REdéclare ``company`` en
    ``OneToOneField`` (une connexion par société) — motif ARC1 documenté de
    redéclaration légitime du champ hérité.
    """

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='adsengine_meta_connection',
        verbose_name='Société',
    )
    enabled = models.BooleanField(
        default=False, verbose_name='Connexion activée')
    ad_account_id = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='ID compte publicitaire')
    page_id = models.CharField(
        max_length=64, blank=True, default='', verbose_name='ID Page')
    pixel_id = models.CharField(
        max_length=64, blank=True, default='', verbose_name='ID Pixel')
    # JSON par société (token System-User long-lived…). Write-only en API : le
    # sérialiseur ne le relit JAMAIS ; un GET n'expose que sa PRÉSENCE.
    credentials = models.JSONField(
        default=dict, blank=True, verbose_name='Identifiants (write-only)')

    class Meta:
        verbose_name = 'Connexion Meta'
        verbose_name_plural = 'Connexions Meta'
        ordering = ['-created_at']

    def __str__(self):
        return f'MetaConnection <{self.ad_account_id or "?"}>'

    @property
    def has_token(self):
        """Vrai si un token exploitable est présent (jamais expose sa valeur)."""
        return bool(self.credentials and self.credentials.get('access_token'))

    @property
    def is_live(self):
        """Vrai si la connexion peut réellement appeler Meta : activée + token."""
        return bool(self.enabled and self.has_token)


class GuardrailConfig(TenantModel):
    """ENG3 — Garde-fous publicitaires d'UNE société (``OneToOne``).

    Plafonds & fenêtres réglables PAR société. L'**activation d'une campagne
    n'est délibérément PAS un champ ici** : elle est interdite en dur au niveau
    service (``guardrails.enforce`` lève TOUJOURS sur une transition ACTIVE,
    quelle que soit la config) — extension permanente de la règle #3. Aucun
    réglage ne peut donc jamais autoriser une activation automatique.
    """

    company = models.OneToOneField(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='adsengine_guardrail_config',
        verbose_name='Société',
    )
    # Plafond de dépense quotidienne (MAD entiers — seuil de garde-fou, pas un
    # montant comptable). ENG9 compare la dépense des miroirs à ce plafond.
    daily_budget_ceiling_mad = models.PositiveIntegerField(
        default=100, verbose_name='Plafond budget quotidien (MAD)')
    # Variation hebdomadaire maximale d'un budget (en %), dans les deux sens.
    weekly_change_pct_max = models.PositiveIntegerField(
        default=20, verbose_name='Variation hebdomadaire max (%)')
    # Fenêtre (heures) d'observation « dépense > 0 et 0 lead » → anomalie (ENG9).
    anomaly_window_hours = models.PositiveIntegerField(
        default=48, verbose_name="Fenêtre de détection d'anomalie (heures)")

    # ── ENG8 — Toggles de capacités PAR société (motif HubSpot Breeze : « par
    # capacité, pas un interrupteur global »). Défaut False : rien ne s'auto-
    # applique tant que la société n'active pas explicitement la capacité. Un
    # ``kind`` couvert par une capacité activée saute l'approbation humaine, mais
    # une ligne ``EngineAction auto=True`` est TOUJOURS écrite (trace d'audit) et
    # l'exécution est journalisée. Ces toggles ne peuvent JAMAIS autoriser une
    # activation de campagne (interdite en dur, invariant permanent).
    auto_rotate_creative = models.BooleanField(
        default=False, verbose_name='Auto — rotation créative (ENG8)')
    auto_rebalance_within_band = models.BooleanField(
        default=False,
        verbose_name='Auto — rééquilibrage dans la bande (ENG8)')

    class Meta:
        verbose_name = 'Garde-fous publicitaires'
        verbose_name_plural = 'Garde-fous publicitaires'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'Garde-fous <plafond {self.daily_budget_ceiling_mad} MAD/j, '
            f'±{self.weekly_change_pct_max}%>'
        )


class AdCampaignMirror(TenantModel):
    """ENG5 — Miroir local d'une campagne Meta.

    Reflet en LECTURE de l'état côté Meta (le ``status`` peut donc valoir
    ``ACTIVE`` si Meta le montre ainsi — le miroir rapporte la réalité ; c'est le
    service qui, lui, n'active jamais). ``created_via_engine`` distingue une
    campagne créée par le moteur (toujours née PAUSED) d'une campagne découverte
    lors d'une synchro. Upsert idempotent par ``(company, meta_id)``.
    """

    meta_id = models.CharField(max_length=64, verbose_name='ID Meta')
    name = models.CharField(max_length=255, blank=True, default='',
                            verbose_name='Nom')
    status = models.CharField(max_length=32, blank=True, default='',
                              verbose_name='Statut Meta')
    objective = models.CharField(max_length=64, blank=True, default='',
                                 verbose_name='Objectif')
    budget = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Budget (unités mineures Meta)')
    created_via_engine = models.BooleanField(
        default=False, verbose_name='Créée par le moteur')

    class Meta:
        verbose_name = 'Miroir de campagne'
        verbose_name_plural = 'Miroirs de campagne'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'meta_id'],
                name='uniq_adsengine_campaign_meta'),
        ]

    def __str__(self):
        return f'Campagne {self.meta_id} ({self.status or "?"})'


class AdSetMirror(TenantModel):
    """ENG5 — Miroir local d'un ad set Meta (rattaché à un miroir de campagne)."""

    meta_id = models.CharField(max_length=64, verbose_name='ID Meta')
    name = models.CharField(max_length=255, blank=True, default='',
                            verbose_name='Nom')
    status = models.CharField(max_length=32, blank=True, default='',
                              verbose_name='Statut Meta')
    budget = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Budget (unités mineures Meta)')
    created_via_engine = models.BooleanField(
        default=False, verbose_name='Créé par le moteur')
    # FK MÊME APP (adsengine) — autorisée. Nullable : un ad set peut être
    # synchronisé avant que son miroir de campagne parent existe.
    campaign = models.ForeignKey(
        'adsengine.AdCampaignMirror', on_delete=models.CASCADE,
        null=True, blank=True, related_name='adsets',
        verbose_name='Campagne')

    class Meta:
        verbose_name = "Miroir d'ad set"
        verbose_name_plural = "Miroirs d'ad set"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'meta_id'],
                name='uniq_adsengine_adset_meta'),
        ]

    def __str__(self):
        return f'AdSet {self.meta_id} ({self.status or "?"})'


class AdMirror(TenantModel):
    """ENG5 — Miroir local d'une ad Meta (rattachée à un miroir d'ad set)."""

    meta_id = models.CharField(max_length=64, verbose_name='ID Meta')
    name = models.CharField(max_length=255, blank=True, default='',
                            verbose_name='Nom')
    status = models.CharField(max_length=32, blank=True, default='',
                              verbose_name='Statut Meta')
    created_via_engine = models.BooleanField(
        default=False, verbose_name='Créée par le moteur')
    adset = models.ForeignKey(
        'adsengine.AdSetMirror', on_delete=models.CASCADE,
        null=True, blank=True, related_name='ads',
        verbose_name='Ad set')

    class Meta:
        verbose_name = "Miroir d'ad"
        verbose_name_plural = "Miroirs d'ad"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'meta_id'],
                name='uniq_adsengine_ad_meta'),
        ]

    def __str__(self):
        return f'Ad {self.meta_id} ({self.status or "?"})'


class InsightSnapshot(TenantModel):
    """ENG5 — Instantané de performance daté d'un objet publicitaire.

    Rattaché par FK générique (``contenttypes``) à N'IMPORTE quel miroir
    (campagne / ad set / ad). Upsert idempotent par
    ``(company, content_type, object_id, date)``.
    """

    content_type = models.ForeignKey(
        'contenttypes.ContentType', on_delete=models.CASCADE,
        verbose_name='Type de cible')
    object_id = models.PositiveIntegerField(verbose_name='ID cible')
    content_object = GenericForeignKey('content_type', 'object_id')
    date = models.DateField(verbose_name='Date')
    spend = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Dépense')
    results = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Résultats')
    frequency = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Fréquence')
    cpl = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Coût par lead')

    class Meta:
        verbose_name = 'Instantané de performance'
        verbose_name_plural = 'Instantanés de performance'
        ordering = ['-date', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'content_type', 'object_id', 'date'],
                name='uniq_adsengine_insight_snap'),
        ]
        indexes = [
            models.Index(
                fields=['content_type', 'object_id'],
                name='adseng_insight_ct_obj_idx'),
        ]

    def __str__(self):
        return f'Insight {self.object_id}@{self.date}'


class EngineAction(TenantModel):
    """ENG7 — Colonne vertébrale propose→approuve→applique du moteur.

    Chaque changement que le moteur veut opérer sur Meta est d'abord PROPOSÉ
    (avec une ``reason_fr`` obligatoire — une phrase en français), puis APPROUVÉ
    par un humain habilité, et seulement alors APPLIQUÉ via ``meta_client``
    (jamais autrement). Le pattern suit ``contrats.EtapeApprobation`` (statut
    LOCAL persistant + acteur serveur), PAS le registre stateless ``apps/agent``.

    **Jamais d'auto-apply** hors des toggles de capacités (ENG8) ; et même dans ce
    cas, une ligne ``EngineAction`` avec ``auto=True`` est TOUJOURS écrite (trace
    d'audit). ``approved_by`` / ``applied_at`` sont posés côté serveur.
    """

    class Statut(models.TextChoices):
        PROPOSEE = 'proposee', 'Proposée'
        APPROUVEE = 'approuvee', 'Approuvée'
        REJETEE = 'rejetee', 'Rejetée'
        APPLIQUEE = 'appliquee', 'Appliquée'
        ECHOUEE = 'echouee', 'Échouée'

    class Kind(models.TextChoices):
        CREATE_CAMPAIGN = 'create_campaign', 'Créer une campagne'
        CREATE_ADSET = 'create_adset', 'Créer un ad set'
        CREATE_AD = 'create_ad', 'Créer une ad'
        # ENG8 — kinds couverts par les toggles de capacités (auto-apply possible
        # si la capacité est activée sur la GuardrailConfig de la société).
        ROTATE_CREATIVE = 'rotate_creative', 'Roter le créatif'
        REBALANCE_BUDGET = 'rebalance_budget', 'Rééquilibrer le budget'
        # ENG9 — mise en pause (proposée par le détecteur d'anomalie). Pauser
        # n'active JAMAIS rien : c'est l'action de sécurité par excellence. La
        # cible (campaign/adset/ad + meta_id) vit dans ``payload``.
        PAUSE = 'pause', 'Mettre en pause'

    kind = models.CharField(
        max_length=32, choices=Kind.choices, verbose_name='Type')
    payload = models.JSONField(
        default=dict, blank=True, verbose_name='Charge utile')
    # Raison OBLIGATOIRE (une phrase FR). Requise au niveau service + serializer,
    # et garantie non vide en base (contrainte CHECK ``adseng_action_reason_req``).
    reason_fr = models.TextField(verbose_name='Raison (une phrase FR)')
    status = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.PROPOSEE,
        verbose_name='Statut')
    # Écrite même en auto-apply (ENG8) : une action jouée sans approbation humaine
    # laisse quand même une trace ``auto=True``. Défaut False (approbation requise).
    auto = models.BooleanField(
        default=False, verbose_name='Jouée automatiquement (ENG8)')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='adsengine_actions_approuvees',
        verbose_name='Approuvée / décidée par')
    applied_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Appliquée le')
    result = models.JSONField(
        default=dict, blank=True, verbose_name='Résultat')
    error = models.TextField(
        blank=True, default='', verbose_name='Erreur')

    class Meta:
        verbose_name = 'Action du moteur'
        verbose_name_plural = 'Actions du moteur'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(reason_fr=''),
                name='adseng_action_reason_req'),
        ]

    def __str__(self):
        return f'{self.get_kind_display()} — {self.get_status_display()}'


class WeeklyBrief(TenantModel):
    """ENG11 — Brief hebdomadaire déterministe (v1, SANS LLM).

    Un instantané hebdomadaire, PAR société, des chiffres RÉELS (dépense, CPL,
    coût-par-signature, fréquence vs seuil de fatigue, conformité SLA) rendu en
    phrases template FR — **jamais de texte généré par un LLM en v1** (motif
    anti-hallucination : c'est exactement le commentaire que les utilisateurs
    éteignent). ``data`` porte les chiffres (JSON) ; ``markdown`` le rendu FR ;
    ``propositions`` (dans ``data``) relie 0-3 ``EngineAction`` proposées.

    Idempotent : une (re)génération pour la même semaine met à jour la ligne
    existante (unique par ``(company, period_start)``), jamais de doublon.
    """

    period_start = models.DateField(verbose_name='Début de période')
    period_end = models.DateField(verbose_name='Fin de période')
    data = models.JSONField(
        default=dict, blank=True, verbose_name='Chiffres (JSON)')
    markdown = models.TextField(
        blank=True, default='', verbose_name='Rendu markdown (FR)')

    class Meta:
        verbose_name = 'Brief hebdomadaire'
        verbose_name_plural = 'Briefs hebdomadaires'
        ordering = ['-period_start', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'period_start'],
                name='uniq_adsengine_weekly_brief'),
        ]

    def __str__(self):
        return f'Brief {self.period_start} → {self.period_end}'


class EngineAlert(TenantModel):
    """ENG13 — Alerte moteur (WhatsApp-first) : violation / anomalie / inopérante.

    Matérialise une alerte émise par le moteur de garde-fous (ENG9) : une
    violation de garde-fou, une anomalie détectée, ou une règle INOPÉRANTE (qui
    n'a pas pu tourner — leçon Madgicx : jamais un échec silencieux). Le rendu FR
    court + le deep-link ``wa.me`` vivent dans ``alerts.py`` (l'ENVOI réel via
    template WhatsApp BSP est gated/plus tard — ici on ne fait que rendre + lister).

    ``action`` relie optionnellement l'alerte à la proposition ``EngineAction``
    qui l'accompagne (ex. l'anomalie propose une pause).

    Les valeurs d'``alert_type`` sont alignées sur ``guardrails.ALERT_*``.
    """

    class Type(models.TextChoices):
        ANOMALIE = 'anomalie', 'Anomalie'
        GARDE_FOU = 'garde_fou', 'Violation de garde-fou'
        REGLE_INOPERANTE = 'regle_inoperante', 'Règle inopérante'

    alert_type = models.CharField(
        max_length=20, choices=Type.choices, verbose_name="Type d'alerte")
    message = models.TextField(verbose_name='Message (FR)')
    action = models.ForeignKey(
        'adsengine.EngineAction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alerts',
        verbose_name='Action liée')
    detail = models.JSONField(
        default=dict, blank=True, verbose_name='Détail')
    acknowledged = models.BooleanField(
        default=False, verbose_name='Acquittée')

    class Meta:
        verbose_name = 'Alerte moteur'
        verbose_name_plural = 'Alertes moteur'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'acknowledged'],
                         name='adseng_alert_co_ack_idx'),
        ]

    def __str__(self):
        return f'[{self.get_alert_type_display()}] {self.message[:40]}'


class CreativeAsset(TenantModel):
    """ENG15 — Asset créatif (reel / static / explainer) stocké dans MinIO.

    ``file_key`` porte la clé de l'objet MinIO (jamais un ``FileField`` — clé
    préfixée société, pattern SCA42). ``policy_stamp`` porte la trace de la
    check-list policy (ENG16) : ``{passed, rules_checked[], checked_at,
    checked_by}``. ``perf`` remonte les chiffres d'insights (impressions/spend/
    résultats). ``parent`` relie une variante (ENG18) à son asset de base.

    RÈGLE DURE (testée) : un asset dont ``policy_stamp.passed`` n'est pas vrai NE
    PEUT PAS être référencé par une ``EngineAction`` de création d'ad — le
    contrôle vit dans ``services`` (``assert_creative_ok_for_ad``). Un asset non
    validé ne part donc jamais en production.
    """

    class AssetType(models.TextChoices):
        REEL = 'reel', 'Reel (vidéo verticale)'
        STATIC = 'static', 'Statique (image)'
        EXPLAINER = 'explainer', 'Explainer animé'

    asset_type = models.CharField(
        max_length=12, choices=AssetType.choices, verbose_name='Type')
    file_key = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Clé MinIO')
    source_lane = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name='Lane source',
        help_text="Origine (upload / fal / templated / zapcap / …).")
    cost_cents = models.PositiveIntegerField(
        default=0, verbose_name='Coût de production (centimes)')
    policy_stamp = models.JSONField(
        default=dict, blank=True,
        verbose_name='Tampon policy (check-list)')
    perf = models.JSONField(
        default=dict, blank=True,
        verbose_name='Performance (remontée des insights)')
    parent = models.ForeignKey(
        'adsengine.CreativeAsset', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='variants',
        verbose_name='Asset parent (variante)')

    class Meta:
        verbose_name = 'Asset créatif'
        verbose_name_plural = 'Assets créatifs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_asset_type_display()} #{self.pk}'

    @property
    def is_policy_passed(self):
        """Vrai si la check-list policy est explicitement passée (ENG16)."""
        return bool((self.policy_stamp or {}).get('passed') is True)


class CreativePolicy(TenantModel):
    """ENG16 — Policy créative PAR société (une par société, ``OneToOne``).

    Deux listes de règles (interdits / permis). Le contrôle est une CHECK-LIST
    DÉTERMINISTE que l'humain confirme règle par règle dans l'UI : **le système
    ENREGISTRE la confirmation, il n'« évalue » jamais seul** le créatif (pas de
    jugement automatique du contenu). ``policy.py`` porte les défauts + la
    logique de check ; ``seed_adsengine`` seed la policy par défaut.

    Défaut (seedé) : JAMAIS de faux chantiers / faux clients / faux témoignages
    ni de chiffre non vérifié ; explainers animés / B-roll abstrait / rendus
    produit OK. Chaque tenant peut définir sa propre policy.
    """

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='adsengine_creative_policy', verbose_name='Société')
    forbidden_rules = models.JSONField(
        default=list, blank=True, verbose_name='Règles interdites')
    allowed_rules = models.JSONField(
        default=list, blank=True, verbose_name='Règles permises')

    class Meta:
        verbose_name = 'Policy créative'
        verbose_name_plural = 'Policies créatives'
        ordering = ['-created_at']

    def __str__(self):
        return f'Policy créative société {self.company_id}'
