from django.urls import path
from .views import dry_run, commit
from .exports_view import export_list

urlpatterns = [
    path('dry-run/', dry_run, name='import-dry-run'),
    path('commit/', commit, name='import-commit'),
    path('export/<str:entity>/', export_list, name='export-list'),
]
