from django.db import transaction  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
from ..models import (
    DocumentConformiteFournisseur, AchatsParametres,
    ToleranceRapprochementCategorie,
)
from ..serializers import (
    DocumentConformiteFournisseurSerializer, AchatsParametresSerializer,
    ToleranceRapprochementCategorieSerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class DocumentConformiteFournisseurViewSet(CompanyScopedModelViewSet):
    """XPUR1 — documents de conformité fournisseur (ARF/CNSS/RC/assurance).

    Lecture tout rôle authentifié ; écriture réservée à ``stock_modifier``
    (repli responsable/admin). ``company`` posée côté serveur. Filtre optionnel
    ``?fournisseur=<id>``."""
    queryset = DocumentConformiteFournisseur.objects.select_related(
        'fournisseur', 'created_by').all()
    serializer_class = DocumentConformiteFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_expiration', 'date_creation', 'type_document']
    ordering = ['fournisseur_id', 'type_document']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [HasPermissionOrLegacy('stock_modifier')()]

    def get_queryset(self):
        qs = super().get_queryset()
        fournisseur_id = self.request.query_params.get('fournisseur')
        if fournisseur_id:
            qs = qs.filter(fournisseur_id=fournisseur_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class AchatsParametresViewSet(viewsets.ViewSet):
    """XPUR1 — paramètres achats de la société connectée (singleton par
    company). GET renvoie (en le créant si besoin) le réglage courant ; PATCH
    le met à jour. ``company`` toujours dérivée de l'utilisateur, jamais du
    corps de requête."""
    permission_classes = [IsAnyRole]

    def list(self, request):
        obj = AchatsParametres.for_company(request.user.company)
        return Response(AchatsParametresSerializer(obj).data)

    def partial_update(self, request, pk=None):
        if not HasPermissionOrLegacy('stock_modifier')().has_permission(
                request, self):
            return Response(
                {'detail': "Vous n'avez pas la permission de modifier ces "
                           "paramètres."},
                status=status.HTTP_403_FORBIDDEN)
        obj = AchatsParametres.for_company(request.user.company)
        serializer = AchatsParametresSerializer(
            obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='checklist-cloture')
    def checklist_cloture(self, request):
        """NTP2P30 — wizard de clôture de fin de mois achats : agrège en
        LECTURE SEULE les 3 listes du mois en cours (ou ``?periode=YYYY-MM-
        DD``) — factures en exception 3-voies non résolues, demandes d'achat
        en attente trop anciennes (``?seuil_jours=N``, défaut 15), documents
        fournisseur expirés. Aucune nouvelle donnée, aucune mutation."""
        from datetime import date
        from ..selectors import checklist_cloture_achats

        periode_param = request.query_params.get('periode')
        periode = None
        if periode_param:
            try:
                periode = date.fromisoformat(periode_param)
            except ValueError:
                return Response(
                    {'detail': 'Paramètre periode invalide (attendu '
                               'YYYY-MM-DD).'},
                    status=status.HTTP_400_BAD_REQUEST)
        seuil_jours = request.query_params.get('seuil_jours', 15)
        try:
            seuil_jours = int(seuil_jours)
        except (TypeError, ValueError):
            seuil_jours = 15
        return Response(checklist_cloture_achats(
            request.user.company, periode, seuil_jours=seuil_jours))


class ToleranceRapprochementCategorieViewSet(CompanyScopedModelViewSet):
    """NTP2P9 — grille éditable Paramètres → Achats : override par catégorie
    des tolérances 3 voies (XPUR10). Lecture tout rôle ; écriture réservée à
    ``stock_modifier`` (repli responsable/admin). Au plus une ligne par
    (société, catégorie) — imposé par la contrainte ``unique_together``."""
    queryset = ToleranceRapprochementCategorie.objects.select_related(
        'categorie').all()
    serializer_class = ToleranceRapprochementCategorieSerializer
    ordering = ['categorie__nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [HasPermissionOrLegacy('stock_modifier')()]
