"""Rythme, cartes à réponse, préférences dites et en-tête du Copilote (reference/api.md §3.4, §4).

Toute donnée est celle de `request.user` (société ET propriétaire, `selectors/rythme.py`) ; le jour
est `services.rythme.aujourdhui()`. Le schéma OpenAPI de chaque route est celui de son échantillon de
`contract_samples/`.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.taches.choix import ClePreference, ModeRythme, SourcePreference
from apps.taches.moteur import rythme as moteur
from apps.taches.serializers.corps import parmi
from apps.taches.serializers.rythme import forme_proposition, forme_rythme, projets_cites
from apps.taches.services import rythme as service
from core.champs_stricts import MOTIF_SANS_NUL
from apps.taches.views.base import (
    ERREUR_CODE, PARSEURS, PERMISSIONS, est_assistant, forme_echantillon, reponses,
)

RYTHME = forme_echantillon('rythme')
INTROUVABLE = 'Introuvable.'
#: 409 d'une carte qui n'est plus ouverte (contract_samples/erreurs.json `proposition_expiree`).
DETAIL_EXPIREE = 'Cette proposition a expiré.'  # textes.md §2.16
CODE_EXPIREE = 'proposition_expiree'


def rythme_de(request, *, geste=None):
    """La réponse RYTHME de l'utilisateur de `request` (relue après une écriture)."""
    reglages = service.reglages_ou_defauts(request.user)
    return forme_rythme(request.user, reglages, service.aujourdhui(), assistant=est_assistant(request),
                        geste_id=geste.pk if geste is not None else None)


# Corps lus À LA MAIN par `services.rythme` (`_lire_corps`, `VALIDATIONS`) : publiés ici à l'identique — listes
# fermées, bornes, et une forme de `valeur` PAR clé de préférence (api-fuzz r2 : `cle` libre, « Clé inconnue. »).
_HEURE_HHMM = {'type': 'string', 'pattern': r'^(?:[01][0-9]|2[0-3]):[0-5][0-9]$'}
CORPS_RYTHME = {
    'type': 'object', 'required': ['mode'], 'properties': {
        'mode': {'type': 'string', **parmi(*ModeRythme.values)},
        'objectif': {'type': 'integer', 'minimum': moteur.PALIER_MIN, 'maximum': moteur.PALIER_MAX},
        'sens': {'type': 'string', 'nullable': True, **parmi(moteur.SENS_PLUS, moteur.SENS_MOINS, '', None)},
    }}


def _preference(cle, valeur):
    return {'type': 'object', 'required': ['cle', 'valeur'],
            'properties': {'cle': {'type': 'string', **parmi(cle)}, 'valeur': valeur}}


_HEURE_OU_OFF = {'anyOf': [{'type': 'string', **parmi(service.ETEINT)}, _HEURE_HHMM]}
CORPS_PREFERENCE = {'oneOf': [
    _preference(ClePreference.CAPACITE_JOUR_MIN,
                {'type': 'integer', 'minimum': service.CAPACITE_MIN, 'maximum': service.CAPACITE_MAX}),
    _preference(ClePreference.JOURS_TRAVAILLES,
                {'type': 'string', 'minLength': 7, 'maxLength': 7, 'pattern': '^[01]*1[01]*$'}),
    _preference(ClePreference.JOURS_COURTS,
                {'type': 'array', 'items': {'type': 'integer', 'minimum': 0, 'maximum': 6}}),
    _preference(ClePreference.CONGES, {'type': 'array', 'items': {
        'type': 'object', 'required': ['du', 'au'],
        'properties': {'du': {'type': 'string', 'format': 'date'}, 'au': {'type': 'string', 'format': 'date'}}}}),
    *(_preference(cle, _HEURE_OU_OFF) for cle in (
        ClePreference.HEURE_MATIN, ClePreference.RELANCE_JOUR, ClePreference.HEURE_SOIR)),
    _preference(ClePreference.HEURE_LIMITE, _HEURE_HHMM),
    _preference(ClePreference.REVUE_SEMAINE, {'anyOf': [
        {'type': 'string', **parmi(service.AUTO, service.ETEINT)}, {'type': 'integer', 'minimum': 0, 'maximum': 6}]}),
    _preference(ClePreference.ESSENTIEL_LE_MATIN, {'type': 'boolean'}),
    _preference(ClePreference.NOTE_LIBRE, {'type': 'array', 'maxItems': service.NOTES_MAX, 'items': {
        'type': 'string', 'maxLength': service.NOTE_LONGUEUR_MAX, 'pattern': MOTIF_SANS_NUL}}),
]}


class RythmeVue(APIView):
    """GET rythme/ (RYTHME) · POST rythme/ `{"mode","objectif"?,"sens"?}` (seul chemin du mode)."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(responses=reponses(RYTHME))
    def get(self, request):
        return Response(rythme_de(request))

    @extend_schema(request={'application/json': CORPS_RYTHME}, responses=reponses(RYTHME, erreurs=(400,)))
    def post(self, request):
        try:
            _reglages, geste = service.regler_rythme(request.user, request.data, service.aujourdhui())
        except service.ErreursRythme as exc:
            return Response(exc.erreurs, status=status.HTTP_400_BAD_REQUEST)
        return Response(rythme_de(request, geste=geste))


class RepondrePropositionVue(APIView):
    """POST rythme/propositions/{id}/repondre/ — `{"reponse"}`, toute carte à réponse."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request={'application/json': {
        'type': 'object', 'required': ['reponse'],
        'properties': {'reponse': {'type': 'string', **parmi(*service.REPONSES_ECRAN)}}}},
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
    parser_classes = PARSEURS

    @extend_schema(request={'application/json': CORPS_PREFERENCE}, responses=reponses(RYTHME, erreurs=(400,)))
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
    parser_classes = PARSEURS

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
    parser_classes = PARSEURS

    @extend_schema(responses=reponses(forme_echantillon('coach_entete')))
    def get(self, request):
        return Response({'lignes': service.entete_coach(request.user, service.aujourdhui())})
