"""Vues du module Hôtellerie & restauration.

Les viewsets filtrent par ``request.user.company`` (``TenantMixin``) et posent
la société côté serveur (jamais du corps de requête). Lecture ouverte à tout
rôle authentifié (``IsAnyRole``) ; écriture réservée Responsable/Admin
(``IsResponsableOrAdmin``), sauf actions explicitement ouvertes (ex. tâches de
housekeeping assignées à l'utilisateur courant).
"""
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from . import services
from .models import (
    Chambre, Folio, PlanTarifaire, Reservation, TacheMenage, TypeChambre,
)
from .serializers import (
    ChambreSerializer, FicheClientSerializer, FolioSerializer,
    PlanTarifaireSerializer, ReservationSerializer, TacheMenageSerializer,
    TypeChambreSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class TypeChambreViewSet(TenantMixin, viewsets.ModelViewSet):
    """Catégories de chambre (Standard/Suite/Riad-suite…), CRUD scopé société."""
    queryset = TypeChambre.objects.all()
    serializer_class = TypeChambreSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['libelle', 'capacite_max']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ChambreViewSet(TenantMixin, viewsets.ModelViewSet):
    """Chambres/unités, CRUD scopé société. Filtre ``?statut=``."""
    queryset = Chambre.objects.select_related('type_chambre').all()
    serializer_class = ChambreSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero', 'nom', 'etage']
    ordering_fields = ['numero', 'statut']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs


class PlanTarifaireViewSet(TenantMixin, viewsets.ModelViewSet):
    """Plans tarifaires (rack/corporate/ota) par type de chambre, CRUD scopé
    société (NTHOT2)."""
    queryset = PlanTarifaire.objects.select_related('type_chambre').all()
    serializer_class = PlanTarifaireSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_fin', 'prix_nuit_ht']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        type_chambre = self.request.query_params.get('type_chambre')
        if type_chambre:
            qs = qs.filter(type_chambre_id=type_chambre)
        return qs


class ReservationViewSet(TenantMixin, viewsets.ModelViewSet):
    """Réservations, CRUD scopé société (NTHOT3). Filtre ``?statut=&date_
    arrivee=``. La création passe par ``services.creer_reservation``
    (validation de chevauchement + résolution client + snapshot prix)."""
    queryset = Reservation.objects.select_related(
        'chambre', 'type_chambre', 'client').all()
    serializer_class = ReservationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_arrivee', 'date_depart', 'date_creation']

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
        date_arrivee = params.get('date_arrivee')
        if date_arrivee:
            qs = qs.filter(date_arrivee=date_arrivee)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        chambre = v.get('chambre')
        try:
            reservation = services.creer_reservation(
                company=request.user.company,
                user=request.user,
                chambre=chambre,
                type_chambre=v.get('type_chambre'),
                date_arrivee=v['date_arrivee'],
                date_depart=v['date_depart'],
                nb_adultes=v.get('nb_adultes', 1),
                nb_enfants=v.get('nb_enfants', 0),
                origine=v.get('origine', Reservation.Origine.WALK_IN),
                client_id=v.get('client_id'),
                client_nom=v.get('client_nom', ''),
                client_telephone=v.get('client_telephone', ''),
            )
        except services.ReservationOverlapError as exc:
            return Response(
                {'chambre': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        out = self.get_serializer(reservation)
        headers = self.get_success_headers(out.data)
        return Response(
            out.data, status=status.HTTP_201_CREATED, headers=headers)

    # ── NTHOT5 — Check-in avec fiche de police marocaine ────────────────────
    @action(detail=True, methods=['post'], url_path='check-in')
    def check_in(self, request, pk=None):
        """Check-in : corps ``{"fiches": [{nom_complet, nationalite,
        type_piece, numero_piece, date_naissance}, ...]}``. 400 si une fiche
        est absente/incomplète (aucune fiche créée dans ce cas)."""
        reservation = self.get_object()
        fiches_data = request.data.get('fiches') or []
        try:
            services.check_in(
                reservation, fiches_data=fiches_data, user=request.user)
        except services.CheckInError as exc:
            return Response(
                {'fiches': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(reservation).data)

    # ── NTHOT6 — Check-out et libération de chambre ─────────────────────────
    @action(detail=True, methods=['post'], url_path='check-out')
    def check_out(self, request, pk=None):
        """Check-out : corps optionnel ``{"override": true}`` (admin/
        responsable) pour forcer malgré un folio non soldé — journalisé."""
        reservation = self.get_object()
        override = bool(request.data.get('override'))
        if override and not request.user.is_responsable:
            return Response(
                {'override': "Réservé aux rôles Responsable/Administrateur."},
                status=status.HTTP_403_FORBIDDEN)
        try:
            services.check_out(reservation, user=request.user, override=override)
        except services.CheckOutError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(reservation).data)

    @action(detail=True, methods=['get'], url_path='fiches-police')
    def fiches_police(self, request, pk=None):
        """Liste les fiches de police saisies au check-in de cette réservation."""
        reservation = self.get_object()
        return Response(
            FicheClientSerializer(
                reservation.fiches_client.all(), many=True).data)

    @action(detail=True, methods=['get'], url_path='fiche-police-pdf')
    def fiche_police_pdf(self, request, pk=None):
        """PDF « fiche de police » (NTHOT5) — document interne, jamais le
        moteur ``/proposal`` de devis client (rule #4)."""
        from django.http import HttpResponse

        from .pdf import render_fiche_police_pdf

        reservation = self.get_object()
        if not reservation.fiches_client.exists():
            return Response(
                {'detail': 'Aucune fiche de police : check-in non effectué.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            pdf_bytes = render_fiche_police_pdf(reservation)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="fiche-police-{reservation.pk}.pdf"')
        return response


class FolioViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Folio client unifié (NTHOT7) — lecture + action de clôture. Créé
    automatiquement à la réservation (``services.creer_reservation``) ;
    aucune création manuelle via l'API."""
    queryset = Folio.objects.select_related('reservation').prefetch_related(
        'lignes').all()
    serializer_class = FolioSerializer

    def get_permissions(self):
        return [IsAnyRole()]

    @action(detail=True, methods=['post'], url_path='cloturer',
            permission_classes=[IsResponsableOrAdmin])
    def cloturer(self, request, pk=None):
        """Clôture le folio en UNE facture ventes consolidée (NTHOT7)."""
        folio = self.get_object()
        try:
            services.cloturer_folio(folio, user=request.user)
        except services.FolioClotureError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(folio).data)


class TacheMenageViewSet(TenantMixin, viewsets.ModelViewSet):
    """Tâches de ménage (NTHOT9). Une femme/homme de chambre (rôle non
    responsable/admin) ne voit QUE ses tâches assignées ; Responsable/Admin
    voient tout (vue de pilotage). Filtre optionnel ``?statut=``."""
    queryset = TacheMenage.objects.select_related('chambre', 'assignee').all()
    serializer_class = TacheMenageSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['terminer']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_responsable:
            qs = qs.filter(assignee=user)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=True, methods=['post'], url_path='terminer')
    def terminer(self, request, pk=None):
        """Marque la tâche terminée — repasse la chambre à ``libre``."""
        tache = self.get_object()
        try:
            services.terminer_tache_menage(tache, user=request.user)
        except services.TacheMenageError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(tache).data)
