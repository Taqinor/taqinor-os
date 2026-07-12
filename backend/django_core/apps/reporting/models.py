# Le reporting agrège les modèles des autres apps — historiquement aucun modèle
# propre. N79 introduit SavedReport ; FG96 ajoute DashboardConfig (config de
# tableau de bord par utilisateur / palier de rôle).
from django.conf import settings
from django.db import models


class SavedReport(models.Model):
    """N79 — Rapport sauvegardé + planification d'envoi par email.

    Multi-tenant : `company` est posée CÔTÉ SERVEUR (jamais lue du corps de
    requête) ; toutes les requêtes sont bornées à la société de l'utilisateur.
    `definition` (JSON) porte les paramètres du rapport (période, filtres…) ;
    `target_kind` choisit quel rapport rendre. `schedule` décide de la cadence
    d'envoi automatique. ADDITIF : NULL/valeurs par défaut = inerte
    (`schedule='none'` → la tâche planifiée ne l'envoie jamais)."""

    class TargetKind(models.TextChoices):
        SALES = 'sales', 'Ventes'
        STOCK = 'stock', 'Stock'
        SERVICE = 'service', 'Service'

    class Schedule(models.TextChoices):
        NONE = 'none', 'Aucune'
        DAILY = 'daily', 'Quotidien'
        WEEKLY = 'weekly', 'Hebdomadaire'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='saved_reports')
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='saved_reports')
    name = models.CharField(max_length=255)
    # Paramètres du rapport (période/filtres). Forme libre, défaut objet vide.
    definition = models.JSONField(default=dict, blank=True)
    target_kind = models.CharField(
        max_length=20, choices=TargetKind.choices, default=TargetKind.SALES)
    schedule = models.CharField(
        max_length=10, choices=Schedule.choices, default=Schedule.NONE)
    # Destinataires : une ou plusieurs adresses (séparées par virgule/point-virgule
    # ou retour à la ligne). Vide → aucun envoi (NO-OP).
    recipients = models.TextField(blank=True, default='')
    # Dernier envoi réussi (anti-doublon léger / traçabilité). NULL = jamais.
    last_sent_at = models.DateTimeField(null=True, blank=True)
    # FG91 — épingle le rapport comme carte sur le tableau de bord. ADDITIF,
    # default False = aucun changement de comportement pour les rapports existants.
    pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rapport sauvegardé'
        verbose_name_plural = 'Rapports sauvegardés'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'schedule']),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_target_kind_display()})'

    def recipient_list(self):
        """Adresses email destinataires, nettoyées. Liste vide si aucune."""
        raw = self.recipients or ''
        parts = []
        for chunk in raw.replace(';', ',').replace('\n', ',').split(','):
            addr = chunk.strip()
            if addr:
                parts.append(addr)
        return parts


# ── FG96 — Config tableau de bord par utilisateur / palier de rôle ───────────

# Ensemble complet des cartes disponibles sur le tableau de bord reporting.
# L'ordre ici est l'ordre d'affichage par défaut (clé = identifiant stable).
ALL_DASHBOARD_CARDS = [
    'kpis',
    'ca_mensuel',
    'top_produits',
    'statuts_factures',
    'conversion',
    'stock_alerte',
    'creances',
    'pipeline',
    'commercial',
]

# Ensembles de cartes par défaut selon le palier de rôle (menu_tier).
# Les clés correspondent aux valeurs de CustomUser.ROLE_*.
ROLE_DEFAULT_CARDS = {
    'admin': ALL_DASHBOARD_CARDS,
    'responsable': ALL_DASHBOARD_CARDS,
    'normal': [
        'kpis',
        'ca_mensuel',
        'conversion',
        'pipeline',
    ],
}

# Défaut global si le palier est inconnu ou absent.
GLOBAL_DEFAULT_CARDS = ALL_DASHBOARD_CARDS


class DashboardConfig(models.Model):
    """FG96 — Configuration de tableau de bord par utilisateur ou palier de rôle.

    Priorité de résolution (endpoint ``/dashboard-config/effective/``) :
      1. Config per-user (user == request.user, company scopée)
      2. Config palier-rôle (user IS NULL, menu_tier == user.menu_tier)
      3. Défaut global côté Python (ROLE_DEFAULT_CARDS / GLOBAL_DEFAULT_CARDS)

    ``cards`` : liste ordonnée de clés de cartes activées (sous-ensemble de
    ALL_DASHBOARD_CARDS). Un ``cards`` vide = toutes les cartes désactivées
    (cas valide). NULL n'est jamais stocké — on stocke toujours une liste.

    Multi-tenant strict : ``company`` est posée côté serveur ; le viewset
    borne TOUTES les requêtes à la société de l'utilisateur courant."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='reporting_dashboard_configs',
    )
    # NULL → config de palier de rôle ; non-NULL → config per-user.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reporting_dashboard_configs',
    )
    # Palier de rôle : 'admin' | 'responsable' | 'normal' | '' pour per-user.
    # Vide pour les configs per-user (user IS NOT NULL).
    menu_tier = models.CharField(max_length=20, blank=True, default='')
    # Liste ordonnée de clés de cartes activées.
    cards = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration tableau de bord"
        verbose_name_plural = "Configurations tableau de bord"
        ordering = ['-updated_at', '-id']
        # Un seul enregistrement per-user par société.
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'user'],
                condition=models.Q(user__isnull=False),
                name='rpt_dashcfg_co_user_uniq',
            ),
            # Un seul enregistrement de palier par (société, menu_tier).
            models.UniqueConstraint(
                fields=['company', 'menu_tier'],
                condition=models.Q(user__isnull=True),
                name='rpt_dashcfg_co_tier_uniq',
            ),
        ]
        indexes = [
            models.Index(
                fields=['company', 'user'],
                name='rpt_dashcfg_co_user_idx',
            ),
            models.Index(
                fields=['company', 'menu_tier'],
                name='rpt_dashcfg_co_tier_idx',
            ),
        ]

    def __str__(self):
        if self.user_id:
            return f"DashboardConfig user={self.user_id} co={self.company_id}"
        return f"DashboardConfig tier={self.menu_tier} co={self.company_id}"


# ── XPLT6 — alertes de seuil sur KPI agrégés ──────────────────────────────────

class KpiAlerte(models.Model):
    """XPLT6 — seuil configurable sur un KPI AGRÉGÉ (pas un objet unique).

    Distinct des alertes par OBJET (`STOCK_BELOW_THRESHOLD`/`FACTURE_OVERDUE`
    dans `automation`) : ici le seuil porte sur un agrégat calculé (ex.
    « DSO > 60 j »), évalué par un job Beat quotidien
    (``apps.reporting.kpi_alertes.evaluate_all_kpi_alertes``).

    ``kpi`` est un catalogue FERMÉ (``Kpi.choices``), chaque valeur branchée
    sur un selector reporting/compta/stock EXISTANT — jamais d'expression
    libre. Dédup : ``deja_notifie`` empêche de re-notifier tant que le seuil
    reste franchi ; il repasse à False dès que l'agrégat repasse sous (ou
    au-dessus, selon l'opérateur) le seuil, permettant une RE-notification au
    prochain re-franchissement."""

    class Kpi(models.TextChoices):
        DSO = 'dso', 'DSO (délai moyen de recouvrement, jours)'
        ENCOURS_ECHU_TOTAL = 'encours_echu_total', 'Encours client échu total (MAD)'
        VALEUR_STOCK_TOTALE = 'valeur_stock_totale', 'Valeur de stock totale (MAD)'

    class Operateur(models.TextChoices):
        SUP = 'sup', '>'
        SUP_EGAL = 'sup_egal', '>='
        INF = 'inf', '<'
        INF_EGAL = 'inf_egal', '<='

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='reporting_kpi_alertes')
    nom = models.CharField(max_length=120, blank=True, default='')
    kpi = models.CharField(max_length=30, choices=Kpi.choices)
    operateur = models.CharField(
        max_length=10, choices=Operateur.choices, default=Operateur.SUP)
    seuil = models.DecimalField(max_digits=14, decimal_places=2)
    # Destinataires : rôle (legacy) OU utilisateurs précis (au moins un des
    # deux, validé côté service/serializer — jamais les deux vides en usage
    # normal, mais aucune contrainte DB pour rester additif).
    destinataire_role = models.CharField(max_length=20, blank=True, default='')
    destinataires_utilisateurs = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name='reporting_kpi_alertes_destinataire')
    actif = models.BooleanField(default=True)
    # Dédup : vrai tant que le seuil reste franchi SANS repasser sous (état de
    # la dernière évaluation). Remis à False dès que l'agrégat repasse du bon
    # côté du seuil, ce qui autorise une nouvelle notification au prochain
    # re-franchissement.
    deja_notifie = models.BooleanField(default=False)
    derniere_valeur = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)
    derniere_evaluation_le = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Alerte KPI'
        verbose_name_plural = 'Alertes KPI'
        ordering = ['-created_at', '-id']
        # Pas d'index composite déclaré ici : l'index implicite Django sur la
        # FK `company` suffit au volume attendu (peu d'alertes par société) et
        # évite un nom d'index hashé à répliquer à la main dans la migration
        # (précédent : divergence silencieuse de nom d'index, voir mémoire
        # "Migration index-name divergence").

    def __str__(self):
        return self.nom or f'{self.get_kpi_display()} {self.operateur} {self.seuil}'

    def est_franchi(self, valeur):
        """True si ``valeur`` franchit le seuil selon l'opérateur configuré."""
        if valeur is None:
            return False
        if self.operateur == self.Operateur.SUP:
            return valeur > self.seuil
        if self.operateur == self.Operateur.SUP_EGAL:
            return valeur >= self.seuil
        if self.operateur == self.Operateur.INF:
            return valeur < self.seuil
        return valeur <= self.seuil


# ── XPLT22 — classeur léger embarqué avec données live (mini-spreadsheet BI) ─

class Classeur(models.Model):
    """XPLT22 — feuille de calcul légère dont des plages référencent des
    datasets LIVE (différenciateur Odoo : aucun tableur in-app aujourd'hui).

    ``cellules`` (JSON) : ``{ "A1": {"formule": "=SOMME(B1:B3)"} | {"valeur":
    42}, …}`` — les formules sont évaluées par l'évaluateur AST-sûr de
    ``core.formula`` (jamais eval JS libre), exposé via un endpoint dédié.
    ``liens`` (JSON) : ``{ "B1:B3": {"saved_query_id": 7} }`` — une plage LIÉE
    à une ``core.SavedQuery`` (requête sauvegardée re-exécutée au CHARGEMENT).
    Les droits d'accès du LECTEUR sont respectés : une plage liée à une
    requête que le lecteur ne peut pas voir (visibilité perso/partagé de
    ``SavedQuery``, comme ``Dashboard``) reste VIDE, jamais une fuite.

    Le partage interne réutilise le pattern XPLT10
    (``core.DashboardPartageInterne``, mais scopé Classeur ici — voir
    ``ClasseurPartageInterne`` plus bas)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='reporting_classeurs')
    proprietaire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='reporting_classeurs',
        help_text='Vide = classeur de société (non personnel).')
    titre = models.CharField(max_length=160, default='Classeur sans titre')
    # {cell_ref: {'formule': str} | {'valeur': scalar}} — opaque pour reporting
    # au niveau stockage ; interprété à l'évaluation (formule.py).
    cellules = models.JSONField(default=dict, blank=True)
    # {range_ref: {'saved_query_id': int}} — plages liées à des SavedQuery.
    liens = models.JSONField(default=dict, blank=True)
    # Partagé société-entière (même sémantique que Dashboard.partage) — le
    # partage FIN (utilisateur/rôle) vit dans ClasseurPartageInterne.
    partage = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Classeur'
        verbose_name_plural = 'Classeurs'
        ordering = ['titre', 'id']

    def __str__(self):
        return self.titre


# ── ZCTR9 — SLA d'approbation paramétrable par société (boîte XKB1) ──────────

class ApprobationSlaConfig(models.Model):
    """ZCTR9 — délai SLA (en jours OUVRÉS) au-delà duquel une demande en
    attente dans la boîte d'approbations centralisée (XKB1) est signalée
    « en retard » dans l'agrégateur ``apps/reporting/approbations.py``.

    Un seul enregistrement par société (``company`` unique) ; ADDITIF —
    aucune ligne pour une société = défaut ``DEFAULT_SLA_JOURS`` (3 jours
    ouvrés), comportement inchangé tant que le founder ne configure rien."""

    DEFAULT_SLA_JOURS = 3

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='approbation_sla_config')
    sla_jours = models.PositiveIntegerField(
        default=DEFAULT_SLA_JOURS,
        help_text=(
            "Nombre de jours ouvrés en attente au-delà duquel une demande "
            "d'approbation est signalée en retard."))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réglage SLA d'approbation"
        verbose_name_plural = "Réglages SLA d'approbation"

    def __str__(self):
        return f'SLA approbation [{self.company_id}] = {self.sla_jours}j ouvrés'

    @classmethod
    def sla_jours_pour(cls, company):
        """Renvoie le SLA (jours ouvrés) configuré pour ``company``, ou le
        défaut si aucune config n'existe (ADDITIF, jamais d'exception)."""
        if company is None:
            return cls.DEFAULT_SLA_JOURS
        cfg = cls.objects.filter(company=company).first()
        return cfg.sla_jours if cfg is not None else cls.DEFAULT_SLA_JOURS


class ClasseurPartageInterne(models.Model):
    """XPLT22 — partage interne fin d'un classeur (réutilise le pattern
    XPLT10 ``core.DashboardPartageInterne``, scopé Classeur)."""

    class Niveau(models.TextChoices):
        LECTURE = 'lecture', 'Lecture'
        EDITION = 'edition', 'Édition'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='reporting_classeur_partages_internes')
    classeur = models.ForeignKey(
        Classeur, on_delete=models.CASCADE, related_name='partages_internes')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='reporting_classeur_partages_recus')
    role = models.CharField(max_length=20, blank=True, default='')
    niveau = models.CharField(
        max_length=10, choices=Niveau.choices, default=Niveau.LECTURE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Partage interne de classeur'
        verbose_name_plural = 'Partages internes de classeur'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['classeur', 'utilisateur'],
                condition=models.Q(utilisateur__isnull=False),
                name='rpt_classeur_partage_user_uniq'),
            models.UniqueConstraint(
                fields=['classeur', 'role'],
                condition=~models.Q(role=''),
                name='rpt_classeur_partage_role_uniq'),
        ]

    def __str__(self):
        cible = self.utilisateur_id or self.role or '—'
        return f'Classeur {self.classeur_id} → {cible} ({self.niveau})'


class WebVitalMetric(models.Model):
    """VX61 — une ligne par métrique Web Vitals RÉELLE mesurée sur le
    terrain (INP/LCP/CLS/TTFB), envoyée par `frontend/src/lib/vitals.js`
    (hand-roll `PerformanceObserver` — la lib `web-vitals` de Google reste
    une dépendance GATÉE) via `navigator.sendBeacon`. Croissance rapide (une
    ligne par métrique par navigation) — purgée par la politique de
    rétention `reporting_web_vitals` (voir `apps.py ready()` + YOPSB10)."""

    class Metric(models.TextChoices):
        LCP = 'LCP', 'Largest Contentful Paint'
        INP = 'INP', 'Interaction to Next Paint'
        CLS = 'CLS', 'Cumulative Layout Shift'
        TTFB = 'TTFB', 'Time to First Byte'

    class Rating(models.TextChoices):
        GOOD = 'good', 'Bon'
        NEEDS_IMPROVEMENT = 'needs-improvement', 'À améliorer'
        POOR = 'poor', 'Mauvais'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='reporting_web_vitals')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reporting_web_vitals')
    route = models.CharField(max_length=255, blank=True, default='')
    metric = models.CharField(max_length=10, choices=Metric.choices)
    value = models.FloatField()
    rating = models.CharField(
        max_length=20, choices=Rating.choices, blank=True, default='')
    navigation_id = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Métrique Web Vitals'
        verbose_name_plural = 'Métriques Web Vitals'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(
                fields=['company', 'route', 'metric', 'created_at'],
                name='rpt_vitals_p75_idx'),
        ]

    def __str__(self):
        return f'{self.metric}={self.value} [{self.route}] ({self.company_id})'
