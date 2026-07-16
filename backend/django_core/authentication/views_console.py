"""SCA22 — Console fondateur des tenants (staff-only, SANS billing).

Endpoints réservés au SUPERUSER (fondateur/support) pour piloter les sociétés :

* ``GET  /api/django/auth/console/tenants/`` — liste des sociétés + compteurs
  d'usage simples (utilisateurs, devis, factures) lus via les selectors des apps
  cibles (jamais un import direct de leurs models) ;
* ``POST /api/django/auth/console/tenants/<id>/statut/`` — change le statut
  (actif / suspendu / fermeture) ; suspendre bloque immédiatement le tenant
  (SCA18) ;
* ``POST /api/django/auth/console/tenants/<id>/note/`` — pose la note libre
  ``plan_flag`` (annotation fondateur, jamais du billing).

Garde d'accès STRICTE : un non-staff reçoit 403 (``IsSuperuserConsole``). Aucune
donnée d'un tenant n'est exposée ici au-delà des compteurs agrégés.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Company


class IsSuperuserConsole(BasePermission):
    """Réservé au superuser (console fondateur). Tout autre compte → refusé."""
    message = "Accès réservé à la console fondateur."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)


def _usage_counts(company):
    """Compteurs d'usage simples d'une société (best-effort, via selectors)."""
    users = company.users.count()
    devis = factures = 0
    try:
        from apps.ventes import selectors as ventes_selectors
        devis = ventes_selectors.compter_devis(company)
        factures = ventes_selectors.compter_factures(company)
    except Exception:  # noqa: BLE001 — un selector KO ne casse pas la console
        pass
    return {'users': users, 'devis': devis, 'factures': factures}


def _tenant_payload(company):
    return {
        'id': company.id,
        'nom': company.nom,
        'slug': company.slug,
        'statut': company.statut,
        'statut_libelle': company.get_statut_display(),
        'actif': company.actif,
        'plan_flag': company.plan_flag,
        'benchmarking_opt_in': company.benchmarking_opt_in,
        'date_creation': company.date_creation,
        'date_fermeture': company.date_fermeture,
        'usage': _usage_counts(company),
    }


class TenantConsoleListView(APIView):
    """GET — liste toutes les sociétés + compteurs d'usage (superuser)."""
    permission_classes = [IsSuperuserConsole]

    def get(self, request):
        companies = Company.objects.all().order_by('nom')
        return Response([_tenant_payload(c) for c in companies])


class TenantConsoleStatutView(APIView):
    """POST — change le statut d'une société (actif/suspendu/fermeture)."""
    permission_classes = [IsSuperuserConsole]

    def post(self, request, pk):
        company = Company.objects.filter(pk=pk).first()
        if company is None:
            return Response({'detail': 'Société introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        statut = (request.data.get('statut') or '').strip()
        valides = {c[0] for c in Company.STATUT_CHOICES}
        if statut not in valides:
            return Response(
                {'detail': f'Statut invalide. Valeurs : {sorted(valides)}.'},
                status=status.HTTP_400_BAD_REQUEST)
        # La fermeture passe par le service dédié (horodate + délai de grâce).
        if statut == Company.STATUT_FERMETURE:
            from authentication import services
            services.mettre_en_fermeture(company, user=request.user)
        elif statut == Company.STATUT_ACTIF and \
                company.statut == Company.STATUT_FERMETURE:
            from authentication import services
            services.rouvrir(company, user=request.user)
        else:
            company.statut = statut
            company.save()
            _journaliser_statut(company, request.user, statut)
        company.refresh_from_db()
        return Response(_tenant_payload(company))


class TenantConsoleNoteView(APIView):
    """POST — pose la note libre ``plan_flag`` (fondateur, sans billing)."""
    permission_classes = [IsSuperuserConsole]

    def post(self, request, pk):
        company = Company.objects.filter(pk=pk).first()
        if company is None:
            return Response({'detail': 'Société introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        note = request.data.get('plan_flag', '')
        company.plan_flag = str(note)[:255]
        company.save(update_fields=['plan_flag'])
        return Response(_tenant_payload(company))


def _journaliser_statut(company, user, statut):
    try:
        from apps.audit.recorder import record
        from apps.audit.models import AuditLog
        record(AuditLog.Action.STATUS, user=user, company=company,
               detail=f'Statut tenant → {statut} (console fondateur).')
    except Exception:
        pass
