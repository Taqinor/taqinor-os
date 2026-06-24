"""Vues du module Gestion de flotte (toutes scopées société).

La flotte est INTERNE. Chaque viewset filtre par ``request.user.company``
(``TenantMixin``) et pose la société côté serveur ; aucune société n'est jamais
acceptée du corps de requête (multi-tenant).
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from .models import ActifFlotte, EnginRoulant, ReferentielFlotte, Vehicule
from .serializers import (
    ActifFlotteSerializer,
    EnginRoulantSerializer,
    ReferentielFlotteSerializer,
    VehiculeSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class _FlotteBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée (TenantMixin). Lecture tout rôle, écriture
    responsable/admin."""

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class VehiculeViewSet(_FlotteBaseViewSet):
    """Véhicules immatriculés du parc (FLOTTE2). Filtrable par énergie/statut,
    recherche par immatriculation/marque/modèle."""
    queryset = Vehicule.objects.all()
    serializer_class = VehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['immatriculation', 'marque', 'modele']
    ordering_fields = ['immatriculation', 'kilometrage', 'statut',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        energie = params.get('energie')
        if energie:
            qs = qs.filter(energie=energie)
        return qs


class EnginRoulantViewSet(_FlotteBaseViewSet):
    """Engins roulants suivis au compteur d'heures (FLOTTE4). Filtrable par
    type/statut, recherche par désignation/marque/modèle."""
    queryset = EnginRoulant.objects.all()
    serializer_class = EnginRoulantSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'marque', 'modele']
    ordering_fields = ['nom', 'compteur_heures', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        type_engin = params.get('type_engin')
        if type_engin:
            qs = qs.filter(type_engin=type_engin)
        return qs


class ReferentielFlotteViewSet(_FlotteBaseViewSet):
    """Listes de référence éditables du parc (FLOTTE6). Filtrable par
    ``?domaine=`` (type_vehicule/type_engin/energie/categorie_permis) et par
    ``?actif=true|false``, recherche par code/libellé."""
    queryset = ReferentielFlotte.objects.all()
    serializer_class = ReferentielFlotteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'libelle']
    ordering_fields = ['domaine', 'ordre', 'libelle', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        domaine = params.get('domaine')
        if domaine:
            qs = qs.filter(domaine=domaine)
        actif = params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'vrai', 'oui'))
        return qs


class ActifFlotteViewSet(_FlotteBaseViewSet):
    """Références d'actif unifiées (FLOTTE5) — Vehicule | EnginRoulant.

    Chaque ``ActifFlotte`` pointe vers SOIT un véhicule SOIT un engin roulant
    de la même société, permettant aux futurs modules entretien/sinistre/
    document de se rattacher à l'un ou l'autre via un FK unique.

    Filtrable par ``?type_actif=vehicule`` ou ``?type_actif=engin``.
    """
    queryset = ActifFlotte.objects.select_related('vehicule', 'engin')
    serializer_class = ActifFlotteSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        type_actif = self.request.query_params.get('type_actif')
        if type_actif == ActifFlotte.TYPE_VEHICULE:
            qs = qs.filter(vehicule__isnull=False)
        elif type_actif == ActifFlotte.TYPE_ENGIN:
            qs = qs.filter(engin__isnull=False)
        return qs
