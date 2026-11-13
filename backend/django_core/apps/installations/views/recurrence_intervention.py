"""ACEL46 — récurrences d'intervention d'un chantier (ZFSM3), créables et
visibles depuis la fiche chantier. Création, liste, désactivation : la tâche de
05:35 (``generer_interventions_recurrentes``) lisait une table que rien ne
remplissait. Société forcée côté serveur ; chantier et technicien validés
tenant par ``SameCompanyFKSerializerMixin`` (id d'une autre société = « objet
inexistant », comme un id absent — ACAL298).
Contrat : ``contract_samples/recurrences_intervention.json``."""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.roles.permissions import DroitDeLaGrille
from authentication.permissions import IsResponsableOrAdmin, LectureDuModule
from core.mixins import SameCompanyFKSerializerMixin
from core.viewsets import CompanyScopedModelViewSet

from ..models import RecurrenceIntervention
from . import _openapi as oa


class RecurrenceInterventionSerializer(SameCompanyFKSerializerMixin, serializers.ModelSerializer):
    same_company_fields = ('installation', 'technicien_defaut')

    class Meta:
        model = RecurrenceIntervention
        fields = ['id', 'installation', 'type_intervention', 'technicien_defaut',
                  'regle', 'intervalle', 'prochaine_echeance', 'date_fin',
                  'nb_occurrences', 'nb_generees', 'actif', 'jour_ancrage']
        read_only_fields = ['nb_generees', 'actif', 'jour_ancrage']


@oa.listing(p0=oa.qi('installation'))
class RecurrenceInterventionViewSet(oa.JsonOnlyMixin, CompanyScopedModelViewSet):
    """ACEL46 — lecture tout rôle du module ; création/désactivation :
    responsable/admin avec ``intervention_gerer``. Filtrable par chantier."""
    queryset = RecurrenceIntervention.objects.select_related('installation').order_by(
        'prochaine_echeance', 'id')
    serializer_class = RecurrenceInterventionSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [LectureDuModule()]
        return [IsResponsableOrAdmin(), DroitDeLaGrille('intervention_gerer')()]

    def get_queryset(self):
        qs = super().get_queryset()
        installation = self.request.query_params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @extend_schema(request=None, responses=RecurrenceInterventionSerializer)
    @action(detail=True, methods=['post'])
    def desactiver(self, request, pk=None):
        """Arrête la récurrence (aucune intervention future générée)."""
        rec = self.get_object()
        rec.actif = False
        rec.save(update_fields=['actif'])
        return Response(self.get_serializer(rec).data)
