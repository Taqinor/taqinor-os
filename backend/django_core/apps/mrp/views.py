"""Vues de l'app `mrp` (Groupe NTMFG — Production / MRP II)."""
from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from .models import Gamme, OperationGamme, OperationOF, OrdreFabrication, PosteDeCharge
from .serializers import (
    GammeSerializer, OperationGammeSerializer, OperationOFSerializer,
    OrdreFabricationSerializer, PosteDeChargeSerializer,
)


class PosteDeChargeViewSet(CompanyScopedModelViewSet):
    """NTMFG1 — CRUD des postes de charge (company-scopé)."""
    queryset = PosteDeCharge.objects.all()
    serializer_class = PosteDeChargeSerializer
    filterset_fields = ['type_poste', 'actif']


class GammeViewSet(CompanyScopedModelViewSet):
    """NTMFG2 — CRUD des gammes opératoires (company-scopé)."""
    queryset = Gamme.objects.select_related('produit').prefetch_related(
        'operations__poste_charge').all()
    serializer_class = GammeSerializer
    filterset_fields = ['produit', 'actif']


class OperationGammeViewSet(viewsets.ModelViewSet):
    """NTMFG2 — opérations d'une gamme. Pas de `company` propre : scope via
    la gamme parente (même convention que
    `installations.KitComposantViewSet`). Filtrable par `?gamme=`."""
    queryset = OperationGamme.objects.select_related(
        'gamme', 'poste_charge').all()
    serializer_class = OperationGammeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(gamme__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        gamme = self.request.query_params.get('gamme')
        if gamme:
            qs = qs.filter(gamme_id=gamme)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        gamme = serializer.validated_data.get('gamme')
        if gamme is not None and getattr(gamme, 'company_id', None) != cid:
            raise ValidationError({'gamme': 'Gamme inconnue pour cette société.'})
        poste = serializer.validated_data.get('poste_charge')
        if poste is not None and getattr(poste, 'company_id', None) != cid:
            raise ValidationError(
                {'poste_charge': 'Poste de charge inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()


class OrdreFabricationViewSet(CompanyScopedModelViewSet):
    """NTMFG3 — CRUD des Ordres de Fabrication (company-scopé). `confirmer/`
    instancie les opérations depuis la gamme et calcule les dates prévues
    (NTMFG3)."""
    queryset = OrdreFabrication.objects.select_related(
        'produit', 'gamme', 'kit_ordre_assemblage').prefetch_related(
        'operations__poste_charge').all()
    serializer_class = OrdreFabricationSerializer
    filterset_fields = ['statut', 'produit', 'gamme']

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        for champ in ('produit', 'gamme', 'kit_ordre_assemblage'):
            valeur = serializer.validated_data.get(champ)
            if valeur is not None and getattr(valeur, 'company_id', None) != cid:
                raise ValidationError(
                    {champ: 'Référence inconnue pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='confirmer')
    def confirmer(self, request, pk=None):
        """NTMFG3 — instancie les opérations depuis la gamme + planifie les
        dates (capacité poste), passe le statut en `planifie`."""
        from .services import confirmer_of
        of = self.get_object()
        confirmer_of(of, user=request.user)
        of.refresh_from_db()
        return Response(self.get_serializer(of).data)

    @action(detail=True, methods=['post'], url_path='cloturer')
    def cloturer(self, request, pk=None):
        """NTMFG4 — clôture l'OF : backflush (consommation composants +
        production composite) exactement une fois, sauf si un
        `kit_ordre_assemblage` porte déjà le mouvement (XMFG1)."""
        from .services import cloturer_of
        of = self.get_object()
        cloturer_of(of, user=request.user)
        of.refresh_from_db()
        return Response(self.get_serializer(of).data)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """NTMFG6 — annule l'OF : libère ses réservations de composants.
        Refuse (400) si le stock a déjà été mouvementé."""
        from .services import annuler_of
        of = self.get_object()
        try:
            annuler_of(of, user=request.user, motif=request.data.get('motif', ''))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        of.refresh_from_db()
        return Response(self.get_serializer(of).data)

    @action(detail=True, methods=['get'], url_path='dispo-composants')
    def dispo_composants(self, request, pk=None):
        """NTMFG6 — disponibilité par ligne réservée (disponible/partiel/
        manquant)."""
        from .selectors import disponibilite_par_ligne_of
        of = self.get_object()
        return Response(disponibilite_par_ligne_of(of))


class OperationOFViewSet(viewsets.ModelViewSet):
    """NTMFG3 — opérations d'un OF. Pas de `company` propre : scope via l'OF
    parent. Filtrable par `?ordre_fabrication=`."""
    queryset = OperationOF.objects.select_related(
        'ordre_fabrication', 'operation_gamme', 'poste_charge').all()
    serializer_class = OperationOFSerializer
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(ordre_fabrication__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        of = self.request.query_params.get('ordre_fabrication')
        if of:
            qs = qs.filter(ordre_fabrication_id=of)
        return qs


@api_view(['POST'])
def mrp_run_view(request):
    """NTMFG5 — ``POST /api/django/mrp/mrp-run/`` : calcul des besoins nets
    (MRP) à la demande, company-scopé. Corps optionnel :
    ``{"produits": [id, ...], "demande_independante": {"<produit_id>": qte},
    "stock_securite_pct": "10", "horizon_jours": 30}``."""
    from .selectors import calculer_besoins_nets

    body = request.data or {}
    resultats = calculer_besoins_nets(
        request.user.company,
        produits=body.get('produits'),
        demande_independante=body.get('demande_independante'),
        stock_securite_pct=body.get('stock_securite_pct') or 0,
        horizon_jours=body.get('horizon_jours'))
    return Response(resultats)
