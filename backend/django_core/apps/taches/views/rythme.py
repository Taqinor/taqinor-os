"""Rythme, cartes à réponse, préférences dites et en-tête du Copilote (reference/api.md §3.4, §4).

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction.
"""
from rest_framework.views import APIView

from apps.taches.views.base import PERMISSIONS, PasEncore


class RythmeVue(APIView):
    """GET rythme/ (RYTHME) · POST rythme/ `{"mode","objectif"?,"sens"?}` (seul chemin du mode)."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()

    def post(self, request):
        raise PasEncore()


class RepondrePropositionVue(APIView):
    """POST rythme/propositions/{id}/repondre/ — `{"reponse"}`, toute carte à réponse."""

    permission_classes = PERMISSIONS

    def post(self, request, id):
        raise PasEncore()


class PreferencesVue(APIView):
    """POST preferences/ — poser `{"cle","valeur"}` → RYTHME."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class PreferenceVue(APIView):
    """DELETE preferences/{cle}/ — retirer une préférence dite → RYTHME."""

    permission_classes = PERMISSIONS

    def delete(self, request, cle):
        raise PasEncore()


class CoachEnteteVue(APIView):
    """GET coach/entete/ — deux lignes (≤ 300 caractères) pour le relais du Copilote."""

    permission_classes = PERMISSIONS

    def get(self, request):
        raise PasEncore()
