from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    RegisterCompanyView,
    UserViewSet,
    CompanyViewSet,
    MeView,
    LogoutView,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'companies', CompanyViewSet, basename='companies')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path(
        'auth/register-company/',
        RegisterCompanyView.as_view(),
        name='auth_register_company',
    ),
    path('auth/me/', MeView.as_view(), name='auth_me'),
    path('auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('', include(router.urls)),
]
