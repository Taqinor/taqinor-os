"""Vues des Ressources humaines (toutes scopées société, admin-gated).

Le module RH est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``). Les
viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la société
côté serveur ; le ``cout_horaire`` (paie/marge) ne quitte jamais cette API.
"""
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.records.models import Attachment
from apps.records.storage import delete_attachment, store_attachment
from authentication.mixins import TenantMixin
from authentication.permissions import HasPermission, IsResponsableOrAdmin

from . import selectors
from .models import (
    Departement,
    DocumentEmploye,
    DossierEmploye,
    Remuneration,
)
from .serializers import (
    DepartementSerializer,
    DocumentEmployeSerializer,
    DossierEmployeSerializer,
    RemunerationSerializer,
)


class _RhBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class DepartementViewSet(_RhBaseViewSet):
    """Départements de la société. Recherche par nom/code."""
    queryset = Departement.objects.all()
    serializer_class = DepartementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'code']
    ordering_fields = ['nom']


class DossierEmployeViewSet(_RhBaseViewSet):
    """Dossiers employés (DC29). Recherche par matricule/nom/prénom."""
    queryset = DossierEmploye.objects.select_related('departement', 'user').all()
    serializer_class = DossierEmployeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['matricule', 'nom', 'prenom', 'cin', 'email']
    ordering_fields = ['nom', 'prenom', 'matricule', 'date_embauche']

    @action(detail=False, methods=['get'], url_path='cdd-a-echeance')
    def cdd_a_echeance(self, request):
        """Alerte fin de CDD : dossiers en CDD dont la fin de contrat tombe
        dans les ``?within=`` prochains jours (défaut 30), scopés société.

        Exclut les CDI (et tout autre type), les CDD sans date de fin, ceux
        déjà expirés et ceux dont la fin dépasse la fenêtre. La société est
        garantie par ``get_queryset`` (TenantMixin) — jamais lue du corps.
        """
        try:
            within = int(request.query_params.get('within', 30))
        except (TypeError, ValueError):
            within = 30
        if within < 0:
            within = 0
        today = timezone.localdate()
        limite = today + timedelta(days=within)
        qs = self.get_queryset().filter(
            type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin__isnull=False,
            contrat_date_fin__gte=today,
            contrat_date_fin__lte=limite,
        ).order_by('contrat_date_fin')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class RemunerationViewSet(TenantMixin, viewsets.ModelViewSet):
    """Rémunération de base des employés (FG157) — paie SENSIBLE.

    Lecture ET écriture réservées aux porteurs de ``salaires_voir`` (palier RH) :
    sans cette permission tout accès est refusé (403). Société scopée
    (TenantMixin) et posée côté serveur. L'historique d'un employé s'obtient via
    ``?employe=<id>`` — les lignes sont triées de la plus récente à la plus
    ancienne (``date_effet`` décroissante), la première étant la rémunération en
    vigueur.
    """
    permission_classes = [HasPermission('salaires_voir')]
    queryset = Remuneration.objects.select_related('employe').all()
    serializer_class = RemunerationSerializer
    filter_backends = [filters.OrderingFilter]
    filterset_fields = ['employe']
    ordering_fields = ['date_effet', 'date_creation', 'montant']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        return qs


class DocumentEmployeViewSet(TenantMixin, viewsets.ModelViewSet):
    """Coffre documents employé (FG159) — pièces administratives d'un dossier.

    Accès calqué sur le dossier : Administrateur/Responsable uniquement
    (``IsResponsableOrAdmin``), société scopée + posée côté serveur (TenantMixin).
    Le fichier RÉUTILISE le stockage objet existant de ``records.Attachment``
    (``store_attachment`` → MinIO) : on ne construit aucun nouveau stockage. La
    création est multipart (``employe`` + ``file`` + ``type_document`` +
    ``date_expiration`` optionnelle) ; la liste d'un employé s'obtient via
    ``?employe=<id>``. La suppression efface la pièce jointe MinIO en cascade.
    """
    permission_classes = [IsResponsableOrAdmin]
    queryset = DocumentEmploye.objects.select_related(
        'employe', 'attachment').all()
    serializer_class = DocumentEmployeSerializer
    parser_classes = [MultiPartParser, JSONParser]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_expiration', 'date_creation', 'type_document']

    def get_queryset(self):
        qs = super().get_queryset()
        employe = self.request.query_params.get('employe')
        if employe:
            qs = qs.filter(employe_id=employe)
        type_document = self.request.query_params.get('type_document')
        if type_document:
            qs = qs.filter(type_document=type_document)
        return qs

    def create(self, request, *args, **kwargs):
        """Téléverse un fichier (MinIO via records.storage) puis enregistre le
        document. ``employe`` doit appartenir à la société ; ``company`` et la
        pièce jointe sont posées côté serveur (jamais lues du corps)."""
        company = request.user.company
        employe_id = request.data.get('employe')
        try:
            employe = DossierEmploye.objects.get(
                pk=employe_id, company=company)
        except (DossierEmploye.DoesNotExist, ValueError, TypeError):
            return Response({'employe': 'Employé inconnu.'},
                            status=status.HTTP_400_BAD_REQUEST)
        file = request.FILES.get('file')
        if not file:
            return Response({'file': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Valide les métadonnées (type/expiration) AVANT de toucher le stockage.
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        meta, err = store_attachment(file)
        if err:
            return Response({'file': err},
                            status=status.HTTP_400_BAD_REQUEST)
        # La pièce jointe records cible le dossier employé (ContentType) — même
        # modèle de stockage que toute autre pièce jointe, sans nouveau stockage.
        ct = ContentType.objects.get_for_model(DossierEmploye)
        attachment = Attachment.objects.create(
            company=company, content_type=ct, object_id=employe.id,
            uploaded_by=request.user, **meta)
        doc = DocumentEmploye.objects.create(
            company=company, employe=employe, attachment=attachment,
            type_document=ser.validated_data.get(
                'type_document', DocumentEmploye.TypeDocument.AUTRE),
            date_expiration=ser.validated_data.get('date_expiration'),
            note=ser.validated_data.get('note', ''))
        return Response(self.get_serializer(doc).data,
                        status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        # Efface le fichier MinIO puis le document (la pièce jointe part en
        # cascade via le OneToOne, mais on libère explicitement le stockage).
        att = instance.attachment
        instance.delete()
        if att is not None:
            delete_attachment(att.file_key)
            att.delete()

    @action(detail=False, methods=['get'], url_path='expirant-bientot')
    def expirant_bientot(self, request):
        """Documents de la société qui expirent dans les ``?within=`` prochains
        jours (défaut 30). S'appuie sur ``selectors.documents_expirant_bientot``
        — scopé société, exclut les documents sans échéance et déjà expirés."""
        within = request.query_params.get('within', 30)
        qs = selectors.documents_expirant_bientot(
            request.user.company, within_days=within)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
