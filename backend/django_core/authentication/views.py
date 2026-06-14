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
from authentication.permissions import IsAdminRole

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
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access = response.data.pop('access', None)
            refresh = response.data.pop('refresh', None)
            _set_auth_cookies(response, access, refresh)
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
    """Create the 3 default system roles for a newly created company."""
    from apps.roles.models import (
        Role,
        ALL_PERMISSIONS,
        RESPONSABLE_PERMISSIONS,
        UTILISATEUR_PERMISSIONS,
    )
    defaults = [
        ('Administrateur', ALL_PERMISSIONS),
        ('Responsable', RESPONSABLE_PERMISSIONS),
        ('Utilisateur', UTILISATEUR_PERMISSIONS),
    ]
    roles = {}
    for nom, perms in defaults:
        role, _ = Role.objects.get_or_create(
            company=company,
            nom=nom,
            defaults={'permissions': perms, 'est_systeme': True},
        )
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
        admin_role = roles['Administrateur']

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
        response = Response({'detail': 'Deconnexion reussie.'})
        _clear_auth_cookies(response)
        return response


# ── Gestion utilisateurs (admin) ───────────────────────────────
class UserViewSet(viewsets.ModelViewSet):
    """Gestion des utilisateurs — admin voit uniquement sa company."""
    serializer_class = UserSerializer

    def get_permissions(self):
        return [IsAdminRole()]

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
