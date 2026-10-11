"""SPL76 — sous-parcours clients (propriétaire « lead » au registre) :
salle de vente, partenaires, apporteurs, deals enregistrés, défis et T-TRACE
(VisiteExterne, AppareilEquipe), déplacés de ``views.py`` à l'identique
(move only).

Règle d'import : ce module n'importe JAMAIS ``views.py`` (``READ_ACTIONS`` et
``_PorteeEnfantsMixin`` viennent du module neutre ``actions_crud``).
"""
import re
import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import filters, mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from core.viewsets import CompanyScopedModelViewSet
from .actions_crud import READ_ACTIONS, _PorteeEnfantsMixin
from .models import (
    AppareilEquipe, Apporteur, DealEnregistre, Defi, Partenaire, SalleVente,
    SalleVenteItem, VisiteExterne,
)
from .serializers_clients import (
    AppareilEquipeSerializer, PartenaireSerializer, SalleVenteSerializer,
    SalleVenteItemSerializer, ApporteurSerializer, DealEnregistreSerializer,
    DefiSerializer, VisiteExterneSerializer,
)
from .services import COOKIE_APPAREIL, domaine_cookies_equipe, enregistrer_appareil_equipe
from . import schema_docs as sd
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin, IsAdminRole


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

    def perform_create(self, serializer):
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

    @extend_schema(responses=sd.EXPORT_XLSX)
    @action(detail=True, methods=['get'], url_path='export-xlsx',
            permission_classes=[IsAnyRole])
    def export_xlsx(self, request, pk=None):
        """NTCRM28 — Export .xlsx du classement, même contenu que
        ``classement/`` (rang/nom/score), pour partage en réunion commerciale."""
        from .exports import export_defi_classement_xlsx
        from .selectors import classement_defi
        defi = self.get_object()
        return export_defi_classement_xlsx(defi, classement_defi(defi))


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
