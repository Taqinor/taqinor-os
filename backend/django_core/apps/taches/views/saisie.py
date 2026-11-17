"""Saisie (reference/api.md §3.2, §4) : saisie rapide et capture (Siri, partage).

Routes déclarées : leurs vues lèvent `PasEncore` (501) jusqu'à leur tâche de construction ; la
capture est authentifiée par le BOUCHON `JetonPasEncoreLivre` (401 neutre) tant que
`JetonAccesAuthentication` n'est pas livrée. `LIGNE` (le format d'une ligne à créer, api.md §4)
est déclarée ICI une fois : `taches/` POST la réutilise.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView

from apps.taches.views.base import (
    AUTH_JETON, ERREUR_CHAMPS, ERREUR_CODE, ERREUR_DETAIL, PERMISSIONS, PasEncore, corps,
    forme_echantillon, parametre, reponses,
)
from core.idempotency import IdempotentCreateMixin


def _facultatif(champ, **options):
    return champ(required=False, **options)


#: Une LIGNE à créer (api.md §4) : `projet_id` / `nouveau_projet` et `section_id` /
#: `nouvelle_section` exclusifs ; `rappel` absolu `{jour, heure}` ou ancré `{ancre,
#: decalage_jours, heure}` ; `etiquettes` = ids ou `{"nom"}` ; `lien` = `{cible, id}`.
CHAMPS_LIGNE = {
    'index': _facultatif(serializers.IntegerField),
    'collage': _facultatif(serializers.IntegerField),
    'client_id': _facultatif(serializers.CharField, max_length=64),
    'titre': _facultatif(serializers.CharField, max_length=280),
    'projet_id': _facultatif(serializers.IntegerField, allow_null=True),
    'nouveau_projet': inline_serializer('TachesLigneNouveauProjet', {
        'nom': serializers.CharField(max_length=120),
        'priorite': serializers.IntegerField(required=False),
    }, required=False, allow_null=True),
    'section_id': _facultatif(serializers.IntegerField, allow_null=True),
    'nouvelle_section': inline_serializer('TachesLigneNouvelleSection', {
        'nom': serializers.CharField(max_length=120),
    }, required=False, allow_null=True),
    'priorite': _facultatif(serializers.IntegerField),
    'jour_prevu': _facultatif(serializers.DateField, allow_null=True),
    'moment': _facultatif(serializers.CharField, allow_blank=True),
    'heure_debut': _facultatif(serializers.CharField, allow_null=True),
    'echeance': _facultatif(serializers.DateField, allow_null=True),
    'echeance_heure': _facultatif(serializers.CharField, allow_null=True),
    'quelque_jour': _facultatif(serializers.BooleanField),
    'estimation_minutes': _facultatif(serializers.IntegerField, allow_null=True),
    'etiquettes': _facultatif(serializers.ListField, child=serializers.JSONField()),
    'recurrence': _facultatif(serializers.JSONField, allow_null=True),
    'rappel': _facultatif(serializers.JSONField, allow_null=True),
    'notes': _facultatif(serializers.CharField, allow_blank=True),
    'checklist': _facultatif(serializers.ListField, child=serializers.CharField()),
    'lien': inline_serializer('TachesLigneLien', {
        'cible': serializers.CharField(), 'id': serializers.IntegerField(),
    }, required=False, allow_null=True),
}
LIGNE = inline_serializer('TachesLigne', CHAMPS_LIGNE)

SAISIE_RAPIDE = inline_serializer('TachesCorpsSaisieRapide', {
    'textes': _facultatif(serializers.ListField, child=serializers.CharField()),
    'texte': _facultatif(serializers.CharField),
    'ids': _facultatif(serializers.ListField, child=serializers.IntegerField()),
    'client_id': _facultatif(serializers.CharField, max_length=64),
    'projet_id': _facultatif(serializers.IntegerField, allow_null=True),
    'lien': _facultatif(serializers.JSONField, allow_null=True),
    'parent_id': _facultatif(serializers.IntegerField, allow_null=True),
    'proprietaire_attendu': _facultatif(serializers.IntegerField),
    'ignorer': _facultatif(serializers.ListField, child=serializers.JSONField()),
    'lignes': _facultatif(serializers.ListField, child=LIGNE),
    'apercu': _facultatif(serializers.BooleanField),
})


class SaisieRapideVue(IdempotentCreateMixin, APIView):
    """POST saisie-rapide/ — analyse, aperçu (`apercu:true`) ou création."""

    permission_classes = PERMISSIONS

    @extend_schema(request=SAISIE_RAPIDE, responses={
        **reponses(forme_echantillon('saisie_rapide'), statut=201, erreurs=(400,), conflit=ERREUR_CODE),
        200: forme_echantillon('saisie_apercu'),
    })
    def post(self, request):
        raise PasEncore()


class CaptureVue(APIView):
    """POST capture/ — Siri / partage, jeton `capture` (J:capture)."""

    authentication_classes = AUTH_JETON
    permission_classes = PERMISSIONS

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
