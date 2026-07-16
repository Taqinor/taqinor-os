"""NTPLT6 — Metering d'usage par tenant (logique testable, hors Celery).

Calcule et persiste un ``TenantUsageSnapshot`` par (société, jour) :
  * ``lignes_par_table`` — nombre de lignes des grosses tables company-scopées
    (comptage BORNÉ : plafonné à ``MAX_COUNT`` pour ne jamais scanner des
    dizaines de millions de lignes d'un coup) ;
  * ``octets_minio`` — total d'octets sous le préfixe société dans MinIO
    (best-effort, 0 si le stockage est indisponible) ;
  * ``nb_requetes_api`` — somme des ``ApiUsageRecord`` de la société ce jour ;
  * ``nb_taches_celery`` — 0 par défaut (non instrumenté ; le champ existe pour
    que N100 le remplisse sans migration quand l'instrumentation arrivera).

Idempotent : ré-exécuter le snapshot d'un jour met à jour la MÊME ligne
(``update_or_create`` sur la contrainte unique ``(company, jour)``).

``core`` reste FONDATION : aucun import d'app métier — la découverte des tables
passe par le registre Django (``core.rls.discover_company_scoped_tables``), les
comptages par SQL paramétré, l'usage API par le modèle ``core.ApiUsageRecord``.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db import connection
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

# Plafond de comptage par table : au-delà on renvoie MAX_COUNT (borné). Évite
# un COUNT(*) illimité sur une table de plusieurs millions de lignes chaque
# nuit — la mesure de facturation n'a pas besoin d'un compte exact au-delà.
MAX_COUNT = 1_000_000

# Grosses tables suivies EN PRIORITÉ (par nom de table) — intersectées avec le
# périmètre company-scopé réel pour ne jamais viser une table absente.
_TRACKED_TABLE_HINTS = (
    'authentication_customuser',
    'crm_lead', 'crm_client', 'ventes_devis', 'ventes_facture',
    'ventes_boncommande', 'stock_mouvementstock', 'stock_produit',
    'installations_installation', 'installations_intervention',
    'sav_ticket', 'core_apiusagerecord',
)


def count_for_company(table: str, company_column: str, company_id: int) -> int:
    """COUNT BORNÉ (≤ MAX_COUNT) des lignes d'une table pour une société."""
    sql = (
        f'SELECT COUNT(*) FROM (SELECT 1 FROM "{table}" '
        f'WHERE "{company_column}" = %s LIMIT {MAX_COUNT}) AS sub'
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [company_id])
        row = cursor.fetchone()
    return int(row[0]) if row else 0


def _tracked_entries():
    """Entrées (table, colonne) suivies = intersection des hints et du périmètre
    company-scopé réel découvert par ``core.rls``."""
    from . import rls
    by_table = {e.table: e for e in rls.discover_company_scoped_tables()}
    entries = []
    for hint in _TRACKED_TABLE_HINTS:
        e = by_table.get(hint)
        if e is not None:
            entries.append(e)
    return entries


def rows_per_table(company_id: int) -> dict:
    """{ 'app_label.Model' : nombre_de_lignes_borné } pour la société."""
    result = {}
    for entry in _tracked_entries():
        try:
            result[entry.label] = count_for_company(
                entry.table, entry.company_column, company_id)
        except Exception:  # noqa: BLE001 - une table absente/erreur ne casse rien
            logger.warning('metering: comptage échoué pour %s', entry.table)
    return result


def minio_bytes(company_id: int) -> int:
    """Total d'octets sous le préfixe société dans les buckets d'upload/PDF.

    Best-effort : 0 si MinIO est indisponible (jamais d'exception propagée).
    Le préfixe société est ``company/<id>/`` — convention d'écriture du repo ;
    on somme les tailles listées sous ce préfixe dans les deux buckets métier.
    """
    total = 0
    prefix = f'company/{company_id}/'
    buckets = [
        getattr(settings, 'MINIO_BUCKET_UPLOADS', 'erp-uploads'),
        getattr(settings, 'MINIO_BUCKET_PDF', 'erp-pdf'),
    ]
    try:
        from .backup import _minio_client
        client = _minio_client()
    except Exception:  # noqa: BLE001 - stockage indisponible → 0
        return 0
    for bucket in buckets:
        try:
            paginator = client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get('Contents', []) or []:
                    total += int(obj.get('Size', 0) or 0)
        except Exception:  # noqa: BLE001 - bucket absent/erreur → ignore
            continue
    return total


def api_requests(company_id: int, jour) -> int:
    """Somme des requêtes API (ApiUsageRecord) de la société ce jour-là."""
    from .models import ApiUsageRecord
    agg = ApiUsageRecord.objects.filter(
        company_id=company_id, jour=jour).aggregate(total=Sum('nb_requetes'))
    return int(agg['total'] or 0)


def snapshot_company(company_id: int, jour=None):
    """Crée/met à jour l'instantané d'usage d'UNE société pour ``jour``.

    Idempotent : ``update_or_create`` sur (company, jour). Renvoie l'instance.
    """
    from .models import TenantUsageSnapshot
    jour = jour or timezone.now().date()
    snapshot, _ = TenantUsageSnapshot.objects.update_or_create(
        company_id=company_id, jour=jour,
        defaults={
            'lignes_par_table': rows_per_table(company_id),
            'octets_minio': minio_bytes(company_id),
            'nb_requetes_api': api_requests(company_id, jour),
            'nb_taches_celery': 0,  # non instrumenté (N100 le remplira)
        },
    )
    return snapshot


def cout_par_tenant(periode=None):
    """NTPLT45 — rapport de coût par tenant croisant ``TenantUsageSnapshot``.

    ``periode`` : chaîne ``'AAAA-MM'`` (un mois) ou ``None`` (toute la période
    disponible). Renvoie une liste triée par requêtes décroissantes :

        [{'company_id', 'company_nom', 'requetes', 'db_time_ms', 'stockage_mo',
          'jobs', 'jours_mesures'}, ...]

    * ``requetes`` — somme des ``nb_requetes_api`` sur la période ;
    * ``db_time_ms`` — cumul du temps DB (NTPLT43 ; 0 tant que non instrumenté) ;
    * ``stockage_mo`` — DERNIÈRE mesure ``octets_minio`` connue (instantané, pas
      un cumul) convertie en Mo ;
    * ``jobs`` — somme des ``nb_taches_celery``.
    Base factuelle de la discussion prix/plan que N100 mènera plus tard.
    """
    from django.db.models import Max, Sum
    from .models import TenantUsageSnapshot

    qs = TenantUsageSnapshot.objects.all()
    if periode:
        try:
            year, month = (int(p) for p in str(periode).split('-')[:2])
            qs = qs.filter(jour__year=year, jour__month=month)
        except (TypeError, ValueError):
            pass

    agg = (qs.values('company_id')
             .annotate(requetes=Sum('nb_requetes_api'),
                       jobs=Sum('nb_taches_celery'),
                       stockage_octets=Max('octets_minio'),
                       jours=Max('jour'))
             .order_by('-requetes'))

    # Nombre de jours mesurés + libellé société (best-effort).
    from authentication.models import Company
    noms = dict(Company.objects.values_list('id', 'nom'))
    rows = []
    for item in agg:
        cid = item['company_id']
        jours_mesures = qs.filter(company_id=cid).count()
        rows.append({
            'company_id': cid,
            'company_nom': noms.get(cid, str(cid)),
            'requetes': int(item['requetes'] or 0),
            'db_time_ms': 0,  # NTPLT43 — non instrumenté (le champ arrivera)
            'stockage_mo': round((item['stockage_octets'] or 0) / (1024 * 1024),
                                 2),
            'jobs': int(item['jobs'] or 0),
            'jours_mesures': jours_mesures,
        })
    return rows


def snapshot_all(jour=None):
    """Crée/met à jour l'instantané de TOUTES les sociétés pour ``jour``.

    Renvoie la liste des ids de sociétés traitées. Une société qui échoue ne
    bloque pas les autres (best-effort, journalisé).
    """
    from authentication.models import Company
    jour = jour or timezone.now().date()
    done = []
    for company_id in Company.objects.values_list('id', flat=True):
        try:
            snapshot_company(company_id, jour=jour)
            done.append(company_id)
        except Exception:  # noqa: BLE001 - une société KO ne bloque pas le reste
            logger.exception('metering: snapshot KO pour société %s', company_id)
    return done
