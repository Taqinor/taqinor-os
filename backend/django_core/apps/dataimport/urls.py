from django.urls import path
from .views import dry_run, commit, save_mapping, job_erreurs_csv
from .exports_view import export_list
# N97 — export configurable & sauvegarde (s'ajoute à côté de l'import).
from .export_views import export_objects_list, export_object, sauvegarde

urlpatterns = [
    path('dry-run/', dry_run, name='import-dry-run'),
    path('commit/', commit, name='import-commit'),
    # XPLT2 — mapping sauvegardé + CSV des lignes en échec d'un job d'import.
    path('mapping/', save_mapping, name='import-save-mapping'),
    path('jobs/<int:job_id>/erreurs.csv', job_erreurs_csv, name='import-job-erreurs'),
    path('export/<str:entity>/', export_list, name='export-list'),
    # N97 — export configurable / sauvegarde complète (admin uniquement).
    path('export-objects/', export_objects_list, name='export-objects'),
    path('export-object/', export_object, name='export-object'),
    path('sauvegarde/', sauvegarde, name='export-sauvegarde'),
]
