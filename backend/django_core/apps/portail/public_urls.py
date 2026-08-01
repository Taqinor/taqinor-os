"""NTPRT19 — Routes PUBLIQUES du module portail (sans login).

Montées sous ``api/django/public/portail/`` (même convention que
``ventes``/``sav``/``stock``/``contrats``…). Le préfixe ``public`` est exempté
du middleware de modules désactivés : la page de login d'un tenant doit
toujours pouvoir se brander.
"""
from django.urls import path

from .public_views import theme_portail_public

urlpatterns = [
    path('theme/', theme_portail_public, name='portail-theme-public'),
]
