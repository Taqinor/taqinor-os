"""NTEXT20/NTEXT21 — API des points d'extension UI (boutons + onglets custom).

``GET core/ui-boutons/?cible=crm.lead`` et ``GET core/ui-onglets/
?cible=ventes.devis`` renvoient les éléments APPLICABLES au demandeur : actifs
+ (``role_tier`` vide ou égal à son palier). Sans ``cible``, la liste couvre
TOUTE la société (écran d'administration : gérer aussi les éléments inactifs/
réservés à un autre palier). Écriture réservée à l'administration.
"""
from django.db.models import Q
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsAdminRole, IsAnyRole

from . import ui_extensions
from .models import UiActionBouton, UiOngletCustom
from .viewsets import CompanyScopedModelViewSet


def _applicable_queryset(qs, request):
    """Filtre ``actif`` + palier de rôle du demandeur (``menu_tier``)."""
    tier = getattr(request.user, 'menu_tier', None)
    return qs.filter(actif=True).filter(Q(role_tier='') | Q(role_tier=tier))


def _resolve_generic(target_model, target_id, company):
    """Résout ``app_label.model``:pk en instance, scopée société si le
    modèle porte une FK ``company``. ``django.apps.apps.get_model`` est une
    résolution PAR CHAÎNE (jamais un import statique d'app) — le même patron
    que le test noyau AUD422 : ``core`` reste une couche de FONDATION."""
    from django.apps import apps as django_apps
    try:
        app_label, model_name = target_model.split('.', 1)
        model = django_apps.get_model(app_label, model_name)
        lookup = {'pk': target_id}
        if company is not None and any(
                f.name == 'company' for f in model._meta.concrete_fields):
            lookup['company'] = company
        return model.objects.filter(**lookup).first()
    except Exception:  # pragma: no cover - défensif
        return None


def _instance_field_context(instance):
    """Valeurs des champs concrets de l'instance (pour l'évaluation de
    ``condition``) — ignore les relations, ne lève jamais."""
    out = {}
    if instance is None:
        return out
    try:
        for f in instance._meta.concrete_fields:
            if f.is_relation:
                continue
            try:
                out[f.attname] = getattr(instance, f.attname)
            except Exception:  # pragma: no cover - défensif
                continue
    except Exception:  # pragma: no cover - défensif
        pass
    return out


class UiActionBoutonSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiActionBouton
        fields = ['id', 'cible', 'libelle', 'icone', 'type_action', 'ref',
                  'role_tier', 'ordre', 'actif', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class UiActionBoutonViewSet(CompanyScopedModelViewSet):
    """NTEXT20 — boutons custom posés sur une fiche."""
    serializer_class = UiActionBoutonSerializer
    queryset = UiActionBouton.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        cible = self.request.query_params.get('cible')
        if cible:
            qs = qs.filter(cible=cible)
            if self.action == 'list':
                qs = _applicable_queryset(qs, self.request)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAdminRole()]

    @action(detail=True, methods=['post'])
    def declencher(self, request, pk=None):
        """Déclenche l'action liée sur un enregistrement précis.

        Corps : ``{"target_model": "crm.lead", "target_id": 12}``. Le
        déclenchement RÉEL est délégué au gestionnaire enregistré pour le
        ``type_action`` du bouton (``ui_extensions.declencher_bouton`` — même
        patron que ``core.workflow.register_delegation_resolver``) : ``core``
        n'exécute directement AUCUNE automatisation/webhook/action serveur."""
        bouton = self.get_object()
        target_model = (request.data.get('target_model') or '').strip()
        target_id = request.data.get('target_id')
        if not target_model or not target_id:
            return Response(
                {'detail': '« target_model » et « target_id » sont requis.'},
                status=400)
        ok, message = ui_extensions.declencher_bouton(
            bouton, target_model, target_id, user=request.user)
        return Response({'ok': ok, 'message': message})


class UiOngletCustomSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiOngletCustom
        fields = ['id', 'cible', 'titre', 'type_contenu', 'ref', 'condition',
                  'ordre', 'role_tier', 'actif', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_condition(self, value):
        if value in (None, ''):
            return value
        from core.rules import validate_condition_group
        errors = validate_condition_group(value)
        if errors:
            raise serializers.ValidationError('; '.join(errors))
        return value


class UiOngletCustomViewSet(CompanyScopedModelViewSet):
    """NTEXT21 — onglets custom posés sur une fiche.

    ``GET ?cible=ventes.devis`` renvoie les onglets applicables (actifs +
    palier). Avec ``&target_id=<id>`` en plus : la ``condition`` (arbre
    core.rules) de chaque onglet est évaluée sur les champs de CET
    enregistrement (un onglet dont la condition est fausse est omis), et un
    onglet ``objet_custom_lie`` embarque son ``contenu`` (les enregistrements
    liés — ``ui_extensions.resoudre_contenu_onglet``)."""
    serializer_class = UiOngletCustomSerializer
    queryset = UiOngletCustom.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        cible = self.request.query_params.get('cible')
        if cible:
            qs = qs.filter(cible=cible)
            if self.action == 'list':
                qs = _applicable_queryset(qs, self.request)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        onglets = list(queryset)
        data = self.get_serializer(onglets, many=True).data

        cible = request.query_params.get('cible')
        target_id = request.query_params.get('target_id')
        if not (cible and target_id):
            return Response(data)

        instance = _resolve_generic(cible, target_id, request.user.company)
        eval_ctx = _instance_field_context(instance)
        onglets_par_id = {o.pk: o for o in onglets}
        resultat = []
        for item in data:
            onglet = onglets_par_id.get(item['id'])
            if onglet is None:
                continue
            if onglet.condition:
                from core.rules import evaluate_condition_group
                if not evaluate_condition_group(onglet.condition, eval_ctx):
                    continue
            if onglet.type_contenu == UiOngletCustom.TypeContenu.OBJET_CUSTOM_LIE:
                item['contenu'] = ui_extensions.resoudre_contenu_onglet(
                    onglet, cible, target_id)
            resultat.append(item)
        return Response(resultat)
