"""NTI18N33 — vues de l'assistant de saisie des fêtes mobiles.

Écran Paramètres → Localisation → Fêtes mobiles : GET pré-remplit l'état de
saisie de l'année demandée, POST valide + enregistre les 4 dates (voir
``fetes_mobiles.py`` pour les règles). Écriture réservée
Administrateur/Responsable promu — même patron que le reste de l'app — ET
porteur de ``localisation_gerer`` (NTI18N40). La LECTURE reste ouverte à tout
rôle interne : le calendrier des fériés sert à tout le monde (planification
chantier/RH), la borner masquerait des jours non ouvrés à ceux qui les subissent."""
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import (
    api_view, parser_classes, permission_classes,
)
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole

from .fetes_mobiles import (
    FETES_MOBILES_CLES,
    SaisieFetesInvalide,
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


@extend_schema(
    parameters=[OpenApiParameter(
        'annee', {'type': 'integer', 'minimum': 1900, 'maximum': 2200},
        OpenApiParameter.QUERY, required=True,
        description='Année civile (1900 à 2200).')],
    responses=FETES_MOBILES_ETAT_RESPONSE)
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
    if not 1900 <= annee <= 2200:  # ENF11 — hors plage : 400, jamais 500
        return Response(
            {'detail': "Paramètre 'annee' attendu entre 1900 et 2200."},
            status=status.HTTP_400_BAD_REQUEST)
    if company is None:
        return Response({cle: None for cle in FETES_MOBILES_CLES})
    return Response(fetes_mobiles_saisies(company, annee))


FETES_MOBILES_ENREGISTRER_REQUEST = inline_serializer(
    'FetesMobilesEnregistrerRequest', {
        'annee': serializers.IntegerField(min_value=1900, max_value=2200),
        'dates': inline_serializer('FetesMobilesEnregistrerDates', {
            # ENF11 — les QUATRE dates sont exigées (« La date de … est
            # manquante », 400) : le schéma le dit, un corps sans elles n'est
            # plus « conforme ».
            'aid_el_fitr': serializers.DateField(),
            'aid_el_adha': serializers.DateField(),
            '1er_moharram': serializers.DateField(),
            'aid_el_mawlid': serializers.DateField(),
        }),
    })


@extend_schema(request=FETES_MOBILES_ENREGISTRER_REQUEST,
               responses=FETES_MOBILES_ETAT_RESPONSE)
@api_view(['POST'])
@parser_classes([JSONParser])  # ENF11 — ``dates`` est un objet imbriqué : JSON seul
@permission_classes([IsAdminOrResponsableTier, PeutGererLocalisation])
def fetes_mobiles_enregistrer(request):
    """POST /parametres/fetes-mobiles/ — ``{"annee": 2027, "dates":
    {"aid_el_fitr": "2027-03-09", ...}}``. Bloque tant qu'au moins une des 4
    dates est vide/illisible (400) ou incohérente — passé, hors année cible
    (409)."""
    company = _audit_company(request)
    if company is None:
        return Response(
            {'detail': 'Aucune société associée à ce compte.'},
            status=status.HTTP_400_BAD_REQUEST)
    # ENF11 — corps validé contre le schéma publié (année 1900..2200, dates
    # ISO) : une valeur démesurée ou un `dates` non objet faisait lever (500).
    corps = request.data if isinstance(request.data, dict) else {}
    annee_brute = corps.get('annee')
    if (isinstance(annee_brute, bool) or not isinstance(annee_brute, int)
            or not 1900 <= annee_brute <= 2200):
        return Response(
            {'detail': "Champ 'annee' requis (entier entre 1900 et 2200)."},
            status=status.HTTP_400_BAD_REQUEST)
    annee = annee_brute
    dates = corps.get('dates') or {}
    if not isinstance(dates, dict) or any(
            valeur is not None and not isinstance(valeur, str)
            for valeur in dates.values()):
        return Response(
            {'detail': "Champ 'dates' : objet de dates AAAA-MM-JJ attendu."},
            status=status.HTTP_400_BAD_REQUEST)
    try:
        enregistrer_fetes_mobiles(company, annee, dates, user=request.user)
    except SaisieFetesInvalide as exc:
        # APAR14 — erreurs aussi rangées SOUS leur champ (« erreurs »), en plus
        # du « detail » à plat historique.
        # ENF11 — saisie bien formée mais refusée par la règle (passé, hors
        # année cible) : conflit d'ÉTAT, 409 ; une forme illisible reste 400.
        return Response({'detail': str(exc), 'erreurs': exc.erreurs},
                        status=(status.HTTP_409_CONFLICT if exc.conflit_etat
                                else status.HTTP_400_BAD_REQUEST))
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(fetes_mobiles_saisies(company, annee))
