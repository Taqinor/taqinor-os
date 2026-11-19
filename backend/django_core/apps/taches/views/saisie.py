"""Saisie (reference/api.md §3.2, §4) : saisie rapide et capture (Siri, partage).

`saisie-rapide/` (TCH48) : aperçu, « Range ma liste » (`ids`) et création tout ou rien. `CHAMPS_LIGNE`
(le format d'une ligne à créer, api.md §4) est déclaré dans `serializers/saisie.py` : `taches/` POST le
réutilise.

`capture/` (TCH96, raccourci Siri) : authentifiée par le jeton `capture` SEUL (`auth_jeton.JetonCapture`,
401 neutre : société et propriétaire viennent du JETON, jamais du corps), bornée par ses débits. La
phrase dictée est une DONNÉE : elle est lue par le MÊME analyseur que la saisie (`saisie.analyseur`,
porte `capture` : jour, heure, moment, échéance, priorité, durée, projet EXISTANT — jamais une
création de projet, d'étape, d'étiquette, de récurrence ni de rappel) puis créée par le MÊME
`creer_taches` (source et porte `capture`). Rejeu au même `client_id` : 200 `deja: true`, la même
phrase, rien de créé. La phrase rendue passe CHAQUE nom par `nom_pour(…, 'siri')` (inv. 38 : un projet
confidentiel est dit « un projet »). `?reponse=texte` : la phrase (ou le refus) en `text/plain`, lue
par Siri (textes.md « L'écran Mon iPhone »).
"""
from django.db import transaction
from django.http import Http404, HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_serializer, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ParseError
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from apps.taches.auth_jeton import JetonCapture
from apps.taches.choix import Moment, Source
from apps.taches.confidentialite import SIRI, est_confidentielle, nom_pour
from apps.taches.models.taches import Tache
from apps.taches.moteur.gabarits import format_heure_dite, format_jour
from apps.taches.saisie.analyseur import analyser
from apps.taches.saisie.grammaire import ProjetConnu
from apps.taches.selectors.base import projets_de
from apps.taches.serializers.corps import CorpsTaches, parmi, present
from apps.taches.serializers.saisie import (
    CHAMPS_LIGNE, CHAMPS_SAISIE, SaisieEntreeSerializer, apercu_ids, apercu_saisie, reponse_creation,
    valider_lignes, verifier_proprietaire,
)
from apps.taches.services.creation import creer_taches
from apps.taches.services.taches import verifier_lien
from apps.taches.throttles import ThrottleCapture, ThrottleCaptureJour
from apps.taches.views.base import (
    ERREUR_CHAMPS, ERREUR_CODE, ERREUR_DETAIL, PARSEURS, PERMISSIONS, MethodeAvantJeton, carte_assistant, corps,
    est_assistant, forme_echantillon, parametre, reponses,
)
from core.idempotency import IdempotentCreateMixin

MESSAGE_REQUIS = 'Requis.'

LIGNE = inline_serializer('TachesLigne', dict(CHAMPS_LIGNE))

#: Le corps publié est celui que `SaisieEntreeSerializer` lit (mêmes champs), `lignes` = des LIGNES.
_SaisieRapide = type('TachesCorpsSaisieRapide', (CorpsTaches,), {
    **CHAMPS_SAISIE, 'lignes': serializers.ListField(child=LIGNE, required=False),
    # `SaisieRapideVue.post` : des `ids` (« Range ma liste »), un texte (aperçu), ou des `lignes` à créer.
    'regles_croisees': ((present('ids', {'type': 'array', 'minItems': 1}),
                         present('textes', {'type': 'array', 'minItems': 1}),
                         present('texte', {'type': 'string', 'minLength': 1}),
                         {'required': ['lignes'], 'properties': {'lignes': {'type': 'array', 'minItems': 1},
                                                                 'apercu': parmi(False)}}),),
})
SAISIE_RAPIDE = extend_schema_serializer(component_name='TachesCorpsSaisieRapide')(_SaisieRapide)


def _a_un_texte(donnees):
    return bool(donnees.get('textes') or donnees.get('texte') or donnees.get('ids'))


class SaisieRapideVue(IdempotentCreateMixin, APIView):
    """POST saisie-rapide/ — analyse, aperçu (`apercu:true`) ou création."""

    permission_classes = PERMISSIONS
    parser_classes = PARSEURS

    @extend_schema(request=SAISIE_RAPIDE, responses={
        **reponses(forme_echantillon('saisie_rapide'), statut=201, erreurs=(400, 404), conflit=ERREUR_CODE),
        200: forme_echantillon('saisie_apercu'),
    })
    def post(self, request):
        entree = SaisieEntreeSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        donnees = entree.validated_data
        verifier_proprietaire(request.user, donnees.get('proprietaire_attendu'))
        assistant = est_assistant(request)
        if donnees.get('ids'):
            return Response(apercu_ids(request.user, donnees['ids'], assistant=assistant))
        if donnees.get('apercu') or (_a_un_texte(donnees) and not donnees.get('lignes')):
            if not _a_un_texte(donnees):
                raise serializers.ValidationError({'texte': [MESSAGE_REQUIS]})
            return Response(apercu_saisie(request.user, donnees, assistant=assistant))
        if not donnees.get('lignes'):
            raise serializers.ValidationError({'lignes': [MESSAGE_REQUIS]})
        return self._avec_idempotence(
            request, lambda: self._creer(request, donnees, assistant), suffixe=f'u{request.user.pk}')

    def _creer(self, request, donnees, assistant):
        """Création TOUT OU RIEN (`creer_taches`, une transaction) → 201 `saisie_rapide.json`. Venant de
        l'assistant, le `titre` d'une ligne est IGNORÉ : sans ligne source, la ligne n'a plus de titre
        et est refusée (échec fermé)."""
        user = request.user
        lignes = valider_lignes(donnees['lignes'])
        if assistant:
            lignes = [{cle: valeur for cle, valeur in ligne.items() if cle != 'titre'} for ligne in lignes]
        if donnees.get('lien'):
            verifier_lien(user, donnees['lien'])
        # Une carte du Copilote validée au doigt : source `assistant`, porte de l'écran (ERR 5).
        source = Source.ASSISTANT if assistant or carte_assistant(request) else Source.RAPIDE
        with transaction.atomic():
            resultat = creer_taches(
                user, lignes, source=source,
                porte='assistant' if assistant else 'saisie', client_id=donnees.get('client_id') or None,
                lien=donnees.get('lien') or None, parent=donnees.get('parent_id'), par_ligne=True)
        return Response(reponse_creation(user, resultat, assistant=assistant), status=201)


# --- Capture (Siri) ------------------------------------------------------------------------------

MESSAGE_CAPTURE_VIDE = 'Dis-moi quoi noter.'
#: Réponses lues par Siri (textes.md « L'écran Mon iPhone ») : un refus ne dit jamais pourquoi.
MESSAGE_CAPTURE_REFUS = "Je n'ai pas pu noter : vérifie ton raccourci dans Mon iPhone."
MESSAGE_CAPTURE_DEBIT = "Trop de notes d'un coup : réessaie dans un moment."
MESSAGES_TEXTE_PAR_STATUT = {401: MESSAGE_CAPTURE_REFUS, 403: MESSAGE_CAPTURE_REFUS, 429: MESSAGE_CAPTURE_DEBIT}
#: En-têtes d'un refus gardés par sa version `text/plain` (le refus reste identique en tout point).
ENTETES_GARDES = ('WWW-Authenticate', 'Retry-After')
TEXTE = 'text/plain; charset=utf-8'
#: Le moment dit seul (« demain matin ») et le jour même (« ce soir »).
MOMENT_DIT = {Moment.MATIN: 'matin', Moment.APRES_MIDI: 'après-midi', Moment.SOIR: 'soir'}
MOMENT_DU_JOUR = {Moment.MATIN: 'ce matin', Moment.APRES_MIDI: 'cet après-midi', Moment.SOIR: 'ce soir'}
_VIDE = {'required': MESSAGE_CAPTURE_VIDE, 'blank': MESSAGE_CAPTURE_VIDE, 'null': MESSAGE_CAPTURE_VIDE,
         'invalid': MESSAGE_CAPTURE_VIDE}


class _Texte(serializers.CharField):
    """Un texte JSON seulement : un nombre n'est jamais converti (`1e400` deviendrait « inf », 12 « 12 »)."""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class CaptureEntreeSerializer(serializers.Serializer):
    """Corps de `capture/` (api.md §4) : titre ≤ 280, notes ≤ 2 000, client_id ≤ 64, des TEXTES — rien
    d'autre n'est lu (ni société, ni propriétaire, ni projet par id)."""

    titre = _Texte(max_length=280, error_messages={**_VIDE, 'max_length': '280 caractères au plus.'})
    notes = _Texte(required=False, allow_blank=True, max_length=2_000,
                   error_messages={'max_length': '2 000 caractères au plus.'})
    client_id = _Texte(required=False, allow_blank=True, max_length=64,
                       error_messages={'max_length': '64 caractères au plus.'})


def _ligne_capturee(user, titre, notes):
    """La LIGNE de `creer_taches` lue dans la phrase dictée par l'analyseur de la saisie, porte
    `capture` (projets du compte seulement ; aucune étape ni étiquette : la porte ne les lit pas)."""
    projets = tuple(ProjetConnu(id=p.pk, nom=p.nom, statut=p.statut, rang=p.rang)
                    for p in projets_de(user).order_by('rang', 'id'))
    analyse = analyser(titre, timezone.localdate(), timezone.localtime(), projets=projets, porte='capture')
    if not analyse.titre:  # « demain 10 h » seul : rien à noter (la réponse unique de api.md §4)
        raise serializers.ValidationError({'titre': [MESSAGE_CAPTURE_VIDE]})
    if analyse.erreurs:
        raise serializers.ValidationError(analyse.erreurs)
    return {**analyse.champs, 'titre': analyse.titre, 'notes': notes}


def _tache_capturee(user, **filtre):
    """La tâche capturée, relue (supprimée comprise : un rejeu ne ressuscite rien) avec ce que
    `nom_pour` lit — aucune requête de plus."""
    tache = (Tache.all_objects.filter(company_id=user.company_id, proprietaire=user, **filtre)
             .select_related('projet', 'parent', 'parent__projet').first())
    if tache is None:
        raise Http404('Introuvable.')
    return tache


def _dans(tache):
    """`journee` si un jour est posé, `projet` si un projet sans jour, sinon `a_trier` (une échéance seule
    laisse la tâche dans À trier, invariant 1)."""
    if tache.jour_prevu is not None:
        return 'journee'
    return 'projet' if tache.projet_id else 'a_trier'


def _quand(tache, aujourdhui):
    """« demain 10 h », « ce soir », « demain matin », « jeu. 19 »."""
    jour = format_jour(tache.jour_prevu, aujourdhui, phrase=True)
    if tache.heure_debut is not None:
        return f'{jour} {format_heure_dite(tache.heure_debut)}'
    if tache.moment in MOMENT_DIT:
        if tache.jour_prevu == aujourdhui:
            return MOMENT_DU_JOUR[tache.moment]
        return f'{jour} {MOMENT_DIT[tache.moment]}'
    return jour


def _phrase_siri(tache, aujourdhui):
    """La phrase lue par Siri (textes.md « L'écran Mon iPhone ») ; chaque nom par `nom_pour(…, 'siri')`."""
    titre = nom_pour(tache, SIRI)
    projet_secret = bool(tache.projet_id) and est_confidentielle(tache.projet)
    if est_confidentielle(tache) and not projet_secret:
        return f'Ajouté : {titre}'
    debut = 'Ajouté' if tache.jour_prevu is None else f'Ajouté pour {_quand(tache, aujourdhui)}'
    if tache.projet_id:
        nom = nom_pour(tache.projet, SIRI)
        return f'{debut} dans {nom} : {titre}' if projet_secret else f'{debut} dans « {nom} » : {titre}'
    if tache.jour_prevu is not None:
        return f'{debut} : {titre}'
    if tache.echeance is not None:
        return f"C'est noté, échéance {format_jour(tache.echeance, aujourdhui, phrase=True)} : {titre}"
    return f"C'est noté : {titre}"


def _premier_message(detail):
    """Le premier message d'une erreur par champ (`{"titre": ["…"]}` → « … »)."""
    if isinstance(detail, dict):
        detail = next(iter(detail.values()), '')
    if isinstance(detail, (list, tuple)):
        detail = detail[0] if detail else ''
    return _premier_message(detail) if isinstance(detail, (dict, list, tuple)) else str(detail)


class CaptureVue(MethodeAvantJeton, APIView):
    """POST capture/ — Siri / partage, jeton `capture` (J:capture)."""

    authentication_classes = [JetonCapture]
    permission_classes = PERMISSIONS
    throttle_classes = [*api_settings.DEFAULT_THROTTLE_CLASSES, ThrottleCapture, ThrottleCaptureJour]

    def _en_texte(self):
        requete = getattr(self, 'request', None)
        return getattr(requete, 'query_params', {}).get('reponse') == 'texte'

    def perform_content_negotiation(self, request, force=False):
        """Sous `?reponse=texte`, un `Accept: text/plain` n'est jamais un 406 : la réponse est écrite ici."""
        return super().perform_content_negotiation(request, force=force or self._en_texte())

    def handle_exception(self, exc):
        """Un refus (400, 401, 403, 429) sous `?reponse=texte` : sa phrase en `text/plain`, même statut,
        mêmes en-têtes `WWW-Authenticate`/`Retry-After` — toujours neutre, jamais le jeton. Un corps
        illisible (`ParseError`) se lit « Dis-moi quoi noter. » (textes.md, « 400 titre vide »)."""
        reponse = super().handle_exception(exc)
        statut = reponse.status_code
        if not self._en_texte() or (statut != 400 and statut not in MESSAGES_TEXTE_PAR_STATUT):
            return reponse
        if isinstance(exc, ParseError):  # corps illisible : jamais l'anglais du lecteur JSON (textes.md)
            texte = MESSAGE_CAPTURE_VIDE
        else:
            texte = MESSAGES_TEXTE_PAR_STATUT.get(statut) or _premier_message(getattr(exc, 'detail', ''))
        rendu = HttpResponse(texte, content_type=TEXTE, status=statut)
        for entete in ENTETES_GARDES:
            if entete in reponse:
                rendu[entete] = reponse[entete]
        return rendu

    @extend_schema(
        request=corps('Capture', {'titre': 'appeler le fournisseur demain 10 h', 'notes': '',
                                  'client_id': '7d2e0a11'}, requis=('titre',)),
        parameters=[parametre('reponse', OpenApiTypes.STR, 'texte : réponse en text/plain (Siri).')],
        responses={
            (201, 'application/json'): forme_echantillon('capture'),
            (201, 'text/plain'): OpenApiTypes.STR,
            (200, 'application/json'): forme_echantillon('capture'),
            (200, 'text/plain'): OpenApiTypes.STR,
            400: ERREUR_CHAMPS, 401: ERREUR_DETAIL, 429: ERREUR_DETAIL,
        })
    def post(self, request):
        entree = CaptureEntreeSerializer(data=request.data)
        entree.is_valid(raise_exception=True)
        donnees = entree.validated_data
        user = request.user
        ligne = _ligne_capturee(user, donnees['titre'], donnees.get('notes') or '')
        client_id = donnees.get('client_id') or None
        resultat = creer_taches(user, [ligne], source=Source.CAPTURE, porte='capture', client_id=client_id)
        deja = not resultat.creees
        tache = (_tache_capturee(user, client_id=client_id) if deja
                 else _tache_capturee(user, pk=resultat.creees[0].pk))
        message = _phrase_siri(tache, timezone.localdate())
        statut = 200 if deja else 201
        if self._en_texte():
            return HttpResponse(message, content_type=TEXTE, status=statut)
        return Response({'id': tache.pk, 'dans': _dans(tache), 'message': message, 'deja': deja}, status=statut)
