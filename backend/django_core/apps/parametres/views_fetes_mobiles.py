"""NTI18N33 — vues de l'assistant de saisie des fêtes mobiles.

Écran Paramètres → Localisation → Fêtes mobiles : GET pré-remplit l'état de
saisie de l'année demandée, POST valide + enregistre les 4 dates (voir
``fetes_mobiles.py`` pour les règles). Écriture réservée
Administrateur/Responsable promu — même patron que le reste de l'app — ET
porteur de ``localisation_gerer`` (NTI18N40). La LECTURE reste ouverte à tout
rôle interne : le calendrier des fériés sert à tout le monde (planification
chantier/RH), la borner masquerait des jours non ouvrés à ceux qui les subissent."""
from rest_framework import status
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
