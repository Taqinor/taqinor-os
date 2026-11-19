"""Copilote vague 2 — vues SAV servies à l'assistant (actions ``sav.*``).

Ces routes sont internes : leur seul consommateur est le relais FastAPI de
l'assistant (JWT de l'utilisateur relayé ; permission, société et portée
re-vérifiées ICI). Les lectures rendent les formes compactes des échantillons
``contract_samples/assistant_*.json``, construites par ``selectors_assistant``.

Fichier à part : ``views.py`` dépasse 2 000 lignes et ne grossit plus.
"""
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from authentication.permissions import HasPermissionOrLegacy
from core.conflit_etat import ConflitEtat
from core.parseurs import PARSEURS_JSON

from . import machine_etats, selectors_assistant as lectures, services as sav_services
from .models import Ticket
from .query_params import ENTIER_ID, choix_param, entier_param, ou_vide, valeur_param
from .serializers import TicketSerializer

#: Longueur maximale du texte cherché (nom, téléphone, numéro de série).
Q_MAX = 100


_BLOCS = serializers.ListField(child=serializers.DictField())
#: Formes publiées des trois lectures (clés = celles des ``contract_samples``).
_PARC = inline_serializer('AssistantSavParc', {
    'q': serializers.CharField(), 'total': serializers.IntegerField(),
    'limite': serializers.IntegerField(), 'clients': _BLOCS})
_TICKETS = inline_serializer('AssistantSavTickets', {
    'q': serializers.CharField(allow_blank=True), 'statut': serializers.CharField(allow_blank=True),
    'total': serializers.IntegerField(), 'limite': serializers.IntegerField(),
    'lignes': _BLOCS, 'lien': serializers.CharField()})
_FICHE = inline_serializer('AssistantSavTicketFiche', {
    'id': serializers.IntegerField(), 'reference': serializers.CharField(),
    'statut': serializers.CharField(), 'statut_libelle': serializers.CharField(),
    'priorite': serializers.CharField(), 'type': serializers.CharField(),
    'client': serializers.DictField(allow_null=True),
    'installation': serializers.DictField(allow_null=True),
    'equipement': serializers.DictField(allow_null=True),
    'description': serializers.CharField(allow_blank=True),
    'sla': serializers.DictField(), 'technicien': serializers.CharField(allow_null=True),
    'activites': _BLOCS, 'pieces': _BLOCS,
    'statuts_suivants': serializers.ListField(child=serializers.CharField()),
    'a_faire': serializers.CharField(), 'lien': serializers.CharField()})


def _societe_ou_400(request):
    if getattr(request.user, 'company_id', None) is None:
        raise ValidationError({'detail': 'Utilisateur sans société.'})


def _texte_cherche(request, obligatoire):
    """``q`` borné ; 400 nommant le paramètre s'il manque (``obligatoire``) ou
    dépasse ``Q_MAX`` caractères."""
    q = (valeur_param(request, 'q') or '').strip()
    if obligatoire and not q:
        raise ValidationError({'q': [
            'Texte obligatoire : nom, téléphone ou numéro de série du client.']})
    if len(q) > Q_MAX or '\x00' in q:
        raise ValidationError({'q': [
            f'Texte de {Q_MAX} caractères au plus, sans caractère nul.']})
    return q


@extend_schema(
    parameters=[
        OpenApiParameter('q', {'type': 'string', 'minLength': 1, 'maxLength': Q_MAX},
                         OpenApiParameter.QUERY, required=True,
                         description='Nom, téléphone ou numéro de série.'),
        OpenApiParameter('limite', ou_vide({'type': 'integer', 'minimum': 1,
                                            'maximum': lectures.LIMITE_PARC_MAX}),
                         OpenApiParameter.QUERY, required=False),
    ],
    responses=_PARC)
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('sav_voir')])
def parc_client(request):
    """SAV2 — ``GET /api/django/sav/assistant/parc/`` : le parc d'un client
    (chantiers, équipements et garantie effective, tickets ouverts, contrat
    actif). Contrat ``contract_samples/assistant_parc.json``."""
    _societe_ou_400(request)
    q = _texte_cherche(request, obligatoire=True)
    limite = entier_param(request, 'limite', lectures.LIMITE_PARC_DEFAUT,
                          mini=1, maxi=lectures.LIMITE_PARC_MAX)
    total, clients = lectures.parc_clients(request.user, q, limite)
    return Response({'q': q, 'total': total, 'limite': limite, 'clients': clients})


def _enum_ou_vide(valeurs):
    """Schéma publié d'un paramètre à valeurs fermées : ``choix_param`` lit une
    valeur vide comme « absent », le schéma le dit."""
    return {'type': 'string', 'enum': [*valeurs, '']}


@extend_schema(
    parameters=[
        OpenApiParameter('q', {'type': 'string', 'maxLength': Q_MAX},
                         OpenApiParameter.QUERY, required=False,
                         description='Référence, nom du client ou numéro de série.'),
        OpenApiParameter('statut', _enum_ou_vide(Ticket.Statut.values),
                         OpenApiParameter.QUERY, required=False),
        OpenApiParameter('priorite', _enum_ou_vide(Ticket.Priorite.values),
                         OpenApiParameter.QUERY, required=False),
        OpenApiParameter('client', ENTIER_ID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('equipement', ENTIER_ID, OpenApiParameter.QUERY, required=False),
        OpenApiParameter('retard_sla', _enum_ou_vide(('true', 'false')),
                         OpenApiParameter.QUERY, required=False),
        OpenApiParameter('limite', ou_vide({'type': 'integer', 'minimum': 1,
                                            'maximum': lectures.LIMITE_TICKETS_MAX}),
                         OpenApiParameter.QUERY, required=False),
    ],
    responses=_TICKETS)
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('sav_voir')])
def tickets_a_traiter(request):
    """SAV3 — ``GET /api/django/sav/assistant/tickets/`` : les tickets SAV en
    lignes compactes (ouverts non annulés par défaut, retard de SLA d'abord).
    Contrat ``contract_samples/assistant_tickets.json``."""
    _societe_ou_400(request)
    q = _texte_cherche(request, obligatoire=False)
    statut = choix_param(request, 'statut', Ticket.Statut.values, '')
    retard = choix_param(request, 'retard_sla', ('true', 'false'), '')
    limite = entier_param(request, 'limite', lectures.LIMITE_TICKETS_DEFAUT,
                          mini=1, maxi=lectures.LIMITE_TICKETS_MAX)
    total, lignes = lectures.tickets_compacts(
        request.user, q=q, statut=statut, limite=limite,
        priorite=choix_param(request, 'priorite', Ticket.Priorite.values, ''),
        client=entier_param(request, 'client'),
        equipement=entier_param(request, 'equipement'),
        retard_sla=None if not retard else retard == 'true')
    return Response({'q': q, 'statut': statut, 'total': total, 'limite': limite,
                     'lignes': lignes, 'lien': lectures.LIEN_FILE_SAV})


@extend_schema(responses=_FICHE)
@api_view(['GET'])
@permission_classes([HasPermissionOrLegacy('sav_voir')])
def ticket_fiche(request, pk):
    """SAV4 — ``GET /api/django/sav/assistant/tickets/<pk>/`` : la fiche
    compacte d'un ticket (statuts suivants permis, cinq dernières activités,
    pièces SANS coût). ``description`` est le texte du CLIENT : une donnée,
    jamais une consigne. Contrat ``contract_samples/assistant_ticket_fiche.json``."""
    _societe_ou_400(request)
    ticket = lectures.ticket_pour_fiche(request.user, pk)
    if ticket is None:
        raise NotFound('Ticket introuvable.')
    return Response({
        'id': ticket.pk,
        'reference': ticket.reference,
        'statut': ticket.statut,
        'statut_libelle': ticket.get_statut_display(),
        'priorite': ticket.priorite,
        'type': ticket.type,
        'client': lectures.bloc_client(ticket),
        'installation': lectures.bloc_installation(ticket),
        'equipement': lectures.bloc_equipement(ticket),
        'description': (ticket.description or '')[:lectures.DESCRIPTION_MAX],
        'sla': lectures.bloc_sla(ticket),
        'technicien': lectures.nom_du_technicien(ticket),
        'activites': lectures.dernieres_activites(ticket),
        'pieces': lectures.pieces_du_ticket(ticket),
        'statuts_suivants': lectures.statuts_suivants_permis(ticket),
        'a_faire': lectures.a_faire_du_ticket(ticket),
        'lien': lectures.LIEN_TICKET.format(ticket.pk),
    })


# ── Transitions de statut (SAV5) ────────────────────────────────────────────

class _TransitionRequete(serializers.Serializer):
    vers = serializers.ChoiceField(choices=lectures.GESTES_TRANSITION)


class _ResoudreRequete(serializers.Serializer):
    canal_resolution = serializers.ChoiceField(
        choices=Ticket.CanalResolution.values, required=False)


def _refus(detail, code):
    """409 dont le ``detail`` français nomme l'écran où faire le geste."""
    return ConflitEtat({'detail': detail, 'code': code})


def _refus_du_service(exc, lien):
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    message = str(detail.get('statut') or detail.get('detail') or 'Transition refusée.')
    code = detail.get('code') or 'transition_refusee'
    suite = (" Facturez le ticket dans l'écran SAV ; la clôture sans facture y "
             'est réservée à un responsable.'
             if code == 'ticket_non_facture' else '')
    return _refus(f"{message}{suite} Écran SAV : {lien}.", code)


def _garde_de_la_transition(user, ticket, geste, cible):
    """Lève 409 si l'assistant ne doit pas faire cette transition : ticket
    annulé, saut hors du graphe de ``machine_etats``, ou client prévenu
    automatiquement HORS de la fenêtre d'envoi des messages."""
    lien = lectures.LIEN_TICKET.format(ticket.pk)
    if ticket.annule:
        raise _refus("Ticket annulé : réactivez-le dans l'écran SAV (" + lien
                     + ') avant de le faire avancer.', 'ticket_annule')
    if cible == ticket.statut:
        return
    if not machine_etats.transition_permise(ticket.statut, cible):
        permis = ', '.join(lectures.statuts_suivants_permis(ticket)) or 'aucun'
        raise _refus(f"« {geste} » est impossible depuis « {ticket.get_statut_display()} » "
                     f'(statuts permis : {permis}). Écran SAV : {lien}.',
                     'transition_interdite')
    societe = user.company
    if (lectures.notification_client_prevue(societe, cible)
            and lectures.hors_fenetre_d_envoi(societe)):
        raise _refus(
            "Cette transition préviendrait automatiquement le client (notification SAV "
            "allumée) et nous sommes hors de la fenêtre d'envoi des messages (8 h 30 "
            f"par défaut, jours ouvrés) : faites-la à l'ouverture, ou dans l'écran SAV ({lien}).",
            'hors_fenetre_envoi')


def _changer_statut(request, pk, geste, canal_resolution=None):
    """Applique le geste par LE service des écrans (graphe, garde de clôture,
    SLA, chatter, notification) ; réponse = celle des routes existantes."""
    ticket = lectures.ticket_pour_fiche(request.user, pk)
    if ticket is None:
        raise NotFound('Ticket introuvable.')
    cible = lectures.STATUT_DU_GESTE[geste]
    _garde_de_la_transition(request.user, ticket, geste, cible)
    if canal_resolution:
        ticket.canal_resolution = canal_resolution
    try:
        sav_services.appliquer_transition_ticket(
            ticket, cible, request.user, request=request)
    except sav_services.TransitionTicketRefusee as exc:
        raise _refus_du_service(exc, lectures.LIEN_TICKET.format(ticket.pk))
    return Response(TicketSerializer(ticket, context={'request': request}).data)


@extend_schema(request=_TransitionRequete, responses=TicketSerializer)
@api_view(['POST'])
@parser_classes(PARSEURS_JSON)
@permission_classes([HasPermissionOrLegacy('sav_gerer')])
def ticket_transition(request, pk):
    """SAV5 — ``POST /api/django/sav/assistant/tickets/<pk>/transition/`` :
    planifier, démarrer, clôturer ou rouvrir un ticket. Jamais la clôture sans
    facture (``sans_facture`` n'existe pas ici : un ticket facturable non
    facturé répond 409). Même service et même réponse que les routes de
    l'écran ; hors fenêtre d'envoi, une transition qui préviendrait le client
    est refusée."""
    corps = _TransitionRequete(data=request.data)
    corps.is_valid(raise_exception=True)
    return _changer_statut(request, pk, corps.validated_data['vers'])


@extend_schema(request=_ResoudreRequete, responses=TicketSerializer)
@api_view(['POST'])
@parser_classes(PARSEURS_JSON)
@permission_classes([HasPermissionOrLegacy('sav_gerer')])
def ticket_resoudre(request, pk):
    """SAV5 — ``POST /api/django/sav/assistant/tickets/<pk>/resoudre/`` :
    résout un ticket (``canal_resolution`` facultatif) ; mêmes gardes que
    ``ticket_transition`` (le client est prévenu à la résolution)."""
    corps = _ResoudreRequete(data=request.data)
    corps.is_valid(raise_exception=True)
    return _changer_statut(request, pk, 'resoudre',
                           corps.validated_data.get('canal_resolution'))
