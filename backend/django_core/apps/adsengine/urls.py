"""Routes du moteur publicitaire Meta Ads, montées sous
``/api/django/adsengine/`` (voir ``erp_agentique/urls.py``).

ENG1 n'expose que ``status/``. Les routeurs ViewSet (connexion, garde-fous,
actions) s'ajoutent ici aux tâches suivantes de la lane.
"""
from django.urls import path

from .views import StatusView

urlpatterns = [
    path('status/', StatusView.as_view(), name='adsengine-status'),
]
