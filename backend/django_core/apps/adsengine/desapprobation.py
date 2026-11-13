"""AERR24 (D-AERR-1 = desapprouver) — retirer l'approbation d'une action
publicitaire tant qu'elle n'est pas appliquée. Hors des murs ``services.py`` /
``views.py`` (C20) : service + mixin d'action monté sur ``EngineActionViewSet``
(droit ``adsengine_approve`` via ``_APPROVE_ACTIONS``)."""
from rest_framework.decorators import action
from rest_framework.response import Response


def desapprouver_action(action_obj, *, user):
    """Remet une action APPROUVÉE (non appliquée) à PROPOSÉE. ENGFIX3 : verrou
    de ligne + re-vérification du statut sous le verrou (course contre
    ``apply_action``) ; ``approved_by`` vidé."""
    from django.db import transaction

    from .models import EngineAction
    with transaction.atomic():
        locked = EngineAction.objects.select_for_update().filter(pk=action_obj.pk).first()
        if locked is None or locked.status != EngineAction.Statut.APPROUVEE:
            raise ValueError("Seule une action approuvée, pas encore appliquée, peut être désapprouvée.")
        locked.status = EngineAction.Statut.PROPOSEE
        locked.approved_by = None
        locked.save(update_fields=['status', 'approved_by', 'updated_at'])
    action_obj.status = EngineAction.Statut.PROPOSEE
    action_obj.approved_by = None
    return action_obj


class DesapprouverActionMixin:
    @action(detail=True, methods=['post'])
    def desapprouver(self, request, pk=None):
        """AERR24 — retire l'approbation (action de nouveau « proposée »)."""
        instance = self.get_object()
        try:
            desapprouver_action(instance, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(self.get_serializer(instance).data)
