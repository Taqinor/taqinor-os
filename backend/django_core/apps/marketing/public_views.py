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
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from . import services


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
    société, ni compteurs, ni prix — juste de quoi rendre la landing)."""
    return {
        'slug': formulaire.slug,
        'nom': formulaire.nom,
        'champs': formulaire.champs or [],
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
