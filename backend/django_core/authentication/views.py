from django.conf import settings
from django.utils.text import slugify
from rest_framework import generics, permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import CustomUser, Company
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    CompanySerializer,
    CustomTokenObtainPairSerializer,
)
from .throttles import LoginRateThrottle, RegisterRateThrottle
from authentication.permissions import IsAdminRole, IsAdminOrResponsableTier

# ── Stratégie CSRF des cookies d'authentification (ERR45) ────────────────────
# Les jetons JWT sont posés en cookies ``httpOnly`` (jamais lisibles par JS, ce
# qui neutralise le vol de jeton par XSS). La protection CSRF des mutations
# authentifiées par cookie repose sur DEUX barrières complémentaires :
#   1. ``SameSite=Strict`` — le navigateur n'attache JAMAIS ces cookies à une
#      requête déclenchée depuis un autre site (origine), ce qui bloque les CSRF
#      classiques. C'est une INVARIANTE de sécurité : ne JAMAIS l'abaisser à
#      'Lax'/'None' sans introduire au préalable un jeton CSRF explicite
#      (double-submit / en-tête X-CSRFToken). Le test
#      ``tests_csrf.test_auth_cookies_are_samesite_strict`` verrouille cette
#      valeur pour qu'un relâchement silencieux casse la CI.
#   2. ``Secure`` en production (cookies HTTPS uniquement) — posé via
#      ``_COOKIE_SECURE`` ci-dessous, renforcé par ``SESSION/CSRF_COOKIE_SECURE``
#      et ``SECURE_SSL_REDIRECT`` dans settings/prod.py.
# Le frontend est servi depuis le même site eTLD+1 que l'API en production, donc
# 'Strict' n'empêche aucun usage légitime. Si une future intégration tierce
# cross-site devait poster avec ces cookies, il FAUDRAIT d'abord ajouter un flux
# de jeton CSRF complet avant d'assouplir SameSite — c'est un changement gardé.
_COOKIE_SECURE = not settings.DEBUG
_COOKIE_SAMESITE = 'Strict'
_ACCESS_MAX_AGE = int(
    settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
)
_REFRESH_MAX_AGE = int(
    settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
)


def _set_auth_cookies(response, access, refresh=None):
    """Positionne les cookies httpOnly sur la reponse Django."""
    response.set_cookie(
        'access_token', access,
        max_age=_ACCESS_MAX_AGE,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        path='/',
    )
    if refresh:
        response.set_cookie(
            'refresh_token', refresh,
            max_age=_REFRESH_MAX_AGE,
            httponly=True,
            secure=_COOKIE_SECURE,
            samesite=_COOKIE_SAMESITE,
            path='/',
        )


def _clear_auth_cookies(response):
    """Supprime les cookies d'authentification."""
    response.delete_cookie('access_token', path='/')
    response.delete_cookie('refresh_token', path='/')


# ── Login ──────────────────────────────────────────────────────
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        from rest_framework.exceptions import ValidationError
        # Double authentification (2FA, N96) : si le mot de passe est bon mais
        # qu'un code TOTP est requis/invalide, on renvoie une réponse 401 au
        # contour stable (`otp_required: true`) que le frontend sait gérer —
        # sans divulguer l'état 2FA d'un compte avant que le mot de passe soit
        # validé.
        try:
            response = super().post(request, *args, **kwargs)
        except ValidationError as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            if detail.get('otp_required'):
                msg = detail.get('detail')
                if isinstance(msg, (list, tuple)):
                    msg = msg[0] if msg else None
                msg = str(msg) if msg else 'Double authentification requise.'
                return Response(
                    {'otp_required': True, 'detail': msg},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            raise
        if response.status_code == 200:
            access = response.data.pop('access', None)
            refresh = response.data.pop('refresh', None)
            _set_auth_cookies(response, access, refresh)
            # Journal d'activité (Feature G) — connexion réussie. Best-effort.
            try:
                from apps.audit.recorder import record
                from apps.audit.models import AuditLog
                # ERR92 — sur un login RÉUSSI, normaliser actor_username depuis
                # l'objet utilisateur résolu (autorité), jamais depuis la chaîne
                # request.data['username'] brute (qui peut différer en casse ou
                # être truquée). On résout par username insensible à la casse.
                raw_uname = (request.data.get('username') or '').strip()
                u = CustomUser.objects.filter(
                    username__iexact=raw_uname).first()
                actor = u.username if u is not None else raw_uname
                record(AuditLog.Action.LOGIN, user=u, actor_username=actor,
                       company=getattr(u, 'company', None), detail='Connexion')
            except Exception:
                pass
        return response


# ── Refresh cookie ──────────────────────────────────────────────
class CookieTokenRefreshView(APIView):
    """
    Renouvelle le access_token depuis le cookie refresh_token.
    Le client n'a pas besoin d'envoyer quoi que ce soit dans le body.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_raw = request.COOKIES.get('refresh_token')
        if not refresh_raw:
            return Response(
                {'detail': 'Refresh token manquant.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            token = RefreshToken(refresh_raw)
            access = str(token.access_token)
            new_refresh = str(token) if settings.SIMPLE_JWT.get(
                'ROTATE_REFRESH_TOKENS', False
            ) else None
            response = Response({'detail': 'Token rafraichi.'})
            _set_auth_cookies(response, access, new_refresh)
            return response
        except TokenError:
            resp = Response(
                {'detail': 'Refresh token invalide ou expire.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_auth_cookies(resp)
            return resp


# ── Inscription d'un utilisateur dans une entreprise existante ─
class RegisterView(generics.CreateAPIView):
    """Admin cree un utilisateur dans sa propre entreprise."""
    queryset = CustomUser.objects.all()
    permission_classes = [IsAdminRole]
    serializer_class = RegisterSerializer
    throttle_classes = [RegisterRateThrottle]

    def get_serializer_context(self):
        from apps.roles.models import Role
        ctx = super().get_serializer_context()
        ctx['company'] = self.request.user.company
        role_id = self.request.data.get('role')
        if role_id and self.request.user.company:
            try:
                ctx['role'] = Role.objects.get(
                    pk=role_id,
                    company=self.request.user.company,
                )
            except Role.DoesNotExist:
                ctx['role'] = None
        return ctx


def _create_system_roles(company):
    """Create the canonical system roles for a newly created company (Feature D).

    Seeds the seven roles + the two legacy ones; returns {nom: Role}.

    Idempotent ET auto-réparateur (N103) : si une ligne du même nom préexiste
    avec ``est_systeme=False`` (rôle personnalisé qui a heurté le nom canonique),
    on la promeut en rôle système. Sans cela, un « Directeur »/« Administrateur »
    laissé ``est_systeme=False`` résoudrait à tort au palier limité et perdrait
    l'accès aux écrans Utilisateurs/Rôles. Additif : ne supprime jamais une ligne
    et ne touche pas aux permissions déjà posées."""
    from apps.roles.models import Role, CANONICAL_SYSTEM_ROLES
    roles = {}
    for nom, perms in CANONICAL_SYSTEM_ROLES:
        role, created = Role.objects.get_or_create(
            company=company,
            nom=nom,
            defaults={'permissions': list(perms), 'est_systeme': True},
        )
        if not created and not role.est_systeme:
            role.est_systeme = True
            role.save(update_fields=['est_systeme'])
        roles[nom] = role
    return roles


# ── Creation d'une nouvelle entreprise (onboarding SaaS) ───────
class RegisterCompanyView(generics.GenericAPIView):
    """
    POST /api/django/auth/register-company/
    Cree une nouvelle entreprise + un administrateur.
    Endpoint public pour l'onboarding SaaS.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]
    serializer_class = RegisterSerializer  # requis par DRF GenericAPIView

    def post(self, request):
        company_nom = request.data.get('company_nom', '').strip()
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        email = request.data.get('email', '').strip()

        errors = {}
        if not company_nom:
            errors['company_nom'] = ["Ce champ est requis."]
        if not username:
            errors['username'] = ["Ce champ est requis."]
        if not password:
            errors['password'] = ["Ce champ est requis."]
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        if CustomUser.objects.filter(username=username).exists():
            return Response(
                {'username': ["Ce nom d'utilisateur est deja utilise."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slug_base = slugify(company_nom) or 'company'
        slug = slug_base
        i = 1
        while Company.objects.filter(slug=slug).exists():
            slug = f"{slug_base}-{i}"
            i += 1

        company = Company.objects.create(nom=company_nom, slug=slug)

        from apps.parametres.models import CompanyProfile
        CompanyProfile.objects.get_or_create(
            company=company,
            defaults={'nom': company_nom},
        )

        roles = _create_system_roles(company)
        # Le propriétaire fondateur de la nouvelle société est Directeur (accès
        # total + Journal d'activité), pour qu'il y ait au moins un Directeur.
        admin_role = roles['Directeur']

        # Types d'activité par défaut (style Odoo) pour la nouvelle société.
        try:
            from apps.records.models import ActivityType
            for nom, icone, ordre, delai in [
                ('Appel', '📞', 10, 0), ('Email', '✉️', 20, 0),
                ('Réunion', '👥', 30, 0), ('Relance', '📅', 40, 3),
                ('À faire', '✔️', 50, 0),
            ]:
                ActivityType.objects.get_or_create(
                    company=company, nom=nom,
                    defaults={'icone': icone, 'ordre': ordre,
                              'delai_defaut_jours': delai, 'est_systeme': True})
        except Exception:
            pass

        # Niveaux de relance par défaut (J+7 / J+15 / J+30).
        try:
            from apps.ventes.models import FollowupLevel
            for ordre, nom, delai in [
                (1, 'Rappel courtois', 7), (2, 'Relance', 15),
                (3, 'Relance ferme', 30),
            ]:
                FollowupLevel.objects.get_or_create(
                    company=company, ordre=ordre,
                    defaults={'nom': nom, 'delai_jours': delai})
        except Exception:
            pass

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            role_legacy=CustomUser.ROLE_ADMIN,
            role=admin_role,
            company=company,
        )

        return Response({
            'detail': 'Entreprise creee avec succes.',
            'company_id': company.id,
            'company_nom': company.nom,
            'username': user.username,
        }, status=status.HTTP_201_CREATED)


# ── Profil courant ─────────────────────────────────────────────
class MeView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


# ── Logout securise ────────────────────────────────────────────
class LogoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_raw = (
            request.COOKIES.get('refresh_token')
            or request.data.get('refresh')
        )
        if refresh_raw:
            try:
                token = RefreshToken(refresh_raw)
                token.blacklist()
            except TokenError:
                pass
        # Journal d'activité (Feature G) — déconnexion. Best-effort.
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(AuditLog.Action.LOGOUT, user=request.user,
                   detail='Déconnexion')
        except Exception:
            pass
        response = Response({'detail': 'Deconnexion reussie.'})
        _clear_auth_cookies(response)
        return response


# ── Gestion utilisateurs (admin) ───────────────────────────────
class UserViewSet(viewsets.ModelViewSet):
    """Gestion des utilisateurs — Administrateur et Responsable, scoped company."""
    serializer_class = UserSerializer

    def get_permissions(self):
        # Écran Utilisateurs ouvert au Responsable (promu) en plus de
        # l'Administrateur ; le palier limité reste bloqué.
        return [IsAdminOrResponsableTier()]

    def get_queryset(self):
        user = self.request.user
        if user.company_id:
            return (
                CustomUser.objects
                .filter(company=user.company)
                .select_related('role')
                .order_by('date_joined')
            )
        if user.is_superuser:
            return CustomUser.objects.all().order_by('date_joined')
        return CustomUser.objects.none()

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='avatar',
            parser_classes=[MultiPartParser])
    def avatar(self, request, pk=None):
        """Téléverse/remplace la photo de profil d'un employé (admin).

        Stockée dans MinIO (bucket erp-uploads) via boto3, comme le logo
        d'entreprise. La photo appartient à l'employé : elle apparaît ensuite
        sur tous ses leads (responsable)."""
        from .avatars import store_avatar
        target = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        key, err = store_avatar(file, target.avatar_key)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_400_BAD_REQUEST)
        target.avatar_key = key
        target.save(update_fields=['avatar_key'])
        return Response(
            UserSerializer(target, context={'request': request}).data)

    def _role_grants_admin(self, target, role_id):
        """L'utilisateur serait-il admin avec ce nouveau rôle ?"""
        if target.is_superuser:
            return True
        if role_id in (None, '', 'null'):
            # Rôle vidé → on retombe sur le legacy.
            return target.role_legacy == CustomUser.ROLE_ADMIN
        from apps.roles.models import Role
        role = Role.objects.filter(pk=role_id).first()
        return bool(role and 'roles_gerer' in (role.permissions or []))

    def update(self, request, *args, **kwargs):
        target = self.get_object()
        data = request.data
        # Détecte une rétrogradation (perte du rôle admin) ou une
        # désactivation du compte.
        retro = False
        if 'role' in data and target.is_admin_role \
                and not self._role_grants_admin(target, data.get('role')):
            retro = True
        if 'is_active' in data and \
                str(data.get('is_active')).lower() in ('false', '0', ''):
            retro = True
        if retro:
            if target.is_protected:
                return Response(
                    {'detail': 'Ce compte propriétaire est protégé : il ne '
                               'peut pas être rétrogradé ni désactivé.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if target.est_dernier_proprietaire():
                return Response(
                    {'detail': 'Impossible de rétrograder le dernier '
                               'propriétaire : le système doit toujours '
                               'garder un administrateur.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        target = self.get_object()
        if target == request.user:
            return Response(
                {'detail': 'Vous ne pouvez pas supprimer votre propre compte.'},  # noqa: E501
                status=status.HTTP_400_BAD_REQUEST,
            )
        if target.is_protected:
            return Response(
                {'detail': 'Ce compte propriétaire est protégé : il ne peut '
                           'pas être supprimé.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if target.is_superuser:
            return Response(
                {'detail': 'Ce compte ne peut pas être supprimé via l\'ERP.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if target.est_dernier_proprietaire():
            return Response(
                {'detail': 'Impossible de supprimer le dernier propriétaire : '
                           'le système doit toujours garder un administrateur.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


# ── Gestion des entreprises (superuser uniquement) ─────────────
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all().order_by('date_creation')
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAdminUser]


# ── Double authentification (2FA TOTP) — opt-in par utilisateur (N96) ──────
_TOTP_ISSUER = 'TAQINOR OS'


def _generate_recovery_codes(n=8):
    """Génère ``n`` codes de secours en clair (8 caractères base32 lisibles).

    Retourne (codes_en_clair, codes_hachés). On ne montre les codes en clair
    qu'UNE seule fois, à l'activation ; en base on ne garde que les hachages."""
    import secrets
    from django.contrib.auth.hashers import make_password
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    plain = [
        ''.join(secrets.choice(alphabet) for _ in range(8))
        for _ in range(n)
    ]
    hashed = [make_password(c) for c in plain]
    return plain, hashed


class TwoFactorSetupView(APIView):
    """POST — démarre la configuration 2FA pour l'utilisateur connecté.

    Génère un nouveau secret TOTP et l'URI otpauth (pour le QR code), persiste
    le secret SANS activer le 2FA (``totp_enabled`` reste False). Tant que le
    secret n'est pas vérifié, la connexion n'est jamais bloquée."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import pyotp
        user = request.user
        if user.totp_enabled:
            return Response(
                {'detail': 'La double authentification est déjà activée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = False
        user.save(update_fields=['totp_secret', 'totp_enabled'])
        label = user.email or user.username
        uri = pyotp.TOTP(secret).provisioning_uri(
            name=label, issuer_name=_TOTP_ISSUER,
        )
        return Response({
            'secret': secret,
            'otpauth_uri': uri,
            'issuer': _TOTP_ISSUER,
            'label': label,
        })


class TwoFactorEnableView(APIView):
    """POST — vérifie un premier code et active le 2FA.

    Corps : ``{"code": "123456"}``. Sur succès : ``totp_enabled=True`` et
    renvoie une liste de codes de secours à usage unique (montrés une seule
    fois)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import pyotp
        user = request.user
        if user.totp_enabled:
            return Response(
                {'detail': 'La double authentification est déjà activée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.totp_secret:
            return Response(
                {'detail': "Aucune configuration en cours. Démarrez d'abord "
                           "la configuration de la double authentification."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        code = str(request.data.get('code', '')).strip().replace(' ', '')
        if not pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
            return Response(
                {'detail': 'Code invalide. Vérifiez le code à 6 chiffres de '
                           'votre application d\'authentification.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        plain, hashed = _generate_recovery_codes()
        user.totp_enabled = True
        user.totp_recovery_codes = hashed
        user.save(update_fields=['totp_enabled', 'totp_recovery_codes'])
        return Response({
            'detail': 'Double authentification activée.',
            'recovery_codes': plain,
        })


class TwoFactorDisableView(APIView):
    """POST — désactive le 2FA. Exige un code TOTP/secours valide OU le mot de
    passe du compte. Efface le secret et les codes de secours."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.totp_enabled:
            return Response(
                {'detail': 'La double authentification n\'est pas activée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        code = request.data.get('code', '')
        password = request.data.get('password', '')
        ok = False
        if code and user.verify_totp(code):
            ok = True
        elif password and user.check_password(password):
            ok = True
        if not ok:
            return Response(
                {'detail': 'Vérification requise : fournissez un code valide '
                           'ou votre mot de passe pour désactiver la double '
                           'authentification.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.totp_enabled = False
        user.totp_secret = None
        user.totp_recovery_codes = []
        user.save(update_fields=[
            'totp_enabled', 'totp_secret', 'totp_recovery_codes'])
        return Response({'detail': 'Double authentification désactivée.'})


class TwoFactorStatusView(APIView):
    """GET — état du 2FA pour l'utilisateur connecté (affichage Paramètres)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'enabled': bool(user.totp_enabled),
            'recovery_codes_remaining': len(user.totp_recovery_codes or []),
        })
