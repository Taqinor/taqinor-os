"""NTPRT19 — Routes PUBLIQUES du module portail (sans login).

Montées sous ``api/django/public/portail/`` (même convention que
``ventes``/``sav``/``stock``/``contrats``…). Le préfixe ``public`` est exempté
du middleware de modules désactivés : la page de login d'un tenant doit
toujours pouvoir se brander.
"""
from django.urls import path

from .public_views import (
    accepter_invitation_portail_public,
    portail_mon_releve,
    theme_portail_public,
)

urlpatterns = [
    path('theme/', theme_portail_public, name='portail-theme-public'),
    # NTPRT6 — l'invité pose son mot de passe via le lien reçu par email.
    path('invitations/accepter/', accepter_invitation_portail_public,
         name='portail-invitation-accepter'),
    # XFAC26/AUD148 — relevé de compte self-service par lien tokenisé (voir
    # le commentaire de tête de ``portail_mon_releve`` dans public_views.py).
    path('<str:token>/mon-releve/', portail_mon_releve,
         name='portail-mon-releve'),
]
