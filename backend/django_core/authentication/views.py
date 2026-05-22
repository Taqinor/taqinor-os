from django.utils.text import slugify
from rest_framework import generics, permissions, viewsets, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
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


# ── Login ──────────────────────────────────────────────────────
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]


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
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass
        return Response({'detail': 'Deconnexion reussie.'})


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

    def destroy(self, request, *args, **kwargs):
        target = self.get_object()
        if target == request.user:
            return Response(
                {'detail': 'Vous ne pouvez pas supprimer votre propre compte.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if target.is_superuser:
            return Response(
                {'detail': 'Ce compte ne peut pas être supprimé via l\'ERP.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


# ── Gestion des entreprises (superuser uniquement) ─────────────
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all().order_by('date_creation')
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAdminUser]
