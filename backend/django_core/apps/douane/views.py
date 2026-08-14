from rest_framework.exceptions import PermissionDenied, ValidationError

from core.viewsets import CompanyScopedModelViewSet

from .models import DossierExport, PieceDossierExport
from .serializers import DossierExportSerializer, PieceDossierExportSerializer
from .services import attribuer_numero_dossier_export


class DossierExportViewSet(CompanyScopedModelViewSet):
    """NTLOG14 — CRUD ``dossiers-export/`` + filtre ``?statut=``. ``numero``
    posé côté serveur (jamais lu du corps de la requête) via
    ``core.numbering``, JAMAIS ``count()+1`` (ARC6). Filtre manuel (pas de
    ``DjangoFilterBackend`` dans ce projet — défaut global :
    ``OrderingFilter``/``SearchFilter`` seulement, motif ``ao.
    PieceConsultationViewSet._filtres_exacts``)."""
    queryset = DossierExport.objects.all()
    serializer_class = DossierExportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _check_tenant(self, serializer):
        # ``devis``/``facture`` sont des string-FK cross-app en LECTURE
        # (jamais un import de leurs modèles) mais restent écrivables via
        # l'API : sans ce garde un id d'une AUTRE société lierait le dossier
        # à un devis/une facture étrangère (motif
        # ``installations.DossierImportViewSet._check_tenant``, FG315).
        company_id = self.request.user.company_id
        for field in ('devis', 'facture'):
            obj = serializer.validated_data.get(field)
            if obj is not None and getattr(obj, 'company_id', None) != company_id:
                raise ValidationError({field: 'Objet inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        instance = serializer.save(
            company=self.request.user.company, created_by=self.request.user)
        attribuer_numero_dossier_export(instance)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        super().perform_update(serializer)


class PieceDossierExportViewSet(CompanyScopedModelViewSet):
    """NTLOG14 — pièces d'un dossier d'export, filtrables par
    ``?dossier=<id>`` (motif ``pieces-consultation`` de ``apps.ao``). Scopage
    société standard (``CompanyScopedModelViewSet``) via la FK ``company``
    propre du modèle — voir la docstring de ``PieceDossierExport``."""
    queryset = PieceDossierExport.objects.all()
    serializer_class = PieceDossierExportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        dossier_id = self.request.query_params.get('dossier')
        if dossier_id:
            qs = qs.filter(dossier_id=dossier_id)
        return qs

    def perform_create(self, serializer):
        # Le `dossier` fourni par le client doit appartenir à la MÊME société
        # que l'utilisateur — sans ce garde, un id d'une AUTRE société créerait
        # une pièce reliée à un dossier étranger (isolation cassée), même si
        # la ligne PieceDossierExport elle-même reste correctement scopée.
        dossier = serializer.validated_data.get('dossier')
        user_company_id = self.request.user.company_id
        if dossier is not None and user_company_id and dossier.company_id != user_company_id:
            raise PermissionDenied("Dossier hors de votre société.")
        serializer.save(company=self.request.user.company)
