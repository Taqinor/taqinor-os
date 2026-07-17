"""API onboarding (NTDMO13) — checklist « Premiers pas » de l'utilisateur.

Endpoints (company + user scopés côté serveur, jamais lus du corps) :

* ``GET  /api/django/onboarding/progress/`` — checklist résolue + résumé ;
* ``POST /api/django/onboarding/progress/{item_id}/ignorer/`` — masque un item ;
* ``POST /api/django/onboarding/progress/ignorer-tout/`` — masque tout le reste.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .selectors import resume_pour_utilisateur


class OnboardingProgressViewSet(viewsets.ViewSet):
    """Checklist « Premiers pas » de l'utilisateur courant (company-scopée)."""
    permission_classes = [IsAuthenticated]

    def _company(self, request):
        return getattr(request.user, 'company', None)

    def list(self, request):
        resume = resume_pour_utilisateur(
            self._company(request), request.user)
        return Response(resume)

    @action(detail=True, methods=['post'], url_path='ignorer')
    def ignorer(self, request, pk=None):
        services.ignorer_item(self._company(request), request.user, pk)
        return Response(
            resume_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='ignorer-tout')
    def ignorer_tout(self, request):
        services.ignorer_tout(self._company(request), request.user)
        return Response(
            resume_pour_utilisateur(self._company(request), request.user),
            status=status.HTTP_200_OK)
