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

from .rules import RULE_TEMPLATE_CHOICES


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
    # Devise du compte publicitaire (ISO-4217, ex. « USD ») — Meta rapporte TOUS
    # les montants (dépense, budgets, insights) dans CETTE devise, pas en MAD.
    # Renseignée par la synchro (lecture du nœud de compte) ; '' tant qu'inconnue.
    currency = models.CharField(
        max_length=8, blank=True, default='',
        verbose_name='Devise du compte')
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

    # ── ADSENG4 — Trésorerie : enveloppe mensuelle + bande de pacing + plancher
    # d'exploration du bandit. Le plafond mensuel est nullable (si absent, dérivé
    # du plafond quotidien × jours du mois — dd-treasury A3). Le plancher
    # d'exploration (P1) garantit qu'un bras minoritaire continue de délivrer :
    # effectif = max(exploration_floor_mad, exploration_floor_pct % du budget).
    monthly_budget_ceiling_mad = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Plafond budget mensuel (MAD)')
    pacing_band_pct = models.PositiveIntegerField(
        default=15, verbose_name='Bande de pacing (%)')
    exploration_floor_mad = models.PositiveIntegerField(
        default=20, verbose_name="Plancher d'exploration (MAD/jour)")
    exploration_floor_pct = models.PositiveIntegerField(
        default=20, verbose_name="Plancher d'exploration (%)")

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

    # ADSENG4 — sévérité (🔴🟠🔵) : valeurs alignées sur ``rules.SEVERITY_*``.
    class Severity(models.TextChoices):
        CRITIQUE = 'critical', 'Urgent'
        ATTENTION = 'warning', 'Attention'
        INFO = 'info', 'Info'

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

    # ── ADSENG4 — sévérité + cooldown (dédup) + escalade ──
    severity = models.CharField(
        max_length=8, choices=Severity.choices, default=Severity.ATTENTION,
        verbose_name='Sévérité')
    # Clé d'entité pour la dédup PAR entité (ex. 'campaign:123' / 'ad:456').
    entity_key = models.CharField(
        max_length=80, blank=True, default='', verbose_name='Clé entité')
    # Fenêtre de dédup (heures). 0 = valeur par défaut de la sévérité.
    cooldown_hours = models.PositiveIntegerField(
        default=0, verbose_name='Cooldown (heures)')
    # Compteur de cycles NON résolus → escalade WARNING→CRITICAL au seuil.
    unresolved_cycles = models.PositiveIntegerField(
        default=0, verbose_name='Cycles non résolus')
    resolved = models.BooleanField(default=False, verbose_name='Résolue')

    class Meta:
        verbose_name = 'Alerte moteur'
        verbose_name_plural = 'Alertes moteur'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'acknowledged'],
                         name='adseng_alert_co_ack_idx'),
            models.Index(fields=['company', 'severity', 'entity_key'],
                         name='adseng_alert_sev_ent_idx'),
        ]

    def __str__(self):
        return f'[{self.get_alert_type_display()}] {self.message[:40]}'

    @property
    def effective_cooldown_hours(self):
        """Cooldown effectif : celui posé, sinon le défaut de la sévérité."""
        if self.cooldown_hours:
            return self.cooldown_hours
        from .rules import default_cooldown_hours
        return default_cooldown_hours(self.severity)

    def register_unresolved_cycle(self):
        """ADSENG4 — Un cycle de plus sans résolution : incrémente le compteur
        et ESCALADE une WARNING en CRITICAL au-delà du seuil (``rules.
        ESCALATION_THRESHOLD``). Idempotent au sens où une alerte résolue ne
        s'escalade jamais. Renvoie True si une escalade a eu lieu."""
        from .rules import ESCALATION_THRESHOLD, SEVERITY_CRITICAL, SEVERITY_WARNING
        if self.resolved:
            return False
        self.unresolved_cycles += 1
        escalated = False
        if (self.severity == SEVERITY_WARNING
                and self.unresolved_cycles >= ESCALATION_THRESHOLD):
            self.severity = SEVERITY_CRITICAL
            escalated = True
        self.save(update_fields=['unresolved_cycles', 'severity'])
        return escalated


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

    # ── ADSENG5 — Décomposition en COMPOSANTS (dd-creative-sci) ──
    # ``hook_id`` groupe tous les assets partageant la même accroche (à travers
    # les visuels) ; ``visual_asset_key`` la clé MinIO du visuel réutilisable.
    # Le texte (accroche/corps) + le CTA permettent la recombinaison
    # déterministe « hook gagnant × autres visuels » (jamais du contenu inventé).
    hook_id = models.CharField(
        max_length=64, blank=True, default='', verbose_name='ID accroche')
    hook_text = models.TextField(
        blank=True, default='', verbose_name='Texte accroche')
    primary_text = models.TextField(
        blank=True, default='', verbose_name='Texte principal')
    visual_asset_key = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Clé MinIO du visuel')
    cta = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name="Appel à l'action (CTA)")

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


class Experiment(TenantModel):
    """ADSENG3 — Une EXPÉRIENCE (test A/B/n) sur une campagne / un ad set.

    Teste UNE variable (le hook, le visuel, l'audience…) entre 2-4 bras
    (``ExperimentArm``). L'expérience ne CHANGE jamais Meta elle-même : elle sert
    de contenant déterministe pour la science (bandit P1) et le journal de
    décision (``DecisionLog``). Cible optionnelle (campagne/ad set miroir) — FK
    MÊME APP (adsengine), donc autorisée.
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_COURS = 'en_cours', 'En cours'
        EN_PAUSE = 'en_pause', 'En pause'
        TERMINEE = 'terminee', 'Terminée'

    class Variable(models.TextChoices):
        HOOK = 'hook', 'Accroche (hook)'
        VISUEL = 'visuel', 'Visuel'
        AUDIENCE = 'audience', 'Audience'
        PLACEMENT = 'placement', 'Placement'
        CTA = 'cta', "Appel à l'action (CTA)"
        AUTRE = 'autre', 'Autre'

    name = models.CharField(max_length=160, verbose_name='Nom')
    tested_variable = models.CharField(
        max_length=12, choices=Variable.choices, default=Variable.HOOK,
        verbose_name='Variable testée')
    status = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    # Cibles miroir (même app) — nullable : une expérience peut être planifiée
    # avant que ses campagnes/ad sets miroir existent.
    campaign = models.ForeignKey(
        'adsengine.AdCampaignMirror', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='experiments',
        verbose_name='Campagne cible')
    adset = models.ForeignKey(
        'adsengine.AdSetMirror', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='experiments',
        verbose_name='Ad set cible')
    start_date = models.DateField(
        null=True, blank=True, verbose_name='Début')
    end_date = models.DateField(
        null=True, blank=True, verbose_name='Fin')
    notes = models.TextField(blank=True, default='', verbose_name='Notes')

    class Meta:
        verbose_name = 'Expérience publicitaire'
        verbose_name_plural = 'Expériences publicitaires'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status'],
                         name='adseng_exp_co_status_idx'),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_status_display()})'


class ExperimentArm(TenantModel):
    """ADSENG3 — Un BRAS d'une expérience : un créatif candidat.

    Porte le ``creative_asset`` testé (FK même app), l'``ad_id`` du miroir Meta
    correspondant (clé de jointure vers ``AdMirror``/``InsightSnapshot``) et la
    LIGNÉE composants (``hook_id``/``visual_id``) — pour tracer d'où vient chaque
    variante (dd-creative-sci). Un bras peut être désactivé (``is_active=False``)
    quand il est « tué » par la science, sans le supprimer (trace).
    """

    experiment = models.ForeignKey(
        'adsengine.Experiment', on_delete=models.CASCADE,
        related_name='arms', verbose_name='Expérience')
    creative_asset = models.ForeignKey(
        'adsengine.CreativeAsset', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='experiment_arms',
        verbose_name='Asset créatif')
    label = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Libellé')
    # ID de l'ad miroir Meta (jointure vers AdMirror.meta_id / InsightSnapshot).
    ad_id = models.CharField(
        max_length=64, blank=True, default='', verbose_name='ID ad (Meta)')
    # Lignée composants (dd-creative-sci) — d'où vient la variante.
    hook_id = models.CharField(
        max_length=64, blank=True, default='', verbose_name='ID accroche')
    visual_id = models.CharField(
        max_length=64, blank=True, default='', verbose_name='ID visuel')
    is_active = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = "Bras d'expérience"
        verbose_name_plural = "Bras d'expérience"
        ordering = ['experiment', 'id']
        indexes = [
            models.Index(fields=['company', 'ad_id'],
                         name='adseng_arm_co_ad_idx'),
        ]

    def __str__(self):
        return self.label or f'Bras #{self.pk}'


class ArmDailyStat(TenantModel):
    """ADSENG3 — Statistiques QUOTIDIENNES d'un bras (alimentées par la sync).

    Une ligne par ``(bras, jour)`` — impressions, clics, conversations, dépense.
    Ce sont les DONNÉES du bandit (P1) : trials = impressions, successes =
    conversations. Upsert idempotent par ``(company, arm, date)`` via
    :meth:`upsert` (une re-synchro du même jour écrase, jamais de doublon).
    """

    arm = models.ForeignKey(
        'adsengine.ExperimentArm', on_delete=models.CASCADE,
        related_name='daily_stats', verbose_name='Bras')
    date = models.DateField(verbose_name='Date')
    impressions = models.PositiveIntegerField(
        default=0, verbose_name='Impressions')
    clicks = models.PositiveIntegerField(default=0, verbose_name='Clics')
    conversations = models.PositiveIntegerField(
        default=0, verbose_name='Conversations')
    spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Dépense')

    class Meta:
        verbose_name = 'Stat quotidienne de bras'
        verbose_name_plural = 'Stats quotidiennes de bras'
        ordering = ['-date', 'arm']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'arm', 'date'],
                name='uniq_adseng_arm_daily'),
        ]
        indexes = [
            models.Index(fields=['arm', 'date'],
                         name='adseng_armstat_arm_dt_idx'),
        ]

    def __str__(self):
        return f'Stat bras {self.arm_id} @ {self.date}'

    @classmethod
    def upsert(cls, *, arm, date, impressions=0, clicks=0,
               conversations=0, spend=0):
        """Upsert idempotent d'une ligne quotidienne (la synchro est la source
        de vérité : les valeurs Meta ÉCRASENT, jamais d'accumulation). Company
        toujours dérivée du bras (jamais reçue de l'extérieur). Renvoie
        ``(stat, created)``."""
        return cls.objects.update_or_create(
            company=arm.company, arm=arm, date=date,
            defaults={
                'impressions': impressions, 'clicks': clicks,
                'conversations': conversations, 'spend': spend,
            })


class DecisionLog(TenantModel):
    """ADSENG3 — Journal d'une DÉCISION de la science (auditabilité totale).

    Chaque cycle du moteur de décision (bandit + garde-fous, P1) écrit ici un
    instantané REJOUABLE : les ``inputs`` (stats des bras au moment T), les
    ``posteriors`` calculés, l'``allocations`` produite, et l'``action`` proposée
    (FK ``EngineAction`` nullable — même app). Jamais d'auto-apply implicite : la
    décision est tracée, l'application reste la boucle propose→approuve (ENG7).
    """

    experiment = models.ForeignKey(
        'adsengine.Experiment', on_delete=models.CASCADE,
        related_name='decisions', verbose_name='Expérience')
    inputs = models.JSONField(
        default=dict, blank=True, verbose_name='Entrées (instantané)')
    posteriors = models.JSONField(
        default=dict, blank=True, verbose_name='Postérieurs')
    allocations = models.JSONField(
        default=dict, blank=True, verbose_name='Allocations produites')
    summary_fr = models.TextField(
        blank=True, default='', verbose_name='Résumé (FR)')
    action = models.ForeignKey(
        'adsengine.EngineAction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='decision_logs',
        verbose_name='Action produite')

    class Meta:
        verbose_name = 'Journal de décision'
        verbose_name_plural = 'Journaux de décision'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'experiment'],
                         name='adseng_declog_co_exp_idx'),
        ]

    def __str__(self):
        return f'Décision exp {self.experiment_id} @ {self.created_at:%Y-%m-%d}'


class RulePolicy(TenantModel):
    """ADSENG4 — Instance de RÈGLE gardien (le calque sous ``GuardrailConfig``).

    ``GuardrailConfig`` porte les plafonds globaux ; ``RulePolicy`` est UNE
    instance d'un template du catalogue (``rules.RULE_TEMPLATES``) — elle ne
    porte QUE des paramètres, la logique vit dans le registre code. **Défaut
    sûr** : ``enabled=False`` (le fondateur opte par template) et ``dry_run=True``
    (force « propose » + préfixe [SIMULATION], aucun envoi) — ``mode='auto'`` est
    structurellement impossible tant que ``dry_run`` est vrai. ``last_result`` est
    écrit à CHAQUE évaluation, même quand rien ne se déclenche (correctif du
    piège Madgicx : jamais un échec silencieux).
    """

    class Mode(models.TextChoices):
        PROPOSE = 'propose', 'Proposer'
        AUTO = 'auto', 'Automatique'

    template_key = models.CharField(
        max_length=48, choices=RULE_TEMPLATE_CHOICES,
        verbose_name='Template de règle')
    enabled = models.BooleanField(default=False, verbose_name='Activée')
    mode = models.CharField(
        max_length=8, choices=Mode.choices, default=Mode.PROPOSE,
        verbose_name='Mode')
    dry_run = models.BooleanField(
        default=True, verbose_name='Simulation (dry-run)')
    # Conditions AND/OR (instanciées depuis le template + params à l'évaluation).
    conditions = models.JSONField(
        default=dict, blank=True, verbose_name='Conditions (AND/OR)')
    params = models.JSONField(
        default=dict, blank=True, verbose_name='Paramètres')
    cadence_hours = models.PositiveIntegerField(
        default=6, verbose_name='Cadence (heures)')
    # Cooldown de dédup PAR entité (heures) — 0 = défaut de la sévérité.
    cooldown_hours = models.PositiveIntegerField(
        default=0, verbose_name='Cooldown par entité (heures)')
    last_evaluated_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernière évaluation')
    last_result = models.JSONField(
        default=dict, blank=True, verbose_name='Dernier résultat (audit)')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='adsengine_rule_policies',
        verbose_name='Créée par')

    class Meta:
        verbose_name = 'Règle de garde-fou'
        verbose_name_plural = 'Règles de garde-fou'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'template_key'],
                name='uniq_adseng_rule_template'),
        ]
        indexes = [
            models.Index(fields=['company', 'enabled'],
                         name='adseng_rule_co_en_idx'),
        ]

    def __str__(self):
        return f'{self.template_key} ({"on" if self.enabled else "off"})'

    @property
    def is_auto_effective(self):
        """``auto`` n'est effectif que si la règle N'EST PAS en simulation
        (invariant : une simulation ne joue jamais rien automatiquement)."""
        return self.mode == self.Mode.AUTO and not self.dry_run


class AnomalyEvent(TenantModel):
    """ADSENG4 — Anomalie détectée par le gardien (dépense sans résultat…).

    Matérialise UNE occurrence d'anomalie sur un objet publicitaire (campagne /
    ad set / ad, désigné par ``entity_type`` + ``entity_meta_id`` — jamais une FK
    dure vers un miroir, pour survivre à une resynchro). ``severity`` aligne
    ``rules.SEVERITY_*`` ; ``rule_policy`` (nullable) relie la règle qui a
    détecté ; ``alert`` (nullable) relie l'``EngineAlert`` émise.
    """

    class Kind(models.TextChoices):
        ZERO_DELIVERY = 'zero_delivery', 'Zéro delivery'
        ZERO_RESULTS = 'zero_results', 'Zéro résultat'
        COST_SPIKE = 'cost_spike', 'Pic de coût'
        FREQUENCY_HIGH = 'frequency_high', 'Fréquence élevée'
        AUTRE = 'autre', 'Autre'

    kind = models.CharField(
        max_length=16, choices=Kind.choices, verbose_name="Type d'anomalie")
    entity_type = models.CharField(
        max_length=16, blank=True, default='',
        verbose_name="Type d'entité (campaign/adset/ad)")
    entity_meta_id = models.CharField(
        max_length=64, blank=True, default='', verbose_name='ID Meta entité')
    severity = models.CharField(
        max_length=8, choices=EngineAlert.Severity.choices,
        default=EngineAlert.Severity.ATTENTION, verbose_name='Sévérité')
    message_fr = models.TextField(
        blank=True, default='', verbose_name='Message (FR)')
    detail = models.JSONField(default=dict, blank=True, verbose_name='Détail')
    resolved = models.BooleanField(default=False, verbose_name='Résolue')
    rule_policy = models.ForeignKey(
        'adsengine.RulePolicy', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='anomalies',
        verbose_name='Règle détectrice')
    alert = models.ForeignKey(
        'adsengine.EngineAlert', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='anomalies',
        verbose_name='Alerte émise')

    class Meta:
        verbose_name = 'Anomalie détectée'
        verbose_name_plural = 'Anomalies détectées'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'resolved'],
                         name='adseng_anom_co_res_idx'),
            models.Index(fields=['company', 'entity_meta_id'],
                         name='adseng_anom_co_ent_idx'),
        ]

    def __str__(self):
        return f'[{self.get_kind_display()}] {self.entity_meta_id or "?"}'


class PacingState(TenantModel):
    """ADSENG4 — État de PACING mensuel matérialisé, par société (idempotent).

    Un instantané par ``(société, mois)`` : enveloppe mensuelle, dépense à date,
    dépense attendue, prévision, ratio, et l'état à 5 valeurs (dd-treasury A3) :
    ``on_track`` / ``under_pacing`` / ``over_pacing`` / ``breach_imminent`` /
    ``paused_for_month``. Upsert idempotent par ``(company, period_start)`` via
    :meth:`upsert` — une recomputation du même mois écrase, jamais de doublon.
    """

    class State(models.TextChoices):
        ON_TRACK = 'on_track', 'Dans les clous'
        UNDER_PACING = 'under_pacing', 'Sous-rythme'
        OVER_PACING = 'over_pacing', 'Sur-rythme'
        BREACH_IMMINENT = 'breach_imminent', 'Franchissement imminent'
        PAUSED_FOR_MONTH = 'paused_for_month', 'En pause pour le mois'

    period_start = models.DateField(verbose_name='Début de période (mois)')
    monthly_budget_ceiling_mad = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Plafond mensuel (MAD)')
    spend_to_date = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Dépense à date')
    expected_spend_to_date = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Dépense attendue à date')
    forecast_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Prévision de dépense (fin de mois)')
    pacing_ratio = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True,
        verbose_name='Ratio de pacing')
    state = models.CharField(
        max_length=20, choices=State.choices, default=State.ON_TRACK,
        verbose_name='État')

    class Meta:
        verbose_name = 'État de pacing'
        verbose_name_plural = 'États de pacing'
        ordering = ['-period_start', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'period_start'],
                name='uniq_adseng_pacing_period'),
        ]

    def __str__(self):
        return f'Pacing {self.period_start:%Y-%m} — {self.get_state_display()}'

    @classmethod
    def upsert(cls, *, company, period_start, **fields):
        """Upsert idempotent d'un état de pacing mensuel (recomputation =
        écrasement, jamais de doublon). Renvoie ``(state, created)``."""
        return cls.objects.update_or_create(
            company=company, period_start=period_start, defaults=fields)


class CreativeGenerationBatch(TenantModel):
    """ADSENG5 — LOT de génération créative (approbation par LOT, jamais par
    variante).

    Une passe de recombinaison « hook gagnant × visuels candidats » produit un
    lot d'assets (cap ~2). Le fondateur approuve/rejette le LOT ENTIER en un
    clic (dd-creative-sci part b) — jamais variante par variante. Tant que le lot
    n'est pas approuvé, ses assets n'entrent pas dans le backlog.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPROUVEE = 'approuvee', 'Approuvé'
        REJETEE = 'rejetee', 'Rejeté'

    source_hook_asset = models.ForeignKey(
        'adsengine.CreativeAsset', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='generation_batches',
        verbose_name='Asset accroche source')
    visual_ids = models.JSONField(
        default=list, blank=True, verbose_name='IDs visuels candidats')
    status = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE,
        verbose_name='Statut')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='adsengine_batches_approuves',
        verbose_name='Décidé par')
    approved_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Décidé le')
    note = models.TextField(blank=True, default='', verbose_name='Note')

    class Meta:
        verbose_name = 'Lot de génération créative'
        verbose_name_plural = 'Lots de génération créative'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status'],
                         name='adseng_batch_co_st_idx'),
        ]

    def __str__(self):
        return f'Lot #{self.pk} ({self.get_status_display()})'


class CreativeBacklogItem(TenantModel):
    """ADSENG5 — Item de BACKLOG créatif : un asset approuvé en file de
    publication.

    Porte l'asset, sa provenance (``batch`` — le lot qui l'a produit, ou upload
    manuel), la campagne cible, la date-au-plus-tôt et un tag saisonnier, plus le
    statut de file (dd-creative-sci part c — le stock 3-6 mois comme DONNÉES).
    """

    class Source(models.TextChoices):
        MANUEL = 'manuel', 'Upload manuel'
        RECOMBINAISON = 'recombinaison', 'Recombinaison'

    class Statut(models.TextChoices):
        EN_FILE = 'en_file', 'En file'
        PROGRAMME = 'programme', 'Programmé'
        PUBLIE = 'publie', 'Publié'
        RETIRE = 'retire', 'Retiré'

    asset = models.ForeignKey(
        'adsengine.CreativeAsset', on_delete=models.CASCADE,
        related_name='backlog_items', verbose_name='Asset')
    batch = models.ForeignKey(
        'adsengine.CreativeGenerationBatch', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='backlog_items',
        verbose_name='Lot source')
    target_campaign = models.ForeignKey(
        'adsengine.AdCampaignMirror', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='backlog_items',
        verbose_name='Campagne cible')
    source = models.CharField(
        max_length=16, choices=Source.choices, default=Source.MANUEL,
        verbose_name='Provenance')
    earliest_date = models.DateField(
        null=True, blank=True, verbose_name='Date au plus tôt')
    seasonal_tag = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Tag saisonnier')
    status = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.EN_FILE,
        verbose_name='Statut file')

    class Meta:
        verbose_name = 'Item de backlog créatif'
        verbose_name_plural = 'Items de backlog créatif'
        ordering = ['earliest_date', 'id']
        indexes = [
            models.Index(fields=['company', 'status'],
                         name='adseng_backlog_co_st_idx'),
        ]

    def __str__(self):
        return f'Backlog #{self.pk} (asset {self.asset_id})'


class FlightPlan(TenantModel):
    """ADSENG5 — Plan de VOL : la feuille de route 3-6 mois comme DONNÉES.

    Un plan regroupe des phases ordonnées (``FlightPhase``), chacune testant une
    variable sur 2-3 bras pendant 3-4 semaines. Le plan lui-même ne LANCE rien :
    c'est une donnée que le moteur consomme pour proposer des campagnes (nées
    PAUSED, règle #3).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ACTIF = 'actif', 'Actif'
        TERMINE = 'termine', 'Terminé'

    name = models.CharField(max_length=160, verbose_name='Nom')
    objective = models.CharField(
        max_length=64, blank=True, default='', verbose_name='Objectif')
    status = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    start_date = models.DateField(null=True, blank=True, verbose_name='Début')
    end_date = models.DateField(null=True, blank=True, verbose_name='Fin')
    notes = models.TextField(blank=True, default='', verbose_name='Notes')

    class Meta:
        verbose_name = 'Plan de vol'
        verbose_name_plural = 'Plans de vol'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status'],
                         name='adseng_flight_co_st_idx'),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_status_display()})'


class FlightPhase(TenantModel):
    """ADSENG5 — Une PHASE ordonnée d'un ``FlightPlan`` (2-3 bras, 3-4 semaines).

    Décrit la variable testée, le template de lancement, le budget et la fenêtre.
    ``num_arms`` (2-4) et ``week_span`` (3-4) bornent la phase (validation de
    base côté serializer).
    """

    plan = models.ForeignKey(
        'adsengine.FlightPlan', on_delete=models.CASCADE,
        related_name='phases', verbose_name='Plan')
    order = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    name = models.CharField(max_length=120, verbose_name='Nom')
    # La séquence canonique (flightplan.PHASE_SEQUENCE) inclut 'consolidation'
    # (13 car.) — max_length=12 tronquait la matérialisation. 32 laisse de la
    # marge pour toute future variable testée (texte libre, pas de choices).
    tested_variable = models.CharField(
        max_length=32, blank=True, default='', verbose_name='Variable testée')
    launch_template = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Template de lancement')
    budget_mad = models.PositiveIntegerField(
        default=0, verbose_name='Budget (MAD)')
    start_date = models.DateField(null=True, blank=True, verbose_name='Début')
    end_date = models.DateField(null=True, blank=True, verbose_name='Fin')
    num_arms = models.PositiveSmallIntegerField(
        default=2, verbose_name='Nombre de bras')
    week_span = models.PositiveSmallIntegerField(
        default=3, verbose_name='Durée (semaines)')

    class Meta:
        verbose_name = 'Phase de vol'
        verbose_name_plural = 'Phases de vol'
        ordering = ['plan', 'order', 'id']
        indexes = [
            models.Index(fields=['plan', 'order'],
                         name='adseng_phase_plan_ord_idx'),
        ]

    def __str__(self):
        return f'{self.name} (plan {self.plan_id})'


class ReconciliationSnapshot(TenantModel):
    """ADSENG5 — Instantané de RÉCONCILIATION Meta-vs-ERP (dd-attribution part b).

    Un instantané daté par campagne : le nombre de leads / la dépense rapportés
    par Meta vs comptés côté ERP, l'écart, et un statut. Ne fusionne JAMAIS les
    deux chiffres (les deux sont montrés côte à côte) — la source de la confiance.
    """

    class Statut(models.TextChoices):
        OK = 'ok', 'Cohérent'
        ECART = 'ecart', 'Écart'
        A_VERIFIER = 'a_verifier', 'À vérifier'

    date = models.DateField(verbose_name='Date')
    campaign = models.ForeignKey(
        'adsengine.AdCampaignMirror', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reconciliations',
        verbose_name='Campagne')
    meta_leads = models.PositiveIntegerField(
        default=0, verbose_name='Leads (côté Meta)')
    erp_leads = models.PositiveIntegerField(
        default=0, verbose_name='Leads (côté ERP)')
    meta_spend = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Dépense (côté Meta)')
    delta_leads = models.IntegerField(
        default=0, verbose_name='Écart de leads (Meta − ERP)')
    status = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.OK,
        verbose_name='Statut')
    detail = models.JSONField(default=dict, blank=True, verbose_name='Détail')

    class Meta:
        verbose_name = 'Instantané de réconciliation'
        verbose_name_plural = 'Instantanés de réconciliation'
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['company', 'date'],
                         name='adseng_recon_co_dt_idx'),
        ]

    def __str__(self):
        return f'Réconciliation {self.date} (écart {self.delta_leads})'
