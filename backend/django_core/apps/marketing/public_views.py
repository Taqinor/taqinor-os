"""Vues PUBLIQUES du module Marketing (``apps.marketing``).

WIR64 / FG206 — capture de lead publique depuis un ``FormulaireIntake`` : une
landing page tokenisée par ``slug`` (``AllowAny``) qui crée un lead via
``crm.services`` (jamais d'import des modèles crm). NTMKT16/17 (plan
CRM_VENTES) supposaient ce module ; il n'existait pas — cette tâche le livre.

Contrat de sécurité :
- ``AllowAny`` + débit par IP (anti-abus/brute-force du slug), même patron que
  les autres endpoints marketing publics (``_MarketingPublicThrottle``) ;
- la société vient TOUJOURS du formulaire résolu côté serveur, jamais du corps ;
- seul un formulaire ``actif=True`` est adressable ;
- l'écriture crm passe par ``apps.marketing.services`` → ``apps.crm.services``.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from . import services

_PREFERENCES_RESPONSE = inline_serializer('PreferencesPubliques', {
    'destinataire': drf_serializers.CharField(),
    'canaux': drf_serializers.DictField(child=drf_serializers.BooleanField()),
    'listes': drf_serializers.ListField(child=inline_serializer(
        'PreferencesPubliquesListe', {
            'id': drf_serializers.IntegerField(),
            'nom': drf_serializers.CharField(),
            'abonne': drf_serializers.BooleanField(),
        })),
})
# GET n'a pas de corps ; POST en a un (canaux/listes choisis) — sans
# `request=`, drf-spectacular tente de deviner un serializer pour LA MEME
# vue GET+POST et echoue sur le cote POST (« unable to guess serializer »).
_PREFERENCES_REQUEST = inline_serializer('PreferencesPubliquesRequest', {
    'canaux': drf_serializers.DictField(
        child=drf_serializers.BooleanField(), required=False),
    'listes': drf_serializers.DictField(
        child=drf_serializers.BooleanField(), required=False),
})


class _IntakePublicThrottle(SimpleRateThrottle):
    """WIR64 — débit par IP de la capture de lead publique (anti-abus / spam
    de soumissions). Même patron que ``_MarketingPublicThrottle``."""
    scope = 'marketing_intake_public'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope, 'ident': self.get_ident(request)}


def _serialiser_formulaire(formulaire):
    """Représentation PUBLIQUE d'un formulaire (aucune donnée sensible : ni
    société, ni compteurs, ni prix — juste de quoi rendre la landing).

    NTMKT16 — ``page`` porte le contenu éditorial de la DERNIÈRE version
    PUBLIÉE (jamais un brouillon) ; ``None`` tant qu'aucune version n'est
    publiée, ce qui laisse le rendu historique inchangé.
    """
    version = services.derniere_version_publiee(formulaire)
    return {
        'slug': formulaire.slug,
        'nom': formulaire.nom,
        'champs': formulaire.champs or [],
        'page': None if version is None else {
            'version': version.version,
            'titre': version.titre,
            'pitch': version.pitch,
            'image_key': version.image_key,
        },
    }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([_IntakePublicThrottle])
def formulaire_intake_public(request, slug):
    """WIR64/FG206 — définition publique d'un formulaire d'intake ACTIF, par
    slug (pour rendre la landing). 404 si inconnu ou inactif."""
    formulaire = services.formulaire_intake_actif_par_slug(slug)
    if formulaire is None:
        return Response({'detail': 'Formulaire introuvable.'}, status=404)
    return Response(_serialiser_formulaire(formulaire))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([_IntakePublicThrottle])
def formulaire_intake_soumettre(request, slug):
    """WIR64/FG206 — soumission publique : crée un lead via crm.services et
    renvoie 201. ``nom`` obligatoire. La société vient du formulaire, jamais
    du corps."""
    formulaire = services.formulaire_intake_actif_par_slug(slug)
    if formulaire is None:
        return Response({'detail': 'Formulaire introuvable.'}, status=404)
    try:
        lead = services.creer_lead_depuis_intake(formulaire, request.data)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    return Response({'id': lead.id, 'cree': True}, status=201)


# ── NTMKT22 — Centre de préférences self-service (public, tokenisé) ─────────
# Même modèle de confiance que ``desinscription/<token>`` (XMKT3) : le jeton
# signé porte la société ET le destinataire ; aucune donnée n'est lue de
# l'URL en clair, aucun autre contact n'est adressable avec un jeton donné.

@extend_schema(request=_PREFERENCES_REQUEST, responses=_PREFERENCES_RESPONSE)
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([_IntakePublicThrottle])
def preferences_publiques(request, token):
    """NTMKT22 — GET : préférences actuelles du contact ; POST : les
    enregistre (par canal / par liste). Jeton invalide ou expiré → 400 propre,
    jamais une 500 ni une fuite d'existence."""
    company, destinataire = services.lire_token_preferences(token)
    if company is None:
        return Response({'detail': 'Lien invalide.'}, status=400)
    if request.method == 'GET':
        return Response(services.preferences_actuelles(company, destinataire))
    return Response(services.enregistrer_preferences(
        company, destinataire, request.data))
