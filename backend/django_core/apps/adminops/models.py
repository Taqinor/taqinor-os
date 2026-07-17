"""apps.adminops — Health score, sandbox, packages de config, adoption,
diagnostic support (Groupe NTADM). Additif — aucun modèle métier existant
n'est modifié."""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class HealthScoreSnapshot(TenantModel):
    """NTADM36 — persistance quotidienne du score NTADM5 pour permettre une
    tendance (widget NTADM6 ↑/↓ vs. il y a 30 jours)."""

    score = models.PositiveSmallIntegerField()
    sous_scores = models.JSONField(default=dict, blank=True)
    calcule_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Instantané health score'
        verbose_name_plural = 'Instantanés health score'
        ordering = ['-calcule_le']

    def __str__(self):
        return f'{self.company_id} — {self.score} ({self.calcule_le:%Y-%m-%d})'


class SandboxEnvironment(TenantModel):
    """NTADM10 — environnement sandbox self-service. `company` (TenantModel)
    = le tenant SOURCE. `sandbox_company` = le tenant cloné (résultat),
    peuplé quand le clonage aboutit."""

    class Statut(models.TextChoices):
        EN_CREATION = 'en_creation', 'En création'
        PRET = 'pret', 'Prêt'
        EXPIRE = 'expire', 'Expiré'
        ECHEC = 'echec', 'Échec'

    sandbox_company = models.ForeignKey(
        'authentication.Company', on_delete=models.SET_NULL, null=True, blank=True,  # on_delete: le tenant sandbox peut être purgé indépendamment de cet enregistrement historique
        related_name='sandbox_environments_cibles')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_CREATION)
    date_expiration = models.DateTimeField()
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,  # on_delete: l'environnement sandbox reste traçable même si son créateur est supprimé
        related_name='sandbox_environments_crees')
    prolongations_count = models.PositiveSmallIntegerField(default=0)
    rappel_j3_envoye = models.BooleanField(default=False)
    rappel_48h_envoye = models.BooleanField(default=False)
    erreur = models.TextField(blank=True, default='')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Environnement sandbox'
        verbose_name_plural = 'Environnements sandbox'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Sandbox {self.company_id} → {self.statut}'


class ConfigPackage(TenantModel):
    """NTADM13 — export horodaté et versionné de la CONFIGURATION d'un
    tenant (jamais de donnée métier/client)."""

    nom = models.CharField(max_length=150)
    version = models.PositiveIntegerField(default=1)
    contenu = models.JSONField(default=dict, blank=True)
    contenu_purge = models.BooleanField(default=False)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,  # on_delete: l'historique d'export reste traçable même si son auteur est supprimé
        related_name='config_packages_crees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Package de configuration'
        verbose_name_plural = 'Packages de configuration'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.nom} v{self.version} ({self.company_id})'


class ConfigPackageApplication(TenantModel):
    """NTADM14 — log NON silencieux de chaque prévisualisation/application
    d'import de package : qui / quand / résultat."""

    class Action(models.TextChoices):
        PREVISUALISATION = 'previsualisation', 'Prévisualisation'
        APPLICATION = 'application', 'Application'

    package_nom = models.CharField(max_length=150)
    package_version = models.PositiveIntegerField(default=1)
    action = models.CharField(max_length=20, choices=Action.choices)
    diff = models.JSONField(default=dict, blank=True)
    applique_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,  # on_delete: le journal d'application reste traçable même si l'acteur est supprimé
        related_name='config_package_applications')
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Journal d'import de package"
        verbose_name_plural = "Journaux d'import de package"
        ordering = ['-date_action']

    def __str__(self):
        return f'{self.action} {self.package_nom} ({self.date_action:%Y-%m-%d})'


class EvenementUsage(TenantModel):
    """NTADM16 — analytics d'adoption privacy-safe : PAS de payload libre,
    seulement des clés d'écran connues, jamais de contenu métier."""

    module = models.CharField(max_length=60)
    ecran = models.CharField(max_length=120, blank=True, default='')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,  # on_delete: l'agrégat d'adoption reste utile même après suppression de l'utilisateur (anonymisé)
        related_name='evenements_usage')
    horodatage = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Événement d'usage"
        verbose_name_plural = "Événements d'usage"
        ordering = ['-horodatage']
        indexes = [models.Index(fields=['company', 'module', 'horodatage'])]

    def __str__(self):
        return f'{self.module}/{self.ecran} — {self.utilisateur_id}'


class AdminOpsSettings(TenantModel):
    """NTADM33 — réglages transverses de ce groupe, tous à défaut =
    comportement documenté existant (jamais restrictif par défaut)."""

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: réglage 1-1, disparaît avec la société (scope multi-société)
        related_name='adminops_settings', verbose_name='Société')
    sandbox_duree_defaut_jours = models.PositiveSmallIntegerField(default=14)
    sandbox_grace_purge_jours = models.PositiveSmallIntegerField(default=7)
    seuil_alerte_sieges_pct = models.PositiveSmallIntegerField(default=90)
    retention_evenements_usage_jours = models.PositiveSmallIntegerField(default=180)
    # NTADM34 — désactivation totale de la fonctionnalité sandbox par tenant.
    sandbox_autorise = models.BooleanField(default=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réglages Administration (société)'
        verbose_name_plural = 'Réglages Administration (société)'

    def __str__(self):
        return f'Réglages adminops — {self.company_id}'

    @classmethod
    def get_or_default(cls, company):
        try:
            return cls.objects.get(company=company)
        except cls.DoesNotExist:
            return cls(company=company)
