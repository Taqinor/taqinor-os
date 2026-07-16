"""FG245 — Éditeur de calepinage toiture (placement panneaux).

ViewSet CRUD pour persister un calepinage toiture attaché à un devis :
surface du pan, retraits, taille de module et liste des panneaux placés
(position/orientation). Le nombre RÉALISTE de panneaux (``panel_count``) est
TOUJOURS recalculé côté serveur depuis la géométrie — jamais lu du corps de la
requête.

Endpoints :
  GET    /ventes/calepinages/            list (par société)
  POST   /ventes/calepinages/            create (company forcée serveur)
  GET    /ventes/calepinages/{id}/       retrieve
  PUT    /ventes/calepinages/{id}/       update
  PATCH  /ventes/calepinages/{id}/       partial_update
  DELETE /ventes/calepinages/{id}/       destroy
  POST   /ventes/calepinages/{id}/recompute/   recalcule le compte de panneaux

Multi-tenancy : ``company`` toujours forcée côté serveur (depuis le devis lié
ou l'utilisateur) ; jamais acceptée du corps. Querysets filtrés par
``request.user.company``.

Couche additive et séparée : ne touche ni le PDF premium (`quote_engine/`) ni
`/proposal`, et ne change aucun statut de devis (RULE #4).
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet  # ARC5
from ..models import RoofLayout
from ..serializers import RoofLayoutSerializer

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update', 'recompute']


class RoofLayoutViewSet(CompanyScopedModelViewSet):
    """FG245 — CRUD calepinage toiture, compte de panneaux calculé serveur.

    ARC5 — sweep TenantMixin : base transverse unique. get_queryset /
    perform_create / perform_update / get_permissions SURCHARGENT la base
    (scoping direct sur `company`) : scoping et matrice 401/403/404 INCHANGÉS
    (règle #4 : couche additive, aucun statut de devis touché)."""

    queryset = RoofLayout.objects.select_related(
        'devis', 'created_by').all()
    serializer_class = RoofLayoutSerializer

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
        # Filtre optionnel ?devis=<id> — borné à la société ci-dessus.
        devis_id = self.request.query_params.get('devis')
        if devis_id:
            qs = qs.filter(devis_id=devis_id)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        company = getattr(user, 'company', None)
        devis = serializer.validated_data.get('devis')
        # Tenant safety : un devis lié doit appartenir à la société de l'user.
        if devis is not None:
            if company is not None and devis.company_id != company.id:
                raise ValidationError({'devis': 'Devis inconnu.'})
            # Société toujours dérivée du devis quand il y en a un.
            company = devis.company
        if company is None:
            raise ValidationError(
                {'company': "Aucune société : impossible de créer le calepinage."})
        instance = serializer.save(company=company, created_by=user)
        # Compte TOUJOURS recalculé serveur : si l'éditeur a fourni des
        # panneaux explicites, on respecte ce placement (compte = len) ;
        # sinon on pave la grille depuis la géométrie.
        instance.recompute(rebuild_panels=not bool(instance.panels))
        instance.save(update_fields=['panels', 'panel_count', 'updated_at'])

    def perform_update(self, serializer):
        instance = serializer.save()
        # Idem à la mise à jour : le compte ne vient jamais du corps.
        provided_panels = 'panels' in serializer.validated_data and bool(
            serializer.validated_data.get('panels'))
        instance.recompute(rebuild_panels=not provided_panels)
        instance.save(update_fields=['panels', 'panel_count', 'updated_at'])

    @action(detail=True, methods=['post'])
    def recompute(self, request, pk=None):
        """POST /calepinages/{id}/recompute/ — recalcule le compte de panneaux.

        Re-pave la grille depuis la géométrie persistée et renvoie le
        calepinage à jour. Aucun changement de statut de devis."""
        layout = self.get_object()
        layout.recompute(rebuild_panels=True)
        layout.save(update_fields=['panels', 'panel_count', 'updated_at'])
        return Response(
            self.get_serializer(layout).data, status=status.HTTP_200_OK)
