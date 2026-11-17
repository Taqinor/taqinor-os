"""Tâches, À trier, fiche et ce qui s'y rattache (reference/api.md §3.1-§3.2, §4) : recherche, listes,
fiche, actions d'une tâche, lot, rappels, récurrences, check-list, étiquettes, vues enregistrées,
supprimées récemment, derniers gestes.

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction. Schémas :
l'échantillon de la route quand il existe (`forme_echantillon`), sinon une forme partagée
(`serializers/formes.py`) ; `GESTE`, `CONFLIT_TACHE` et `REORDONNER` sont déclarés ici une fois.
"""
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.taches.choix import Source
from apps.taches.confidentialite import ASSISTANT, ECRAN
from apps.taches.selectors.base import taches_de
from apps.taches.serializers.formes import (
    ItemSerializer, TacheEcriteSerializer, TacheSerializer, charger_items, contexte,
)
from apps.taches.serializers.saisie import (
    AttendreEntreeSerializer, PlanifierEntreeSerializer, ProprietaireEntreeSerializer, TacheCreationSerializer,
    TrancherEntreeSerializer, lire_corps, reponse_ecrite, taches_chargees, valider_patch,
    verifier_proprietaire,
)
from apps.taches.services.creation import creer_taches
from apps.taches.services.planification import planifier
from apps.taches.services.taches import (
    attendre_tache, avertissements_du_jour, liste_taches, modifier_tache, rappel_a_la_creation,
    recevoir_tache, restaurer_tache, reverifier_lien, rouvrir_tache, sauter_occurrence, supprimer_tache,
    terminer_tache, trancher_tache,
)
from apps.taches.views.base import (
    ERREUR_CODE, PAGINATION, PERMISSIONS, PasEncore, corps, est_assistant, forme_echantillon, page_de,
    parametre, reponses,
)
from apps.taches.views.saisie import CHAMPS_LIGNE
from core.idempotency import IdempotentCreateMixin
from core.openapi_operations import mots_operation
from core.pagination import StandardPagination
from core.verrou_optimiste import ConflitVersion

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
#: Toute écriture rend son `geste_id` (api.md §0), une étiquette ou une vue enregistrée comprise.
VUE_ENREGISTREE = inline_serializer('TachesVueEnregistree', {
    'id': serializers.IntegerField(), 'nom': serializers.CharField(), 'rang': serializers.IntegerField(),
    'filtres': serializers.DictField(), 'geste_id': serializers.IntegerField(allow_null=True),
})
ETIQUETTE_ECRITE = inline_serializer('TachesEtiquetteEcrite', {
    'id': serializers.IntegerField(), 'nom': serializers.CharField(), 'couleur': serializers.CharField(),
    'geste_id': serializers.IntegerField(allow_null=True),
})


def _reponse(request, resultat):
    """La TACHE_ECRITE d'une action (`tache`, `suivante`, `geste_id`, avertissements)."""
    return Response(reponse_ecrite(
        request.user, resultat.tache, assistant=est_assistant(request), geste=resultat.geste,
        suivante=getattr(resultat, 'suivante', None), avertissements=resultat.avertissements))


def _conflit_complet(request, exc, pk):
    """409 `conflit_version` : `actuel` devient la forme TACHE COMPLÈTE (le bandeau de conflit la lit)."""
    exc.detail['actuel'] = TacheSerializer(
        taches_chargees(request.user, [pk])[0], context=contexte(assistant=est_assistant(request))).data
    return exc


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
        assistant = est_assistant(request)
        paginateur = StandardPagination()
        page = paginateur.paginate_queryset(
            charger_items(liste_taches(request.user, request.query_params, assistant=assistant)),
            request, view=self)
        donnees = ItemSerializer(page, many=True, context=contexte(assistant=assistant)).data
        return paginateur.get_paginated_response(donnees)

    @extend_schema(request=inline_serializer('TachesCorpsTache', {
        **CHAMPS_LIGNE,
        'parent_id': serializers.IntegerField(required=False, allow_null=True),
        'proprietaire_attendu': serializers.IntegerField(required=False),
    }), responses=reponses(TacheEcriteSerializer, statut=201, erreurs=(400,), conflit=ERREUR_CODE))
    def post(self, request):
        entree = TacheCreationSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        donnees = dict(entree.validated_data)
        verifier_proprietaire(request.user, donnees.pop('proprietaire_attendu', None))
        parent_id = donnees.pop('parent_id', None)
        return self._avec_idempotence(
            request, lambda: self._creer(request, donnees, parent_id), suffixe=f'u{request.user.pk}')

    def _creer(self, request, ligne, parent_id):
        """Une LIGNE → 201 `tache_ecrite.json` ; un rejeu du même `client_id` rend la tâche déjà créée (200)."""
        user, assistant = request.user, est_assistant(request)
        with transaction.atomic():
            resultat = creer_taches(
                user, [ligne], source=Source.ASSISTANT if assistant else Source.MANUEL,
                porte='assistant' if assistant else 'ecran', parent=parent_id)
        if not resultat.creees:
            existante = taches_de(user).filter(client_id=ligne.get('client_id')).first()
            if existante is None:
                raise Http404('Introuvable.')
            return Response(reponse_ecrite(user, existante, assistant=assistant))
        tache = resultat.creees[0]
        rappel, question = rappel_a_la_creation(user, tache)
        donnees = reponse_ecrite(
            user, tache, assistant=assistant, geste=resultat.geste,
            projet_cree=resultat.projets_crees[0] if resultat.projets_crees else None,
            rappel=rappel, question_titres=question,
            avertissements=avertissements_du_jour(user, tache, timezone.localdate()))
        return Response(donnees, status=201)


class TacheVue(APIView):
    """GET (TACHE, lien revérifié) · PATCH (verrou 409) · DELETE taches/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(TacheSerializer, erreurs=(404,)))
    def get(self, request, id):
        trouvees = taches_chargees(request.user, [id])
        if not trouvees:
            raise Http404('Introuvable.')
        tache = reverifier_lien(request.user, trouvees[0])
        return Response(TacheSerializer(tache, context=contexte(assistant=est_assistant(request))).data)

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
        donnees = valider_patch(request.data)
        assistant = est_assistant(request)
        version = donnees.pop('lock_version')
        try:
            resultat = modifier_tache(request.user, id, donnees, version=version,
                                      usage=ASSISTANT if assistant else ECRAN)
        except ConflitVersion as exc:
            raise _conflit_complet(request, exc, id)
        return _reponse(request, resultat)

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        geste = supprimer_tache(request.user, id)
        return Response({'geste_id': geste.pk})


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
        donnees = lire_corps(PlanifierEntreeSerializer, request.data)
        verifier_proprietaire(request.user, donnees.get('proprietaire_attendu'))
        try:
            resultat = planifier(
                id, acteur=request.user, jour_prevu=donnees.get('jour_prevu'), moment=donnees.get('moment', ''),
                heure_debut=donnees.get('heure_debut'), quelque_jour=donnees.get('quelque_jour', False),
                version=donnees['lock_version'])
        except ConflitVersion as exc:
            raise _conflit_complet(request, exc, id)
        return _reponse(request, resultat)


class TacheTerminerVue(APIView):
    """POST taches/{id}/terminer/ — cocher."""

    permission_classes = PERMISSIONS

    @extend_schema(request=PROPRIETAIRE_ATTENDU, responses=ECRITE_AVEC_COMPTE)
    def post(self, request, id):
        donnees = lire_corps(ProprietaireEntreeSerializer, request.data)
        verifier_proprietaire(request.user, donnees.get('proprietaire_attendu'))
        return _reponse(request, terminer_tache(request.user, id))


class TacheRouvrirVue(APIView):
    """POST taches/{id}/rouvrir/ — décocher."""

    permission_classes = PERMISSIONS

    @extend_schema(request=PROPRIETAIRE_ATTENDU, responses=ECRITE_AVEC_COMPTE)
    def post(self, request, id):
        donnees = lire_corps(ProprietaireEntreeSerializer, request.data)
        verifier_proprietaire(request.user, donnees.get('proprietaire_attendu'))
        return _reponse(request, rouvrir_tache(request.user, id))


class TacheTrancherVue(APIView):
    """POST taches/{id}/trancher/ — aujourdhui, garder, jour, un_jour, abandonner."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsTrancher', {
        'choix': serializers.CharField(),
        'jour': serializers.DateField(required=False, allow_null=True),
    }), responses=ECRITE)
    def post(self, request, id):
        donnees = lire_corps(TrancherEntreeSerializer, request.data)
        return _reponse(request, trancher_tache(request.user, id, donnees['choix'], donnees.get('jour')))


class TacheSauterVue(APIView):
    """POST taches/{id}/sauter/ — sauter une occurrence."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=ECRITE)
    def post(self, request, id):
        return _reponse(request, sauter_occurrence(request.user, id))


class TacheAttendreVue(APIView):
    """POST taches/{id}/attendre/ — « En attente de… »."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('TacheAttendre', {'en_attente_de': 'Lydec'}, requis=('en_attente_de',)),
                   responses=ECRITE)
    def post(self, request, id):
        donnees = lire_corps(AttendreEntreeSerializer, request.data)
        return _reponse(request, attendre_tache(request.user, id, donnees['en_attente_de']))


class TacheRecuVue(APIView):
    """POST taches/{id}/recu/ — reçu."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=ECRITE)
    def post(self, request, id):
        return _reponse(request, recevoir_tache(request.user, id))


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
        return _reponse(request, restaurer_tache(request.user, id))


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
                   responses=reponses(ETIQUETTE_ECRITE, statut=201, erreurs=(400,)))
    def post(self, request):
        raise PasEncore()


class EtiquetteVue(APIView):
    """PATCH · DELETE etiquettes/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('EtiquettePatch', {'nom': 'magasin', 'couleur': 'ciel'}),
                   responses=reponses(ETIQUETTE_ECRITE, erreurs=(400, 404)))
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
