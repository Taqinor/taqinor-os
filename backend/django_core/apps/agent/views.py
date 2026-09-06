"""AG1 — Endpoint catalogue des actions agentiques.

``GET /api/django/agent/actions/`` — renvoie, pour le caller authentifié, le
sous-ensemble du catalogue qu'il a le droit d'exécuter (filtré par permission,
et donc société-aware via son rôle). Métadonnées uniquement : aucune exécution.

YHARD2 — journal des actions IA confirmées (lecture admin/Directeur) + endpoint
d'annulation pour une action réversible.
"""
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework.views import APIView

from authentication.permissions import IsAdminRole

from .models import AgentActionLog
from .registry import for_user
from .services import ActionNotUndoableError, annuler_action, log_confirmed_action

# AUDV27 — mappe une ``action_key`` PILOTE vers le modèle (app_label, nom) de
# l'objet qu'elle crée, pour dériver ``content_type``/``object_id`` du journal
# SANS jamais importer le modèle de l'app métier ici (résolu par
# ``django.apps.apps.get_model``, string-only — même garde que les FK string
# cross-app). Volontairement minimal (1 entrée pilote, AUDV27) : une action
# absente de cette table est quand même journalisée, seulement sans cible
# résolue (``object_repr`` vide).
_RESULTED_OBJECT_MODELS = {
    'crm.client.create': ('crm', 'Client'),
}


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


class AgentActionConfirmerView(APIView):
    """AUDV27 (YHARD2) — ``POST /api/django/agent/logs/confirmer/`` :
    journalise la CONFIRMATION d'une action IA APRÈS son exécution réelle
    (appelé par le relais FastAPI juste après un ``confirm_proposal``
    réussi — jamais à la simple proposition, éphémère côté agent/Redis).

    Le journal YHARD2 restait vide en production : ``log_confirmed_action``
    existait, testée, mais AUCUN appelant ne l'invoquait après une exécution
    réelle. Self-service (tout utilisateur authentifié journalise SA PROPRE
    action confirmée) — la LECTURE/l'ANNULATION du journal restent admin/
    Directeur (``AgentActionLogView``/``AgentActionUndoView``). ``company``/
    ``user`` posés côté serveur, jamais lus du corps."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=inline_serializer(
        'AgentActionConfirmee', {
            'id': drf_serializers.IntegerField(),
            'action_key': drf_serializers.CharField(),
            'risk_level': drf_serializers.CharField(),
            'user': drf_serializers.CharField(allow_null=True),
            'confirmed_at': drf_serializers.DateTimeField(allow_null=True),
            'executed_at': drf_serializers.DateTimeField(allow_null=True),
            'object_repr': drf_serializers.CharField(),
            'undone_at': drf_serializers.DateTimeField(allow_null=True),
            'is_undoable': drf_serializers.BooleanField(),
        }))
    def post(self, request):
        data = request.data or {}
        action_key = (data.get('action_key') or '').strip()
        risk_level = data.get('risk_level') or ''
        if not action_key or risk_level not in AgentActionLog.RiskLevel.values:
            return Response(
                {'detail': 'action_key et risk_level (valide) sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        company = request.user.company
        if company is None:
            return Response(
                {'detail': "Aucune société associée à l'utilisateur."},
                status=status.HTTP_400_BAD_REQUEST)

        resulted_object = None
        object_id = data.get('object_id')
        mapping = _RESULTED_OBJECT_MODELS.get(action_key)
        if object_id and mapping:
            from django.apps import apps as django_apps
            try:
                model = django_apps.get_model(*mapping)
            except LookupError:
                model = None
            if model is not None:
                resulted_object = model.objects.filter(
                    pk=object_id, company=company).first()

        log = log_confirmed_action(
            company=company, user=request.user, action_key=action_key,
            risk_level=risk_level, inputs=data.get('inputs') or {},
            proposal_hash=data.get('proposal_hash') or '',
            resulted_object=resulted_object,
        )
        return Response(_serialize_log(log), status=status.HTTP_201_CREATED)


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
