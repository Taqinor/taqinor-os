from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BlocReutilisableViewSet,
    KbArticleAclViewSet,
    KbArticleLienViewSet,
    KbArticleVersionViewSet,
    KbArticleViewSet,
    KbFavoriViewSet,
    KbLectureObligatoireViewSet,
    KbParcoursArticleViewSet,
    KbParcoursAssignationViewSet,
    KbParcoursViewSet,
    PartageArticleKbViewSet,
    public_article,
)

router = DefaultRouter()
router.register(r'articles', KbArticleViewSet)
router.register(r'versions', KbArticleVersionViewSet)
router.register(r'article-liens', KbArticleLienViewSet)
router.register(r'article-acls', KbArticleAclViewSet)
router.register(r'lectures-obligatoires', KbLectureObligatoireViewSet)
router.register(r'favoris', KbFavoriViewSet)
router.register(r'partages', PartageArticleKbViewSet)
router.register(r'parcours', KbParcoursViewSet)
router.register(r'parcours-articles', KbParcoursArticleViewSet)
router.register(r'parcours-assignations', KbParcoursAssignationViewSet)
router.register(r'blocs', BlocReutilisableViewSet)

urlpatterns = [
    # XKB19 — endpoint PUBLIC (sans login) AVANT le router : jeton opaque,
    # jamais confondu avec un pk numérique du router.
    path('public/<str:token>/', public_article, name='kb-public-article'),
    path('', include(router.urls)),
]
