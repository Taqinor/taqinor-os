from django.urls import path
from .views import dry_run, commit

urlpatterns = [
    path('dry-run/', dry_run, name='import-dry-run'),
    path('commit/', commit, name='import-commit'),
]
