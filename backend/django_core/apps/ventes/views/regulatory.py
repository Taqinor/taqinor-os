"""FG268-FG271 — ViewSets du dossier réglementaire de raccordement (ventes).

Multi-tenancy : ``company`` TOUJOURS forcée côté serveur (dérivée du devis lié,
borné à la société de l'utilisateur), jamais lue du corps. Querysets filtrés par
``request.user.company``. Couche additive : ne touche ni le PDF premium ni
`/proposal`, et ne change aucun statut de devis (RULE #4). Aucun prix exposé.
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet  # ARC5
from ..models import (
    RegulatoryDossier, DossierChecklistItem, DossierExchange,
    SubventionDossier, Regularisation8221,
)
from ..serializers_regulatory import (
    RegulatoryDossierSerializer, DossierChecklistItemSerializer,
    DossierExchangeSerializer, SubventionDossierSerializer,
    Regularisation8221Serializer,
)
from .. import regulatory_docs

READ_ACTIONS = ['list', 'retrieve']

# Affectation par défaut de chaque code de pièce à une étape de soumission.
_PIECE_ETAPE = {
    'etude_raccordement': 'etude',
    'etude_impact_reseau': 'etude',
    'convention_raccordement': 'convention',
    'attestation_conformite': 'comptage',
}


def _company_or_none(user):
    return getattr(user, 'company', None)


class RegulatoryDossierViewSet(CompanyScopedModelViewSet):
    # ARC5 — sweep TenantMixin : base transverse unique (idem pour les 5 viewsets
    # de ce module). get_queryset / perform_create / perform_update /
    # get_permissions SURCHARGENT la base (scoping direct sur `company`) : scoping
    # et matrice 401/403/404 INCHANGÉS (règle #4 : couche additive, aucun statut
    # de devis touché, aucun prix exposé).
    """FG268 — CRUD dossier réglementaire + génération de checklist par régime."""

    queryset = RegulatoryDossier.objects.select_related(
        'devis', 'chantier', 'created_by').prefetch_related(
        'checklist_items').all()
    serializer_class = RegulatoryDossierSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        devis_id = self.request.query_params.get('devis')
        if devis_id:
            qs = qs.filter(devis_id=devis_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _resolve_company(self, devis):
        user = self.request.user
        company = _company_or_none(user)
        if devis is not None:
            if company is not None and devis.company_id != company.id:
                raise ValidationError({'devis': 'Devis inconnu.'})
            return devis.company
        if company is None:
            raise ValidationError(
                {'company': "Aucune société : impossible de créer le dossier."})
        return company

    def perform_create(self, serializer):
        devis = serializer.validated_data.get('devis')
        company = self._resolve_company(devis)
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        devis = serializer.validated_data.get(
            'devis', serializer.instance.devis)
        company = self._resolve_company(devis)
        serializer.save(company=company)

    @action(detail=True, methods=['post'], url_path='generer-checklist')
    def generer_checklist(self, request, pk=None):
        """POST /{id}/generer-checklist/ — crée les pièces manquantes du régime.

        Idempotent : n'ajoute que les codes absents (jamais de doublon, jamais
        de suppression). Aucun changement de statut de devis."""
        dossier = self.get_object()
        pack = regulatory_docs.required_documents(dossier.regime_8221)
        existing = set(
            dossier.checklist_items.values_list('code', flat=True))
        created = 0
        for ordre, piece in enumerate(pack):
            code = piece['code']
            if code in existing:
                continue
            DossierChecklistItem.objects.create(
                company=dossier.company, dossier=dossier, code=code,
                libelle=piece['label'], obligatoire=piece.get('required', True),
                etape=_PIECE_ETAPE.get(code, 'depot'), ordre=ordre)
            created += 1
        dossier.refresh_from_db()
        return Response(
            {'created': created,
             'dossier': self.get_serializer(dossier).data},
            status=status.HTTP_200_OK)


class DossierChecklistItemViewSet(CompanyScopedModelViewSet):  # ARC5 (voir note ci-dessus)
    """FG268 — CRUD pièces/étapes de checklist (scopé société)."""

    queryset = DossierChecklistItem.objects.select_related('dossier').all()
    serializer_class = DossierChecklistItemSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        dossier_id = self.request.query_params.get('dossier')
        if dossier_id:
            qs = qs.filter(dossier_id=dossier_id)
        return qs

    def _resolve_company(self, dossier):
        user = self.request.user
        company = _company_or_none(user)
        if dossier is None:
            raise ValidationError({'dossier': 'Dossier requis.'})
        if company is not None and dossier.company_id != company.id:
            raise ValidationError({'dossier': 'Dossier inconnu.'})
        return dossier.company

    def perform_create(self, serializer):
        dossier = serializer.validated_data.get('dossier')
        company = self._resolve_company(dossier)
        serializer.save(company=company)

    def perform_update(self, serializer):
        dossier = serializer.validated_data.get(
            'dossier', serializer.instance.dossier)
        company = self._resolve_company(dossier)
        serializer.save(company=company)


class DossierExchangeViewSet(CompanyScopedModelViewSet):  # ARC5 (voir note ci-dessus)
    """FG269 — journal de la navette opérateur (scopé société)."""

    queryset = DossierExchange.objects.select_related(
        'dossier', 'created_by').all()
    serializer_class = DossierExchangeSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        dossier_id = self.request.query_params.get('dossier')
        if dossier_id:
            qs = qs.filter(dossier_id=dossier_id)
        type_echange = self.request.query_params.get('type_echange')
        if type_echange:
            qs = qs.filter(type_echange=type_echange)
        return qs

    def _resolve_company(self, dossier):
        user = self.request.user
        company = _company_or_none(user)
        if dossier is None:
            raise ValidationError({'dossier': 'Dossier requis.'})
        if company is not None and dossier.company_id != company.id:
            raise ValidationError({'dossier': 'Dossier inconnu.'})
        return dossier.company

    def perform_create(self, serializer):
        dossier = serializer.validated_data.get('dossier')
        company = self._resolve_company(dossier)
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        dossier = serializer.validated_data.get(
            'dossier', serializer.instance.dossier)
        company = self._resolve_company(dossier)
        serializer.save(company=company)


class SubventionDossierViewSet(CompanyScopedModelViewSet):  # ARC5 (voir note ci-dessus)
    """FG270 — éligibilité & suivi des subventions (scopé société)."""

    queryset = SubventionDossier.objects.select_related(
        'devis', 'created_by').all()
    serializer_class = SubventionDossierSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        devis_id = self.request.query_params.get('devis')
        if devis_id:
            qs = qs.filter(devis_id=devis_id)
        programme = self.request.query_params.get('programme')
        if programme:
            qs = qs.filter(programme=programme)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _resolve_company(self, devis):
        user = self.request.user
        company = _company_or_none(user)
        if devis is not None:
            if company is not None and devis.company_id != company.id:
                raise ValidationError({'devis': 'Devis inconnu.'})
            return devis.company
        if company is None:
            raise ValidationError(
                {'company': "Aucune société : impossible de créer le dossier."})
        return company

    def perform_create(self, serializer):
        devis = serializer.validated_data.get('devis')
        company = self._resolve_company(devis)
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        devis = serializer.validated_data.get(
            'devis', serializer.instance.devis)
        company = self._resolve_company(devis)
        serializer.save(company=company)


class Regularisation8221ViewSet(CompanyScopedModelViewSet):  # ARC5 (voir note ci-dessus)
    """FG271 — workflow de régularisation Article 33 (scopé société)."""

    queryset = Regularisation8221.objects.select_related(
        'devis', 'chantier', 'created_by').all()
    serializer_class = Regularisation8221Serializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        devis_id = self.request.query_params.get('devis')
        if devis_id:
            qs = qs.filter(devis_id=devis_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _resolve_company(self, devis):
        user = self.request.user
        company = _company_or_none(user)
        if devis is not None:
            if company is not None and devis.company_id != company.id:
                raise ValidationError({'devis': 'Devis inconnu.'})
            return devis.company
        if company is None:
            raise ValidationError(
                {'company': "Aucune société : régularisation impossible."})
        return company

    def perform_create(self, serializer):
        devis = serializer.validated_data.get('devis')
        company = self._resolve_company(devis)
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        devis = serializer.validated_data.get(
            'devis', serializer.instance.devis)
        company = self._resolve_company(devis)
        serializer.save(company=company)

    @action(detail=True, methods=['post'], url_path='generer-declaration')
    def generer_declaration(self, request, pk=None):
        """POST /{id}/generer-declaration/ — marque la déclaration générée.

        Enregistre le chemin/clé du PDF de déclaration fourni et fait avancer le
        statut vers ``declaration_generee`` (jamais un statut de DEVIS). Le rendu
        PDF lui-même reste hors de ce endpoint."""
        regul = self.get_object()
        chemin = (request.data or {}).get('declaration_pdf')
        if not chemin:
            raise ValidationError(
                {'declaration_pdf': 'Chemin/clé du PDF requis.'})
        regul.declaration_pdf = chemin
        if regul.statut == Regularisation8221.Statut.A_REGULARISER:
            regul.statut = Regularisation8221.Statut.DECLARATION_GENEREE
        regul.save(update_fields=['declaration_pdf', 'statut', 'updated_at'])
        return Response(self.get_serializer(regul).data,
                        status=status.HTTP_200_OK)
