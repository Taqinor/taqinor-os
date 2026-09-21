"""Vues du module Immobilier (scopées société via ``TenantMixin``).

Aucune permission fine dédiée (comme ``apps.flotte``) : ``IsAuthenticated``
(défaut DRF global) suffit pour ce premier lot — une gate fine pourra être
ajoutée plus tard sans changer la forme des endpoints.
"""
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from core.permissions import ScopedPermission
from core.viewsets import CompanyScopedModelViewSet

from .models import (
    Bail, Batiment, BudgetCharges, DepenseCharges, EcheanceLoyer,
    ElementEtatLieux, EtatLieuxImmo, Local, Locataire, Niveau,
    PhotoEtatLieux, PieceEtatLieux, RegularisationCharges, RelanceLoyer, Site,
)
from .serializers import (
    BailSerializer, BatimentSerializer, BudgetChargesSerializer,
    DepenseChargesSerializer, EcheanceLoyerSerializer, ElementEtatLieuxSerializer,
    EtatLieuxImmoSerializer, LocalSerializer, LocataireSerializer,
    NiveauSerializer, PhotoEtatLieuxSerializer, PieceEtatLieuxSerializer,
    RegularisationChargesSerializer, RelanceLoyerSerializer,
    RevisionLoyerSerializer, SiteSerializer,
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

    @action(detail=True, methods=['get'], url_path='repartition-charges',
            permission_classes=[ScopedPermission])
    def repartition_charges(self, request, pk=None):
        """NTPRO12 — Répartition des dépenses réelles de charges par local
        occupé (tantièmes ou surface selon ``mode_repartition``)."""
        from . import services

        batiment = self.get_object()
        exercice = request.query_params.get('exercice')
        if not exercice:
            return Response(
                {'detail': 'Le paramètre exercice est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        data = services.repartir_charges(batiment, int(exercice))
        return Response(data)

    @action(detail=True, methods=['post'], url_path='generer-regularisation',
            permission_classes=[ScopedPermission])
    def generer_regularisation(self, request, pk=None):
        """NTPRO13 — Génère/recalcule la régularisation annuelle des charges
        de chaque bail actif du bâtiment pour ``exercice`` (idempotent)."""
        from . import services

        batiment = self.get_object()
        exercice = request.data.get('exercice')
        if not exercice:
            return Response(
                {'detail': 'exercice est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        resultats = services.generer_regularisation(batiment, int(exercice))
        return Response(
            RegularisationChargesSerializer(resultats, many=True).data,
            status=status.HTTP_201_CREATED)


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

    @action(detail=True, methods=['get'],
            permission_classes=[ScopedPermission])
    def consommation(self, request, pk=None):
        """NTPRO11 — Total consommé (dépenses réelles) vs budgété, écart %."""
        from . import selectors

        budget = self.get_object()
        return Response(selectors.consommation_budget(budget))


class DepenseChargesViewSet(_ImmobilierBaseViewSet):
    """NTPRO11 — Dépenses réelles de charges rattachées à un budget."""
    queryset = DepenseCharges.objects.select_related(
        'budget_charges', 'budget_charges__batiment').all()
    serializer_class = DepenseChargesSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        budget_id = self.request.query_params.get('budget_charges')
        if budget_id:
            qs = qs.filter(budget_charges_id=budget_id)
        return qs


class RegularisationChargesViewSet(_ImmobilierBaseViewSet):
    """NTPRO13 — Régularisations de charges (LECTURE seule côté API : une
    ligne naît TOUJOURS de `batiments/{id}/generer-regularisation/`)."""
    queryset = RegularisationCharges.objects.select_related(
        'bail', 'bail__local', 'bail__locataire').all()
    serializer_class = RegularisationChargesSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['exercice', 'date_creation']
    http_method_names = ['get', 'head', 'options', 'post']

    def get_queryset(self):
        qs = super().get_queryset()
        bail_id = self.request.query_params.get('bail')
        exercice = self.request.query_params.get('exercice')
        sens = self.request.query_params.get('sens')
        if bail_id:
            qs = qs.filter(bail_id=bail_id)
        if exercice:
            qs = qs.filter(exercice=exercice)
        if sens:
            qs = qs.filter(sens=sens)
        return qs

    def create(self, request, *args, **kwargs):
        # Aucune création directe : une RegularisationCharges naît TOUJOURS
        # de `batiments/{id}/generer-regularisation/`.
        return Response(
            {'detail': "Utiliser batiments/{id}/generer-regularisation/."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=True, methods=['post'],
            permission_classes=[ScopedPermission])
    def emettre(self, request, pk=None):
        """NTPRO13 — Émet le document ventes (facture ou avoir) correspondant
        au sens de la régularisation. Neutre → aucun document, 200 no-op."""
        from . import services

        regularisation = self.get_object()
        try:
            document_id = services.emettre_regularisation(regularisation)
        except services.ClientVentesIntrouvableError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data = self.get_serializer(regularisation).data
        data['document_ventes_id'] = document_id
        return Response(data, status=status.HTTP_200_OK)


class EtatLieuxImmoViewSet(_ImmobilierBaseViewSet):
    """NTPRO15 — États des lieux (entrée/sortie) d'un bail, pré-remplis
    depuis la grille standard du type de local à la création."""
    queryset = EtatLieuxImmo.objects.select_related(
        'bail', 'bail__local').prefetch_related('pieces__elements').all()
    serializer_class = EtatLieuxImmoSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        bail_id = self.request.query_params.get('bail')
        moment = self.request.query_params.get('moment')
        if bail_id:
            qs = qs.filter(bail_id=bail_id)
        if moment:
            qs = qs.filter(moment=moment)
        return qs

    def create(self, request, *args, **kwargs):
        """NTPRO15 — Crée l'état des lieux PRÉ-REMPLI (grille standard) via
        ``services.creer_etat_lieux`` : jamais un POST libre qui contournerait
        le pré-remplissage."""
        from . import services

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bail = serializer.validated_data['bail']
        etat_lieux = services.creer_etat_lieux(
            bail, serializer.validated_data['moment'],
            technicien=serializer.validated_data.get('technicien'),
            date=serializer.validated_data.get('date'))
        out = self.get_serializer(etat_lieux)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'],
            url_path=r'elements/(?P<element_id>[^/.]+)/photos',
            parser_classes=[MultiPartParser, FormParser, JSONParser],
            permission_classes=[ScopedPermission])
    def ajouter_photo(self, request, pk=None, element_id=None):
        """NTPRO16 — Téléverse une photo (multipart, champ ``photo``) sur un
        élément de CET état des lieux (borné à la société via
        ``get_object``, puis l'élément est cherché dans SES pièces — jamais
        un id d'élément d'un autre état des lieux)."""
        from . import services

        etat_lieux = self.get_object()
        try:
            element = ElementEtatLieux.objects.get(
                pk=element_id, piece__etat_lieux=etat_lieux)
        except (ElementEtatLieux.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Élément introuvable pour cet état des lieux.'},
                status=status.HTTP_404_NOT_FOUND)

        file = request.FILES.get('photo') or request.FILES.get('file')
        if not file:
            return Response(
                {'detail': 'Le fichier photo est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            photo = services.ajouter_photo_element(
                element, file, uploaded_by=request.user)
        except services.PhotoInvalideError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PhotoEtatLieuxSerializer(photo).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'],
            url_path=r'photos/(?P<photo_id>[^/.]+)/download',
            permission_classes=[ScopedPermission])
    def telecharger_photo(self, request, pk=None, photo_id=None):
        """NTPRO16 — Proxy même-origine (comme `ged.DocumentVersion.apercu`)
        pour servir les octets d'une photo sans exposer l'hôte MinIO
        interne. Bornée à cet état des lieux (jamais une photo d'un autre)."""
        from django.http import HttpResponse

        from apps.records.storage import fetch_attachment

        etat_lieux = self.get_object()
        try:
            photo = PhotoEtatLieux.objects.get(
                pk=photo_id, element__piece__etat_lieux=etat_lieux)
        except (PhotoEtatLieux.DoesNotExist, ValueError):
            return Response(
                {'detail': 'Photo introuvable pour cet état des lieux.'},
                status=status.HTTP_404_NOT_FOUND)

        data, err = fetch_attachment(photo.file_key)
        if err:
            return Response({'detail': err}, status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(
            data, content_type=photo.mime or 'application/octet-stream')
        safe_name = (photo.filename or 'photo').replace('"', '')
        response['Content-Disposition'] = f'inline; filename="{safe_name}"'
        return response


class PieceEtatLieuxViewSet(_ImmobilierBaseViewSet):
    """NTPRO15 — Pièces inspectées (créées automatiquement via la grille
    standard — pas de création directe, seulement lecture/mise à jour de
    l'état/commentaire relevés sur le terrain)."""
    queryset = PieceEtatLieux.objects.select_related('etat_lieux').all()
    serializer_class = PieceEtatLieuxSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre']
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        etat_lieux_id = self.request.query_params.get('etat_lieux')
        if etat_lieux_id:
            qs = qs.filter(etat_lieux_id=etat_lieux_id)
        return qs


class ElementEtatLieuxViewSet(_ImmobilierBaseViewSet):
    """NTPRO15 — Éléments inspectés (créés automatiquement via la grille
    standard — pas de création directe, seulement lecture/mise à jour de
    l'état/commentaire relevés sur le terrain)."""
    queryset = ElementEtatLieux.objects.select_related('piece').all()
    serializer_class = ElementEtatLieuxSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre']
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        piece_id = self.request.query_params.get('piece')
        if piece_id:
            qs = qs.filter(piece_id=piece_id)
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
