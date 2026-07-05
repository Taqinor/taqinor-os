"""AG1 — Endpoint catalogue des actions agentiques.

``GET /api/django/agent/actions/`` — renvoie, pour le caller authentifié, le
sous-ensemble du catalogue qu'il a le droit d'exécuter (filtré par permission,
et donc société-aware via son rôle). Métadonnées uniquement : aucune exécution.

YHARD2 — journal des actions IA confirmées (lecture admin/Directeur) + endpoint
d'annulation pour une action réversible.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAdminRole

from .models import AgentActionLog
from .registry import for_user
from .services import ActionNotUndoableError, annuler_action


class AgentActionsView(APIView):
    """Catalogue des actions exécutables par l'utilisateur courant."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        actions = [a.as_dict() for a in for_user(request.user)]
        return Response({'count': len(actions), 'actions': actions})


def _serialize_log(log: AgentActionLog) -> dict:
    return {
        'id': log.pk,
        'action_key': log.action_key,
        'risk_level': log.risk_level,
        'user': getattr(log.user, 'username', None),
        'confirmed_at': log.confirmed_at,
        'executed_at': log.executed_at,
        'object_repr': log.object_repr,
        'undone_at': log.undone_at,
        'is_undoable': log.is_undoable,
    }


class AgentActionLogView(APIView):
    """YHARD2 — ``GET /api/django/agent/logs/`` : journal des actions IA
    confirmées, scopé société, admin/Directeur uniquement (paramétrage
    interne — pas une surface grand public)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        user = request.user
        qs = AgentActionLog.objects.select_related('user')
        if user.company_id:
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        qs = qs.order_by('-confirmed_at')[:200]
        data = [_serialize_log(log) for log in qs]
        return Response({'count': len(data), 'results': data})


class AgentActionUndoView(APIView):
    """YHARD2 — ``POST /api/django/agent/logs/<id>/annuler/`` : annule une
    action réversible non déjà annulée. Company-scopée (une entrée d'une
    autre société renvoie 404, jamais une fuite d'existence)."""

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        user = request.user
        qs = AgentActionLog.objects.all()
        if user.company_id:
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        try:
            log = qs.get(pk=pk)
        except AgentActionLog.DoesNotExist:
            return Response({'detail': 'Introuvable.'}, status=404)

        try:
            annuler_action(log, user=user)
        except ActionNotUndoableError as exc:
            return Response({'detail': str(exc)}, status=409)

        return Response(_serialize_log(log))


class AutomationDraftView(APIView):
    """XPLT18 — ``POST /api/django/agent/actions/automation-draft/``.

    Endpoint cible de l'action catalogue ``automation.rule.propose_draft``.
    Ne fait QUE relayer vers ``apps.automation.services`` (jamais d'import de
    ``apps.automation.models`` ici — frontière cross-app respectée) : c'est
    ce service qui re-valide le brouillon contre le catalogue fermé et crée
    la règle TOUJOURS désactivée. ``company`` est imposée depuis
    ``request.user`` (jamais depuis le corps)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.automation.services import DraftRuleError, \
            create_draft_rule_from_agent
        from rest_framework import status

        company = request.user.company
        if company is None:
            return Response(
                {'detail': "Aucune société associée à l'utilisateur."},
                status=status.HTTP_400_BAD_REQUEST)

        data = request.data or {}
        try:
            rule = create_draft_rule_from_agent(
                company=company,
                nom=data.get('nom', ''),
                trigger_type=data.get('trigger_type', ''),
                trigger_config=data.get('trigger_config') or {},
                action_type=data.get('action_type', ''),
                action_config=data.get('action_config') or {},
            )
        except DraftRuleError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'id': rule.pk,
                'nom': rule.nom,
                'enabled': rule.enabled,
                'trigger_type': rule.trigger_type,
                'action_type': rule.action_type,
            },
            status=status.HTTP_201_CREATED)
