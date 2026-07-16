import csv
import json
from datetime import timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminOrResponsableTier, IsAdminRole
from apps.parametres.models import SettingsAuditLog
from .models import Role, ALL_PERMISSIONS
from .serializers import RoleSerializer


class _CsvOrJSONRenderer(JSONRenderer):
    """XPLT12 — DRF négocie `?format=csv` AVANT le corps de la vue
    (`DefaultContentNegotiation`) : sans renderer déclaré pour `csv`, l'appel
    échoue en 404 en amont. On déclare le format sur l'action ; la vue renvoie
    ensuite un `HttpResponse` CSV manuel (JSON reste le défaut sans `?format`)."""
    format = 'csv'
    media_type = 'text/csv'


# XPLT12 — seuil par défaut (jours) au-delà duquel un compte est « dormant »
# (aucune connexion depuis N jours). Paramétrable via ``?dormant_days=N``.
DEFAULT_DORMANT_DAYS = 90


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
        # XPLT12 — la revue d'accès (certification : qui a quel rôle/permission,
        # dernière connexion, comptes dormants, 2FA, sessions) est un rapport de
        # sécurité réservé à l'Administrateur, jamais nécessaire au palier
        # Responsable.
        if getattr(self, 'action', None) in ('permission_catalog', 'revue_acces'):
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

    def _revue_acces_rows(self, request):
        """XPLT12 — construit les lignes de la revue d'accès pour la société
        ACTIVE de la requête.

        Une ligne par compte : rôle, permissions effectives, dernière connexion,
        statut dormant (aucune connexion depuis ``dormant_days`` jours), 2FA, et
        nombre de sessions actives (``authentication.UserSession`` N96, non
        révoquées). ``authentication`` est une app de FONDATION — sa lecture
        depuis ``roles`` est autorisée (jamais d'app métier importée)."""
        from authentication.models import CustomUser, UserSession

        try:
            dormant_days = int(request.query_params.get(
                'dormant_days', DEFAULT_DORMANT_DAYS))
        except (TypeError, ValueError):
            dormant_days = DEFAULT_DORMANT_DAYS
        if dormant_days < 0:
            dormant_days = DEFAULT_DORMANT_DAYS

        now = timezone.now()
        cutoff = now - timedelta(days=dormant_days)

        company = request.user.company
        users = (
            CustomUser.objects
            .filter(company=company)
            .select_related('role')
            .order_by('username')
        )

        # Sessions actives (non révoquées) par utilisateur, en une requête,
        # scopées à la même société.
        from django.db.models import Count
        session_counts = dict(
            UserSession.objects
            .filter(company=company, revoked=False)
            .values_list('user')
            .annotate(n=Count('id'))
        )

        rows = []
        for u in users:
            last_login = u.last_login
            if last_login is not None:
                jours = (now - last_login).days
                dormant = last_login < cutoff
            else:
                jours = None
                dormant = True  # jamais connecté → dormant
            if u.is_superuser:
                perms = list(ALL_PERMISSIONS)
            elif u.role_id:
                perms = list(u.role.permissions or [])
            else:
                perms = []
            rows.append({
                'id': u.id,
                'username': u.username,
                'email': u.email or '',
                'nom_complet': u.get_full_name() or '',
                'role': u.role.nom if u.role_id else None,
                'is_active': u.is_active,
                'last_login': last_login.isoformat() if last_login else None,
                'jours_depuis_connexion': jours,
                'dormant': dormant,
                'deux_fa': bool(u.totp_enabled),
                'sessions_actives': session_counts.get(u.id, 0),
                'permissions': perms,
            })
        return dormant_days, rows

    @action(detail=False, methods=['get'], url_path='revue-acces',
            renderer_classes=[_CsvOrJSONRenderer])
    def revue_acces(self, request):
        """XPLT12 — Rapport de revue d'accès & comptes dormants (admin).

        Certification périodique : pour chaque compte de la société active,
        rôle, permissions effectives, ``last_login``, statut dormant
        (> ``dormant_days`` jours sans connexion, défaut 90), 2FA activée et
        sessions actives. ``?format=csv`` renvoie l'export CSV pour archivage.
        """
        dormant_days, rows = self._revue_acces_rows(request)

        if (request.query_params.get('format') or '').lower() == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = (
                'attachment; filename="revue-acces.csv"')
            writer = csv.writer(response)
            writer.writerow([
                'username', 'email', 'nom_complet', 'role', 'actif',
                'derniere_connexion', 'jours_depuis_connexion', 'dormant',
                '2fa', 'sessions_actives', 'permissions',
            ])
            for r in rows:
                writer.writerow([
                    r['username'], r['email'], r['nom_complet'],
                    r['role'] or '', 'oui' if r['is_active'] else 'non',
                    r['last_login'] or '',
                    '' if r['jours_depuis_connexion'] is None
                    else r['jours_depuis_connexion'],
                    'oui' if r['dormant'] else 'non',
                    'oui' if r['deux_fa'] else 'non',
                    r['sessions_actives'],
                    '; '.join(r['permissions']),
                ])
            return response

        return Response({
            'dormant_days': dormant_days,
            'total': len(rows),
            'dormants': sum(1 for r in rows if r['dormant']),
            'utilisateurs': rows,
        })
