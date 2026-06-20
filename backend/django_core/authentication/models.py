from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils.text import slugify


class Company(models.Model):
    nom = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nom)
            self.slug = base or f"company-{Company.objects.count() + 1}"
        super().save(*args, **kwargs)


class CustomUser(AbstractUser):
    ROLE_ADMIN = 'admin'
    ROLE_RESPONSABLE = 'responsable'
    ROLE_NORMAL = 'normal'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrateur'),
        (ROLE_RESPONSABLE, 'Utilisateur Responsable'),
        (ROLE_NORMAL, 'Utilisateur Normal'),
    ]

    # Legacy role field kept for backward compat and migration reference
    role_legacy = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_NORMAL,
    )
    # New FK to custom Role model (null until init_roles runs)
    role = models.ForeignKey(
        'roles.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    # Poste / intitulé du métier (ex. « Commerciale », « Technicien »).
    # Purement informatif, affiché dans l'admin et à côté de l'avatar.
    poste = models.CharField(max_length=120, blank=True, default='')
    # Clé MinIO (bucket erp-uploads) de la photo de profil. Vide = avatar
    # à initiales. Même mécanisme de stockage que logo/signature entreprise
    # (boto3, jamais de FileField/ImageField) — aucune dépendance nouvelle.
    avatar_key = models.CharField(max_length=500, blank=True, default='')
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    # Compte propriétaire protégé : ne peut être ni supprimé ni rétrogradé,
    # par personne (y compris lui-même). Garantit, avec la garde « dernier
    # propriétaire », qu'on ne peut jamais se verrouiller dehors. La
    # récupération passe par l'accès SSH au serveur (management command), pas
    # par un secret en dur. Additif, défaut False.
    is_protected = models.BooleanField(default=False)
    # Superviseur direct (hiérarchie d'équipe, Feature E). Auto-référence
    # nullable : un Directeur/Admin l'assigne dans Paramètres → Équipe. L'« équipe »
    # d'un utilisateur = tous ceux partageant son superviseur direct (ses pairs),
    # plus — pour un responsable — tout son sous-arbre. Sert à la portée de
    # visibilité des enregistrements (Feature F). Additif, défaut NULL : tant
    # qu'aucun superviseur n'est posé, l'arbre est plat. SET_NULL : retirer un
    # manager ne supprime jamais ses subordonnés.
    supervisor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates',
    )

    # ── Double authentification (2FA TOTP) — strictement OPT-IN (N96) ──────
    # Le secret TOTP partagé (base32). Posé dès la phase de configuration mais
    # le 2FA n'est ACTIF qu'une fois ``totp_enabled`` passé à True (après
    # vérification d'un premier code). Nullable/vide par défaut : tout compte
    # existant a donc le 2FA DÉSACTIVÉ et se connecte exactement comme avant —
    # aucun verrouillage possible.
    totp_secret = models.CharField(max_length=64, blank=True, null=True)
    # Drapeau d'activation. Défaut False : 2FA inactif tant que l'utilisateur
    # ne l'a pas explicitement activé et vérifié lui-même.
    totp_enabled = models.BooleanField(default=False)
    # Codes de secours à usage unique, stockés HACHÉS (jamais en clair).
    # Liste JSON de hachages (make_password). Permet de se reconnecter si le
    # téléphone d'authentification est perdu. Additif, défaut liste vide.
    totp_recovery_codes = models.JSONField(default=list, blank=True)

    def verify_totp(self, code):
        """Valide un code TOTP courant (ou un code de secours à usage unique).

        Retourne True si le code est valide. Un code de secours consommé est
        retiré de ``totp_recovery_codes`` et persisté. Tolérance d'une fenêtre
        (±30 s) pour absorber les petites dérives d'horloge."""
        if not self.totp_secret:
            return False
        import pyotp
        from django.contrib.auth.hashers import check_password
        code = (str(code) if code is not None else '').strip().replace(' ', '')
        if not code:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        if totp.verify(code, valid_window=1):
            return True
        # Repli : code de secours à usage unique (haché en base).
        for hashed in list(self.totp_recovery_codes or []):
            if check_password(code, hashed):
                remaining = [h for h in self.totp_recovery_codes if h != hashed]
                self.totp_recovery_codes = remaining
                self.save(update_fields=['totp_recovery_codes'])
                return True
        return False

    @staticmethod
    def tier_for_role(role):
        """Palier de menu hérité correspondant à un Role (ou None sans rôle).

        Délègue à la source unique de vérité ``role_tiers`` : le palier dérive
        d'abord du signal de permission faisant autorité du rôle (``roles_gerer``
        → 'admin', ``users_voir`` → 'responsable') — robuste à toute dérive de
        nom/``est_systeme`` laissée par le mapping rétroactif des rôles — puis,
        à défaut, du nom système (Administrateur/Directeur → 'admin', Responsable
        → 'responsable', Utilisateur / rôle personnalisé → 'normal')."""
        if role is None:
            return None
        from authentication.role_tiers import tier_for_role_fields
        return tier_for_role_fields(
            role.nom, role.est_systeme, role.permissions or [])

    @property
    def menu_tier(self):
        """Palier de menu FAISANT AUTORITÉ, dérivé du NOUVEAU rôle.

        C'est le signal que le frontend doit utiliser pour choisir le menu : il
        vient toujours du Role assigné, jamais du champ ``role_legacy`` qui peut
        dériver (un Administrateur créé avec role_legacy='normal' obtenait à
        tort le menu limité). Repli sur ``role_legacy`` uniquement pour les
        comptes encore sans rôle."""
        if self.is_superuser:
            return self.ROLE_ADMIN
        if self.role_id:
            return self.tier_for_role(self.role)
        return self.role_legacy

    @property
    def is_admin_role(self):
        if self.is_superuser:
            return True
        if self.role:
            return 'roles_gerer' in (self.role.permissions or [])
        return self.role_legacy == self.ROLE_ADMIN

    @staticmethod
    def admins_actifs_qs(company):
        """Utilisateurs actifs ayant le rôle propriétaire/admin d'une société.

        Couvre les deux modèles de rôle : FK Role avec 'roles_gerer', et le
        legacy role_legacy='admin'. Sert à empêcher la suppression/rétrogradation
        du DERNIER propriétaire.
        """
        from django.db.models import Q
        qs = CustomUser.objects.filter(is_active=True)
        if company is not None:
            qs = qs.filter(company=company)
        return qs.filter(
            Q(role__permissions__contains=['roles_gerer'])
            | Q(role__isnull=True, role_legacy=CustomUser.ROLE_ADMIN)
            | Q(is_superuser=True)
        )

    def est_dernier_proprietaire(self):
        """True si retirer ce compte laisserait sa société sans aucun admin."""
        if not self.is_admin_role:
            return False
        autres = self.admins_actifs_qs(self.company).exclude(pk=self.pk)
        return not autres.exists()

    @property
    def is_responsable(self):
        if self.is_superuser:
            return True
        if self.role:
            return True
        return self.role_legacy in (
            self.ROLE_RESPONSABLE, self.ROLE_ADMIN
        )

    def has_erp_permission(self, code):
        """Check if user has a specific ERP permission code."""
        if self.is_superuser:
            return True
        if self.role:
            return code in (self.role.permissions or [])
        return False

    @property
    def can_view_buy_prices(self):
        """Voir les prix d'achat & marges (Feature D). Réservé par permission
        explicite (Directeur/Admin), avec REPLI historique pour les comptes
        SANS rôle fin (légacy) — comme ``HasPermissionOrLegacy`` : on ne retire
        jamais l'accès aux comptes hérités."""
        if self.is_superuser:
            return True
        if self.role_id:
            return 'prix_achat_voir' in (self.role.permissions or [])
        return True  # compte légacy sans rôle fin → comportement historique

    @property
    def can_view_activity_log(self):
        """Voir le Journal d'activité (Feature G). Permission explicite
        (Directeur par défaut). Superuser toujours autorisé."""
        if self.is_superuser:
            return True
        if self.role_id:
            return 'journal_activite_voir' in (self.role.permissions or [])
        return False

    def record_scope(self):
        """'all' | 'subtree' | 'team' — portée de visibilité (Feature F).

        Un rôle SANS marqueur de portée voit tout (légacy/personnalisé/admin)."""
        from authentication.scoping import record_scope_for
        return record_scope_for(self)

    def visible_user_ids(self):
        """Ensemble d'ids utilisateurs dont cet utilisateur peut voir les
        enregistrements (lui-même toujours inclus). Voir ``scoping``."""
        from authentication.scoping import visible_user_ids
        return visible_user_ids(self)

    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        related_name="customuser_set",
        related_query_name="customuser",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        related_name="customuser_set",
        related_query_name="customuser",
    )

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.username
