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

    class Meta:
        verbose_name = 'Garde-fous publicitaires'
        verbose_name_plural = 'Garde-fous publicitaires'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'Garde-fous <plafond {self.daily_budget_ceiling_mad} MAD/j, '
            f'±{self.weekly_change_pct_max}%>'
        )
