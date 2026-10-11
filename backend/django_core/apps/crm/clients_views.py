"""SPL76 — sous-parcours clients (propriétaire « lead » au registre) :
salle de vente, partenaires, apporteurs, deals enregistrés, défis et T-TRACE
(VisiteExterne, AppareilEquipe), déplacés de ``views.py`` à l'identique
(move only) ; SPL78 — ClientViewSet et les actions clients de LeadViewSet
(``LeadClientsActionsMixin``) ; SPL80 — parrainage, objectifs, concurrents,
plans d'activité, équipes, forecast, plans de compte et playbooks.

Règle d'import : ce module n'importe JAMAIS ``views.py`` (``READ_ACTIONS`` et
``_PorteeEnfantsMixin`` viennent du module neutre ``actions_crud``).
"""
import re
import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import filters, mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from core.permissions import declared_action_permissions
from core.viewsets import CompanyScopedModelViewSet
from authentication.scoping import scope_queryset, scope_client_queryset
from .actions_crud import READ_ACTIONS, WRITE_ACTIONS, _PorteeEnfantsMixin
from apps.records.views import ChatterViewSetMixin
from .models import (
    AppareilEquipe, Apporteur, Client, ConcurrentPerte, DealEnregistre, Defi,
    EquipeCommerciale, ForecastEntry, ForecastSnapshot, Lead,
    LeadPlaybookProgress, ObjectifCommercial, Parrainage, Partenaire,
    PlanActivite, PlanCompte, Playbook, PlaybookEtape, PlaybookTache,
    RevueCompte, SalleVente, SalleVenteItem, VisiteExterne,
)
from .serializers import LeadActivitySerializer, masquer_pii_dict
from .serializers_clients import (
    AppareilEquipeSerializer, ClientSerializer, PartenaireSerializer,
    SalleVenteSerializer, SalleVenteItemSerializer, ApporteurSerializer,
    DealEnregistreSerializer, DefiSerializer, VisiteExterneSerializer,
    ConcurrentPerteSerializer, ParrainageSerializer, ObjectifCommercialSerializer,
    ObjectifAttainmentSerializer, PlanActiviteSerializer, EquipeCommercialeSerializer,
    ForecastEntrySerializer, ForecastSnapshotSerializer, PlanCompteSerializer,
    RevueCompteSerializer, PlaybookSerializer, PlaybookEtapeSerializer,
    PlaybookTacheSerializer, LeadPlaybookProgressSerializer,
)
from .services import COOKIE_APPAREIL, domaine_cookies_equipe, enregistrer_appareil_equipe
from . import activity
from . import schema_docs as sd
from authentication.permissions import (
    HasPermissionOrLegacy, IsAnyRole, IsResponsableOrAdmin, IsAdminRole,
)


class SalleVenteViewSet(_PorteeEnfantsMixin, CompanyScopedModelViewSet):

    """NTCRM17 — Salle de vente digitale (CRUD interne, authentifié).

    ``company`` posé côté serveur (TenantMixin). ``created_by`` forcé à la
    création. Lecture tout rôle, écriture responsable/admin (mêmes gardes
    que ``PointContactViewSet``). Ajout/retrait d'items via des actions
    dédiées (jamais un PATCH imbriqué non trivial du serializer nested)."""
    # ACRM9 — lectures bornées à la portée (leads : lead ;

    # clients : client).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ('lead',)

    portee_clients = ('client',)
    serializer_class = SalleVenteSerializer
    queryset = SalleVente.objects.select_related(
        'company', 'lead', 'client', 'created_by').prefetch_related('items').all()

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        # ACRM65 (D-ACRM-6 (ii)=(b)) — salles PARQUÉES quand le réglage
        # société est éteint : liste vide, détail / analytics / items 404
        # (get_object lit ce queryset). Rien n'est supprimé.
        from .parcage import salles_vente_actives
        qs = super().get_queryset()
        if not salles_vente_actives(self.request.user.company_id):
            return qs.none()
        return qs

    def perform_create(self, serializer):
        # ACRM65 — réglage éteint : aucune salle ne se crée (404, comme les
        # autres routes `salles-vente/`).
        from rest_framework.exceptions import NotFound

        from .parcage import salles_vente_actives
        if not salles_vente_actives(self.request.user.company_id):
            raise NotFound()
        serializer.save(company=self.request.user.company,
                        created_by=self.request.user)

    @extend_schema(request=SalleVenteItemSerializer, responses={201: SalleVenteItemSerializer})
    @action(detail=True, methods=['post'], url_path='items',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_item(self, request, pk=None):
        salle = self.get_object()
        # `{**request.data, ...}` transforme chaque valeur d'un QueryDict
        # (multipart/urlencoded) en liste à un élément (`'devis'` devient
        # `['devis']`), ce qui casse la validation du ChoiceField `type` —
        # `.copy()` + affectation préserve les valeurs scalaires quel que
        # soit le type de `request.data` (QueryDict ou dict JSON).
        data = request.data.copy()
        data['salle'] = salle.pk
        serializer = SalleVenteItemSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(salle=salle)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=['delete'], url_path=r'items/(?P<item_id>\d+)',
            permission_classes=[IsResponsableOrAdmin])
    def retirer_item(self, request, pk=None, item_id=None):
        salle = self.get_object()
        deleted, _ = SalleVenteItem.objects.filter(
            salle=salle, pk=item_id).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='analytics',
            permission_classes=[IsAnyRole])
    def analytics(self, request, pk=None):
        """NTCRM19 — nombre de vues, dernière vue, délai création→première
        vue (signal d'intérêt). Le suivi PAR ITEM n'est pas câblé
        (`SalleVenteVue` journalise la salle entière, pas item par item) —
        seul l'agrégat salle est exposé, conformément à la tâche NTCRM19
        (« si consultation par item trackée » — non le cas ici)."""
        from .selectors import salle_vente_analytics
        salle = self.get_object()
        return Response(salle_vente_analytics(salle))


class PartenaireViewSet(CompanyScopedModelViewSet):
    """Partenaires commerciaux (apporteurs/sous-revendeurs/installateurs,
    FG234/FG237) + couche certification NTMIG26.

    SOLMVP10/SOLMVP30b — cette route vivait sous ``/api/django/compta/
    partenaires/`` (shim ODX13) ; ``compta`` est désormais une coquille
    parquée SANS AUCUNE url (``core.parked``). ``crm.Partenaire`` n'a jamais
    quitté cette app (le modèle et ses données restent intacts) : il reprend
    ici nativement sa propre surface API, seule maison qu'il ait jamais eue.
    Le token d'accès est posé côté serveur, jamais lu du corps de requête.
    """
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    serializer_class = PartenaireSerializer
    queryset = Partenaire.objects.all()
    permission_classes = [IsResponsableOrAdmin]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['nom', 'date_creation']

    def perform_create(self, serializer):
        import secrets
        serializer.save(
            company=self.request.user.company,
            token_acces=secrets.token_urlsafe(32))

    @extend_schema(request=None, responses=sd.OBJ)
    @action(
        detail=True,
        methods=['post'],
        url_path='provisionner-acces',
        permission_classes=[IsAdminRole],
    )
    def provisionner_acces(self, request, pk=None):
        """NTPRT4 — Ouvre au partenaire un vrai compte utilisateur portail.

        RÉSERVÉ À L'ADMINISTRATEUR INTERNE (``IsAdminRole``), même garde que
        l'action jumelle NTPRT2 (``ComptePortailClientViewSet.
        provisionner_acces``) : ouvrir un accès externe à des données
        partenaire (soumissions, commissions) est une action
        d'administration. Le mot de passe temporaire n'est JAMAIS renvoyé
        ici : il part par email au partenaire (cf. ``apps.portail.services.
        provisionner_compte_partenaire``).
        """
        from apps.portail import services as portail_services

        partenaire = self.get_object()
        try:
            # ADOC124 — jumeau d'ADOC123 (vue client) : sans e-mail, le mot
            # de passe temporaire ne part nulle part ⇒ refus NOMMÉ, aucun
            # compte créé, aucun e-mail.
            user, cree = portail_services.provisionner_compte_partenaire(
                request.user.company, partenaire.id, exiger_email=True)
        except portail_services.ProvisionnementSansEmail as exc:
            return Response({'detail': str(exc)}, status=400)
        if user is None:
            return Response(
                {'detail': 'Partenaire inconnu pour cette société.'},
                status=400)
        return Response({
            'utilisateur_id': user.id,
            'username': user.username,
            'email': user.email,
            'actif': user.is_active,
            'cree': cree,
            'detail': (
                'Accès portail créé — mot de passe temporaire envoyé par '
                'email.' if cree else 'Accès portail déjà existant.'),
        })


class ApporteurViewSet(CompanyScopedModelViewSet):
    """NTCRM20 — Apporteurs d'affaires (registre B2B, CRUD interne)."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    serializer_class = ApporteurSerializer
    queryset = Apporteur.objects.select_related('company').all()

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class DealEnregistreViewSet(_PorteeEnfantsMixin, CompanyScopedModelViewSet):

    """NTCRM20 — Deals enregistrés par un apporteur (protection anti-poaching).

    ``approuver``/``rejeter`` : actions dédiées plutôt qu'un PATCH direct du
    statut — un rejet/expiration lève la protection immédiatement pour un
    futur enregistrement concurrent (`clean()` du modèle)."""
    # ACRM9 — lectures bornées à la portée (leads : lead ;

    # clients : —).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ('lead',)

    portee_clients = ()
    serializer_class = DealEnregistreSerializer
    queryset = DealEnregistre.objects.select_related(
        'company', 'apporteur', 'lead').all()

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'a_payer':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @extend_schema(request=None, responses=DealEnregistreSerializer)
    @action(detail=True, methods=['post'], url_path='approuver',
            permission_classes=[IsResponsableOrAdmin])
    def approuver(self, request, pk=None):
        deal = self.get_object()
        deal.statut = DealEnregistre.Statut.APPROUVE
        deal.save(update_fields=['statut'])
        return Response(DealEnregistreSerializer(deal).data)

    @extend_schema(request=None, responses=DealEnregistreSerializer)
    @action(detail=True, methods=['post'], url_path='rejeter',
            permission_classes=[IsResponsableOrAdmin])
    def rejeter(self, request, pk=None):
        deal = self.get_object()
        deal.statut = DealEnregistre.Statut.REJETE
        deal.save(update_fields=['statut'])
        return Response(DealEnregistreSerializer(deal).data)

    @extend_schema(responses=DealEnregistreSerializer(many=True))
    @action(detail=False, methods=['get'], url_path='a-payer')
    def a_payer(self, request):
        """NTCRM22 — liste des commissions À_PAYER, pour le comptable."""
        qs = self.get_queryset().filter(statut=DealEnregistre.Statut.A_PAYER)
        return Response(DealEnregistreSerializer(qs, many=True).data)


@extend_schema_view(list=extend_schema(parameters=[sd.param('actif', OpenApiTypes.BOOL)]))
class DefiViewSet(CompanyScopedModelViewSet):
    """NTCRM23 — Défis d'équipe (gamification) : CRUD + classement."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    serializer_class = DefiSerializer
    queryset = Defi.objects.select_related('company').all()

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'classement':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='classement',
            permission_classes=[IsAnyRole])
    def classement(self, request, pk=None):
        from .selectors import classement_defi
        defi = self.get_object()
        return Response(classement_defi(defi))


@extend_schema_view(list=extend_schema(parameters=[sd.param('appareil_id'), sd.P_LEAD, sd.param('point')]))
class VisiteExterneViewSet(viewsets.ReadOnlyModelViewSet):
    """T-TRACE — écran de revue des visites externes (lecture seule).

    Routes :
      GET /crm/visites-externes/                (filtre ?appareil_id=&?lead=&?point=)
      GET /crm/visites-externes/{id}/
      GET /crm/visites-externes/appareils/       (agrégat par appareil)

    Toujours scopé société (``TenantMixin``, via le queryset filtré ici) : un
    commercial ne voit que le traçage de SA société."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    # Attribut de classe requis par drf-spectacular pour typer `{id}` (le
    # runtime passe TOUJOURS par get_queryset, qui rescope par société).
    queryset = VisiteExterne.objects.all()
    serializer_class = VisiteExterneSerializer
    permission_classes = [IsAnyRole]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'duree_s']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = VisiteExterne.objects.select_related(
            'company', 'lead').filter(company=self.request.user.company)
        params = self.request.query_params
        appareil_id = params.get('appareil_id')
        if appareil_id:
            qs = qs.filter(appareil_id=appareil_id)
        lead_id = params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        point = params.get('point')
        if point:
            qs = qs.filter(point=point)
        return qs

    # Permission EXPLICITE sur l'@action (pattern d'or crm du cliquet
    # core.action_permission_scan : chaque @action porte sa garde).
    @extend_schema(parameters=[sd.param('appareil_id')], responses=sd.liste('CrmAppareilVisites'))
    @action(detail=False, methods=['get'], permission_classes=[IsAnyRole])
    def appareils(self, request):
        """Agrégat PAR APPAREIL : nb visites, durée totale, première/dernière
        visite, leads touchés, propositions ouvertes, statut équipe.

        Borné aux 200 appareils les plus RÉCEMMENT actifs (écran de revue, pas
        un export) — ``?appareil_id=`` cible un appareil précis sans cette
        limite."""
        from django.db.models import Count, Max, Min, Q, Sum

        from .visites import appareils_equipe_ids

        base = VisiteExterne.objects.filter(
            company=request.user.company).exclude(appareil_id='')
        appareil_id = request.query_params.get('appareil_id')
        if appareil_id:
            base = base.filter(appareil_id=appareil_id)

        agreges = (
            base.values('appareil_id')
            .annotate(
                visites=Count('id'),
                duree_totale_s=Sum('duree_s'),
                premiere=Min('created_at'),
                derniere=Max('created_at'),
                propositions=Count(
                    'id', filter=Q(point=VisiteExterne.Point.PROPOSITION)),
            )
            .order_by('-derniere')[:200]
        )
        equipe_ids = appareils_equipe_ids(request.user.company)

        resultats = []
        for ligne in agreges:
            aid = ligne['appareil_id']
            # Dédoublonné en PYTHON, jamais par `.distinct()` — même piège
            # `Meta.ordering` que `visites.historique_appareil`.
            leads = list(
                base.filter(appareil_id=aid)
                .exclude(lead__isnull=True)
                .order_by('lead_id')
                .values_list('lead_id', 'lead__nom')
                .distinct())
            vus, leads_touches = set(), []
            for lead_id, lead_nom in leads:
                if lead_id not in vus:
                    vus.add(lead_id)
                    leads_touches.append({'id': lead_id, 'nom': lead_nom or ''})
            resultats.append({
                'appareil_id': aid,
                'visites': ligne['visites'],
                'duree_totale_s': ligne['duree_totale_s'] or 0,
                'premiere': ligne['premiere'],
                'derniere': ligne['derniere'],
                'leads': leads_touches,
                'propositions': ligne['propositions'],
                'equipe': aid in equipe_ids,
            })
        return Response(resultats)


#: QJEQUIPE3 — forme d'un uuid v4, l'``appareil_id`` que le site pose dans le
#: ``localStorage`` du navigateur. Insensible à la casse. Une valeur hors forme
#: n'est PAS une erreur 400 : ce navigateur n'a peut-être jamais visité le
#: site public, on lui en attribue simplement un neuf.
_UUID_APPAREIL_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE)


#: Durée de vie du cookie ``tq_appareil`` posé par l'ERP : 2 ans. L'identité
#: d'un navigateur de l'équipe est durable, pas une session.
_COOKIES_EQUIPE_MAX_AGE = 730 * 24 * 3600


#: Longueur retenue du navigateur annoncé dans le libellé automatique — assez
#: pour reconnaître l'appareil dans la liste, jamais un user-agent entier.
_MAX_NAVIGATEUR = 80


class AppareilEquipeViewSet(mixins.ListModelMixin, mixins.CreateModelMixin,
                            mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """QJ-EQUIPE-2 — registre des appareils de l'équipe (exclusion permanente
    et rétroactive du traçage T-TRACE). Pas de retrieve/update : on liste, on
    ajoute, on retire — jamais de modification en place d'un enregistrement.

    Lecture ouverte à tout rôle authentifié de la société ; écriture réservée
    responsable/admin (marquer/démarquer un appareil équipe est une décision
    de gouvernance anti-fraude). EXCEPTION QJEQUIPE3 : ``ce-navigateur``, où
    l'utilisateur ne marque QUE son propre navigateur — voir son docstring."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    # Attribut de classe requis par drf-spectacular pour typer `{id}` (le
    # runtime passe TOUJOURS par get_queryset, qui rescope par société).
    queryset = AppareilEquipe.objects.all()
    serializer_class = AppareilEquipeSerializer

    def get_queryset(self):
        return AppareilEquipe.objects.filter(
            company=self.request.user.company).select_related('cree_par')

    def get_permissions(self):
        # AUD421 — TOUTE action qui déclare une `permission_classes` inline doit
        # être NOMMÉE ici : DRF appelle `get_permissions()` pour chaque requête,
        # y compris une @action, et un repli non délégué rendrait la déclaration
        # inline purement décorative (ici : plus restrictive, donc l'action
        # deviendrait inaccessible au commercial qu'elle vise).
        if self.action in ('list', 'ce_navigateur'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def create(self, request, *args, **kwargs):
        """Idempotent-friendly : (re)marquer un appareil déjà enregistré met à
        jour son libellé au lieu de lever une erreur d'unicité — un commercial
        qui reclique « ajouter » avec un libellé différent ne doit pas voir un
        400. L'idempotence vit dans `crm.services.enregistrer_appareil_equipe`
        (QJEQUIPE3), partagée avec `ce_navigateur` : un seul chemin d'écriture
        du registre, donc un seul comportement à garantir."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appareil, cree = enregistrer_appareil_equipe(
            request.user.company,
            serializer.validated_data.get('appareil_id', ''),
            libelle=serializer.validated_data.get('libelle') or '',
            user=request.user)
        donnees = self.get_serializer(appareil).data
        if not cree:
            return Response(donnees, status=status.HTTP_200_OK)
        return Response(donnees, status=status.HTTP_201_CREATED,
                        headers=self.get_success_headers(donnees))

    @extend_schema(
        request=inline_serializer('AppareilEquipeCeNavigateurRequest', {
            'appareil_id': serializers.CharField(required=False,
                                                 allow_blank=True),
            'navigateur': serializers.CharField(required=False,
                                                allow_blank=True),
        }),
        responses={200: AppareilEquipeSerializer},
    )
    @action(detail=False, methods=['post'], url_path='ce-navigateur',
            permission_classes=[IsAnyRole])
    def ce_navigateur(self, request):
        """QJEQUIPE3 — « reconnaître CE navigateur » en un clic, depuis l'ERP.

        Le piège que ça ferme : le registre serveur ne sert à rien tant que
        personne n'y inscrit son appareil, et l'``appareil_id`` — posé par le
        SITE dans son ``localStorage`` — n'est pas lisible depuis l'ERP. Cet
        endpoint fait les deux en un seul appel : il retient l'identifiant
        (celui envoyé par l'écran, sinon celui du cookie ``tq_appareil``,
        sinon un neuf), l'inscrit au registre de la société, et pose le cookie
        partagé ``tq_appareil`` sur le domaine du site — de sorte que la
        prochaine ouverture d'une proposition, qu'elle passe par le SSR
        (en-tête ``X-Appareil-Id``) ou directement par l'API (cookie), soit
        reconnue PAR LE REGISTRE, scopé société.

        JAMAIS le cookie ``tq_equipe`` (revue adversariale 16/09/2026) : ce
        signal court-circuite le gate public SANS regarder la société. Un
        utilisateur d'une AUTRE société de cet ERP peut être NOTRE prospect —
        avec ``tq_equipe`` posé à sa connexion, l'ouverture de son propre
        devis chez nous ne notifierait plus jamais personne. Le registre, lui,
        ne connaît l'appareil que pour SA société.

        OUVERT À TOUT RÔLE, délibérément : un commercial doit pouvoir dire
        « ce téléphone est le mien » sans passer par un responsable. Il ne
        marque que SON navigateur — jamais un appareil arbitraire d'un
        prospect : celui-là reste réservé à `create` (responsable/admin).

        Le libellé automatique n'est posé qu'à la CRÉATION et porte le nom de
        l'utilisateur connecté (jamais un prénom en dur) : un libellé déjà
        saisi à la main dans l'écran Visiteurs n'est jamais écrasé."""
        appareil_id = str(request.data.get('appareil_id') or '').strip()
        cookie = str(request.COOKIES.get(COOKIE_APPAREIL) or '').strip()
        # ACRM24 (C-ACRM-017) — l'identifiant du CORPS n'est retenu que s'il
        # est CELUI de ce navigateur (cookie ``tq_appareil``) ou n'a jamais
        # servi à une visite rattachée à un lead : sinon n'importe quel rôle
        # pourrait inscrire l'appareil d'un PROSPECT (lu dans « Visiteurs »)
        # comme appareil d'équipe — et ses ouvertures de devis ne
        # notifieraient plus personne. Refusé → un identifiant NEUF.
        if (_UUID_APPAREIL_RE.match(appareil_id) and appareil_id != cookie
                and VisiteExterne.objects.filter(
                    company=request.user.company, appareil_id=appareil_id,
                    lead__isnull=False).exists()):
            appareil_id = ''
        if not _UUID_APPAREIL_RE.match(appareil_id):
            appareil_id = cookie
        if not _UUID_APPAREIL_RE.match(appareil_id):
            appareil_id = str(uuid.uuid4())

        navigateur = str(
            request.data.get('navigateur') or '').strip()[:_MAX_NAVIGATEUR]
        deja_connu = self.get_queryset().filter(
            appareil_id=appareil_id).exists()
        libelle = ''
        if not deja_connu:
            qui = (request.user.get_full_name() or '').strip() \
                or request.user.username
            libelle = f"{qui} — {navigateur or 'navigateur'}"

        appareil, _cree = enregistrer_appareil_equipe(
            request.user.company, appareil_id, libelle=libelle,
            user=request.user)
        if appareil is None:
            # Compte sans société (jamais un 500 pour un appel de fond).
            return Response(
                {'detail': 'Aucune société rattachée à ce compte : '
                           'appareil non enregistré.'},
                status=status.HTTP_400_BAD_REQUEST)

        reponse = Response(self.get_serializer(appareil).data,
                           status=status.HTTP_200_OK)
        # `secure` : même règle que les cookies JWT d'`authentication.views`
        # (`not settings.DEBUG`) — derrière Caddy→nginx, `X-Forwarded-Proto`
        # porte le schéma interne (http), donc `request.is_secure()` seul
        # laisserait tomber le drapeau en production.
        from django.conf import settings
        commun = {
            'max_age': _COOKIES_EQUIPE_MAX_AGE,
            'domain': domaine_cookies_equipe(request),
            'path': '/',
            'secure': request.is_secure() or not settings.DEBUG,
            'samesite': 'Lax',
        }
        # `tq_appareil` lisible par JavaScript (httponly=False) : le site le
        # lit pour aligner son `localStorage` et le relayer en en-tête
        # `X-Appareil-Id` sur ses fetchs SSR. `tq_equipe` n'est PAS posé ici —
        # voir le docstring (signal non scopé société).
        reponse.set_cookie(COOKIE_APPAREIL, appareil.appareil_id,
                           httponly=False, **commun)
        return reponse


#: ACRM3 — les LECTURES de l'annuaire clients (en plus de ``READ_ACTIONS``) :
#: elles exigent ``crm_voir`` ou le code de lecture d'un module consommateur.
CLIENT_LECTURE_ACTIONS = [
    'documents', 'search', 'dormants', 'engagement', 'engagement_bulk',
    'mon_portefeuille',
]


def _voit_le_crm(user):
    """ACRM3 — vrai si ``user`` lit le CRM (``crm_voir``), même règle que
    ``HasPermissionOrLegacy('crm_voir')`` : superuser, rôle fin portant le
    code, ou compte historique responsable sans rôle fin."""
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'role', None):
        return user.has_erp_permission('crm_voir')
    return bool(getattr(user, 'is_responsable', False))


class ClientViewSet(CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    # ARC2 — pilote : base transverse unique (TenantMixin + ModelViewSet). Le
    # get_queryset (portée de visibilité) et perform_create (company +
    # created_by forcés serveur) SURCHARGENT la base : réponses inchangées.
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'nom', 'prenom', 'email', 'telephone',
        'ice', 'if_fiscal', 'rc', 'cin',
    ]
    ordering_fields = ['nom', 'date_creation']
    ordering = ['-date_creation']

    def get_queryset(self):
        # Portée de visibilité (Feature F) : un rôle restreint ne voit que les
        # clients rattachés à ses documents/leads visibles. 'all' → inchangé.
        # APRF17 (C-APRF-006) — ce que ``ClientSerializer`` lit PAR LIGNE
        # (créateur, nombre de devis, totaux facturé/payé : lignes, paiements
        # et ventilations d'avances) est chargé EN LOT : la liste coûte le
        # même nombre de requêtes à 5 et à 15 clients. Chemins en chaînes —
        # aucun import des modèles ventes/facturation.
        return (scope_client_queryset(super().get_queryset(),
                                      self.request.user)
                .select_related('created_by')
                .prefetch_related(
                    'devis', 'factures__lignes', 'factures__paiements',
                    'factures__affectations_paiement__paiement'))

    def perform_create(self, serializer):
        # Traçabilité (L16) : société ET créateur forcés côté serveur — jamais
        # acceptés du corps de la requête.
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
        )

    def perform_update(self, serializer):
        # NTI18N49 — snapshot de la langue documentaire AVANT écriture, pour
        # journaliser le changement dans le chatter (lead rattaché) une fois
        # la sauvegarde faite. Aucun autre comportement de perform_update
        # n'est touché (comportement DRF par défaut préservé).
        old_langue = serializer.instance.langue_document
        super().perform_update(serializer)
        new_client = serializer.instance
        if new_client.langue_document != old_langue:
            activity.log_client_langue_document_change(
                new_client, self.request.user,
                old_value=old_langue, new_value=new_client.langue_document,
            )
            # CRM-LANGUE-EVENT — comble le seam NTI18N43 (jusqu'ici sans
            # émetteur) : une intégration tierce (webhook publicapi
            # `langue_changed`) doit savoir que ce client a changé de langue
            # documentaire. `emettre_langue_changed` porte déjà sa propre
            # garde « ça a vraiment changé » — le if ci-dessus la double,
            # sans risque (idempotent).
            from core.events import emettre_langue_changed
            emettre_langue_changed(
                new_client.company,
                ancienne_langue=old_langue,
                nouvelle_langue=new_client.langue_document,
                client_id=new_client.pk,
                user=self.request.user,
            )

    def get_permissions(self):
        # QC1 — `search` est une LECTURE scopée société (autocomplete des
        # données propres) : ouverte à tout rôle authentifié, comme `list`.
        # Ce get_permissions prime sur le permission_classes de l'action —
        # NTCRM14/15/16/29 : `dormants`/`relancer_dormance`/`engagement`/
        # `engagement_bulk`/`mon_portefeuille` sont des LECTURES (ou une
        # relance légère) déjà ouvertes via `permission_classes=[IsAnyRole]`
        # sur leur @action, mais get_permissions() PRIME dessus — sans les
        # lister ICI elles retombaient sur le défaut `IsAdminRole` (403 pour
        # tout rôle Commercial/Responsable non-admin).
        #
        # ACRM3 (C-ACRM-001) — « tout rôle authentifié » laissait le
        # Commercial terrain (app Visites seule) et l'Admin RH lire
        # l'annuaire clients et chercher des leads avec leur téléphone : les
        # LECTURES exigent désormais un code fin de lecture — ``crm_voir``,
        # ou celui d'un module qui CONSOMME l'annuaire clients (``sav_voir``
        # pour le SAV, ``installation_voir`` pour les chantiers) — et la
        # relance (une écriture au chatter du lead) ``crm_modifier``.
        # ``OrLegacy`` préserve les comptes historiques sans rôle fin.
        if self.action in READ_ACTIONS + CLIENT_LECTURE_ACTIONS:
            return [(HasPermissionOrLegacy('crm_voir')
                     | HasPermissionOrLegacy('sav_voir')
                     | HasPermissionOrLegacy('installation_voir'))()]
        elif self.action == 'relancer_dormance':
            return [HasPermissionOrLegacy('crm_modifier')()]
        elif self.action == 'export_xlsx':
            # Export : garde propre (ASEC50, code ``crm_export``) — hors
            # périmètre d'ACRM3.
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['dupliquer']:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        # ACRM21 (C-ACRM-014) — les autres @action (consolidation,
        # data-export, anonymize) sont gardées par CE QUE LEUR
        # DÉCORATEUR DÉCLARE (patron ``declared_action_permissions``) : le
        # repli brut ``IsAdminRole`` refusait au Commercial le bloc « CA
        # groupe » (déclaré ``IsAnyRole``) et l'export RGPD (déclaré
        # ``IsResponsableOrAdmin``).
        declared = declared_action_permissions(self)
        if declared is not None:
            return declared
        return [IsAdminRole()]

    @extend_schema(request=None, responses={201: ClientSerializer})
    @action(detail=True, methods=['post'], url_path='dupliquer',
            permission_classes=[IsResponsableOrAdmin])
    def dupliquer(self, request, pk=None):
        """NTUX13 — Duplique cette fiche client (suffixe « (copie) », email/
        ICE vidés — voir ``services.dupliquer_client``)."""
        source = self.get_object()
        from .clients_identite import dupliquer_client
        copie = dupliquer_client(source, user=request.user)
        return Response(
            ClientSerializer(copie, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @extend_schema(request=sd.corps('CrmClientsExportRequest', ids=serializers.ListField(child=serializers.IntegerField(), required=False)), responses=sd.EXPORT_XLSX)
    @action(detail=False, methods=['post'], url_path='export-xlsx',
            permission_classes=[IsAnyRole])
    def export_xlsx(self, request):
        """Exporte une sélection de clients en .xlsx (société courante)."""
        from .exports import export_clients_xlsx
        ids = request.data.get('ids') or []
        qs = self.get_queryset()
        if ids:
            qs = qs.filter(id__in=ids)
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.EXPORT, detail='Export clients (.xlsx)')
        # ACRM4 — sans ``client_pii_voir`` : export sans colonnes PII.
        from .serializers import pii_masquee_pour
        return export_clients_xlsx(
            qs.order_by('nom'), masquer_pii=pii_masquee_pour(request.user))

    @extend_schema(parameters=[sd.P_Q], responses=sd.corps('CrmClientSearch', results=serializers.ListField(child=serializers.DictField())))
    @action(detail=False, methods=['get'], url_path='search',
            permission_classes=[IsAnyRole])
    def search(self, request):
        """QC1 — Autocomplete entreprise sur les DONNÉES PROPRES de la société
        (clients + fournisseurs + leads), recherche floue sur nom/ICE, scopée
        société côté serveur. Passe par le provider seam ``search_companies``
        (QC2 pourra brancher un registre licencié derrière un flag). LECTURE
        SEULE — ne crée jamais rien.

        Paramètre : ``q`` (texte). Renvoie ``{results: [{source, id, nom, ice,
        if_fiscal, rc, adresse, telephone, email}, …]}`` (≤ 12)."""
        from .company_search import search_companies
        q = (request.query_params.get('q') or '').strip()
        # CRX16 — la portée de visibilité du rôle s'applique à l'autocomplete
        # comme à la liste (``scope_client_queryset`` côté clients) : sans
        # elle, un rôle restreint lisait ici les coordonnées d'enregistrements
        # que sa propre liste lui masque.
        results = (search_companies(request.user.company, q,
                                    user=request.user)
                   if q else [])
        # ACRM3 — un module consommateur (SAV, chantiers) cherche des
        # CLIENTS : sans ``crm_voir``, aucun lead (ni son téléphone) ne sort
        # de l'autocomplete.
        if not _voit_le_crm(request.user):
            results = [r for r in results if r.get('source') != 'lead']
        return Response({'results': results})

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='documents',
            permission_classes=[IsAnyRole])
    def documents(self, request, pk=None):
        """Panneau détail (L4) : devis, factures et chantiers liés à un client.

        Lecture seule, bornée à la société courante (get_object passe par la
        portée TenantMixin + visibilité). Référence / statut / total uniquement
        — aucun prix d'achat ni marge n'apparaît (sortie client-facing)."""
        client = self.get_object()

        def _statut(obj):
            try:
                return obj.get_statut_display()
            except Exception:
                return getattr(obj, 'statut', None)

        def _date(obj):
            # Devis → date_creation ; Facture → date_emission.
            d = getattr(obj, 'date_creation', None) \
                or getattr(obj, 'date_emission', None)
            return d.isoformat() if d else None

        devis = [
            {
                'id': d.id,
                'reference': d.reference,
                'statut': _statut(d),
                'total_ttc': str(d.total_ttc),
                'date': _date(d),
            }
            for d in client.devis.all().order_by('-date_creation')
        ]
        factures = [
            {
                'id': f.id,
                'reference': f.reference,
                'statut': _statut(f),
                # VX245(c) — clé RAW (additive, jamais lue par les autres
                # consommateurs de `statut`) : « Relancer par WhatsApp »
                # n'apparaît QUE sur une facture réellement en retard, sans
                # dépendre du libellé FR affiché (fragile/localisé).
                'statut_key': f.statut,
                'total_ttc': str(f.total_ttc),
                'date': _date(f),
            }
            for f in client.factures.all().order_by('-date_emission')
        ]
        chantiers = [
            {
                'id': i.id,
                'reference': i.reference,
                'statut': _statut(i),
            }
            for i in client.installations.all().order_by('-id')
        ]
        return Response({
            'devis': devis,
            'factures': factures,
            'chantiers': chantiers,
        })

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='consolidation',
            permission_classes=[IsAnyRole])
    def consolidation(self, request, pk=None):
        """XSAL9 — Rollup CA groupe (société mère + toutes ses filiales,
        récursif) — voir ``selectors.consolidation_client``. Lecture seule,
        bornée à la société courante (get_object passe par TenantMixin)."""
        from .selectors import consolidation_client
        client = self.get_object()
        rollup = consolidation_client(client)
        return Response({
            'filiales': [
                {'id': f.id, 'nom': str(f), 'parent_id': f.parent_id}
                for f in rollup['filiales']
            ],
            'ca_devis_total': str(rollup['ca_devis_total']),
            'ca_factures_total': str(rollup['ca_factures_total']),
            'nb_devis_total': rollup['nb_devis_total'],
            'nb_factures_total': rollup['nb_factures_total'],
        })

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='data-export',
            permission_classes=[IsResponsableOrAdmin])
    def data_export(self, request, pk=None):
        """FG26 — bundle d'accès du sujet (RGPD) : toutes les données
        personnelles détenues sur un client + la liste de ses documents liés.

        Lecture seule, company-scopée (get_object passe par TenantMixin +
        visibilité). Destiné à satisfaire une demande d'accès du sujet."""
        client = self.get_object()
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.EXPORT, instance=client,
               detail='Export RGPD (accès du sujet)')
        identite = {
            'id': client.id,
            'nom': client.nom, 'prenom': client.prenom,
            'email': client.email, 'telephone': client.telephone,
            'adresse': client.adresse, 'type_client': client.type_client,
            'cin': client.cin, 'ice': client.ice,
            'if_fiscal': client.if_fiscal, 'rc': client.rc,
            'custom_data': client.custom_data,
            'date_creation': client.date_creation.isoformat()
            if client.date_creation else None,
            'is_anonymized': client.is_anonymized,
        }
        # ACRM53 — même règle que ``ClientSerializer`` : un rôle sans
        # ``client_pii_voir`` reçoit l'export sans téléphone/email/adresse.
        from .serializers import masquer_pii_dict
        masquer_pii_dict(identite, request.user)
        documents = {
            'devis': [
                {'reference': d.reference, 'statut': getattr(d, 'statut', None),
                 'total_ttc': str(d.total_ttc)}
                for d in client.devis.all().order_by('-date_creation')
            ],
            'factures': [
                {'reference': f.reference, 'statut': getattr(f, 'statut', None),
                 'total_ttc': str(f.total_ttc)}
                for f in client.factures.all().order_by('-date_emission')
            ],
        }
        return Response({'identite': identite, 'documents': documents})

    @extend_schema(request=None, responses=ClientSerializer)
    @action(detail=True, methods=['post'], url_path='anonymize',
            permission_classes=[IsAdminRole])
    def anonymize(self, request, pk=None):
        """FG26 — droit à l'effacement : scrube les PII du client tout en
        PRÉSERVANT l'intégrité comptable (devis/factures conservés, liés à une
        identité neutralisée). Admin uniquement, irréversible, idempotent."""
        from django.utils import timezone
        client = self.get_object()
        if client.is_anonymized:
            return Response(
                {'detail': 'Ce client est déjà anonymisé.'},
                status=status.HTTP_400_BAD_REQUEST)
        client.nom = f'Client anonymisé #{client.id}'
        client.prenom = None
        client.email = None
        client.telephone = None
        client.adresse = None
        client.cin = None
        client.ice = None
        client.if_fiscal = None
        client.rc = None
        client.custom_data = None
        client.is_anonymized = True
        client.anonymized_at = timezone.now()
        client.save()
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.UPDATE, instance=client,
               detail='Anonymisation RGPD (effacement des données personnelles)')
        return Response(ClientSerializer(
            client, context={'request': request}).data)

    def destroy(self, request, *args, **kwargs):
        # Un client avec des devis est PROTÉGÉ (pas de cascade) : message
        # français clair au lieu d'un 500 silencieux.
        from django.db.models import ProtectedError
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': "Ce client a des devis liés — supprimez ou "
                           "réassignez ses devis d'abord."},
                status=status.HTTP_409_CONFLICT,
            )

    @extend_schema(parameters=[sd.param('seuil', OpenApiTypes.INT)], responses=sd.OBJ)
    @action(detail=False, methods=['get'], url_path='dormants',
            permission_classes=[IsAnyRole])
    def dormants(self, request):
        """NTCRM14 — Comptes dormants : au moins un devis/facture passé mais
        aucune activité (devis/facture/LeadActivity/PointContact) depuis
        `?seuil=` jours (défaut 90). Distinct de `segments?segment=dormants`
        (seuil fixe 18 mois, sans LeadActivity/PointContact) — celui-ci
        alimente aussi la commande de notification `detecter_comptes_dormants`.
        """
        from .selectors import comptes_dormants
        try:
            seuil = int(request.query_params.get('seuil', 90))
        except (TypeError, ValueError):
            seuil = 90
        company = request.user.company if request.user.company_id else None
        # ALEA27 — bornée par la portée du viewset (société + équipe).
        entries = comptes_dormants(
            company, seuil_jours=seuil, clients=self.get_queryset())
        results = [{
            'id': e['client'].id,
            'nom': str(e['client']),
            'derniere_activite': (
                e['derniere_activite'].isoformat()
                if e['derniere_activite'] else None),
            'jours_inactivite': e['jours_inactivite'],
        } for e in entries]
        return Response({'seuil': seuil, 'count': len(results), 'results': results})

    @extend_schema(request=None, responses={201: LeadActivitySerializer})
    @action(detail=True, methods=['post'], url_path='relancer-dormance',
            permission_classes=[IsAnyRole])
    def relancer_dormance(self, request, pk=None):
        """NTCRM15 — Bouton one-click « créer une activité de relance » du
        widget Comptes dormants : journalise une note sur le lead le plus
        récent lié à ce client. 404 si le client n'a aucun lead (rien à
        relancer via le chatter — cas rare, clients importés sans lead)."""
        from . import activity
        from .models import Lead
        client = self.get_object()
        # ACRM7 — le lead relancé est choisi parmi ceux de la PORTÉE de
        # l'appelant : jamais une note chez un collègue hors portée.
        lead = (scope_queryset(
                    Lead.objects.filter(company=client.company,
                                        client=client),
                    request.user, ['owner'])
                .order_by('-date_creation').first())
        if lead is None:
            return Response(
                {'detail': "Aucun lead lié à ce client — relance impossible."},
                status=status.HTTP_404_NOT_FOUND)
        act = activity.log_note(
            lead, request.user,
            f'Relance dormance — compte {client} réactivé manuellement.')
        return Response(LeadActivitySerializer(
            act, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='engagement',
            permission_classes=[IsAnyRole])
    def engagement(self, request, pk=None):
        """NTCRM16 — Score d'engagement multi-signaux (0-100) de CE client."""
        from .engagement import engagement_for_client
        client = self.get_object()
        return Response(engagement_for_client(client))

    @extend_schema(responses=sd.liste('CrmEngagementClient'))
    @action(detail=False, methods=['get'], url_path='engagement-bulk',
            permission_classes=[IsAnyRole])
    def engagement_bulk(self, request):
        """NTCRM16 — Score d'engagement multi-signaux pour la liste (bulk)."""
        from .engagement import engagement_bulk as _engagement_bulk
        qs = self.get_queryset()
        return Response(_engagement_bulk(list(qs)))

    @extend_schema(responses=sd.OBJ)
    @action(detail=False, methods=['get'], url_path='mon-portefeuille',
            permission_classes=[IsAnyRole])
    def mon_portefeuille(self, request):
        """NTCRM29 — Widget « portefeuille de comptes » : les comptes du
        commercial CONNECTÉ (owner via leads liés), triés par score
        d'engagement croissant (les plus froids en premier). Jamais scopé
        depuis la query string — toujours ``request.user``/``request.user.
        company``."""
        from .selectors import portefeuille_commercial
        results = portefeuille_commercial(request.user.company, request.user)
        return Response({'count': len(results), 'results': results})


class LeadClientsActionsMixin:
    """SPL78 — actions « clients » de LeadViewSet (conversion en client,
    analytics de salle de vente, rapprochement client), déplacées de
    ``views.py`` à corps inchangés.

    ``get_permissions`` coopératif (patron SPL75) : il ne garde QUE ses
    actions, sinon ``super()`` (la chaîne finit sur ``_RepliIsAdminMixin``).
    """

    def get_permissions(self):
        if self.action in ('client_match', 'salle_vente_analytics_view'):
            # VTA4 — lectures de la fiche : code fin ``crm_voir``.
            return [HasPermissionOrLegacy('crm_voir')()]
        if self.action == 'convertir_client':
            # VX199 — conversion de lead : permission ERP FINE (crm_modifier).
            return [HasPermissionOrLegacy('crm_modifier')()]
        return super().get_permissions()

    @extend_schema(request=sd.corps('CrmConvertirClientRequest', mode=serializers.ChoiceField(choices=['nouveau', 'lier', 'aucun']), client_id=serializers.IntegerField(required=False)), responses=sd.OBJ)
    @action(detail=True, methods=['post'], url_path='convertir-client',
            permission_classes=[HasPermissionOrLegacy('crm_modifier')])
    def convertir_client(self, request, pk=None):
        """ZSAL4 — assistant de conversion EXPLICITE lead → client (body
        {mode: nouveau|lier|aucun, client_id?}). Journalisé dans le chatter."""
        lead = self.get_object()
        mode = (request.data.get('mode') or '').strip()
        client_id = request.data.get('client_id')
        from .clients_identite import ClientIntrouvable, convertir_lead_en_client
        try:
            # ACRM7 — le client à lier est cherché dans la PORTÉE de
            # l'appelant (même règle que ``ClientViewSet.get_queryset``).
            client = convertir_lead_en_client(
                lead=lead, user=request.user, mode=mode, client_id=client_id,
                clients=scope_client_queryset(
                    Client.objects.filter(company=lead.company),
                    request.user))
        except ClientIntrouvable as exc:
            # LEVÉ, pas renvoyé (même motif que `placement_cadences`) : le
            # contrat de la vue reste la forme de son 200 ; DRF rend le 400
            # ``{client_id: [...]}``.
            raise DRFValidationError({'client_id': [str(exc)]})
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'mode': mode,
            # ACRM4 — contexte transmis : la PII du client suit la règle
            # unique du masquage (``client_pii_voir``).
            'client': (ClientSerializer(
                client, context={'request': request}).data
                if client else None),
        })

    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='salle-vente-analytics',
            permission_classes=[IsAnyRole])
    def salle_vente_analytics_view(self, request, pk=None):
        """NTCRM19 — résumé de consultation de la salle de vente la plus
        récente de ce lead, pour le widget « le client a consulté N fois,
        dernière fois <date> » de la fiche lead. `null` si aucune salle."""
        from .selectors import salle_vente_summary_for_lead
        lead = self.get_object()
        summary = salle_vente_summary_for_lead(request.user.company, lead.pk)
        return Response(summary)

    # ── FG38 — Correspondance Lead↔Client (doublon retour client) ────────────
    @extend_schema(responses=sd.OBJ)
    @action(detail=True, methods=['get'], url_path='client-match',
            permission_classes=[IsAnyRole])
    def client_match(self, request, pk=None):
        """Cherche si le lead correspond à un Client existant de la société.

        Normalise téléphone et email, puis cherche dans Client (pas dans Lead).
        Retourne [] si aucune correspondance ou {id, nom, nb_devis, nb_chantiers}
        pour chaque client correspondant.
        """
        lead = self.get_object()
        company = request.user.company
        from .models import Client as ClientModel
        # 25/08/2026 — LANE NUMÉROS INTERNATIONAUX : bascule depuis
        # `apps.ventes.utils.phone.normalize_ma_phone` (forçait un préfixe
        # '212', ne rapprochait jamais un lead à numéro étranger) vers la
        # même clé QW10 que `selectors.find_client_by_phone` juste au-dessus.
        from .leads_doublons import normalize_phone

        conditions = []
        phone_norm = normalize_phone(lead.telephone or '') if lead.telephone else None
        email_norm = (lead.email or '').strip().lower() or None
        if phone_norm:
            conditions.append(
                Lead._meta.model.objects.none()  # placeholder — on fait direct
            )

        # Recherche directe sur Client
        # ALEA27 (jumeau) — bornée par la portée client de l'utilisateur
        # (même règle que ``ClientViewSet.get_queryset``) : un client hors
        # portée n'est jamais rendu.
        client_qs = scope_client_queryset(
            ClientModel.objects.filter(company=company), request.user)
        found = []
        pks_seen = set()
        if phone_norm:
            for c in client_qs:
                norm = normalize_phone(c.telephone or '') if c.telephone else None
                if norm and norm == phone_norm and c.pk not in pks_seen:
                    found.append(c)
                    pks_seen.add(c.pk)
        if email_norm:
            for c in client_qs.filter(email__iexact=email_norm):
                if c.pk not in pks_seen:
                    found.append(c)
                    pks_seen.add(c.pk)

        result = []
        for c in found:
            # ACRM4 — PII vidée pour un rôle sans ``client_pii_voir``.
            result.append(masquer_pii_dict({
                'id': c.id,
                'nom': f"{c.nom} {c.prenom or ''}".strip(),
                'email': c.email,
                'telephone': c.telephone,
                'nb_devis': c.devis.count(),
                'nb_chantiers': c.installations.count() if hasattr(c, 'installations') else 0,
            }, request.user))
        return Response(result)


@extend_schema(responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def equipes_statistiques(request):
    """ZSAL3 — Tableau de bord « Mes équipes » : pipeline ouvert/pondéré,
    activités en retard, CA signé du mois vs cible, par équipe commerciale
    active de la société courante."""
    user = request.user
    if not user.company_id:
        if not user.is_superuser:
            return Response({'equipes': []})
        return Response({'equipes': []})
    from .selectors import stats_equipe
    return Response({'equipes': stats_equipe(user.company)})


class ParrainageViewSet(_PorteeEnfantsMixin, CompanyScopedModelViewSet):

    """N98 — parrainages. Lecture tout rôle, écriture responsable/admin.

    À la création, la récompense est pré-remplie depuis Paramètres
    (referral_reward) quand elle n'est pas fournie. ?stats=1 ajoute un petit
    tableau de bord (totaux par statut + récompenses)."""
    # ACRM9 — lectures bornées à la portée (leads : filleul_lead ;

    # clients : parrain, filleul_client).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ('filleul_lead',)

    portee_clients = ('parrain', 'filleul_client')
    queryset = Parrainage.objects.select_related(
        'parrain', 'filleul_lead', 'filleul_client').all()
    serializer_class = ParrainageSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['stats']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        company = self.request.user.company
        extra = {'created_by': self.request.user}
        if serializer.validated_data.get('recompense') in (None, ''):
            try:
                from apps.parametres.models import CompanyProfile
                prof = CompanyProfile.get(company)
                if prof and prof.referral_reward is not None:
                    extra['recompense'] = prof.referral_reward
            except Exception:
                pass
        serializer.save(**extra)

    @extend_schema(responses=sd.OBJ)
    @action(detail=False, methods=['get'], url_path='stats',
            permission_classes=[IsAnyRole])
    def stats(self, request):
        """Tableau de bord parrainage : compte par statut + récompenses."""
        from decimal import Decimal
        qs = self.get_queryset()
        total = qs.count()
        par_statut = {}
        rec_total = Decimal('0')
        rec_versee = Decimal('0')
        for p in qs:
            par_statut[p.statut] = par_statut.get(p.statut, 0) + 1
            if p.recompense:
                rec_total += p.recompense
                if p.statut == Parrainage.Statut.RECOMPENSE_VERSEE:
                    rec_versee += p.recompense
        return Response({
            'total': total,
            'par_statut': par_statut,
            'recompenses_total': str(rec_total),
            'recompenses_versees': str(rec_versee),
        })


class PlanActiviteViewSet(CompanyScopedModelViewSet):
    """Plans d'activité (checklists de tâches commerciales) : lecture tout
    rôle, écriture responsable/admin. Société forcée côté serveur."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = PlanActivite.objects.prefetch_related(
        'etapes', 'etapes__activity_type').all()
    serializer_class = PlanActiviteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class EquipeCommercialeViewSet(CompanyScopedModelViewSet):
    """ZSAL3 — Équipes commerciales (admin CRUD, Paramètres → CRM). Lecture
    tout rôle (le dashboard « Mes équipes » y référence des noms), écriture
    ADMIN. Société forcée côté serveur (TenantMixin).

    ACRM26 (C-ACRM-021) — l'écriture (création, modification dont
    ``responsable``, suppression) passe au palier ADMIN : une équipe pilote
    une PORTÉE (le rollup du forecast, les cartes « Mes équipes ») — un
    Commercial pouvait se nommer responsable d'une équipe et lire son
    pipeline."""
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = EquipeCommerciale.objects.prefetch_related('membres').all()
    serializer_class = EquipeCommercialeSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]


@extend_schema_view(list=extend_schema(parameters=[sd.param('metric'), sd.param('year', OpenApiTypes.INT), sd.param('period_type'), sd.param('owner', description='Identifiant ou « null ».')]))
class ObjectifCommercialViewSet(CompanyScopedModelViewSet):
    """CRUD objectifs commerciaux + endpoint d'atteinte (réalisé vs cible).

    Routes :
      GET/POST  /crm/objectifs/
      GET/PATCH /crm/objectifs/{id}/
      DELETE    /crm/objectifs/{id}/
      GET       /crm/objectifs/attainment/?year=&metric=&period_type=&owner=
      GET       /crm/objectifs/{id}/attainment/
    """
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = ObjectifCommercial.objects.all()
    serializer_class = ObjectifCommercialSerializer

    def get_queryset(self):
        qs = super().get_queryset().select_related('owner')
        # Filtres optionnels.
        metric = self.request.query_params.get('metric')
        if metric:
            qs = qs.filter(metric=metric)
        year = self.request.query_params.get('year')
        if year:
            qs = qs.filter(period_year=year)
        period_type = self.request.query_params.get('period_type')
        if period_type:
            qs = qs.filter(period_type=period_type)
        owner = self.request.query_params.get('owner')
        if owner == 'null':
            qs = qs.filter(owner__isnull=True)
        elif owner:
            qs = qs.filter(owner_id=owner)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
        )

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['attainment', 'attainment_list']:
            return [IsAnyRole()]
        return [IsAdminRole()]

    @extend_schema(responses=ObjectifAttainmentSerializer)
    @action(detail=True, methods=['get'], url_path='attainment',
            permission_classes=[IsAnyRole])
    def attainment(self, request, pk=None):
        """Réalisé vs cible pour un objectif unique."""
        from .selectors import compute_attainment
        obj = self.get_object()
        data = compute_attainment(obj)
        payload = {
            'id': obj.pk,
            'metric': obj.metric,
            'metric_display': obj.get_metric_display(),
            'period_type': obj.period_type,
            'period_year': obj.period_year,
            'period_month': obj.period_month,
            'period_quarter': obj.period_quarter,
            'cible': obj.cible,
            'owner': obj.owner_id,
            'owner_nom': getattr(obj.owner, 'username', None),
            **data,
        }
        s = ObjectifAttainmentSerializer(payload)
        return Response(s.data)

    # YAPIC6 — sans cette annotation le schéma documente un OBJET unique alors
    # que l'action renvoie une LISTE (drf-spectacular déduit le détail depuis
    # le serializer). Annotation de schéma uniquement : aucun effet runtime.
    @extend_schema(
        parameters=[
            sd.param('metric'), sd.param('year', OpenApiTypes.INT),
            sd.param('period_type'),
            sd.param('owner', description='Identifiant ou « null ».'),
        ],
        responses=ObjectifAttainmentSerializer(many=True),
    )
    @action(detail=False, methods=['get'], url_path='attainment',
            permission_classes=[IsAnyRole])
    def attainment_list(self, request):
        """Réalisé vs cible pour tous les objectifs du filtre courant."""
        from .selectors import compute_attainment
        qs = self.get_queryset()
        result = []
        for obj in qs:
            data = compute_attainment(obj)
            result.append({
                'id': obj.pk,
                'metric': obj.metric,
                'metric_display': obj.get_metric_display(),
                'period_type': obj.period_type,
                'period_year': obj.period_year,
                'period_month': obj.period_month,
                'period_quarter': obj.period_quarter,
                'cible': obj.cible,
                'owner': obj.owner_id,
                'owner_nom': getattr(obj.owner, 'username', None),
                **data,
            })
        s = ObjectifAttainmentSerializer(result, many=True)
        return Response(s.data)


@extend_schema_view(list=extend_schema(parameters=[sd.P_LEAD]))
class ConcurrentPerteViewSet(_PorteeEnfantsMixin, CompanyScopedModelViewSet):

    """FG242 — concurrent gagnant + prix saisis sur un lead perdu.

    Intelligence concurrentielle : sur un lead PERDU (drapeau ``Lead.perdu`` —
    « Perdu » est un lost-flag, pas une étape STAGES.py), on capture qui nous a
    battu et à quel prix.

    Routes :
      GET/POST  /crm/concurrents-perte/        (filtre ?lead=<id>)
      GET/PATCH /crm/concurrents-perte/{id}/
      DELETE    /crm/concurrents-perte/{id}/

    Lecture tout rôle, écriture responsable/admin. Toujours scopé par société
    (TenantMixin) : la société et ``saisi_par`` sont posés côté serveur depuis
    l'utilisateur actif — jamais lus du corps de requête (multi-tenant).
    """
    # ACRM9 — lectures bornées à la portée (leads : lead ;

    # clients : —).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ('lead',)

    portee_clients = ()
    serializer_class = ConcurrentPerteSerializer
    queryset = ConcurrentPerte.objects.select_related(
        'lead', 'company', 'saisi_par').all()
    filterset_fields = ['lead']
    ordering_fields = ['saisi_le', 'concurrent_prix']
    ordering = ['-saisi_le']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        lead_id = self.request.query_params.get('lead')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def perform_create(self, serializer):
        """Société et saisi_par toujours posés côté serveur ; trace chatter."""
        obj = serializer.save(
            company=self.request.user.company,
            saisi_par=self.request.user,
        )
        # Trace l'info dans le chatter du lead (best-effort, ne casse jamais
        # la création si le log échoue).
        try:
            from . import activity
            prix = ''
            if obj.concurrent_prix is not None:
                prix = f' à {obj.concurrent_prix} {obj.devise or ""}'.rstrip()
            activity.log_note(
                obj.lead, self.request.user,
                f"Concurrent gagnant saisi : {obj.concurrent_nom}{prix}.",
            )
        except Exception:
            pass


@extend_schema_view(list=extend_schema(parameters=[sd.P_OWNER, sd.param('categorie'), sd.param('periode', description='AAAA-MM')]))
class ForecastEntryViewSet(_PorteeEnfantsMixin, CompanyScopedModelViewSet):

    """CRUD des catégorisations forecast (commit/best-case/pipeline/omis).

    Routes :
      GET/POST  /crm/forecast-entries/?owner=&categorie=&periode=
      GET/PATCH /crm/forecast-entries/{id}/
    La réponse liste inclut ``totaux_par_categorie`` (somme des montants
    effectifs des lignes filtrées, par catégorie)."""
    # ACRM9 — lectures bornées à la portée (leads : lead ;

    # clients : —).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ('lead',)

    portee_clients = ()
    queryset = ForecastEntry.objects.select_related('lead', 'lead__owner')
    serializer_class = ForecastEntrySerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        owner = self.request.query_params.get('owner')
        if owner:
            qs = qs.filter(lead__owner_id=owner)
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        periode = self.request.query_params.get('periode')  # 'YYYY-MM'
        if periode and '-' in periode:
            year, month = periode.split('-', 1)
            try:
                qs = qs.filter(
                    lead__date_cloture_prevue__year=int(year),
                    lead__date_cloture_prevue__month=int(month))
            except ValueError:
                pass
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            mis_a_jour_par=self.request.user)

    def perform_update(self, serializer):
        serializer.save(mis_a_jour_par=self.request.user)

    def list(self, request, *args, **kwargs):
        from decimal import Decimal
        response = super().list(request, *args, **kwargs)
        totaux = {}
        for entry in self.filter_queryset(self.get_queryset()):
            totaux[entry.categorie] = (
                totaux.get(entry.categorie, Decimal('0'))
                + (entry.montant_effectif or Decimal('0')))
        if isinstance(response.data, dict) and 'results' in response.data:
            response.data['totaux_par_categorie'] = totaux
        else:
            response.data = {
                'results': response.data, 'totaux_par_categorie': totaux}
        return response


@extend_schema(parameters=[sd.param('periode', description='AAAA-MM'), sd.param('equipe', OpenApiTypes.INT)], responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([IsAnyRole])
def forecast_rollup_view(request):
    """NTCRM5 — Roll-up hiérarchique du forecast : ``?periode=YYYY-MM&
    equipe=<id>``. Un Responsable/manager (non Admin) ne voit QUE les équipes
    qu'il dirige (``EquipeCommerciale.responsable``) ; un Admin/Directeur voit
    tout. ``?equipe=<id>`` restreint la réponse à cette équipe précise."""
    user = request.user
    if not user.company_id:
        return Response({'equipes': [], 'total_societe': {}})
    periode = None
    periode_param = request.query_params.get('periode')
    if periode_param and '-' in periode_param:
        year, month = periode_param.split('-', 1)
        try:
            periode = {
                'period_type': 'month', 'period_year': int(year),
                'period_month': int(month),
            }
        except ValueError:
            periode = None
    manager = None if getattr(user, 'is_admin_role', False) else user
    from .selectors import forecast_rollup
    data = forecast_rollup(user.company, periode=periode, manager=manager)
    equipe_id = request.query_params.get('equipe')
    if equipe_id:
        try:
            equipe_id = int(equipe_id)
        except ValueError:
            equipe_id = None
        data = {
            **data,
            'equipes': [e for e in data['equipes'] if e['equipe_id'] == equipe_id],
        }
    return Response(data)


@extend_schema(parameters=[sd.P_OWNER, sd.param('semaines', OpenApiTypes.INT)], responses=sd.OBJ)
@api_view(['GET'])
@permission_classes([IsAnyRole])
def forecast_historique_view(request):
    """NTCRM6 — Série de snapshots hebdomadaires : ``?owner=&semaines=12``.
    ``owner`` vide = snapshots SOCIÉTÉ (owner=None) ; sinon un commercial
    donné. Renvoie la série ordonnée chronologiquement pour un graphe
    d'évolution (glissement visible)."""
    user = request.user
    if not user.company_id:
        return Response({'series': []})
    owner = request.query_params.get('owner')
    try:
        semaines = int(request.query_params.get('semaines') or 12)
    except ValueError:
        semaines = 12
    qs = ForecastSnapshot.objects.filter(company=user.company)
    qs = qs.filter(owner_id=owner) if owner else qs.filter(owner__isnull=True)
    qs = qs.order_by('-semaine_iso')[:max(1, semaines)]
    data = list(reversed(ForecastSnapshotSerializer(qs, many=True).data))
    return Response({'series': data})


@extend_schema_view(list=extend_schema(parameters=[sd.param('client', OpenApiTypes.INT)]))
class PlanCompteViewSet(_PorteeEnfantsMixin, ChatterViewSetMixin, CompanyScopedModelViewSet):

    """NTCRM10 — Plan de compte. ARC8 : l'historique (chatter) converge sur
    ``records.Activity`` — création + changements de champ suivis journalisés
    via ``records.services`` (le « mail.thread » maison), jamais un modèle
    ``*Activity`` local. Le mixin ``ChatterViewSetMixin`` ajoute en plus les
    actions génériques ``chatter/historique`` (GET) et ``chatter/noter`` (POST)."""
    # ACRM9 — lectures bornées à la portée (leads : — ;

    # clients : client).

    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    portee_leads = ()

    portee_clients = ('client',)
    queryset = PlanCompte.objects.select_related('client')
    serializer_class = PlanCompteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['historique']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        from apps.records.models import Activity
        from apps.records.services import log_activity
        instance = serializer.save(
            company=self.request.user.company, created_by=self.request.user,
            mis_a_jour_par=self.request.user)
        log_activity(
            instance, Activity.Kind.CREATION, user=self.request.user,
            body=f'Plan de compte créé pour {instance.client}.')

    def perform_update(self, serializer):
        from apps.records.services import log_field_change
        old = PlanCompte.objects.get(pk=serializer.instance.pk)
        instance = serializer.save(mis_a_jour_par=self.request.user)
        tracked = [
            'objectifs_strategiques', 'potentiel_estime', 'concurrents_presents',
            'prochaine_revue', 'statut',
        ]
        for field in tracked:
            old_val, new_val = getattr(old, field), getattr(instance, field)
            if old_val != new_val:
                log_field_change(
                    instance, field,
                    str(old_val) if old_val is not None else '',
                    str(new_val) if new_val is not None else '',
                    user=self.request.user)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        from apps.records.serializers import ChatterActivitySerializer
        from apps.records.services import chatter_qs
        plan = self.get_object()
        qs = chatter_qs(plan, company=request.user.company)
        return Response(ChatterActivitySerializer(qs, many=True).data)


class RevueCompteViewSet(CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = RevueCompte.objects.select_related('plan')
    serializer_class = RevueCompteSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        # RevueCompte n'a PAS de champ `company` propre (scopée via son plan
        # de compte parent) : `TenantMixin.get_queryset()` (appelé par
        # `super()`) filtre sur `company=user.company`, ce qui lève un
        # FieldError (500) sur ce modèle — on construit donc le queryset
        # directement, jamais via `super().get_queryset()`.
        qs = RevueCompte.objects.select_related('plan')
        user = self.request.user
        if user.company_id:
            return qs.filter(plan__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PlaybookViewSet(CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = Playbook.objects.prefetch_related('etapes__taches')
    serializer_class = PlaybookSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class _PlaybookEnfantViewSetMixin:
    """CRX14 — socle des deux enfants de playbook (étapes, tâches).

    ``PlaybookEtape`` et ``PlaybookTache`` N'ONT PAS de champ ``company`` : la
    frontière société passe par le playbook parent. Le ``get_queryset`` de
    ``TenantMixin`` (``qs.filter(company=…)``) levait donc un ``FieldError``
    AVANT d'atteindre le re-scope ``playbook__company`` écrit juste après —
    autrement dit ce re-scope était MORT et toute lecture/écriture d'un objet
    existant (list, retrieve, update, destroy) répondait 500. On remplace
    entièrement le filtrage par le chemin parent, en gardant la sémantique de
    ``TenantMixin`` pour les trois acteurs : utilisateur d'une société →
    scopé ; superuser SANS société (acteur plateforme) → tout ; ni l'un ni
    l'autre → rien.

    ``perform_create``/``perform_update`` valident en plus le PARENT désigné
    par le corps : sans cela, un id de playbook (ou d'étape) d'une autre
    société suffisait à y greffer — ou à y déplacer — une étape.
    """

    #: Chemin ORM du parent portant la société (ex. ``playbook__company_id``).
    company_path = ''
    #: Nom du champ de relation parent dans le corps de la requête.
    parent_field = ''

    def base_queryset(self):
        raise NotImplementedError

    def get_queryset(self):
        qs = self.base_queryset()
        user = self.request.user
        if user.company_id:
            return qs.filter(**{self.company_path: user.company_id})
        if user.is_superuser:
            return qs
        return qs.none()

    def parent_company_id(self, parent):
        raise NotImplementedError

    def _valider_parent(self, serializer):
        company_id = getattr(self.request.user, 'company_id', None)
        if not company_id:
            return
        parent = serializer.validated_data.get(self.parent_field)
        if parent is None:
            # Absent d'un PATCH partiel : le parent existant a déjà été scopé
            # par ``get_queryset``, rien à revalider.
            if serializer.partial:
                return
            raise DRFValidationError(
                {self.parent_field: 'Ce champ est obligatoire.'})
        if self.parent_company_id(parent) != company_id:
            raise DRFValidationError(
                {self.parent_field: 'Élément hors de votre société.'})

    def perform_create(self, serializer):
        self._valider_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._valider_parent(serializer)
        serializer.save()


class PlaybookEtapeViewSet(_PlaybookEnfantViewSetMixin,
                           CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = PlaybookEtape.objects.select_related('playbook').prefetch_related('taches')
    serializer_class = PlaybookEtapeSerializer
    company_path = 'playbook__company_id'
    parent_field = 'playbook'

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def base_queryset(self):
        return PlaybookEtape.objects.select_related(
            'playbook').prefetch_related('taches')

    def parent_company_id(self, parent):
        return parent.company_id


class PlaybookTacheViewSet(_PlaybookEnfantViewSetMixin,
                           CompanyScopedModelViewSet):
    parser_classes = [JSONParser]  # ENF6 (D2) — aucun upload sur cette vue
    queryset = PlaybookTache.objects.select_related('etape__playbook')
    serializer_class = PlaybookTacheSerializer
    company_path = 'etape__playbook__company_id'
    parent_field = 'etape'

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def base_queryset(self):
        return PlaybookTache.objects.select_related('etape__playbook')

    def parent_company_id(self, parent):
        return parent.playbook.company_id


class _LeadPlaybookPermission(IsAnyRole):
    """ACRM8 — lire la progression : tout rôle interne ; cocher une tâche
    (POST) est une écriture commerciale : ``crm_modifier``."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return HasPermissionOrLegacy('crm_modifier')().has_permission(
            request, view)


@api_view(['GET', 'POST'])
@permission_classes([_LeadPlaybookPermission])
def lead_playbook_view(request, lead_id):
    """NTCRM12 — ``GET`` : progression playbook du lead (toutes les tâches
    générées pour son étape courante ou une étape antérieure). ``POST``
    ``{'tache': <id>, 'fait': true}`` : coche/décoche UNE tâche, pose
    l'acteur+la date côté serveur (jamais silencieux).

    ACRM8/ACRM9 — le lead est résolu dans la PORTÉE de l'appelant : hors
    portée = absent (404)."""
    from .selectors import leads_en_portee
    lead = leads_en_portee(request.user).filter(pk=lead_id).first()
    if lead is None:
        return Response({'detail': 'Lead introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        # AGR526 — `tache__etape__playbook` : la clé de texte (`cle_message`)
        # se lit sur le NOM du playbook, sans requête par ligne.
        progress = lead.playbook_progress.select_related(
            'tache', 'tache__etape', 'tache__etape__playbook', 'lead',
            'fait_par').all()
        return Response(LeadPlaybookProgressSerializer(progress, many=True).data)

    tache_id = request.data.get('tache')
    fait = bool(request.data.get('fait', True))
    progress = LeadPlaybookProgress.objects.filter(
        lead=lead, tache_id=tache_id).first()
    if progress is None:
        return Response(
            {'detail': 'Tâche de playbook introuvable pour ce lead.'},
            status=status.HTTP_404_NOT_FOUND)
    from django.utils import timezone as _tz
    progress.fait = fait
    progress.fait_par = request.user if fait else None
    progress.fait_le = _tz.now() if fait else None
    progress.save(update_fields=['fait', 'fait_par', 'fait_le'])
    return Response(LeadPlaybookProgressSerializer(progress).data)
