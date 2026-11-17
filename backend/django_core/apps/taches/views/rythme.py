"""Rythme, cartes à réponse, préférences dites et en-tête du Copilote (reference/api.md §3.4, §4).

Toute donnée est celle de `request.user` (société ET propriétaire, `selectors/rythme.py`) ; le jour
est `services.rythme.aujourdhui()`. Le schéma OpenAPI de chaque route est celui de son échantillon de
`contract_samples/`.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.taches.choix import SourcePreference
from apps.taches.serializers.rythme import forme_proposition, forme_rythme, projets_cites
from apps.taches.services import rythme as service
from apps.taches.views.base import (
    ERREUR_CODE, PERMISSIONS, corps, est_assistant, forme_echantillon, reponses,
)

RYTHME = forme_echantillon('rythme')
INTROUVABLE = 'Introuvable.'
#: 409 d'une carte qui n'est plus ouverte (contract_samples/erreurs.json `proposition_expiree`).
DETAIL_EXPIREE = 'Proposition expirée.'
CODE_EXPIREE = 'proposition_expiree'


def rythme_de(request, *, geste=None):
    """La réponse RYTHME de l'utilisateur de `request` (relue après une écriture)."""
    reglages = service.reglages_ou_defauts(request.user)
    return forme_rythme(request.user, reglages, service.aujourdhui(), assistant=est_assistant(request),
                        geste_id=geste.pk if geste is not None else None)


class RythmeVue(APIView):
    """GET rythme/ (RYTHME) · POST rythme/ `{"mode","objectif"?,"sens"?}` (seul chemin du mode)."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(RYTHME))
    def get(self, request):
        return Response(rythme_de(request))

    @extend_schema(request=inline_serializer('TachesCorpsRythme', {
        'mode': serializers.CharField(),
        'objectif': serializers.IntegerField(required=False),
        'sens': serializers.CharField(required=False),
    }), responses=reponses(RYTHME, erreurs=(400, 404)))
    def post(self, request):
        try:
            _reglages, geste = service.regler_rythme(request.user, request.data, service.aujourdhui())
        except service.ErreursRythme as exc:
            return Response(exc.erreurs, status=status.HTTP_400_BAD_REQUEST)
        except service.SansReglages:
            raise NotFound(INTROUVABLE)
        return Response(rythme_de(request, geste=geste))


class RepondrePropositionVue(APIView):
    """POST rythme/propositions/{id}/repondre/ — `{"reponse"}`, toute carte à réponse."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('RepondreProposition', {'reponse': 'oui'}, requis=('reponse',)),
                   responses=reponses(forme_echantillon('proposition_repondue'), erreurs=(400, 404),
                                      conflit=ERREUR_CODE))
    def post(self, request, id):
        try:
            carte, geste = service.repondre_carte(request.user, id, request.data.get('reponse'),
                                                  service.aujourdhui())
        except service.ErreursRythme as exc:
            return Response(exc.erreurs, status=status.HTTP_400_BAD_REQUEST)
        except (service.Introuvable, service.SansReglages):
            raise NotFound(INTROUVABLE)
        except service.PropositionExpiree:
            return Response({'detail': DETAIL_EXPIREE, 'code': CODE_EXPIREE}, status=status.HTTP_409_CONFLICT)
        assistant = est_assistant(request)
        projets = projets_cites(request.user, [carte])
        return Response({'proposition': forme_proposition(carte, assistant=assistant, projets=projets),
                         'rythme': rythme_de(request, geste=geste), 'geste_id': geste.pk})


class PreferencesVue(APIView):
    """POST preferences/ — poser `{"cle","valeur"}` → RYTHME."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsPreference', {
        'cle': serializers.CharField(),
        'valeur': serializers.JSONField(),
    }), responses=reponses(RYTHME, erreurs=(400,)))
    def post(self, request):
        source = SourcePreference.COPILOTE if est_assistant(request) else SourcePreference.ECRAN
        try:
            geste = service.poser_preference(request.user, request.data.get('cle'), request.data.get('valeur'),
                                             source)
        except service.ErreursRythme as exc:
            return Response(exc.erreurs, status=status.HTTP_400_BAD_REQUEST)
        return Response(rythme_de(request, geste=geste))


class PreferenceVue(APIView):
    """DELETE preferences/{cle}/ — retirer une préférence dite → RYTHME."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(RYTHME, erreurs=(404,)))
    def delete(self, request, cle):
        try:
            geste = service.retirer_preference(request.user, cle)
        except service.Introuvable:
            raise NotFound(INTROUVABLE)
        return Response(rythme_de(request, geste=geste))


class CoachEnteteVue(APIView):
    """GET coach/entete/ — deux lignes (≤ 300 caractères) pour le relais du Copilote."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('coach_entete')))
    def get(self, request):
        return Response({'lignes': service.entete_coach(request.user, service.aujourdhui())})
