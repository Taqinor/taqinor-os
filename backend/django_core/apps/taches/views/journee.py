"""Journée, rituels et pastille (reference/api.md §2, §3.1, §4).

Routes déclarées : une vue pas encore construite lève `PasEncore` (501) ; le schéma OpenAPI de
chaque route est celui de son échantillon de `contract_samples/` (`forme_echantillon`). Les vues
construites lisent le jour (`?jour=`, défaut : aujourd'hui) et l'heure murale, puis délèguent tout à
`services/journee.py`.
"""
import datetime
from contextlib import contextmanager

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.taches.serializers.formes import TacheEcriteSerializer, contexte
from apps.taches.serializers.journee import PLAFOND_LIGNES
from apps.taches.services import journee as services
from apps.taches.views.base import (
    PERMISSIONS, PasEncore, corps, est_assistant, forme_echantillon, parametre, reponses)
from core.idempotency import IdempotentCreateMixin

JOUR = parametre('jour', OpenApiTypes.DATE, 'Jour (AAAA-MM-JJ) ; défaut : aujourd\'hui.')
TOUT = parametre('tout', OpenApiTypes.BOOL, '1 : « Voir toutes les tâches de mes projets ».')
MESSAGE_DATE = 'Date attendue (AAAA-MM-JJ).'
VRAI = ('1', 'true', 'oui')


def date_de(valeur, champ):
    """Une date AAAA-MM-JJ, ou 400 au champ nommé."""
    try:
        return datetime.date.fromisoformat(str(valeur))
    except (TypeError, ValueError):
        raise ValidationError({champ: [MESSAGE_DATE]})


def jour_de(request, champ='jour'):
    """`?jour=` (défaut : aujourd'hui, fuseau de la société)."""
    texte = request.query_params.get(champ)
    return date_de(texte, champ) if texte else timezone.localdate()


def maintenant():
    """Heure murale de la société."""
    return timezone.localtime()


def drapeau(request, champ):
    return (request.query_params.get(champ) or '').lower() in VRAI


def ids_de(request, champ):
    """`?exclure=41,42` → [41, 42] ; un morceau qui n'est pas un nombre est ignoré (lecture seule)."""
    morceaux = (request.query_params.get(champ) or '').split(',')
    return [int(m) for m in (m.strip() for m in morceaux) if m.isdigit()]


def par_compte(request):
    """Espace de clés d'idempotence propre au compte (deux comptes, même clé : deux gestes)."""
    return f'compte-{request.user.pk}'


def valide(classe, donnees):
    serializer = classe(data=donnees)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@contextmanager
def refus_en_400():
    """`services.journee.Refus` → 400 au champ nommé."""
    try:
        yield
    except services.Refus as exc:
        raise ValidationError(exc.erreurs)


class LigneCorps(serializers.Serializer):
    type = serializers.ChoiceField(choices=(services.TACHE, services.ACTIVITE))
    id = serializers.IntegerField(min_value=1)


class PlanifierCorps(serializers.Serializer):
    jour = serializers.DateField()
    mode = serializers.CharField()
    lignes = serializers.ListField(child=LigneCorps(), max_length=PLAFOND_LIGNES)
    essentielles = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False,
                                         default=list)
    triage = serializers.ListField(required=False, default=list)


class EssentielCorps(serializers.Serializer):
    tache_id = serializers.IntegerField(min_value=1)
    essentielle = serializers.BooleanField()


class AujourdhuiVue(APIView):
    """GET aujourdhui/ — LE contrat de la journée (§2)."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[JOUR, TOUT], responses=reponses(forme_echantillon('aujourdhui'), erreurs=(400,)))
    def get(self, request):
        return Response(services.aujourdhui(request.user, jour_de(request), maintenant(),
                                            tout=drapeau(request, 'tout'), assistant=est_assistant(request)))


class BadgeVue(APIView):
    """GET badge/ — la pastille : ouverts GARDÉS d'Essentiel, Prévu et Ce soir."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('badge')))
    def get(self, request):
        return Response(services.badge(request.user, timezone.localdate()))


class VuVue(APIView):
    """POST vu/ — ouverture du jour ; carte de retour."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('Vu', {'ecran': 'aujourdhui'}),
                   responses=reponses(forme_echantillon('vu'), erreurs=(400,)))
    def post(self, request):
        heure = maintenant()
        return Response(services.vu(request.user, heure.date(), heure))


class PropositionJourneeVue(APIView):
    """GET journee/proposition/ — la proposition du jour, sans écriture."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[
        JOUR, TOUT,
        parametre('exclure', OpenApiTypes.STR, 'Ids de tâches exclues, séparés par des virgules.'),
        parametre('inclure', OpenApiTypes.STR, 'Ids de tâches ajoutées, séparés par des virgules.'),
    ], responses=reponses(forme_echantillon('journee_proposition'), erreurs=(400,)))
    def get(self, request):
        heure = maintenant()
        return Response(services.proposition_du_jour(
            request.user, jour_de(request), heure, exclure=ids_de(request, 'exclure'),
            inclure=ids_de(request, 'inclure'), tout=drapeau(request, 'tout'), assistant=est_assistant(request)))


class PrioritesVue(APIView):
    """GET journee/priorites/ — « Aide-moi à prioriser »."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[JOUR], responses=reponses(forme_echantillon('priorites'), erreurs=(400,)))
    def get(self, request):
        raise PasEncore()


class PointVue(APIView):
    """GET journee/point/ — « Où j'en suis ? »."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('point')))
    def get(self, request):
        raise PasEncore()


class PlanifierJourneeVue(IdempotentCreateMixin, APIView):
    """POST journee/planifier/ — « Garder ces N » (mode `express`)."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('JourneePlanifier', {
        'jour': '2026-11-17', 'mode': 'express', 'lignes': [{'type': 'tache', 'id': 30}],
        'essentielles': [20], 'triage': [],
    }, requis=('jour', 'mode', 'lignes')), responses=reponses(forme_echantillon('journee_ecrite'), erreurs=(400,)))
    def post(self, request):
        return self._avec_idempotence(request, lambda: self._planifier(request), suffixe=par_compte(request))

    def _planifier(self, request):
        corps_ = valide(PlanifierCorps, request.data)
        with refus_en_400():
            return Response(services.planifier_express(
                request.user, corps_['jour'], maintenant(), lignes=corps_['lignes'],
                essentielles=corps_['essentielles'], mode=corps_['mode'], assistant=est_assistant(request)))


class EssentielVue(APIView):
    """POST journee/essentiel/ — ★."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('JourneeEssentiel', {'tache_id': 20, 'essentielle': True},
                                 requis=('tache_id', 'essentielle')),
                   responses=reponses(TacheEcriteSerializer, erreurs=(400, 404)))
    def post(self, request):
        corps_ = valide(EssentielCorps, request.data)
        with refus_en_400():
            ecrite = services.marquer_essentielle(request.user, corps_['tache_id'], corps_['essentielle'],
                                                  maintenant())
        contexte_ = contexte(assistant=est_assistant(request))
        return Response(TacheEcriteSerializer(ecrite, context=contexte_).data)


class AllegerVue(IdempotentCreateMixin, APIView):
    """POST journee/alleger/ — garder k, le reste aux projets sans report."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('JourneeAlleger', {'jour': '2026-11-17', 'garder': [20, 42]},
                                 requis=('jour', 'garder')),
                   responses=reponses(forme_echantillon('journee_ecrite'), erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class ClotureVue(APIView):
    """GET journee/cloture/ — le contenu du bilan du soir."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[JOUR], responses=reponses(forme_echantillon('journee_cloture'), erreurs=(400,)))
    def get(self, request):
        raise PasEncore()


class CloturerVue(IdempotentCreateMixin, APIView):
    """POST journee/cloturer/ — clore la journée."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('JourneeCloturer', {
        'jour': '2026-11-17', 'choix': [{'id': 52, 'choix': 'jour', 'jour': '2026-11-23'}],
        'le_reste': True, 'reflexion': '',
    }, requis=('jour',)), responses=reponses(forme_echantillon('journee_cloturee'), erreurs=(400,)))
    def post(self, request):
        raise PasEncore()
