from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AccessReviewCampaignViewSet

router = DefaultRouter()
router.register(r'campaigns', AccessReviewCampaignViewSet,
                basename='accessreview-campaign')

urlpatterns = [
    path('', include(router.urls)),
]
