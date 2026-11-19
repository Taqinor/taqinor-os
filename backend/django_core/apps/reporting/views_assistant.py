"""RPT3 (copilote vague 2) — ``GET /api/django/reporting/assistant/ca/`` : « combien
on a fait ce mois ? ».

Contrat : ``contract_samples/assistant_ca.json``. L'ERP compte TROIS chiffres
d'affaires qui ne se confondent jamais, et la réponse rend TOUJOURS les trois,
chacun avec son libellé et sa définition (jamais un « CA » nu) :

* SIGNÉ HT — ``metriques_ca.ca_signe_ht`` : devis acceptés en vigueur, à la
  date de signature (la population et le montant du classement commercial) ;
* FACTURÉ HT — ``metriques_ca.ca_facture_ht_periode`` : l'adaptateur de la
  métrique ``ca_ht``, net d'avoirs, à la date d'émission ;
* ENCAISSÉ HT — ``metriques_ca.encaisse_ht`` : le calcul du tableau de bord
  Reporting (part HT des paiements reçus), à la date d'émission des factures.

Garde : celle du tableau de bord Reporting qu'elle reflète (``IsResponsableOrAdmin``
+ lecture du module ventes) et la même portée du rôle (``borner_portee``) : un
commercial « soi » lit SES chiffres, jamais ceux de la société. Délibérément
ABSENTS : marge, prix d'achat, coût, classement des commerciaux, chiffre par
personne.
"""
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin

from .gardes_lecture import lecture_source
from .metriques_ca import ca_facture_ht_periode, ca_signe_ht, encaisse_ht
from .services import portee_du_role

#: Fenêtre publiée : ``du`` et ``au`` inclus, 366 jours au plus.
JOURS_MAX = 366
NOMS = frozenset({'du', 'au', 'format'})
_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}$')
LIEN = '/reporting/commercial'

NOTE = ('Trois chiffres différents : ne jamais dire « le CA » sans dire '
        'lequel.')
NOTE_PORTEE = (' Chiffres limités aux dossiers de votre portée, pas à toute '
               'la société.')


class RefusAssistant(APIException):
    """Refus lisible par le relais : ``detail`` (français, nomme le paramètre),
    ``field`` et ``code`` machine — les seules clés qu'il garde."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'refus_assistant'

    def __init__(self, detail, field, code, statut=None):
        if statut is not None:
            self.status_code = statut
        super().__init__(detail={'detail': detail, 'field': field,
                                 'code': code}, code=code)


def _date(request, nom):
    """La date ``AAAA-MM-JJ`` stricte du paramètre ``nom`` (obligatoire, une
    seule fois) ; sinon 400 qui nomme le paramètre."""
    valeurs = request.query_params.getlist(nom)
    if len(valeurs) > 1:
        raise RefusAssistant(
            f"{nom} : le paramètre ne doit figurer qu'une fois.", nom,
            'parametre_repete')
    brut = valeurs[0].strip() if valeurs else ''
    if not brut:
        raise RefusAssistant(
            f'{nom} : date obligatoire au format AAAA-MM-JJ.', nom,
            'parametre_manquant')
    try:
        if not _ISO.match(brut):
            raise ValueError(brut)
        return date.fromisoformat(brut)
    except ValueError:
        raise RefusAssistant(
            f'{nom} : date attendue au format AAAA-MM-JJ.', nom,
            'date_illisible')


def lire_periode(request):
    """``(du, au)`` validées : paramètres connus, ``au`` ≥ ``du``, 366 jours
    au plus. Toute faute → 400 (paramètre) ou 409 (``au`` < ``du``, plus de 366 jours :
    règles d'ensemble) ``{detail, field, code}`` nommant le paramètre."""
    for nom in sorted(set(request.query_params.keys()) - NOMS):
        raise RefusAssistant(
            f'{nom} : paramètre non déclaré pour cette lecture (du et au '
            'seulement).', nom, 'parametre_inconnu')
    du, au = _date(request, 'du'), _date(request, 'au')
    if au < du:
        # Règles d'ENSEMBLE que le schéma publié ne dit pas : refus d'état 409.
        raise RefusAssistant(
            'au : la date de fin précède la date de début.', 'au',
            'periode_invalide', statut=status.HTTP_409_CONFLICT)
    if (au - du).days + 1 > JOURS_MAX:
        raise RefusAssistant(
            f'au : la période couvre plus de {JOURS_MAX} jours.', 'au',
            'periode_trop_longue', statut=status.HTTP_409_CONFLICT)
    return du, au


def montant(valeur):
    """Montant en texte décimal à deux décimales (arrondi au centime)."""
    return str(Decimal(valeur).quantize(Decimal('0.01'),
                                        rounding=ROUND_HALF_UP))


_PARAMETRES = [
    OpenApiParameter('du', {'type': 'string', 'format': 'date'},
                     OpenApiParameter.QUERY, required=True,
                     description='Premier jour inclus (AAAA-MM-JJ).'),
    OpenApiParameter('au', {'type': 'string', 'format': 'date'},
                     OpenApiParameter.QUERY, required=True,
                     description=f'Dernier jour inclus, au plus {JOURS_MAX} '
                                 'jours après `du`.'),
]
_CHIFFRES = inline_serializer('AssistantCaChiffre', {
    'cle': serializers.ChoiceField(
        choices=['signe_ht', 'facture_ht', 'encaisse_ht']),
    'libelle': serializers.CharField(),
    'montant_ht': serializers.CharField(),
    'definition': serializers.CharField(),
}, many=True)
_REPONSE = inline_serializer('AssistantCaReponse', {
    'du': serializers.DateField(),
    'au': serializers.DateField(),
    'devise': serializers.CharField(),
    'chiffres': _CHIFFRES,
    'note': serializers.CharField(),
    'a_faire': serializers.ChoiceField(choices=['voir_impayes', 'rien']),
    'lien': serializers.CharField(),
})
_REFUS = inline_serializer('AssistantCaRefus', {
    'detail': serializers.CharField(),
    'field': serializers.CharField(),
    'code': serializers.CharField(),
})


@extend_schema(parameters=_PARAMETRES,
               responses={200: _REPONSE, 400: _REFUS, 403: _REFUS, 409: _REFUS})
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin, lecture_source('ventes')])
def ca_trois_chiffres(request):
    """Les trois chiffres d'affaires HT de la période, étiquetés."""
    societe = request.user.company
    if societe is None:
        raise RefusAssistant(
            "Rapport commercial : ce compte n'est rattaché à aucune société.",
            '', 'sans_societe', statut=status.HTTP_403_FORBIDDEN)
    du, au = lire_periode(request)
    signe = ca_signe_ht(societe, request.user, period=(du, au))
    facture = ca_facture_ht_periode(societe, du, au, user=request.user)
    encaisse = encaisse_ht(societe, request.user, period=(du, au))
    restreint = portee_du_role(request.user) is not None
    return Response({
        'du': du.isoformat(),
        'au': au.isoformat(),
        'devise': 'MAD',
        'chiffres': [
            {'cle': 'signe_ht', 'libelle': 'Signé HT',
             'montant_ht': montant(signe),
             'definition': ("Devis acceptés en vigueur, selon la date de "
                            "signature dans la période ; HT remisé, un devis "
                            "remplacé par une révision acceptée ne compte "
                            "pas deux fois.")},
            {'cle': 'facture_ht', 'libelle': 'Facturé HT',
             'montant_ht': montant(facture),
             'definition': ("Factures émises, payées ou en retard, selon la "
                            "date d'émission dans la période ; HT net "
                            "d'avoirs, hors brouillons et annulées.")},
            {'cle': 'encaisse_ht', 'libelle': 'Encaissé HT',
             'montant_ht': montant(encaisse),
             'definition': ("Paiements reçus à ce jour sur les factures "
                            "émises dans la période (date d'émission, pas "
                            "date de paiement), ramenés au HT — comme le "
                            "tableau de bord.")},
        ],
        'note': NOTE + (NOTE_PORTEE if restreint else ''),
        'a_faire': 'voir_impayes' if facture > encaisse else 'rien',
        'lien': LIEN,
    })
