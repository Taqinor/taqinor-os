"""ACAL238 — la porte de DÉPÔT des gabarits de dossier réglementaire.

``GET/POST /api/django/calepinage/gabarits-dossiers/`` et
``GET/PATCH/DELETE gabarits-dossiers/<id>/`` — contrat
``contract_samples/gabarits_dossier_reglementaire.json`` (ACAL15).

C'est un RÉGLAGE SOCIÉTÉ (comme ``parametres/``) : aucun identifiant de
calepinage n'y entre, d'où son préfixe propre. La porte est UNIQUE pour tous
les genres (dp_mairie, enedis, consuel, manuel…) ; l'écriture vit dans
``services/reglementaire.py`` (``deposer_gabarit``…), cette vue ne fait que
traduire HTTP ↔ service.

* Société TOUJOURS serveur : le queryset est borné à ``request.user.company``
  (``CompanyScopedModelViewSet``) — l'id d'une autre société et un id absent
  reçoivent donc le MÊME 404 ; ``company`` n'est jamais lue du corps.
* Permission = celle des réglages : ``calepinage_gerer`` (lecture comprise —
  un simple lecteur reçoit 403).
* Refus : 400 sous le champ NOMMÉ (``fichier``,
  ``pieces_attendues[i].source_reference``…) ; 409 nommé au DELETE d'un
  gabarit utilisé (PROTECT).
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from ..models import GabaritDossierReglementaire
from ..permissions import PeutGererCalepinage
from ..services.reglementaire import (
    GabaritRefuse, deposer_gabarit, gabarit_publie, modifier_gabarit,
    supprimer_gabarit,
)

__all__ = ['GabaritDossierViewSet']

_FORME_GABARIT = inline_serializer('CalepinageGabaritDossier', {
    'id': serializers.IntegerField(),
    'pays': serializers.CharField(),
    'code': serializers.CharField(),
    'genre': serializers.CharField(),
    'intitule': serializers.CharField(),
    'version': serializers.CharField(),
    'actif': serializers.BooleanField(),
    'pieces_attendues': serializers.ListField(child=serializers.DictField()),
    'champs': serializers.ListField(child=serializers.DictField()),
    'fichiers': serializers.DictField(allow_null=True),
    'depose_par': serializers.DictField(allow_null=True),
    'depose_le': serializers.DateTimeField(allow_null=True),
})


_CORPS_GABARIT = inline_serializer('CalepinageGabaritDossierCorps', {
    'fichier': serializers.FileField(required=False),
    'pays': serializers.CharField(required=False),
    'code': serializers.CharField(required=False),
    'genre': serializers.CharField(required=False),
    'intitule': serializers.CharField(required=False),
    'version': serializers.CharField(required=False),
    'actif': serializers.BooleanField(required=False),
    'pieces_attendues': serializers.JSONField(required=False),
    'champs': serializers.JSONField(required=False),
})


def _donnees(request):
    """Le corps (multipart ou JSON) en dict simple, sans le fichier."""
    brut = request.data
    if hasattr(brut, 'dict'):
        brut = brut.dict()
    donnees = dict(brut) if isinstance(brut, dict) else {}
    donnees.pop('fichier', None)
    donnees.pop('company', None)
    return donnees


def _refus(refus):
    return Response(refus.erreurs, status=refus.statut)


class GabaritDossierViewSet(CompanyScopedModelViewSet):
    """ACAL238 — CRUD société des gabarits de dossier réglementaire."""

    queryset = GabaritDossierReglementaire.objects.select_related(
        'fichier', 'depose_par')
    permission_classes = [PeutGererCalepinage]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    pagination_class = None
    #: YAPIC2/YAPIC11 — tri et recherche DÉCLARÉS (liste blanche) ; l'ordre
    #: par défaut reste celui du registre (pays, intitulé, id).
    ordering_fields = ['pays', 'intitule', 'code', 'version', 'depose_le',
                       'id']
    ordering = ['pays', 'intitule', 'id']
    search_fields = ['intitule', 'code', 'pays']

    def get_permissions(self):
        return [PeutGererCalepinage()]

    @extend_schema(responses={200: inline_serializer(
        'CalepinageGabaritsDossiers',
        {'gabarits': serializers.ListField(child=serializers.DictField())})})
    def list(self, request, *args, **kwargs):
        gabarits = self.filter_queryset(self.get_queryset())
        return Response({'gabarits': [gabarit_publie(g) for g in gabarits]})

    @extend_schema(request=None, responses={200: _FORME_GABARIT})
    def retrieve(self, request, *args, **kwargs):
        return Response(gabarit_publie(self.get_object()))

    @extend_schema(request=_CORPS_GABARIT, responses={201: inline_serializer(
        'CalepinageGabaritDepose', {'gabarit': serializers.DictField()})})
    def create(self, request, *args, **kwargs):
        try:
            gabarit = deposer_gabarit(request.user.company, request.user,
                                      _donnees(request),
                                      request.FILES.get('fichier'))
        except GabaritRefuse as refus:
            return _refus(refus)
        return Response({'gabarit': gabarit_publie(gabarit)},
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=_CORPS_GABARIT, responses={200: _FORME_GABARIT})
    def partial_update(self, request, *args, **kwargs):
        gabarit = self.get_object()
        try:
            modifier_gabarit(gabarit, request.user, _donnees(request),
                             request.FILES.get('fichier'))
        except GabaritRefuse as refus:
            return _refus(refus)
        return Response(gabarit_publie(gabarit))

    @extend_schema(request=None, responses={204: None})
    def destroy(self, request, *args, **kwargs):
        try:
            supprimer_gabarit(self.get_object(), request.user)
        except GabaritRefuse as refus:
            return _refus(refus)
        return Response(status=status.HTTP_204_NO_CONTENT)
