from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from authentication.views import CustomTokenObtainPairView

urlpatterns = [
    path('api/django/admin/', admin.site.urls),
    # JWT Auth endpoints
    path('api/django/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/django/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/django/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    # App URLs
    path('api/django/', include('authentication.urls')),
    path('api/django/stock/', include('apps.stock.urls')),
    path('api/django/crm/', include('apps.crm.urls')),
    path('api/django/ventes/', include('apps.ventes.urls')),
    path('api/django/parametres/', include('apps.parametres.urls')),
    path('api/django/roles/', include('apps.roles.urls')),
]
