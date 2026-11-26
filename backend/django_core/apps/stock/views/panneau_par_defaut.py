"""D-ACAL-169 — LE panneau par défaut de la société : lecture (tout le stock) et désignation (un responsable).

Vues DÉDIÉES, hors de ``ProduitViewSet`` : ``views/produit.py`` dépasse 2 000 lignes et ne grossit plus (règle
FICHIER_MUR) ; les routes restent sous ``stock/produits/<id>/…`` (``urls.py``, avant le routeur). Contrat :
``contract_samples/panneau_par_defaut.json``. Aucun prix dans aucune réponse.

Droits :
* lecture ``GET stock/panneau-par-defaut/`` — ``LectureDuModule`` (qui ouvre le stock, Technicien compris : le nom
  du panneau par défaut n'est pas un prix) ;
* ``definir-`` / ``retirer-panneau-par-defaut`` — ``catalogue_prix_modifier`` (« Modifier les prix du catalogue »,
  Directeur + Administrateur par défaut ; compte hérité sans rôle fin : responsable/admin, ``HasPermissionOrLegacy``).
  Ce geste décide du panneau — donc du prix — de tout devis composé automatiquement : c'est un geste de catalogue
  réservé aux responsables, jamais ``stock_voir`` ni la simple modification d'une fiche (``stock_modifier``).
"""
from django.http import Http404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import HasPermissionOrLegacy, LectureDuModule
from core.entite_scoping import scope_entite_queryset

from .. import selectors_panneau_defaut, services_panneau_defaut
from ..models import Produit

DROIT_DESIGNER = 'catalogue_prix_modifier'

_RESUME = inline_serializer('StockPanneauParDefaut', {
    'produit_id': serializers.IntegerField(allow_null=True),
    'nom': serializers.CharField(allow_null=True),
    'pmax_wc': serializers.FloatField(allow_null=True),
    'source': serializers.ChoiceField(choices=selectors_panneau_defaut.SOURCES),
    'motif': serializers.CharField(allow_null=True),
})
_ERREUR = inline_serializer('StockPanneauParDefautErreur', {
    'panneau_par_defaut': serializers.ListField(child=serializers.CharField(), required=False),
    'detail': serializers.CharField(required=False),
})


def _produit_de_la_societe(request, pk):
    """Le produit ``pk`` de la société de l'utilisateur, dans sa portée d'entités, ARCHIVÉS COMPRIS (pour refuser un
    archivé par une phrase, pas par un 404). Un produit global ou d'une autre société, ou un compte sans société
    (qui sinon « verrait » les produits globaux, ``company_id`` NULL) : 404."""
    if request.user.company_id is None:
        raise Http404
    qs = scope_entite_queryset(
        Produit.objects.filter(company_id=request.user.company_id), request.user, 'entite')
    produit = qs.select_related('categorie', 'fiche_technique').filter(pk=pk).first()
    if produit is None:
        raise Http404
    return produit


class PanneauParDefautView(APIView):
    """``GET stock/panneau-par-defaut/`` — le résumé du contrat (cinq clés, toujours)."""

    permission_classes = [LectureDuModule]
    permission_module = 'stock'
    http_method_names = ['get', 'head', 'options']

    @extend_schema(responses={200: _RESUME})
    def get(self, request):
        return Response(selectors_panneau_defaut.resume_panneau_par_defaut(request.user.company))


class DefinirPanneauParDefautView(APIView):
    """``POST stock/produits/<id>/definir-panneau-par-defaut/`` — désigne CE produit (retire le précédent)."""

    permission_classes = [HasPermissionOrLegacy(DROIT_DESIGNER)]
    permission_module = 'stock'
    http_method_names = ['post', 'options']

    @extend_schema(request=None, responses={200: _RESUME, 400: _ERREUR, 404: _ERREUR})
    def post(self, request, pk):
        produit = _produit_de_la_societe(request, pk)
        resume = services_panneau_defaut.definir_panneau_par_defaut(request.user.company, produit, request.user)
        return Response(resume)


class RetirerPanneauParDefautView(APIView):
    """``POST stock/produits/<id>/retirer-panneau-par-defaut/`` — retire le drapeau de CE produit (idempotent)."""

    permission_classes = [HasPermissionOrLegacy(DROIT_DESIGNER)]
    permission_module = 'stock'
    http_method_names = ['post', 'options']

    @extend_schema(request=None, responses={200: _RESUME, 404: _ERREUR})
    def post(self, request, pk):
        produit = _produit_de_la_societe(request, pk)
        resume = services_panneau_defaut.retirer_panneau_par_defaut(request.user.company, produit, request.user)
        return Response(resume)
