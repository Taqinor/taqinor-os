"""L'iPhone (reference/api.md §3.4 ; conception/spec-6b-iphone.md) : jetons d'accès, notification
de test, tuile Scriptable, calendrier abonné.

`jetons/` (session, jamais sous l'en-tête assistant : 403) : la liste ne sert jamais d'empreinte ; la
création rend le clair UNE fois et révoque l'ancien du même usage. La tuile et le flux sont
authentifiés par `JetonAccesAuthentication` de LEUR usage (`auth_jeton.py`) ; le flux sert du
`text/calendar`, son jeton est dans l'adresse (aucun en-tête d'authentification au schéma) : son
chemin est masqué pour les journaux et ses réponses d'erreur ne sont jamais réécrites par
`django.request`. `mon-iphone/test-notification/` (TCH97, reste) : `balayage.envoyer_test`, 204.

Tuile et flux (TCH97, regles.md §10) : la société et le propriétaire sont ceux du JETON (posés sur
`request.user` par l'authentification) ; la sélection est celle de l'écran — le préfiltre et la
journée de `selectors/journee.py`, les règles PURES de `moteur/flux.py` — et chaque titre passe par
`nom_pour(…, 'tuile' | 'flux')` : jamais de notes, de check-list, de lien ERP, de nom de projet, de
titre d'activité ERP ni de rendez-vous externe. Le flux est écrit par `reporting.calendar.build_ics`
(CRLF, lignes pliées à 75 octets, échappement, UID `tache-<id>@taqinor`, heures en UTC).
"""
import datetime

from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.permissions import BasePermission
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from apps.taches import balayage
from apps.taches.auth_jeton import JetonFlux, JetonTuile, emettre_jeton, revoquer_jeton
from apps.taches.choix import StatutTache
from apps.taches.confidentialite import nom_pour
from apps.taches.moteur import flux as moteur_flux
from apps.taches.selectors import journee as sel
from apps.taches.selectors.base import jetons_de
from apps.taches.serializers.presence import JetonEntreeSerializer, JetonSerializer, forme_jeton_cree
from apps.taches.services import journee as services_journee
from apps.taches.throttles import ThrottleFlux, ThrottleTuile
from apps.taches.views.base import (
    ERREUR_CODE, ERREUR_DETAIL, PARSEURS, PERMISSIONS, MethodeAvantJeton, est_assistant, forme_echantillon,
    reponses,
)
from core import chemins_sensibles

#: Refus du test de notification quand l'administrateur a coupé l'envoi (textes.md §2.21, mots du bandeau).
DETAIL_ENVOI_COUPE = 'Messages et rappels de Tâches coupés pour la société.'
CODE_ENVOI_COUPE = 'envoi_coupe'
#: `jetons/` rend au plus 20 lignes (api.md §0), actives d'abord puis les plus récentes.
PLAFOND_JETONS = 20
DETAIL_INTROUVABLE = 'Introuvable.'
DEBITS = list(api_settings.DEFAULT_THROTTLE_CLASSES)
#: Le calendrier abonné (textes.md §8) et son type servi.
NOM_CALENDRIER = 'Tâches Taqinor'
TYPE_ICS = 'text/calendar; charset=utf-8'
#: Toucher la tuile ouvre Aujourd'hui : l'hôte de la requête suivi de ce chemin (regles.md §10).
CHEMIN_AUJOURDHUI = '/taches/aujourdhui'
#: La tuile ne sert ni la capacité ni le temps disponible : `progression_du_jour` les calcule sur
#: ce neutre (aucune lecture de plus), seuls `faites`, `prevues` et l'Essentiel sont servis.
CAPACITE_HORS_TUILE = (0, '')
CHARGEMENT_ITEM = ('projet', 'recurrence', 'parent', 'parent__projet', 'bloquee_par')


def _titre_de(taches):
    """Le `nom_pour` des modules purs (appelé sur un `ItemPur`) branché sur la `Tache` lue, chargée
    avec `projet`, `parent` et `parent__projet` : aucune requête par titre."""
    def titre(item, usage, reglages):
        return nom_pour(taches[item.id], usage, reglages)
    return titre


# --- La tuile ------------------------------------------------------------------------------------

def _corps_tuile(user, jour, maintenant, lien):
    """`tuile.json` : la journée lue comme l'écran (`lire_journee`), `faites` par `compte_faites`,
    `prevues` et l'Essentiel par `progression_du_jour`, puis `moteur.flux.tuile_pure`."""
    reglages = sel.reglages_de(user)
    journee = sel.lire_journee(user, jour, reglages=reglages)
    closes = sel.activites_closes_du_jour(user, jour)
    faites, detail = sel.compte_faites(user, jour, closes)
    progression = sel.progression_du_jour(journee, faites=faites, detail=detail, capacite=CAPACITE_HORS_TUILE,
                                          closes=closes)
    taches = {pk: objet for (type_, pk), objet in journee.objets.items() if type_ == sel.TACHE}
    # L'objectif du jour est celui d'Aujourd'hui : LA fonction servie (jour court, plan validé).
    objectif = services_journee.objectif_du_jour(reglages, jour, sel.preferences_de(user), journee.plan)
    corps = moteur_flux.tuile_pure(
        list(journee.items.values()), jour, journee.plan_pur, objectif['nb'],
        progression, reglages, _titre_de(taches), journee.travailles)
    return {'jour': jour.isoformat(), 'maj': maintenant.isoformat(timespec='seconds'), **corps, 'lien': lien}


# --- Le flux de calendrier -----------------------------------------------------------------------

def _evenement_ics(evenement):
    """Forme d'appel de `reporting.calendar.build_ics` : journée entière (`date`) ou horodatée
    (`start_dt`/`end_dt` AWARE : l'heure murale de la société, écrite en UTC) ; `DESCRIPTION` vide."""
    forme = {'uid': evenement.uid, 'summary': evenement.titre, 'description': ''}
    if evenement.journee_entiere:
        forme['date'] = evenement.debut
    else:
        forme['start_dt'] = timezone.make_aware(evenement.debut)
        forme['end_dt'] = timezone.make_aware(evenement.fin)
    return forme


def ics_du_flux(evenements):
    """Le texte `.ics` des `EvenementFlux` (`moteur.flux.evenements_flux`), calendrier « Tâches
    Taqinor » — `build_ics` en import local (app de fondation, aucune édition de `calendar.py`)."""
    from apps.reporting.calendar import build_ics
    return build_ics(None, [_evenement_ics(e) for e in evenements], calname=NOM_CALENDRIER)


def _taches_du_flux(user, jour):
    """Le préfiltre de la journée (invariant 10), réduit aux tâches à faire prévues dans
    [J, J + 14] — `evenements_flux` décide du reste. Une requête, quel que soit leur nombre."""
    fin = jour + datetime.timedelta(days=moteur_flux.FENETRE_JOURS)
    return list(sel.taches_de_la_journee(user, jour)
                .filter(statut=StatutTache.A_FAIRE, jour_prevu__gte=jour, jour_prevu__lte=fin)
                .select_related(*CHARGEMENT_ITEM))


def _corps_flux(user, jour):
    reglages = sel.reglages_de(user)
    travailles = sel.travailles_autour(user, jour)
    focus = sel.projets_de_la_semaine(user, jour)
    taches = _taches_du_flux(user, jour)
    items = [sel.item_de_tache(tache, focus) for tache in taches]
    evenements = moteur_flux.evenements_flux(
        items, jour, reglages, _titre_de({tache.pk: tache for tache in taches}), travailles)
    return ics_du_flux(evenements)


class SansNegociation(BaseContentNegotiation):
    """Le flux répond au client d'abonnement quel que soit son `Accept` (un `Accept: text/calendar`
    ne doit jamais valoir un 406 avant le gestionnaire) : succès en `text/calendar` écrit par la vue,
    refus et erreurs en JSON."""

    def select_parser(self, request, parsers):
        return parsers[0] if parsers else None

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


class HorsAssistant(BasePermission):
    """403 sous l'en-tête assistant (api.md §0 : `jetons/` ne sert jamais le relais du Copilote)."""

    message = "L'assistant ne gère pas les jetons."

    def has_permission(self, request, view):
        return not est_assistant(request)


class JetonsVue(APIView):
    """GET jetons/ (sans empreinte) · POST jetons/ `{usage}` (clair rendu UNE fois)."""

    permission_classes = [*PERMISSIONS, HorsAssistant]
    parser_classes = PARSEURS

    @extend_schema(responses=reponses(forme_echantillon('jetons_liste')))
    def get(self, request):
        jetons = (jetons_de(request.user)
                  .order_by(F('revoque_le').desc(nulls_first=True), '-created_at', '-pk')[:PLAFOND_JETONS])
        return Response({'results': JetonSerializer(jetons, many=True).data})

    @extend_schema(request=JetonEntreeSerializer,
                   responses=reponses(forme_echantillon('jeton'), statut=201, erreurs=(400,)))
    def post(self, request):
        entree = JetonEntreeSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        jeton, clair = emettre_jeton(request.user, entree.validated_data['usage'],
                                     entree.validated_data['libelle'])
        reponse = Response(forme_jeton_cree(request, jeton, clair), status=status.HTTP_201_CREATED)
        reponse['Cache-Control'] = 'no-store'
        return reponse


class JetonRevoquerVue(APIView):
    """POST jetons/{id}/revoquer/ — l'id d'un autre compte répond comme un id inconnu (404)."""

    permission_classes = [*PERMISSIONS, HorsAssistant]
    parser_classes = PARSEURS

    @extend_schema(request=None, responses=reponses(None, statut=204, erreurs=(404,)))
    def post(self, request, id):
        jeton = jetons_de(request.user).filter(pk=id).first()
        if jeton is None:
            raise NotFound(DETAIL_INTROUVABLE)
        revoquer_jeton(jeton)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TestNotificationVue(APIView):
    """POST mon-iphone/test-notification/ — push `TACHES_RAPPEL` au seul compte de la requête, hors plafond
    (`balayage.envoyer_test`) ; 204 sans corps. Coupe-circuit de la société allumé : rien n'est envoyé et la
    réponse le DIT (409 `envoi_coupe`, `detail` montré par Mon iPhone) — jamais un 204 muet."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=None, responses=reponses(None, statut=204, conflit=ERREUR_CODE))
    def post(self, request):
        if not balayage.envoyer_test(request.user):
            return Response({'detail': DETAIL_ENVOI_COUPE, 'code': CODE_ENVOI_COUPE}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TuileVue(MethodeAvantJeton, APIView):
    """GET tuile/ — tuile Scriptable, jeton `tuile` (J:tuile)."""

    authentication_classes = [JetonTuile]
    permission_classes = PERMISSIONS
    parser_classes = PARSEURS
    throttle_classes = [*DEBITS, ThrottleTuile]

    @extend_schema(responses={200: forme_echantillon('tuile'), 401: ERREUR_DETAIL, 429: ERREUR_DETAIL})
    def get(self, request):
        corps = _corps_tuile(request.user, timezone.localdate(), timezone.localtime(),
                             request.build_absolute_uri(CHEMIN_AUJOURDHUI))
        reponse = Response(corps)
        reponse['Cache-Control'] = 'no-store'
        return reponse


class FluxVue(MethodeAvantJeton, APIView):
    """GET flux/{jeton}.ics — calendrier abonné, jeton `flux` dans l'adresse (J:flux)."""

    authentication_classes = [JetonFlux]
    permission_classes = PERMISSIONS
    parser_classes = PARSEURS
    throttle_classes = [*DEBITS, ThrottleFlux]
    renderer_classes = [JSONRenderer]
    content_negotiation_class = SansNegociation

    def initialize_request(self, request, *args, **kwargs):
        """Le chemin porte le jeton : `request.path` (lu par les journaux, dont celui d'un 500) est
        masqué dès l'entrée de la vue par LA fonction de `core.chemins_sensibles` (motifs déclarés par
        `auth_jeton.CHEMINS_SENSIBLES`) ; le jeton reste lu dans les `kwargs` de l'adresse résolue."""
        request.path = chemins_sensibles.masquer(request.path)
        return super().initialize_request(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        """Le chemin porte le jeton : une réponse d'erreur n'est jamais écrite par `django.request`
        (« Not Found: /…/flux/<jeton>.ics ») ; `Cache-Control: no-store` partout."""
        response = super().finalize_response(request, response, *args, **kwargs)
        if response.status_code >= 400:
            response._has_been_logged = True
        response['Cache-Control'] = 'no-store'
        return response

    @extend_schema(auth=[], responses={
        (200, 'text/calendar'): OpenApiTypes.STR,
        (404, 'application/json'): ERREUR_DETAIL,
        (429, 'application/json'): ERREUR_DETAIL,
    })
    def get(self, request, jeton):
        # `jeton` a déjà servi à l'authentification ; il n'est ni relu, ni journalisé, ni rendu.
        return HttpResponse(_corps_flux(request.user, timezone.localdate()), content_type=TYPE_ICS)
