"""Vues LECTURE SEULE de l'API publique (N89), sous /api/public/v1/.

Chaque vue est authentifiée par clé d'API (ApiKeyAuthentication), scopée à la
société de la clé (jamais cross-tenant), paginée et protégée par un scope
précis (`required_scope`). Aucune écriture, aucun prix d'achat.

FG104 — filtrage, tri & synchro incrémentale. Sans dépendance externe
(`django-filter` n'est PAS installé) : un filtre est artisanal, restreint à une
liste blanche par vue (`filter_whitelist`), plus `?updated_since=` (ISO-8601 sur
le champ d'horodatage déclaré dans `sync_field`) pour la synchro incrémentale, et
le `OrderingFilter` natif de DRF (aucune dépendance) restreint par
`ordering_fields`. Un paramètre inconnu ou une valeur illisible renvoie 400 —
jamais d'erreur 500, jamais de fuite cross-tenant (la société reste imposée par
la clé).
"""
from django.utils.dateparse import parse_datetime, parse_date

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.crm.models import Lead
from apps.ventes.models import Devis, Facture
from apps.installations.models import Installation
from apps.stock.models import Produit

from .auth import PUBLIC_AUTHENTICATION_CLASSES, HasApiScope, ApiKeyRateThrottle
from .constants import (
    SCOPE_READ_CALEPINAGES, SCOPE_READ_LEADS, SCOPE_READ_DEVIS,
    SCOPE_READ_FACTURES, SCOPE_READ_CHANTIERS, SCOPE_READ_STOCK,
)
from .public_response import PublicApiResponseMixin
from .public_serializers import (
    PublicLeadSerializer, PublicDevisSerializer,
    PublicFactureSerializer, PublicChantierSerializer,
    PublicProduitSerializer, PublicCalepinageSerializer,
    PublicCalepinageResultatSerializer, resultat_calepinage_public,
)

# Paramètres de requête réservés à la pagination / au tri : jamais traités comme
# des filtres de champ inconnus.
_RESERVED_PARAMS = {'page', 'page_size', 'ordering', 'format', 'updated_since'}


class PublicReadOnlyViewSet(PublicApiResponseMixin, viewsets.ReadOnlyModelViewSet):
    """Base commune : auth par clé, scope, throttle par clé, scope société.

    La société vient TOUJOURS de la clé (request.auth.company_id), jamais d'un
    paramètre client — pas de fuite cross-tenant possible.

    FG104 — chaque sous-classe déclare :
      * ``filter_whitelist`` : champs filtrables par égalité (``?statut=...``) ;
      * ``ordering_fields``  : champs autorisés au tri (``?ordering=-date...``) ;
      * ``sync_field``       : champ d'horodatage pour ``?updated_since=`` (synchro
        incrémentale) — ``date_modification`` quand il existe, sinon la date de
        création/émission.
    """
    authentication_classes = PUBLIC_AUTHENTICATION_CLASSES
    permission_classes = [HasApiScope]
    throttle_classes = [ApiKeyRateThrottle]
    # Tri natif DRF (inclus dans rest_framework, aucune dépendance ajoutée).
    filter_backends = [OrderingFilter]
    required_scope = None       # défini par chaque sous-classe
    filter_whitelist = ()       # champs filtrables (liste blanche)
    ordering_fields = ()        # champs triables (liste blanche)
    sync_field = None           # champ d'horodatage pour ?updated_since=

    def get_company_id(self):
        return self.request.auth.company_id

    def get_queryset(self):
        return super().get_queryset().filter(company_id=self.get_company_id())

    def filter_queryset(self, queryset):
        # 1) Filtres de champ artisanaux (liste blanche) + synchro incrémentale.
        queryset = self._apply_field_filters(queryset)
        queryset = self._apply_updated_since(queryset)
        # 2) Tri natif DRF (restreint par ordering_fields).
        return super().filter_queryset(queryset)

    def _apply_field_filters(self, queryset):
        params = self.request.query_params
        for key in params:
            if key in _RESERVED_PARAMS:
                continue
            if key not in self.filter_whitelist:
                raise ValidationError(
                    {key: "Filtre inconnu ou non autorisé."})
            # Égalité simple sur la valeur fournie (scoping société déjà appliqué).
            queryset = queryset.filter(**{key: params.get(key)})
        return queryset

    def _apply_updated_since(self, queryset):
        raw = self.request.query_params.get('updated_since')
        if not raw or not self.sync_field:
            return queryset
        # Accepte un datetime ISO-8601 ou une date simple (AAAA-MM-JJ).
        value = parse_datetime(raw) or parse_date(raw)
        if value is None and ' ' in raw:
            # Un '+' d'offset ISO-8601 non encodé est décodé en espace par
            # l'URL ; on le restaure avant de lever une erreur.
            fixed = raw.replace(' ', '+')
            value = parse_datetime(fixed) or parse_date(fixed)
        if value is None:
            raise ValidationError({
                'updated_since':
                    "Date/heure invalide (attendu ISO-8601, ex. "
                    "2026-06-30 ou 2026-06-30T12:00:00Z)."})
        return queryset.filter(**{f'{self.sync_field}__gte': value})


class PublicLeadViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_LEADS
    serializer_class = PublicLeadSerializer
    queryset = Lead.objects.all().order_by('-date_creation')
    filter_whitelist = (
        'stage', 'canal', 'priorite', 'perdu', 'source',
        'type_installation', 'ville',
    )
    ordering_fields = ('date_creation', 'date_modification', 'id')
    sync_field = 'date_modification'


class PublicDevisViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_DEVIS
    serializer_class = PublicDevisSerializer
    queryset = Devis.objects.prefetch_related('lignes').order_by('-date_creation')
    filter_whitelist = ('statut', 'mode_installation', 'client', 'lead')
    ordering_fields = ('date_creation', 'id')
    # Devis n'a pas de date_modification : la synchro suit la date de création.
    sync_field = 'date_creation'


class PublicFactureViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_FACTURES
    serializer_class = PublicFactureSerializer
    queryset = Facture.objects.prefetch_related('lignes').order_by('-date_emission')
    filter_whitelist = ('statut', 'type_facture', 'client', 'devis')
    ordering_fields = ('date_emission', 'id')
    # Facture n'a pas de date_modification : la synchro suit la date d'émission.
    sync_field = 'date_emission'


class PublicChantierViewSet(PublicReadOnlyViewSet):
    required_scope = SCOPE_READ_CHANTIERS
    serializer_class = PublicChantierSerializer
    queryset = Installation.objects.all().order_by('-id')
    filter_whitelist = (
        'statut', 'raccordement', 'type_installation', 'client',
        'devis', 'lead',
    )
    ordering_fields = ('date_creation', 'date_modification', 'id')
    sync_field = 'date_modification'


class PublicCalepinageViewSet(PublicReadOnlyViewSet):
    """CAL214 — calepinages (apps.calepinage) en LECTURE SEULE, scope
    `read:calepinages`.

    FRONTIÈRE INTER-APPS TENUE ICI : le queryset vient de
    ``apps.calepinage.selectors.liste_calepinages`` — jamais
    ``apps.calepinage.models``. C'est le selector qui borne la société (il
    renvoie un queryset VIDE pour ``company=None``, donc un filtre absent ne
    peut pas se muer en absence de filtre), et la société vient TOUJOURS de la
    clé d'API, jamais d'un paramètre client.

    Ni géométrie brute ni coût interne ne sortent d'ici : la liste des clés
    publiées est celle, explicite, de ``PublicCalepinageSerializer``.
    """
    required_scope = SCOPE_READ_CALEPINAGES
    serializer_class = PublicCalepinageSerializer
    filter_whitelist = ('statut', 'lead_id', 'client_id', 'devis_id')
    ordering_fields = ('created_at', 'updated_at', 'id')
    sync_field = 'updated_at'

    def get_queryset(self):
        from apps.calepinage.selectors import liste_calepinages
        return liste_calepinages(self._company())

    def _company(self):
        """La société DE LA CLÉ — jamais lue d'un paramètre de requête.

        ``None`` hors contexte de requête (génération du schéma OpenAPI, qui
        introspecte ``get_queryset()`` sans requête) : le selector rend alors
        un queryset VIDE mais typé, donc le schéma sait dériver le type de
        ``{id}`` et rien ne fuite — l'absence de clé ne peut pas se muer en
        absence de filtre.
        """
        requete = getattr(self, 'request', None)
        return getattr(getattr(requete, 'auth', None), 'company', None)

    @extend_schema(responses={200: PublicCalepinageResultatSerializer})
    @action(detail=True, methods=['get'], url_path='resultat')
    def resultat(self, request, pk=None):
        """CALX369 — ``GET calepinages/<pk>/resultat/`` : la simulation servie.

        Sous-ressource en LECTURE SEULE, sous le scope EXISTANT
        ``read:calepinages`` (aucune nouvelle famille d'URL). Elle publie ce
        que ``PublicCalepinageResultatSerializer`` déclare champ par champ :
        production annuelle, rendement spécifique, ratio de performance,
        P50/P75/P90, postes de pertes (libellé, pourcentage, source) et
        horodatage du calcul. Le résultat est celui que l'atelier SERT
        (``apps.calepinage.selectors.resultat_servi``), contrôle de fraîcheur
        compris : non simulé ou périmé ⇒ grandeurs à ``null`` et ``motif``.

        CE QUE CETTE PORTÉE N'OUVRE PAS. ``read:calepinages`` ne permet NI
        d'écrire NI de LANCER une simulation : déclencher un calcul reste une
        porte INTERNE
        (``POST /api/django/calepinage/calepinages/<pk>/simuler/``,
        derrière la permission de gestion du module), et aucune
        portée publique ne l'ouvre aujourd'hui. Aurora sépare ces trois
        familles — lecture (``read_designs``), écriture (``write_designs``)
        et exécution (``run_design_automation`` : « Run Performance
        Simulation »),
        https://help.aurorasolar.com/hc/en-us/articles/29421703614995-Access-Scopes.
        Le jour où un intégrateur demandera de lancer une simulation, la
        portée à créer s'appellera ``calepinages:simuler`` (même forme que
        ``leads:write``) — elle n'est PAS créée ici.

        LA SÉRIE HORAIRE N'EST PAS PUBLIÉE ICI, et c'est voulu : 8 760 points
        par année simulée, sur plusieurs années, pèsent des mégaoctets — ce
        volume ruinerait le quota et le temps de réponse d'une lecture qu'une
        intégration appelle pour trois nombres. Même décision que le
        ``GET resultat/`` interne (D-CALX 14) : la série reste servie par
        l'export CSV de l'atelier.
        """
        from apps.calepinage.selectors import resultat_servi

        calepinage = self.get_object()
        charge = resultat_calepinage_public(calepinage.pk,
                                            resultat_servi(calepinage))
        return Response(PublicCalepinageResultatSerializer(charge).data)


class PublicProduitViewSet(PublicReadOnlyViewSet):
    """XSTK23 — disponibilité produit en lecture seule. Jamais de coût."""
    required_scope = SCOPE_READ_STOCK
    serializer_class = PublicProduitSerializer
    queryset = Produit.objects.filter(is_archived=False).select_related(
        'categorie').order_by('-id')
    filter_whitelist = ('sku', 'marque', 'categorie')
    ordering_fields = ('id', 'nom')
    # Produit n'a pas d'horodatage de modification dédié exposable ici :
    # pas de synchro incrémentale pour cette ressource (comportement explicite,
    # ?updated_since= reste inopérant plutôt que d'exposer un faux champ).
    sync_field = None
