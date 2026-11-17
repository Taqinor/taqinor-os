"""Saisie (reference/api.md §3.2, §4) : saisie rapide et capture (Siri, partage).

`saisie-rapide/` (TCH48) : aperçu, « Range ma liste » (`ids`) et création tout ou rien. La capture
lève `PasEncore` (501) jusqu'à sa tâche ; elle est authentifiée par le jeton `capture`
(`auth_jeton.JetonCapture`, 401 neutre) et bornée par ses débits. `CHAMPS_LIGNE` (le format d'une
ligne à créer, api.md §4) est déclaré dans `serializers/saisie.py` : `taches/` POST le réutilise.
"""
from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from apps.taches.auth_jeton import JetonCapture
from apps.taches.choix import Source
from apps.taches.serializers.saisie import (
    CHAMPS_LIGNE, SaisieEntreeSerializer, apercu_ids, apercu_saisie, reponse_creation, valider_lignes,
    verifier_proprietaire,
)
from apps.taches.services.creation import creer_taches
from apps.taches.services.taches import verifier_lien
from apps.taches.throttles import ThrottleCapture, ThrottleCaptureJour
from apps.taches.views.base import (
    ERREUR_CHAMPS, ERREUR_CODE, ERREUR_DETAIL, PERMISSIONS, MethodeAvantJeton, PasEncore,
    corps, est_assistant, forme_echantillon, parametre, reponses,
)
from core.idempotency import IdempotentCreateMixin

MESSAGE_REQUIS = 'Requis.'

LIGNE = inline_serializer('TachesLigne', dict(CHAMPS_LIGNE))

SAISIE_RAPIDE = inline_serializer('TachesCorpsSaisieRapide', {
    'textes': serializers.ListField(child=serializers.CharField(), required=False),
    'texte': serializers.CharField(required=False),
    'ids': serializers.ListField(child=serializers.IntegerField(), required=False),
    'client_id': serializers.CharField(max_length=64, required=False),
    'projet_id': serializers.IntegerField(allow_null=True, required=False),
    'lien': serializers.JSONField(allow_null=True, required=False),
    'parent_id': serializers.IntegerField(allow_null=True, required=False),
    'proprietaire_attendu': serializers.IntegerField(required=False),
    'ignorer': serializers.ListField(child=serializers.JSONField(), required=False),
    'lignes': serializers.ListField(child=LIGNE, required=False),
    'apercu': serializers.BooleanField(required=False),
})


def _a_un_texte(donnees):
    return bool(donnees.get('textes') or donnees.get('texte') or donnees.get('ids'))


class SaisieRapideVue(IdempotentCreateMixin, APIView):
    """POST saisie-rapide/ — analyse, aperçu (`apercu:true`) ou création."""

    permission_classes = PERMISSIONS

    @extend_schema(request=SAISIE_RAPIDE, responses={
        **reponses(forme_echantillon('saisie_rapide'), statut=201, erreurs=(400,), conflit=ERREUR_CODE),
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
        with transaction.atomic():
            resultat = creer_taches(
                user, lignes, source=Source.ASSISTANT if assistant else Source.RAPIDE,
                porte='assistant' if assistant else 'saisie', client_id=donnees.get('client_id') or None,
                lien=donnees.get('lien') or None, parent=donnees.get('parent_id'), par_ligne=True)
        return Response(reponse_creation(user, resultat, assistant=assistant), status=201)


class CaptureVue(MethodeAvantJeton, APIView):
    """POST capture/ — Siri / partage, jeton `capture` (J:capture)."""

    authentication_classes = [JetonCapture]
    permission_classes = PERMISSIONS
    throttle_classes = [*api_settings.DEFAULT_THROTTLE_CLASSES, ThrottleCapture, ThrottleCaptureJour]

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
        raise PasEncore()
