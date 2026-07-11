"""FG254 / DC35 — Bibliothèque de fiches techniques modules/onduleurs.

ViewSet CRUD pour les fiches techniques normalisées (datasheets) rattachées à
un produit du catalogue. La fiche ne porte QUE les paramètres électriques
normalisés (Pmax/Voc/Isc/Vmp/Imp + coef. température) et un PDF datasheet
optionnel — jamais la marque/description/garantie/courbe (déjà sur Produit,
DC35), et jamais aucun prix.

Endpoints :
  GET    /ventes/fiches-techniques/            list (par société)
  POST   /ventes/fiches-techniques/            create (company forcée serveur)
  GET    /ventes/fiches-techniques/{id}/       retrieve
  PUT    /ventes/fiches-techniques/{id}/       update
  PATCH  /ventes/fiches-techniques/{id}/       partial_update
  DELETE /ventes/fiches-techniques/{id}/       destroy

Filtres optionnels : ?produit=<id>, ?type_fiche=panneau|onduleur.

Multi-tenancy : ``company`` TOUJOURS forcée côté serveur depuis le produit lié
(lui-même borné à la société de l'utilisateur) ; jamais lue du corps. Querysets
filtrés par ``request.user.company``. Couche additive séparée du PDF premium et
de `/proposal` ; ne change aucun statut de devis (RULE #4).
"""
from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet  # ARC5
from ..models import FicheTechnique
from ..serializers import FicheTechniqueSerializer

READ_ACTIONS = ['list', 'retrieve']


class FicheTechniqueViewSet(CompanyScopedModelViewSet):
    """FG254 — CRUD fiches techniques normalisées, scopé société.

    ARC5 — sweep TenantMixin : base transverse unique. get_queryset /
    perform_create / perform_update / get_permissions SURCHARGENT la base
    (scoping direct sur `company`) : scoping et matrice 401/403/404 INCHANGÉS
    (règle #4 : couche additive, aucun statut de devis touché)."""

    queryset = FicheTechnique.objects.select_related(
        'produit', 'created_by').all()
    serializer_class = FicheTechniqueSerializer

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
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        type_fiche = self.request.query_params.get('type_fiche')
        if type_fiche:
            qs = qs.filter(type_fiche=type_fiche)
        return qs

    def _resolve_company(self, produit):
        """Société dérivée du produit lié, bornée à celle de l'utilisateur."""
        user = self.request.user
        user_company = getattr(user, 'company', None)
        produit_company_id = getattr(produit, 'company_id', None)
        if user_company is not None:
            if produit_company_id is not None and \
                    produit_company_id != user_company.id:
                raise ValidationError({'produit': 'Produit inconnu.'})
            return user_company
        # Superuser sans société : on suit la société du produit.
        if produit_company_id is None:
            raise ValidationError(
                {'company': "Aucune société : impossible de créer la fiche."})
        return produit.company

    def perform_create(self, serializer):
        produit = serializer.validated_data.get('produit')
        company = self._resolve_company(produit)
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        produit = serializer.validated_data.get(
            'produit', serializer.instance.produit)
        company = self._resolve_company(produit)
        serializer.save(company=company)
