from rest_framework.routers import DefaultRouter
from .views import CustomFieldDefViewSet

router = DefaultRouter()
router.register(r'definitions', CustomFieldDefViewSet)
urlpatterns = router.urls
