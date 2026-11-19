"""Copilote vague 2 (lane CALA) — les routes MINCES servies à l'assistant.

Chaque route est une ``@action`` du ``CalepinageViewSet`` greffée par
affectation (patron CALX2, ``views/rattachements.py``) ; aucune ne grossit
``views/calepinages.py``. Elles ne sont appelées par aucun écran : le relais
FastAPI les sert aux actions de ``apps.calepinage.agent_actions`` (marqueur
``# headless:`` lu par ``scripts/check_calepinage_actions_consommees.py``).

Contrats (forme EXACTE, ``contrats_assistant.CONTRATS_ASSISTANT``) :
``calepinage_assistant_resume.json``, ``…_du_lead.json``,
``…_a_traiter.json``, ``…_contenance.json``, ``…_preparer.json``,
``…_publier_apercu.json``, ``…_publier_devis.json``.

La société et la portée viennent TOUJOURS de ``request.user`` : un
calepinage hors de la vue de l'appelant est introuvable (404, ``get_object``
borné par ``selectors.calepinages_visibles``). Aucun prix, aucune géométrie.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..serializers import forme_du_contrat
from ..services.assistant import LeadIntrouvable, etat_du_lead, resume_compact
from .calepinages import CalepinageViewSet

__all__ = ['resume', 'du_lead']


def refus(detail, champ, code, statut=status.HTTP_400_BAD_REQUEST):
    """Le refus NOMMÉ des routes de l'assistant : ``{detail, field, code}``."""
    return Response({'detail': detail, 'field': champ, 'code': code},
                    status=statut)


def _variante_demandee(request, calepinage):
    """``(variante | None, refus | None)`` pour ``?variante=`` (CALA2)."""
    from .. import selectors

    brut = request.query_params.get('variante')
    if brut is None:
        return None, None
    brut = str(brut).strip()
    if not (brut.isascii() and brut.isdigit() and len(brut) < 19):
        return None, refus("« variante » attend l'identifiant numérique de la "
                           'variante.', 'variante', 'variante_invalide')
    variante = selectors.variantes(calepinage).filter(pk=int(brut)).first()
    if variante is None:
        return None, refus('Variante introuvable.', 'variante',
                           'variante_introuvable', status.HTTP_404_NOT_FOUND)
    if not isinstance(variante.roof_layout, dict) or not variante.roof_layout:
        return None, refus(
            f"La variante « {variante.nom} » n'a pas de conception : "
            "dessinez-la dans l'atelier du calepinage avant de la résumer.",
            'variante', 'variante_sans_conception', status.HTTP_409_CONFLICT)
    return variante, None


@extend_schema(
    parameters=[OpenApiParameter(
        'variante', OpenApiTypes.INT, OpenApiParameter.QUERY, required=False,
        description='Variante du même calepinage à résumer.')],
    responses={200: forme_du_contrat('CalepinageAssistantResume',
                                     'calepinage_assistant_resume.json')})
# headless: servie au relais de l'assistant (apps.calepinage.agent_actions, calepinage.resume)
@action(detail=True, methods=['get'], url_path='resume',
        permission_classes=[PeutVoirCalepinage])
def resume(self, request, pk=None):
    """CALA2 — le résumé COMPACT d'un calepinage, pour l'assistant."""
    calepinage = self.get_object()  # borné par calepinages_visibles
    variante, refuse = _variante_demandee(request, calepinage)
    if refuse is not None:
        return refuse
    return Response(resume_compact(calepinage, variante=variante))


def lead_du_parametre(request):
    """``(lead_id | None, refus | None)`` — ``?lead=`` obligatoire, entier > 0."""
    brut = str(request.query_params.get('lead') or '').strip()
    if not (brut.isascii() and brut.isdigit() and 0 < len(brut) < 19 and int(brut) > 0):
        return None, refus("Paramètre `lead` obligatoire : l'identifiant entier "
                           'du lead.', 'lead', 'lead_invalide')
    return int(brut), None


LEAD_INTROUVABLE = ('Lead introuvable.', 'lead', 'lead_introuvable',
                    status.HTTP_404_NOT_FOUND)


@extend_schema(
    parameters=[OpenApiParameter(
        'lead', OpenApiTypes.INT, OpenApiParameter.QUERY, required=True,
        description='Le lead dont on veut le calepinage.')],
    responses={200: forme_du_contrat('CalepinageAssistantDuLead',
                                     'calepinage_assistant_du_lead.json')})
# headless: servie au relais de l'assistant (apps.calepinage.agent_actions, calepinage.du_lead)
@action(detail=False, methods=['get'], url_path='du-lead',
        permission_classes=[PeutVoirCalepinage])
def du_lead(self, request):
    """CALA3 — le calepinage OUVERT d'un lead, résumé, et le geste suivant."""
    lead_id, refuse = lead_du_parametre(request)
    if refuse is not None:
        return refuse
    try:
        return Response(etat_du_lead(request.user, lead_id))
    except LeadIntrouvable:
        return refus(*LEAD_INTROUVABLE)


# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.resume = resume
CalepinageViewSet.du_lead = du_lead
