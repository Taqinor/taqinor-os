"""ADEV137 — la conception rangée servie (D-ACAL-97), et son aperçu sans écriture.

* ``GET /api/django/ventes/conception/<lead_id>/`` — la version COURANTE du lead
  (``selectors_conception.conception_courante``), forme EXACTE du contrat
  ``contract_samples/conception_lead.json`` ;
* ``POST /api/django/ventes/conception/apercu/`` — la sortie du moteur pour des
  valeurs tapées non enregistrées (``conception/service.py::apercu_conception``),
  forme ``apercu.reponse`` du contrat ; rien n'est écrit.

Même forme que les aperçus d'étude voisins (``etude_horaire_view``) : fonction
``@api_view``, ``IsAnyRole``, porteur borné à la société de l'appelant — un lead
ou un calepinage d'une autre société répond 404 AVANT toute lecture du reste du
corps. Le DÉTAIL des clés reste décrit par le contrat (PACT10) : aucun
sérialiseur imbriqué n'en fait une seconde définition.
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

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
                "société, et (code `conception_absente`) tant qu'aucune version n'est calculée. " + _FORME)
@api_view(['GET'])
@permission_classes([IsAnyRole])
def conception_du_lead(request, lead_id):
    from apps.crm.selectors import get_company_lead

    from ..selectors_conception import conception_courante

    company = _societe(request)
    lead = get_company_lead(company, lead_id) if company is not None else None
    if lead is None:
        return Response({'detail': 'Lead introuvable.'}, status=404)
    forme = conception_courante(company, lead.pk)
    if forme is None:
        return Response({'detail': 'Aucune conception calculée pour ce lead.', 'code': 'conception_absente'},
                        status=404)
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
    responses={200: OpenApiResponse(description=_FORME), 400: _ERREUR, 404: _ERREUR, 409: _ERREUR},
    summary='ADEV137 — aperçu de la conception sur des valeurs tapées (aucune écriture)',
    description="Même moteur que la version rangée, sur une copie en mémoire du porteur ; aucune version "
                "n'est écrite. 404 pour un porteur d'une autre société (avant toute lecture du reste du "
                "corps) ; 409 pour un dossier d'appel d'offres (hors moteur). " + _FORME)
@api_view(['POST'])
@permission_classes([IsAnyRole])
@parser_classes([JSONParser])
def apercu_conception(request):
    from ..conception.service import SaisieRefusee, apercu_conception as apercu

    corps = request.data if isinstance(request.data, dict) else None
    if corps is None:
        return Response({'detail': 'Corps de requête invalide : un objet JSON est attendu.'}, status=400)
    company = _societe(request)
    lead, calepinage_id, introuvable = _porteur_du_corps(company, corps)
    if introuvable is not None:
        return introuvable
    entrees, imposes = corps.get('entrees') or {}, corps.get('imposes') or {}
    if not isinstance(entrees, dict) or not isinstance(imposes, dict):
        return Response({'detail': 'Corps de requête invalide : « entrees » et « imposes » sont des objets.'},
                        status=400)
    from apps.ventes.domain.composition_imposee import CHAMPS_IMPOSES
    inconnus = sorted(set(imposes) - set(CHAMPS_IMPOSES))
    if inconnus:
        return Response({'detail': 'Champ imposé inconnu : %s.' % ', '.join(inconnus), 'champ': inconnus[0]},
                        status=400)
    try:
        sortie, refus = apercu(lead, company, calepinage_id=calepinage_id, saisies=entrees, imposes=imposes)
    except SaisieRefusee as exc:
        return Response({'detail': str(exc), 'champ': exc.champ}, status=400)
    if refus is not None:
        return Response({'detail': refus['message'], 'code': refus['code'], 'champ': refus['champ']}, status=409)
    return Response(sortie)


def _porteur_du_corps(company, corps):
    """``(lead, calepinage_id, réponse 4xx)`` : le porteur borné société, lu
    AVANT le reste du corps (404 pour une autre société)."""
    from apps.calepinage.selectors import calepinage_detail
    from apps.crm.selectors import get_company_lead

    lead_id, calepinage_id = _entier(corps.get('lead')), _entier(corps.get('calepinage'))
    if lead_id is False or calepinage_id is False:
        return None, None, Response({'detail': '« lead » et « calepinage » sont des identifiants.'}, status=400)
    if not lead_id and not calepinage_id:
        return None, None, Response({'detail': 'Porteur requis : « lead » ou « calepinage ».'}, status=400)
    lead = get_company_lead(company, lead_id) if lead_id and company is not None else None
    if lead_id and lead is None:
        return None, None, Response({'detail': 'Lead introuvable.'}, status=404)
    if calepinage_id and (company is None or calepinage_detail(calepinage_id, company) is None):
        return None, None, Response({'detail': 'Calepinage introuvable.'}, status=404)
    return lead, (None if lead is not None else calepinage_id), None


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
