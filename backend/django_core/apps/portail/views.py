"""Vues du module Portail client (``apps.portail``).

ODX12 — ré-export TRANSITOIRE des ViewSets portail qui vivent encore dans
``apps.compta.views`` (adossés à ``_ComptaBaseViewSet`` = ``TenantMixin`` +
``ModelViewSet``, avec le scoping ``request.user.company`` et l'assignation
forcée de ``company`` en ``perform_create``). Ce module donne aux nouvelles
routes ``/api/django/portail/…`` un point d'entrée ``apps.portail.views``
stable ; les anciennes routes ``/api/django/compta/…`` continuent de servir les
MÊMES classes. Les mécanismes d'authentification portail (tokens/comptes
clients) sont conservés À L'IDENTIQUE — aucun élargissement d'accès. ODX22
re-logera le corps ici.

NTPRT2 — ``ComptePortailClientViewSet`` est désormais une SOUS-CLASSE locale
qui ajoute l'action d'administration ``provisionner-acces`` (création du vrai
compte utilisateur portail). La classe de base compta reste servie À
L'IDENTIQUE sous ``/api/django/compta/…`` : la nouvelle action n'existe que sur
le préfixe ``/api/django/portail/…``, aucun endpoint historique n'est modifié.
"""

from rest_framework.decorators import action
from rest_framework.response import Response

from apps.compta.views import (  # noqa: F401
    AcceptationDevisPortailViewSet,
    DemandeTicketPortailViewSet,
    DocumentClientPortailViewSet,
    JalonChantierPortailViewSet,
    PaiementFacturePortailViewSet,
)
from apps.compta.views import (
    ComptePortailClientViewSet as _ComptePortailClientViewSetBase,
)
from authentication.permissions import IsAdminRole

from . import services


class ComptePortailClientViewSet(_ComptePortailClientViewSetBase):
    """Comptes d'accès au portail client + provisionnement d'un VRAI compte.

    Hérite intégralement du ViewSet compta (scoping société ``TenantMixin``,
    ``perform_create`` qui génère le token, garde de classe
    ``IsResponsableOrAdmin``) et n'ajoute QUE l'action NTPRT2.
    """

    def perform_update(self, serializer):
        """AUD138 — La bascule « Actif » RÉVOQUE (ou rouvre) vraiment l'accès.

        L'écran ERP PATCHe ``actif`` et annonce que la révocation « empêche la
        prochaine connexion ». Jusqu'ici ce drapeau n'était lu que par le
        chemin magic-link tokenisé : le compte utilisateur JWT (mécanisme
        PRIMAIRE depuis NTPRT2) continuait d'accéder à tout. Le PATCH est donc
        routé vers l'action serveur UNIQUE
        ``services.revoquer_acces_client`` / ``reactiver_acces_client``, qui
        ferme (ou rouvre) les DEUX portes dans la même transaction.

        Posé sur cette sous-classe — la seule montée sous
        ``/api/django/portail/comptes-portail/`` (PACT26) — pour ne pas créer
        une arête ``compta.views -> portail.services`` de plus.
        """
        avant = bool(getattr(serializer.instance, 'actif', True))
        compte = serializer.save()
        apres = bool(compte.actif)
        if apres == avant:
            return
        if apres:
            services.reactiver_acces_client(compte.company, compte.client_id)
        else:
            services.revoquer_acces_client(compte.company, compte.client_id)

    @action(
        detail=True,
        methods=['post'],
        url_path='provisionner-acces',
        permission_classes=[IsAdminRole],
    )
    def provisionner_acces(self, request, pk=None):
        """NTPRT2 — Ouvre au client un vrai compte utilisateur portail.

        RÉSERVÉ À L'ADMINISTRATEUR INTERNE (``IsAdminRole``), plus strict que
        la garde de classe ``IsResponsableOrAdmin`` : ouvrir un accès externe
        à des données client est une action d'administration, pas une action
        de Responsable. La garde par action est honorée nativement par DRF
        (ce ViewSet ne surcharge PAS ``get_permissions``) — un compte portail
        externe ne peut de toute façon pas l'atteindre (``is_admin_role`` est
        faux pour les rôles ``portail_*``).

        Le mot de passe temporaire n'est JAMAIS renvoyé ici : il part par
        email au client (cf. ``services.provisionner_compte_portail_client``).
        """
        compte = self.get_object()
        user, cree = services.provisionner_compte_portail_client(
            request.user.company, compte.client_id)
        if user is None:
            return Response(
                {'detail': 'Client inconnu pour cette société.'}, status=400)
        return Response({
            'utilisateur_id': user.id,
            'username': user.username,
            'email': user.email,
            'actif': user.is_active,
            'cree': cree,
            'detail': (
                'Accès portail créé — mot de passe temporaire envoyé par '
                'email.'
                if cree else
                'Un accès portail existe déjà pour ce client.'
            ),
        })
