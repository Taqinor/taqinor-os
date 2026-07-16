"""ZFSM3 — récurrences d'intervention autonomes (sans contrat).

NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
(un module par ressource). Comportement et symboles inchangés : le package
__init__ ré-exporte toutes les vues publiques."""
from rest_framework.exceptions import ValidationError

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import RecurrenceIntervention
from ..serializers import RecurrenceInterventionSerializer

READ_ACTIONS = ['list', 'retrieve']


class RecurrenceInterventionViewSet(CompanyScopedModelViewSet):
    """ZFSM3 — CRUD des récurrences d'intervention (Chantiers → onglet
    Récurrences). Lecture/écriture réservées responsable/admin (planification
    terrain). Tout est scopé à la société ; la société est posée côté
    serveur, jamais lue du corps de requête."""
    queryset = RecurrenceIntervention.objects.select_related(
        'installation', 'technicien_defaut').all()
    serializer_class = RecurrenceInterventionSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        installation = self.request.query_params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        return qs

    def _check_installation_tenant(self, serializer):
        """Tenant safety : le chantier ciblé doit appartenir à la société."""
        installation = serializer.validated_data.get('installation')
        company = self.request.user.company
        if installation is not None and installation.company_id != getattr(
                company, 'id', None):
            raise ValidationError({'installation': 'Chantier inconnu.'})

    def perform_create(self, serializer):
        self._check_installation_tenant(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_installation_tenant(serializer)
        serializer.save()
