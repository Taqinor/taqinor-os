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
