"""NTPRT20/NTPRT27 — Tableaux de bord des portails FOURNISSEUR et PARTENAIRE.

Deux endpoints en LECTURE SEULE, symétriques du portail client :

* ``GET /api/django/portail/fournisseur/tableau-de-bord/``
* ``GET /api/django/portail/partenaire/tableau-de-bord/``

Chacun est gardé par la portée EXACTE correspondante
(``IsPortalFournisseurUser`` / ``IsPortalPartenaireUser``, NTPRT5+) : un compte
CLIENT — ou un compte portail d'une autre portée, ou un interne — est refusé.
La garde exige aussi un rattachement non nul, et les sélecteurs appelés exigent
le couple (société, entité) : un compte sans entité voit des compteurs à ZÉRO,
jamais les chiffres de la société entière.

Les lectures passent par ``stock.selectors`` / ``crm.selectors`` (jamais un
import de leurs ``models`` depuis portail — frontière cross-app CLAUDE.md).
"""
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from apps.roles.permissions import (
    IsPortalFournisseurUser, IsPortalPartenaireUser, portal_scope_id,
)


@api_view(['GET'])
@permission_classes([IsPortalFournisseurUser])
def tableau_de_bord_fournisseur(request):
    """NTPRT20 — cartes résumé du fournisseur connecté."""
    from apps.stock.selectors import resume_portail_fournisseur
    return Response(resume_portail_fournisseur(
        request.user.company, portal_scope_id(request.user)))


@api_view(['GET'])
@permission_classes([IsPortalPartenaireUser])
def tableau_de_bord_partenaire(request):
    """NTPRT27 — cartes résumé du partenaire connecté."""
    from apps.crm.selectors import resume_portail_partenaire
    return Response(resume_portail_partenaire(
        request.user.company, portal_scope_id(request.user)))


class CandidatureFournisseurThrottle(SimpleRateThrottle):
    """NTPRT25 — même patron de limitation que XPUR22 (par IP, cache-based,
    aucune dépendance nouvelle). Un formulaire d'auto-inscription PUBLIC est
    une surface d'écriture anonyme : sans plafond, c'est un injecteur de
    référentiel."""

    scope = 'portail_candidature_fournisseur'
    rate = '10/hour'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([CandidatureFournisseurThrottle])
def candidature_fournisseur(request):
    """NTPRT25 — auto-inscription d'un fournisseur (PUBLIC, rate-limité).

    La société est résolue par l'en-tête ``Host`` (domaine white-label du
    tenant, même mécanique que NTPRT19) — JAMAIS par un champ du corps : sinon
    n'importe qui poserait une candidature dans le référentiel du tenant de son
    choix. Hôte non reconnu ⇒ 404, jamais de fournisseur orphelin ni rattaché
    au mauvais tenant.

    Le fournisseur naît ``statut_validation='en_attente_validation'`` : il
    n'apparaît dans AUCUNE liste de sourcing automatique tant qu'un
    administrateur interne n'a pas tranché (``decider-candidature``). Seuls les
    champs de ``CHAMPS_CANDIDATURE_FOURNISSEUR`` sont lus du corps — ni
    ``statut``, ni ``statut_validation``, ni ``company``.

    La réponse ne renvoie AUCUNE donnée de la société ni l'id créé : un
    formulaire public n'a pas à savoir ce qui existe de l'autre côté.
    """
    from apps.stock.services import enregistrer_candidature_fournisseur

    from .branding import company_pour_hote

    company = company_pour_hote(request.get_host())
    if company is None:
        return Response({'detail': 'Introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    fournisseur = enregistrer_candidature_fournisseur(company, request.data)
    if fournisseur is None:
        return Response(
            {'detail': 'Le nom de votre société est requis.'},
            status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {'detail': 'Votre candidature a bien été enregistrée. Elle sera '
                   'examinée par nos équipes.'},
        status=status.HTTP_201_CREATED)
