"""Copilote vague 2 (CHTA2, CHTA3, CHTA5) — routes MINCES de l'assistant sur
les chantiers, greffées sur ``InstallationViewSet`` par ce mixin (même
octroi de lecture, même ``get_queryset`` borné à la société et à la portée,
mêmes gardes : chaque action est rangée dans la liste qui convient de
``InstallationViewSet.get_permissions``).

* ``GET chantiers/{id}/etat-assistant/`` — la fiche compacte
  (``contract_samples/assistant_chantier_etat.json``).

Les dictionnaires renvoyés sont construits par
:mod:`apps.installations.selectors_assistant` (littéraux, clés de
l'échantillon). Aucun prix, aucun coût, aucune position de personne.
"""
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from .. import selectors_assistant
from . import _openapi as oa


class ChantierAssistantMixin:
    """Actions de l'assistant d'``InstallationViewSet`` (voir le module)."""

    def _chantier_assistant(self):
        """Le chantier ``pk`` DANS la portée de l'écran (404 sinon), sans les
        préchargements de la liste (inutiles à une fiche compacte)."""
        qs = self.get_queryset().prefetch_related(None)
        inst = get_object_or_404(qs, pk=self.kwargs.get('pk'))
        self.check_object_permissions(self.request, inst)
        return inst

    # headless: lu par l'action d'assistant `installations.chantier.etat`.
    @oa.extend_schema(responses={200: oa.OBJ, 404: oa.OBJ})
    @action(detail=True, methods=['get'], url_path='etat-assistant')
    def etat_assistant(self, request, pk=None):
        """CHTA2 — prêt à poser ? pourquoi ? matériel (quantités), acompte,
        pose, étape suivante, ``a_faire`` et liens. Lecture seule."""
        inst = self._chantier_assistant()
        return Response(selectors_assistant.etat_chantier(
            inst, aujourdhui=timezone.localdate()))
