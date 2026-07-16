"""T12 — endpoint export comptable (journal des ventes + résumé TVA).

SCA41 — au-delà d'un seuil (défaut 2 000 factures de la période, surchargeable
par ``VENTES_EXPORT_ASYNC_ROW_THRESHOLD``), les exports XLSX partent en tâche
Celery (queue `interactive`) au lieu d'occuper un slot gunicorn pendant toute
leur construction. Sous le seuil, le chemin synchrone reste STRICTEMENT
inchangé (mêmes octets, UI inchangée). Le CSV reste toujours synchrone.
"""
import uuid

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from .exports import (
    export_journal_ventes, period_bounds,
    export_comptable_xlsx, export_comptable_csv,
    export_grand_livre_xlsx, export_grand_livre_csv,
    export_async_row_threshold, count_export_rows,
)


def _maybe_async_export(request, layout, debut, fin):
    """SCA41 — bascule sur la voie asynchrone si le nombre de factures de la
    période atteint le seuil. Renvoie une ``Response`` 202 (job accepté) quand
    l'export part en Celery, ou ``None`` pour laisser l'appelant faire l'export
    synchrone habituel (octets inchangés)."""
    from django.core.cache import cache
    from .tasks import (
        task_build_async_export, export_job_cache_key, EXPORT_JOB_CACHE_TTL,
    )

    company = request.user.company
    n_rows = count_export_rows(company, debut, fin)
    if n_rows < export_async_row_threshold():
        return None

    token = uuid.uuid4().hex
    # État initial en cache AVANT dispatch, scopé société — le endpoint de
    # statut vérifie cette société avant tout accès (jamais inter-tenant).
    cache.set(export_job_cache_key(token), {
        'company_id': company.id,
        'layout': layout,
        'status': 'pending',
    }, EXPORT_JOB_CACHE_TTL)
    task_build_async_export.apply_async(
        args=[company.id, layout, debut.isoformat(), fin.isoformat(), token],
        queue='interactive',
    )
    status_path = f'/api/django/ventes/export/status/{token}/'
    return Response(
        {
            'detail': ('Export volumineux — génération en arrière-plan.'),
            'job_id': token,
            'status': 'pending',
            'rows': n_rows,
            'status_url': status_path,
        },
        status=202,
    )


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def journal_ventes(request):
    """GET ?month=YYYY-MM | ?quarter=YYYY-Q | ?start=&end= → .xlsx
    (journal des ventes + résumé TVA), borné à la société."""
    user = request.user
    if not user.company_id and not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)
    try:
        debut, fin = period_bounds(request.query_params)
    except (ValueError, TypeError):
        return Response({'detail': 'Période invalide.'}, status=400)
    async_resp = _maybe_async_export(request, 'journal', debut, fin)
    if async_resp is not None:
        return async_resp
    return export_journal_ventes(user.company, debut, fin)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def export_comptable(request):
    """GET ?start=&end= (ou ?month=/?quarter=) &fmt=xlsx|csv &layout=… → export
    comptable des factures VALIDÉES de la plage. Groundwork DGI — lecture seule,
    borné société, aucune transmission.

    `layout` (FG49) :
      • ``ligne`` (défaut) — une ligne par ligne de facture, ventilation TVA par
        ligne + ICE client + totaux ;
      • ``grand-livre`` — grand-livre codé par compte CGNC (3421 clients / 7111
        ventes / 4455 TVA collectée), écritures débit/crédit équilibrées prêtes
        pour import direct chez le fiduciaire (mise en page type PCG/Sage).

    `fmt` par défaut = xlsx (sinon csv). (NB : on n'utilise pas ``format``,
    réservé par DRF pour la négociation de contenu.)"""
    user = request.user
    if not user.company_id and not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)
    try:
        debut, fin = period_bounds(request.query_params)
    except (ValueError, TypeError):
        return Response({'detail': 'Période invalide.'}, status=400)
    fmt = (request.query_params.get('fmt') or 'xlsx').lower()
    layout = (request.query_params.get('layout') or 'ligne').lower()
    if layout in ('grand-livre', 'grand_livre', 'gl', 'compte'):
        if fmt == 'csv':
            return export_grand_livre_csv(user.company, debut, fin)
        async_resp = _maybe_async_export(request, 'grand-livre', debut, fin)
        if async_resp is not None:
            return async_resp
        return export_grand_livre_xlsx(user.company, debut, fin)
    if fmt == 'csv':
        return export_comptable_csv(user.company, debut, fin)
    async_resp = _maybe_async_export(request, 'comptable', debut, fin)
    if async_resp is not None:
        return async_resp
    return export_comptable_xlsx(user.company, debut, fin)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def export_status(request, token):
    """SCA41 — statut d'un export asynchrone + URL de téléchargement pré-signée.

    Strictement borné société : un job appartenant à une AUTRE société renvoie
    404 (jamais 403 informatif — on ne révèle pas l'existence du job). Quand le
    job est prêt, renvoie une URL MinIO pré-signée (lecture seule, expiration
    courte) vers le fichier — jamais d'accès public direct au bucket."""
    from django.core.cache import cache
    from .tasks import export_job_cache_key
    from .utils.minio_client import get_minio_client
    from django.conf import settings

    user = request.user
    if not user.company_id and not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)

    job = cache.get(export_job_cache_key(token))
    # Job inconnu OU appartenant à une autre société → 404 indistinct.
    if not job or job.get('company_id') != user.company_id:
        return Response({'detail': 'Export introuvable.'}, status=404)

    status_val = job.get('status')
    if status_val == 'ready':
        client = get_minio_client()
        url = client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.MINIO_BUCKET_PDF, 'Key': job['key']},
            ExpiresIn=3600,
        )
        return Response({
            'status': 'ready',
            'download_url': url,
            'filename': job.get('filename'),
        })
    if status_val == 'error':
        return Response({'status': 'error',
                         'detail': 'La génération a échoué.'}, status=500)
    return Response({'status': 'pending'}, status=202)
