"""Tâches, À trier, fiche et ce qui s'y rattache (reference/api.md §3.1-§3.2, §4) : recherche, listes,
fiche, actions d'une tâche, lot, rappels, récurrences, check-list, étiquettes, vues enregistrées,
supprimées récemment, derniers gestes.

Routes toutes construites (TCH156 : étiquettes et vues enregistrées en dernier). Schémas :
l'échantillon de la route quand il existe (`forme_echantillon`), sinon une forme partagée
(`serializers/formes.py`) ; `GESTE`, `CONFLIT_TACHE` et `REORDONNER` sont déclarés ici une fois.
"""
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.taches.choix import Source
from apps.taches.confidentialite import ASSISTANT, ECRAN
from apps.taches.selectors.base import etiquettes_servies, taches_de
from apps.taches.selectors.journee import progression_courante
from apps.taches.serializers.formes import (
    ItemSerializer, RappelEcritSerializer, TacheEcriteSerializer, TacheSerializer, charger_items, contexte,
)
from apps.taches.serializers.saisie import (
    CHAMPS_CREATION, AttendreEntreeSerializer, ChangementEntreeSerializer, ChecklistEntreeSerializer,
    ElementChecklistEntreeSerializer, EtiquetteEntreeSerializer, EtiquettePatchSerializer, forme_etiquette,
    forme_vue, lire_corps, LotEntreeSerializer, PlanifierEntreeSerializer,
    ProprietaireEntreeSerializer, RappelEntreeSerializer, RecurrenceEntreeSerializer,
    ReordonnerElementEntreeSerializer, ReordonnerEntreeSerializer, RepeterEntreeSerializer, reponse_ecrite,
    reponse_etiquette, reponse_gestes, reponse_recherche, reponse_supprimees, reponse_vue, TacheCreationSerializer,
    TachePatchSerializer, taches_chargees, TrancherEntreeSerializer, valider_patch, verifier_proprietaire,
    VueEntreeSerializer, VuePatchSerializer,
)
from apps.taches.services.creation import creer_taches
from apps.taches.services.etiquettes import (
    creer_etiquette, creer_vue, liste_vues, modifier_etiquette, modifier_vue, supprimer_etiquette, supprimer_vue,
)
from apps.taches.services.gestes import annuler_geste, titres_des_gestes
from apps.taches.services.planification import planifier
from apps.taches.services.rappels import poser_rappel, repeter_rappel, retirer_rappel
from apps.taches.services.taches import (
    ajouter_element, apercu_changement, attendre_tache, avertissement_hors_fenetre, avertissements_du_jour,
    LIMITE_RECHERCHE_MAX, derniers_gestes, entete_de_liste, gestes_confidentiels, liste_taches, lot_taches,
    modifier_element,
    modifier_regle, modifier_tache,
    rappel_a_la_creation, recevoir_tache, rechercher, reordonner_element, reordonner_tache, restaurer_tache,
    retirer_element, reverifier_lien, rouvrir_tache, sauter_occurrence, supprimees_recentes, supprimer_tache,
    tache_du_compte, terminer_tache, trancher_tache,
)
from apps.taches.views.base import (
    ERREUR_CODE, PAGINATION, PARSEURS, PERMISSIONS, carte_assistant, est_assistant, forme_echantillon,
    parametre, reponses,
)
from core.champs_stricts import MOTIF_NON_BLANC_SANS_NUL
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
    parametre('periode', OpenApiTypes.STR, 'aujourdhui, semaine, retard, faites_semaine (depuis lundi).'),
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
    parser_classes = PARSEURS

    @extend_schema(parameters=[OpenApiParameter('q', {'type': 'string', 'minLength': 1,
                                                      'pattern': MOTIF_NON_BLANC_SANS_NUL},
                                                OpenApiParameter.QUERY, required=True, description='Mots cherchés.'),
                               OpenApiParameter('limite', {'type': 'integer', 'minimum': 1,
                                                           'maximum': LIMITE_RECHERCHE_MAX},
                                                OpenApiParameter.QUERY, required=False)],
                   responses=reponses(forme_echantillon('recherche'), erreurs=(400,)))
    def get(self, request):
        assistant = est_assistant(request)
        projets, taches = rechercher(request.user, request.query_params, assistant=assistant)
        return Response(reponse_recherche(projets, taches, assistant=assistant))


#: La page de `GET taches/` (StandardPagination) ; `total` et `activites_closes` n'y sont QUE pour
#: `periode=faites_semaine` (R3-003, `faites_semaine.json`) : déclarés, non requis.
PAGE_ITEMS = inline_serializer('TachesPageItems', {
    'count': serializers.IntegerField(),
    'next': serializers.CharField(allow_null=True),
    'previous': serializers.CharField(allow_null=True),
    'results': serializers.ListField(child=ItemSerializer()),
    'total': serializers.IntegerField(required=False),
    'activites_closes': serializers.ListField(required=False, child=inline_serializer('TachesActiviteClose', {
        'jour': serializers.DateField(), 'titre': serializers.CharField(allow_blank=True)})),
})


class TachesVue(IdempotentCreateMixin, APIView):
    """GET taches/ (listes paginées) · POST taches/ (une LIGNE)."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS
    schema = mots_operation(get='list')  # sinon même operationId que GET taches/{id}/

    @extend_schema(parameters=FILTRES_LISTE, responses=reponses(PAGE_ITEMS, erreurs=(400,)))
    def get(self, request):
        assistant = est_assistant(request)
        paginateur = StandardPagination()
        page = paginateur.paginate_queryset(
            charger_items(liste_taches(request.user, request.query_params, assistant=assistant)),
            request, view=self)
        donnees = ItemSerializer(page, many=True, context=contexte(assistant=assistant)).data
        reponse = paginateur.get_paginated_response(donnees)
        reponse.data.update(entete_de_liste(request.user, request.query_params))
        return reponse

    @extend_schema(request=inline_serializer('TachesCorpsTache', dict(CHAMPS_CREATION)),
                   # 200 : rejeu d'un `client_id` déjà créé — la tâche existante, même forme (`_creer`).
                   responses={**reponses(TacheEcriteSerializer, statut=201, erreurs=(400, 404), conflit=ERREUR_CODE),
                              200: TacheEcriteSerializer})
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
        # Une carte du Copilote validée au doigt : source `assistant`, porte de l'écran (ERR 5).
        source = Source.ASSISTANT if assistant or carte_assistant(request) else Source.MANUEL
        with transaction.atomic():
            resultat = creer_taches(
                user, [ligne], source=source,
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
    parser_classes = PARSEURS

    @extend_schema(responses=reponses(TacheSerializer, erreurs=(404,)))
    def get(self, request, id):
        trouvees = taches_chargees(request.user, [id])
        if not trouvees:
            raise Http404('Introuvable.')
        tache = reverifier_lien(request.user, trouvees[0])
        return Response(TacheSerializer(tache, context=contexte(assistant=est_assistant(request))).data)

    @extend_schema(request=TachePatchSerializer,
                   responses=reponses(TacheEcriteSerializer, erreurs=(400, 404), conflit=CONFLIT_TACHE))
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
    parser_classes = PARSEURS

    @extend_schema(request=PlanifierEntreeSerializer,
                   responses=reponses(TacheEcriteSerializer, erreurs=(400, 404), conflit=CONFLIT_TACHE))
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
    parser_classes = PARSEURS

    @extend_schema(request=ProprietaireEntreeSerializer, responses=ECRITE_AVEC_COMPTE)
    def post(self, request, id):
        donnees = lire_corps(ProprietaireEntreeSerializer, request.data)
        verifier_proprietaire(request.user, donnees.get('proprietaire_attendu'))
        return _reponse(request, terminer_tache(request.user, id))


class TacheRouvrirVue(APIView):
    """POST taches/{id}/rouvrir/ — décocher."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=ProprietaireEntreeSerializer, responses=ECRITE_AVEC_COMPTE)
    def post(self, request, id):
        donnees = lire_corps(ProprietaireEntreeSerializer, request.data)
        verifier_proprietaire(request.user, donnees.get('proprietaire_attendu'))
        return _reponse(request, rouvrir_tache(request.user, id))


class TacheTrancherVue(APIView):
    """POST taches/{id}/trancher/ — aujourdhui, garder, jour, un_jour, abandonner."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=TrancherEntreeSerializer, responses=ECRITE)
    def post(self, request, id):
        donnees = lire_corps(TrancherEntreeSerializer, request.data)
        return _reponse(request, trancher_tache(request.user, id, donnees['choix'], donnees.get('jour')))


class TacheSauterVue(APIView):
    """POST taches/{id}/sauter/ — sauter une occurrence."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=None, responses=ECRITE)
    def post(self, request, id):
        return _reponse(request, sauter_occurrence(request.user, id))


class TacheAttendreVue(APIView):
    """POST taches/{id}/attendre/ — « En attente de… »."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=AttendreEntreeSerializer,
                   responses=ECRITE)
    def post(self, request, id):
        donnees = lire_corps(AttendreEntreeSerializer, request.data)
        return _reponse(request, attendre_tache(request.user, id, donnees['en_attente_de']))


class TacheRecuVue(APIView):
    """POST taches/{id}/recu/ — reçu."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=None, responses=ECRITE)
    def post(self, request, id):
        return _reponse(request, recevoir_tache(request.user, id))


class TacheReordonnerVue(APIView):
    """POST taches/{id}/reordonner/ — `{"liste","avant_id","apres_id"}`."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=ReordonnerEntreeSerializer,
                   responses=reponses(None, statut=204, erreurs=(400, 404, 409)))
    def post(self, request, id):
        donnees = lire_corps(ReordonnerEntreeSerializer, request.data)
        reordonner_tache(request.user, id, donnees['liste'], donnees.get('avant_id'), donnees.get('apres_id'))
        return Response(status=204)


class TacheRestaurerVue(APIView):
    """POST taches/{id}/restaurer/ — restaurer une tâche supprimée."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=None, responses=ECRITE)
    def post(self, request, id):
        return _reponse(request, restaurer_tache(request.user, id))


class TacheRappelsVue(APIView):
    """POST taches/{id}/rappels/ — poser un rappel."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=RappelEntreeSerializer, responses=ECRITE)
    def post(self, request, id):
        donnees = lire_corps(RappelEntreeSerializer, request.data)
        resultat = poser_rappel(
            id, acteur=request.user, heure=donnees['heure'], jour=donnees.get('jour'),
            ancre=donnees.get('ancre', ''), decalage_jours=donnees.get('decalage_jours', 0))
        resultat.rappel.hors_fenetre = resultat.hors_fenetre
        tache = tache_du_compte(request.user, id)
        return Response(reponse_ecrite(
            request.user, tache, assistant=est_assistant(request), geste=resultat.geste, rappel=resultat.rappel,
            question_titres=resultat.question_titres, avertissements=avertissement_hors_fenetre(resultat)))


class TacheChangementApercuVue(APIView):
    """POST taches/{id}/changement/apercu/ — écho d'un renommage, abandon ou suppression."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=ChangementEntreeSerializer,
                   responses=reponses(forme_echantillon('tache_changement'), erreurs=(400, 404)))
    def post(self, request, id):
        donnees = lire_corps(ChangementEntreeSerializer, request.data)
        assistant = est_assistant(request)
        tache, proposition = apercu_changement(request.user, id, donnees['geste'], donnees.get('titre'),
                                               usage=ASSISTANT if assistant else ECRAN)
        item = charger_items(taches_de(request.user).filter(pk=tache.pk)).get()
        return Response({'tache': ItemSerializer(item, context=contexte(assistant=assistant)).data,
                         'proposition': proposition})


class LotVue(IdempotentCreateMixin, APIView):
    """POST taches/lot/ — une action sur une sélection (≤ 200)."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=LotEntreeSerializer, responses=reponses(forme_echantillon('lot'), erreurs=(400, 404)))
    def post(self, request):
        donnees = lire_corps(LotEntreeSerializer, request.data)
        return self._avec_idempotence(
            request, lambda: Response(lot_taches(request.user, donnees['ids'], donnees['action'],
                                                 donnees.get('valeurs'))),
            suffixe=f'u{request.user.pk}')


class RappelVue(APIView):
    """DELETE rappels/{id}/ — retirer un rappel."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        geste = retirer_rappel(request.user, id)
        return Response({'geste_id': geste.pk if geste is not None else None})


class RappelRepeterVue(APIView):
    """POST rappels/{id}/repeter/ — « Encore 10 min · 1 h · Demain 9 h »."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=RepeterEntreeSerializer,
                   responses=reponses(forme_echantillon('rappel_repeter'), erreurs=(400, 404)))
    def post(self, request, id):
        donnees = lire_corps(RepeterEntreeSerializer, request.data)
        resultat = repeter_rappel(request.user, id, dans_minutes=donnees.get('dans_minutes'),
                                  jour=donnees.get('jour'), heure=donnees.get('heure'))
        resultat.rappel.hors_fenetre = resultat.hors_fenetre
        return Response({'rappel': RappelEcritSerializer(resultat.rappel).data,
                         'geste_id': resultat.geste.pk if resultat.geste is not None else None})


class RecurrenceVue(APIView):
    """PATCH recurrences/{id}/ — modifier ou arrêter (`actif:false`) une récurrence."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=RecurrenceEntreeSerializer, responses=ECRITE)
    def patch(self, request, id):
        donnees = lire_corps(RecurrenceEntreeSerializer, request.data)
        return _reponse(request, modifier_regle(request.user, id, donnees))


class ChecklistVue(APIView):
    """POST checklist/ — ajouter un point `{"tache_id","libelle"}`."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=ChecklistEntreeSerializer,
                   responses=reponses(TacheEcriteSerializer, statut=201, erreurs=(400, 404)))
    def post(self, request):
        donnees = lire_corps(ChecklistEntreeSerializer, request.data)
        resultat = ajouter_element(request.user, donnees['tache_id'], donnees['libelle'])
        reponse = _reponse(request, resultat)
        reponse.status_code = 201
        return reponse


class ElementChecklistVue(APIView):
    """PATCH · DELETE checklist/{id}/."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=ElementChecklistEntreeSerializer, responses=ECRITE)
    def patch(self, request, id):
        donnees = lire_corps(ElementChecklistEntreeSerializer, request.data)
        return _reponse(request, modifier_element(request.user, id, donnees))

    @extend_schema(request=None, responses=reponses(TacheEcriteSerializer, erreurs=(404,)))
    def delete(self, request, id):
        return _reponse(request, retirer_element(request.user, id))


class ElementChecklistReordonnerVue(APIView):
    """POST checklist/{id}/reordonner/."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=ReordonnerElementEntreeSerializer,
                   responses=reponses(None, statut=204, erreurs=(400, 404)))
    def post(self, request, id):
        donnees = lire_corps(ReordonnerElementEntreeSerializer, request.data)
        reordonner_element(request.user, id, donnees.get('avant_id'), donnees.get('apres_id'))
        return Response(status=204)


class EtiquettesVue(APIView):
    """GET etiquettes/ (liste paginée) · POST etiquettes/ `{"nom","couleur"}`."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(parameters=PAGINATION, responses=reponses(forme_echantillon('etiquettes')))
    def get(self, request):
        paginateur = StandardPagination()
        etiquettes = etiquettes_servies(request.user, assistant=est_assistant(request))
        page = paginateur.paginate_queryset(etiquettes.order_by('nom_cle', 'id'), request, view=self)
        return paginateur.get_paginated_response([forme_etiquette(e) for e in page])

    @extend_schema(request=EtiquetteEntreeSerializer,
                   responses=reponses(ETIQUETTE_ECRITE, statut=201, erreurs=(400, 409)))
    def post(self, request):
        donnees = lire_corps(EtiquetteEntreeSerializer, request.data)
        etiquette, geste = creer_etiquette(request.user, nom=donnees['nom'], couleur=donnees.get('couleur'))
        return Response(reponse_etiquette(etiquette, geste), status=201)


class EtiquetteVue(APIView):
    """PATCH · DELETE etiquettes/{id}/."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=EtiquettePatchSerializer,
                   responses=reponses(ETIQUETTE_ECRITE, erreurs=(400, 404, 409)))
    def patch(self, request, id):
        donnees = lire_corps(EtiquettePatchSerializer, request.data)
        etiquette, geste = modifier_etiquette(request.user, id, donnees)
        return Response(reponse_etiquette(etiquette, geste))

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        return Response({'geste_id': supprimer_etiquette(request.user, id).pk})


class VuesVue(APIView):
    """GET vues/ (≤ 30, non paginé) · POST vues/ `{"nom","filtres","rang"}`."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(responses=reponses(forme_echantillon('vues')))
    def get(self, request):
        return Response({'results': [forme_vue(v) for v in liste_vues(request.user)]})

    @extend_schema(request=VueEntreeSerializer,
                   responses=reponses(VUE_ENREGISTREE, statut=201, erreurs=(400, 404, 409)))
    def post(self, request):
        donnees = lire_corps(VueEntreeSerializer, request.data)
        vue, geste = creer_vue(request.user, nom=donnees['nom'], filtres=donnees.get('filtres'),
                               rang=donnees.get('rang'))
        return Response(reponse_vue(vue, geste), status=201)


class VueEnregistreeVue(APIView):
    """PATCH · DELETE vues/{id}/."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=VuePatchSerializer, responses=reponses(VUE_ENREGISTREE, erreurs=(400, 404, 409)))
    def patch(self, request, id):
        donnees = lire_corps(VuePatchSerializer, request.data)
        vue, geste = modifier_vue(request.user, id, donnees)
        return Response(reponse_vue(vue, geste))

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        return Response({'geste_id': supprimer_vue(request.user, id).pk})


class SupprimeesVue(APIView):
    """GET supprimees/ — Supprimées récemment (un projet = une ligne)."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(responses=reponses(forme_echantillon('supprimees')))
    def get(self, request):
        projets, compteurs, taches = supprimees_recentes(request.user)
        return Response(reponse_supprimees(projets, compteurs, taches, assistant=est_assistant(request)))


class GestesVue(APIView):
    """GET gestes/ — derniers gestes (7 jours)."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(responses=reponses(forme_echantillon('gestes')))
    def get(self, request):
        gestes = derniers_gestes(request.user)
        assistant = est_assistant(request)
        masques = gestes_confidentiels(request.user, gestes) if assistant else frozenset()
        titres = {} if assistant else titres_des_gestes(request.user, gestes)  # le Copilote ne reçoit aucun titre
        return Response(reponse_gestes(gestes, masques, titres))


class GesteAnnulerVue(APIView):
    """POST gestes/{id}/annuler/ — Annuler (200 partiel)."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=None, responses=reponses(forme_echantillon('geste_annuler'), erreurs=(404,)))
    def post(self, request, id):
        bilan = annuler_geste(request.user, id)
        # La progression du jour (même calcul que TACHE_ECRITE) : l'écran recale sa ligne après « Annuler ».
        return Response({**bilan, 'progression': progression_courante(request.user, timezone.localdate())})
