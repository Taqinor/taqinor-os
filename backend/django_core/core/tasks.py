"""Tâches Celery de la couche fondation ``core`` (autodécouvertes par
``erp_agentique.celery`` comme ``apps.ventes.tasks``).

  * YOPSB1 — ``core.dump_database`` : pg_dump quotidien réel vers MinIO
    (03:00 Africa/Casablanca), journalisé en ``BackupRun``.
  * YOPSB2 — ``core.restore_drill`` : drill de restauration hebdomadaire
    (lundi 04:00), restaure le dernier dump dans une base JETABLE et vérifie
    des comptages clés — jamais la base de production.
  * YOPSB3 — ``core.purge_backups`` : purge GFS quotidienne des dumps
    (05:00), DRY-RUN tant que ``BACKUP_PURGE_AUTO_APPLY`` n'est pas activé.
  * YOPSB10 — ``core.run_retention`` : sweep quotidien (02:00) de TOUTES les
    politiques de rétention enregistrées (``core.retention``), DRY-RUN tant
    que ``RETENTION_AUTO_APPLY`` n'est pas activé.
  * YHARD6 — ``core.beat_heartbeat`` : tick fréquent (toutes les 5 min) qui
    écrit un timestamp dans le cache (``core.metrics.mark_beat_heartbeat``) —
    permet à ``/metrics`` et ``core/health.py`` de détecter un beat arrêté.

Toute la logique vit dans ``core.backup``/``core.retention`` (testable sans
Celery) ; ces tâches ne sont qu'une fine enveloppe planifiable, comme les
autres tâches du dépôt (cf. apps/ged/tasks.py)."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='core.dump_database')
def dump_database_task():
    """YOPSB1 — pg_dump quotidien réel vers MinIO (planifié 03:00)."""
    from core.models import BackupRun

    from . import backup

    run = BackupRun.objects.create(
        kind=BackupRun.KIND_DB_DUMP, mode=BackupRun.MODE_PLANIFIE,
        company=None)
    run = backup.dump_database(run)
    logger.info('core.dump_database: statut=%s run=%s', run.statut, run.pk)
    return {'statut': run.statut, 'run_id': run.pk}


@shared_task(name='core.restore_drill')
def restore_drill_task():
    """YOPSB2 — drill de restauration hebdomadaire (planifié lundi 04:00)."""
    from core.models import BackupRun

    from . import backup

    run = BackupRun.objects.create(
        kind=BackupRun.KIND_RESTORE_DRILL, mode=BackupRun.MODE_PLANIFIE,
        company=None)
    run = backup.restore_drill(run)
    logger.info('core.restore_drill: statut=%s run=%s', run.statut, run.pk)
    return {'statut': run.statut, 'run_id': run.pk}


@shared_task(name='core.purge_backups')
def purge_backups_task():
    """YOPSB3 — purge GFS quotidienne des dumps (planifié 05:00).

    DRY-RUN par défaut (``settings.BACKUP_PURGE_AUTO_APPLY``) : ne supprime
    rien tant que le drapeau n'est pas explicitement vrai."""
    from django.conf import settings

    from . import backup

    apply_ = bool(getattr(settings, 'BACKUP_PURGE_AUTO_APPLY', False))
    result = backup.purger_backups(apply_=apply_)
    logger.info('core.purge_backups: apply=%s conserves=%d supprimes=%d',
                apply_, result['conserves'], result['supprimes'])
    return result


@shared_task(name='core.run_retention')
def run_retention_task():
    """YOPSB10 — sweep quotidien de toutes les politiques de rétention
    enregistrées (planifié 02:00). DRY-RUN par défaut
    (``settings.RETENTION_AUTO_APPLY``) : chaque politique reçoit
    ``apply_=False`` tant que le drapeau n'est pas explicitement vrai."""
    from django.conf import settings

    from . import retention

    apply_ = bool(getattr(settings, 'RETENTION_AUTO_APPLY', False))
    results = retention.run_all_policies(apply_=apply_)
    logger.info('core.run_retention: apply=%s policies=%d',
                apply_, len(results))
    return results


@shared_task(name='core.beat_heartbeat')
def beat_heartbeat_task():
    """YHARD6 — tick de heartbeat du beat (planifié toutes les 5 min).

    Écrit best-effort un timestamp dans le cache ; consommé par
    ``core.metrics.beat_heartbeat_age_seconds`` (endpoint ``/metrics``) et par
    ``core/health.py`` (statut ``degraded`` si le beat est arrêté)."""
    from . import metrics

    metrics.mark_beat_heartbeat()
    return {'ok': True}


@shared_task(name='core.dispatch_outbox')
def dispatch_outbox_task():
    """NTPLT10 — livraison des événements outbox aux handlers durables.

    Filet beat (toutes les 5 min) en plus de l'enqueue immédiat on_commit :
    livre les événements ``pending``/``failed`` échus, applique retries
    exponentiels bornés puis dead-letter. Idempotente (re-run ne double-livre
    pas — dédup ``ProcessedEvent``). Queue ``default``."""
    from . import dispatch_outbox

    counts = dispatch_outbox.dispatch_pending()
    logger.info('core.dispatch_outbox: livrés=%d échecs=%d dead=%d',
                counts['delivered'], counts['failed'], counts['dead'])
    return counts


@shared_task(name='core.scan_live_isolation')
def scan_live_isolation_task():
    """NTPLT8 — scan mensuel DRY-RUN d'étanchéité des DONNÉES vivantes.

    Vérifie sur la base RÉELLE qu'aucune ligne des tables company-scopées n'a un
    ``company_id`` NULL ou orphelin (société supprimée). Complète YRBAC12 (qui
    teste le CODE en CI) par un contrôle des DONNÉES en prod. Ne modifie rien ;
    remonte les anomalies aux admins + audit via le reporteur enregistré."""
    from . import tenant_isolation_scan

    report = tenant_isolation_scan.scan_live_isolation()
    logger.info('core.scan_live_isolation: %d anomalie(s) sur %d table(s)',
                report['anomalies'], report['scanned'])
    return {'anomalies': report['anomalies'], 'scanned': report['scanned']}


@shared_task(name='core.ensure_partitions')
def ensure_partitions_task():
    """NTPLT36 — maintenance des partitions mensuelles À L'AVANCE.

    Crée le mois courant + M+1/M+2 de chaque table partitionnée enregistrée
    (``core.partitioning``), pour qu'une insertion future ait toujours sa
    partition prête. Idempotent (re-run ne recrée rien). Queue ``scheduled``."""
    from . import ensure_partitions

    results = ensure_partitions.ensure_all()
    logger.info('core.ensure_partitions: %d table(s) maintenue(s)',
                len(results))
    return {t: len(p) for t, p in results.items()}


@shared_task(name='core.snapshot_tenant_usage')
def snapshot_tenant_usage_task():
    """NTPLT6 — instantané NOCTURNE d'usage par tenant (metering).

    Une ligne ``TenantUsageSnapshot`` par (société, jour), idempotente (un
    re-run du jour met à jour la même ligne). Comptages BORNÉS. Fondation de
    N100 (plans/billing, différé). Queue ``scheduled`` (tâche planifiée)."""
    from . import usage

    done = usage.snapshot_all()
    logger.info('core.snapshot_tenant_usage: %d société(s) mesurée(s)',
                len(done))
    return {'companies': len(done)}


@shared_task(name='core.purge_idempotency_records')
def purge_idempotency_records_task():
    """YAPIC10 — purge quotidienne des ``IdempotencyRecord`` (YAPIC9) plus
    vieux que 24 h (fenêtre alignée sur la pratique Stripe pour
    ``Idempotency-Key``, documentée dans ``docs/api-conventions.md``).

    Idempotente (un re-run ne supprime rien de plus) et company-agnostique
    (purge par ``created_at``, jamais par société — une clé d'idempotence
    n'a plus de sens à rejouer passé la fenêtre, quel que soit le tenant).
    Queue ``scheduled``."""
    from django.utils import timezone

    from .idempotency import IdempotencyRecord

    cutoff = timezone.now() - timezone.timedelta(hours=24)
    deleted, _ = IdempotencyRecord.objects.filter(
        created_at__lt=cutoff).delete()
    logger.info('core.purge_idempotency_records: supprimés=%d', deleted)
    return {'deleted': deleted}


@shared_task(name='core.escalate_workflow_sla')
def escalate_workflow_sla_task():
    """FG366 / WIR50 — escalade HORAIRE des étapes de workflow au SLA dépassé.

    La commande ``escalate_workflow_sla`` documentait « à câbler sur Celery
    Beat » sans y figurer : une ``WorkflowStepInstance`` en attente dont
    l'échéance SLA est passée n'était jamais escaladée automatiquement.
    Enveloppe fine : délègue à la commande homonyme (balayage PAR SOCIÉTÉ,
    ``sla_echeance < now``), idempotente."""
    from django.core.management import call_command

    call_command('escalate_workflow_sla')
    logger.info('core.escalate_workflow_sla: balayage terminé.')
    # Contrat WIR50 des enveloppes de sécurité : un accusé {'ok': True} (même
    # forme que ``authentication.desactiver_comptes_dormants``), pour qu'un
    # résultat Celery vide ne se confonde pas avec une tâche qui n'a rien fait.
    return {'ok': True}


@shared_task(name='core.executer_exports_planifies')
def executer_exports_planifies_task():
    """NTDATA26 — exécute les extraits planifiés DUS (beat HORAIRE).

    ``ScheduledExport.cron`` portait déjà la cadence, mais rien ne la LISAIT :
    un extrait « quotidien » ne partait que si quelqu'un cliquait « exécuter ».
    Ce job ferme le trou.

    SOCIÉTÉS ACTIVES UNIQUEMENT (SCA19) : un extrait part vers une destination
    EXTERNE (entrepôt, SFTP, S3, Snowflake) — un tenant suspendu ou en
    fermeture ne doit plus rien émettre. Une destination non configurée reste
    un no-op propre, horodaté ``dernier_statut='non_configure'``."""
    from authentication.selectors import active_companies

    from . import scheduled_export

    recap = scheduled_export.executer_exports_dus(
        companies=list(active_companies()))
    logger.info('core.executer_exports_planifies: %s extrait(s) exécuté(s).',
                len(recap))
    return recap


@shared_task(name='core.generer_sla_mensuel')
def generer_sla_mensuel_task():
    """NTOBS3 — génère le snapshot SLA mensuel de toutes les sociétés actives
    (planifié le 1er du mois). Enveloppe fine de la commande homonyme."""
    from django.core.management import call_command

    call_command('generer_sla_mensuel')
    logger.info('core.generer_sla_mensuel: génération terminée.')
    return {'ok': True}


REVERSIBILITE_BUCKET = 'erp-reversibilite'


def _marquer_run(run_id, **champs):
    """NTOBS7 — met à jour l'``ExportReversibiliteRun`` d'historique, si son
    id a été fourni (best-effort, jamais bloquant : NTOBS6 seul — sans
    ``run_id`` — reste valide)."""
    if not run_id:
        return
    try:
        from .export_registry import ExportReversibiliteRun
        ExportReversibiliteRun.objects.filter(pk=run_id).update(**champs)
    except Exception:  # noqa: BLE001 — best-effort
        logger.exception(
            'core._marquer_run: échec mise à jour run %s.', run_id)


@shared_task(name='core.export_reversibilite_tenant')
def export_reversibilite_tenant(
        company_id, demande_par_id=None, datasets=None, run_id=None):
    """NTOBS6/NTOBS7 — construit le ZIP de réversibilité complet d'une
    société (CSV par dataset enregistré, ``core.export_registry`` — JAMAIS
    ``prix_achat``/champ interne-only), notifie le demandeur avec un lien
    tokenisé expirant sous 7 jours (``core.signed_download``), et fait
    progresser l'``ExportReversibiliteRun`` d'historique (``run_id``,
    optionnel — NTOBS7).

    ``datasets`` (NTOBS20, hors périmètre de ce lot) : optionnel, sous-liste
    de noms de datasets — absence = comportement par défaut (tout)."""
    import io
    import json
    import zipfile

    from django.utils import timezone as dj_timezone

    from authentication.models import Company

    from . import export_registry, signed_download
    from .export_registry import ExportReversibiliteRun

    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        logger.warning(
            'core.export_reversibilite_tenant: société %s introuvable.',
            company_id)
        _marquer_run(run_id, statut=ExportReversibiliteRun.Statut.ECHEC)
        return {'ok': False}

    fichiers, comptes = export_registry.export_all_datasets(company)
    if datasets:
        fichiers = {
            nom: contenu for nom, contenu in fichiers.items()
            if nom[:-4] in datasets  # nom = '<dataset>.csv'
        }
        comptes = {k: v for k, v in comptes.items() if k in datasets}

    manifest = {
        'company_id': company.id,
        'genere_le': dj_timezone.now().isoformat(),
        'datasets': comptes,
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for nom, contenu in fichiers.items():
            zf.writestr(nom, contenu)
        zf.writestr(
            'manifest.json',
            json.dumps(manifest, indent=2, ensure_ascii=False))
    taille = buf.tell()
    buf.seek(0)

    from .backup import _minio_client

    object_key = (
        f'{company.id}/export-{dj_timezone.now():%Y%m%d%H%M%S}.zip')
    try:
        client = _minio_client()
        try:
            client.head_bucket(Bucket=REVERSIBILITE_BUCKET)
        except Exception:  # noqa: BLE001 — best-effort, bucket peut-être absent
            try:
                client.create_bucket(Bucket=REVERSIBILITE_BUCKET)
            except Exception:  # noqa: BLE001
                pass
        client.put_object(
            Bucket=REVERSIBILITE_BUCKET, Key=object_key, Body=buf.getvalue())
    except Exception:  # noqa: BLE001 — jamais bloquant, journalisé
        logger.exception(
            'core.export_reversibilite_tenant: échec upload MinIO '
            '(société %s).', company.id)
        _marquer_run(run_id, statut=ExportReversibiliteRun.Statut.ECHEC)
        return {'ok': False}

    lien = signed_download.creer_lien(
        company, REVERSIBILITE_BUCKET, object_key, taille_octets=taille)
    _marquer_run(
        run_id, statut=ExportReversibiliteRun.Statut.PRET,
        fichier_key=object_key, taille_octets=taille, token=lien.token,
        expire_le=lien.expire_le)

    if demande_par_id:
        try:
            from authentication.models import CustomUser

            from . import notify_registry

            demandeur = CustomUser.objects.filter(pk=demande_par_id).first()
            if demandeur:
                # 'export_reversibilite_pret' reflète apps.notifications.
                # models.EventType.EXPORT_REVERSIBILITE_PRET — passé en
                # string littéral, jamais un import d'apps.notifications
                # (contrat import-linter core-foundation-is-a-base-layer).
                notify_registry.notify(
                    demandeur, 'export_reversibilite_pret',
                    'Votre export de données est prêt',
                    body='Le lien expire dans 7 jours.',
                    link=f'/api/django/core/export-reversibilite/'
                         f'telecharger/{lien.token}/',
                    company=company,
                )
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.exception(
                'core.export_reversibilite_tenant: notification échouée '
                '(société %s).', company.id)

    return {'ok': True, 'token': lien.token, 'taille_octets': taille}


@shared_task(name='core.notifier_fenetres_maintenance')
def notifier_fenetres_maintenance_task():
    """NTOBS9 — notifie 24h/1h avant une fenêtre de maintenance planifiée
    (beat toutes les 15 min). Enveloppe fine de
    ``core.maintenance_windows`` (nommage distinct de ``core.maintenance``,
    NTPLT55, une fonctionnalité totalement différente)."""
    from . import maintenance_windows

    n = maintenance_windows.notifier_fenetres_a_venir()
    logger.info('core.notifier_fenetres_maintenance: %d notification(s).', n)
    return {'notifies': n}


@shared_task(name='core.notifier_seuils_usage')
def notifier_seuils_usage_task():
    """NTOBS13 — notifie chaque société franchissant 80%/100% d'un quota
    mesuré (beat quotidien). Enveloppe fine de ``core.usage_limits``."""
    from . import usage_limits

    n = usage_limits.notifier_seuils_usage()
    logger.info('core.notifier_seuils_usage: %d notification(s).', n)
    return {'notifies': n}
