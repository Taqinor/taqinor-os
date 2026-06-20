from rest_framework import viewsets, filters

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin, IsAdminRole

from .models import Outillage, KitOutillage, KitOutillageItem
from .serializers import (
    OutillageSerializer, KitOutillageSerializer, KitOutillageItemSerializer,
)

READ_ACTIONS = ['list', 'retrieve']

# Kits d'outillage par défaut — semés à la première consultation par société.
# Coquilles nommées et vides : le founder y ajoute les outils de son parc.
_DEFAULT_KITS = [
    'Kit pose structure',
    'Kit raccordement électrique',
    'Kit mise en service',
]


def seed_kits_outillage(company):
    """Sème les 3 kits par défaut une seule fois par société (idempotent)."""
    if company is None or KitOutillage.objects.filter(company=company).exists():
        return
    for i, nom in enumerate(_DEFAULT_KITS):
        KitOutillage.objects.get_or_create(
            company=company, nom=nom, defaults={'ordre': i})


class OutillageViewSet(TenantMixin, viewsets.ModelViewSet):
    """Catalogue d'outillage durable (F1). Lecture tout rôle ; écriture
    responsable/admin. Filtrable par statut et emplacement, recherche par
    nom / asset tag / n° de série. JAMAIS de stock vendable."""
    queryset = Outillage.objects.select_related('emplacement').all()
    serializer_class = OutillageSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'asset_tag', 'numero_serie', 'categorie']
    ordering_fields = ['nom', 'statut', 'date_achat', 'date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        emplacement = params.get('emplacement')
        if emplacement:
            qs = qs.filter(emplacement_id=emplacement)
        return qs


class KitOutillageViewSet(TenantMixin, viewsets.ModelViewSet):
    """Kits d'outillage (F2), gérés dans Paramètres. Lecture tout rôle ;
    écriture admin. Les 3 kits par défaut sont semés à la première liste."""
    queryset = KitOutillage.objects.prefetch_related('items__outil').all()
    serializer_class = KitOutillageSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        if request.user.company_id:
            seed_kits_outillage(request.user.company)
        return super().list(request, *args, **kwargs)


class KitOutillageItemViewSet(TenantMixin, viewsets.ModelViewSet):
    """Outils d'un kit (F2). Company posée côté serveur depuis le kit parent ;
    écriture admin. Filtrable par kit."""
    queryset = KitOutillageItem.objects.select_related('outil', 'kit').all()
    serializer_class = KitOutillageItemSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        kit = self.request.query_params.get('kit')
        if kit:
            qs = qs.filter(kit_id=kit)
        return qs

    def perform_create(self, serializer):
        # La société de l'item suit toujours celle du kit parent.
        serializer.save(company=serializer.validated_data['kit'].company)

    def perform_update(self, serializer):
        kit = serializer.validated_data.get('kit') or serializer.instance.kit
        serializer.save(company=kit.company)
