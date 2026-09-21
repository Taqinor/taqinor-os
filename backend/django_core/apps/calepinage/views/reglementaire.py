"""CAL191 — la vue ``GET /calepinages/<pk>/dossiers-reglementaires/``.

Elle sert MOT POUR MOT le contrat ``contract_samples/
dossiers_reglementaires.json`` (CAL247), que l'écran des dossiers (CAL196)
consomme : liste des dossiers disponibles pour le PAYS de la société, état
pièce par pièce, champs « à compléter » VENANT DU SERVEUR, et le message qui
dit quoi déposer quand la société n'a aucun gabarit.

Même forme que ``views/equipements.py`` (CAL243) : le code vit dans son
propre fichier et l'action est RATTACHÉE au ``CalepinageViewSet`` par une
affectation d'attribut de classe, depuis un import d'``urls.py`` exécuté
AVANT ``router.register`` — deux lanes travaillent en parallèle sur
``views/calepinages.py``, y ajouter une méthode garantirait un conflit.

La lecture est PURE : aucune écriture, aucun dossier créé au passage (un GET
qui crée une ligne en base est un GET qui ment).

CALX40 — LA PORTE DE GÉNÉRATION
--------------------------------
``services/reglementaire.py`` savait déjà PRODUIRE un dossier
(``construire_pack_dossier``, écrit et testé) mais aucune vue ne l'exposait :
l'écran portait donc un bouton « Générer le dossier » définitivement inerte.
``POST calepinages/<pk>/generer-dossier/`` ouvre cette porte — et RIEN
d'autre :

* aucun second chemin de rendu ni de dépôt n'est créé (règle fondateur n°4) :
  la vue APPELLE le service existant, qui rend les pièces du module et les
  dépose par la plomberie déjà en service ;
* aucun formulaire officiel n'est fabriqué sans le gabarit DÉPOSÉ par la
  société : sans gabarit, la réponse est un 400 qui NOMME ce qui manque et dit
  quoi déposer (jamais un « non enregistré » générique) ;
* le serveur re-vérifie lui-même ``peut_generer`` sur l'agrégat du contrat
  CAL247 : un écran qui aurait laissé cliquer un bouton grisé ne peut pas
  faire sortir un dossier amputé.
"""
from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
from ..services.reglementaire import (
    DossierRefuse, construire_pack_dossier, dossiers_du_calepinage,
)
from .calepinages import CalepinageViewSet

__all__ = ['dossiers_reglementaires', 'generer_dossier']


def _forme():
    """YAPIC6/PACT7 — la forme DÉCLARÉE, tirée du contrat CAL247."""
    return inline_serializer('CalepinageDossiersReglementaires', {
        'calepinage': serializers.IntegerField(),
        'pays': serializers.CharField(allow_null=True),
        'gabarits_deposes': serializers.IntegerField(),
        'message_aucun_gabarit': serializers.CharField(allow_null=True),
        'dossiers': serializers.ListField(child=serializers.DictField()),
    })


@extend_schema(responses={200: _forme()})
@action(detail=True, methods=['get'], url_path='dossiers-reglementaires',
        permission_classes=[PeutVoirCalepinage])
def dossiers_reglementaires(self, request, pk=None):
    """CAL191 — les dossiers réglementaires du calepinage (contrat CAL247)."""
    return Response(dossiers_du_calepinage(self.get_object()))


# ── CALX40 — OUVRIR LA GÉNÉRATION D'UN DOSSIER ────────────────────────────

#: Le message servi quand la demande ne désigne aucun dossier.
MESSAGE_SANS_DESIGNATION = (
    "Indiquez le dossier à générer : « dossier » (un dossier déjà commencé) "
    "ou « gabarit » (le gabarit déposé par la société)."
)


def _forme_generation():
    """La forme DÉCLARÉE de la réponse de génération (CALX40)."""
    return inline_serializer('CalepinageGenererDossier', {
        'dossier': serializers.IntegerField(),
        'document': serializers.IntegerField(allow_null=True),
        'genere_le': serializers.DateTimeField(allow_null=True),
        'pieces': serializers.ListField(child=serializers.DictField()),
        'signalements': serializers.ListField(child=serializers.CharField()),
    })


def _compose_designe(agregat, corps):
    """Le dossier COMPOSÉ désigné par le corps, ou ``None``.

    On cherche dans l'agrégat du contrat CAL247 (et pas directement en base) :
    ce que le serveur accepte de générer est EXACTEMENT ce que l'écran voit,
    jamais un dossier d'un autre pays ou d'un gabarit désactivé.
    """
    demande_dossier = corps.get('dossier')
    demande_gabarit = corps.get('gabarit')
    for compose in agregat.get('dossiers') or []:
        if demande_dossier is not None and compose.get('id') is not None:
            if str(compose['id']) == str(demande_dossier):
                return compose
        if demande_gabarit is not None and compose.get('gabarit_id') is not None:
            if str(compose['gabarit_id']) == str(demande_gabarit):
                return compose
    return None


def _dossier_en_base(calepinage, compose):
    """La ligne ``DossierReglementaire`` du dossier composé, créée si besoin.

    Un dossier jamais commencé sort de l'agrégat avec ``id = null`` : c'est ce
    POST — jamais le GET — qui l'ouvre. La société vient TOUJOURS du
    calepinage (jamais du corps de la requête).
    """
    from ..models import DossierReglementaire, GabaritDossierReglementaire

    company = calepinage.company
    if compose.get('id') is not None:
        return DossierReglementaire.objects.filter(
            company=company, calepinage=calepinage,
            pk=compose['id']).first()
    gabarit = GabaritDossierReglementaire.objects.filter(
        company=company, pk=compose.get('gabarit_id')).first()
    if gabarit is None:
        return None
    dossier, _cree = DossierReglementaire.objects.get_or_create(
        company=company, calepinage=calepinage, gabarit=gabarit)
    return dossier


@extend_schema(responses={200: _forme_generation()})
@action(detail=True, methods=['post'], url_path='generer-dossier',
        permission_classes=[PeutGererCalepinage])
def generer_dossier(self, request, pk=None):
    """CALX40 — ``POST /calepinages/<pk>/generer-dossier/``.

    Le corps porte ``{dossier: <id>}`` ou ``{gabarit: <id>}``. Tout refus est
    rendu 400 SOUS LE CHAMP qu'il concerne (``gabarit``, ``dossier``, ou le
    code de la pièce qui n'a pas pu être rendue), avec le motif en français —
    jamais un « non enregistré » générique.
    """
    calepinage = self.get_object()
    corps = request.data if isinstance(request.data, dict) else {}
    agregat = dossiers_du_calepinage(calepinage)

    if agregat.get('message_aucun_gabarit'):
        # Société sans AUCUN gabarit déposé : le message dit quoi déposer.
        return Response({'gabarit': [agregat['message_aucun_gabarit']]},
                        status=status.HTTP_400_BAD_REQUEST)

    compose = _compose_designe(agregat, corps)
    if compose is None:
        return Response({'dossier': [MESSAGE_SANS_DESIGNATION]},
                        status=status.HTTP_400_BAD_REQUEST)
    if not (compose.get('gabarit') or {}).get('present'):
        return Response({'gabarit': [compose['motif_non_generable']]},
                        status=status.HTTP_400_BAD_REQUEST)
    if not compose.get('peut_generer'):
        return Response({'dossier': [compose['motif_non_generable']]},
                        status=status.HTTP_400_BAD_REQUEST)

    dossier = _dossier_en_base(calepinage, compose)
    if dossier is None:
        return Response({'dossier': [MESSAGE_SANS_DESIGNATION]},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        pack = construire_pack_dossier(dossier, created_by=request.user)
    except DossierRefuse as refus:
        return Response({refus.piece or 'dossier': [str(refus)]},
                        status=status.HTTP_400_BAD_REQUEST)

    document = pack.get('document')
    dossier.document_id = getattr(document, 'pk', None)
    dossier.genere_le = timezone.now()
    dossier.save(update_fields=['document_id', 'genere_le'])
    return Response({
        'dossier': dossier.pk,
        'document': dossier.document_id,
        'genere_le': dossier.genere_le,
        'pieces': [{'code': code, 'libelle': libelle}
                   for code, libelle in pack.get('pieces') or ()],
        'signalements': list(pack.get('signalements') or ()),
    })


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.dossiers_reglementaires = dossiers_reglementaires
CalepinageViewSet.generer_dossier = generer_dossier
