"""Vues du module Immobilier (scopées société via ``TenantMixin``).

Aucune permission fine dédiée (comme ``apps.flotte``) : ``IsAuthenticated``
(défaut DRF global) suffit pour ce premier lot — une gate fine pourra être
ajoutée plus tard sans changer la forme des endpoints.
"""
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import ScopedPermission
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    Bail, Batiment, BudgetCharges, EcheanceLoyer, Local, Locataire, Niveau,
    RelanceLoyer, Site,
)
from .serializers import (
    BailSerializer, BatimentSerializer, BudgetChargesSerializer,
    EcheanceLoyerSerializer, LocalSerializer, LocataireSerializer,
    NiveauSerializer, RelanceLoyerSerializer, RevisionLoyerSerializer,
    SiteSerializer,
)


class _ImmobilierBaseViewSet(CompanyScopedModelViewSet):
    """Base commune : société scopée (get_queryset + perform_create/update)."""
    pass


class SiteViewSet(_ImmobilierBaseViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'ville']
    ordering_fields = ['nom', 'date_creation']

    @action(detail=True, methods=['get'],
            permission_classes=[ScopedPermission])
    def rentabilite(self, request, pk=None):
        """NTPRO9 — Rentabilité agrégée du site (revenus - charges - travaux)."""
        from . import selectors

        site = self.get_object()
        data = selectors.rentabilite_actif(
            request.user.company, site_id=site.id,
            periode=request.query_params.get('periode'))
        return Response(data)


class BatimentViewSet(_ImmobilierBaseViewSet):
    queryset = Batiment.objects.select_related('site').all()
    serializer_class = BatimentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom']

    def get_queryset(self):
        qs = super().get_queryset()
        site_id = self.request.query_params.get('site')
        if site_id:
            qs = qs.filter(site_id=site_id)
        return qs

    @action(detail=True, methods=['get'],
            permission_classes=[ScopedPermission])
    def rentabilite(self, request, pk=None):
        """NTPRO9 — Rentabilité agrégée du bâtiment (revenus - charges - travaux)."""
        from . import selectors

        batiment = self.get_object()
        data = selectors.rentabilite_actif(
            request.user.company, batiment_id=batiment.id,
            periode=request.query_params.get('periode'))
        return Response(data)


class NiveauViewSet(_ImmobilierBaseViewSet):
    queryset = Niveau.objects.select_related('batiment').all()
    serializer_class = NiveauSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero', 'ordre']

    def get_queryset(self):
        qs = super().get_queryset()
        batiment_id = self.request.query_params.get('batiment')
        if batiment_id:
            qs = qs.filter(batiment_id=batiment_id)
        return qs


class LocalViewSet(_ImmobilierBaseViewSet):
    queryset = Local.objects.select_related('niveau', 'niveau__batiment').all()
    serializer_class = LocalSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference']
    ordering_fields = ['reference']

    def get_queryset(self):
        qs = super().get_queryset()
        niveau_id = self.request.query_params.get('niveau')
        batiment_id = self.request.query_params.get('batiment')
        site_id = self.request.query_params.get('site')
        statut = self.request.query_params.get('statut')
        if niveau_id:
            qs = qs.filter(niveau_id=niveau_id)
        if batiment_id:
            qs = qs.filter(niveau__batiment_id=batiment_id)
        if site_id:
            qs = qs.filter(niveau__batiment__site_id=site_id)
        if statut:
            qs = qs.filter(statut=statut)
        return qs


class LocataireViewSet(_ImmobilierBaseViewSet):
    """NTPRO2 — Locataires (personnes/sociétés), distincts du CRM."""
    queryset = Locataire.objects.all()
    serializer_class = LocataireSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'cin', 'ice']
    ordering_fields = ['nom', 'date_creation']

    def perform_create(self, serializer):
        from . import services
        locataire = serializer.save(company=self.request.user.company)
        # Best-effort : relie à un crm.Client existant sans jamais en créer un
        # nouveau (NTPRO2). Un échec de résolution ne bloque jamais la création
        # du locataire.
        try:
            services.resolve_client_ventes_for_locataire(locataire)
        except Exception:
            pass
        return locataire

    @action(detail=True, methods=['post'], url_path='resolve-client',
            permission_classes=[ScopedPermission])
    def resolve_client(self, request, pk=None):
        """Relance la résolution vers un ``crm.Client`` existant (idempotent)."""
        from . import services
        locataire = self.get_object()
        client_id = services.resolve_client_ventes_for_locataire(locataire)
        return Response({'client_ventes_id': client_id})


class BailViewSet(_ImmobilierBaseViewSet):
    """NTPRO3 — Baux (habitation loi 67-12 / commercial loi 49-16)."""
    queryset = Bail.objects.select_related('local', 'locataire').all()
    serializer_class = BailSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_debut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        local_id = self.request.query_params.get('local')
        locataire_id = self.request.query_params.get('locataire')
        statut = self.request.query_params.get('statut')
        if local_id:
            qs = qs.filter(local_id=local_id)
        if locataire_id:
            qs = qs.filter(locataire_id=locataire_id)
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        from . import services

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        local = serializer.validated_data.pop('local')
        locataire = serializer.validated_data.pop('locataire')
        try:
            bail = services.creer_bail(
                company=request.user.company, local=local,
                locataire=locataire, **serializer.validated_data)
        except services.BailActifExistantError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        out = self.get_serializer(bail)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def reviser(self, request, pk=None):
        """NTPRO4 — Révision de loyer indexée (body: nouveau_loyer, date_effet)."""
        from . import services

        bail = self.get_object()
        nouveau_loyer = request.data.get('nouveau_loyer')
        date_effet = request.data.get('date_effet')
        if not nouveau_loyer or not date_effet:
            return Response(
                {'detail': 'nouveau_loyer et date_effet sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        revision = services.appliquer_revision(
            bail, nouveau_loyer, date_effet,
            indice=request.data.get('indice', ''))
        return Response(
            RevisionLoyerSerializer(revision).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='encaisser-depot',
            permission_classes=[ScopedPermission])
    def encaisser_depot(self, request, pk=None):
        """NTPRO5 — Marque le dépôt de garantie comme reçu."""
        from . import services

        bail = self.get_object()
        services.encaisser_depot(
            bail, date_reception=request.data.get('date_reception'))
        return Response(self.get_serializer(bail).data)

    @action(detail=True, methods=['post'], url_path='restituer-depot',
            permission_classes=[ScopedPermission])
    def restituer_depot(self, request, pk=None):
        """NTPRO5 — Restitue le dépôt de garantie (jamais plus que le dépôt initial)."""
        from . import services

        bail = self.get_object()
        try:
            services.restituer_depot(
                bail,
                montant_retenu=request.data.get('montant_retenu', 0),
                motif_retenue=request.data.get('motif_retenue', ''),
                date_restitution=request.data.get('date_restitution'))
        except services.DepotGarantieError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data = self.get_serializer(bail).data
        data['montant_restitue'] = str(services.montant_restitue_depot(bail))
        return Response(data)

    @action(detail=True, methods=['post'], url_path='generer-echeancier',
            permission_classes=[ScopedPermission])
    def generer_echeancier(self, request, pk=None):
        """NTPRO6 — Génère l'échéancier mensuel du bail (idempotent)."""
        from . import services

        bail = self.get_object()
        creees = services.generer_echeancier(bail)
        return Response(
            EcheanceLoyerSerializer(creees, many=True).data,
            status=status.HTTP_201_CREATED)


class EcheanceLoyerViewSet(_ImmobilierBaseViewSet):
    """NTPRO6/7/8 — Échéances de loyer (échéancier + quittancement + impayés)."""
    queryset = EcheanceLoyer.objects.select_related(
        'bail', 'bail__local', 'bail__locataire').all()
    serializer_class = EcheanceLoyerSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['periode_debut', 'date_creation']

    def create(self, request, *args, **kwargs):
        # Aucune création directe : une EcheanceLoyer naît TOUJOURS de
        # ``services.generer_echeancier`` (Bail.generer-echeancier), jamais
        # d'un POST libre qui contournerait l'idempotence/unique_together.
        return Response(
            {'detail': "Utiliser baux/{id}/generer-echeancier/."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def get_queryset(self):
        qs = super().get_queryset()
        bail_id = self.request.query_params.get('bail')
        statut = self.request.query_params.get('statut')
        if bail_id:
            qs = qs.filter(bail_id=bail_id)
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @action(detail=True, methods=['post'], url_path='emettre-quittance',
            permission_classes=[ScopedPermission])
    def emettre_quittance(self, request, pk=None):
        """NTPRO7 — Émet la quittance (facture ventes) de cette échéance."""
        from . import services

        echeance = self.get_object()
        try:
            facture_id = services.emettre_quittance(echeance)
        except services.ClientVentesIntrouvableError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data = self.get_serializer(echeance).data
        data['facture_ventes_id'] = facture_id
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='quittance-pdf',
            permission_classes=[ScopedPermission])
    def quittance_pdf(self, request, pk=None):
        """NTPRO7 — PDF de la quittance (période/local/locataire/montant)."""
        from django.http import HttpResponse

        from . import pdf as immobilier_pdf

        echeance = self.get_object()
        pdf_bytes = immobilier_pdf.render_quittance_pdf(echeance)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="quittance-{echeance.id}.pdf"')
        return response

    @action(detail=False, methods=['get'],
            permission_classes=[ScopedPermission])
    def impayees(self, request):
        """NTPRO8 — Tableau des échéances impayées (locataire, montant, jours
        de retard), lu via ``apps.ventes.selectors`` (jamais un modèle
        Paiement dupliqué ici)."""
        from . import selectors

        data = selectors.echeances_impayees(request.user.company)
        return Response(data)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def relancer(self, request, pk=None):
        """NTPRO8 — Enregistre une relance d'impayé (incrémente le niveau)."""
        from . import services

        echeance = self.get_object()
        relance = services.relancer_echeance(
            echeance, canal=request.data.get('canal'),
            template_utilise=request.data.get('template_utilise', ''))
        return Response(
            RelanceLoyerSerializer(relance).data,
            status=status.HTTP_201_CREATED)


class BudgetChargesViewSet(_ImmobilierBaseViewSet):
    """NTPRO10 — Budget de charges par bâtiment/exercice/poste."""
    queryset = BudgetCharges.objects.select_related('batiment').all()
    serializer_class = BudgetChargesSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['exercice', 'poste', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        batiment_id = self.request.query_params.get('batiment')
        exercice = self.request.query_params.get('exercice')
        if batiment_id:
            qs = qs.filter(batiment_id=batiment_id)
        if exercice:
            qs = qs.filter(exercice=exercice)
        return qs


class RelanceLoyerViewSet(_ImmobilierBaseViewSet):
    """NTPRO8 — Relances d'impayé sur échéances de loyer (lecture seule côté
    API : une relance naît TOUJOURS de ``echeances-loyer/{id}/relancer/``)."""
    queryset = RelanceLoyer.objects.select_related('echeance_loyer').all()
    serializer_class = RelanceLoyerSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_envoi']
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        echeance_id = self.request.query_params.get('echeance_loyer')
        if echeance_id:
            qs = qs.filter(echeance_loyer_id=echeance_id)
        return qs
