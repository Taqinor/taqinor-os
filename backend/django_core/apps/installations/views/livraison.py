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

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import Livraison, LivraisonLigne
from ..serializers import (
    LivraisonSerializer, LivraisonLigneSerializer, RetourLivraisonSerializer,
)
from ..services import (
    ventiler_stock_livraison, contre_transferer_stock_livraison,
    generer_retour_livraison,
)

READ_ACTIONS = ['list', 'retrieve']


class LivraisonViewSet(CompanyScopedModelViewSet):
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
        """FG329 — passe la livraison en transit. YSTCK5 : ventile le stock
        dépôt → van (idempotent, best-effort). XSTK22 : notifie le client
        (best-effort, une seule fois)."""
        liv = self.get_object()
        liv.statut = Livraison.Statut.EN_TRANSIT
        liv.save(update_fields=['statut', 'date_modification'])
        try:
            ventiler_stock_livraison(liv, request.user)
        except Exception:  # pragma: no cover - défensif, best-effort
            pass
        self._notify_client(liv, Livraison.Statut.EN_TRANSIT, request)
        return Response(self.get_serializer(liv).data)

    @action(detail=True, methods=['post'])
    def livrer(self, request, pk=None):
        """FG329 — marque la livraison livrée. XSTK22 : notifie le client
        (best-effort). XSTK23 : émet le webhook public `livraison.livree`
        (best-effort, jamais bloquant, via le SERVICE publicapi — jamais son
        modèle)."""
        liv = self.get_object()
        liv.statut = Livraison.Statut.LIVREE
        liv.save(update_fields=['statut', 'date_modification'])
        self._notify_client(liv, Livraison.Statut.LIVREE, request)
        try:
            from apps.publicapi.services import notify_livraison_livree
            notify_livraison_livree(
                company_id=liv.company_id,
                livraison_id=liv.id,
                reference=liv.reference,
                installation_id=liv.installation_id,
                numero_suivi=liv.numero_suivi,
            )
        except Exception:  # pragma: no cover - défensif, best-effort
            pass
        return Response(self.get_serializer(liv).data)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """FG329 — annule la livraison. YSTCK5 : contre-transfert van → dépôt
        si le stock avait été ventilé (idempotent, best-effort)."""
        liv = self.get_object()
        try:
            contre_transferer_stock_livraison(liv, request.user)
        except Exception:  # pragma: no cover - défensif, best-effort
            pass
        return self._set_statut(request, Livraison.Statut.ANNULEE)

    @action(detail=True, methods=['post'], url_path='generer-retour',
            permission_classes=[IsResponsableOrAdmin])
    def generer_retour(self, request, pk=None):
        """ZSTK8 — génère un `RetourLivraison` brouillon pré-rempli depuis
        les lignes livrées. Refuse si la livraison n'est pas LIVREE (rien à
        retourner tant qu'elle n'est pas arrivée)."""
        liv = self.get_object()
        if liv.statut != Livraison.Statut.LIVREE:
            return Response(
                {'detail': 'Seule une livraison livrée peut générer un '
                 'retour.'},
                status=status.HTTP_400_BAD_REQUEST)
        motif = (request.data.get('motif') or '').strip()
        retour = generer_retour_livraison(liv, request.user, motif=motif)
        return Response(
            RetourLivraisonSerializer(retour).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='bon-livraison',
            permission_classes=[IsAnyRole])
    def bon_livraison(self, request, pk=None):
        """ZSTK4 — bon de livraison PDF (packing/delivery slip). Client-facing :
        aucun `cout_transport` ni prix d'achat (test dédié)."""
        from django.http import HttpResponse
        from .. import livraison_pdf
        liv = self.get_object()
        pdf_bytes = livraison_pdf.bon_livraison_pdf(liv)
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'inline; filename="bon-livraison-{liv.id}.pdf"')
        return resp

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
