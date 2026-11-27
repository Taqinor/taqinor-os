"""ADEV137 — la conception rangée servie (D-ACAL-97), et son aperçu sans écriture.

* ``GET /api/django/ventes/conception/<lead_id>/`` — la version COURANTE du lead
  (``selectors_conception.conception_courante``), forme EXACTE du contrat
  ``contract_samples/conception_lead.json`` ;
* ``POST /api/django/ventes/conception/apercu/`` — la sortie du moteur pour des
  valeurs tapées non enregistrées (``conception/service.py::apercu_conception``),
  forme ``apercu.reponse`` du contrat ; rien n'est écrit.

Même forme que les aperçus d'étude voisins (``etude_horaire_view``) : fonction
``@api_view``, ``IsAnyRole`` + ``crm_voir`` (comme les routes du lead,
``crm/roof_views.py``), porteur borné à ce que l'APPELANT voit — un lead hors de
``crm.selectors.leads_visibles`` (autre société, ou hors de la portée de son
rôle) ou un calepinage hors de ``calepinage.selectors.calepinages_visibles``
répond 404 AVANT toute lecture du reste du corps (relecture B1 : la conception
porte factures, consommation et lieu du client). Le DÉTAIL des clés reste décrit par le contrat (PACT10) : aucun
sérialiseur imbriqué n'en fait une seconde définition.
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from apps.ventes.conception.champs import CHAMPS_ENTREES
from apps.ventes.domain.composition_imposee import CHAMPS_IMPOSES
from authentication.permissions import HasPermissionOrLegacy, IsAnyRole
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE

_ID_MAX = 2147483647
#: api-fuzz (PR #1552) — le corps de l'aperçu publié tel que la vue le REFUSE en
#: 400 (``x-corps-resserre``, même convention que ``CORPS_LEAD_OU_CLIENT`` de
#: ``openapi_docs``) : un porteur non nul est requis (« lead » ou « calepinage »,
#: un identifiant 0 vaut absent) ; « imposes » ne porte que ``CHAMPS_IMPOSES`` ;
#: « entrees » que les colonnes de ``CHAMPS_ENTREES`` (union des marchés — la
#: colonne hors du marché du lead et la valeur illisible restent des refus que
#: le schéma ne peut pas dire, liés au lead lu en base).
_APERCU_RESSERRE = {EXTENSION_CORPS_RESSERRE: {
    'anyOf': [
        {'required': [porteur], 'properties': {porteur: {'type': 'integer', 'minimum': 1}}}
        for porteur in ('lead', 'calepinage')],
    'properties': {
        'lead': {'maximum': _ID_MAX},
        'calepinage': {'maximum': _ID_MAX},
        'imposes': {'type': 'object', 'additionalProperties': False,
                    'properties': {champ: {} for champ in CHAMPS_IMPOSES}},
        'entrees': {'type': 'object', 'additionalProperties': False,
                    'properties': {champ: {} for champ in sorted(
                        {c for champs in CHAMPS_ENTREES.values() for c in champs})}},
    }}}

_FORME = ("Forme exacte : apps/ventes/contract_samples/conception_lead.json "
          "(clé « exemple » pour la version rangée, « apercu.reponse » pour l'aperçu).")
_ERREUR = inline_serializer('ConceptionErreur', {
    'detail': serializers.CharField(), 'code': serializers.CharField(required=False),
    'champ': serializers.CharField(required=False)})


def _societe(request):
    return getattr(request.user, 'company', None)


@extend_schema(
    responses={200: OpenApiResponse(description=_FORME), 404: _ERREUR},
    summary='ADEV137 — conception courante du lead (moteur unique, lecture seule)',
    description="La version COURANTE de la conception rangée du lead. 404 pour un lead d'une autre "
                "société ou introuvable ; 200 `{etat: 'aucune', code: 'conception_absente'}` tant qu'aucune version "
                "n'est calculée (état normal d'un lead neuf). " + _FORME)
@api_view(['GET'])
@permission_classes([IsAnyRole, HasPermissionOrLegacy('crm_voir')])
def conception_du_lead(request, lead_id):
    from ..selectors_conception import conception_courante

    company = _societe(request)
    lead = _lead_visible(request.user, company, lead_id)
    if lead is None:
        return Response({'detail': 'Lead introuvable.'}, status=404)
    forme = conception_courante(company, lead.pk)
    if forme is None:
        # Un lead neuf n'a pas de conception : état NORMAL, servi en 200 (contrat `exemple_aucune`) ; le 404
        # reste réservé au lead introuvable (autre société, hors portée, inexistant), tous indistincts.
        return Response({'etat': 'aucune', 'code': 'conception_absente',
                         'detail': 'Aucune conception calculée pour ce lead.'})
    return Response(forme)


@extend_schema(
    request=inline_serializer('ConceptionApercuRequest', {
        'lead': serializers.IntegerField(required=False, allow_null=True, help_text='Porteur (scopé société).'),
        'calepinage': serializers.IntegerField(
            required=False, allow_null=True, help_text='Porteur sans lead (scopé société).'),
        'entrees': serializers.DictField(
            required=False, help_text='{colonne du lead : valeur tapée}, colonnes de CHAMPS_ENTREES du marché.'),
        'imposes': serializers.DictField(
            required=False, help_text='Champs imposés de POST devis/auto/ (composition_imposee.CHAMPS_IMPOSES).'),
    }),
    extensions=_APERCU_RESSERRE,
    responses={200: OpenApiResponse(description=_FORME), 400: _ERREUR, 404: _ERREUR, 409: _ERREUR},
    summary='ADEV137 — aperçu de la conception sur des valeurs tapées (aucune écriture)',
    description="Même moteur que la version rangée, sur une copie en mémoire du porteur ; aucune version "
                "n'est écrite. 404 pour un porteur d'une autre société (avant toute lecture du reste du "
                "corps) ; 409 pour un dossier d'appel d'offres (hors moteur). " + _FORME)
@api_view(['POST'])
@permission_classes([IsAnyRole, HasPermissionOrLegacy('crm_voir')])
@parser_classes([JSONParser])
def apercu_conception(request):
    from ..conception.service import SaisieRefusee, apercu_conception as apercu

    corps = request.data if isinstance(request.data, dict) else None
    if corps is None:
        return Response({'detail': 'Corps de requête invalide : un objet JSON est attendu.'}, status=400)
    company = _societe(request)
    lead, calepinage, introuvable = _porteur_du_corps(request.user, company, corps)
    if introuvable is not None:
        return introuvable
    entrees, imposes = corps.get('entrees') or {}, corps.get('imposes') or {}
    if not isinstance(entrees, dict) or not isinstance(imposes, dict):
        return Response({'detail': 'Corps de requête invalide : « entrees » et « imposes » sont des objets.'},
                        status=400)
    from ..conception.consommation_imposee import CLE as CLE_CONSOMMATION
    inconnus = sorted(set(imposes) - set(CHAMPS_IMPOSES) - {CLE_CONSOMMATION})  # reste d'ACAL2020
    if inconnus:
        return Response({'detail': 'Champ imposé inconnu : %s.' % ', '.join(inconnus), 'champ': inconnus[0]},
                        status=400)
    try:
        sortie, refus = apercu(lead, company, calepinage=calepinage, saisies=entrees, imposes=imposes,
                               investissement=corps.get('investissement'))  # E7d (M1)
    except SaisieRefusee as exc:
        return Response({'detail': str(exc), 'champ': exc.champ}, status=400)
    if refus is not None:
        return Response({'detail': refus['message'], 'code': refus['code'], 'champ': refus['champ']}, status=409)
    return Response(sortie)


def _lead_visible(user, company, lead_id):
    """Le lead si l'appelant le VOIT (société + portée de son rôle), sinon ``None``."""
    from apps.crm.selectors import leads_visibles

    if company is None or not lead_id:
        return None
    return leads_visibles(user, company).filter(pk=lead_id).first()


def _porteur_du_corps(user, company, corps):
    """``(lead, calepinage, réponse 4xx)`` : le porteur que l'appelant VOIT,
    résolu AVANT le reste du corps (404 hors société ou hors portée). Un
    calepinage d'un lead hors de sa portée est introuvable comme le lead."""
    from apps.ventes.selectors_calepinage import calepinage_visible_pour

    lead_id, calepinage_id = _entier(corps.get('lead')), _entier(corps.get('calepinage'))
    if lead_id is False or calepinage_id is False:
        return None, None, Response({'detail': '« lead » et « calepinage » sont des identifiants.'}, status=400)
    if not lead_id and not calepinage_id:
        if isinstance(corps.get('entrees'), dict) and corps['entrees']:
            return None, None, None  # ADEV152 — devis sans lead : les seules valeurs tapées
        return None, None, Response({'detail': 'Porteur requis : « lead », « calepinage » ou des valeurs tapées.'},
                                    status=400)
    lead = _lead_visible(user, company, lead_id) if lead_id else None
    if lead_id and lead is None:
        return None, None, Response({'detail': 'Lead introuvable.'}, status=404)
    if lead is not None:
        return lead, None, None
    calepinage = calepinage_visible_pour(user, company, calepinage_id)
    if calepinage is None or (calepinage.lead_id and _lead_visible(user, company, calepinage.lead_id) is None):
        return None, None, Response({'detail': 'Calepinage introuvable.'}, status=404)
    return None, calepinage, None


def _entier(valeur):
    """Un identifiant entier, ``None`` absent, ``False`` illisible."""
    if valeur in (None, ''):
        return None
    if isinstance(valeur, bool):
        return False
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return False
