"""Vues Agriculture (scopées société, accès Administrateur/Responsable en
écriture, tout rôle authentifié en lecture — même patron que ``apps.flotte``/
``apps.qhse``)."""
from django.http import HttpResponse
from rest_framework import filters, viewsets
from rest_framework.decorators import action

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.mixins import TenantMixin

from .models import (
    CampagneCulturale, EquipeSaisonniere, EtapeCampagne, Exploitation,
    IntrantAgricole, Parcelle, PointageAgricole,
)
from .serializers import (
    CampagneCulturaleSerializer, EquipeSaisonniereSerializer,
    EtapeCampagneSerializer, ExploitationSerializer,
    IntrantAgricoleSerializer, ParcelleSerializer, PointageAgricoleSerializer,
)

READ_ACTIONS = {'list', 'retrieve'}


class _AgricultureBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée (TenantMixin). Lecture tout rôle, écriture
    responsable/admin."""

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ExploitationViewSet(_AgricultureBaseViewSet):
    """NTAGR1 — Exploitations agricoles d'une société."""
    queryset = Exploitation.objects.all()
    serializer_class = ExploitationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'adresse']
    ordering_fields = ['nom', 'date_creation']


class ParcelleViewSet(_AgricultureBaseViewSet):
    """NTAGR1 — Parcelles cultivables. Filtrable ``?exploitation_id=&culture=``."""
    queryset = Parcelle.objects.all()
    serializer_class = ParcelleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'code', 'culture_principale']
    ordering_fields = ['nom', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        exploitation_id = params.get('exploitation_id')
        if exploitation_id:
            qs = qs.filter(exploitation_id=exploitation_id)
        culture = params.get('culture')
        if culture:
            qs = qs.filter(culture_principale__iexact=culture)
        return qs


class CampagneCulturaleViewSet(_AgricultureBaseViewSet):
    """NTAGR2 — Campagnes culturales. Filtrable ``?parcelle_id=&statut=``."""
    queryset = CampagneCulturale.objects.all()
    serializer_class = CampagneCulturaleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['culture', 'variete']
    ordering_fields = ['date_creation', 'date_semis', 'date_recolte_prevue']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        parcelle_id = params.get('parcelle_id')
        if parcelle_id:
            qs = qs.filter(parcelle_id=parcelle_id)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=True, methods=['get'], url_path='registre-phyto-pdf')
    def registre_phyto_pdf(self, request, pk=None):
        """NTAGR7 — Registre phytosanitaire ONSSA imprimable (PDF interne,
        WeasyPrint) — JAMAIS le moteur ``/proposal`` (règle CLAUDE.md #4, ce
        n'est pas un devis client)."""
        from .report_phyto import render_registre_phyto_pdf

        campagne = self.get_object()
        pdf_bytes = render_registre_phyto_pdf(campagne)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="registre-phyto-{campagne.pk}.pdf"')
        return response


class EtapeCampagneViewSet(_AgricultureBaseViewSet):
    """NTAGR3 — Étapes horodatées d'une campagne. Filtrable ``?campagne_id=``."""
    queryset = EtapeCampagne.objects.all()
    serializer_class = EtapeCampagneSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        campagne_id = self.request.query_params.get('campagne_id')
        if campagne_id:
            qs = qs.filter(campagne_id=campagne_id)
        return qs


class IntrantAgricoleViewSet(_AgricultureBaseViewSet):
    """NTAGR5 — Catalogue agronomique lié à ``stock.Produit``. Filtrable
    ``?categorie=``."""
    queryset = IntrantAgricole.objects.all()
    serializer_class = IntrantAgricoleSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['categorie', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        categorie = self.request.query_params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        return qs


class EquipeSaisonniereViewSet(_AgricultureBaseViewSet):
    """NTAGR9 — Équipes saisonnières."""
    queryset = EquipeSaisonniere.objects.all()
    serializer_class = EquipeSaisonniereSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom', 'date_creation']


class PointageAgricoleViewSet(_AgricultureBaseViewSet):
    """NTAGR9 — Pointages journaliers. Filtrable
    ``?campagne_id=&parcelle_id=&equipe_id=``."""
    queryset = PointageAgricole.objects.all()
    serializer_class = PointageAgricoleSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        campagne_id = params.get('campagne_id')
        if campagne_id:
            qs = qs.filter(campagne_id=campagne_id)
        parcelle_id = params.get('parcelle_id')
        if parcelle_id:
            qs = qs.filter(parcelle_id=parcelle_id)
        equipe_id = params.get('equipe_id')
        if equipe_id:
            qs = qs.filter(equipe_id=equipe_id)
        return qs
