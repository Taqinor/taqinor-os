"""NTI18N33 — vues de l'assistant de saisie des fêtes mobiles.

Écran Paramètres → Localisation → Fêtes mobiles : GET pré-remplit l'état de
saisie de l'année demandée, POST valide + enregistre les 4 dates (voir
``fetes_mobiles.py`` pour les règles). Écriture réservée
Administrateur/Responsable promu — même patron que le reste de l'app — ET
porteur de ``localisation_gerer`` (NTI18N40). La LECTURE reste ouverte à tout
rôle interne : le calendrier des fériés sert à tout le monde (planification
chantier/RH), la borner masquerait des jours non ouvrés à ceux qui les subissent."""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole

from .fetes_mobiles import (
    FETES_MOBILES_CLES,
    enregistrer_fetes_mobiles,
    fetes_mobiles_saisies,
)
from .localisation import PeutGererLocalisation
from .views_common import _audit_company

# NTI18N33 — les 4 fêtes hégiriennes (voir ``FETES_MOBILES_CLES``) : chaque
# clé porte soit ``None`` (pas encore saisie), soit une date ISO déjà
# enregistrée — jamais une autre clé (``fetes_mobiles_saisies`` renvoie
# EXACTEMENT ces 4 clés, ``fetes_mobiles_etat`` aussi quand la société est
# introuvable). Même forme pour l'état (GET) et l'enregistrement (POST) —
# déclarée une seule fois ici, jamais deux composants identiques.
FETES_MOBILES_ETAT_RESPONSE = inline_serializer('FetesMobilesEtat', {
    'aid_el_fitr': serializers.CharField(allow_null=True),
    'aid_el_adha': serializers.CharField(allow_null=True),
    '1er_moharram': serializers.CharField(allow_null=True),
    'aid_el_mawlid': serializers.CharField(allow_null=True),
})


@extend_schema(responses=FETES_MOBILES_ETAT_RESPONSE)
@api_view(['GET'])
@permission_classes([IsAnyRole])
def fetes_mobiles_etat(request):
    """GET /parametres/fetes-mobiles/?annee=2027 — état de saisie actuel."""
    company = _audit_company(request)
    try:
        annee = int(request.query_params.get('annee'))
    except (TypeError, ValueError):
        return Response(
            {'detail': "Paramètre 'annee' requis (entier)."},
            status=status.HTTP_400_BAD_REQUEST)
    if company is None:
        return Response({cle: None for cle in FETES_MOBILES_CLES})
    return Response(fetes_mobiles_saisies(company, annee))


FETES_MOBILES_ENREGISTRER_REQUEST = inline_serializer(
    'FetesMobilesEnregistrerRequest', {
        'annee': serializers.IntegerField(),
        'dates': inline_serializer('FetesMobilesEnregistrerDates', {
            'aid_el_fitr': serializers.CharField(required=False),
            'aid_el_adha': serializers.CharField(required=False),
            '1er_moharram': serializers.CharField(required=False),
            'aid_el_mawlid': serializers.CharField(required=False),
        }),
    })


@extend_schema(request=FETES_MOBILES_ENREGISTRER_REQUEST,
               responses=FETES_MOBILES_ETAT_RESPONSE)
@api_view(['POST'])
@permission_classes([IsAdminOrResponsableTier, PeutGererLocalisation])
def fetes_mobiles_enregistrer(request):
    """POST /parametres/fetes-mobiles/ — ``{"annee": 2027, "dates":
    {"aid_el_fitr": "2027-03-09", ...}}``. Bloque (400) tant qu'au moins
    une des 4 dates est vide/incohérente (hors année cible)."""
    company = _audit_company(request)
    if company is None:
        return Response(
            {'detail': 'Aucune société associée à ce compte.'},
            status=status.HTTP_400_BAD_REQUEST)
    try:
        annee = int(request.data.get('annee'))
    except (TypeError, ValueError):
        return Response(
            {'detail': "Champ 'annee' requis (entier)."},
            status=status.HTTP_400_BAD_REQUEST)
    dates = request.data.get('dates') or {}
    try:
        enregistrer_fetes_mobiles(company, annee, dates)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(fetes_mobiles_saisies(company, annee))
