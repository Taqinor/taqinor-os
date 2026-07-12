"""FG368 — Introspection des jobs planifiés (Celery Beat).

Brique fondation : lit la configuration des tâches périodiques pour la
présenter dans l'écran Paramètres « Tâches planifiées ». Aucune dépendance
domaine — uniquement l'infra Celery (``from celery import current_app``), ce
qui garde ``core`` au rang de couche de base (import-linter).

Deux sources sont fusionnées, la seconde étant optionnelle :

  1. ``current_app.conf.beat_schedule`` — la planification STATIQUE déclarée
     dans ``erp_agentique/celery.py`` (toujours présente).
  2. ``django_celery_beat.models.PeriodicTask`` — la planification dynamique en
     base SI l'app est installée. On dégrade proprement (rien) quand elle ne
     l'est pas : aujourd'hui elle n'est pas installée, et le code ne doit pas
     s'en plaindre.

La forme normalisée d'un job est :

    {
        "name": str,            # clé/identifiant lisible
        "task": str,            # chemin de la tâche Celery (ex. 'ventes.x')
        "schedule": str,        # description humaine de la cadence
        "enabled": bool,        # actif ?
        "source": str,          # 'beat_schedule' | 'periodic_task'
        "last_run": str | None, # ISO 8601 si connu (DB uniquement)
    }
"""
from celery import current_app


def _describe_schedule(schedule):
    """Rend une cadence Celery (crontab / timedelta / nombre) lisible.

    Tolérant : ne lève jamais — un planning illisible renvoie ``str(schedule)``.
    """
    if schedule is None:
        return ''
    # crontab : possède minute/hour/day_of_week/… — on rend la forme cron.
    minute = getattr(schedule, '_orig_minute', None)
    hour = getattr(schedule, '_orig_hour', None)
    if minute is not None and hour is not None:
        dow = getattr(schedule, '_orig_day_of_week', '*')
        dom = getattr(schedule, '_orig_day_of_month', '*')
        mon = getattr(schedule, '_orig_month_of_year', '*')
        return f'{minute} {hour} {dom} {mon} {dow}'
    # timedelta / schedule(run_every=…)
    run_every = getattr(schedule, 'run_every', None)
    if run_every is not None:
        total = getattr(run_every, 'total_seconds', None)
        if callable(total):
            return f'toutes les {int(total())} s'
        return str(run_every)
    return str(schedule)


def _raw_beat_schedule():
    """Lecture brute de la planification statique Celery (seam testable).

    Isolé pour que les tests puissent injecter un ``beat_schedule`` sans patcher
    l'objet ``Settings`` de Celery (qui ne supporte pas un delattr propre).
    """
    return getattr(current_app.conf, 'beat_schedule', None)


def _from_beat_schedule():
    """Jobs issus de la planification statique ``conf.beat_schedule``.

    Garde-fous : un schedule absent/vide renvoie ``[]`` ; une entrée mal formée
    est ignorée plutôt que de tout faire échouer.
    """
    out = []
    schedule = _raw_beat_schedule() or {}
    if not isinstance(schedule, dict):
        return out
    for name, entry in schedule.items():
        if not isinstance(entry, dict):
            continue
        out.append({
            'name': str(name),
            'task': entry.get('task', ''),
            'schedule': _describe_schedule(entry.get('schedule')),
            'enabled': bool(entry.get('enabled', True)),
            'source': 'beat_schedule',
            'last_run': None,
        })
    return out


def _from_periodic_tasks():
    """Jobs issus de ``django_celery_beat`` SI l'app est installée.

    Dégrade en ``[]`` sans erreur quand l'app/la table n'existe pas (cas
    actuel : django-celery-beat n'est pas une dépendance du projet).
    """
    try:
        from django_celery_beat.models import PeriodicTask
    except Exception:  # noqa: BLE001 — app non installée : dégradation propre.
        return []
    out = []
    try:
        rows = list(PeriodicTask.objects.all())
    except Exception:  # noqa: BLE001 — table absente / non migrée.
        return []
    for pt in rows:
        last = getattr(pt, 'last_run_at', None)
        out.append({
            'name': pt.name,
            'task': pt.task,
            'schedule': str(getattr(pt, 'schedule', '') or ''),
            'enabled': bool(getattr(pt, 'enabled', True)),
            'source': 'periodic_task',
            'last_run': last.isoformat() if last else None,
        })
    return out


def list_jobs():
    """Liste normalisée de tous les jobs planifiés configurés.

    Fusionne la planification statique et (si présente) la planification DB.
    Retourne ``[]`` quand rien n'est configuré. Triée par nom pour un rendu
    stable.
    """
    jobs = _from_beat_schedule() + _from_periodic_tasks()
    jobs.sort(key=lambda j: j['name'])
    return jobs


def known_task_names():
    """Ensemble des chemins de tâches connus via la planification configurée.

    Sert de liste blanche pour l'exécution manuelle : on n'autorise que le
    déclenchement d'une tâche réellement planifiée.
    """
    return {j['task'] for j in list_jobs() if j['task']}


def run_job(task_name):
    """Déclenche manuellement une tâche planifiée par son chemin Celery.

    - Refuse une tâche inconnue (hors planification) → ``ValueError``.
    - N'explose JAMAIS si le broker est injoignable : l'exception
      d'envoi est capturée et remontée comme ``RuntimeError`` avec un message
      clair (la vue la traduit en 503, pas en 500).

    Retourne l'identifiant de tâche (str) en cas de succès.
    """
    if not task_name or task_name not in known_task_names():
        raise ValueError(f"Tâche inconnue ou non planifiée : {task_name!r}")
    try:
        result = current_app.send_task(task_name)
    except Exception as exc:  # noqa: BLE001 — broker down / erreur transport.
        raise RuntimeError(
            f"Impossible d'envoyer la tâche {task_name!r} : {exc}"
        ) from exc
    return str(getattr(result, 'id', '') or '')


# ── NTPLT29 — Soumission d'un job de fond avec suivi de progression ──────────


def submit(kind, task, *, company, user, **kwargs):
    """Crée un ``BackgroundJob`` (company/user FORCÉS server-side) et dispatche
    la tâche Celery ``task`` en lui passant le ``job_id``.

    * ``kind`` — type logique (ex. ``'export_xlsx'``, ``'import_dataimport'``) ;
    * ``task`` — la tâche Celery (objet ``@shared_task``) ou son nom (str) ;
    * ``company`` / ``user`` — imposés par l'appelant (jamais lus d'un body) ;
    * ``kwargs`` — arguments métier passés à la tâche.

    La tâche reçoit ``job_id=<pk>`` en kwarg et est responsable de mettre à jour
    l'avancement (``BackgroundJob.marquer_progression/termine/echec``). Renvoie
    l'instance ``BackgroundJob`` créée. Si le broker est injoignable, le job est
    marqué ``failed`` et l'exception est remontée (l'appelant décide).
    """
    from .models import BackgroundJob

    job = BackgroundJob.objects.create(company=company, user=user, kind=kind)
    payload = dict(kwargs)
    payload['job_id'] = job.pk
    payload['company_id'] = getattr(company, 'id', company)
    try:
        if isinstance(task, str):
            current_app.send_task(task, kwargs=payload)
        else:
            task.delay(**payload)
    except Exception as exc:  # noqa: BLE001 — broker down : job en échec propre
        job.marquer_echec(f'Envoi de la tâche impossible : {exc}')
        raise
    return job
