"""Projets, étapes, modèles et revue (reference/api.md §3.3, §4).

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction. Schémas :
l'échantillon de la route quand il existe (`forme_echantillon`), sinon la forme PROJET partagée ;
`GESTE` et `REORDONNER` viennent de `views/taches.py` (déclarés une fois).
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView

from apps.taches.serializers.formes import ProjetSerializer
from apps.taches.views.base import (
    ERREUR_CODE, PAGINATION, PERMISSIONS, PasEncore, corps, forme_echantillon, parametre, reponses,
)
from apps.taches.views.taches import GESTE, REORDONNER
from core.idempotency import IdempotentCreateMixin
from core.openapi_operations import mots_operation

#: 409 d'un projet : `conflit_version` (`lock_version`, `actuel` = PROJET).
CONFLIT_PROJET = inline_serializer('TachesConflitProjet', {
    'detail': serializers.CharField(),
    'code': serializers.CharField(),
    'lock_version': serializers.IntegerField(required=False),
    'actuel': ProjetSerializer(required=False),
})
#: Une étape (« section ») écrite ; `geste_id` comme toute écriture.
SECTION = inline_serializer('TachesSection', {
    'id': serializers.IntegerField(),
    'projet_id': serializers.IntegerField(),
    'nom': serializers.CharField(),
    'rang': serializers.IntegerField(),
    'date_debut': serializers.DateField(allow_null=True),
    'date_fin': serializers.DateField(allow_null=True),
    'geste_id': serializers.IntegerField(allow_null=True),
})
PROJET_ECRIT = forme_echantillon('projet_ecrit')
#: Dupliquer, instancier : aperçu (`apercu:true`) 200, création 201.
APERCU_OU_CREATION = {
    **reponses(forme_echantillon('projet_ecrit'), statut=201, erreurs=(400, 404)),
    200: forme_echantillon('modele_instancier'),
}
SANS_CORPS = reponses(None, statut=204, erreurs=(400, 404))


class ProjetsVue(IdempotentCreateMixin, APIView):
    """GET projets/ (liste paginée + constat) · POST projets/ (créer)."""

    permission_classes = PERMISSIONS
    schema = mots_operation(get='list')  # sinon même operationId que GET projets/{id}/

    @extend_schema(parameters=[parametre('statut', OpenApiTypes.STR, 'actif, en_pause ou archive.'), *PAGINATION],
                   responses=reponses(forme_echantillon('projets_liste'), erreurs=(400,)))
    def get(self, request):
        raise PasEncore()

    @extend_schema(request=corps('Projet', {'nom': 'Chantier X', 'priorite': 2, 'couleur': 'vert', 'icone': '',
                                            'objectif': '', 'domaine': ''}, requis=('nom',)),
                   responses=reponses(PROJET_ECRIT, statut=201, erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class ProjetVue(APIView):
    """GET (PROJET) · PATCH (verrou 409) · DELETE (avec ses tâches) projets/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(ProjetSerializer, erreurs=(404,)))
    def get(self, request, id):
        raise PasEncore()

    @extend_schema(request=inline_serializer('TachesCorpsProjetPatch', {
        'nom': serializers.CharField(required=False, max_length=120),
        'objectif': serializers.CharField(required=False, allow_blank=True),
        'icone': serializers.CharField(required=False, allow_blank=True),
        'couleur': serializers.CharField(required=False),
        'priorite': serializers.IntegerField(required=False),
        'statut': serializers.CharField(required=False),
        'date_debut': serializers.DateField(required=False, allow_null=True),
        'echeance': serializers.DateField(required=False, allow_null=True),
        'domaine': serializers.CharField(required=False, allow_blank=True),
        'confidentiel': serializers.BooleanField(required=False),
        'affichage': serializers.DictField(required=False),
        'risque': serializers.CharField(required=False, allow_blank=True),
        'lock_version': serializers.IntegerField(),
    }), responses=reponses(ProjetSerializer, erreurs=(400, 404), conflit=CONFLIT_PROJET))
    def patch(self, request, id):
        raise PasEncore()

    @extend_schema(request=None, responses=reponses(PROJET_ECRIT, erreurs=(404,)))
    def delete(self, request, id):
        raise PasEncore()


class ProjetReordonnerVue(APIView):
    """POST projets/{id}/reordonner/ — ordre manuel, « Mettre en haut »."""

    permission_classes = PERMISSIONS

    @extend_schema(request=REORDONNER, responses=SANS_CORPS)
    def post(self, request, id):
        raise PasEncore()


class TrierParPrioriteVue(APIView):
    """POST projets/trier-par-priorite/ — ordre par priorité, une fois."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(None, statut=204))
    def post(self, request):
        raise PasEncore()


class ProjetAffichageVue(APIView):
    """GET projets/{id}/vue/ — sections, ITEM, avancement, santé, jalon, burn-up."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[parametre('vue', OpenApiTypes.STR, 'liste, tableau ou chronologie.')],
                   responses=reponses(forme_echantillon('projet_vue'), erreurs=(400, 404)))
    def get(self, request, id):
        raise PasEncore()


class PlanificationApercuVue(APIView):
    """POST projets/{id}/planification/apercu/ — lire une liste, rien n'est écrit."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('PlanificationApercu', {'texte': 'Études :\nVisite\n- photos\n◆ Mise en service'},
                                 requis=('texte',)),
                   responses=reponses(forme_echantillon('planification_apercu'), erreurs=(400, 404)))
    def post(self, request, id):
        raise PasEncore()


class PlanificationVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/planification/ — tout créer, priorité comprise (verrou 409)."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsPlanification', {
        'priorite': serializers.IntegerField(required=False),
        'objectif': serializers.CharField(required=False, allow_blank=True),
        'echeance': serializers.DateField(required=False, allow_null=True),
        'risque': serializers.CharField(required=False, allow_blank=True),
        'sections': serializers.ListField(required=False, child=inline_serializer('TachesCorpsPlanificationSection', {
            'nom': serializers.CharField(),
            'taches': serializers.ListField(child=inline_serializer('TachesCorpsPlanificationTache', {
                'titre': serializers.CharField(max_length=280),
                'jalon': serializers.BooleanField(required=False),
                'sous_taches': serializers.ListField(required=False, child=serializers.CharField()),
            })),
        })),
        'actions': serializers.ListField(required=False, child=inline_serializer('TachesCorpsPlanificationAction', {
            'titre': serializers.CharField(max_length=280),
            'quand': serializers.CharField(required=False),
        })),
        'lock_version': serializers.IntegerField(),
    }), responses=reponses(forme_echantillon('planification'), erreurs=(400, 404), conflit=CONFLIT_PROJET))
    def post(self, request, id):
        raise PasEncore()


class DecalerVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/decaler/ — `{"delta_jours","apercu"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('Decaler', {'delta_jours': 7, 'apercu': True}, requis=('delta_jours',)),
                   responses=reponses(forme_echantillon('decalage'), erreurs=(400, 404)))
    def post(self, request, id):
        raise PasEncore()


class ProjetTerminerVue(APIView):
    """POST projets/{id}/terminer/ — clôture."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsProjetTerminer', {
        'issue': serializers.CharField(),
        'bilan': serializers.CharField(required=False, allow_blank=True),
        'taches_ouvertes': serializers.CharField(required=False),
        'projet_cible_id': serializers.IntegerField(required=False, allow_null=True),
    }), responses=reponses(PROJET_ECRIT, erreurs=(400, 404)))
    def post(self, request, id):
        raise PasEncore()


class ProjetRouvrirVue(APIView):
    """POST projets/{id}/rouvrir/ — réouverture."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(PROJET_ECRIT, erreurs=(404,)))
    def post(self, request, id):
        raise PasEncore()


class ProjetRestaurerVue(APIView):
    """POST projets/{id}/restaurer/ — le projet et les tâches supprimées avec lui."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(PROJET_ECRIT, erreurs=(404,), conflit=ERREUR_CODE))
    def post(self, request, id):
        raise PasEncore()


class DupliquerVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/dupliquer/ — `{"nom","date_debut","apercu"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('Dupliquer', {'nom': 'Salon 2027', 'date_debut': '2027-03-01', 'apercu': True},
                                 requis=('nom',)),
                   responses=APERCU_OU_CREATION)
    def post(self, request, id):
        raise PasEncore()


class EnregistrerModeleVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/enregistrer-modele/ — `{"nom","inclure_notes"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('EnregistrerModele', {'nom': 'Salon', 'inclure_notes': False}, requis=('nom',)),
                   responses=reponses(forme_echantillon('modele'), statut=201, erreurs=(400, 404)))
    def post(self, request, id):
        raise PasEncore()


class SectionsVue(APIView):
    """POST sections/ — `{"projet_id","nom","date_debut"?,"date_fin"?}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsSection', {
        'projet_id': serializers.IntegerField(),
        'nom': serializers.CharField(max_length=120),
        'date_debut': serializers.DateField(required=False, allow_null=True),
        'date_fin': serializers.DateField(required=False, allow_null=True),
    }), responses=reponses(SECTION, statut=201, erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class SectionVue(APIView):
    """PATCH (renommer, dates) · DELETE (tâches « Sans étape ») sections/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsSectionPatch', {
        'nom': serializers.CharField(required=False, max_length=120),
        'date_debut': serializers.DateField(required=False, allow_null=True),
        'date_fin': serializers.DateField(required=False, allow_null=True),
    }), responses=reponses(SECTION, erreurs=(400, 404)))
    def patch(self, request, id):
        raise PasEncore()

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        raise PasEncore()


class SectionReordonnerVue(APIView):
    """POST sections/{id}/reordonner/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=REORDONNER, responses=SANS_CORPS)
    def post(self, request, id):
        raise PasEncore()


class ModelesVue(APIView):
    """GET modeles/ — liste paginée."""

    permission_classes = PERMISSIONS
    schema = mots_operation(get='list')  # sinon même operationId que GET modeles/{id}/

    @extend_schema(parameters=PAGINATION, responses=reponses(forme_echantillon('modeles_liste')))
    def get(self, request):
        raise PasEncore()


class ModeleVue(APIView):
    """GET · PATCH `{"nom"}` · DELETE modeles/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('modele'), erreurs=(404,)))
    def get(self, request, id):
        raise PasEncore()

    @extend_schema(request=corps('ModelePatch', {'nom': 'Salon'}, requis=('nom',)),
                   responses=reponses(forme_echantillon('modele'), erreurs=(400, 404)))
    def patch(self, request, id):
        raise PasEncore()

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        raise PasEncore()


class ModeleInstancierVue(IdempotentCreateMixin, APIView):
    """POST modeles/{id}/instancier/ — `{"nom","date_lancement","apercu"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('ModeleInstancier', {'nom': 'Salon', 'date_lancement': '2026-11-23',
                                                      'apercu': True}, requis=('nom',)),
                   responses=APERCU_OU_CREATION)
    def post(self, request, id):
        raise PasEncore()


class RevueProjetsVue(APIView):
    """GET revue/projets/ — bilan de la semaine (ou Semaine courte) et cartes."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[parametre('semaine', OpenApiTypes.DATE, 'Lundi de la semaine ; défaut : courante.')],
                   responses=reponses(forme_echantillon('revue_projets'), erreurs=(400,)))
    def get(self, request):
        raise PasEncore()


class RevueDecisionVue(APIView):
    """PUT revue/projets/{projet_id}/ — la décision d'une carte de revue."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsRevueDecision', {
        'semaine': serializers.DateField(),
        'intention': serializers.CharField(required=False, allow_blank=True),
        'prochaine_action_id': serializers.IntegerField(required=False, allow_null=True),
        'decision': serializers.CharField(),
        'focus': serializers.BooleanField(required=False),
        'issue': serializers.CharField(required=False, allow_null=True),
    }), responses=reponses(forme_echantillon('revue_decision'), erreurs=(400, 404)))
    def put(self, request, projet_id):
        raise PasEncore()
