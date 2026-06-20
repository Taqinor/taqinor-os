from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsAdminRole
from apps.parametres.models import SettingsAuditLog
from .models import CustomFieldDef
from .serializers import CustomFieldDefSerializer


class CustomFieldDefViewSet(TenantMixin, viewsets.ModelViewSet):
    """Définitions de champs personnalisés (Paramètres). Lecture tout rôle
    (les formulaires en ont besoin), écriture admin. Filtre ?module=lead.
    Création/suppression d'une définition est journalisée au Journal d'audit
    des paramètres (section='champs')."""
    queryset = CustomFieldDef.objects.all()
    serializer_class = CustomFieldDefSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        module = self.request.query_params.get('module')
        if module:
            qs = qs.filter(module=module)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAdminRole()]

    def _audit(self, label, instance, old=None, new=None):
        """Écrit une ligne d'audit company-scopée (section='champs')."""
        user = self.request.user
        SettingsAuditLog.log_change(
            company=getattr(user, 'company', None), user=user,
            section='champs', field=f'{instance.module}.{instance.code}',
            field_label=label, old=old, new=new,
        )

    def perform_create(self, serializer):
        # L818 — TenantMixin force la société côté serveur (jamais du corps).
        instance = serializer.save(company=self.request.user.company)
        self._audit('Champ personnalisé créé', instance,
                    old=None, new=instance.libelle)

    def perform_destroy(self, instance):
        # L818 — journaliser avant suppression (le custom_data des
        # enregistrements n'est pas touché : approche additive).
        self._audit('Champ personnalisé supprimé', instance,
                    old=instance.libelle, new=None)
        instance.delete()

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """L813 — réordonne les définitions d'un module. Corps : une liste
        d'ids dans l'ordre voulu ({"ids": [3, 1, 2]}). `ordre` est posé selon
        la position ; seules les définitions de la société courante sont
        affectées."""
        ids = request.data.get('ids') or []
        if not isinstance(ids, list):
            return Response({'detail': 'Liste d’ids attendue.'}, status=400)
        defs = {d.id: d for d in self.get_queryset().filter(id__in=ids)}
        for position, def_id in enumerate(ids):
            d = defs.get(def_id)
            if d is not None and d.ordre != position:
                d.ordre = position
                d.save(update_fields=['ordre'])
        return Response({'ok': True, 'count': len(defs)})
