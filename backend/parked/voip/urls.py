from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AppelViewSet, MesIdentifiantsVoipView, VoipParametresView

router = DefaultRouter()
router.register(r'appels', AppelViewSet, basename='voip-appel')

urlpatterns = [
    path('parametres/', VoipParametresView.as_view(), name='voip-parametres'),
    path('mes-identifiants/', MesIdentifiantsVoipView.as_view(),
         name='voip-mes-identifiants'),
    path('', include(router.urls)),
]
