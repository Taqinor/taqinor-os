from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401

from authentication.mixins import TenantMixin  # noqa: F401
from authentication.permissions import (  # noqa: F401
    IsAnyRole, IsResponsableOrAdmin, IsAdminRole,
)
from core.viewsets import CompanyScopedModelViewSet
from django.utils import timezone  # noqa: F401

from .. import activity  # noqa: F401
from .. import intervention_activity  # noqa: F401
from ..models import (  # noqa: F401
    Installation, Intervention, TypeIntervention, ChecklistTemplate,
    ChecklistEtapeModele, ShotListSlot, ComponentSerial,
    ConsommationLigne, VoiceMemo, Reserve, ToolReturn, SafetyChecklistSlot,
)
from ..serializers import (  # noqa: F401
    InstallationSerializer, InterventionSerializer,
    InstallationActivitySerializer, InterventionActivitySerializer,
    TypeInterventionSerializer, ChecklistTemplateSerializer,
    ChecklistEtapeModeleSerializer, ChantierChecklistItemSerializer,
    ShotListSlotSerializer, InterventionPreparationSerializer,
    ComponentSerialSerializer, MaterielConsommationSerializer,
    ConsommationLigneSerializer, VoiceMemoSerializer, ReserveSerializer,
    ToolReturnSerializer, SafetyChecklistSlotSerializer, SafetySignoffSerializer,
)
from ..services import (  # noqa: F401
    create_installation_from_devis, seed_checklist_etapes,
    ensure_checklist_items, ensure_default_template,
)
from .. import field_services  # noqa: F401
from .. import field_capture  # noqa: F401

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# Types d'intervention par défaut (clés = Intervention.Type), tous « système ».
_DEFAULT_TYPES_INTERVENTION = [
    ('pose', 'Pose'),
    ('raccordement', 'Raccordement'),
    ('mise_en_service', 'Mise en service'),
    ('controle', 'Contrôle'),
    ('depannage', 'Dépannage'),
]


# Jalon de statut canonique → champ date à horodater (N6/N7) si vide.
_STATUT_DATE_FIELD = {
    Installation.Statut.SIGNE: 'date_signature',
    Installation.Statut.MATERIEL_COMMANDE: 'date_materiel_commande',
    Installation.Statut.PLANIFIE: 'date_pose_prevue',
    Installation.Statut.INSTALLE: 'date_pose_reelle',
    Installation.Statut.RECEPTIONNE: 'date_reception',
    Installation.Statut.CLOTURE: 'date_cloture',
}


def _stamp_statut_dates(inst, old_statut):
    """Pose la date du jalon atteint si elle est vide (jamais d'écrasement).
    Travaille sur le statut CANONIQUE pour couvrir aussi les statuts hérités."""
    canon = Installation.canonical_statut(inst.statut)
    if Installation.canonical_statut(old_statut) == canon:
        return
    field = _STATUT_DATE_FIELD.get(canon)
    if field and getattr(inst, field, None) is None:
        setattr(inst, field, timezone.localdate())
        inst.save(update_fields=[field])


def _apply_stock_statut_effects(inst, canon_old, canon_new, user):
    """N14 — effets STOCK d'un changement de statut canonique du chantier.

    À l'arrivée à « Installé », consomme les réservations (une SORTIE par SKU,
    idempotente côté service). À l'arrivée à « Clôturé », libère les
    réservations restantes non consommées. Le service est idempotent : il ne
    rejoue jamais une réservation déjà consommée."""
    from ..services import consume_reservations, release_reservations  # noqa: F401
    if canon_new == canon_old:
        return
    if canon_new == Installation.Statut.INSTALLE:
        nb = consume_reservations(inst, user)
        if nb:
            activity.log_note(
                inst, user,
                f"Stock consommé — {nb} référence(s) sortie(s) du stock "
                f"(chantier « Installé »).")
    elif canon_new == Installation.Statut.CLOTURE:
        nb = release_reservations(inst)
        if nb:
            activity.log_note(
                inst, user,
                f"Réservation de stock libérée — {nb} référence(s) "
                f"(chantier clôturé).")


def seed_types_intervention(company):
    if company is None or TypeIntervention.objects.filter(company=company).exists():
        return
    for i, (cle, libelle) in enumerate(_DEFAULT_TYPES_INTERVENTION):
        TypeIntervention.objects.get_or_create(
            company=company, cle=cle,
            defaults={'libelle': libelle, 'ordre': i, 'protege': True})

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class TypeInterventionViewSet(CompanyScopedModelViewSet):
    """Types d'intervention gérés (Paramètres → Chantiers). Lecture tout rôle,
    écriture admin. Un type protégé ou utilisé ne peut pas être supprimé."""
    queryset = TypeIntervention.objects.all()
    serializer_class = TypeInterventionSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        if request.user.company_id:
            seed_types_intervention(request.user.company)
        return super().list(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        t = self.get_object()
        if t.protege:
            return Response(
                {'detail': "Ce type est protégé et ne peut pas être supprimé."},
                status=status.HTTP_409_CONFLICT)
        if Intervention.objects.filter(company=t.company, type_intervention=t.cle).exists():
            return Response(
                {'detail': "Ce type est utilisé par des interventions — "
                           "archivez-le plutôt."},
                status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)
