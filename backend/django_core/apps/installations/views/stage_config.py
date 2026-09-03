"""CH5 — Configuration des étapes/gates de chantier (Paramètres, Directeur-only).

Le Directeur ajoute / retire / réordonne les étapes du cycle de vie chantier,
marque chaque étape bloquante ou consultative et attache ses éléments requis
(`exige_*`) — sur le modèle CH1. Lecture ouverte à tout rôle (l'écran de suivi
en a besoin) ; ÉCRITURE réservée au Directeur.

Multi-tenant : la société est TOUJOURS posée côté serveur ; le queryset est
scopé à la société du demandeur. Une étape SYSTÈME (protégée) ne se supprime
pas — elle se désactive (même règle que les checklists/shot-list).
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core.viewsets import CompanyScopedModelViewSet
from apps.core.destroy_mixins import UsageGuardedDestroyMixin

from ..models import StageModele
from ..serializers_stage import StageModeleSerializer
from ..services import seed_stages

READ_ACTIONS = ['list', 'retrieve']


class IsDirecteur(BasePermission):
    """Réservé au Directeur.

    Autorité : le rôle système « Directeur » (via son signal de permission le
    plus élevé — le Journal d'activité, réservé Directeur par défaut). Un
    superuser passe toujours ; un compte HÉRITÉ sans rôle fin garde l'accès
    historique (palier admin legacy) pour ne jamais régresser un propriétaire
    existant."""
    message = "Configuration réservée au Directeur."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        # Rôle fin : le Directeur porte `journal_activite_voir` (réservé
        # Directeur par défaut) — le signal le plus discriminant du palier.
        if getattr(user, 'role_id', None):
            return 'journal_activite_voir' in (user.role.permissions or [])
        # Compte hérité sans rôle fin → palier admin legacy (propriétaire).
        return getattr(user, 'is_admin_role', False)


class StageModeleViewSet(UsageGuardedDestroyMixin, CompanyScopedModelViewSet):
    """CH5 — étapes/gates configurables (Paramètres → Chantiers). Lecture tout
    rôle ; écriture Directeur uniquement.

    AUD313 — la LECTURE n'amorce plus rien. Le cycle PV international
    s'amorce uniquement par l'action d'écriture explicite
    `POST /etapes-chantier/amorcer/`, réservée au Directeur : un GET (ouvert à
    tout rôle, y compris depuis l'onglet « Jalons » d'une fiche chantier) ne
    peut plus activer les 4 gates BLOQUANTS du cycle par défaut pour toute la
    société.
    VX241(b) — la suppression effective écrit désormais une ligne AuditLog
    (UsageGuardedDestroyMixin) : StageModele n'est pas dans TRACKED_MODELS."""
    queryset = StageModele.objects.all()
    serializer_class = StageModeleSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsDirecteur()]

    @action(detail=False, methods=['post'], url_path='amorcer')
    def amorcer(self, request):
        """AUD313 — amorce le cycle de vie PV international de la société.

        SEUL point d'entrée de `seed_stages` côté API, réservé au Directeur
        (via `get_permissions`). Idempotent et additif : ne touche jamais une
        étape existante (libellés, ordre, drapeaux et exigences édités par le
        Directeur sont préservés)."""
        company = request.user.company
        if company is None:
            return Response({'detail': 'Aucune société sur le compte.'},
                            status=status.HTTP_400_BAD_REQUEST)
        crees = seed_stages(company)
        stages = StageModele.objects.filter(
            company=company).order_by('ordre', 'id')
        return Response(
            {
                'crees': len(crees),
                'etapes': StageModeleSerializer(stages, many=True).data,
            },
            status=status.HTTP_201_CREATED)

    def destroy_guard_message(self, stage):
        if stage.protege:
            return "Cette étape système est protégée — désactivez-la plutôt."
        return None
