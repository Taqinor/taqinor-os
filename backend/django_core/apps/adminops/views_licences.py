"""NTADM8/9 — Licences & sièges.

NTADM8 : statut d'usage des sièges (utilisés/max) — alimente la bannière NON
BLOQUANTE de l'écran Utilisateurs (le dépassement de quota n'empêche jamais la
création d'un compte, voir ``apps.adminops.receivers`` pour l'alerte de
franchissement).

NTADM9 : écran admin « Licences & sièges » — même endpoint, complété du
palier de licence (``CompanyProfile.plan``), des modules inclus et de
l'historique des changements de plan (réutilise ``SettingsAuditLog``, N55 —
jamais un second journal maison).

Lecture seule, gardé Administrateur (``IsAdministrateur``, même pattern que le
reste de cette app) ; NTADM39 affine l'accès fin (``adminops_licences_voir``,
rétrocompat rôles système — voir ``permissions.py``)."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.parametres.models import CompanyProfile
from authentication.services import sieges_utilises as _sieges_utilises

from .permissions import IsAdministrateur


def _statut_sieges(company, profile):
    utilises = _sieges_utilises(company)
    max_sieges = profile.nb_sieges_max
    quota_atteint = bool(max_sieges) and utilises >= max_sieges
    return {
        'sieges_utilises': utilises,
        'sieges_max': max_sieges,
        'quota_atteint': quota_atteint,
    }


def _statut_plan(profile):
    plan = profile.plan
    if plan is None:
        return None
    return {
        'code': plan.code,
        'nom': plan.nom,
        'modules_inclus': list(plan.modules_inclus or []),
    }


def _historique_plan(company):
    """NTADM9 — historique des changements de plan (réutilise
    ``SettingsAuditLog`` N55, section 'licence', jamais un second journal)."""
    from apps.parametres.models import SettingsAuditLog
    lignes = (
        SettingsAuditLog.objects
        .filter(company=company, section='licence', field='plan')
        .order_by('-timestamp')[:50]
    )
    return [
        {
            'ancien_plan': ligne.old_value,
            'nouveau_plan': ligne.new_value,
            'par': (ligne.user.get_full_name() or ligne.user.username) if ligne.user else '',
            'le': ligne.timestamp.isoformat() if ligne.timestamp else None,
        }
        for ligne in lignes
    ]


@api_view(['GET'])
@permission_classes([IsAdministrateur])
def licence_statut_view(request):
    """NTADM8/9 — statut de licence complet : plan, modules inclus, sièges
    utilisés/max, historique des changements de plan."""
    company = request.user.company
    profile = CompanyProfile.get(company=company)
    return Response({
        'plan': _statut_plan(profile),
        **_statut_sieges(company, profile),
        'historique_plan': _historique_plan(company),
    })
