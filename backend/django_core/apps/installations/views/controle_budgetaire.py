"""Vue FG313 — contrôle budgétaire à la commande.

``ControleBudgetaireCommandeView`` : un endpoint de LECTURE qui répond, avant de
valider un bon de commande, si un montant d'achat prévu tient dans le budget
RESTANT du programme (``BudgetProjet``, FG294, même app). Il ne valide rien et ne
modifie rien — c'est un garde-fou consultatif (ROUTINE) que l'écran d'achat
appelle avant l'envoi.

GET /installations/controle-budgetaire/?montant=...&projet=...&categorie=materiel

Multi-tenant : la société vient de ``request.user.company`` (jamais du corps). Le
programme ciblé est implicitement scopé société par le sélecteur. Lecture tout
rôle (consultation), comme les autres lectures budget.
"""
from decimal import Decimal

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAnyRole
from core.champs_stricts import nombre_ou_400

from .. import selectors
from . import _openapi as oa

CATEGORIES = ('materiel', 'main_oeuvre', 'sous_traitance', 'divers')
_MONTANT_OU_VIDE = {'oneOf': [
    {'type': 'number', 'minimum': 0}, {'type': 'string', 'enum': ['']}]}


_ControleBudgetaireSerializer = inline_serializer(
    'ControleBudgetaireResultat', fields={
        'controle': serializers.ChoiceField(
            choices=['non_configure', 'ok', 'depassement']),
        'depasse': serializers.BooleanField(),
        'categorie': serializers.CharField(required=False),
        'reste_categorie': serializers.FloatField(allow_null=True),
        'reste_total': serializers.FloatField(allow_null=True),
        'montant': serializers.FloatField(),
    })


class ControleBudgetaireCommandeView(APIView):
    """FG313 — contrôle budgétaire consultatif avant commande. Lecture tout
    rôle ; aucune écriture. Société posée serveur."""
    permission_classes = [IsAnyRole]

    @extend_schema(
        parameters=[
            # ERR-ENF11 : bornes publiées = bornes lues (montant >= 0, vide =
            # 0 ; projet = id 1..ID_MAX ou vide).
            OpenApiParameter('montant', _MONTANT_OU_VIDE,
                             description="Montant d'achat prévu (>= 0)."),
            OpenApiParameter('projet', oa.ID_OU_VIDE,
                             description='Id du programme.'),
            OpenApiParameter('categorie', OpenApiTypes.STR,
                             enum=list(CATEGORIES), default='materiel'),
        ],
        responses={200: _ControleBudgetaireSerializer})
    def get(self, request):
        company = request.user.company
        # ERR-ENF11 : `NaN` faisait un 500 (comparaison Decimal), `projet=abc`
        # un 500 ORM, `categorie=` (hors énumération) valait « materiel ».
        montant = Decimal(str(nombre_ou_400(
            request.query_params.get('montant'), 'montant', defaut=0, mini=0)))
        projet_id = oa.id_requete(request, 'projet')
        categorie = request.query_params.get('categorie', 'materiel')
        if categorie not in CATEGORIES:
            return Response(
                {'categorie': f'Catégorie inconnue (attendu {CATEGORIES}).'},
                status=status.HTTP_400_BAD_REQUEST)
        result = selectors.controle_budgetaire_commande(
            company, montant, projet_id=projet_id, categorie=categorie)
        return Response(result, status=status.HTTP_200_OK)
