from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AccessReviewCampaignViewSet, SodRuleViewSet

router = DefaultRouter()
router.register(r'campaigns', AccessReviewCampaignViewSet,
                basename='accessreview-campaign')
router.register(r'sod-rules', SodRuleViewSet, basename='accessreview-sod')

urlpatterns = [
    path('', include(router.urls)),
]
