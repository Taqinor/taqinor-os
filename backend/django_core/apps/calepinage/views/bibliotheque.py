"""CAL246 — ``GET /calepinages/modeles/`` : les calepinages MARQUÉS modèle.

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
------------------------------------------------------------
Même discipline que ``views/equipements.py`` (CAL243) : d'AUTRES lanes
``backend/calepinage-*`` travaillent en ce moment sur ``views/calepinages.py``
(file-disjoint par construction du plan de lanes) — y ajouter une méthode
créerait un conflit de fusion garanti. L'action est donc posée ICI, sur son
propre fichier, puis RATTACHÉE au ``CalepinageViewSet`` par une ligne
d'import dans ``urls.py`` (affectation d'attribut de classe — le même effet
qu'une définition inline, sans toucher au corps de la classe).

LA BIBLIOTHÈQUE (CAL197-CAL200), EN DEUX ENDROITS — JAMAIS UNE TROISIÈME
FORME D'URL (CAL233)
--------------------------------------------------------------------------
* ``GET /api/django/calepinage/parametres/`` sert DÉJÀ les presets et le
  matériel favori (sections de ``ParametresCalepinage``, CAL45/CAL16) — ce
  module y AJOUTE ``kits`` (catalogue LU, jamais stocké : voir
  ``views/parametres.py``) ;
* ``GET /api/django/calepinage/calepinages/modeles/`` (CETTE action, sur le
  routeur DRF de l'objet métier — ``detail=False``, donc pas de second
  préfixe d'URL) sert les calepinages marqués MODÈLE (CAL199).

Lecture PURE, bornée société par ``get_queryset``/``self.request.user`` comme
toute autre action du viewset — écriture gardée par ``calepinage_gerer``
ailleurs (marquer/démarquer, action de ``services.modeles``).
"""
from __future__ import annotations

from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.utils import extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.champs_stricts import ChaineStricte

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
from ..serializers import (
    FORME_DETAIL_CALEPINAGE, CalepinageLectureSerializer, CalepinageSerializer,
    corps_obligatoire, forme_reponse,
)
from ..services.modeles import ModeleInvalide, calepinages_modeles
from ..services.modeles import demarquer_modele as service_demarquer
from ..services.modeles import marquer_modele as service_marquer
from ..services.variantes import DuplicationEnConflit, VarianteRefusee
from .calepinages import CalepinageViewSet

__all__ = ['modeles', 'marquer_modele', 'demarquer_modele', 'depuis_modele']


@extend_schema(responses=CalepinageLectureSerializer(many=True))
@action(detail=False, methods=['get'], url_path='modeles',
        permission_classes=[PeutVoirCalepinage], pagination_class=None)
def modeles(self, request):
    """CAL199/CAL246 — les calepinages marqués « modèle » de la société.

    Lecture PURE, bornée société (``request.user.company`` — jamais un corps
    de requête)."""
    company = getattr(request.user, 'company', None)
    lignes = calepinages_modeles(company)
    return Response(CalepinageSerializer(lignes, many=True).data)


# ── CALX42 — LES TROIS PORTES D'ÉCRITURE DE LA BIBLIOTHÈQUE ────────────────
# ``services/modeles.py`` porte ``marquer_modele`` (:76), ``demarquer_modele``
# (:97) et ``creer_depuis_modele`` (:140, servi par ``depuis-modele``) ;
# seule la LECTURE ``modeles`` était servie, et l'écran de bibliothèque se
# déclarait en lecture seule « faute de porte ». Les trois portes sont posées
# ICI, dans le module qui sert déjà la lecture — pas un module de plus, donc
# aucune ligne neuve dans ``views/rattachements.py`` (il importe déjà celui-ci).
# Aucun troisième chemin de copie n'est ouvert : ``creer_depuis_modele``
# appelle ``services.variantes.dupliquer`` (CAL14), comme sa docstring le dit.


_FORME_BASCULE = forme_reponse(
    'CalepinageModeleBascule', calepinage=drf_serializers.IntegerField(),
    modele=drf_serializers.BooleanField())


def _identifiant(brut):
    """Un identifiant entier, ou ``None`` — jamais une valeur devinée."""
    if brut in (None, ''):
        return None
    try:
        return int(brut)
    except (TypeError, ValueError):
        return None


@extend_schema(request=None, responses=_FORME_BASCULE)
@action(detail=True, methods=['post'], url_path='marquer-modele',
        permission_classes=[PeutGererCalepinage])
def marquer_modele(self, request, pk=None):
    """CALX42 — pose le drapeau « modèle réutilisable » (idempotent)."""
    calepinage = self.get_object()  # borné société par get_queryset
    try:
        service_marquer(calepinage, user=request.user)
    except ModeleInvalide as refus:
        return Response({refus.champ or 'detail': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response({'calepinage': calepinage.pk, 'modele': True})


@extend_schema(request=None, responses=_FORME_BASCULE)
@action(detail=True, methods=['post'], url_path='demarquer-modele',
        permission_classes=[PeutGererCalepinage])
def demarquer_modele(self, request, pk=None):
    """CALX42 — retire le drapeau « modèle » (idempotent)."""
    calepinage = self.get_object()  # borné société par get_queryset
    service_demarquer(calepinage, user=request.user)
    return Response({'calepinage': calepinage.pk, 'modele': False})


def _modele_de_la_societe(company, brut):
    """ACAL295 — le modèle est résolu dans la BIBLIOTHÈQUE de la société
    (calepinages MARQUÉS modèle, partagés par tous) : un calepinage non
    marqué — visible ou non de l'appelant — est « Modèle introuvable. »,
    jamais copié (aucun oracle par la porte des modèles)."""
    identifiant = _identifiant(brut)
    if not identifiant:
        return None
    return calepinages_modeles(company).filter(pk=identifiant).first()


# ── CALX351 — DÉMARRER DEPUIS UN MODÈLE ET/OU UN JEU DE RÉGLAGES ───────────
# ACAL184 — ``creer-depuis-modele`` (CALX42) est RETIRÉE : ``depuis-modele``
# est la porte UNIQUE (bibliothèque ET écran de création) ; elle
# accepte en plus un DEVIS comme rattachement et un JEU DE RÉGLAGES société
# (``preset_id``) appliqué aux pans du document de départ ; sans modèle, elle
# crée par la porte ordinaire du rattachement (``services/creation.py`` —
# lead, client, ou devis idempotent), le jeu en plus. Aucun troisième chemin
# de copie : la copie reste ``services.modeles.creer_depuis_modele`` (CAL14).
# La réponse est le DÉTAIL agrégé (contrat ``calepinage_detail.json``).

#: Le champ PUBLIÉ par un refus, dans le vocabulaire du corps de la requête.
CHAMPS_DU_CORPS = {'modele': 'modele_id', 'lead': 'lead_id',
                   'client': 'client_id', 'devis': 'devis_id'}


def _refus_nomme(refus):
    """Le refus nommé — 400, ou le statut du refus (``statut_http`` : 404
    pour un jeu de réglages inconnu)."""
    champ = CHAMPS_DU_CORPS.get(refus.champ, refus.champ) or 'detail'
    return Response({champ: str(refus)},
                    status=getattr(refus, 'statut_http',
                                   status.HTTP_400_BAD_REQUEST))


#: Plus grand identifiant d'une clé primaire entière (``AutoField`` PostgreSQL,
#: entier 32 bits) : au-delà, la requête ne peut désigner aucune ligne.
ID_MAX = 2_147_483_647

#: Les identifiants qui désignent LE rattachement du calepinage créé : au moins
#: l'un des trois est exigé (le ``modele_id`` seul n'en est pas un).
RATTACHEMENTS = ('lead_id', 'client_id', 'devis_id')


# ERR-ENF11-FUZZ-CALEPINAGE (w4) — le corps de ``depuis-modele``, UN seul
# prédicat publié ET appliqué : identifiants entiers >= 1 (``0`` n'a jamais
# désigné quoi que ce soit), titre au plus 200 signes (la colonne), ``preset_id``
# texte ; AU MOINS un rattachement (lead, client ou devis) — dit au schéma par
# ``anyOf`` (extension ci-dessous). Ce que la forme ne peut pas dire — l'id
# désigne-t-il une ligne de la société ? le devis est-il déjà lié ? — est un 404
# / 409. (Commentaire et non docstring : elle fuiterait dans l'OpenAPI.)
class CalepinageDepuisModeleCorpsSerializer(drf_serializers.Serializer):
    modele_id = drf_serializers.IntegerField(
        required=False, min_value=1, max_value=ID_MAX)
    lead_id = drf_serializers.IntegerField(
        required=False, min_value=1, max_value=ID_MAX)
    client_id = drf_serializers.IntegerField(
        required=False, min_value=1, max_value=ID_MAX)
    devis_id = drf_serializers.IntegerField(
        required=False, min_value=1, max_value=ID_MAX)
    titre = ChaineStricte(required=False, allow_blank=True, max_length=200,
                          trim_whitespace=False)
    preset_id = ChaineStricte(required=False, allow_blank=True,
                              allow_null=True)

    def validate(self, attrs):
        if not any(attrs.get(cle) for cle in RATTACHEMENTS):
            raise drf_serializers.ValidationError({
                'client_id': ["Aucun client n'a été indiqué : choisissez le "
                              "client dont vous concevez la toiture."]})
        return attrs


class _RattachementExigePublie(OpenApiSerializerExtension):
    """« Au moins un rattachement » PUBLIÉ : sans cela ``{}`` (ou ``{titre}``)
    était un corps « conforme » refusé en 400."""
    target_class = CalepinageDepuisModeleCorpsSerializer

    def map_serializer(self, auto_schema, direction):
        schema = auto_schema._map_serializer(
            self.target, direction, bypass_extensions=True)
        if direction != 'request':
            return schema
        return {**schema, 'anyOf': [{'required': [cle]}
                                    for cle in RATTACHEMENTS]}


@extend_schema(
    request=CalepinageDepuisModeleCorpsSerializer,
    # CI #993 api-fuzz — ``preset_id`` est l'identifiant TEXTE d'un jeu :
    # inconnu ⇒ 404 nommant ``preset_id`` ; non-texte (objet, nombre) ⇒ 400.
    responses={200: FORME_DETAIL_CALEPINAGE, 201: FORME_DETAIL_CALEPINAGE})
@corps_obligatoire
@action(detail=False, methods=['post'], url_path='depuis-modele',
        permission_classes=[PeutGererCalepinage])
def depuis_modele(self, request):
    """CALX351 — ``{modele_id?, lead_id|client_id|devis_id, titre,
    preset_id?}`` → le calepinage créé, en DÉTAIL (201 ; 200 quand un devis
    avait déjà son calepinage).

    Un modèle d'une autre société est INTROUVABLE (404) ; un jeu de réglages
    inconnu est refusé en nommant ``preset_id`` ; ``preset_id`` absent ⇒
    création strictement identique à la porte d'aujourd'hui.
    """
    from ..services.creation import (
        CreationRefusee, DevisTenuParUnArchive, corps_conflit,
        creer_pour_client, demarrer_depuis_modele,
        obtenir_ou_creer_pour_devis,
        ouvrir_ou_creer_pour_lead,
    )
    from .calepinages import detail_calepinage

    champs = CalepinageDepuisModeleCorpsSerializer(data=request.data)
    champs.is_valid(raise_exception=True)
    corps = champs.validated_data
    company = getattr(request.user, 'company', None)
    lead_id = corps.get('lead_id')
    client_id = corps.get('client_id')
    devis_id = corps.get('devis_id')
    titre = corps.get('titre') or ''
    preset_id = corps.get('preset_id')
    brut_modele = corps.get('modele_id')
    cree = True
    try:
        if brut_modele not in (None, ''):
            modele = _modele_de_la_societe(company, brut_modele)
            if modele is None:
                return Response({'modele_id': 'Modèle introuvable.'},
                                status=status.HTTP_404_NOT_FOUND)
            calepinage = demarrer_depuis_modele(
                modele, company, user=request.user, lead_id=lead_id,
                client_id=client_id, devis_id=devis_id, titre=titre,
                preset_id=preset_id)
        elif devis_id:
            calepinage, cree = obtenir_ou_creer_pour_devis(
                devis_id, company, user=request.user, titre=titre,
                preset_id=preset_id)
            if not cree:
                # ACAL295 — l'existant hors de la vue de l'appelant : 409
                # sans identifiant ni nom ; visible : servi comme avant.
                conflit = corps_conflit(calepinage, request.user)
                if 'detail' in conflit:
                    return Response(conflit,
                                    status=status.HTTP_409_CONFLICT)
        elif lead_id:
            # ACAL182 — la porte UNIQUE sur un lead : un lead qui a déjà un
            # calepinage OUVERT n'en reçoit pas un second (D-ACAL-12).
            calepinage, cree = ouvrir_ou_creer_pour_lead(
                lead_id, company, user=request.user, titre=titre,
                preset_id=preset_id)
            if not cree:
                return Response(corps_conflit(calepinage, request.user),
                                status=status.HTTP_409_CONFLICT)
        else:
            calepinage = creer_pour_client(client_id, company,
                                           user=request.user, titre=titre,
                                           preset_id=preset_id)
    except DuplicationEnConflit as conflit:
        # ACAL184 (D-ACAL-12) — le lead cible a déjà un calepinage OUVERT :
        # 409 du contrat calepinage_creation_conflit.json.
        return Response(conflit.corps, status=status.HTTP_409_CONFLICT)
    except DevisTenuParUnArchive as refus:
        # Lot 2 critique #4 — le devis est tenu par un calepinage ARCHIVÉ.
        return Response(refus.corps(), status=status.HTTP_409_CONFLICT)
    except (CreationRefusee, ModeleInvalide, VarianteRefusee) as refus:
        return _refus_nomme(refus)
    return Response(detail_calepinage(calepinage, request),
                    status=(status.HTTP_201_CREATED if cree
                            else status.HTTP_200_OK))


# Rattachement au viewset PIVOT — voir la docstring du module pour le
# pourquoi de cette forme plutôt qu'une méthode inline. Le nom d'attribut est
# EXACTEMENT celui de la fonction : DRF découvre l'action par
# ``get_extra_actions()`` et compare les deux.
CalepinageViewSet.modeles = modeles
CalepinageViewSet.marquer_modele = marquer_modele
CalepinageViewSet.demarquer_modele = demarquer_modele
CalepinageViewSet.depuis_modele = depuis_modele  # CALX351
