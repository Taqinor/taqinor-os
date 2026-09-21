"""NTPRT19 — Vue PUBLIQUE du branding portail (page de login white-label).

Un seul endpoint, en lecture, sans authentification :
``GET /api/django/public/portail/theme/``.

La société est résolue STRICTEMENT par l'en-tête ``Host`` (domaine white-label
de ``TenantTheme``) — jamais par un paramètre de requête, qui transformerait cet
endpoint en énumérateur de tenants. Aucun host correspondant ⇒ marque VIDE
(200), jamais 404 : la page de login s'affiche simplement avec le thème par
défaut.

La charge utile ne contient QUE de la marque (nom affiché, logo, deux
couleurs) : ni identifiant de société, ni domaine, ni identité légale.

DURCISSEMENT (YRBAC9) : `AllowAny` sans authentification ⇒ le débit par IP est
BORNÉ. Sans cela, chaque appel déclenche une requête `TenantTheme` par `Host`,
donc un anonyme pouvait (a) énumérer les domaines white-label en faisant varier
l'en-tête `Host` autant qu'il voulait, et (b) charger la base gratuitement. Le
quota est par IP, donc indépendant du `Host` — faire varier le domaine ne
réarme pas le compteur, ce qui est précisément l'abus visé.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .branding import MARQUE_VIDE, company_pour_hote, marque_portail

# ── NTPRT6 — forme déclarée de l'acceptation d'invitation ───────────────────
ACCEPTER_INVITATION_PORTAIL_REQUEST = inline_serializer(
    'AccepterInvitationPortailRequest', {
        'token': serializers.CharField(),
        'mot_de_passe': serializers.CharField(),
    })

ACCEPTER_INVITATION_PORTAIL_RESPONSE = inline_serializer(
    'AccepterInvitationPortailResponse', {
        'detail': serializers.CharField(),
    })


class ThemePortailPublicThrottle(SimpleRateThrottle):
    """Quota anonyme du thème public, par IP (jamais par `Host`).

    60/minute : large pour un vrai chargement de page de login (quelques appels
    par visiteur, y compris derrière le NAT d'une société), étroit pour un
    balayage de domaines.
    """

    scope = 'portail_theme_public'
    rate = '60/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([ThemePortailPublicThrottle])
def theme_portail_public(request):
    """Marque du portail pour le domaine appelant (repli neutre)."""
    company = company_pour_hote(request.get_host())
    if company is None:
        return Response(dict(MARQUE_VIDE))
    return Response(marque_portail(company))


# ── NTPRT6 — Acceptation PUBLIQUE d'une invitation à l'équipe portail ───────

class AccepterInvitationPortailThrottle(SimpleRateThrottle):
    """Formulaire anonyme d'écriture (pose un mot de passe + crée un compte) :
    même patron de limitation par IP que ``CandidatureFournisseurThrottle``
    (NTPRT25) — un token seul ne suffit pas à se dispenser d'un plafond."""

    scope = 'portail_accepter_invitation'
    rate = '20/hour'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


@extend_schema(request=ACCEPTER_INVITATION_PORTAIL_REQUEST,
               responses=ACCEPTER_INVITATION_PORTAIL_RESPONSE)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AccepterInvitationPortailThrottle])
def accepter_invitation_portail_public(request):
    """NTPRT6 — L'invité pose son mot de passe via le lien reçu par email.

    ``token`` et ``mot_de_passe`` sont les SEULS champs lus — jamais d'email
    ni de rôle depuis le corps (l'un et l'autre viennent de l'invitation
    elle-même, posée côté serveur à l'appel ``inviter_membre_portail``). La
    réponse ne renvoie AUCUNE information sur l'invitation en cas d'échec
    (token inconnu/expiré/déjà utilisé/révoqué) — un seul message générique,
    jamais de quoi distinguer un token invalide d'un token déjà consommé.
    """
    from . import services

    token = (request.data.get('token') or '').strip()
    mot_de_passe = request.data.get('mot_de_passe') or ''
    if not token or not mot_de_passe:
        return Response(
            {'detail': 'Le token et le mot de passe sont requis.'},
            status=status.HTTP_400_BAD_REQUEST)

    user = services.accepter_invitation_portail(token, mot_de_passe)
    if user is None:
        return Response(
            {'detail': 'Invitation introuvable, déjà utilisée, révoquée '
                       'ou expirée.'},
            status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {'detail': 'Compte créé — vous pouvez maintenant vous connecter.'})


# ── XFAC26 / AUD148 — Relevé de compte self-service (lien tokenisé) ────────
#
# Correctif CI SOLMVP : cette surface vivait dans ``apps.compta`` (montée
# sous ``/api/django/compta/portail/<token>/mon-releve/``, shim ODX12 jamais
# achevé — voir ``apps.portail.selectors``, en-tête). SOLMVP30b a coquillé
# ``compta`` en app SANS AUCUNE url (contrat ``core.parked``) ; la lecture
# elle-même (``apps.ventes.selectors.releve_client_portail``) n'a jamais
# quitté le périmètre MVP solaire, seule sa porte d'entrée manquait. Elle
# reprend ICI, sous le préfixe public natif du portail, seule maison qu'elle
# ait jamais eue côté portail. ``portail_contester_facture`` (XFAC27) N'EST
# PAS restauré : il créait une ``litiges.Reclamation`` — ``litiges`` est une
# app parquée du MVP solaire (``core.parked``), donc hors périmètre, pas
# seulement de cette lane.

class RelevePortailThrottle(SimpleRateThrottle):
    """Débit du relevé de compte tokenisé, par IP (même patron que
    ``ThemePortailPublicThrottle``) : un token seul ne dispense jamais d'un
    plafond anonyme."""

    scope = 'portail_mon_releve'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


def _releve_noindex(response):
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _releve_not_found():
    return _releve_noindex(Response(
        {'detail': "Ce lien de portail est invalide ou n'existe pas."},
        status=status.HTTP_404_NOT_FOUND))


def _resoudre_compte_par_token(token):
    """Compte portail ACTIF pour ``token``, ou ``None`` — jamais cross-tenant.

    Horodate l'accès (AUD148) via le service dédié, jamais une écriture
    inline ici : même point d'entrée que le reste du module.
    """
    from . import services
    from .models import ComptePortailClient

    if not token:
        return None
    compte = (ComptePortailClient.objects
              .filter(token_acces=token, actif=True)
              .select_related('client')
              .first())
    if compte is not None:
        services.enregistrer_connexion_portail(
            compte.id, compte.derniere_connexion)
    return compte


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([RelevePortailThrottle])
def portail_mon_releve(request, token):
    """XFAC26 — Relevé de compte self-service : postes ouverts, solde
    courant, mini balance âgée (0-30/31-60/61-90/90+).

    GET /api/django/public/portail/<token>/mon-releve/

    Résout le compte par token (404 si invalide/inconnu/révoqué, sans fuite
    d'existence), puis lit le relevé via ``apps.ventes.selectors`` — jamais un
    import de ``apps.ventes.models``. Le client ne voit jamais le compte d'un
    autre (le relevé est celui de ``compte.client``, borné à la société du
    compte)."""
    compte = _resoudre_compte_par_token(token)
    if compte is None:
        return _releve_not_found()

    client = compte.client
    if client is None or client.company_id != compte.company_id:
        return _releve_not_found()

    from apps.ventes import selectors as ventes_selectors

    data = ventes_selectors.releve_client_portail(client)
    return _releve_noindex(Response(data))
