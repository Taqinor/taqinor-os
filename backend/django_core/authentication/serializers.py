from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import CustomUser, Company


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ('id', 'nom', 'slug', 'actif', 'date_creation')
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
        return token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.PrimaryKeyRelatedField(
        required=False,
        allow_null=True,
        default=None,
        read_only=True,
    )

    class Meta:
        model = CustomUser
        fields = (
            'username', 'password', 'email',
            'first_name', 'last_name', 'role',
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
    avatar_url = serializers.SerializerMethodField()
    # Superviseur direct (Feature E) — assignable par un Directeur/Admin dans
    # Paramètres → Équipe. Nom en lecture seule pour l'affichage.
    supervisor_nom = serializers.CharField(
        source='supervisor.username', read_only=True
    )

    class Meta:
        model = CustomUser
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'role_nom', 'role_legacy', 'menu_tier', 'permissions',
            'poste', 'avatar_key', 'avatar_url',
            'supervisor', 'supervisor_nom',
            'is_active', 'is_superuser', 'is_protected',
            'password', 'date_joined', 'last_login',
            'company_id', 'company_nom',
        )
        read_only_fields = (
            'id', 'date_joined', 'last_login',
            'company_id', 'company_nom',
            'role_nom', 'role_legacy', 'menu_tier', 'permissions',
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

    def validate_supervisor(self, value):
        """Le superviseur doit être dans la même entreprise et jamais soi-même."""
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
