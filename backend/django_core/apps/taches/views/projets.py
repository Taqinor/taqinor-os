"""Projets, étapes, modèles et revue (reference/api.md §3.3, §4).

Toutes les routes sont construites (dupliquer, modèles : TCH64). Schémas :
l'échantillon de la route quand il existe (`forme_echantillon`), sinon la forme PROJET partagée ;
`GESTE` et `REORDONNER` viennent de `views/taches.py` (déclarés une fois).
"""
import datetime
import json

from django.http import Http404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.utils.encoders import JSONEncoder
from rest_framework.views import APIView

from apps.taches.confidentialite import est_confidentielle
from apps.taches.entrees import MESSAGE_DATE, jour_dans_bornes
from apps.taches.selectors import projets as lecture
from apps.taches.serializers import projets as formes_projets
from apps.taches.serializers.formes import ProjetSerializer
from apps.taches.services import projets as ecriture
from apps.taches.views.base import (
    ERREUR_CODE, PAGINATION, PERMISSIONS, corps, est_assistant, forme_echantillon, parametre, reponses,
)
from apps.taches.views.taches import GESTE, REORDONNER
from core.idempotency import IdempotentCreateMixin
from core.openapi_operations import mots_operation
from core.pagination import StandardPagination
from core.verrou_optimiste import ConflitVersion


def _json(donnees):
    """Des données JSON pures (dates en texte) : ce que l'idempotence mémorise et rejoue."""
    return json.loads(json.dumps(donnees, cls=JSONEncoder))


def _valider(classe, donnees, **options):
    """Le corps reçu, validé (400 par champ) ; seules les clés déclarées passent."""
    serialiseur = classe(data=donnees, **options)
    serialiseur.is_valid(raise_exception=True)
    return serialiseur.validated_data


def _etat(request):
    """`(état des projets, contexte des formes)` de la requête, calculés au jour courant."""
    assistant = est_assistant(request)
    etat = lecture.etat_projets(request.user, timezone.localdate(), usage='assistant' if assistant else 'ecran')
    return etat, formes_projets.contexte_de(etat, assistant=assistant)


def _projet_ou_404(request, pk):
    projet = lecture.projet_de(request.user, pk)
    if projet is None:
        raise Http404('Introuvable.')
    return projet


def _avec_conflit_projet(request, appel):
    """Joue `appel()` ; un 409 `conflit_version` porte l'état courant du projet (forme PROJET)."""
    try:
        return appel()
    except ConflitVersion as exc:
        projet = getattr(exc, 'projet', None)
        if projet is not None:
            projet.refresh_from_db()
            _, ctx = _etat(request)
            exc.detail['actuel'] = formes_projets.forme_projet(projet, ctx)
        raise


def _ecrit(request, resultat, statut=200):
    """La réponse `projet_ecrit` d'une écriture (état recalculé APRÈS elle)."""
    _, ctx = _etat(request)
    return Response(formes_projets.projet_ecrit(resultat, ctx), status=statut)


MESSAGE_PROJET_CONFIDENTIEL = "Ce projet est confidentiel : l'assistant ne le copie pas."


def _reponse_instance(request, instance):
    """Aperçu (`apercu:true`) : le plan daté, 200 ; sinon le projet créé, 201 (`projet_ecrit.json`)."""
    if instance.resultat is None:
        return Response(_json(formes_projets.modele_apercu(instance.plan)))
    reponse = _ecrit(request, instance.resultat, 201)
    reponse.data = _json(reponse.data)
    return reponse


def _forme_modele(request, modele):
    """`modele.json` du modèle, servi selon l'usage de la requête (notes tues à l'assistant, revue F4 #2)."""
    return formes_projets.ModeleSerializer(modele, context={'assistant': est_assistant(request)}).data


def _modele_ou_404(request, pk):
    """Le modèle `pk` servi au compte (`modeles_servis`) ; sous l'en-tête assistant, un modèle confidentiel répond
    comme un id inconnu (revue F4 #3 : la liste le tait, la fiche et les gestes aussi)."""
    modele = lecture.modele_de(request.user, pk, assistant=est_assistant(request))
    if modele is None:
        raise Http404('Introuvable.')
    return modele


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
        statut = request.query_params.get('statut') or None
        if statut not in (None, 'actif', 'en_pause', 'archive'):
            raise serializers.ValidationError({'statut': ['Valeur inconnue.']})
        etat, ctx = _etat(request)
        pagination = StandardPagination()
        page = pagination.paginate_queryset(lecture.projets_filtres(request.user, statut), request, view=self)
        reponse = pagination.get_paginated_response(ProjetSerializer(page, many=True, context=ctx).data)
        reponse.data['constat'] = etat.constat
        return reponse

    @extend_schema(request=corps('Projet', {'nom': 'Chantier X', 'priorite': 2, 'couleur': 'vert', 'icone': '',
                                            'objectif': '', 'domaine': ''}, requis=('nom',)),
                   responses=reponses(PROJET_ECRIT, statut=201, erreurs=(400,)))
    def post(self, request):
        donnees = _valider(formes_projets.ProjetCreationSerializer, request.data)

        def creer():
            resultat = ecriture.creer_projet(request.user, **donnees)
            reponse = _ecrit(request, resultat, 201)
            reponse.data = _json(reponse.data)
            return reponse
        return self._avec_idempotence(request, creer, suffixe=f'u{request.user.pk}')


class ProjetVue(APIView):
    """GET (PROJET) · PATCH (verrou 409) · DELETE (avec ses tâches) projets/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(ProjetSerializer, erreurs=(404,)))
    def get(self, request, id):
        projet = _projet_ou_404(request, id)
        _, ctx = _etat(request)
        return Response(formes_projets.forme_projet(projet, ctx))

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
        donnees = dict(_valider(formes_projets.ProjetModificationSerializer, request.data))
        version = donnees.pop('lock_version')
        projet = _avec_conflit_projet(
            request, lambda: ecriture.modifier_projet(request.user, id, donnees, version=version))
        _, ctx = _etat(request)
        return Response(formes_projets.forme_projet(projet, ctx))

    @extend_schema(request=None, responses=reponses(PROJET_ECRIT, erreurs=(404,)))
    def delete(self, request, id):
        _projet_ou_404(request, id)
        _, ctx = _etat(request)  # lu AVANT la suppression : compteurs et santé du projet tel qu'il était
        resultat = ecriture.supprimer_projet(request.user, id)
        return Response(formes_projets.projet_ecrit(resultat, ctx))


class ProjetReordonnerVue(APIView):
    """POST projets/{id}/reordonner/ — ordre manuel, « Mettre en haut »."""

    permission_classes = PERMISSIONS

    @extend_schema(request=REORDONNER, responses=SANS_CORPS)
    def post(self, request, id):
        donnees = _valider(formes_projets.ReordonnerSerializer, request.data)
        ecriture.reordonner_projet(request.user, id, avant_id=donnees.get('avant_id'),
                                   apres_id=donnees.get('apres_id'))
        return Response(status=204)


class TrierParPrioriteVue(APIView):
    """POST projets/trier-par-priorite/ — ordre par priorité, une fois."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(None, statut=204))
    def post(self, request):
        ecriture.trier_par_priorite(request.user)
        return Response(status=204)


class ProjetAffichageVue(APIView):
    """GET projets/{id}/vue/ — sections, ITEM, avancement, santé, jalon, burn-up."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[parametre('vue', OpenApiTypes.STR, 'liste, tableau ou chronologie.')],
                   responses=reponses(forme_echantillon('projet_vue'), erreurs=(400, 404)))
    def get(self, request, id):
        _valider(formes_projets.VueProjetSerializer, {k: v for k, v in request.query_params.items() if k == 'vue'})
        projet = _projet_ou_404(request, id)
        etat, ctx = _etat(request)
        return Response(formes_projets.vue_du_projet(request.user, projet, etat, ctx, etat.jour))


class PlanificationApercuVue(APIView):
    """POST projets/{id}/planification/apercu/ — lire une liste, rien n'est écrit."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('PlanificationApercu', {'texte': 'Études :\nVisite\n- photos\n◆ Mise en service'},
                                 requis=('texte',)),
                   responses=reponses(forme_echantillon('planification_apercu'), erreurs=(400, 404)))
    def post(self, request, id):
        projet = _projet_ou_404(request, id)
        if est_assistant(request) and est_confidentielle(projet):
            raise PermissionDenied("Ce projet est confidentiel : l'assistant ne lit pas sa liste.")
        donnees = _valider(formes_projets.ApercuPlanSerializer, request.data)
        return Response(formes_projets.apercu_du_plan(projet, donnees['texte']))


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
        donnees = dict(_valider(formes_projets.PlanificationSerializer, request.data))
        version = donnees.pop('lock_version')
        assistant = est_assistant(request)

        def creer():
            resultat = _avec_conflit_projet(request, lambda: ecriture.planifier_projet(
                request.user, id, donnees, version=version, assistant=assistant))
            _, ctx = _etat(request)
            return Response(_json(formes_projets.planification_rendue(request.user, resultat, ctx)), status=201)
        return self._avec_idempotence(request, creer, suffixe=f'u{request.user.pk}')


class DecalerVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/decaler/ — `{"delta_jours","apercu"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('Decaler', {'delta_jours': 7, 'apercu': True}, requis=('delta_jours',)),
                   responses=reponses(forme_echantillon('decalage'), erreurs=(400, 404)))
    def post(self, request, id):
        donnees = _valider(formes_projets.DecalerSerializer, request.data)
        usage = 'assistant' if est_assistant(request) else 'ecran'

        def decaler():
            try:
                changements, geste = ecriture.decaler_projet(
                    request.user, id, donnees['delta_jours'], apercu=donnees['apercu'], usage=usage)
            except ecriture.DecalageRefuse as refus:
                # Le refus rend l'aperçu : ce qui AURAIT bougé, et les tâches qui passeraient avant aujourd'hui.
                return Response(_json({'delta_jours': [refus.refus], 'changements': refus.changements,
                                       'avant_aujourdhui': refus.avant_aujourdhui}), status=400)
            return Response(_json(formes_projets.decalage_rendu(changements, geste)))
        return self._avec_idempotence(request, decaler, suffixe=f'u{request.user.pk}')


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
        donnees = _valider(formes_projets.TerminerSerializer, request.data)
        resultat = ecriture.terminer_projet(request.user, id, **donnees)
        return _ecrit(request, resultat)


class ProjetRouvrirVue(APIView):
    """POST projets/{id}/rouvrir/ — réouverture."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(PROJET_ECRIT, erreurs=(404,)))
    def post(self, request, id):
        return _ecrit(request, ecriture.rouvrir_projet(request.user, id))


class ProjetRestaurerVue(APIView):
    """POST projets/{id}/restaurer/ — le projet et les tâches supprimées avec lui."""

    permission_classes = PERMISSIONS

    @extend_schema(request=None, responses=reponses(PROJET_ECRIT, erreurs=(404,), conflit=ERREUR_CODE))
    def post(self, request, id):
        return _ecrit(request, ecriture.restaurer_projet(request.user, id))


class DupliquerVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/dupliquer/ — `{"nom","date_debut","apercu"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('Dupliquer', {'nom': 'Salon 2027', 'date_debut': '2027-03-01', 'apercu': True},
                                 requis=('nom',)),
                   responses=APERCU_OU_CREATION)
    def post(self, request, id):
        donnees = _valider(formes_projets.DupliquerSerializer, request.data)
        projet = _projet_ou_404(request, id)
        if est_assistant(request) and est_confidentielle(projet):
            raise PermissionDenied(MESSAGE_PROJET_CONFIDENTIEL)

        def dupliquer():
            return _reponse_instance(request, ecriture.dupliquer_projet(
                request.user, id, donnees['nom'], donnees.get('date_debut'), apercu=donnees['apercu']))
        return self._avec_idempotence(request, dupliquer, suffixe=f'u{request.user.pk}')


class EnregistrerModeleVue(IdempotentCreateMixin, APIView):
    """POST projets/{id}/enregistrer-modele/ — `{"nom","inclure_notes"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('EnregistrerModele', {'nom': 'Salon', 'inclure_notes': False}, requis=('nom',)),
                   responses=reponses(forme_echantillon('modele'), statut=201, erreurs=(400, 404)))
    def post(self, request, id):
        donnees = _valider(formes_projets.EnregistrerModeleSerializer, request.data)
        projet = _projet_ou_404(request, id)
        if est_assistant(request) and est_confidentielle(projet):
            raise PermissionDenied(MESSAGE_PROJET_CONFIDENTIEL)

        def enregistrer():
            modele = ecriture.enregistrer_modele(request.user, id, donnees['nom'],
                                                 inclure_notes=donnees['inclure_notes'])
            return Response(_json(_forme_modele(request, modele)), status=201)
        return self._avec_idempotence(request, enregistrer, suffixe=f'u{request.user.pk}')


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
        donnees = _valider(formes_projets.SectionCreationSerializer, request.data)
        section, geste = ecriture.creer_section(request.user, **donnees)
        return Response(formes_projets.section_ecrite(section, geste), status=201)


class SectionVue(APIView):
    """PATCH (renommer, dates) · DELETE (tâches « Sans étape ») sections/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=inline_serializer('TachesCorpsSectionPatch', {
        'nom': serializers.CharField(required=False, max_length=120),
        'date_debut': serializers.DateField(required=False, allow_null=True),
        'date_fin': serializers.DateField(required=False, allow_null=True),
    }), responses=reponses(SECTION, erreurs=(400, 404)))
    def patch(self, request, id):
        donnees = _valider(formes_projets.SectionModificationSerializer, request.data)
        section, geste = ecriture.modifier_section(request.user, id, donnees)
        return Response(formes_projets.section_ecrite(section, geste))

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        geste = ecriture.supprimer_section(request.user, id)
        return Response({'geste_id': geste.pk})


class SectionReordonnerVue(APIView):
    """POST sections/{id}/reordonner/."""

    permission_classes = PERMISSIONS

    @extend_schema(request=REORDONNER, responses=SANS_CORPS)
    def post(self, request, id):
        donnees = _valider(formes_projets.ReordonnerSerializer, request.data)
        ecriture.reordonner_section(request.user, id, avant_id=donnees.get('avant_id'),
                                    apres_id=donnees.get('apres_id'))
        return Response(status=204)


class ModelesVue(APIView):
    """GET modeles/ — liste paginée."""

    permission_classes = PERMISSIONS
    schema = mots_operation(get='list')  # sinon même operationId que GET modeles/{id}/

    @extend_schema(parameters=PAGINATION, responses=reponses(forme_echantillon('modeles_liste')))
    def get(self, request):
        pagination = StandardPagination()
        modeles = lecture.modeles_servis(request.user, assistant=est_assistant(request))
        page = pagination.paginate_queryset(modeles.order_by('nom', 'id'), request, view=self)
        return pagination.get_paginated_response(formes_projets.ModeleListeSerializer(page, many=True).data)


class ModeleVue(APIView):
    """GET · PATCH `{"nom"}` · DELETE modeles/{id}/."""

    permission_classes = PERMISSIONS

    @extend_schema(responses=reponses(forme_echantillon('modele'), erreurs=(404,)))
    def get(self, request, id):
        return Response(_forme_modele(request, _modele_ou_404(request, id)))

    @extend_schema(request=corps('ModelePatch', {'nom': 'Salon'}, requis=('nom',)),
                   responses=reponses(forme_echantillon('modele'), erreurs=(400, 404)))
    def patch(self, request, id):
        donnees = _valider(formes_projets.ModeleModificationSerializer, request.data)
        _modele_ou_404(request, id)
        modele = ecriture.renommer_modele(request.user, id, donnees['nom'])
        return Response(_forme_modele(request, modele))

    @extend_schema(request=None, responses=reponses(GESTE, erreurs=(404,)))
    def delete(self, request, id):
        _modele_ou_404(request, id)
        ecriture.supprimer_modele(request.user, id)
        return Response({'geste_id': None})


class ModeleInstancierVue(IdempotentCreateMixin, APIView):
    """POST modeles/{id}/instancier/ — `{"nom","date_lancement","apercu"}`."""

    permission_classes = PERMISSIONS

    @extend_schema(request=corps('ModeleInstancier', {'nom': 'Salon', 'date_lancement': '2026-11-23',
                                                      'apercu': True}, requis=('nom',)),
                   responses=APERCU_OU_CREATION)
    def post(self, request, id):
        donnees = _valider(formes_projets.ModeleInstancierSerializer, request.data)
        _modele_ou_404(request, id)

        def instancier():
            return _reponse_instance(request, ecriture.instancier_modele(
                request.user, id, donnees['nom'], donnees.get('date_lancement'), apercu=donnees['apercu']))
        return self._avec_idempotence(request, instancier, suffixe=f'u{request.user.pk}')


class RevueProjetsVue(APIView):
    """GET revue/projets/ — bilan de la semaine (ou Semaine courte) et cartes."""

    permission_classes = PERMISSIONS

    @extend_schema(parameters=[parametre('semaine', OpenApiTypes.DATE, 'Lundi de la semaine ; défaut : courante.')],
                   responses=reponses(forme_echantillon('revue_projets'), erreurs=(400,)))
    def get(self, request):
        brut = request.query_params.get('semaine')
        try:
            semaine = datetime.date.fromisoformat(brut) if brut else timezone.localdate()
        except ValueError:
            raise serializers.ValidationError({'semaine': [MESSAGE_DATE]})
        if not jour_dans_bornes(semaine):
            raise serializers.ValidationError({'semaine': [MESSAGE_DATE]})
        etat, ctx = _etat(request)
        return Response(formes_projets.revue_des_projets(request.user, etat, ctx, lecture.lundi_de(semaine)))


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
        donnees = _valider(formes_projets.RevueDecisionSerializer, request.data)
        revue, projet, geste = ecriture.decider_revue(request.user, projet_id, donnees)
        _, ctx = _etat(request)
        return Response(formes_projets.decision_rendue(revue, projet, geste, ctx))
