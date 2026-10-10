"""ZFSM1 — gabarit de fiche d'intervention configurable par type
(Paramètres → Chantiers) + relevé matérialisé par intervention.

NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
(un module par ressource). Comportement et symboles inchangés : le package
__init__ ré-exporte toutes les vues publiques."""

from rest_framework.exceptions import ValidationError

from authentication.permissions import IsAnyRole, IsAdminRole
from core.viewsets import CompanyScopedModelViewSet
from apps.core.destroy_mixins import UsageGuardedDestroyMixin

from ..models import FicheInterventionTemplate, FicheInterventionChamp
from ..serializers import (
    FicheInterventionTemplateSerializer, FicheInterventionChampSerializer,
)
from . import _openapi as oa

READ_ACTIONS = ['list', 'retrieve']


class FicheInterventionTemplateViewSet(oa.JsonOnlyMixin, UsageGuardedDestroyMixin,
                                       CompanyScopedModelViewSet):
    """ZFSM1 — gabarits de fiche d'intervention (Paramètres → Chantiers).
    Lecture tout rôle, écriture admin. Un gabarit par `type_intervention` et
    par société ; `protege` verrouille un gabarit système. Tout est scopé à
    la société ; la société est posée côté serveur, jamais lue du corps."""
    queryset = FicheInterventionTemplate.objects.prefetch_related('champs').all()
    serializer_class = FicheInterventionTemplateSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def destroy_guard_message(self, template):
        if template.protege:
            return "Ce gabarit est protégé — désactivez-le plutôt."
        # ACHT73 — un gabarit qui a des relevés porte l'historique des mesures
        # des interventions : on le désactive, on ne le supprime pas.
        nb = template.releves.count()
        if nb:
            return (f"Utilisé par {nb} relevé{'s' if nb > 1 else ''} "
                    "d'intervention — désactivez le gabarit plutôt que de le "
                    "supprimer.")
        return None


@oa.listing(p0=oa.qi('template'))
class FicheInterventionChampViewSet(oa.JsonOnlyMixin, UsageGuardedDestroyMixin,
                                    CompanyScopedModelViewSet):
    """ZFSM1 — champs d'un gabarit de fiche d'intervention. Lecture tout rôle,
    écriture admin. Filtrable via ?template=<id>."""
    queryset = FicheInterventionChamp.objects.all()
    serializer_class = FicheInterventionChampSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        template = self.request.query_params.get('template')
        if template:
            qs = qs.filter(template_id=template)
        return qs

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def destroy_guard_message(self, champ):
        # ACHT73 — un champ qui porte des VALEURS (mesures saisies) ne se
        # supprime pas : l'historique des relevés disparaîtrait.
        nb = champ.valeurs.exclude(valeur='').count()
        if nb:
            return (f"Utilisé par {nb} valeur{'s' if nb > 1 else ''} "
                    "saisie" + ('s' if nb > 1 else '') + " — le champ ne "
                    "peut pas être supprimé.")
        return None

    def _check_template_tenant(self, serializer):
        """Tenant safety : le gabarit ciblé doit appartenir à la société."""
        template = serializer.validated_data.get('template')
        company = self.request.user.company
        if template is not None and template.company_id != getattr(
                company, 'id', None):
            raise ValidationError({'template': 'Gabarit inconnu.'})

    def perform_create(self, serializer):
        self._check_template_tenant(serializer)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._check_template_tenant(serializer)
        super().perform_update(serializer)
