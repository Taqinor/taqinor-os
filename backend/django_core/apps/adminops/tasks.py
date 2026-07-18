"""apps.adminops.tasks — jobs Celery beat (best-effort, jamais bloquants).
Enregistrés dans `erp_agentique/celery.py::beat_schedule` +
`CELERY_TASK_ROUTES` (settings/base.py)."""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='adminops.cloner_sandbox')
def cloner_sandbox(sandbox_env_id):
    """NTADM10 — clonage asynchrone déclenché par `sandbox_service.creer_sandbox`."""
    from .sandbox_service import cloner_sandbox_sync
    cloner_sandbox_sync(sandbox_env_id)


@shared_task(name='adminops.purger_sandbox_expires')
def purger_sandbox_expires():
    """NTADM11 — quotidien : un sandbox expiré passe `sandbox_company.actif=False`
    immédiatement, puis est HARD-supprimé après le délai de grâce (défaut 7j,
    réglable par tenant via `AdminOpsSettings`)."""
    from .models import AdminOpsSettings, SandboxEnvironment

    now = timezone.now()
    expires = SandboxEnvironment.objects.filter(
        statut=SandboxEnvironment.Statut.PRET, date_expiration__lte=now)
    for env in expires:
        env.statut = SandboxEnvironment.Statut.EXPIRE
        env.save(update_fields=['statut'])
        if env.sandbox_company is not None:
            env.sandbox_company.actif = False
            env.sandbox_company.save(update_fields=['actif'])

    # Hard-delete après le délai de grâce.
    a_purger = SandboxEnvironment.objects.filter(
        statut=SandboxEnvironment.Statut.EXPIRE)
    for env in a_purger:
        reglage = AdminOpsSettings.get_or_default(env.company)
        grace = timezone.timedelta(days=reglage.sandbox_grace_purge_jours)
        if now >= env.date_expiration + grace:
            sandbox_company = env.sandbox_company
            env.sandbox_company = None
            env.save(update_fields=['sandbox_company'])
            if sandbox_company is not None:
                sandbox_company.delete()


@shared_task(name='adminops.rappeler_sandbox_a_expirer')
def rappeler_sandbox_a_expirer():
    """NTADM35 (J-3) + rappel J-48h (NTADM11) — best-effort, dédup par flag."""
    from .models import SandboxEnvironment

    now = timezone.now()
    pret = SandboxEnvironment.objects.filter(
        statut=SandboxEnvironment.Statut.PRET, cree_par__isnull=False)
    for env in pret:
        restant = env.date_expiration - now
        if not env.rappel_j3_envoye and restant <= timezone.timedelta(days=3):
            _notifier_expiration(env, 'dans 3 jours')
            env.rappel_j3_envoye = True
            env.save(update_fields=['rappel_j3_envoye'])
        if not env.rappel_48h_envoye and restant <= timezone.timedelta(hours=48):
            _notifier_expiration(env, 'dans 48 heures')
            env.rappel_48h_envoye = True
            env.save(update_fields=['rappel_48h_envoye'])


def _notifier_expiration(env, delai_txt):
    try:
        # EventType.DIGEST — même repli générique que `apps.credit.tasks`
        # pour un événement cross-app sans type dédié (ajouter un nouveau
        # choix à `EventType` exigerait une migration dans `apps.notifications`,
        # hors périmètre de cette lane).
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        notify(
            env.cree_par, EventType.DIGEST,
            'Sandbox bientôt expiré',
            body=f"Votre environnement sandbox expire {delai_txt}.",
            company=env.company)
    except Exception:  # pragma: no cover - best-effort
        logger.warning('adminops: notification sandbox expiration échouée')


@shared_task(name='adminops.recalculer_health_score_tenants')
def recalculer_health_score_tenants():
    """NTADM36 — recalcule et persiste le score NTADM5 pour chaque tenant actif."""
    from authentication.models import Company

    from .health_score import calculer_health_score
    from .models import HealthScoreSnapshot

    for company in Company.objects.filter(actif=True):
        resultat = calculer_health_score(company)
        HealthScoreSnapshot.objects.create(
            company=company, score=resultat['score'],
            sous_scores=resultat['sous_scores'])


@shared_task(name='adminops.purger_config_packages_anciens')
def purger_config_packages_anciens():
    """NTADM38 — mensuel : vide le `contenu` JSON (garde la ligne de
    métadonnées) des `ConfigPackage` de plus de 12 mois."""
    from .models import ConfigPackage

    seuil = timezone.now() - timezone.timedelta(days=365)
    ConfigPackage.objects.filter(
        date_creation__lt=seuil, contenu_purge=False).update(
        contenu={}, contenu_purge=True)


@shared_task(name='adminops.purger_evenements_usage')
def purger_evenements_usage():
    """NTADM16 — purge des `EvenementUsage` au-delà de la rétention configurée
    (défaut 180j, RGPD/CNDP-safe). Rétention par tenant via `AdminOpsSettings`."""
    from authentication.models import Company

    from .models import AdminOpsSettings, EvenementUsage

    for company in Company.objects.filter(actif=True):
        reglage = AdminOpsSettings.get_or_default(company)
        seuil = timezone.now() - timezone.timedelta(
            days=reglage.retention_evenements_usage_jours)
        EvenementUsage.objects.filter(
            company=company, horodatage__lt=seuil).delete()
