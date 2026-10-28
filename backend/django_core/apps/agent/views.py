"""AG1 — Endpoint catalogue des actions agentiques.

``GET /api/django/agent/actions/`` — renvoie, pour le caller authentifié, le
sous-ensemble du catalogue qu'il a le droit d'exécuter (filtré par permission,
et donc société-aware via son rôle). Métadonnées uniquement : aucune exécution.

YHARD2 — journal des actions IA confirmées (lecture admin/Directeur) + endpoint
d'annulation pour une action réversible.
"""
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.exceptions import ParseError, PermissionDenied
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework.views import APIView

from authentication.permissions import IsAdminRole, IsAnyRole
from apps.records.champs_stricts import RegexStricte

from .models import AgentActionLog, AssistantEvent
from .registry import for_user
from .services import (
    ActionNotUndoableError, annuler_action, log_confirmed_action,
    preuve_confirmation_valide,
)
from rest_framework.parsers import JSONParser

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


class ConfirmationActionSerializer(drf_serializers.Serializer):
    action_key = drf_serializers.CharField()
    risk_level = drf_serializers.ChoiceField(
        choices=list(AgentActionLog.RiskLevel.values))
    inputs = drf_serializers.DictField(required=False)
    object_id = drf_serializers.IntegerField(required=False, allow_null=True)
    preuve = drf_serializers.CharField(required=False)


def sans_nul(valeur):
    """Copie de ``valeur`` (JSON) sans octet NUL (NUL) dans les chaînes
    ni les clés : PostgreSQL le refuse dans un ``jsonb`` / un ``varchar`` (500)
    alors que le schéma l'annonce valide ; il n'a aucun sens métier."""
    if isinstance(valeur, str):
        return valeur.replace(chr(0), '')
    if isinstance(valeur, list):
        return [sans_nul(element) for element in valeur]
    if isinstance(valeur, dict):
        return {sans_nul(cle): sans_nul(element)
                for cle, element in valeur.items()}
    return valeur


class BrouillonAutomationSerializer(drf_serializers.Serializer):
    # ``nom`` : au moins un caractère non blanc (le service refuse un nom vide
    # après ``strip``), 255 au plus (``AutomationRule.nom``). CI #1003 (fuzz) —
    # une VRAIE chaîne JSON : ``RegexField`` convertissait ``0`` en ``"0"`` et
    # créait le brouillon (201) alors que le schéma publie ``type: string``.
    nom = RegexStricte(r'\S', max_length=255)
    trigger_type = drf_serializers.CharField()
    trigger_config = drf_serializers.DictField(required=False)
    action_type = drf_serializers.CharField()
    action_config = drf_serializers.DictField(required=False)

    def get_fields(self):
        # Catalogue FERMÉ lu via le selector d'automation (jamais ses modèles),
        # à l'exécution : même source que ``create_draft_rule_from_agent``.
        from apps.automation.selectors import closed_rule_catalogue
        from core.parseurs import ChoixDocumente

        champs = super().get_fields()
        catalogue = closed_rule_catalogue()
        # ERR-ENF11-FUZZ-AGENT — énum EN LIGNE (``core.parseurs.
        # ChoixDocumente``) : action_type « 0 » était conforme au schéma puis
        # refusé ; un composant d'énum partagé renommerait TriggerTypeEnum.
        champs['trigger_type'] = ChoixDocumente(catalogue['trigger_types'])
        champs['action_type'] = ChoixDocumente(catalogue['action_types'])
        return champs


_JournalAgent = inline_serializer('AgentActionJournal', {
    'id': drf_serializers.IntegerField(),
    'action_key': drf_serializers.CharField(),
    'risk_level': drf_serializers.CharField(),
    'user': drf_serializers.CharField(allow_null=True),
    'confirmed_at': drf_serializers.DateTimeField(allow_null=True),
    'executed_at': drf_serializers.DateTimeField(allow_null=True),
    'object_repr': drf_serializers.CharField(),
    'undone_at': drf_serializers.DateTimeField(allow_null=True),
    'is_undoable': drf_serializers.BooleanField(),
})


class AgentActionsView(APIView):
    """Catalogue des actions exécutables par l'utilisateur courant."""

    # ASEC43 — vues agent INTERNES : un compte portail (portee != interne)
    # reçoit 403 (IsAnyRole = authentifié ET interne).
    permission_classes = [IsAnyRole]

    @extend_schema(responses=inline_serializer('AgentCatalogue', {
        'count': drf_serializers.IntegerField(),
        'actions': drf_serializers.ListField(child=drf_serializers.DictField())}))
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

    permission_classes = [IsAnyRole, IsAdminRole]

    @extend_schema(responses=inline_serializer('AgentJournalListe', {
        'count': drf_serializers.IntegerField(),
        'results': drf_serializers.ListField(child=_JournalAgent)}))
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

    permission_classes = [IsAnyRole, IsAdminRole]

    @extend_schema(request=None, responses=_JournalAgent)
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

    # ASEC43 — self-service INTERNE seulement (compte portail -> 403).
    permission_classes = [IsAnyRole]
    parser_classes = [JSONParser]

    @extend_schema(request=ConfirmationActionSerializer, responses={201: inline_serializer(
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
        })})
    def post(self, request):
        data = request.data or {}
        # CI #1003 (fuzz) — les TYPES publiés par ``ConfirmationActionSerializer``
        # sont vérifiés avant tout usage : un ``action_key`` liste (``[null]``)
        # levait AttributeError sur ``.strip()`` (500) ; un corps non-objet ou
        # un ``object_id`` non entier est un 400, jamais une erreur serveur.
        if not isinstance(data, dict):
            raise ParseError('Un objet JSON est attendu.')
        action_key = data.get('action_key') or ''
        risk_level = data.get('risk_level') or ''
        object_id = data.get('object_id')
        if (not isinstance(action_key, str) or not isinstance(risk_level, str)
                or (object_id is not None and (isinstance(object_id, bool)
                                               or not isinstance(object_id, int)))):
            raise ParseError(
                'action_key et risk_level sont des chaînes, object_id un entier.')
        action_key = action_key.strip()
        # AANA18 — les refus sont LEVES (corps DRF `{detail}`, statut
        # inchange) : la seule forme RENVOYEE est le journal, que le contrat
        # `logs_confirmer.json` declare complet (`forme_serveur: complete`).
        if not action_key or risk_level not in AgentActionLog.RiskLevel.values:
            raise ParseError('action_key et risk_level (valide) sont requis.')
        company = request.user.company
        if company is None:
            raise ParseError("Aucune société associée à l'utilisateur.")

        # AANA18 (C-AANA-008) — n'accepter QUE la confirmation d'une
        # proposition réellement émise par l'agent POUR CET utilisateur :
        #   1. l'action figure dans SON catalogue (registry.for_user : module
        #      actif + permission requise détenue) et au même niveau de risque ;
        #   2. la preuve HMAC signée par le relais FastAPI (secret partagé
        #      AGENT_HMAC_SECRET) couvre action + entrées + objet + utilisateur
        #      + société de CETTE requête. Sinon 403, aucun journal créé.
        action = next(
            (a for a in for_user(request.user) if a.key == action_key), None)
        if action is None or action.risk != risk_level or (
                action.required_permission
                and not request.user.has_erp_permission(
                    action.required_permission)):
            raise PermissionDenied("Action non autorisée pour ce compte.")
        inputs = data.get('inputs') or {}
        preuve = data.get('preuve')
        if not isinstance(inputs, dict) or not preuve_confirmation_valide(
                preuve, action_key=action_key, company_id=company.pk,
                user_id=request.user.pk, inputs=inputs, object_id=object_id):
            raise PermissionDenied(
                "Preuve de confirmation absente ou invalide.")

        resulted_object = None
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
            risk_level=risk_level, inputs=inputs,
            # AANA18 — l'empreinte journalisée est la preuve HMAC vérifiée,
            # jamais un jeton brut ni une valeur libre du corps.
            proposal_hash=preuve,
            resulted_object=resulted_object,
        )
        return Response(_serialize_log(log), status=status.HTTP_201_CREATED)


# ── AIC6 — journal de l'assistant des commerciaux (contrat AIC1) ─────────────
# Action « virtuelle » signee par le relais FastAPI : la preuve HMAC
# (`preuve_confirmation_valide`, meme secret que logs/confirmer/) couvre le
# corps de l'evenement pour CET utilisateur et CETTE societe.
ACTION_PREUVE_EVENEMENT = 'assistant.evenement'
_CHAMPS_TOKENS = ('cache_read', 'input', 'output')

_EvenementAssistant = inline_serializer('AssistantEvenement', {
    'id': drf_serializers.IntegerField(),
    'intention': drf_serializers.ChoiceField(
        choices=AssistantEvent.Intention.values),
    'question': drf_serializers.CharField(),
    'resume_reponse': drf_serializers.CharField(),
    'ecran': drf_serializers.CharField(),
    'lead_id': drf_serializers.IntegerField(allow_null=True),
    'outils_appeles': drf_serializers.ListField(
        child=drf_serializers.CharField()),
    'erreur': drf_serializers.DictField(allow_null=True),
    'note': drf_serializers.IntegerField(),
    'commentaire': drf_serializers.CharField(allow_null=True),
    'modele': drf_serializers.CharField(),
    'repli': drf_serializers.BooleanField(),
    'manuel_present': drf_serializers.BooleanField(),
    'tokens': drf_serializers.DictField(child=drf_serializers.IntegerField()),
    'cree_le': drf_serializers.DateTimeField(),
})


class EvenementAssistantEntreeSerializer(drf_serializers.Serializer):
    intention = drf_serializers.ChoiceField(
        choices=AssistantEvent.Intention.values)
    question = drf_serializers.CharField(max_length=2000)
    resume_reponse = drf_serializers.CharField(required=False, allow_blank=True)
    ecran = drf_serializers.CharField(required=False, allow_blank=True)
    lead_id = drf_serializers.IntegerField(required=False, allow_null=True)
    outils_appeles = drf_serializers.ListField(
        child=drf_serializers.CharField(), required=False)
    erreur = drf_serializers.DictField(required=False, allow_null=True)
    modele = drf_serializers.CharField(required=False, allow_blank=True)
    repli = drf_serializers.BooleanField(required=False)
    manuel_present = drf_serializers.BooleanField(required=False)
    tokens = drf_serializers.DictField(
        child=drf_serializers.IntegerField(), required=False)
    preuve = drf_serializers.CharField()


class NoteEvenementSerializer(drf_serializers.Serializer):
    note = drf_serializers.ChoiceField(choices=[-1, 0, 1])
    commentaire = drf_serializers.CharField(
        max_length=200, required=False, allow_null=True, allow_blank=True)


def _serialiser_evenement(ev: AssistantEvent) -> dict:
    return {
        'id': ev.pk,
        'intention': ev.intention,
        'question': ev.question,
        'resume_reponse': ev.resume_reponse,
        'ecran': ev.ecran,
        'lead_id': ev.lead_id,
        'outils_appeles': ev.outils_appeles,
        'erreur': ev.erreur,
        'note': ev.note,
        'commentaire': ev.commentaire,
        'modele': ev.modele,
        'repli': ev.repli,
        'manuel_present': ev.manuel_present,
        'tokens': ev.tokens,
        'cree_le': ev.created_at,
    }


def _types_evenement_valides(data: dict) -> bool:
    """Types JSON publies, verifies AVANT tout usage (jamais de coercition :
    `0` n'est pas une chaine, `"1"` n'est pas un booleen)."""
    textes = ('intention', 'question', 'resume_reponse', 'ecran', 'modele',
              'preuve')
    if any(k in data and not isinstance(data[k], str) for k in textes):
        return False
    if any(k in data and not isinstance(data[k], bool)
           for k in ('repli', 'manuel_present')):
        return False
    lead = data.get('lead_id')
    if lead is not None and (isinstance(lead, bool) or not isinstance(lead, int)):
        return False
    outils = data.get('outils_appeles', [])
    if not isinstance(outils, list) or not all(isinstance(o, str) for o in outils):
        return False
    if data.get('erreur') is not None and not isinstance(data['erreur'], dict):
        return False
    tokens = data.get('tokens', {})
    return isinstance(tokens, dict) and all(
        isinstance(v, int) and not isinstance(v, bool) for v in tokens.values())


def _evenements_de_la_societe(user):
    qs = AssistantEvent.objects.all()
    if user.company_id:
        return qs.filter(company_id=user.company_id)
    return qs if user.is_superuser else qs.none()


class AssistantEventView(APIView):
    """AIC6 — ``POST /api/django/agent/evenements/`` : création par le RELAIS
    FastAPI (preuve HMAC, 403 sinon) ; ``GET`` : liste paginée de la société,
    admin/Directeur seulement."""

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAnyRole(), IsAdminRole()]
        return [IsAnyRole()]

    @extend_schema(responses=inline_serializer('AssistantEvenementsPage', {
        'count': drf_serializers.IntegerField(),
        'next': drf_serializers.CharField(allow_null=True),
        'previous': drf_serializers.CharField(allow_null=True),
        'results': drf_serializers.ListField(child=_EvenementAssistant)}))
    def get(self, request):
        from core.pagination import StandardPagination

        paginator = StandardPagination()
        page = paginator.paginate_queryset(
            _evenements_de_la_societe(request.user).order_by('-created_at'),
            request, view=self)
        return paginator.get_paginated_response(
            [_serialiser_evenement(ev) for ev in page])

    @extend_schema(request=EvenementAssistantEntreeSerializer,
                   responses={201: _EvenementAssistant})
    def post(self, request):
        data = request.data
        if not isinstance(data, dict) or not _types_evenement_valides(data):
            raise ParseError("Corps d'événement invalide (types publiés).")
        entree = EvenementAssistantEntreeSerializer(data=sans_nul(data))
        entree.is_valid(raise_exception=True)
        company = request.user.company
        if company is None:
            raise ParseError("Aucune société associée à l'utilisateur.")
        corps = {k: v for k, v in data.items() if k != 'preuve'}
        if not preuve_confirmation_valide(
                data.get('preuve'), action_key=ACTION_PREUVE_EVENEMENT,
                company_id=company.pk, user_id=request.user.pk,
                inputs=corps, object_id=None):
            raise PermissionDenied("Preuve du relais absente ou invalide.")
        v = entree.validated_data
        lead_id = v.get('lead_id')
        if lead_id is not None:
            from apps.crm.selectors import get_company_lead
            lead_id = lead_id if get_company_lead(company, lead_id) else None
        erreur = v.get('erreur')
        ev = AssistantEvent.objects.create(
            company=company, user=request.user,
            intention=v['intention'], question=v['question'],
            resume_reponse=(v.get('resume_reponse') or '')[:500],
            ecran=(v.get('ecran') or '')[:255], lead_id=lead_id,
            outils_appeles=v.get('outils_appeles') or [],
            erreur=erreur or None,
            modele=(v.get('modele') or '')[:64],
            repli=v.get('repli', False),
            manuel_present=v.get('manuel_present', False),
            tokens={k: int((v.get('tokens') or {}).get(k, 0))
                    for k in _CHAMPS_TOKENS},
        )
        return Response(_serialiser_evenement(ev),
                        status=status.HTTP_201_CREATED)


class AssistantEventNoteView(APIView):
    """AIC6 — ``PATCH /api/django/agent/evenements/<id>/note/`` : le commercial
    note SA réponse (note −1/0/1, commentaire ≤ 200). Seuls ces deux champs
    sont lus ; l'événement d'un autre utilisateur répond 404."""

    permission_classes = [IsAnyRole]
    parser_classes = [JSONParser]

    @extend_schema(request=NoteEvenementSerializer, responses=inline_serializer(
        'AssistantEvenementNote', {
            'id': drf_serializers.IntegerField(),
            'note': drf_serializers.IntegerField(),
            'commentaire': drf_serializers.CharField(allow_null=True)}))
    def patch(self, request, pk):
        data = request.data
        if not isinstance(data, dict) or isinstance(data.get('note'), bool) \
                or not isinstance(data.get('note'), int) or (
                    data.get('commentaire') is not None
                    and not isinstance(data.get('commentaire'), str)):
            raise ParseError('note est un entier (−1, 0, 1), commentaire un texte.')
        entree = NoteEvenementSerializer(data={
            'note': data.get('note'), 'commentaire': data.get('commentaire')})
        entree.is_valid(raise_exception=True)
        ev = AssistantEvent.objects.filter(
            pk=pk, user=request.user, company_id=request.user.company_id,
        ).first()
        if ev is None:
            return Response({'detail': 'Introuvable.'}, status=404)
        ev.note = entree.validated_data['note']
        ev.commentaire = sans_nul(entree.validated_data.get('commentaire')) or None
        ev.save(update_fields=['note', 'commentaire'])
        return Response({'id': ev.pk, 'note': ev.note,
                         'commentaire': ev.commentaire})


class AutomationDraftView(APIView):
    """XPLT18 — ``POST /api/django/agent/actions/automation-draft/``.

    Endpoint cible de l'action catalogue ``automation.rule.propose_draft``.
    Ne fait QUE relayer vers ``apps.automation.services`` (jamais d'import de
    ``apps.automation.models`` ici — frontière cross-app respectée) : c'est
    ce service qui re-valide le brouillon contre le catalogue fermé et crée
    la règle TOUJOURS désactivée. ``company`` est imposée depuis
    ``request.user`` (jamais depuis le corps).

    ASEC43 — même droit que le viewset canonique des automatisations
    (``IsAdminRole``) : un Viewer, un Commercial ou un compte portail
    reçoivent 403 sans brouillon créé."""

    permission_classes = [IsAnyRole, IsAdminRole]
    parser_classes = [JSONParser]

    @extend_schema(request=BrouillonAutomationSerializer, responses={201: inline_serializer(
        'AutomationBrouillonCree', {
            'id': drf_serializers.IntegerField(),
            'nom': drf_serializers.CharField(),
            'enabled': drf_serializers.BooleanField(),
            'trigger_type': drf_serializers.CharField(),
            'action_type': drf_serializers.CharField()})})
    def post(self, request):
        from apps.automation.services import DraftRuleError, \
            create_draft_rule_from_agent
        from rest_framework import status

        company = request.user.company
        if company is None:
            return Response(
                {'detail': "Aucune société associée à l'utilisateur."},
                status=status.HTTP_400_BAD_REQUEST)

        # ERR-ENF11-FUZZ-AGENT — le corps est validé contre le schéma publié
        # (400 par champ) ; le service re-valide le catalogue fermé.
        brouillon = BrouillonAutomationSerializer(data=sans_nul(request.data))
        brouillon.is_valid(raise_exception=True)
        data = brouillon.validated_data
        try:
            rule = create_draft_rule_from_agent(
                company=company,
                nom=data['nom'],
                trigger_type=data['trigger_type'],
                trigger_config=data.get('trigger_config') or {},
                action_type=data['action_type'],
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
