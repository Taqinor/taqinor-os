"""NTGRC4 — politique de rétention du journal d'audit pilotée par GRC.

Le journal d'audit est une pièce de preuve : sa fenêtre de conservation ne
descend JAMAIS sous le plancher légal (NTSEC17,
``selectors.effective_retention_days``). Une politique GRC plus courte que ce
plancher est donc relevée au plancher avant tout comptage — jamais l'inverse.

Le type d'objet ``audit_log`` est exposé en **signalement seul** : la purge
réelle reste le chemin dédié et audité ``manage.py purge_audit_log`` (qui
applique le plancher, archive en best-effort et trace ce qu'il fait). On ne
duplique pas un second chemin de suppression du journal de preuve.
"""
from __future__ import annotations

TYPES = ('audit_log',)

MOTIF_NON_APPLICABLE = (
    "Le journal d'audit est une pièce de preuve : la rétention GRC le SIGNALE "
    "et la purge réelle passe par `manage.py purge_audit_log`, qui applique le "
    "plancher légal."
)


def _echus(politique, now):
    """Lignes d'audit échues pour CETTE politique (bornées à sa société).

    La durée retenue est ``max(durée GRC, plancher légal)``.
    """
    from django.utils import timezone

    from .models import AuditLog
    from .selectors import effective_retention_days

    jours = effective_retention_days(politique['jours'])
    if jours <= 0:  # pragma: no cover - jours vient d'un PositiveInteger > 0
        return AuditLog.objects.none()
    cutoff = now - timezone.timedelta(days=jours)
    return AuditLog.objects.filter(
        company=politique['company'], timestamp__lt=cutoff)


def sweep_objets(now, apply_):
    """Compte les lignes d'audit hors fenêtre. Ne supprime jamais rien."""
    from apps.grc.selectors import politiques_retention_actives

    total = 0
    for politique in politiques_retention_actives(TYPES):
        total += _echus(politique, now).count()
    return total


def register():
    """Enregistre la politique Audit (idempotent, appelée en ready())."""
    from core.retention import register_retention_policy

    register_retention_policy('audit_logs_echus', sweep_objets)
