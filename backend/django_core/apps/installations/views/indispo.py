"""Vue FG302 — calendrier de disponibilité des ressources terrain.

``IndisponibiliteRessourceViewSet`` : CRUD des créneaux d'indisponibilité
(congé/formation/arrêt/autre) d'un technicien OU d'une camionnette. Lecture tout
rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` : le queryset
est filtré sur la société de l'utilisateur et la société + ``created_by`` sont
posés côté serveur (jamais lus du corps). Les cibles (technicien, camionnette)
sont validées tenant : elles doivent appartenir à la société de l'utilisateur."""
from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import IndisponibiliteRessource
from ..serializers import IndisponibiliteRessourceSerializer

READ_ACTIONS = ['list', 'retrieve']


def _check_target_tenant(serializer, company):
    """Tenant safety : technicien & camionnette ciblés doivent appartenir à la
    société de l'utilisateur (sinon on fuiterait/affecterait une autre société)."""
    cid = getattr(company, 'id', None)
    technicien = serializer.validated_data.get('technicien')
    if technicien is not None and getattr(technicien, 'company_id', None) != cid:
        raise ValidationError({'technicien': 'Technicien inconnu.'})
    camionnette = serializer.validated_data.get('camionnette')
    if camionnette is not None and \
            getattr(camionnette, 'company_id', None) != cid:
        raise ValidationError({'camionnette': 'Camionnette inconnue.'})


class IndisponibiliteRessourceViewSet(CompanyScopedModelViewSet):
    """FG302 — indisponibilités (congé/formation/arrêt/autre) d'un technicien ou
    d'une camionnette. Lecture tout rôle, écriture responsable/admin. Société +
    `created_by` posés côté serveur ; cibles validées tenant. Filtrable par
    `technicien`, `camionnette` et `type_indispo`, et par fenêtre `debut`/`fin`
    (chevauchement inclusif)."""
    queryset = IndisponibiliteRessource.objects.select_related(
        'technicien', 'camionnette', 'created_by').all()
    serializer_class = IndisponibiliteRessourceSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        technicien = params.get('technicien')
        if technicien:
            qs = qs.filter(technicien_id=technicien)
        camionnette = params.get('camionnette')
        if camionnette:
            qs = qs.filter(camionnette_id=camionnette)
        type_indispo = params.get('type_indispo')
        if type_indispo:
            qs = qs.filter(type_indispo=type_indispo)
        # Fenêtre [debut, fin] : on ne garde que les créneaux qui CHEVAUCHENT.
        debut = params.get('debut')
        fin = params.get('fin')
        if debut:
            qs = qs.filter(date_fin__gte=debut)
        if fin:
            qs = qs.filter(date_debut__lte=fin)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_target_tenant(serializer, company)
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_target_tenant(serializer, company)
        serializer.save(company=company)
