"""Tâches, À trier, fiche et ce qui s'y rattache (reference/api.md §3.1-§3.2, §4) : recherche, listes,
fiche, actions d'une tâche, lot, rappels, récurrences, check-list, étiquettes, vues enregistrées,
supprimées récemment, derniers gestes.

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction. Schémas :
l'échantillon de la route quand il existe (`forme_echantillon`), sinon une forme partagée
(`serializers/formes.py`) ; `GESTE`, `CONFLIT_TACHE` et `REORDONNER` sont déclarés ici une fois.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView

from apps.taches.serializers.formes import (
    EtiquetteCourteSerializer, ItemSerializer, TacheEcriteSerializer, TacheSerializer,
)
from apps.taches.views.base import (
    ERREUR_CODE, PAGINATION, PERMISSIONS, PasEncore, corps, forme_echantillon, page_de, parametre,
    reponses,
)
from apps.taches.views.saisie import CHAMPS_LIGNE
from core.idempotency import IdempotentCreateMixin
from core.openapi_operations import mots_operation

#: Réponse d'une écriture qui ne rend que son geste annulable (`{"geste_id"}`).
GESTE = inline_serializer('TachesGeste', {'geste_id': serializers.IntegerField(allow_null=True)})
#: 409 d'une tâche : `conflit_version` (`lock_version`, `actuel` = TACHE) ou `autre_compte`.
CONFLIT_TACHE = inline_serializer('TachesConflitTache', {
    'detail': serializers.CharField(),
    'code': serializers.CharField(),
    'lock_version': serializers.IntegerField(required=False),
    'actuel': TacheSerializer(required=False),
})
#: Corps d'un réordonnancement : la place entre deux voisins (aucun geste rendu : 204).
REORDONNER = inline_serializer('TachesCorpsReordonner', {
    'liste': serializers.CharField(required=False),
    'avant_id': serializers.IntegerField(required=False, allow_null=True),
    'apres_id': serializers.IntegerField(required=False, allow_null=True),
})
PROPRIETAIRE_ATTENDU = corps('ProprietaireAttendu', {'proprietaire_attendu': 7})
ECRITE = reponses(TacheEcriteSerializer, erreurs=(400, 404))
ECRITE_AVEC_COMPTE = reponses(TacheEcriteSerializer, erreurs=(400, 404), conflit=ERREUR_CODE)
VUE_ENREGISTREE = inline_serializer('TachesVueEnregistree', {
    'id': serializers.IntegerField(), 'nom': serializers.CharField(), 'rang': serializers.IntegerField(),
    'filtres': serializers.DictField(),
})

FILTRES_LISTE = [
    parametre('vue', OpenApiTypes.STR, 'boite (À trier), quelque_jour (En réserve)…'),
    parametre('q', OpenApiTypes.STR, 'Mots, sans accents.'),
    parametre('projet', OpenApiTypes.INT),
    parametre('section', OpenApiTypes.INT),
    parametre('etiquette', OpenApiTypes.INT),
    parametre('priorite_min', OpenApiTypes.INT),
    parametre('statut', OpenApiTypes.STR),
    parametre('periode', OpenApiTypes.STR),
    parametre('tri', OpenApiTypes.STR),
    parametre('groupe', OpenApiTypes.STR),
    parametre('inclure_faites', OpenApiTypes.BOOL),
    parametre('cible', OpenApiTypes.STR, 'Fiche ERP liée (crm.lead, crm.client, ventes.devis).'),
    parametre('cible_id', OpenApiTypes.INT),
    parametre('ouvertes', OpenApiTypes.BOOL),
    *PAGINATION,
]


class RechercheVue(APIView):
    """GET recherche/ — projets et tâches par mots."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[parametre('q', OpenApiTypes.STR, 'Mots cherchés (requis).'),
                               parametre('limite', OpenApiTypes.INT)],
                   responses=reponses(forme_echantillon('recherche'), erreurs=(400,)))
    def get(self, request):
        raise PasEncore()


class TachesVue(IdempotentCreateMixin, APIView):
    """GET taches/ (listes paginées) · POST taches/ (une LIGNE)."""

    permission_classes = PERMISSIONS
    schema = mots_operation(get='list')  # sinon même operationId que GET taches/{id}/

    @extend_schema(parameters=FILTRES_LISTE, responses=reponses(page_de('Items', ItemSerializer()), erreurs=(400,)))
    def get(self, request):
        raise PasEncore()

    @extend_schema(request=inline_serializer('TachesCorpsTache', {
        **CHAMPS_LIGNE,
        'parent_id': serializers.IntegerField(required=False, allow_null=True),
        'proprietaire_attendu': serializers.IntegerField(required=False),
    }), responses=reponses(TacheEcriteSerializer, statut=201, erreurs=(400,), conflit=ERREUR_CODE))
    def post(self, request):
        raise PasEncore()


class TacheVue(APIView):
    """GET (TACHE, lien revérifié) · PATCH (verrou 409) · DELETE taches/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(TacheSerializer, erreurs=(404,)))
    def get(self, request, id):
        raise PasEncore()

    @extend_schema(request=inline_serializer('TachesCorpsTachePatch', {
        'titre': serializers.CharField(required=False, max_length=280),
        'notes': serializers.CharField(required=False, allow_blank=True),
        'priorite': serializers.IntegerField(required=False),
        'echeance': serializers.DateField(required=False, allow_null=True),
        'echeance_heure': serializers.CharField(required=False, allow_null=True),
        'estimation_minutes': serializers.IntegerField(required=False, allow_null=True),
        'duree_reelle_minutes': serializers.IntegerField(required=False, allow_null=True),
        'projet_id': serializers.IntegerField(required=False, allow_null=True),
        'section_id': serializers.IntegerField(required=False, allow_null=True),
        'jalon': serializers.BooleanField(required=False),
        'bloquee_par_id': serializers.IntegerField(required=False, allow_null=True),
        'confidentiel': serializers.BooleanField(required=False),
        'etiquettes': serializers.ListField(required=False, child=serializers.IntegerField()),
        'recurrence': serializers.JSONField(required=False, allow_null=True),
        'lien': serializers.JSONField(required=False, allow_null=True),
        'lock_version': serializers.IntegerField(),
    }), responses=reponses(TacheEcriteSerializer, erreurs=(400, 404), conflit=CONFLIT_TACHE))
    def patch(self, request, id):
        raise PasEncore()

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        raise PasEncore()


class TachePlanifierVue(APIView):
    """POST taches/{id}/planifier/ — seul chemin du jour, de l'heure et du moment."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsPlanifier', {
        'jour_prevu': serializers.DateField(required=False, allow_null=True),
        'moment': serializers.CharField(required=False, allow_blank=True),
        'heure_debut': serializers.CharField(required=False, allow_null=True),
        'quelque_jour': serializers.BooleanField(required=False),
        'lock_version': serializers.IntegerField(),
        'proprietaire_attendu': serializers.IntegerField(required=False),
    }), responses=reponses(TacheEcriteSerializer, erreurs=(400, 404), conflit=CONFLIT_TACHE))
    def post(self, request, id):
        raise PasEncore()


class TacheTerminerVue(APIView):
    """POST taches/{id}/terminer/ — cocher."""

    permission_classes = PERMISSIONS

    @extend_schema(request=PROPRIETAIRE_ATTENDU, responses=ECRITE_AVEC_COMPTE)
    def post(self, request, id):
        raise PasEncore()


class TacheRouvrirVue(APIView):
    """POST taches/{id}/rouvrir/ — décocher."""

    permission_classes = PERMISSIONS

    @extend_schema(request=PROPRIETAIRE_ATTENDU, responses=ECRITE_AVEC_COMPTE)
    def post(self, request, id):
        raise PasEncore()


class TacheTrancherVue(APIView):
    """POST taches/{id}/trancher/ — aujourdhui, garder, jour, un_jour, abandonner."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsTrancher', {
        'choix': serializers.CharField(),
        'jour': serializers.DateField(required=False, allow_null=True),
    }), responses=ECRITE)
    def post(self, request, id):
        raise PasEncore()


class TacheSauterVue(APIView):
    """POST taches/{id}/sauter/ — sauter une occurrence."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=ECRITE)
    def post(self, request, id):
        raise PasEncore()


class TacheAttendreVue(APIView):
    """POST taches/{id}/attendre/ — « En attente de… »."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('TacheAttendre', {'en_attente_de': 'Lydec'}, requis=('en_attente_de',)),
                   responses=ECRITE)
    def post(self, request, id):
        raise PasEncore()


class TacheRecuVue(APIView):
    """POST taches/{id}/recu/ — reçu."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=ECRITE)
    def post(self, request, id):
        raise PasEncore()


class TacheReordonnerVue(APIView):
    """POST taches/{id}/reordonner/ — `{"liste","avant_id","apres_id"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=REORDONNER, responses=reponses(None, statut=204, erreurs=(400, 404)))
    def post(self, request, id):
        raise PasEncore()


class TacheRestaurerVue(APIView):
    """POST taches/{id}/restaurer/ — restaurer une tâche supprimée."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=ECRITE)
    def post(self, request, id):
        raise PasEncore()


class TacheRappelsVue(APIView):
    """POST taches/{id}/rappels/ — poser un rappel."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsRappel', {
        'jour': serializers.DateField(required=False),
        'heure': serializers.CharField(required=False),
        'ancre': serializers.CharField(required=False, allow_blank=True),
        'decalage_jours': serializers.IntegerField(required=False),
    }), responses=ECRITE)
    def post(self, request, id):
        raise PasEncore()


class TacheChangementApercuVue(APIView):
    """POST taches/{id}/changement/apercu/ — écho d'un renommage, abandon ou suppression."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('TacheChangementApercu', {'geste': 'renommer', 'titre': 'Devis Settat — relance'},
                                 requis=('geste',)),
                   responses=reponses(forme_echantillon('tache_changement'), erreurs=(400, 404)))
    def post(self, request, id):
        raise PasEncore()


class LotVue(IdempotentCreateMixin, APIView):
    """POST taches/lot/ — une action sur une sélection (≤ 200)."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsLot', {
        'ids': serializers.ListField(child=serializers.IntegerField()),
        'action': serializers.CharField(),
        'valeurs': serializers.DictField(required=False),
    }), responses=reponses(forme_echantillon('lot'), erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class RappelVue(APIView):
    """DELETE rappels/{id}/ — retirer un rappel."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        raise PasEncore()


class RappelRepeterVue(APIView):
    """POST rappels/{id}/repeter/ — « Encore 10 min · 1 h · Demain 9 h »."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsRepeter', {
        'dans_minutes': serializers.IntegerField(required=False),
        'jour': serializers.DateField(required=False),
        'heure': serializers.CharField(required=False),
    }), responses=reponses(forme_echantillon('rappel_repeter'), erreurs=(400, 404)))
    def post(self, request, id):
        raise PasEncore()


class RecurrenceVue(APIView):
    """PATCH recurrences/{id}/ — modifier ou arrêter (`actif:false`) une récurrence."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsRecurrence', {
        'frequence': serializers.CharField(required=False),
        'intervalle': serializers.IntegerField(required=False),
        'jours_semaine': serializers.CharField(required=False),
        'jour_du_mois': serializers.IntegerField(required=False, allow_null=True),
        'rang_dans_mois': serializers.IntegerField(required=False, allow_null=True),
        'mode': serializers.CharField(required=False),
        'date_debut': serializers.DateField(required=False),
        'date_fin': serializers.DateField(required=False, allow_null=True),
        'actif': serializers.BooleanField(required=False),
        'appliquer_a_l_ouverte': serializers.BooleanField(required=False),
    }), responses=ECRITE)
    def patch(self, request, id):
        raise PasEncore()


class ChecklistVue(APIView):
    """POST checklist/ — ajouter un point `{"tache_id","libelle"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('Checklist', {'tache_id': 20, 'libelle': 'Prix'}, requis=('tache_id', 'libelle')),
                   responses=reponses(TacheEcriteSerializer, statut=201, erreurs=(400, 404)))
    def post(self, request):
        raise PasEncore()


class ElementChecklistVue(APIView):
    """PATCH · DELETE checklist/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('ChecklistElement', {'libelle': 'Prix TTC', 'fait': True}), responses=ECRITE)
    def patch(self, request, id):
        raise PasEncore()

    @extend_schema(request=None, responses=reponses(TacheEcriteSerializer, erreurs=(404,)))
    def delete(self, request, id):
        raise PasEncore()


class ElementChecklistReordonnerVue(APIView):
    """POST checklist/{id}/reordonner/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=REORDONNER, responses=reponses(None, statut=204, erreurs=(400, 404)))
    def post(self, request, id):
        raise PasEncore()


class EtiquettesVue(APIView):
    """GET etiquettes/ (liste paginée) · POST etiquettes/ `{"nom","couleur"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=PAGINATION, responses=reponses(forme_echantillon('etiquettes')))
    def get(self, request):
        raise PasEncore()

    @extend_schema(request=corps('Etiquette', {'nom': 'magasin', 'couleur': 'ciel'}, requis=('nom',)),
                   responses=reponses(EtiquetteCourteSerializer, statut=201, erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class EtiquetteVue(APIView):
    """PATCH · DELETE etiquettes/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('EtiquettePatch', {'nom': 'magasin', 'couleur': 'ciel'}),
                   responses=reponses(EtiquetteCourteSerializer, erreurs=(400, 404)))
    def patch(self, request, id):
        raise PasEncore()

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        raise PasEncore()


class VuesVue(APIView):
    """GET vues/ (≤ 30, non paginé) · POST vues/ `{"nom","filtres","rang"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('vues')))
    def get(self, request):
        raise PasEncore()

    @extend_schema(request=inline_serializer('TachesCorpsVue', {
        'nom': serializers.CharField(max_length=60),
        'filtres': serializers.DictField(required=False),
        'rang': serializers.IntegerField(required=False),
    }), responses=reponses(VUE_ENREGISTREE, statut=201, erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class VueEnregistreeVue(APIView):
    """PATCH · DELETE vues/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsVuePatch', {
        'nom': serializers.CharField(required=False, max_length=60),
        'filtres': serializers.DictField(required=False),
        'rang': serializers.IntegerField(required=False),
    }), responses=reponses(VUE_ENREGISTREE, erreurs=(400, 404)))
    def patch(self, request, id):
        raise PasEncore()

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        raise PasEncore()


class SupprimeesVue(APIView):
    """GET supprimees/ — Supprimées récemment (un projet = une ligne)."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('supprimees')))
    def get(self, request):
        raise PasEncore()


class GestesVue(APIView):
    """GET gestes/ — derniers gestes (7 jours)."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('gestes')))
    def get(self, request):
        raise PasEncore()


class GesteAnnulerVue(APIView):
    """POST gestes/{id}/annuler/ — Annuler (200 partiel)."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(forme_echantillon('geste_annuler'), erreurs=(404,)))
    def post(self, request, id):
        raise PasEncore()
