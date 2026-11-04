# flake8: noqa  (sonde de contre-visite vérifie APRF, rejouable par scripts/sonde.py — AMET93)
"""APRF34 : un export de mouvements au-delà du seuil part en tâche de fond ; le livrable doit rester
TÉLÉCHARGEABLE par l'utilisateur. On joue la tâche réelle `export_mouvements_xlsx_task` (le dépôt MinIO
seul est remplacé : HTTP sortant bloqué par le lanceur), puis on lit ce que l'utilisateur reçoit :
la notification « export prêt » et `GET /api/django/core/jobs-status/<id>/`."""
SONDE = {"constat": "C-APRF-VER-001", "sha": "e62ca97aa",
         "attendu": "lien de la notification sur l'hôte MinIO interne et aucune URL servie par Django au statut du job"}


def sonde(ctx):
    from unittest import mock
    from urllib.parse import urlparse
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from core.jobs import submit
    from core.models import BackgroundJob
    from apps.notifications.models import Notification
    from apps.stock import tasks as stock_tasks
    from apps.stock.services import MOUVEMENTS_EXPORT_JOB_KIND
    co = Company.objects.create(nom='Sonde APRF VER-001', slug='sonde-aprf-ver-001')
    u = get_user_model().objects.create_user(username='sonde-aprf-ver-001', password='x', company=co,
                                             role_legacy='admin')
    job = submit(MOUVEMENTS_EXPORT_JOB_KIND, stock_tasks.export_mouvements_xlsx_task,
                 company=co, user=u, mouvement_ids=[])
    with mock.patch('apps.records.storage.store_export_result',
                    return_value=f'exports/{co.pk}/{job.pk}.xlsx'):
        stock_tasks.export_mouvements_xlsx_task(job_id=job.pk, company_id=co.pk, mouvement_ids=[])
    job.refresh_from_db()
    notif = Notification.objects.filter(company=co).order_by('-id').first()
    texte = ' '.join(str(getattr(notif, f, '') or '') for f in ('link', 'message', 'corps', 'body')) if notif else ''
    import re
    urls = re.findall(r'https?://[^\s\'"]+', texte)
    hotes = sorted({urlparse(x).netloc for x in urls})
    api = APIClient()
    api.force_authenticate(u)
    r = api.get(f'/api/django/core/jobs-status/{job.pk}/', HTTP_HOST='localhost')
    corps = r.json() if r.status_code == 200 else {}
    url_django = [k for k, v in corps.items() if isinstance(v, str) and v.startswith('/api/')]
    minio = str(settings.MINIO_ENDPOINT)
    print(f'job={job.statut} cle={job.result_file_key!r} notif={bool(notif)} hotes_lien={hotes} '
          f'MINIO_ENDPOINT={minio} jobs-status={r.status_code} cles={sorted(corps)} url_django={url_django}')
    repro = bool(hotes) and all(h == minio for h in hotes) and not url_django
    return {'repro': repro, 'hotes': hotes, 'minio': minio, 'cles_statut': sorted(corps)}
