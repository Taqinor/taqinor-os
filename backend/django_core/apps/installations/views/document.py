"""Vues du contrôle documentaire de projet (FG297).

  * ``DocumentProjetViewSet`` : registre des documents techniques d'un chantier
    (schéma unifilaire, calepinage, note de calcul, autre). Filtrable par
    ``installation`` et ``type_doc``. Société posée côté serveur.
  * ``RevisionDocumentViewSet`` : révisions d'un document (indice, date,
    auteur, fichier). Filtrable par ``document``. Auteur + société posés côté
    serveur.

Toutes les vues sont multi-tenant via ``TenantMixin``."""
from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import DocumentProjet, RevisionDocument
from ..serializers import DocumentProjetSerializer, RevisionDocumentSerializer

READ_ACTIONS = ['list', 'retrieve']


def _check_installation_tenant(serializer, company):
    """Tenant safety : le chantier ciblé doit appartenir à la société du user."""
    cid = getattr(company, 'id', None)
    installation = serializer.validated_data.get('installation')
    if installation is not None and installation.company_id != cid:
        raise ValidationError({'installation': 'Chantier inconnu.'})


def _check_document_tenant(serializer, company):
    """Tenant safety : le document ciblé doit appartenir à la société du user."""
    cid = getattr(company, 'id', None)
    document = serializer.validated_data.get('document')
    if document is not None and document.company_id != cid:
        raise ValidationError({'document': 'Document inconnu.'})


class DocumentProjetViewSet(CompanyScopedModelViewSet):
    """FG297 — registre des documents techniques d'un chantier. Lecture tout
    rôle, écriture responsable/admin. Filtrable par ``installation`` et
    ``type_doc``. Société posée côté serveur, jamais lue du corps."""
    queryset = DocumentProjet.objects.prefetch_related(
        'inst_revisions__auteur').select_related('installation').all()
    serializer_class = DocumentProjetSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        installation = self.request.query_params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        type_doc = self.request.query_params.get('type_doc')
        if type_doc:
            qs = qs.filter(type_doc=type_doc)
        return qs

    def perform_create(self, serializer):
        _check_installation_tenant(serializer, self.request.user.company)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        _check_installation_tenant(serializer, self.request.user.company)
        serializer.save(company=self.request.user.company)


class RevisionDocumentViewSet(CompanyScopedModelViewSet):
    """FG297 — révisions d'un document de projet (indice, date, auteur,
    fichier). Lecture tout rôle, écriture responsable/admin. Filtrable par
    ``document``. Auteur + société posés côté serveur, jamais lus du corps."""
    queryset = RevisionDocument.objects.select_related(
        'document', 'auteur', 'fichier').all()
    serializer_class = RevisionDocumentSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        return qs

    def perform_create(self, serializer):
        _check_document_tenant(serializer, self.request.user.company)
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)

    def perform_update(self, serializer):
        _check_document_tenant(serializer, self.request.user.company)
        serializer.save(company=self.request.user.company)
