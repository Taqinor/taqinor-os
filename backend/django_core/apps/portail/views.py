"""Vues du module Portail client (``apps.portail``).

SOLMVP16 — le corps de ces ViewSets vivait encore, par ré-export transitoire
ODX12, dans le module compta (adossés à ``_ComptaBaseViewSet`` = ``TenantMixin``
+ ``ModelViewSet``, avec le scoping ``request.user.company`` et l'assignation
forcée de ``company`` en ``perform_create``) ; il est désormais relogé ICI,
sur une base locale équivalente (``_PortailBaseViewSet``). Les mécanismes
d'authentification portail (tokens/comptes clients) sont conservés À
L'IDENTIQUE — aucun élargissement d'accès.

NTPRT2 — ``ComptePortailClientViewSet`` ajoute l'action d'administration
``provisionner-acces`` (création du vrai compte utilisateur portail) par
rapport au CRUD de base.
"""

import logging

from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminRole, IsResponsableOrAdmin

from . import services
from .models import (
    AcceptationDevisPortail,
    ComptePortailClient,
    DemandeTicketPortail,
    DocumentClientPortail,
    JalonChantierPortail,
    PaiementFacturePortail,
)
from .serializers import (
    AcceptationDevisPortailSerializer,
    ComptePortailClientSerializer,
    DemandeTicketPortailSerializer,
    DocumentClientPortailSerializer,
    JalonChantierPortailSerializer,
    PaiementFacturePortailSerializer,
)

#: AUD141 — journal des RÉVÉLATIONS et rotations de jeton portail (qui, quand,
#: sur quel compte). Le jeton lui-même n'est JAMAIS journalisé.
logger = logging.getLogger('portail.acces')


class _PortailBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class ComptePortailClientViewSet(_PortailBaseViewSet):
    """Comptes d'accès au portail self-service client (FG228) + provisionnement
    d'un VRAI compte utilisateur (NTPRT2). Le token est généré côté serveur ;
    le compte se lie au client par id (résolu via le service crm) et ne
    duplique aucune donnée métier (DC32)."""
    queryset = ComptePortailClient.objects.all()
    serializer_class = ComptePortailClientSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']

    def perform_create(self, serializer):
        # DC32 — le client est lié PAR FK ; on vérifie qu'il est bien dans la
        # société de l'utilisateur (jamais un client d'un autre tenant).
        client = serializer.validated_data.get('client')
        company = self.request.user.company
        if client is not None and getattr(
                client, 'company_id', None) != getattr(company, 'id', None):
            raise ValidationError(
                {'client': 'Client inconnu pour cette société.'})
        if client is None:
            raise ValidationError(
                {'client': 'Le client est requis pour ouvrir un accès portail.'})
        # AUDV03 / FG228 (DRAFT165-29) — le provisionnement passe par le
        # SERVICE, pas par un `serializer.save()` nu.
        #
        # Avant : chaque POST créait un compte de plus (ou heurtait la
        # contrainte d'unicité). `services.provisionner_compte_portail` est
        # idempotent par (société, client) : il renvoie le compte existant. Le
        # token reste généré côté serveur, à l'intérieur du service.
        #
        # AUD148(c) — re-provisionner NE RÉACTIVE JAMAIS un compte révoqué
        # (`actif=False`) : le service le renvoie TEL QUEL. Rouvrir un accès
        # révoqué reste une action admin explicite
        # (`apps.portail.services.reactiver_acces_client`), jamais un effet de
        # bord d'un POST de provisionnement.
        serializer.instance = services.provisionner_compte_portail(
            company, client_id=client.id)

    def perform_update(self, serializer):
        """AUD138 — La bascule « Actif » RÉVOQUE (ou rouvre) vraiment l'accès.

        L'écran ERP PATCHe ``actif`` et annonce que la révocation « empêche la
        prochaine connexion ». Jusqu'ici ce drapeau n'était lu que par le
        chemin magic-link tokenisé : le compte utilisateur JWT (mécanisme
        PRIMAIRE depuis NTPRT2) continuait d'accéder à tout. Le PATCH est donc
        routé vers l'action serveur UNIQUE
        ``services.revoquer_acces_client`` / ``reactiver_acces_client``, qui
        ferme (ou rouvre) les DEUX portes dans la même transaction.
        """
        avant = bool(getattr(serializer.instance, 'actif', True))
        # ``super()`` = ``TenantMixin.perform_update`` : la société reste forcée
        # côté serveur (jamais lue du corps) — on ajoute un effet, on n'en
        # retire aucun.
        super().perform_update(serializer)
        compte = serializer.instance
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

    # ── AUD141 — le jeton d'accès quitte le payload de liste ────────────────
    #
    # ``token_acces`` authentifie À LUI SEUL le relevé de compte, son PDF, la
    # contestation de facture et les vues publiques contrats. Il était affiché
    # en clair dans une colonne de l'écran ERP et publié dans son export CSV :
    # un export envoyé par email ou déposé sur un partage donnait un accès
    # permanent aux relevés financiers de tous les clients de la société.
    # ``ComptePortailClientSerializer`` ne rend donc plus qu'un aperçu
    # (4 derniers caractères) ; le lien complet ne s'obtient que par ces deux
    # actions, réservées à l'ADMINISTRATEUR et journalisées.

    @action(
        detail=True,
        methods=['post'],
        url_path='lien-acces',
        permission_classes=[IsAdminRole],
    )
    def lien_acces(self, request, pk=None):
        """AUD141 — Révèle le lien d'accès tokenisé, UNE demande à la fois.

        POST (jamais GET) : une révélation est un ACTE, pas une lecture — elle
        ne doit ni s'appeler en préchargement, ni finir dans un historique de
        navigateur ou un log d'accès HTTP. Réservée à l'administrateur, et
        journalisée (qui, quand, quel compte — jamais le jeton lui-même).
        """
        compte = self.get_object()
        logger.info(
            'AUD141 lien-acces revele — compte=%s client=%s societe=%s par=%s',
            compte.id, compte.client_id, compte.company_id, request.user.id)
        return Response({
            'token_acces': compte.token_acces,
            'lien': request.build_absolute_uri(
                f'/portail-contrats/{compte.token_acces}'),
            'detail': ("Lien d'accès révélé — cette demande est journalisée."),
        })

    @action(
        detail=True,
        methods=['post'],
        url_path='regenerer-jeton',
        permission_classes=[IsAdminRole],
    )
    def regenerer_jeton(self, request, pk=None):
        """AUD141 — Fait tourner le jeton : l'ancien lien cesse de fonctionner.

        Le geste de reprise quand un export ou un email a fui. Renvoie
        l'aperçu du NOUVEAU jeton, jamais le jeton entier — le lien complet se
        redemande explicitement par ``lien-acces``.
        """
        import secrets

        compte = self.get_object()
        compte.token_acces = secrets.token_urlsafe(32)
        compte.save(update_fields=['token_acces'])
        logger.info(
            'AUD141 jeton regenere — compte=%s client=%s societe=%s par=%s',
            compte.id, compte.client_id, compte.company_id, request.user.id)
        return Response({
            'token_apercu': self.get_serializer(compte).data.get(
                'token_apercu'),
            'detail': ("Jeton régénéré — l'ancien lien ne fonctionne plus."),
        })


class AcceptationDevisPortailViewSet(_PortailBaseViewSet):
    """Acceptations / e-signatures de devis depuis le portail (FG229).

    AUD140 — LECTURE SEULE côté ERP. Cette ligne EST la preuve d'acceptation
    électronique (signataire, IP, horodatage — loi 53-05) : son propre modèle
    justifie le ``PROTECT`` sur ``devis`` par cet argument. La création reste
    le chemin PORTAIL authentifié
    (``apps.portail.views_client.MesDevisPortailViewSet.accepter``, qui signe
    au nom du CLIENT connecté).
    """
    queryset = AcceptationDevisPortail.objects.all()
    serializer_class = AcceptationDevisPortailSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'signe_le']
    #: AUD140 — POST/PUT/PATCH/DELETE répondent 405 (aucune action d'écriture
    #: ne subsiste sur cette ressource : on peut fermer le verbe entier).
    http_method_names = ['get', 'head', 'options']


class PaiementFacturePortailViewSet(_PortailBaseViewSet):
    """Intentions de paiement en ligne d'une facture depuis le portail (FG230).

    AUD140 — LECTURE SEULE côté ERP, à l'exception de ``rapprocher`` (le SEUL
    workflow serveur : il confirme la réception d'un virement). La création
    reste le chemin PORTAIL authentifié
    (``apps.portail.views_client.MesFacturesPortailViewSet.payer``), qui appelle
    ``services.initier_paiement_facture``.
    """
    queryset = PaiementFacturePortail.objects.all()
    serializer_class = PaiementFacturePortailSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation', 'paye_le']

    def get_queryset(self):
        """AUD146 — Honore `?statut=` : la file « À rapprocher » était fausse.

        Une valeur inconnue est REFUSÉE (400) plutôt qu'ignorée : rendre la
        liste entière sur un filtre incompris est exactement le défaut.
        """
        qs = super().get_queryset()
        statut = (self.request.query_params.get('statut') or '').strip()
        if not statut:
            return qs
        if statut not in PaiementFacturePortail.Statut.values:
            raise ValidationError({'statut': 'Statut de paiement inconnu.'})
        return qs.filter(statut=statut)

    def _refus_lecture_seule(self, request):
        raise MethodNotAllowed(
            request.method,
            detail=("Une intention de paiement portail ne se crée, ne se "
                    "modifie et ne se supprime pas depuis l'ERP : elle est "
                    "posée par le client depuis son portail. Seule l'action "
                    "« rapprocher » est disponible."))

    def create(self, request, *args, **kwargs):
        self._refus_lecture_seule(request)

    def update(self, request, *args, **kwargs):
        self._refus_lecture_seule(request)

    def partial_update(self, request, *args, **kwargs):
        self._refus_lecture_seule(request)

    def destroy(self, request, *args, **kwargs):
        self._refus_lecture_seule(request)

    @action(detail=True, methods=['post'])
    def rapprocher(self, request, pk=None):
        paiement = self.get_object()
        reference = request.data.get('reference') or None
        services.rapprocher_paiement_facture(
            paiement, reference=reference, user=request.user)
        return Response(self.get_serializer(paiement).data)


class DocumentClientPortailViewSet(_PortailBaseViewSet):
    """Documents (factures ONEE…) téléversés par le client depuis le portail
    (FG231). La société est posée côté serveur ; ``marquer_traite`` signale
    qu'un document a été intégré à l'étude."""
    queryset = DocumentClientPortail.objects.all()
    serializer_class = DocumentClientPortailSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_depot']

    @action(detail=True, methods=['post'])
    def marquer_traite(self, request, pk=None):
        doc = self.get_object()
        if not doc.traite:
            doc.traite = True
            doc.save(update_fields=['traite'])
        return Response(self.get_serializer(doc).data)


class JalonChantierPortailViewSet(_PortailBaseViewSet):
    """Jalons d'avancement de chantier exposés au client (FG232). La société est
    posée côté serveur ; ``marquer_atteint`` avance un jalon (côté interne). Le
    client lit la timeline en lecture-seule côté portail."""
    queryset = JalonChantierPortail.objects.all()
    serializer_class = JalonChantierPortailSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'date_jalon', 'chantier_id']

    @action(detail=True, methods=['post'])
    def marquer_atteint(self, request, pk=None):
        jalon = self.get_object()
        if not jalon.atteint:
            from django.utils import timezone
            jalon.atteint = True
            if not jalon.date_jalon:
                jalon.date_jalon = timezone.localdate()
            jalon.save(update_fields=['atteint', 'date_jalon'])
        return Response(self.get_serializer(jalon).data)


class DemandeTicketPortailViewSet(_PortailBaseViewSet):
    """Demandes de ticket SAV ouvertes par le client depuis le portail (FG233).
    La société est posée côté serveur ; ``prendre_en_charge`` avance la demande
    et référence le ticket SAV créé (par id — le vrai ticket vit dans l'app sav,
    créé via son service, jamais importée ici)."""
    queryset = DemandeTicketPortail.objects.all()
    serializer_class = DemandeTicketPortailSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']

    @action(detail=True, methods=['post'])
    def prendre_en_charge(self, request, pk=None):
        demande = self.get_object()
        ticket_id = request.data.get('ticket_id')
        if demande.statut == DemandeTicketPortail.Statut.SOUMISE:
            demande.statut = DemandeTicketPortail.Statut.PRISE_EN_CHARGE
            if ticket_id:
                demande.ticket_id = ticket_id
            demande.save(update_fields=['statut', 'ticket_id'])
        return Response(self.get_serializer(demande).data)
