import json

from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminOrResponsableTier, IsAdminRole
from apps.parametres.models import SettingsAuditLog
from .models import Role, ALL_PERMISSIONS
from .serializers import RoleSerializer


def _perms_diff(old_perms, new_perms):
    """VX234 — diff structuré des permissions (set-difference), stocké en JSON
    dans old_value/new_value (TextField) : {"nom": ..., "ajoutees": [...],
    "retirees": [...], "total": N}. Un échange net-neutre (ex. retirer
    crm_supprimer + ajouter ventes_export) reste donc lisible au Journal au
    lieu d'un compte de permissions inchangé."""
    old_set, new_set = set(old_perms or []), set(new_perms or [])
    return sorted(new_set - old_set), sorted(old_set - new_set)


class RoleViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    Gestion des rôles d'une entreprise.
    Administrateur et Responsable (promu) peuvent créer/modifier/supprimer des
    rôles ; le palier limité reste bloqué.
    Les rôles système (est_systeme=True) ne peuvent pas être supprimés.
    Chaque création/modification/suppression écrit une ligne au Journal d'audit
    des paramètres (section='roles').
    """
    queryset = Role.objects.select_related('company').all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminOrResponsableTier]

    def get_permissions(self):
        # YRBAC10 — le CATALOGUE de permissions (source unique du gating
        # front↔back) est réservé à l'Administrateur : c'est une carte de
        # sécurité (permissions + enforcement par route), lue par un écran
        # admin, jamais nécessaire au palier Responsable. Le reste du viewset
        # garde son palier Administrateur/Responsable (comportement inchangé).
        if getattr(self, 'action', None) == 'permission_catalog':
            return [IsAdminRole()]
        return super().get_permissions()

    def get_queryset(self):
        return super().get_queryset().prefetch_related('users')

    def _audit(self, field, label, old, new):
        """Écrit une ligne d'audit company-scopée pour le rôle agissant."""
        user = self.request.user
        SettingsAuditLog.log_change(
            company=getattr(user, 'company', None), user=user,
            section='roles', field=field, field_label=label, old=old, new=new,
        )

    def perform_create(self, serializer):
        # TenantMixin force la société côté serveur (jamais depuis la requête).
        instance = serializer.save(company=self.request.user.company)
        ajoutees, _retirees = _perms_diff([], instance.permissions)
        self._audit(
            field=f'role:{instance.nom}',
            label='Rôle créé',
            old=None,
            new=json.dumps({
                'nom': instance.nom, 'ajoutees': ajoutees, 'retirees': [],
                'total': len(instance.permissions or []),
            }),
        )

    def perform_update(self, serializer):
        # ── Anti auto-escalade (ERR5) ─────────────────────────────────────
        # Un non-administrateur ne peut pas modifier les permissions du rôle
        # qui lui est ASSIGNÉ (changer son propre rôle pour s'octroyer des
        # droits). L'admin (roles_gerer/superuser) garde le contrôle total. La
        # garde des permissions élevées + rôles système vit dans le serializer ;
        # celle-ci ferme l'auto-escalade sur son propre rôle (même non système).
        user = self.request.user
        instance0 = serializer.instance
        if user.role_id == instance0.pk \
                and not getattr(user, 'is_admin_role', False):
            new_perms = serializer.validated_data.get('permissions')
            if new_perms is not None and \
                    sorted(new_perms or []) != sorted(instance0.permissions or []):
                raise PermissionDenied(
                    "Vous ne pouvez pas modifier les permissions de votre "
                    "propre rôle."
                )
        old_nom = serializer.instance.nom
        old_perms = sorted(serializer.instance.permissions or [])
        instance = serializer.save(company=self.request.user.company)
        new_perms = sorted(instance.permissions or [])
        if old_perms != new_perms or old_nom != instance.nom:
            ajoutees, retirees = _perms_diff(old_perms, new_perms)
            self._audit(
                field=f'role:{instance.nom}',
                label='Rôle modifié',
                old=json.dumps({'nom': old_nom, 'total': len(old_perms)}),
                new=json.dumps({
                    'nom': instance.nom, 'ajoutees': ajoutees, 'retirees': retirees,
                    'total': len(new_perms),
                }),
            )

    def perform_destroy(self, instance):
        if instance.est_systeme:
            raise PermissionDenied(
                "Les rôles système ne peuvent pas être supprimés."
            )
        if instance.users.exists():
            raise PermissionDenied(
                "Ce rôle est assigné à des utilisateurs. "
                "Réassignez-les avant de supprimer ce rôle."
            )
        nom = instance.nom
        perms_count = len(instance.permissions or [])
        instance.delete()
        self._audit(
            field=f'role:{nom}',
            label='Rôle supprimé',
            old=json.dumps({'nom': nom, 'total': perms_count}),
            new=None,
        )

    @action(detail=False, methods=['get'], url_path='permissions-disponibles')
    def permissions_disponibles(self, request):
        """Retourne la liste de toutes les permissions disponibles."""
        return Response({'permissions': ALL_PERMISSIONS})

    @action(detail=False, methods=['get'], url_path='permission-catalog')
    def permission_catalog(self, request):
        """YRBAC10 — Catalogue de permissions + carte d'enforcement par route.

        SOURCE UNIQUE (admin, lecture seule) alimentant le gating frontend
        (Sidebar, gardes de route, hook ``useHasPermission``) : plus de liste
        parallèle codée en dur côté SPA. Le catalogue expose

          - ``permissions`` : la matrice de codes ``ALL_PERMISSIONS`` ;
          - ``routes`` : la carte route→rôles RÉELLEMENT enforced, DÉRIVÉE de la
            matrice canonique YRBAC2 (``core.rbac_matrix``) — pour chaque
            endpoint de référence, la liste des rôles canoniques autorisés
            (verdict ``allow``). Un test de dérive front↔back compare cette
            carte au gating de la nav/routes et échoue sur tout décalage.

        ``core`` est FONDATION : sa lecture depuis ``roles`` est autorisée et
        n'introduit aucun import métier (le module ne déclare que des données)."""
        from core.rbac_matrix import MATRIX, ALLOW
        routes = [
            {
                'app': entry.app,
                'label': entry.label,
                'method': entry.method,
                'path': entry.path,
                'allowed_roles': sorted(
                    name for name, verdict in entry.verdicts.items()
                    if verdict == ALLOW
                ),
            }
            for entry in MATRIX
        ]
        return Response({'permissions': ALL_PERMISSIONS, 'routes': routes})
