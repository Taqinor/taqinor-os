"""Vues LECTURE SEULE de l'API publique (N89), sous /api/public/.

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

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter

from apps.crm.models import Lead
from apps.ventes.models import Devis, Facture
from apps.installations.models import Installation
from apps.stock.models import Produit

from .auth import ApiKeyAuthentication, HasApiScope, ApiKeyRateThrottle
from .constants import (
    SCOPE_READ_LEADS, SCOPE_READ_DEVIS,
    SCOPE_READ_FACTURES, SCOPE_READ_CHANTIERS, SCOPE_READ_STOCK,
)
from .public_response import PublicApiResponseMixin
from .public_serializers import (
    PublicLeadSerializer, PublicDevisSerializer,
    PublicFactureSerializer, PublicChantierSerializer,
    PublicProduitSerializer,
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
    authentication_classes = [ApiKeyAuthentication]
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
