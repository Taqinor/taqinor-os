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
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
from ..serializers import forme_du_contrat
from ..services.assistant import (
    LeadIntrouvable, RefusAssistant, etat_du_lead, preparer as preparer_calepinage,
    resume_compact,
)
from .calepinages import CalepinageViewSet

__all__ = ['resume', 'du_lead', 'preparer']


def refus(detail, champ, code, statut=status.HTTP_400_BAD_REQUEST):
    """Le refus NOMMÉ des routes de l'assistant : ``{detail, field, code}``."""
    return Response({'detail': detail, 'field': champ, 'code': code},
                    status=statut)


def corps_borne(request, autorises, consigne):
    """``(corps, refus | None)`` — le corps JSON doit être un objet et ne
    porter QUE les champs ``autorises`` ; tout autre champ est refusé (400)
    en le nommant, avec la ``consigne`` (ce qui se règle à l'écran)."""
    corps = request.data if request.data not in (None, '') else {}
    if not isinstance(corps, dict):
        return None, refus('Le corps attendu est un objet JSON.', 'detail',
                           'corps_invalide')
    refuses = sorted(set(corps) - set(autorises))
    if refuses:
        return None, refus(f'Champ refusé : {refuses[0]}. {consigne}',
                           refuses[0], 'champ_refuse')
    return corps, None


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


_FORME_PREPARER = forme_du_contrat('CalepinageAssistantPreparer',
                                   'calepinage_assistant_preparer.json')


@extend_schema(
    request=inline_serializer('CalepinageAssistantPreparerCorps', {
        'lead': drf_serializers.IntegerField(min_value=1)}),
    responses={200: _FORME_PREPARER, 201: _FORME_PREPARER})
# headless: servie au relais de l'assistant (apps.calepinage.agent_actions, calepinage.preparer)
@action(detail=False, methods=['post'], url_path='preparer',
        permission_classes=[PeutGererCalepinage])
def preparer(self, request):
    """CALA6 — ouvre (ou retrouve) le calepinage du lead et reprend la visite
    validée, en UN geste ; rend le bouton qui ouvre l'atelier."""
    corps, refuse = corps_borne(request, ('lead',), "Seul « lead » est accepté.")
    if refuse is not None:
        return refuse
    brut = corps.get('lead')
    if isinstance(brut, bool) or not isinstance(brut, int) or brut < 1:
        return refus("« lead » attend l'identifiant entier du lead.", 'lead',
                     'lead_invalide')
    try:
        reponse, cree = preparer_calepinage(request.user, brut)
    except LeadIntrouvable:
        return refus(*LEAD_INTROUVABLE)
    except RefusAssistant as refuse_metier:
        return Response(refuse_metier.corps(), status=refuse_metier.statut)
    return Response(reponse, status=(status.HTTP_201_CREATED if cree
                                     else status.HTTP_200_OK))


# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.resume = resume
CalepinageViewSet.du_lead = du_lead
CalepinageViewSet.preparer = preparer
