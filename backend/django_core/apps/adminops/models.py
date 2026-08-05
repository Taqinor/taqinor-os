"""apps.adminops — Health score, sandbox, packages de config, adoption,
diagnostic support (Groupe NTADM). Additif — aucun modèle métier existant
n'est modifié."""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TenantModel

#: NTADM22 — fenêtre par défaut d'une demande d'impersonation. Passé ce délai
#: sans consentement, la demande est périmée et ne peut PLUS être autorisée
#: rétroactivement (NTADM37 la marque `expiree`).
DUREE_DEMANDE_IMPERSONATION = timedelta(minutes=30)


def default_expiration_impersonation():
    """Échéance par défaut d'une demande d'impersonation (now + 30 min).

    Fonction nommée au niveau module (et non un ``lambda``) pour être
    sérialisable par les migrations Django."""
    return timezone.now() + DUREE_DEMANDE_IMPERSONATION


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


class SessionImpersonation(TenantModel):
    """NTADM22 — session de support « se connecter en tant que », SOUS CONSENTEMENT.

    `company` (TenantModel) = le tenant CIBLE (celui qui subit l'assistance) —
    c'est lui qui doit consentir, et c'est dans son journal que tout apparaît.

    Invariant central, garanti par le service ET par la base : **sans
    consentement explicite, aucune session n'existe**. Une demande naît
    `consentement_donne=False` et ne devient exploitable que si l'Administrateur
    du tenant cible clique « Autoriser » AVANT `expire_le`. Une demande périmée
    (`expiree=True`, NTADM37) ne peut JAMAIS être autorisée rétroactivement.
    """

    utilisateur_cible = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: la session n'a plus d'objet sans son utilisateur cible (composition)
        related_name='impersonations_subies',
        verbose_name='Utilisateur assisté')
    initiee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,  # on_delete: la trace d'audit survit à la suppression du compte support
        related_name='impersonations_initiees',
        verbose_name='Demandée par (support)')
    motif = models.TextField(
        verbose_name='Motif',
        help_text="Obligatoire — affiché tel quel au tenant dans la demande "
                  "de consentement.")
    consentement_donne = models.BooleanField(
        default=False, verbose_name='Consentement donné')
    consentement_le = models.DateTimeField(null=True, blank=True)
    consentement_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,  # on_delete: la preuve de consentement reste lisible même si son auteur est supprimé
        related_name='impersonations_consenties',
        verbose_name='Consentement donné par')
    refusee = models.BooleanField(default=False, verbose_name='Refusée')
    refus_le = models.DateTimeField(null=True, blank=True)
    expire_le = models.DateTimeField(
        default=default_expiration_impersonation,
        verbose_name="Échéance de la demande")
    demarree_le = models.DateTimeField(null=True, blank=True)
    terminee_le = models.DateTimeField(null=True, blank=True)
    expiree = models.BooleanField(default=False, verbose_name='Périmée')

    class Meta:
        verbose_name = "Session d'impersonation"
        verbose_name_plural = "Sessions d'impersonation"
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'consentement_donne'],
                         name='adminops_imp_co_consent'),
        ]

    def __str__(self):
        return f'Impersonation {self.utilisateur_cible_id} ({self.statut})'

    # ── Lecture d'état (aucune écriture ici) ────────────────────────────────
    def est_perimee(self, now=None):
        """True si la fenêtre de consentement est passée sans consentement."""
        if self.consentement_donne:
            return False
        return (now or timezone.now()) >= self.expire_le

    def est_active(self, now=None):
        """True SEULEMENT si une session utilisable existe à cet instant.

        Exige le consentement, l'absence de refus/péremption/clôture, et une
        échéance non atteinte. C'est l'unique porte d'entrée : tout le reste
        du code demande `est_active()`, jamais `consentement_donne` seul."""
        now = now or timezone.now()
        return bool(
            self.consentement_donne
            and not self.refusee
            and not self.expiree
            and self.terminee_le is None
            and now < self.expire_le
        )

    @property
    def statut(self):
        """Libellé français de l'état courant (jamais stocké — dérivé)."""
        if self.refusee:
            return 'refusee'
        if self.terminee_le is not None:
            return 'terminee'
        if self.expiree or self.est_perimee():
            return 'expiree'
        if self.consentement_donne:
            return 'active'
        return 'en_attente'


class FactureLicence(TenantModel):
    """N100(e) — registre de FACTURATION DE LICENCE, côté ÉDITEUR uniquement.

    Ce que ce modèle EST : le journal minimal par lequel le fondateur suit ce
    que chaque tenant lui doit pour l'usage de l'ERP (période, plan, montants,
    encaissement). Consultable et modifiable UNIQUEMENT depuis la console
    fondateur (superuser) — jamais exposé au tenant lui-même.

    Ce que ce modèle N'EST PAS — et ne doit jamais devenir :
      * une facture MÉTIER du tenant à SES clients : celles-ci vivent dans
        `apps.ventes` et n'ont rien à voir ici. Les deux ne se mélangent
        jamais, d'où ce modèle dans `adminops` et pas dans `ventes` ;
      * une passerelle de paiement : aucun encaissement automatique, aucun
        prestataire. Le fondateur pointe manuellement « payée ».

    `company` (TenantModel) = le tenant FACTURÉ. La référence est produite par
    `core.numbering.next_reference` (jamais un count()+1).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EMISE = 'emise', 'Émise'
        PAYEE = 'payee', 'Payée'

    reference = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Référence')
    #: Premier jour du mois facturé (une ligne par période et par tenant).
    periode = models.DateField(verbose_name='Période facturée')
    #: Copie FIGÉE du code de plan au moment de l'émission — le plan courant
    #: peut changer ensuite sans réécrire l'histoire de la facturation.
    plan_code = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Plan (snapshot)')
    montant_ht = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Montant HT')
    tva = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='TVA')
    montant_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name='Montant TTC')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    date_emission = models.DateField(null=True, blank=True)
    date_paiement = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='', verbose_name='Notes')

    class Meta:
        verbose_name = 'Facture de licence'
        verbose_name_plural = 'Factures de licence'
        ordering = ['-periode', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='adminops_lic_co_statut'),
        ]

    def __str__(self):
        return f'{self.reference or "(brouillon)"} — {self.company_id}'


class AnnonceProduit(models.Model):
    """NTADM18 — annonce PRODUIT de l'éditeur : le référentiel PLATEFORME.

    GLOBAL PAR CONCEPTION — volontairement SANS FK ``company`` (exempté du
    garde YDATA4, cf. ``scripts/tenant_exempt_models.txt``) : une nouveauté de
    l'ERP est publiée UNE fois par l'éditeur et concerne toutes les sociétés.
    Ce n'est pas de la donnée métier d'un tenant ; aucune société n'en est
    propriétaire.

    À ne pas confondre avec ses deux voisines, qui restent distinctes :
      * ``notifications.Annonce`` — annonces INTERNES d'un tenant à ses propres
        équipes (RH/organisation), scopées société ;
      * ``innovation.AnnonceProduit`` — repli LOCAL et volontairement simple
        que sa propre docstring décrit comme provisoire « tant que le
        référentiel plateforme (NTADM18) n'est pas bâti », et qu'elle interdit
        explicitement de fusionner avec celui-ci.

    La publication n'est PAS ouverte aux Administrateurs de tenant : diffuser à
    toutes les sociétés est une action d'éditeur (cf. ``views_annonces``).
    """

    titre = models.CharField(max_length=200, verbose_name='Titre')
    corps = models.TextField(
        blank=True, default='', verbose_name='Corps (markdown court)')
    date_publication = models.DateTimeField(
        default=timezone.now, verbose_name='Date de publication')
    #: Ciblage optionnel. VIDE = tout le monde (comportement par défaut).
    cible_roles = models.ManyToManyField(
        'roles.Role', blank=True, related_name='annonces_produit_plateforme',
        verbose_name='Rôles ciblés')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,  # on_delete: l'annonce publiée survit à la suppression de son auteur
        related_name='annonces_produit_publiees', verbose_name='Publiée par')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Annonce produit'
        verbose_name_plural = 'Annonces produit'
        ordering = ['-date_publication', '-id']

    def __str__(self):
        return self.titre


class LectureAnnonce(models.Model):
    """NTADM18 — accusé de lecture d'une annonce produit par UN utilisateur.

    Global comme l'annonce qu'il référence (pas de FK ``company`` : la société
    de l'utilisateur est déjà portée par ``utilisateur.company``). Le couple
    (utilisateur, annonce) est unique : marquer lu deux fois est sans effet."""

    annonce = models.ForeignKey(
        AnnonceProduit, on_delete=models.CASCADE,  # on_delete: composition — un accusé de lecture n'a aucun sens sans son annonce
        related_name='lectures', verbose_name='Annonce')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  # on_delete: composition — l'accusé disparaît avec le compte qui l'a posé
        related_name='lectures_annonces_produit', verbose_name='Utilisateur')
    lu_le = models.DateTimeField(auto_now_add=True, verbose_name='Lu le')

    class Meta:
        verbose_name = "Lecture d'annonce produit"
        verbose_name_plural = "Lectures d'annonces produit"
        ordering = ['-lu_le', '-id']
        unique_together = [('utilisateur', 'annonce')]

    def __str__(self):
        return f'{self.utilisateur_id} a lu {self.annonce_id}'


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
