"""Vues FG329 — planification des livraisons (dépôt → site).

``LivraisonViewSet`` : CRUD des livraisons ; référence anti-collision posée
serveur ; cycle ``expedier`` (→ en transit) / ``livrer`` (→ livrée) / ``annuler``
(→ annulée). ``LivraisonLigneViewSet`` : articles d'une livraison. Lecture tout
rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` ;
chantier/dépôt validés tenant. Cross-app : ``stock`` en string-FK.
"""
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from apps.ventes.utils.references import create_with_reference

from ..models import Livraison, LivraisonLigne
from ..serializers import LivraisonSerializer, LivraisonLigneSerializer

READ_ACTIONS = ['list', 'retrieve']


class LivraisonViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG329 — livraisons planifiées. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `installation`, `statut`, `depot`,
    `date_prevue`."""
    queryset = Livraison.objects.select_related(
        'installation', 'depot', 'created_by').prefetch_related('lignes').all()
    serializer_class = LivraisonSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        installation = params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        depot = params.get('depot')
        if depot:
            qs = qs.filter(depot_id=depot)
        date_prevue = params.get('date_prevue')
        if date_prevue:
            qs = qs.filter(date_prevue=date_prevue)
        # FG333 — filtre par mode d'acheminement (dépôt vs direct site).
        mode = params.get('mode_acheminement')
        if mode:
            qs = qs.filter(mode_acheminement=mode)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        for field, label in (
                ('installation', 'Chantier'), ('depot', 'Dépôt'),
                ('transporteur', 'Transporteur')):
            obj = serializer.validated_data.get(field)
            if obj is not None and getattr(obj, 'company_id', None) != cid:
                raise ValidationError(
                    {field: f'{label} inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)

        def _save(reference):
            return serializer.save(
                company=company, created_by=self.request.user,
                reference=reference)

        create_with_reference(Livraison, 'LIV', company, _save)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def _set_statut(self, request, statut):
        liv = self.get_object()
        liv.statut = statut
        liv.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(liv).data)

    def _notify_client(self, liv, statut, request):
        """XSTK22 — notification client best-effort au passage en transit/
        livrée, UNE SEULE FOIS (garde ``notifie_transit_le`` pour le
        transit ; la notification livrée n'a pas besoin de garde dédiée
        car ``livrer`` n'est jamais appelé deux fois par le même flux
        d'action, mais on reste idempotent en ne renvoyant rien si déjà
        notifié pour ce statut)."""
        from .. import livraison_client_notify
        if statut == Livraison.Statut.EN_TRANSIT:
            if liv.notifie_transit_le is not None:
                return
            livraison_client_notify.notify_livraison_transition(
                liv, 'en_transit', request=request)
            liv.notifie_transit_le = timezone.now()
            liv.save(update_fields=['notifie_transit_le'])
        elif statut == Livraison.Statut.LIVREE:
            livraison_client_notify.notify_livraison_transition(
                liv, 'livree', request=request)

    @action(detail=True, methods=['post'])
    def expedier(self, request, pk=None):
        """FG329 — passe la livraison en transit. XSTK22 : notifie le client
        (best-effort, une seule fois)."""
        liv = self.get_object()
        liv.statut = Livraison.Statut.EN_TRANSIT
        liv.save(update_fields=['statut', 'date_modification'])
        self._notify_client(liv, Livraison.Statut.EN_TRANSIT, request)
        return Response(self.get_serializer(liv).data)

    @action(detail=True, methods=['post'])
    def livrer(self, request, pk=None):
        """FG329 — marque la livraison livrée. XSTK22 : notifie le client
        (best-effort)."""
        liv = self.get_object()
        liv.statut = Livraison.Statut.LIVREE
        liv.save(update_fields=['statut', 'date_modification'])
        self._notify_client(liv, Livraison.Statut.LIVREE, request)
        return Response(self.get_serializer(liv).data)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """FG329 — annule la livraison."""
        return self._set_statut(request, Livraison.Statut.ANNULEE)

    @action(detail=False, methods=['get'], url_path='portail',
            permission_classes=[IsAnyRole])
    def portail(self, request):
        """XSTK22 — section « Livraisons » du portail client (FG228) : les
        livraisons des chantiers de ``?client=ID``, format plat SANS
        ``cout_transport`` ni prix d'achat (même patron que
        ``monitoring.client_portal``)."""
        from .. import selectors
        company = request.user.company
        client_id = request.query_params.get('client')
        if company is None or not client_id:
            return Response(
                {'detail': 'client requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        return Response(
            selectors.livraisons_client_portail(company, client_id))


class LivraisonLigneViewSet(viewsets.ModelViewSet):
    """FG329 — lignes de livraison. Pas de `company` propre : scope via la
    livraison parente. Filtrable par `livraison`. Lecture tout rôle, écriture
    responsable/admin."""
    queryset = LivraisonLigne.objects.select_related(
        'livraison', 'produit').all()
    serializer_class = LivraisonLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(livraison__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        livraison = self.request.query_params.get('livraison')
        if livraison:
            qs = qs.filter(livraison_id=livraison)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        livraison = serializer.validated_data.get('livraison')
        if livraison is not None and getattr(
                livraison, 'company_id', None) != cid:
            raise ValidationError(
                {'livraison': 'Livraison inconnue pour cette société.'})
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()
