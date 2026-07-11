"""Vue DC40 — équipe terrain CANONIQUE.

``EquipeViewSet`` : CRUD des équipes terrain (membres = utilisateurs) — le
modèle d'équipe UNIQUE réutilisé par le roster (FG169), le plan de charge
(FG299) et le planning camionnette (FG303). Lecture tout rôle, écriture
responsable/admin. Multi-tenant via ``TenantMixin`` : le queryset est filtré
sur la société de l'utilisateur et la société + ``created_by`` sont posés côté
serveur (jamais lus du corps). Les cibles (membres, chef) sont validées tenant :
elles doivent appartenir à la société de l'utilisateur."""
from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import Equipe
from ..serializers import EquipeSerializer

READ_ACTIONS = ['list', 'retrieve']


def _check_members_tenant(serializer, company):
    """Tenant safety : les membres et le chef ciblés doivent appartenir à la
    société de l'utilisateur (sinon on affecterait/fuiterait une autre
    société)."""
    cid = getattr(company, 'id', None)
    membres = serializer.validated_data.get('membres')
    if membres:
        for membre in membres:
            if getattr(membre, 'company_id', None) != cid:
                raise ValidationError({'membres': 'Membre inconnu.'})
    chef = serializer.validated_data.get('chef')
    if chef is not None and getattr(chef, 'company_id', None) != cid:
        raise ValidationError({'chef': 'Chef inconnu.'})


class EquipeViewSet(CompanyScopedModelViewSet):
    """DC40 — équipes terrain (membres = utilisateurs). Lecture tout rôle,
    écriture responsable/admin. Société + `created_by` posés côté serveur ;
    membres/chef validés tenant. Filtrable par `actif`."""
    queryset = Equipe.objects.select_related(
        'chef', 'created_by').prefetch_related('membres').all()
    serializer_class = EquipeSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif is not None:
            val = str(actif).lower() in ('1', 'true', 'oui', 'yes')
            qs = qs.filter(actif=val)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_members_tenant(serializer, company)
        serializer.save(company=company, created_by=self.request.user)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_members_tenant(serializer, company)
        serializer.save(company=company)
