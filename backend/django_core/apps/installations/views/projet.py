"""Vues de la couche GESTION DE PROJET du chantier (FG293 / FG296 / FG298).

  * FG293 — ``JalonProjetViewSet`` : jalons/phases de projet d'un chantier.
  * FG296 — ``ModeleProjetViewSet`` : modèles de projet (chantier-type) +
    action ``instancier`` qui applique le modèle à un chantier.
  * FG298 — ``ReunionChantierViewSet`` : comptes-rendus de réunion de chantier.

Toutes les vues sont multi-tenant via ``TenantMixin`` : le queryset est filtré
sur la société de l'utilisateur et la société est posée côté serveur dans
``perform_create`` (jamais lue du corps de la requête)."""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import (
    Installation, JalonProjet, ModeleProjet, ReunionChantier,
)
from ..serializers import (
    JalonProjetSerializer, ModeleProjetSerializer, ReunionChantierSerializer,
)
from ..services import instantiate_modele_projet, notifier_jalon_a_facturer

READ_ACTIONS = ['list', 'retrieve']


def _check_installation_tenant(serializer, company):
    """Tenant safety : le chantier ciblé doit appartenir à la société du user."""
    cid = getattr(company, 'id', None)
    installation = serializer.validated_data.get('installation')
    if installation is not None and installation.company_id != cid:
        raise ValidationError({'installation': 'Chantier inconnu.'})


class JalonProjetViewSet(CompanyScopedModelViewSet):
    """FG293 — jalons & phases de projet d'un chantier (dates cible & réelle).
    Lecture tout rôle, écriture responsable/admin. Filtrable par `installation`.
    Société posée côté serveur."""
    queryset = JalonProjet.objects.select_related('installation').all()
    serializer_class = JalonProjetSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        installation = self.request.query_params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        return qs

    def perform_create(self, serializer):
        _check_installation_tenant(serializer, self.request.user.company)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        _check_installation_tenant(serializer, self.request.user.company)
        old_atteint = serializer.instance.atteint
        serializer.save(company=self.request.user.company)
        jalon = serializer.instance
        # YSERV7 — au passage à `atteint=True`, nudge de facturation
        # (best-effort, idempotent — ne bloque jamais l'update du jalon).
        if jalon.atteint and not old_atteint:
            try:
                notifier_jalon_a_facturer(jalon, self.request.user)
            except Exception:  # pragma: no cover - défensif
                pass


class ModeleProjetViewSet(CompanyScopedModelViewSet):
    """FG296 — modèles de projet (templates de chantier-type). Lecture tout
    rôle, écriture responsable/admin. L'action `instancier` applique le modèle à
    un chantier (pré-crée jalons + BoM type). Société posée côté serveur."""
    queryset = ModeleProjet.objects.prefetch_related(
        'jalons', 'bom_lignes').all()
    serializer_class = ModeleProjetSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        type_installation = self.request.query_params.get('type_installation')
        if type_installation:
            qs = qs.filter(type_installation=type_installation)
        return qs

    @action(detail=True, methods=['post'])
    def instancier(self, request, pk=None):
        """FG296 — applique ce modèle de projet à un chantier (`installation`
        dans le corps). Idempotent et additif : ne duplique jamais un jalon de
        même libellé ni une ligne de BoM déjà gelée. Le chantier doit appartenir
        à la société de l'utilisateur."""
        modele = self.get_object()
        installation_id = request.data.get('installation')
        if not installation_id:
            return Response(
                {'detail': "Le champ « installation » est requis."},
                status=status.HTTP_400_BAD_REQUEST)
        installation = (Installation.objects
                        .filter(company=request.user.company,
                                pk=installation_id)
                        .first())
        if installation is None:
            return Response(
                {'detail': "Chantier introuvable pour cette société."},
                status=status.HTTP_404_NOT_FOUND)
        result = instantiate_modele_projet(installation, modele, request.user)
        return Response(result, status=status.HTTP_200_OK)


class ReunionChantierViewSet(CompanyScopedModelViewSet):
    """FG298 — comptes-rendus de réunion de chantier (ordre du jour / présents /
    décisions / actions). Lecture tout rôle, écriture responsable/admin.
    Filtrable par `installation`. Société + rédacteur posés côté serveur."""
    queryset = ReunionChantier.objects.select_related(
        'installation', 'redige_par').all()
    serializer_class = ReunionChantierSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        installation = self.request.query_params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        return qs

    def perform_create(self, serializer):
        # Société + rédacteur posés côté serveur — jamais lus du corps.
        _check_installation_tenant(serializer, self.request.user.company)
        serializer.save(
            company=self.request.user.company, redige_par=self.request.user)

    def perform_update(self, serializer):
        _check_installation_tenant(serializer, self.request.user.company)
        serializer.save(company=self.request.user.company)
