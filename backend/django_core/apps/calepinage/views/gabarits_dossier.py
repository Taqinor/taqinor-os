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

from django.http import QueryDict
from drf_spectacular.utils import (
    extend_schema, extend_schema_serializer, inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.response import Response

from core.champs_stricts import BooleenStrict, ChaineStricte
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


#: CI #997 api-fuzz (3) — les éléments de ``pieces_attendues`` / ``champs`` : le
#: modèle (``GabaritDossierReglementaire._erreur_pieces`` / ``_erreur_champs``)
#: exige un code, un intitulé + une source (pièce) ou un libellé (champ) ; un
#: ``DictField`` nu publiait un objet quelconque que le serveur refusait
#: (« Le champ n°1 doit porter un code »). Schéma de REQUÊTE seulement : la
#: validation reste celle du modèle (le code de chaque élément doit en plus
#: être unique dans sa liste, ce qu'un schéma n'exprime pas).
_ELEMENT_PIECE = inline_serializer('CalepinageGabaritPieceAttendue', {
    'code': ChaineStricte(allow_blank=False),
    'intitule': ChaineStricte(allow_blank=False),
    'source_reference': ChaineStricte(allow_blank=False),
    'obligatoire': BooleenStrict(required=False),
})
_ELEMENT_CHAMP = inline_serializer('CalepinageGabaritChampSaisi', {
    'code': ChaineStricte(allow_blank=False),
    'libelle': ChaineStricte(allow_blank=False),
    'type': serializers.ChoiceField(
        choices=GabaritDossierReglementaire.TYPES_CHAMP, required=False),
    'cle_calepinage': serializers.ChoiceField(
        choices=GabaritDossierReglementaire.CLES_PREREMPLISSAGE,
        required=False),
    'obligatoire': BooleenStrict(required=False),
})

#: ERR-ENF11-FUZZ-CALEPINAGE — le fichier PDF ne voyage qu'en ``multipart`` :
#: le corps JSON n'a PAS de champ ``fichier`` (une chaîne vide « conforme » à un
#: champ binaire était refusée). Les listes ``pieces_attendues`` / ``champs``
#: sont du JSON natif en ``application/json``, du TEXTE JSON en multipart (le
#: formulaire) : le schéma multipart ne publie donc que le fichier et les
#: champs scalaires.
_SCALAIRES_GABARIT = {
    'pays': serializers.RegexField(r'^[A-Za-z]{2}$', max_length=2),
    'code': serializers.SlugField(max_length=60),
    # CI #997 api-fuzz : le formulaire envoie ``genre`` vide (facultatif) et le
    # serveur l'accepte — le schéma publie donc un motif qui admet le vide.
    'genre': serializers.RegexField(r'^[-a-zA-Z0-9_]*$', required=False,
                                    max_length=40, allow_blank=True),
    'intitule': ChaineStricte(max_length=200),
    'version': ChaineStricte(required=False, max_length=20, allow_blank=True),
    'actif': serializers.BooleanField(required=False),
}

_CORPS_GABARIT = inline_serializer('CalepinageGabaritDossierCorps', {
    **_SCALAIRES_GABARIT,
    'pieces_attendues': serializers.ListField(
        child=_ELEMENT_PIECE, required=False),
    'champs': serializers.ListField(
        child=_ELEMENT_CHAMP, required=False),
})
_CORPS_GABARIT_MULTIPART = inline_serializer(
    'CalepinageGabaritDossierCorpsFichier', {
        'fichier': serializers.FileField(required=False),
        **_SCALAIRES_GABARIT})
_REQUETE_GABARIT = {'application/json': _CORPS_GABARIT,
                    'multipart/form-data': _CORPS_GABARIT_MULTIPART}


@extend_schema_serializer(many=False)
class CalepinageGabaritsListe(serializers.Serializer):
    """``{gabarits: [...]}`` : l'action s'appelle ``list`` mais ne rend PAS
    un tableau (``many=False`` empêche drf-spectacular de l'envelopper)."""

    gabarits = serializers.ListField(child=serializers.DictField())


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


def _fichier_mal_forme(request):
    """ENF11 (api-fuzz « accepted schema-violating request », ``fichier=``) —
    ``fichier`` est un FICHIER (multipart) : une valeur de formulaire vide ou un
    texte est hors schéma et refusé en 400 nommé, jamais ignoré en silence."""
    if not isinstance(request.data, (dict, QueryDict)):
        return Response({'detail': "Le corps doit être un objet "
                                   "(multipart ou JSON)."},
                        status=status.HTTP_400_BAD_REQUEST)
    if 'fichier' in request.data and 'fichier' not in request.FILES:
        return Response({'fichier': [
            "Le gabarit se dépose en fichier PDF (envoi multipart) : "
            "« fichier » n'est pas un fichier."]},
            status=status.HTTP_400_BAD_REQUEST)
    return None


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

    # Schéma brut (dict) : un sérialiseur serait enveloppé en tableau par
    # drf-spectacular sur l'action ``list`` alors que la réponse est un objet.
    @extend_schema(responses={200: CalepinageGabaritsListe})
    def list(self, request, *args, **kwargs):
        gabarits = self.filter_queryset(self.get_queryset())
        return Response({'gabarits': [gabarit_publie(g) for g in gabarits]})

    @extend_schema(request=None, responses={200: _FORME_GABARIT})
    def retrieve(self, request, *args, **kwargs):
        return Response(gabarit_publie(self.get_object()))

    @extend_schema(request=_REQUETE_GABARIT, responses={201: inline_serializer(
        'CalepinageGabaritDepose', {'gabarit': serializers.DictField()})})
    def create(self, request, *args, **kwargs):
        mal_forme = _fichier_mal_forme(request)
        if mal_forme is not None:
            return mal_forme
        try:
            gabarit = deposer_gabarit(request.user.company, request.user,
                                      _donnees(request),
                                      request.FILES.get('fichier'))
        except GabaritRefuse as refus:
            return _refus(refus)
        return Response({'gabarit': gabarit_publie(gabarit)},
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=_REQUETE_GABARIT, responses={200: _FORME_GABARIT})
    def partial_update(self, request, *args, **kwargs):
        gabarit = self.get_object()
        mal_forme = _fichier_mal_forme(request)
        if mal_forme is not None:
            return mal_forme
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
