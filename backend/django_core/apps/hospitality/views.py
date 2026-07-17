"""Vues du module Hôtellerie & restauration.

Les viewsets filtrent par ``request.user.company`` (``TenantMixin``) et posent
la société côté serveur (jamais du corps de requête). Lecture ouverte à tout
rôle authentifié (``IsAnyRole``) ; écriture réservée Responsable/Admin
(``IsResponsableOrAdmin``), sauf actions explicitement ouvertes (ex. tâches de
housekeeping assignées à l'utilisateur courant).
"""
import datetime

from django.shortcuts import get_object_or_404
from rest_framework import filters, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from . import selectors, services
from .models import (
    Chambre, EvenementBanquet, Folio, IngredientRecette, MainCourante,
    PlanTarifaire, Recette, Reservation, SalleEvenement, TacheMenage,
    TypeChambre,
)
from .serializers import (
    ChambreSerializer, EvenementBanquetSerializer, FicheClientSerializer,
    FolioSerializer, IngredientRecetteSerializer, MainCouranteSerializer,
    PlanTarifaireSerializer, RecetteSerializer, ReservationSerializer,
    SalleEvenementSerializer, TacheMenageSerializer, TypeChambreSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class TypeChambreViewSet(CompanyScopedModelViewSet):
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


class ChambreViewSet(CompanyScopedModelViewSet):
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


class PlanTarifaireViewSet(CompanyScopedModelViewSet):
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


class ReservationViewSet(CompanyScopedModelViewSet):
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

    def perform_update(self, serializer):
        """NTHOT3 — un PATCH/PUT peut modifier ``chambre``/``date_arrivee``/
        ``date_depart`` : la garde de chevauchement (posée seulement à la
        création via ``creer_reservation``) DOIT être ré-appliquée ici, sinon
        une mise à jour double-réserverait une chambre ou la re-pointerait vers
        une chambre d'une autre société. La société des FK est aussi revérifiée
        (défense en profondeur, en plus des ``validate_*`` du sérialiseur)."""
        instance = serializer.instance
        company = self.request.user.company
        v = serializer.validated_data
        chambre = v.get('chambre', instance.chambre)
        type_chambre = v.get('type_chambre', instance.type_chambre)
        for obj, label in ((chambre, 'chambre'), (type_chambre, 'type_chambre')):
            if obj is not None and obj.company_id != company.id:
                raise ValidationError(
                    {label: f"{label} introuvable pour votre société."})
        date_arrivee = v.get('date_arrivee', instance.date_arrivee)
        date_depart = v.get('date_depart', instance.date_depart)
        try:
            services.check_reservation_overlap(
                chambre, date_arrivee, date_depart, exclude_id=instance.pk)
        except services.ReservationOverlapError as exc:
            raise ValidationError({'chambre': str(exc)})
        serializer.save()

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
    # NB : ne PAS surcharger ``get_permissions`` ici — le comportement DRF par
    # défaut lit ``self.permission_classes`` (posé par ViewSetMixin depuis le
    # kwarg ``permission_classes=`` de ``@action`` AVANT l'appel), donc la
    # classe reste la lecture par défaut et l'action ``cloturer`` ci-dessous
    # applique correctement son ``IsResponsableOrAdmin`` propre. Un
    # ``get_permissions`` inconditionnel écraserait cet override d'action
    # (bug réel déjà documenté sur ``WriteScopedPermissionMixin``).
    permission_classes = [IsAnyRole]

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


class TacheMenageViewSet(CompanyScopedModelViewSet):
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


class MainCouranteViewSet(CompanyScopedModelViewSet):
    """NTHOT12 — Main courante / passations d'équipe. Journal APPEND-ONLY :
    seuls list/retrieve/create sont exposés (une note n'est ni modifiée ni
    supprimée — intégrité du journal). Lecture/écriture ouvertes à tout rôle
    authentifié (saisie rapide depuis n'importe quel écran)."""
    queryset = MainCourante.objects.select_related('auteur').all()
    serializer_class = MainCouranteSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_note']

    def get_permissions(self):
        return [IsAnyRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        categorie = params.get('categorie')
        if categorie:
            qs = qs.filter(categorie=categorie)
        date = params.get('date')
        if date:
            qs = qs.filter(date_note__date=date)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)


class RecetteViewSet(CompanyScopedModelViewSet):
    """NTHOT13 — Cartes/menus (recettes), CRUD scopé société avec
    sous-ressource ``ingredients`` (GET liste / POST ajoute ; DELETE sur
    ``ingredients/{ingredient_id}/`` retire une ligne)."""
    queryset = Recette.objects.prefetch_related('ingredients__produit').all()
    serializer_class = RecetteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom_plat']
    ordering_fields = ['nom_plat', 'prix_vente_ht']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['ingredients']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=True, methods=['get', 'post'], url_path='ingredients')
    def ingredients(self, request, pk=None):
        recette = self.get_object()
        if request.method == 'POST':
            if not request.user.is_responsable:
                return Response(
                    {'detail': "Réservé aux rôles Responsable/Administrateur."},
                    status=status.HTTP_403_FORBIDDEN)
            serializer = IngredientRecetteSerializer(
                data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            ingredient = IngredientRecette.objects.create(
                recette=recette, **serializer.validated_data)
            return Response(
                IngredientRecetteSerializer(ingredient).data,
                status=status.HTTP_201_CREATED)
        return Response(
            IngredientRecetteSerializer(
                recette.ingredients.all(), many=True).data)

    @action(detail=True, methods=['delete'],
            url_path=r'ingredients/(?P<ingredient_id>\d+)',
            permission_classes=[IsResponsableOrAdmin])
    def ingredient_delete(self, request, pk=None, ingredient_id=None):
        recette = self.get_object()
        ingredient = get_object_or_404(
            IngredientRecette, pk=ingredient_id, recette=recette)
        ingredient.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SalleEvenementViewSet(CompanyScopedModelViewSet):
    """NTHOT18 — Salles événementielles, CRUD scopé société."""
    queryset = SalleEvenement.objects.all()
    serializer_class = SalleEvenementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom', 'capacite_max']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class EvenementBanquetViewSet(CompanyScopedModelViewSet):
    """NTHOT17/NTHOT18 — Événements/banquets. La création/mise à jour passe
    par ``services.creer_evenement``/la garde de chevauchement de salle
    (NTHOT18, uniquement entre événements ``confirme``)."""
    queryset = EvenementBanquet.objects.select_related(
        'salle', 'client', 'lead').prefetch_related('menu_recettes').all()
    serializer_class = EvenementBanquetSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_fin', 'date_creation']

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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        try:
            evenement = services.creer_evenement(
                company=request.user.company,
                user=request.user,
                nom_evenement=v['nom_evenement'],
                date_debut=v['date_debut'],
                date_fin=v['date_fin'],
                nb_convives=v.get('nb_convives', 0),
                salle=v.get('salle'),
                statut=v.get('statut', EvenementBanquet.Statut.BROUILLON),
                client_id=v.get('client_id'),
                lead_id=v.get('lead_id'),
            )
        except services.SalleOverlapError as exc:
            return Response(
                {'salle': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        menu_recettes = v.get('menu_recettes')
        if menu_recettes:
            evenement.menu_recettes.set(menu_recettes)
        out = self.get_serializer(evenement)
        headers = self.get_success_headers(out.data)
        return Response(
            out.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        """Ré-applique la garde de chevauchement de salle sur mise à jour
        (même raisonnement que ``ReservationViewSet.perform_update``,
        NTHOT3) : un PATCH qui change ``salle``/``date_debut``/``date_fin``/
        ``statut`` DOIT être re-validé."""
        instance = serializer.instance
        company = self.request.user.company
        v = serializer.validated_data
        salle = v.get('salle', instance.salle)
        if salle is not None and salle.company_id != company.id:
            raise ValidationError({'salle': 'Salle introuvable pour votre société.'})
        date_debut = v.get('date_debut', instance.date_debut)
        date_fin = v.get('date_fin', instance.date_fin)
        statut = v.get('statut', instance.statut)
        if statut == EvenementBanquet.Statut.CONFIRME:
            try:
                services.check_salle_overlap(
                    salle, date_debut, date_fin, exclude_id=instance.pk)
            except services.SalleOverlapError as exc:
                raise ValidationError({'salle': str(exc)})
        serializer.save()

    # ── NTHOT17 — Génération du devis d'événement (flux devis existant) ─────
    @action(detail=True, methods=['post'], url_path='generer-devis',
            permission_classes=[IsResponsableOrAdmin])
    def generer_devis(self, request, pk=None):
        """Génère UN Devis ventes brouillon pour cet événement (rule #4 :
        jamais un moteur de devis parallèle, jamais un PDF alternatif)."""
        evenement = self.get_object()
        try:
            devis = services.generer_devis_evenement(
                evenement, user=request.user)
        except services.GenerationDevisEvenementError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                'devis_id': devis.id,
                'devis_reference': devis.reference,
                **self.get_serializer(evenement).data,
            },
            status=status.HTTP_200_OK)


class TableauBordView(views.APIView):
    """NTHOT11 — Tableau de bord RevPAR/ADR/TO. ``?debut=&fin=`` (YYYY-MM-DD,
    fin exclusive) ; défaut = les 30 derniers jours."""
    permission_classes = [IsAnyRole]

    def get(self, request):
        today = datetime.date.today()
        debut_str = request.query_params.get('debut')
        fin_str = request.query_params.get('fin')
        try:
            debut = (
                datetime.date.fromisoformat(debut_str) if debut_str
                else today - datetime.timedelta(days=30))
            fin = datetime.date.fromisoformat(fin_str) if fin_str else today
        except ValueError:
            return Response(
                {'detail': 'Dates invalides (attendu YYYY-MM-DD).'},
                status=status.HTTP_400_BAD_REQUEST)
        data = selectors.dashboard_hotellerie(
            request.user.company, debut, fin)
        return Response(data)
