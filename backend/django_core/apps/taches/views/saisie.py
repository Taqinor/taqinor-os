"""Saisie (reference/api.md §3.2, §4) : saisie rapide et capture (Siri, partage).

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; la
capture est authentifiée par le BOUCHON `JetonPasEncoreLivre` (401 neutre) tant que
`JetonAccesAuthentication` n'est pas livrée.
"""
from rest_framework.views import APIView

from apps.taches.views.base import AUTH_JETON, PERMISSIONS, PasEncore
from core.idempotency import IdempotentCreateMixin


class SaisieRapideVue(IdempotentCreateMixin, APIView):
    """POST saisie-rapide/ — analyse, aperçu (`apercu:true`) ou création."""

    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()


class CaptureVue(APIView):
    """POST capture/ — Siri / partage, jeton `capture` (J:capture)."""

    authentication_classes = AUTH_JETON
    permission_classes = PERMISSIONS

    def post(self, request):
        raise PasEncore()
