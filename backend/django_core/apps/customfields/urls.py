from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import CustomFieldDefViewSet, CustomObjectDefViewSet, CustomRecordViewSet

router = DefaultRouter()
router.register(r'definitions', CustomFieldDefViewSet)
router.register(r'objects', CustomObjectDefViewSet, basename='customobjectdef')

# XPLT16 — CRUD dynamique des enregistrements d'un objet personnalisé.
# object_code est un SlugField : le convertisseur <slug:...> le contraint
# suffisamment (lettres/chiffres/tirets) sans validation supplémentaire.
records_list = CustomRecordViewSet.as_view(
    {'get': 'list', 'post': 'create'})
records_detail = CustomRecordViewSet.as_view(
    {'get': 'retrieve', 'put': 'update', 'patch': 'partial_update',
     'delete': 'destroy'})
# NTEXT2/NTEXT3 — schémas d'affichage auto-générés (liste/formulaire) pour un
# objet personnalisé, réutilisant CustomRecordViewSet (résolution objet +
# permission par-objet identiques aux records).
records_vue_liste = CustomRecordViewSet.as_view({'get': 'vue_liste'})
records_vue_formulaire = CustomRecordViewSet.as_view({'get': 'vue_formulaire'})

# NTEXT34 — catalogue de MODÈLES d'objets prêts à l'emploi (lecture tout rôle)
# + installation pour la société (admin), idempotente.
objets_catalogue = CustomObjectDefViewSet.as_view({'get': 'objets_catalogue'})
objets_catalogue_installer = CustomObjectDefViewSet.as_view(
    {'post': 'installer_modele_catalogue'})

urlpatterns = [
    path('objets-catalogue/', objets_catalogue, name='objets-catalogue'),
    path('objets-catalogue/installer/<slug:code>/',
         objets_catalogue_installer, name='objets-catalogue-installer'),
    path('custom-objects/<slug:object_code>/records/',
         records_list, name='customrecord-list'),
    path('custom-objects/<slug:object_code>/records/<int:pk>/',
         records_detail, name='customrecord-detail'),
    path('custom-objects/<slug:object_code>/vue-liste/',
         records_vue_liste, name='customrecord-vue-liste'),
    path('custom-objects/<slug:object_code>/vue-formulaire/',
         records_vue_formulaire, name='customrecord-vue-formulaire'),
    path('', include(router.urls)),
]
