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
from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.parseurs import PARSEURS_JSON

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
from ..serializers import forme_du_contrat
from ..services.assistant import (
    LeadIntrouvable, RefusAssistant, etat_du_lead, preparer as preparer_calepinage,
    resume_compact,
)
from ..services.contenance import BORNES_COTE_M, BORNES_PENTE_DEG, ORIGINES
from .calepinages import CalepinageViewSet

__all__ = ['resume', 'du_lead', 'preparer', 'publier_devis_apercu', 'publier_devis',
           'a_traiter', 'contenance']


#: Borne haute des identifiants numériques lus en paramètre (``len < 19``).
ID_MAX = 999999999999999999
#: Un identifiant publié AVEC ses bornes : une valeur du schéma est acceptée.
ENTIER_ID = {'type': 'integer', 'minimum': 1, 'maximum': ID_MAX}

#: Le refus NOMMÉ ``{detail, field, code}`` (404 / 409), DOCUMENTÉ.
REPONSE_REFUS = OpenApiResponse(
    response=inline_serializer('CalepinageAssistantRefus', {
        'detail': drf_serializers.CharField(required=False),
        'field': drf_serializers.CharField(required=False),
        'code': drf_serializers.CharField(required=False)}),
    description='Refus nommé : introuvable (404) ou état qui ne le permet pas (409).')
REFUS_404_409 = {404: REPONSE_REFUS, 409: REPONSE_REFUS}


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
        'variante', ENTIER_ID, OpenApiParameter.QUERY, required=False,
        description='Variante du même calepinage à résumer.')],
    responses={200: forme_du_contrat('CalepinageAssistantResume',
                                     'calepinage_assistant_resume.json'),
               **REFUS_404_409})
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
        'lead', ENTIER_ID, OpenApiParameter.QUERY, required=True,
        description='Le lead dont on veut le calepinage.')],
    responses={200: forme_du_contrat('CalepinageAssistantDuLead',
                                     'calepinage_assistant_du_lead.json'),
               **REFUS_404_409})
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
        'lead': drf_serializers.IntegerField(min_value=1, max_value=ID_MAX)}),
    responses={200: _FORME_PREPARER, 201: _FORME_PREPARER, **REFUS_404_409})
# headless: servie au relais de l'assistant (apps.calepinage.agent_actions, calepinage.preparer)
@action(detail=False, methods=['post'], url_path='preparer',
        permission_classes=[PeutGererCalepinage], parser_classes=PARSEURS_JSON)
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


def _publication(fonction, calepinage, user, **kwargs):
    """Rend la réponse d'un des deux temps de la publication, refus compris :
    les refus du pont devis (``DevisRefuse``) gardent la charge ventes et le
    statut d'état de ``generer-devis`` / ``sync-devis`` (mêmes fonctions)."""
    from ..services.devis import DevisRefuse
    from .calepinages import _refus_devis, _statut_refus_devis

    try:
        return Response(fonction(calepinage, user=user, **kwargs))
    except RefusAssistant as refuse_metier:
        return Response(refuse_metier.corps(), status=refuse_metier.statut)
    except DevisRefuse as refuse_devis:
        return Response(_refus_devis(refuse_devis),
                        status=_statut_refus_devis(refuse_devis))


@extend_schema(responses={200: forme_du_contrat(
    'CalepinageAssistantPublierApercu', 'calepinage_assistant_publier_apercu.json'),
    **REFUS_404_409})
# headless: servie au relais de l'assistant (apps.calepinage.agent_actions, aperçu de calepinage.publier_devis)
@action(detail=True, methods=['get'], url_path='publier-devis/apercu',
        permission_classes=[PeutGererCalepinage])
def publier_devis_apercu(self, request, pk=None):
    """CALA7 — l'aperçu (ancien → nouveau total TTC) de la publication au
    devis, calculé par le MÊME service dans une transaction annulée."""
    from ..services.assistant import apercu_publication

    return _publication(apercu_publication, self.get_object(), user=request.user)


#: Un total TTC recopié de l'aperçu : texte décimal, deux décimales au plus.
MONTANT = r'^\d{1,12}(\.\d{1,2})?$'
#: CALA7 — ce que le corps de ``publier-devis`` accepte, et rien d'autre.
CHAMPS_PUBLIER = ('ancien_total_ttc', 'nouveau_total_ttc', 'devis')
CONSIGNE_PUBLIER = ('Seuls ancien_total_ttc, nouveau_total_ttc et devis sont acceptés ; '
                    'TVA, remise et dérogation se règlent à l\'écran.')


@extend_schema(
    request=inline_serializer('CalepinageAssistantPublierCorps', {
        'ancien_total_ttc': drf_serializers.RegexField(MONTANT, allow_null=True),
        'nouveau_total_ttc': drf_serializers.RegexField(MONTANT),
        'devis': drf_serializers.IntegerField(
            required=False, allow_null=True, min_value=1, max_value=ID_MAX)}),
    responses={200: forme_du_contrat('CalepinageAssistantPublierDevis',
                                     'calepinage_assistant_publier_devis.json'),
               **REFUS_404_409})
# headless: servie au relais de l'assistant (apps.calepinage.agent_actions, calepinage.publier_devis)
@action(detail=True, methods=['post'], url_path='publier-devis',
        permission_classes=[PeutGererCalepinage], parser_classes=PARSEURS_JSON)
def publier_devis(self, request, pk=None):
    """CALA7 — publie la conception au devis (génère le brouillon ou
    resynchronise le devis lié, envoyé compris) aux SEULS totaux confirmés."""
    from ..services.assistant import publier

    calepinage = self.get_object()  # 404 AVANT toute lecture du corps
    corps, refuse = corps_borne(request, CHAMPS_PUBLIER, CONSIGNE_PUBLIER)
    if refuse is not None:
        return refuse
    if not isinstance(corps.get('nouveau_total_ttc'), str) or not isinstance(
            corps.get('ancien_total_ttc'), (str, type(None))):
        return refus('Recopiez nouveau_total_ttc et ancien_total_ttc (absent ou '
                     'null sans devis lié) de l\'aperçu confirmé.',
                     'nouveau_total_ttc', 'totaux_manquants')
    devis_vu = corps.get('devis')
    if devis_vu is not None and (isinstance(devis_vu, bool) or not isinstance(devis_vu, int)):
        return refus('devis : l\'identifiant du devis lié, recopié de l\'aperçu.',
                     'devis', 'devis_invalide')
    return _publication(publier, calepinage, user=request.user,
                        ancien_vu=corps.get('ancien_total_ttc'),
                        nouveau_vu=corps.get('nouveau_total_ttc'), devis_vu=devis_vu)


@extend_schema(
    parameters=[OpenApiParameter(
        'limite', {'type': 'integer', 'minimum': 1, 'maximum': 20},
        OpenApiParameter.QUERY, required=False,
        description='Nombre de lignes, de 1 à 20 (10 par défaut).')],
    responses={200: forme_du_contrat('CalepinageAssistantATraiter',
                                     'calepinage_assistant_a_traiter.json')})
# headless: servie au relais de l'assistant (apps.calepinage.agent_actions, calepinage.a_traiter)
@action(detail=False, methods=['get'], url_path='a-traiter',
        permission_classes=[PeutVoirCalepinage])
def a_traiter(self, request):
    """CALA9 — la file « calepinages à traiter » de l'appelant."""
    from ..selectors import calepinages_a_traiter
    from ..services.assistant import LIMITE_DEFAUT, LIMITE_MAX

    brut = request.query_params.get('limite')
    limite = LIMITE_DEFAUT
    if brut is not None:
        brut = str(brut).strip()
        if not (brut.isascii() and brut.isdigit() and 1 <= int(brut) <= LIMITE_MAX):
            return refus(f'limite : un entier entre 1 et {LIMITE_MAX}.', 'limite',
                         'limite_invalide')
        limite = int(brut)
    return Response(calepinages_a_traiter(request.user, limite=limite))


#: CALA10 — les paramètres de ``contenance/`` ; les cotes ne valent que pour
#: ``origine=dicte``.
PARAMS_CONTENANCE = ('lead', 'origine', 'produit', 'longueur_m', 'largeur_m',
                     'pente_deg', 'toit_plat')
PARAMS_DICTES = ('longueur_m', 'largeur_m', 'pente_deg', 'toit_plat')


def _nombre_schema(bornes):
    """Le schéma publié d'un nombre borné (mêmes bornes que la lecture)."""
    return {'type': 'number', 'minimum': bornes[0], 'maximum': bornes[1]}


def _nombre_borne(brut, champ, bornes):
    """Un nombre fini dans ``bornes``, sinon :class:`RefusAssistant` (400)."""
    try:
        valeur = float(brut)
    except ValueError:
        valeur = None
    if valeur is None or valeur != valeur or not (bornes[0] <= valeur <= bornes[1]):
        raise RefusAssistant(f'{champ} : un nombre entre {bornes[0]:g} et {bornes[1]:g}.',
                             champ, 'parametre_invalide', status.HTTP_400_BAD_REQUEST)
    return valeur


def _lire_contenance(params):
    """``(origine, cotes, produit_id)`` validés ; :class:`RefusAssistant` 400
    nommé pour un paramètre inconnu, répété, hors borne ou hors origine."""
    for cle in params:
        if cle not in PARAMS_CONTENANCE or len(params.getlist(cle)) > 1:
            raise RefusAssistant(f'Paramètre refusé : {cle} (inconnu ou répété).', cle,
                                 'parametre_refuse', status.HTTP_400_BAD_REQUEST)
    origine = params.get('origine')
    if origine not in ORIGINES:
        raise RefusAssistant('origine : visite, trace ou dicte.', 'origine',
                             'origine_invalide', status.HTTP_400_BAD_REQUEST)
    # Règles ENTRE paramètres : le schéma ne sait pas les dire, donc un 409
    # nommé (jamais un 400 sur une requête conforme au schéma publié).
    dictes = [cle for cle in PARAMS_DICTES if cle in params]
    if dictes and origine != 'dicte':
        raise RefusAssistant(f'{dictes[0]} : seulement avec origine=dicte.', dictes[0],
                             'parametre_refuse')
    cotes = {}
    if origine == 'dicte':
        for cle in ('longueur_m', 'largeur_m'):
            if cle not in params:
                raise RefusAssistant(f'{cle} : obligatoire avec origine=dicte.', cle,
                                     'parametre_manquant')
            cotes[cle] = _nombre_borne(params[cle], cle, BORNES_COTE_M)
        plat = str(params.get('toit_plat', '')).strip().lower()
        cotes['toit_plat'] = plat in ('true', '1', 'oui')
        cotes['pente_deg'] = (_nombre_borne(params['pente_deg'], 'pente_deg', BORNES_PENTE_DEG)
                              if 'pente_deg' in params else None)
        if not cotes['toit_plat'] and cotes['pente_deg'] is None:
            raise RefusAssistant('pente_deg : donnez la pente, ou toit_plat=true.',
                                 'pente_deg', 'pente_manquante')
    produit = str(params.get('produit', '')).strip()
    if produit and not (produit.isascii() and produit.isdigit() and len(produit) < 19):
        raise RefusAssistant("produit : l'identifiant entier du panneau.", 'produit',
                             'parametre_invalide', status.HTTP_400_BAD_REQUEST)
    return origine, cotes, (int(produit) if produit else None)


@extend_schema(
    parameters=[
        OpenApiParameter('lead', ENTIER_ID, OpenApiParameter.QUERY, required=True),
        OpenApiParameter('origine', {'type': 'string', 'enum': list(ORIGINES)},
                         OpenApiParameter.QUERY, required=True),
        OpenApiParameter('produit', ENTIER_ID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('longueur_m', _nombre_schema(BORNES_COTE_M), OpenApiParameter.QUERY,
                         required=False, description='Avec origine=dicte (obligatoire).'),
        OpenApiParameter('largeur_m', _nombre_schema(BORNES_COTE_M), OpenApiParameter.QUERY,
                         required=False, description='Avec origine=dicte (obligatoire).'),
        OpenApiParameter('pente_deg', _nombre_schema(BORNES_PENTE_DEG), OpenApiParameter.QUERY,
                         required=False, description='Avec origine=dicte, ou toit_plat=true.'),
        OpenApiParameter('toit_plat', OpenApiTypes.BOOL, OpenApiParameter.QUERY, required=False)],
    responses={200: forme_du_contrat('CalepinageAssistantContenance',
                                     'calepinage_assistant_contenance.json'),
               **REFUS_404_409})
# headless: servie au relais de l'assistant (apps.calepinage.agent_actions, calepinage.contenance)
@action(detail=False, methods=['get'], url_path='contenance',
        permission_classes=[PeutVoirCalepinage])
def contenance(self, request):
    """CALA10 — l'ESTIMATION du nombre de panneaux avant dessin ; n'écrit rien."""
    from ..services.contenance import estimer

    lead_id, refuse = lead_du_parametre(request)
    if refuse is not None:
        return refuse
    try:
        origine, cotes, produit_id = _lire_contenance(request.query_params)
        return Response(estimer(request.user, lead_id=lead_id, origine=origine,
                                cotes=cotes, produit_id=produit_id))
    except LeadIntrouvable:
        return refus(*LEAD_INTROUVABLE)
    except RefusAssistant as refuse_metier:
        return Response(refuse_metier.corps(), status=refuse_metier.statut)


# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.resume = resume
CalepinageViewSet.du_lead = du_lead
CalepinageViewSet.preparer = preparer
CalepinageViewSet.publier_devis_apercu = publier_devis_apercu
CalepinageViewSet.publier_devis = publier_devis
CalepinageViewSet.a_traiter = a_traiter
CalepinageViewSet.contenance = contenance
