from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import CustomUser, Company, UserSession


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        # SCA46 — expose le consentement benchmarking (Boolean, défaut False,
        # opt-in strict). Aucune agrégation construite : le CONSENTEMENT est la
        # donnée (voir NTDATA46 — toute future agrégation pointe ce champ).
        fields = ('id', 'nom', 'slug', 'actif', 'benchmarking_opt_in',
                  'date_creation')
        read_only_fields = ('id', 'slug', 'date_creation')


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    # Double authentification (2FA TOTP) — opt-in (N96). Champ optionnel : il
    # n'est EXIGÉ que si l'utilisateur a activé le 2FA. Un compte sans 2FA se
    # connecte exactement comme avant (le champ est ignoré).
    otp = serializers.CharField(
        required=False, allow_blank=True, write_only=True,
    )

    def validate(self, attrs):
        # On laisse d'abord la validation standard authentifier (username +
        # mot de passe). Si elle échoue, l'erreur d'identifiants est levée ici
        # avant qu'on parle de 2FA — on ne révèle jamais l'état 2FA d'un compte
        # avant d'avoir prouvé le mot de passe.
        otp = (self.initial_data.get('otp') or '').strip()
        data = super().validate(attrs)
        user = self.user
        # SCA18 — refuse d'émettre un JWT pour un tenant NON actif (suspendu ou
        # en fermeture). Vérifié APRÈS l'authentification (mot de passe prouvé),
        # message français. Un superuser (support/console) reste exempté pour
        # pouvoir intervenir. Un tenant actif est inchangé.
        if user is not None and not getattr(user, 'is_superuser', False):
            company = getattr(user, 'company', None)
            if company is not None and not getattr(
                    company, 'est_operationnel', True):
                raise serializers.ValidationError(
                    {'detail': "Ce compte société est suspendu. Contactez "
                               "l'administrateur."},
                    code='tenant_suspendu',
                )
        if user is not None and getattr(user, 'totp_enabled', False):
            if not otp:
                # Signal clair que le 2FA est requis : le frontend déclenche la
                # saisie du code à 6 chiffres et resoumet.
                raise serializers.ValidationError(
                    {'otp_required': True,
                     'detail': 'Double authentification requise.'},
                    code='otp_required',
                )
            if not user.verify_totp(otp):
                raise serializers.ValidationError(
                    {'otp_required': True,
                     'detail': 'Code de double authentification invalide.'},
                    code='otp_invalid',
                )
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        # Backward compat: legacy role string ('admin'/'responsable'/'normal')
        token['role'] = user.role_legacy
        # Palier de menu faisant autorité, dérivé du NOUVEAU rôle.
        token['menu_tier'] = user.menu_tier
        token['role_nom'] = user.role.nom if user.role else None
        token['permissions'] = (
            list(user.role.permissions) if user.role else []
        )
        token['is_superuser'] = user.is_superuser
        token['company_id'] = user.company_id
        token['company_nom'] = (
            user.company.nom if user.company else None
        )
        # XPLT19 — société ACTIVE. À la connexion elle vaut la société d'attache
        # (``company_id``) : comportement byte-identique pour un mono-société.
        # Un switch (``/auth/switch-company/``) réémet des jetons portant l'id de
        # la société choisie (membre uniquement). ``CookieJWTAuthentication``
        # lit ce claim à chaque requête et borne ``request.user.company``.
        from authentication.active_company import ACTIVE_COMPANY_CLAIM
        token[ACTIVE_COMPANY_CLAIM] = user.company_id
        return token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        default=None,
        read_only=True,
    )

    # FG21 — onboarding : l'admin peut cocher « doit changer son mot de passe à
    # la première connexion ». Optionnel, défaut False → comportement inchangé
    # (l'admin pose un mot de passe utilisable tel quel tant qu'il ne coche pas).
    must_change_password = serializers.BooleanField(
        required=False, default=False)

    class Meta:
        model = CustomUser
        fields = (
            'username', 'password', 'email',
            'first_name', 'last_name', 'role', 'must_change_password',
        )

    def create(self, validated_data):
        from apps.roles.models import Role
        company = self.context.get('company')
        role = self.context.get('role')

        # Default to the company's "Utilisateur" system role
        if role is None and company:
            role = Role.objects.filter(
                company=company, nom='Utilisateur'
            ).first()

        validated_data.pop('role', None)
        must_change = validated_data.pop('must_change_password', False)
        # role_legacy doit suivre le palier du Role assigné (Administrateur →
        # 'admin', Responsable → 'responsable', sinon 'normal'). Le figer à
        # 'normal' donnait à tort le menu limité aux comptes admin/responsable.
        role_legacy = CustomUser.tier_for_role(role) or CustomUser.ROLE_NORMAL
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role_legacy=role_legacy,
            role=role,
            company=company,
        )
        # FG21 — force la rotation à la première connexion si demandé.
        if must_change:
            user.must_change_password = True
            user.save(update_fields=['must_change_password'])
        return user


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    company_nom = serializers.CharField(
        source='company.nom', read_only=True
    )
    role_nom = serializers.CharField(
        source='role.nom', read_only=True
    )
    # Palier de menu faisant autorité, dérivé du NOUVEAU rôle (jamais du legacy).
    menu_tier = serializers.ReadOnlyField()
    permissions = serializers.SerializerMethodField()
    # ODX6 — clés des modules explicitement DÉSACTIVÉS pour la société de
    # l'utilisateur (lecture seule), servies au bootstrap pour que la nav
    # frontend masque ces modules et que le routeur bloque leurs routes. Défaut
    # (aucun toggle) = liste vide ⇒ nav strictement identique à aujourd'hui.
    modules_desactives = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    # Superviseur direct (Feature E) — assignable par un Directeur/Admin dans
    # Paramètres → Équipe. Nom en lecture seule pour l'affichage.
    supervisor_nom = serializers.CharField(
        source='supervisor.username', read_only=True
    )
    # DC17 — référentiel des postes (FG160) : intitulé normalisé du Poste lié,
    # exposé en LECTURE SEULE pour l'affichage. Le champ écrivable reste le texte
    # libre ``poste`` (comportement inchangé) ; ``poste_ref`` est rattaché par la
    # migration de dédup et le restera via les écrans RH. ``source`` accède au FK
    # sans importer ``rh.models`` côté authentication.
    poste_ref_intitule = serializers.CharField(
        source='poste_ref.intitule', read_only=True, default=None
    )
    # XPLT19 — accès multi-sociétés : liste des sociétés opérables (home + M2M)
    # + société ACTIVE courante. Lecture seule ; sert au sélecteur d'entête. Un
    # compte mono-société renvoie une liste à un élément (pas de sélecteur).
    societes_operables = serializers.SerializerMethodField()
    active_company_id = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'role_nom', 'role_legacy', 'menu_tier', 'permissions',
            'modules_desactives',
            'poste', 'poste_ref', 'poste_ref_intitule',
            'avatar_key', 'avatar_url',
            'supervisor', 'supervisor_nom',
            'societes_operables', 'active_company_id',
            'is_active', 'is_superuser', 'is_protected',
            # Rotation forcée des identifiants (N96). ``must_change_password`` est
            # piloté par un admin (UserViewSet) pour forcer un changement à la
            # prochaine session, et lu par le frontend depuis /auth/me/. Défaut
            # False → aucun compte forcé tant qu'un admin ne l'active pas.
            # ``password_changed_at`` est calculé côté serveur (lecture seule).
            'must_change_password', 'password_changed_at',
            'password', 'date_joined', 'last_login',
            'company_id', 'company_nom',
        )
        read_only_fields = (
            'id', 'date_joined', 'last_login',
            'company_id', 'company_nom',
            'societes_operables', 'active_company_id',
            'password_changed_at',
            'role_nom', 'role_legacy', 'menu_tier', 'permissions',
            'modules_desactives',
            # DC17 — le référentiel poste ne se pose PAS par un PATCH direct du
            # corps utilisateur (multi-tenant : jamais de Poste cross-société lu
            # de la requête). Il est rattaché par la migration de dédup puis géré
            # via les écrans RH ; ici lecture seule. Le texte libre ``poste``
            # reste, lui, écrivable (comportement inchangé).
            'poste_ref', 'poste_ref_intitule',
            # avatar_key se pilote par l'endpoint d'upload dédié, jamais par
            # un PATCH direct du corps ; avatar_url est calculé (présigné).
            'avatar_key', 'avatar_url',
            # is_protected ne se pilote PAS via l'API (pas de privilège qui
            # se donne tout seul) : seulement par le seed et la commande de
            # récupération serveur.
            'is_superuser', 'is_protected',
        )

    def get_permissions(self, obj):
        if obj.role:
            return obj.role.permissions or []
        return []

    def get_modules_desactives(self, obj):
        """ODX6 — clés des modules désactivés pour la société de l'utilisateur.

        Source unique : ``core.feature_flags.modules_desactives`` (état
        ``ModuleToggle`` — ODX3). ``core`` est une app de fondation, sa lecture
        depuis ``authentication`` est autorisée. Aucune société / absence de
        toggle ⇒ liste vide (comportement par défaut inchangé). Best-effort :
        jamais bloquant pour ``/auth/me/``."""
        try:
            from core.feature_flags import modules_desactives
            return sorted(modules_desactives(getattr(obj, 'company', None)))
        except Exception:
            return []

    def get_societes_operables(self, obj):
        """Sociétés que ce compte peut opérer (home + M2M), dédupliquées."""
        try:
            return [
                {'id': c.id, 'nom': c.nom, 'slug': c.slug}
                for c in obj.societes_operables()
            ]
        except Exception:
            return []

    def get_active_company_id(self, obj):
        """Société ACTIVE de la requête courante — c'est ``obj.company`` qui a
        déjà été bornée par ``ActiveCompanyMiddleware``/``CookieJWTAuthentication``
        (elle vaut la société d'attache sans switch actif)."""
        return getattr(obj, 'company_id', None)

    def validate_role(self, value):
        """Le rôle assigné doit appartenir à l'entreprise de l'assignateur, et
        seul un administrateur peut octroyer un rôle de palier admin (ERR21).

        Sans ce contrôle, ``UserViewSet`` (ouvert au Responsable promu) acceptait
        un PK de rôle arbitraire : un manager pouvait assigner le rôle d'un AUTRE
        tenant, ou le rôle Administrateur local, pour escalader un compte."""
        if value is None:
            return value
        request = self.context.get('request')
        actor = getattr(request, 'user', None)
        company = getattr(actor, 'company', None)
        # Multi-tenant : le rôle doit être de la société de l'assignateur.
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                "Ce rôle n'appartient pas à votre entreprise.")
        # Tier : seul un administrateur (roles_gerer/superuser) peut octroyer un
        # rôle de palier admin. Un Responsable ne peut pas fabriquer un admin.
        from .models import CustomUser
        if CustomUser.tier_for_role(value) == CustomUser.ROLE_ADMIN \
                and actor is not None \
                and not getattr(actor, 'is_admin_role', False):
            raise serializers.ValidationError(
                "Seul un administrateur peut assigner un rôle administrateur.")
        return value

    def validate_supervisor(self, value):
        """Le superviseur doit être dans la même entreprise, jamais soi-même,
        et ne jamais engendrer de cycle dans la chaîne de supervision."""
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Superviseur hors de votre entreprise.')
        if self.instance is not None and value.id == self.instance.id:
            raise serializers.ValidationError(
                "Un utilisateur ne peut pas être son propre superviseur.")
        # VX235(b) — avant ce garde, seule l'auto-supervision directe était
        # bloquée : un cycle A→B→C→A (poser le superviseur de A sur C, qui
        # remonte déjà à B puis A) corrompait silencieusement
        # `records_scope_sous_arbre` (parcours d'arbre supposé acyclique).
        # Remonte la chaîne de superviseurs de `value` (borne 20 sauts) et
        # rejette si `self.instance` y apparaît déjà.
        if self.instance is not None:
            seen = value.supervisor
            for _ in range(20):
                if seen is None:
                    break
                if seen.id == self.instance.id:
                    raise serializers.ValidationError(
                        'Ce superviseur créerait un cycle dans la chaîne '
                        'de supervision.')
                seen = seen.supervisor
        return value

    def get_avatar_url(self, obj):
        from .avatars import presign_avatar
        return presign_avatar(obj.avatar_key)

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        # role_legacy suit le palier du Role assigné (sinon il resterait au
        # défaut 'normal' et l'admin/responsable hériterait du menu limité).
        if 'role' in validated_data:
            user.role_legacy = (
                CustomUser.tier_for_role(validated_data.get('role'))
                or CustomUser.ROLE_NORMAL
            )
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # Quand le rôle change, role_legacy doit se réaligner sur son palier —
        # sinon le menu reste figé sur l'ancien palier (dérive legacy).
        if 'role' in validated_data:
            instance.role_legacy = (
                CustomUser.tier_for_role(validated_data.get('role'))
                or CustomUser.ROLE_NORMAL
            )
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UserSessionSerializer(serializers.ModelSerializer):
    """Session active visible (N96). ``is_current`` marque la session de
    l'appareil courant pour l'UI (« cet appareil »). Le ``jti`` n'est jamais
    exposé."""
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = (
            'id', 'user_agent', 'ip_address',
            'created_at', 'last_seen_at', 'is_current',
        )
        read_only_fields = fields

    def get_is_current(self, obj):
        current_jti = self.context.get('current_jti')
        return bool(current_jti and obj.jti == current_jti)
