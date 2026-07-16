from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils.text import slugify

from core.crypto_fields import EncryptedCharField


class Company(models.Model):
    # SCA18 — cycle de vie du tenant. ``actif`` (bool historique) est CONSERVÉ
    # intact (jamais supprimé) et reste le drapeau lu partout ; ``statut`` ajoute
    # une granularité (actif / suspendu / en fermeture) appliquée au JWT et à
    # l'API. Un PONT de synchro bidirectionnel réversible garde les deux
    # cohérents : ``statut != actif`` → ``actif`` recalculé (seul ``actif``
    # signifie « opérationnel »). Backfill : chaque société existante prend
    # ``statut=actif`` si ``actif`` sinon ``suspendu`` — comportement inchangé.
    STATUT_ACTIF = 'actif'
    STATUT_SUSPENDU = 'suspendu'
    STATUT_FERMETURE = 'fermeture'
    STATUT_CHOICES = [
        (STATUT_ACTIF, 'Actif'),
        (STATUT_SUSPENDU, 'Suspendu'),
        (STATUT_FERMETURE, 'En fermeture'),
    ]

    nom = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    actif = models.BooleanField(default=True)
    statut = models.CharField(
        'Statut du compte', max_length=12, choices=STATUT_CHOICES,
        default=STATUT_ACTIF,
        help_text="Cycle de vie du tenant : seul « actif » autorise login/API. "
                  "« suspendu »/« en fermeture » bloquent l'accès (rule SCA18).")
    # SCA21 — date de passage en fermeture : démarre le délai de grâce (30 j)
    # pendant lequel les données restent intactes avant qu'une purge explicite
    # (management command, double confirmation) puisse être exécutée.
    date_fermeture = models.DateTimeField(
        'Date de mise en fermeture', null=True, blank=True)
    # SCA22 — annotation libre du fondateur (console tenants) : note de plan /
    # remarque libre, JAMAIS de billing ici. Additif, défaut vide.
    plan_flag = models.CharField(
        'Note de plan (fondateur)', max_length=255, blank=True, default='')
    # SCA46 — consentement au benchmarking anonymisé agrégé. Le CONSENTEMENT est
    # une donnée (Boolean, défaut False — opt-in strict) ; AUCUNE agrégation
    # n'est construite ici. Une future feature d'agrégation devra pointer ce
    # champ (voir NTDATA46) au lieu de re-modéliser le consentement.
    benchmarking_opt_in = models.BooleanField(
        'Consentement benchmarking anonymisé', default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"

    def __str__(self):
        return self.nom

    @property
    def est_operationnel(self):
        """True si le tenant est ACTIF (login + API autorisés). Un tenant
        suspendu ou en fermeture n'est pas opérationnel."""
        return self.statut == self.STATUT_ACTIF and self.actif

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nom)
            self.slug = base or f"company-{Company.objects.count() + 1}"
        # SCA18 — pont de synchro bool↔statut (réversible, sans perte).
        # ``actif`` (bool historique) et ``statut`` (granulaire) doivent toujours
        # s'accorder sur l'état OPÉRATIONNEL. Réconciliation :
        #   * si un code historique a mis ``actif=False`` alors que ``statut`` est
        #     resté « actif » → on promeut ``statut`` en « suspendu » (le bool
        #     mène) : une désactivation existante reste effective ;
        #   * sinon ``actif`` suit ``statut`` (« actif » ⇔ True). Un tenant
        #     suspendu/en fermeture a donc toujours ``actif=False``, ce qui fait
        #     que TOUT code qui ne lit que ``actif`` bloque déjà ces tenants.
        ancien_statut, ancien_actif = self.statut, self.actif
        # Qui mène ? Comparaison à l'état PERSISTÉ : si l'appelant n'a touché
        # que le bool historique ``actif``, le bool mène (dans les deux sens) ;
        # sinon ``statut`` mène. Sans cela, réactiver via ``statut = actif``
        # était re-dégradé en « suspendu » (l'actif=False persistant gagnait).
        db = (Company.objects.filter(pk=self.pk)
              .values('statut', 'actif').first()) if self.pk else None
        if db is not None:
            statut_change = self.statut != db['statut']
            actif_change = self.actif != db['actif']
            if actif_change and not statut_change:
                if self.actif is False and self.statut == self.STATUT_ACTIF:
                    self.statut = self.STATUT_SUSPENDU
                elif self.actif is True and self.statut != self.STATUT_ACTIF:
                    self.statut = self.STATUT_ACTIF
        elif self.statut == self.STATUT_ACTIF and self.actif is False:
            self.statut = self.STATUT_SUSPENDU
        self.actif = (self.statut == self.STATUT_ACTIF)
        # Un save(update_fields=[…]) partiel doit persister la réconciliation
        # du pont s'il a modifié statut/actif — sinon la base divergerait.
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            extra = set()
            if self.statut != ancien_statut:
                extra.add('statut')
            if self.actif != ancien_actif:
                extra.add('actif')
            if extra:
                kwargs['update_fields'] = list(set(update_fields) | extra)
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
    # Champ texte LIBRE HÉRITÉ : conservé intact (jamais supprimé) pour rester
    # totalement réversible et garder l'historique des intitulés saisis. Le
    # référentiel canonique est désormais ``poste_ref`` (FK ``rh.Poste``, FG160).
    poste = models.CharField(max_length=120, blank=True, default='')
    # DC17 — Référentiel des postes (FG160) : FK vers le ``rh.Poste`` normalisé
    # de la société, qui remplace progressivement le ``poste`` texte libre. Le
    # poste CANONIQUE d'un collaborateur vit sur ``rh.DossierEmploye`` ; ce FK
    # sur ``CustomUser`` est l'écho côté compte applicatif. Référence par
    # STRING-FK (``'rh.Poste'``) — aucune importation des modèles rh côté
    # authentication. Nullable + SET_NULL : additif, jamais de verrouillage ni de
    # cascade ; supprimer un Poste détache simplement le compte. ``related_name``
    # préfixé par le label (``auth_users``) pour éviter toute collision avec
    # ``Poste.employes`` (DossierEmploye). Migré/dédupliqué par société depuis
    # ``poste`` via une migration de données réversible.
    poste_ref = models.ForeignKey(
        'rh.Poste',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auth_users',
    )
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
    # XPLT19 — Accès multi-sociétés. Un utilisateur (ex. le fondateur qui opère
    # une EI ET une SARL) peut être MEMBRE de plusieurs sociétés. ``company``
    # ci-dessus reste la société d'attache (« home », défaut de connexion) ;
    # ``societes_autorisees`` liste TOUTES les sociétés qu'il peut opérer.
    # ADDITIF & rétrocompatible : une migration de données backfille chaque
    # compte existant avec {sa ``company``}, donc un compte mono-société a
    # exactement {sa société} — comportement byte-identique (il ne peut pas
    # switcher). La société ACTIVE d'une requête est portée par un claim JWT et
    # appliquée par ``ActiveCompanyMiddleware`` (voir ``active_company.py``) —
    # jamais un ``save()`` : le FK ``company`` d'attache n'est jamais modifié.
    societes_autorisees = models.ManyToManyField(
        Company,
        blank=True,
        related_name='membres_autorises',
        verbose_name='Sociétés autorisées',
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
    totp_secret = EncryptedCharField(max_length=64, blank=True, null=True)
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
        """Porte les endpoints d'écriture/gestion gardés par
        ``IsResponsableOrAdmin``.

        Bug historique (ERR4) : renvoyait True dès qu'un Role était posé, ce qui
        laissait passer les rôles STRICTEMENT lecture seule (Viewer,
        Utilisateur…) sur tous les endpoints d'écriture — y compris validation de
        devis, émission de facture, mouvements de stock, édition/réassignation de
        leads, etc.

        Correctif : pour un compte portant un Role fin, on n'est « responsable »
        que si le rôle accorde AU MOINS UNE permission d'écriture/gestion — un
        rôle ne portant que des permissions de lecture (suffixe ``_voir``) et/ou
        des marqueurs de portée (``records_scope_*``) est désormais EXCLU. Cela
        bloque les rôles lecture seule sans pénaliser les rôles métier
        légitimes (Commercial, Technicien…) qui détiennent leurs droits
        d'écriture fins. Les comptes HÉRITÉS sans Role fin gardent exactement
        leur comportement via ``role_legacy`` (aucune régression légacy)."""
        if self.is_superuser:
            return True
        if self.role_id:
            return self._role_grants_write(self.role.permissions or [])
        return self.role_legacy in (
            self.ROLE_RESPONSABLE, self.ROLE_ADMIN
        )

    @staticmethod
    def _role_grants_write(permissions):
        """True si la liste de permissions accorde au moins une action
        d'écriture/gestion (toute permission qui n'est ni une lecture
        ``*_voir`` ni un marqueur de portée ``records_scope_*``)."""
        for perm in permissions:
            # `_voir` (FR) et `_view` (EN, ex. adsengine_view/ENG19) sont tous
            # deux des permissions de LECTURE — ne jamais les compter comme écriture.
            if perm.endswith('_voir') or perm.endswith('_view'):
                continue
            if perm.startswith('records_scope'):
                continue
            return True
        return False

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
    def can_view_marge(self):
        """FG20 — voir la marge interne calculée (donnée sensible). Permission
        explicite ``marge_voir`` (Directeur/Admin par défaut), avec repli
        historique pour les comptes SANS rôle fin (légacy) : on ne retire jamais
        l'accès aux comptes hérités. Superuser toujours autorisé."""
        if self.is_superuser:
            return True
        if self.role_id:
            return 'marge_voir' in (self.role.permissions or [])
        return True  # compte légacy sans rôle fin → comportement historique

    @property
    def can_view_client_pii(self):
        """FG20 — voir les coordonnées personnelles d'un client/lead
        (téléphone, email, adresse, WhatsApp, GPS). Permission ``client_pii_voir``
        (accordée par défaut aux rôles opérationnels), repli historique pour les
        comptes légacy. Superuser toujours autorisé."""
        if self.is_superuser:
            return True
        if self.role_id:
            return 'client_pii_voir' in (self.role.permissions or [])
        return True  # compte légacy sans rôle fin → comportement historique

    @property
    def can_view_cout_non_qualite(self):
        """XQHS22 — voir les montants du coût de la non-qualité QHSE (NCR/
        CAPA/incident). Permission ``cout_non_qualite_voir`` (même palier que
        ``marge_voir``/``prix_achat_voir``), repli historique pour les comptes
        légacy. Superuser toujours autorisé."""
        if self.is_superuser:
            return True
        if self.role_id:
            return 'cout_non_qualite_voir' in (self.role.permissions or [])
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

    # ── XPLT19 — accès multi-sociétés & société active ────────────────────────
    def societes_operables(self):
        """Liste des sociétés que ce compte peut opérer (home + M2M), dédupliquée.

        Un compte mono-société renvoie exactement {sa société} — il ne peut donc
        pas switcher (comportement inchangé)."""
        from authentication.active_company import companies_for_user
        return companies_for_user(self)

    def peut_operer_societe(self, company_id):
        """True si ce compte est membre de la société ``company_id`` (home ou
        ``societes_autorisees``). Un switch n'est autorisé que vers une société
        pour laquelle ceci est True."""
        from authentication.active_company import user_can_operate
        return user_can_operate(self, company_id)

    # ── Rotation forcée des identifiants (N96) — strictement OPT-IN ──────────
    # Drapeau de rotation : quand un administrateur le passe à True, l'utilisateur
    # est invité à changer son mot de passe à sa PROCHAINE session (le frontend
    # lit ``must_change_password`` dans /auth/me/ et force le formulaire). Le
    # changement de mot de passe efface le drapeau. Défaut False : AUCUN compte
    # existant n'est jamais verrouillé ni forcé — comportement inchangé tant
    # qu'un admin ne l'active pas explicitement.
    must_change_password = models.BooleanField(default=False)
    # ── FG22 — verrouillage de compte (par société, opt-in) ──────────────────
    # Compteur d'échecs CONSÉCUTIFS de connexion (remis à 0 sur succès) et date
    # de fin de verrouillage temporaire. Additifs, défaut inerte : tant que la
    # société n'active pas ``lockout_max_attempts`` (>0), rien ne se verrouille.
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    # Horodatage du dernier changement de mot de passe (informatif, affiché dans
    # l'onglet sécurité). Nullable : null pour tout compte qui n'a jamais changé
    # son mot de passe via le flux dédié — additif, aucun défaut imposé.
    password_changed_at = models.DateTimeField(null=True, blank=True)

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


class UserSession(models.Model):
    """Session de connexion visible et révocable (N96).

    Chaque connexion réussie crée une ligne tracée (appareil/navigateur, IP,
    horodatages) liée à l'utilisateur ET à sa société (multi-tenant). Le ``jti``
    du jeton de rafraîchissement permet de relier la session au jeton JWT et de
    le blacklister à la révocation. Additif : aucune session existante n'est
    affectée ; les comptes qui ne se reconnectent pas n'ont simplement aucune
    ligne tant qu'ils ne se connectent pas à nouveau.

    Révoquer une session = marquer ``revoked=True`` (elle disparaît de la liste)
    ET blacklister son jeton de rafraîchissement (via ``token_blacklist``) pour
    qu'il ne puisse plus rafraîchir d'accès."""

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='user_sessions',
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        'authentication.CustomUser',
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    # Identifiant du jeton de rafraîchissement (claim ``jti``) — sert à relier la
    # session au jeton JWT et à le blacklister. Indexé pour retrouver la session
    # courante d'une requête à partir de son cookie refresh.
    jti = models.CharField(max_length=255, db_index=True)
    user_agent = models.CharField(max_length=400, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    # NTSEC13 — empreinte d'appareil (hash SHA-256 de user_agent + plateforme).
    # À la première apparition d'une empreinte pour un utilisateur, une alerte
    # « appareil inconnu » est levée. Vide pour le legacy (aucune alerte).
    device_fingerprint = models.CharField(
        max_length=64, blank=True, default='', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    # Révocation : la session reste en base (trace) mais sort de la liste active.
    revoked = models.BooleanField(default=False)
    # NTSEC9 — horodatage de la dernière ré-authentification MFA (TOTP/passkey)
    # rattachée à CETTE session. Posé à la connexion quand un second facteur a
    # été vérifié ; lu par `apps.identity.stepup.require_recent_mfa` pour exiger
    # une MFA récente sur les actions sensibles. NULL = jamais de MFA récente
    # sur cette session (additif : les sessions existantes restent NULL).
    last_mfa_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Session utilisateur"
        verbose_name_plural = "Sessions utilisateur"
        ordering = ('-last_seen_at',)

    def __str__(self):
        return f"{self.user_id} — {self.user_agent[:40]}"
