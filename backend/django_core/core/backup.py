"""FG395 — Sauvegarde / restauration en libre-service (par société).

Couche de FONDATION : matérialise un BUNDLE des données d'une société (export)
et trace une RESTAURATION, SANS que ``core`` n'importe une app métier (contrat
import-linter ``core-foundation-is-a-base-layer``). Les données proviennent
EXCLUSIVEMENT du registre de datasets de l'explorateur (``core.data_explorer``),
dont chaque ``queryset_provider`` est DÉJÀ scopé par société : ``core`` agrège
sans rien connaître du métier.

Conception
----------

* ``construire_manifeste(company, user, datasets=None)`` — pour chaque dataset
  enregistré (ou la sous-liste demandée), compte les lignes scopées société et
  renvoie un manifeste ``{datasets: [{name, label, lignes}], total_lignes}``.
* ``executer_sauvegarde(run)`` — remplit le manifeste du ``BackupRun`` (export),
  passe ``statut`` à ``termine`` et horodate ``termine_le``. La matérialisation
  d'un artefact physique (fichier/objet de stockage) reste un no-op tant
  qu'aucune destination n'est branchée — l'opération réussit (manifeste produit)
  sans dépendance externe.
* ``executer_restauration(run)`` — une restauration RÉELLE écrasant des données
  vivantes exige une validation et un magasin d'artefacts provisionnés par le
  fondateur (AUTH/destructif). Tant que ces prérequis ne sont pas branchés, la
  restauration est tracée en ``non_configure`` (jamais d'écriture aveugle) — le
  contrat de fondation est préservé et l'opération est revertable.

Aucune importation d'app domaine ici : seulement ``core.data_explorer`` (registre
en mémoire) et l'ORM générique.
"""
from __future__ import annotations

import datetime
import logging
import re
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from psycopg2 import sql
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import api_view, permission_classes
from authentication.permissions import IsAuthenticatedInterne
from rest_framework.response import Response

from . import data_explorer
from .models import BackupRun

logger = logging.getLogger(__name__)

# YOPSB1 — bucket MinIO dédié aux dumps Postgres réels (distinct des exports
# manifeste FG395). Recopié depuis apps/ventes/utils/minio_client.py SANS
# l'importer : core reste une couche de fondation qui ne dépend d'aucune app
# domaine (contrat import-linter core-foundation-is-a-base-layer).
BACKUP_BUCKET = 'erp-backups'


def _minio_client():
    """Client boto3/S3 vers MinIO (recopié de ventes.utils.minio_client pour
    que core reste dépendance-libre vis-à-vis des apps domaine)."""
    import boto3
    return boto3.client(
        's3',
        endpoint_url=f'http://{settings.MINIO_ENDPOINT}',
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name='us-east-1',
    )


def _ensure_backup_bucket(client) -> None:
    """Crée le bucket ``erp-backups`` s'il n'existe pas (best-effort)."""
    try:
        client.head_bucket(Bucket=BACKUP_BUCKET)
    except Exception:
        try:
            client.create_bucket(Bucket=BACKUP_BUCKET)
            logger.info('Bucket MinIO créé: %s', BACKUP_BUCKET)
        except Exception as exc:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
            logger.warning('Impossible de créer le bucket %s: %s',
                           BACKUP_BUCKET, exc)


def _datasets_cibles(datasets):
    """Liste de noms de datasets à inclure (vide → tous les enregistrés)."""
    connus = {d['name']: d for d in data_explorer.list_datasets()}
    if not datasets:
        return list(connus.values())
    out = []
    for name in datasets:
        d = connus.get(name)
        if d is not None:
            out.append(d)
    return out


def construire_manifeste(company, user=None, datasets=None):
    """Construit le manifeste d'un bundle de sauvegarde pour ``company``.

    Compte les lignes scopées société par dataset (le ``queryset_provider`` du
    dataset garantit le scoping). Renvoie un dict JSON-sérialisable.
    """
    lignes_par_dataset = []
    total = 0
    for d in _datasets_cibles(datasets):
        name = d['name']
        try:
            ds = data_explorer.get_dataset(name)
            qs = ds['provider'](company, user)
            nb = qs.count()
        except Exception as exc:  # noqa: BLE001 — dataset défaillant n'arrête pas (D-ENF22-BLE001)
            logger.warning("construire manifeste : échec ignoré, comportement dégradé", exc_info=True)
            lignes_par_dataset.append(
                {'name': name, 'label': d['label'], 'erreur': str(exc)})
            continue
        total += nb
        lignes_par_dataset.append(
            {'name': name, 'label': d['label'], 'lignes': nb})
    return {
        'datasets': lignes_par_dataset,
        'total_lignes': total,
        'genere_le': timezone.now().isoformat(),
    }


def executer_sauvegarde(run: BackupRun):
    """Exécute une sauvegarde (export) : remplit le manifeste, marque terminé.

    Ne dépend d'aucun service externe : produit toujours un manifeste. La
    matérialisation d'un artefact physique reste optionnelle (no-op si aucune
    destination de stockage n'est configurée).
    """
    run.statut = BackupRun.STATUT_EN_COURS
    run.save(update_fields=['statut', 'updated_at'])
    manifeste = construire_manifeste(run.company, run.declenche_par,
                                     run.datasets)
    run.manifest = manifeste
    run.statut = BackupRun.STATUT_TERMINE
    run.termine_le = timezone.now()
    run.detail = {'message': 'Manifeste de sauvegarde produit.'}
    run.save(update_fields=['manifest', 'statut', 'termine_le', 'detail',
                            'updated_at'])
    return run


def executer_restauration(run: BackupRun):
    """Trace une restauration.

    Une restauration RÉELLE (écriture/écrasement de données vivantes) exige un
    magasin d'artefacts et une validation provisionnés par le fondateur
    (AUTH/destructif). Tant qu'ils ne sont pas branchés, l'opération est tracée
    en ``non_configure`` SANS écrire — jamais d'écriture aveugle.
    """
    if not run.artifact_ref:
        run.statut = BackupRun.STATUT_NON_CONFIGURE
        run.detail = {
            'message': "Aucun artefact source : restauration non configurée "
                       "(magasin d'artefacts à provisionner par le fondateur).",
        }
        run.save(update_fields=['statut', 'detail', 'updated_at'])
        return run
    # Avec un artefact branché mais sans pipeline de restauration validé, on
    # reste en no-op tracé : la fondation ne réalise aucune écriture métier.
    run.statut = BackupRun.STATUT_NON_CONFIGURE
    run.detail = {
        'message': 'Pipeline de restauration non branché (no-op tracé).',
        'artifact_ref': run.artifact_ref,
    }
    run.save(update_fields=['statut', 'detail', 'updated_at'])
    return run


# ---------------------------------------------------------------------------
# YOPSB1 — Sauvegarde Postgres réelle, planifiée et hors-serveur.
#
# ``dump_database`` lance un ``pg_dump`` (format custom -Fc) vers un fichier
# temporaire puis l'UPLOAD dans MinIO (bucket ``erp-backups``), et journalise
# le résultat en ``BackupRun`` (kind=db_dump, company=None — système-wide).
# Un ``pg_dump`` en échec (code retour != 0) marque le run ``echec`` et NE
# lève PAS d'exception : l'appelant (commande de gestion / tâche Celery)
# inspecte ``run.statut`` et sort en code non-nul le cas échéant.
# ---------------------------------------------------------------------------

def _pg_dump_env_args():
    """Renvoie (args pg_dump, env avec PGPASSWORD) depuis les variables DB_*
    déjà lues par ``settings/base.py`` — jamais un mot de passe en argv."""
    import os

    db = settings.DATABASES['default']
    args = [
        'pg_dump',
        '-Fc',
        '-h', db.get('HOST', 'db'),
        '-p', str(db.get('PORT', '5432')),
        '-U', db.get('USER', 'erp_user'),
        '-d', db.get('NAME', 'erp_db'),
    ]
    env = dict(os.environ)
    if db.get('PASSWORD'):
        env['PGPASSWORD'] = db['PASSWORD']
    return args, env


def dump_database(run: BackupRun) -> BackupRun:
    """YOPSB1 — exécute un ``pg_dump`` réel de toute l'instance et l'upload
    dans MinIO. ``run`` doit être ``kind=KIND_DB_DUMP`` (company=None).

    Échec ``pg_dump`` (code retour non nul ou exception) → ``statut=echec``,
    détail de l'erreur, AUCUNE levée d'exception (l'appelant décide du code
    process de sortie via ``run.statut``)."""
    run.statut = BackupRun.STATUT_EN_COURS
    run.save(update_fields=['statut', 'updated_at'])

    args, env = _pg_dump_env_args()
    horodatage = timezone.now().strftime('%Y%m%d-%H%M%S')
    object_key = f'pg_dumps/{horodatage}.dump'

    with tempfile.TemporaryDirectory() as tmpdir:
        dump_path = Path(tmpdir) / 'db.dump'
        try:
            with open(dump_path, 'wb') as fh:
                result = subprocess.run(
                    args, stdout=fh, stderr=subprocess.PIPE, env=env,
                    timeout=3600)
        except Exception as exc:  # noqa: BLE001 — pg_dump introuvable, timeout… (D-ENF22-BLE001)
            logger.warning("dump database : échec ignoré, comportement dégradé", exc_info=True)
            run.statut = BackupRun.STATUT_ECHEC
            run.detail = {'message': f'pg_dump: exception: {exc}'}
            run.save(update_fields=['statut', 'detail', 'updated_at'])
            return run

        if result.returncode != 0:
            run.statut = BackupRun.STATUT_ECHEC
            run.detail = {
                'message': 'pg_dump a échoué (code non nul).',
                'returncode': result.returncode,
                'stderr': (result.stderr or b'').decode(errors='replace')[:2000],
            }
            run.save(update_fields=['statut', 'detail', 'updated_at'])
            return run

        taille = dump_path.stat().st_size
        try:
            client = _minio_client()
            _ensure_backup_bucket(client)
            client.upload_file(str(dump_path), BACKUP_BUCKET, object_key)
        except Exception as exc:  # noqa: BLE001 — échec upload = échec du run (D-ENF22-BLE001)
            logger.warning("dump database : échec ignoré, comportement dégradé", exc_info=True)
            run.statut = BackupRun.STATUT_ECHEC
            run.detail = {'message': f"Échec de l'upload MinIO: {exc}"}
            run.save(update_fields=['statut', 'detail', 'updated_at'])
            return run

        # ADCG30 — les fichiers métier suivent le dump : un échec de copie
        # fait échouer le run (même règle que l'upload du dump).
        try:
            fichiers = sauvegarder_fichiers(client)
        except Exception as exc:  # noqa: BLE001 — échec copie = échec du run (D-ENF22-BLE001)
            logger.warning("dump database : échec de la copie des fichiers", exc_info=True)
            run.statut = BackupRun.STATUT_ECHEC
            run.detail = {'message': f'Échec de la copie des fichiers : {exc}'}
            run.save(update_fields=['statut', 'detail', 'updated_at'])
            return run

        # SCA13 — copie hors-boîte, best-effort, APRÈS le succès du backup
        # local (MinIO reste la source de vérité du statut du run). Le
        # fichier local (dump_path) existe encore ICI, dans le `with`
        # TemporaryDirectory — appelé avant sa suppression automatique.
        offsite_detail = _push_offsite(dump_path, object_key)

    run.object_key = object_key
    run.bytes_taille = taille
    run.artifact_ref = f'minio://{BACKUP_BUCKET}/{object_key}'
    run.statut = BackupRun.STATUT_TERMINE
    run.termine_le = timezone.now()
    message = 'pg_dump réussi et déposé dans MinIO.'
    if offsite_detail.get('status') == 'echec':
        # ADCG31 — le dump local reste restaurable (run termine), mais l'échec
        # de la copie distante se VOIT : message du run + logger.error.
        message += f" — copie hors serveur EN ÉCHEC : {offsite_detail.get('message', '')}"
        logger.error('dump database : copie hors serveur en échec (run %s) : %s',
                     run.pk, offsite_detail.get('message', ''))
    run.detail = {'message': message,
                  'bytes': taille, 'offsite': offsite_detail,
                  'fichiers': fichiers}
    run.save(update_fields=['object_key', 'bytes_taille', 'artifact_ref',
                            'statut', 'termine_le', 'detail', 'updated_at'])
    return run


def _lister_objets(client, bucket, prefix=''):
    """``{clé: (taille, etag)}`` de tous les objets (pagination par jeton)."""
    objets, kw = {}, {'Bucket': bucket, 'Prefix': prefix}
    while True:
        try:
            resp = client.list_objects_v2(**kw)
        except Exception as exc:  # bucket encore jamais créé = vide ; le reste remonte
            if getattr(exc, 'response', {}).get('Error', {}).get('Code') == 'NoSuchBucket':
                return objets
            raise
        for obj in resp.get('Contents', []):
            objets[obj['Key']] = (obj.get('Size'), obj.get('ETag'))
        if not resp.get('IsTruncated'):
            return objets
        kw['ContinuationToken'] = resp.get('NextContinuationToken')


def sauvegarder_fichiers(client):
    """ADCG30 — copie INCRÉMENTALE des buckets métier sous
    ``erp-backups/fichiers/<bucket>/<clé>`` (objet absent ou taille/ETag
    différent ⇒ copie ; jamais de suppression : un objet effacé à la source
    reste dans la copie), puis vers la cible hors-boîte si configurée
    (best-effort, comme le dump). Lève en nommant le bucket fautif."""
    cfg = _offsite_settings()
    resultat = {}
    for bucket in (settings.MINIO_BUCKET_UPLOADS, settings.MINIO_BUCKET_PDF):
        prefixe = f'fichiers/{bucket}/'
        try:
            source = _lister_objets(client, bucket)
            copie = _lister_objets(client, BACKUP_BUCKET, prefixe)
            for cle, meta in source.items():
                if copie.get(prefixe + cle) != meta:
                    client.copy_object(Bucket=BACKUP_BUCKET, Key=prefixe + cle,
                                       CopySource={'Bucket': bucket, 'Key': cle})
        except Exception as exc:
            raise RuntimeError(f'bucket {bucket} : {exc}') from exc
        resultat[bucket] = {'objets': len(source),
                            'octets': sum(t or 0 for t, _e in source.values())}
        if _offsite_configured(cfg):
            try:
                distant = _offsite_client(cfg)
                deja = _lister_objets(distant, cfg['bucket'], prefixe)
                for cle, (taille, _etag) in source.items():
                    if (deja.get(prefixe + cle) or (None,))[0] != taille:
                        corps = client.get_object(Bucket=bucket, Key=cle)['Body']
                        distant.upload_fileobj(corps, cfg['bucket'], prefixe + cle)
                resultat[bucket]['offsite'] = 'ok'
            except Exception as exc:  # noqa: BLE001 — best-effort comme le dump (D-ENF22-BLE001)
                logger.warning('ADCG30: copie hors-boîte %s en échec: %s', bucket, exc)
                resultat[bucket]['offsite'] = f'echec: {exc}'
    return resultat


# ---------------------------------------------------------------------------
# SCA13 — Copie de sauvegarde hors-boîte (key-gated OFF par défaut).
#
# ``restore_drill`` (YOPSB2, ci-dessus) prouve la restaurabilité d'un dump
# SUR LA MÊME instance Postgres/MinIO — un sinistre boîte entière (disque
# mort, corruption du volume Docker, incident datacenter) n'est pas couvert
# par une copie qui reste sur la même boîte. ``_push_offsite`` pousse le
# dump vers une cible S3-compatible EXTERNE si les 4 variables
# ``BACKUP_OFFSITE_*`` sont TOUTES posées — OFF par défaut (aucune des 4
# posée → no-op silencieux, zéro appel réseau supplémentaire, comportement
# byte-identique à avant SCA13). Réutilise le client boto3 déjà en
# dépendance (``requirements.txt`` — déjà utilisé par ``_minio_client()``) :
# AUCUNE nouvelle dépendance.
#
# Un échec de la copie offsite NE FAIT JAMAIS échouer le ``BackupRun``
# (``run.statut`` reste piloté par le backup local MinIO) — la couche
# offsite est une résilience additionnelle best-effort, jamais un nouveau
# point de défaillance pour le backup principal.
# ---------------------------------------------------------------------------

def _offsite_settings():
    """Configuration hors-boîte lue depuis l'environnement. Toutes les clés
    valent chaîne vide si non posées — ``_offsite_configured`` en dérive le
    statut ON/OFF."""
    import os

    return {
        'endpoint': os.environ.get('BACKUP_OFFSITE_ENDPOINT', ''),
        'bucket': os.environ.get('BACKUP_OFFSITE_BUCKET', ''),
        'access_key': os.environ.get('BACKUP_OFFSITE_ACCESS_KEY', ''),
        'secret_key': os.environ.get('BACKUP_OFFSITE_SECRET_KEY', ''),
        'retain_last': int(os.environ.get('BACKUP_OFFSITE_RETAIN_LAST', '7')),
    }


def _offsite_configured(cfg=None):
    """OFF par défaut : ON seulement si les 4 variables requises sont TOUTES
    posées (endpoint/bucket/clés) — jamais un sous-ensemble partiel actif."""
    cfg = cfg or _offsite_settings()
    return bool(cfg['endpoint'] and cfg['bucket']
                and cfg['access_key'] and cfg['secret_key'])


def _offsite_client(cfg):
    """Client boto3/S3 vers la cible hors-boîte (même bibliothèque que
    ``_minio_client`` — un second client, endpoint/clés différents)."""
    import boto3
    return boto3.client(
        's3',
        endpoint_url=cfg['endpoint'],
        aws_access_key_id=cfg['access_key'],
        aws_secret_access_key=cfg['secret_key'],
        region_name='us-east-1',
    )


def _push_offsite(dump_path: Path, object_key: str) -> dict:
    """Pousse ``dump_path`` vers la cible hors-boîte si configurée, puis
    applique une rétention simple (garde les N derniers objets sous
    ``pg_dumps/``). Renvoie un dict de détail (jamais lève — best-effort) :
    ``{'configured': bool, 'status': 'ok'|'echec'|'off', 'message': str}``."""
    cfg = _offsite_settings()
    if not _offsite_configured(cfg):
        return {'configured': False, 'status': 'off',
                'message': 'BACKUP_OFFSITE_* non configuré — hors-boîte désactivé.'}

    try:
        client = _offsite_client(cfg)
        client.upload_file(str(dump_path), cfg['bucket'], object_key)
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.warning('SCA13: échec upload hors-boîte %s: %s', object_key, exc)
        return {'configured': True, 'status': 'echec', 'message': str(exc)}

    purge_detail = _purge_offsite_retention(client, cfg)
    return {'configured': True, 'status': 'ok',
            'message': f"Copié vers {cfg['bucket']}/{object_key}.",
            'retention': purge_detail}


def _purge_offsite_retention(client, cfg) -> dict:
    """Rétention simple hors-boîte : garde les N derniers dumps
    (``pg_dumps/``), supprime le reste. Best-effort — une erreur de listing/
    suppression ne fait jamais échouer le push principal (déjà réussi à ce
    stade)."""
    try:
        resp = client.list_objects_v2(Bucket=cfg['bucket'], Prefix='pg_dumps/')
        objets = sorted(
            (obj['Key'] for obj in resp.get('Contents', [])), reverse=True)
        a_purger = objets[cfg['retain_last']:]
        for key in a_purger:
            client.delete_object(Bucket=cfg['bucket'], Key=key)
        return {'conserves': min(len(objets), cfg['retain_last']),
                'supprimes': len(a_purger)}
    except Exception as exc:  # noqa: BLE001 — best-effort (D-ENF22-BLE001)
        logger.warning('SCA13: échec rétention hors-boîte: %s', exc)
        return {'erreur': str(exc)}


# ---------------------------------------------------------------------------
# YOPSB2 — Drill de restauration testé + vérification d'intégrité des dumps.
#
# ``restore_drill`` télécharge le dernier dump réussi (YOPSB1), le restaure
# dans une base JETABLE (jamais la production — garde dure sur le nom), puis
# compare des comptages de tables clés au manifeste du dump. La base scratch
# est DROP à la fin (succès ou échec de la comparaison).
# ---------------------------------------------------------------------------

RESTORE_DRILL_TABLES = [
    'authentication_customuser',
    'ventes_devis',
    'crm_lead',
]

# NTPLT62 — tables (avec colonne company) sur lesquelles le drill vérifie les
# comptages PAR SOCIÉTÉ (top 5 par volume), pas seulement globaux. Prouve que la
# restauration ramène bien les données de CHAQUE gros tenant, pas juste un total
# global qui masquerait la perte d'une société entière.
RESTORE_DRILL_TENANT_TABLES = [
    ('ventes_devis', 'company_id'),
    ('crm_lead', 'company_id'),
]
RESTORE_DRILL_TOP_TENANTS = 5


def _top_tenants_live(limit=RESTORE_DRILL_TOP_TENANTS):
    """IDs des sociétés les plus volumineuses dans la base LIVE (best-effort).

    Somme des lignes des tables tenant ci-dessus, groupée par company_id. Renvoie
    ``{company_id: total_live}``. Best-effort : une table absente est ignorée."""
    from django.db import connection as _live
    totals: dict = {}
    if _live.vendor != 'postgresql':
        return totals
    with _live.cursor() as cur:
        for table, col in RESTORE_DRILL_TENANT_TABLES:
            try:
                cur.execute(sql.SQL(
                    'SELECT {col}, COUNT(*) FROM {table} '
                    'WHERE {col} IS NOT NULL GROUP BY {col}').format(
                        col=sql.Identifier(col),
                        table=sql.Identifier(table)))
                for company_id, n in cur.fetchall():
                    totals[company_id] = totals.get(company_id, 0) + n
            except Exception:  # noqa: BLE001 — table absente → ignorée (D-ENF22-BLE001)
                logger.warning("top tenants live : échec ignoré, comportement dégradé", exc_info=True)
                continue
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return dict(top)


def _comptages_live():
    """ADCG38 — comptages des tables clés dans la base LIVE (même requête
    que la base restaurée) ; ``{}`` hors Postgres."""
    from django.db import connection as _live
    if _live.vendor != 'postgresql':
        return {}
    with _live.cursor() as cur:
        return _compter_tables(cur)


def detecter_ecarts_tenant(top_live, restored):
    """Croise comptages live vs restaurés par société (NTPLT62).

    Renvoie ``(comptages_par_societe, ecarts)`` où ``comptages_par_societe`` est
    ``{company_id: {'live': n, 'restore': m}}`` et ``ecarts`` la liste des
    sociétés avec ``live > 0`` mais ``restore == 0`` (perte totale d'un tenant)."""
    comptages_par_societe = {}
    ecarts = []
    for company_id, live_n in top_live.items():
        restore_n = int(restored.get(company_id, 0) or 0)
        comptages_par_societe[str(company_id)] = {
            'live': int(live_n), 'restore': restore_n}
        if live_n > 0 and restore_n == 0:
            ecarts.append(company_id)
    return comptages_par_societe, ecarts


def _tenant_counts_in_restored(cur, company_ids):
    """Comptages par société DANS la base restaurée (cursor psycopg2 ouvert)."""
    counts: dict = {cid: 0 for cid in company_ids}
    if not company_ids:
        return counts
    for table, col in RESTORE_DRILL_TENANT_TABLES:
        try:
            cur.execute(sql.SQL(
                'SELECT {col}, COUNT(*) FROM {table} '
                'WHERE {col} = ANY(%s) GROUP BY {col}').format(
                    col=sql.Identifier(col), table=sql.Identifier(table)),
                (list(company_ids),))
            for company_id, n in cur.fetchall():
                counts[company_id] = counts.get(company_id, 0) + n
        except Exception:  # noqa: BLE001 — dégrade proprement (D-ENF22-BLE001)
            logger.warning("tenant counts in restored : échec ignoré, comportement dégradé", exc_info=True)
            continue
    return counts


class RestoreDrillGuardError(Exception):
    """Levée si la base cible du drill == la base de production (jamais)."""


def _restore_drill_db_name():
    """Nom de la base scratch du drill (configurable), avec garde dure
    empêchant qu'elle coïncide avec la base de production."""
    import os

    name = os.environ.get('BACKUP_RESTORE_DRILL_DB', 'erp_restore_drill')
    prod_name = settings.DATABASES['default']['NAME']
    if name == prod_name:
        raise RestoreDrillGuardError(
            "BACKUP_RESTORE_DRILL_DB coïncide avec la base de production "
            f"({prod_name!r}) — refus d'écrire dessus.")
    return name


def _psql_env_args_for(db_name):
    import os

    db = settings.DATABASES['default']
    env = dict(os.environ)
    if db.get('PASSWORD'):
        env['PGPASSWORD'] = db['PASSWORD']
    base = ['-h', db.get('HOST', 'db'), '-p', str(db.get('PORT', '5432')),
            '-U', db.get('USER', 'erp_user')]
    return base, env, db_name


def _dernier_dump_termine():
    return (BackupRun.objects
            .filter(kind=BackupRun.KIND_DB_DUMP,
                    statut=BackupRun.STATUT_TERMINE)
            .exclude(object_key='')
            .order_by('-termine_le', '-id')
            .first())


def _sortie(proc):
    return (proc.stderr or b'').decode(errors='replace')[:2000]


def _restaurer_dump(object_key, dump_path, base_args, env, cible, options=(),
                    recreer=True, avant_restore=None):
    """ADCG37 — séquence UNIQUE (exercice + restauration réelle) :
    téléchargement → (dropdb si ``recreer``) → createdb → ``avant_restore()``
    → ``pg_restore`` + ``options``. ``None`` si tout passe, sinon le ``detail``
    d'échec du run."""
    try:
        _minio_client().download_file(BACKUP_BUCKET, object_key, str(dump_path))
    except Exception as exc:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
        logger.warning('restauration : échec du téléchargement', exc_info=True)
        return {'message': f'Échec du téléchargement MinIO: {exc}'}
    if recreer:
        subprocess.run(['dropdb', *base_args, '--if-exists', cible],
                       env=env, stderr=subprocess.PIPE, timeout=120)
    create = subprocess.run(['createdb', *base_args, cible],
                            env=env, stderr=subprocess.PIPE, timeout=120)
    if create.returncode != 0:
        return {'message': f'createdb ({cible}) a échoué.', 'stderr': _sortie(create)}
    echec = avant_restore() if avant_restore else None
    if echec:
        return echec
    restore = subprocess.run(
        ['pg_restore', *base_args, '-d', cible, *options, str(dump_path)],
        env=env, stderr=subprocess.PIPE, timeout=3600)
    if restore.returncode != 0:
        return {'message': 'pg_restore a échoué.', 'stderr': _sortie(restore)}
    return None


def _connecter(db_name):
    import psycopg2
    db = settings.DATABASES['default']
    return psycopg2.connect(
        host=db.get('HOST', 'db'), port=db.get('PORT', '5432'),
        user=db.get('USER', 'erp_user'), password=db.get('PASSWORD', ''),
        dbname=db_name)


def _compter_tables(cur):
    comptages = {}
    for table in RESTORE_DRILL_TABLES:
        cur.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table)))
        comptages[table] = cur.fetchone()[0]
    return comptages


def restore_drill(run: BackupRun) -> BackupRun:
    """YOPSB2 — restaure le dernier dump réussi dans une base scratch,
    vérifie des comptages clés, puis DROP la base scratch. ``run`` doit être
    ``kind=KIND_RESTORE_DRILL`` (company=None, système-wide).

    Garde dure : refuse d'écrire si la base cible == la base de production
    (``RestoreDrillGuardError``, jamais un ``pg_restore`` aveugle)."""
    run.statut = BackupRun.STATUT_EN_COURS
    run.save(update_fields=['statut', 'updated_at'])

    try:
        drill_db = _restore_drill_db_name()
    except RestoreDrillGuardError as exc:
        run.statut = BackupRun.STATUT_ECHEC
        run.detail = {'message': str(exc)}
        run.save(update_fields=['statut', 'detail', 'updated_at'])
        return run

    source = _dernier_dump_termine()
    if source is None:
        run.statut = BackupRun.STATUT_ECHEC
        run.detail = {'message': 'Aucun BackupRun db_dump terminé disponible '
                                 'à restaurer.'}
        run.save(update_fields=['statut', 'detail', 'updated_at'])
        return run
    # ADCG39 — jamais un « succès » sur un vieux dump : au-delà de la rétention
    # quotidienne (ou sans date de fin), l'exercice échoue sans télécharger.
    age = (timezone.now() - source.termine_le).days if source.termine_le else None
    if age is None or age > _retention_settings()['daily']:
        run.statut = BackupRun.STATUT_ECHEC
        run.detail = {'message': f"Dump source trop ancien ({age if age is not None else '?'} jours)"}
        run.save(update_fields=['statut', 'detail', 'updated_at'])
        return run

    base_args, env, _ = _psql_env_args_for(drill_db)

    with tempfile.TemporaryDirectory() as tmpdir:
        dump_path = Path(tmpdir) / 'restore.dump'
        try:
            # 1-2) téléchargement, (re)création de la base scratch (DROP si
            #      résiduelle d'un drill interrompu) puis pg_restore — séquence
            #      partagée avec la restauration réelle (ADCG37).
            echec = _restaurer_dump(source.object_key, dump_path, base_args,
                                    env, drill_db,
                                    options=('--no-owner', '--no-privileges'))
            if echec:
                run.statut = BackupRun.STATUT_ECHEC
                run.detail = echec
                run.save(update_fields=['statut', 'detail', 'updated_at'])
                return run

            # 3) comptages de tables clés dans la base restaurée.
            comptages = {}
            try:
                conn = _connecter(drill_db)
                try:
                    with conn.cursor() as cur:
                        comptages = _compter_tables(cur)
                        live = _comptages_live()  # ADCG38
                        # NTPLT62 — comptages PAR SOCIÉTÉ (top 5 par volume).
                        top_live = _top_tenants_live()
                        restored = _tenant_counts_in_restored(
                            cur, list(top_live.keys()))
                finally:
                    conn.close()
            except Exception as exc:  # noqa: BLE001 — journalisé, dégradation propre (D-ENF22-BLE001)
                logger.warning("restore drill : échec ignoré, comportement dégradé", exc_info=True)
                run.statut = BackupRun.STATUT_ECHEC
                run.detail = {'message': f'Échec des comptages: {exc}'}
                run.save(update_fields=['statut', 'detail', 'updated_at'])
                return run

            # NTPLT62 — écart si un gros tenant live n'a AUCUNE ligne restaurée
            # (la restauration a perdu une société entière). Un restauré < live
            # est normal (le dump est plus ancien) ; restauré == 0 alors que
            # live > 0 est une ALERTE.
            comptages_par_societe, ecarts = detecter_ecarts_tenant(
                top_live, restored)
            # ADCG38 — table clé vide alors que peuplée en live, ou société
            # perdue ⇒ l'exercice ÉCHOUE (restauré < live reste normal).
            manques = [f'{t} 0 ligne (live {live[t]})' for t, n in comptages.items()
                       if n == 0 and live.get(t, 0) > 0]
            manques += [f'société {c} sans données restaurées' for c in ecarts]
            if manques:
                run.statut = BackupRun.STATUT_ECHEC
                run.detail = {'message': 'Base restaurée incomplète : ' + ' ; '.join(manques),
                              'comptages': comptages, 'comptages_par_societe': comptages_par_societe,
                              'ecarts_tenant': [str(c) for c in ecarts]}
                run.save(update_fields=['statut', 'detail', 'updated_at'])
                return run
        except BaseException as exc:
            # ADCG35 — interruption (limite de temps Celery, erreur imprévue) :
            # le run finit `echec`, jamais `en_cours` à vie, puis on relève.
            logger.warning('restore drill : exercice interrompu', exc_info=True)
            run.statut = BackupRun.STATUT_ECHEC
            run.detail = {'message': 'Exercice de restauration interrompu : '
                                     f'{type(exc).__name__}'}
            run.save(update_fields=['statut', 'detail', 'updated_at'])
            raise
        finally:
            # Toujours DROP la base scratch, succès ou échec (jamais laisser
            # traîner une base jetable en dehors du drill).
            subprocess.run(
                ['dropdb', *base_args, '--if-exists', drill_db],
                env=env, stderr=subprocess.PIPE, timeout=120)

    run.statut = BackupRun.STATUT_TERMINE
    run.termine_le = timezone.now()
    run.detail = {
        'message': 'Drill de restauration réussi.',
        'source_run_id': source.pk,
        'source_object_key': source.object_key,
        'comptages': comptages,
        # NTPLT62 — comptages par société (top 5) + écarts (perte de tenant).
        'comptages_par_societe': comptages_par_societe,
        'ecarts_tenant': [str(c) for c in ecarts],
    }
    run.save(update_fields=['statut', 'termine_le', 'detail', 'updated_at'])
    return run


# ---------------------------------------------------------------------------
# ADCG37 — Restauration RÉELLE (commande ``restaurer_sauvegarde``) : même
# séquence que l'exercice, mais AVEC propriétaires et droits, rôles rejoués
# (``backend/db/rls_roles.sql``), fichiers remis, base CONSERVÉE.
# ---------------------------------------------------------------------------

_NOM_BASE_SUR = re.compile(r'^[a-z_][a-z0-9_]{0,62}$')


def verifier_cible_restauration(cible, remplacer_production=None):
    """Nom de base sûr ; la base de production seulement si
    ``remplacer_production`` la NOMME (garde du patron RestoreDrillGuardError)."""
    if not _NOM_BASE_SUR.match(cible or ''):
        raise RestoreDrillGuardError(f'Nom de base cible invalide : {cible!r}.')
    prod = settings.DATABASES['default']['NAME']
    if cible == prod and remplacer_production != prod:
        raise RestoreDrillGuardError(
            f'La base cible est la base de production ({prod!r}) : relancer avec '
            f'--remplacer-production {prod} pour confirmer.')


def _appliquer_roles(base_args, env, cible, roles_sql):
    """Rejoue rls_roles.sql (app_rls + sql_agent_ro, idempotent) sur ``cible``."""
    try:
        texte = Path(roles_sql).read_text(encoding='utf-8')
    except OSError as exc:
        return {'message': f'Script des rôles illisible ({roles_sql}) : {exc}'}
    owner = settings.DATABASES['default'].get('USER', 'erp_user').replace('"', '""')
    texte = texte.replace('DATABASE erp_db', f'DATABASE "{cible}"').replace('erp_user', f'"{owner}"')
    proc = subprocess.run(
        ['psql', *base_args, '-d', cible, '-q', '-v', 'ON_ERROR_STOP=1', '-f', '-'],
        input=texte.encode('utf-8'), env=env, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=300)
    if proc.returncode != 0:
        return {'message': 'Application des rôles (rls_roles.sql) a échoué.', 'stderr': _sortie(proc)}
    return None


def _restaurer_fichiers(client, suffixe):
    """Recopie ``erp-backups/fichiers/<bucket>/`` (ADCG30) vers ``<bucket><suffixe>``."""
    resultat = {}
    for bucket in (settings.MINIO_BUCKET_UPLOADS, settings.MINIO_BUCKET_PDF):
        prefixe, cible = f'fichiers/{bucket}/', f'{bucket}{suffixe}'
        try:
            client.head_bucket(Bucket=cible)
        except Exception:  # noqa: BLE001 — bucket absent : on le crée (D-ENF22-BLE001)
            logger.info('restauration : création du bucket %s', cible)
            client.create_bucket(Bucket=cible)
        objets = _lister_objets(client, BACKUP_BUCKET, prefixe)
        for cle in objets:
            client.copy_object(Bucket=cible, Key=cle[len(prefixe):],
                               CopySource={'Bucket': BACKUP_BUCKET, 'Key': cle})
        resultat[cible] = {'objets': len(objets)}
    return resultat


def restaurer_sauvegarde(run, object_key, cible, suffixe_buckets, roles_sql,
                         remplacer_production=None):
    """Restaure ``object_key`` dans la base NEUVE ``cible`` (jamais supprimée,
    ni avant ni après), rôles avant et après ``pg_restore``, puis fichiers."""
    verifier_cible_restauration(cible, remplacer_production)
    run.statut = BackupRun.STATUT_EN_COURS
    run.save(update_fields=['statut', 'updated_at'])
    base_args, env, _ = _psql_env_args_for(cible)
    comptages = fichiers = None
    with tempfile.TemporaryDirectory() as tmpdir:
        echec = _restaurer_dump(
            object_key, Path(tmpdir) / 'restore.dump', base_args, env, cible,
            recreer=False,
            avant_restore=lambda: _appliquer_roles(base_args, env, cible, roles_sql))
    echec = echec or _appliquer_roles(base_args, env, cible, roles_sql)
    if not echec:
        try:
            fichiers = _restaurer_fichiers(_minio_client(), suffixe_buckets)
            conn = _connecter(cible)
            try:
                with conn.cursor() as cur:
                    comptages = _compter_tables(cur)
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001 — journalisé, échec du run (D-ENF22-BLE001)
            logger.warning('restauration : échec après pg_restore', exc_info=True)
            echec = {'message': f'Échec après pg_restore : {exc}'}
    if echec:
        run.statut, run.detail = BackupRun.STATUT_ECHEC, echec
        run.save(update_fields=['statut', 'detail', 'updated_at'])
        return run
    run.statut, run.termine_le = BackupRun.STATUT_TERMINE, timezone.now()
    run.detail = {'message': 'Restauration réussie.', 'base': cible,
                  'source_object_key': object_key, 'comptages': comptages,
                  'fichiers': fichiers}
    run.save(update_fields=['statut', 'termine_le', 'detail', 'updated_at'])
    return run


# ---------------------------------------------------------------------------
# YOPSB3 — Rétention + purge automatique des sauvegardes (7j/4sem/12mois).
#
# ``purger_backups`` applique un schéma Grandfather-Father-Son configurable
# par variables d'environnement (défauts codés) sur les ``BackupRun``
# ``kind=db_dump`` ``statut=termine`` non encore purgés : garde le dernier
# dump de chaque jour sur N jours, de chaque semaine sur W semaines, de
# chaque mois sur M mois ; le reste est supprimé (objet MinIO + soft-delete
# du BackupRun). DRY-RUN par défaut (``apply_=False``) : rien n'est supprimé
# tant que l'appelant ne passe pas explicitement ``apply_=True`` (la tâche
# Celery lit ``settings.BACKUP_PURGE_AUTO_APPLY``, comme GED25).
# ---------------------------------------------------------------------------

def _retention_settings():
    import os

    return {
        'daily': int(os.environ.get('BACKUP_RETENTION_DAILY', '7')),
        'weekly': int(os.environ.get('BACKUP_RETENTION_WEEKLY', '4')),
        'monthly': int(os.environ.get('BACKUP_RETENTION_MONTHLY', '12')),
    }


def _a_conserver(runs, now):
    """Détermine l'ensemble des ``BackupRun`` à CONSERVER selon le schéma GFS.

    ``runs`` : itérable de BackupRun triés ou non, avec ``termine_le`` posé.
    Renvoie un ``set`` de PK à garder."""
    cfg = _retention_settings()
    conserver = set()

    # Regroupe par clé (jour / semaine ISO / mois), garde le PLUS RÉCENT de
    # chaque groupe dans la fenêtre de rétention correspondante.
    def _garder_dernier_par_groupe(candidats, key_fn, fenetre_debut):
        groupes = {}
        for r in candidats:
            if r.termine_le is None or r.termine_le < fenetre_debut:
                continue
            key = key_fn(r.termine_le)
            actuel = groupes.get(key)
            if actuel is None or r.termine_le > actuel.termine_le:
                groupes[key] = r
        conserver.update(r.pk for r in groupes.values())

    runs = list(runs)
    _garder_dernier_par_groupe(
        runs, lambda dt: dt.date(),
        now - datetime.timedelta(days=cfg['daily']))
    _garder_dernier_par_groupe(
        runs, lambda dt: (dt.isocalendar()[0], dt.isocalendar()[1]),
        now - datetime.timedelta(weeks=cfg['weekly']))
    _garder_dernier_par_groupe(
        runs, lambda dt: (dt.year, dt.month),
        now - datetime.timedelta(days=31 * cfg['monthly']))
    return conserver


def purger_backups(now=None, apply_=False):
    """YOPSB3 — purge GFS des dumps db_dump terminés hors schéma de
    rétention. ``apply_=False`` (défaut) : DRY-RUN, ne supprime rien, ne fait
    que renvoyer le compte prévisionnel. ``apply_=True`` : supprime l'objet
    MinIO + soft-delete le ``BackupRun`` pour chaque run hors schéma.

    Renvoie ``{conserves, supprimes, dry_run}``."""
    now = now or timezone.now()
    qs = (BackupRun.objects
          .filter(kind=BackupRun.KIND_DB_DUMP,
                  statut=BackupRun.STATUT_TERMINE,
                  purge_is_deleted=False)
          .exclude(termine_le__isnull=True))
    runs = list(qs)
    conserver_pks = _a_conserver(runs, now)
    a_purger = [r for r in runs if r.pk not in conserver_pks]

    if not apply_:
        return {
            'conserves': len(conserver_pks),
            'supprimes': len(a_purger),
            'dry_run': True,
        }

    client = None
    for r in a_purger:
        if r.object_key:
            try:
                client = client or _minio_client()
                client.delete_object(Bucket=BACKUP_BUCKET, Key=r.object_key)
            except Exception as exc:  # noqa: BLE001 — échec objet n'arrête pas (D-ENF22-BLE001)
                logger.warning(
                    'purger_backups: échec suppression objet MinIO %s: %s',
                    r.object_key, exc)
                continue
        r.purge_is_deleted = True
        r.purge_deleted_at = now
        r.save(update_fields=['purge_is_deleted', 'purge_deleted_at',
                              'updated_at'])

    return {
        'conserves': len(conserver_pks),
        'supprimes': len(a_purger),
        'dry_run': False,
    }


# ---------------------------------------------------------------------------
# NTOBS5 — Écran self-service « Sauvegardes » pour l'admin tenant.
#
# LECTURE SEULE des ``BackupRun`` déjà produits par YOPSB1/2 — jamais un
# nouveau moteur. Pour les runs SYSTÈME-WIDE (``company=None`` — dump complet
# + drill), on n'expose QUE date + statut (jamais l'artefact/manifeste
# interne) ; pour les exports propres à la société, l'accès est déjà scopé
# par construction (filtre ``company=company``).
# ---------------------------------------------------------------------------

def _rpo_planifie_label():
    """RPO affiché = dérivé de la VRAIE planification beat de
    ``core.dump_database`` (jamais une valeur écrite en dur qui pourrait
    diverger du planning réel). ``None`` si la lecture échoue — jamais un
    texte inventé en repli."""
    try:
        from erp_agentique.celery import app as celery_app
        entry = celery_app.conf.beat_schedule.get('core-dump-database')
        if not entry:
            return None
        schedule = entry['schedule']
        heure = sorted(schedule.hour)[0] if schedule.hour else 0
        minute = sorted(schedule.minute)[0] if schedule.minute else 0
        return f'quotidien, {heure:02d}:{minute:02d}'
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.warning("rpo planifie label : échec ignoré, comportement dégradé", exc_info=True)
        return None


def _run_resume(run):
    if run is None:
        return None
    return {
        'date': (run.termine_le or run.created_at).isoformat(),
        'statut': run.statut,
    }


def _plus_recent():
    # ADCG41 — le plus RÉCENT, réussi ou non : un échec sans `termine_le`
    # (NULL en tête d'un tri décroissant) ne masque plus les succès suivants.
    from django.db.models.functions import Coalesce
    return (Coalesce('termine_le', 'created_at').desc(), '-id')


def _derniere_sauvegarde_run():
    # ADCG34 — seul un dump réel compte : un export FG395 n'est qu'un
    # manifeste de comptages (aucun artefact restaurable).
    return (BackupRun.objects
            .filter(kind=BackupRun.KIND_DB_DUMP, company__isnull=True,
                    statut=BackupRun.STATUT_TERMINE, purge_is_deleted=False)
            .order_by(*_plus_recent())
            .first())


def copie_distante(run):
    """ADCG31 — état de la copie hors serveur du dernier dump :
    ``{etat: off|ok|echec, date[, message]}`` ou ``None`` (aucun dump)."""
    off = ((run.detail or {}).get('offsite') or {}) if run is not None else {}
    if off.get('status') not in ('off', 'ok', 'echec'):
        return None
    etat = {'etat': off['status'], 'date': _run_resume(run)['date']}
    if off['status'] == 'echec':
        etat['message'] = off.get('message', '')
    return etat


def resume_sauvegardes(company):
    """NTOBS5 — résumé self-service pour l'admin tenant.

    Renvoie ``{derniere_sauvegarde, dernier_drill, rpo_planifie,
    rto_annonce_heures}`` — chaque champ ``None`` quand la donnée n'existe
    pas encore (jamais un défaut forfaitaire affiché comme réel)."""
    derniere_sauvegarde = _derniere_sauvegarde_run()
    dernier_drill = (
        BackupRun.objects
        .filter(kind=BackupRun.KIND_RESTORE_DRILL, company__isnull=True)
        .order_by(*_plus_recent())
        .first()
    )

    rto_annonce_heures = None
    try:
        from django.apps import apps as django_apps
        # ENF20 : profil résolu par libellé, aucune arête statique core -> apps.
        CompanyProfile = django_apps.get_model('parametres', 'CompanyProfile')
        profile = CompanyProfile.objects.filter(company=company).first()
        if profile is not None:
            rto_annonce_heures = profile.rto_annonce_heures
    except Exception:  # noqa: BLE001 — best-effort (D-ENF22-BLE001)
        logger.warning("resume sauvegardes : échec ignoré, comportement dégradé", exc_info=True)

    return {
        'derniere_sauvegarde': _run_resume(derniere_sauvegarde),
        'dernier_drill': _run_resume(dernier_drill),
        'rpo_planifie': _rpo_planifie_label(),
        'rto_annonce_heures': rto_annonce_heures,
    }


_RUN_RESUME_SHAPE = inline_serializer('BackupRunResume', {
    'date': drf_serializers.DateTimeField(),
    'statut': drf_serializers.CharField(),
}, allow_null=True)


@extend_schema(responses=inline_serializer('MesSauvegardesReponse', {
    'derniere_sauvegarde': _RUN_RESUME_SHAPE,
    'dernier_drill': _RUN_RESUME_SHAPE,
    'rpo_planifie': drf_serializers.CharField(allow_null=True),
    'rto_annonce_heures': drf_serializers.IntegerField(allow_null=True),
    # ADCG31 — écran interne seulement (l'API publique de fiabilité garde ses 4 clés).
    'copie_distante': drf_serializers.DictField(allow_null=True),
}))
@api_view(['GET'])
@permission_classes([IsAuthenticatedInterne])
def mes_sauvegardes_view(request):
    """GET /api/django/core/mes-sauvegardes/ — scopé société de l'appelant."""
    donnees = resume_sauvegardes(request.user.company)
    donnees['copie_distante'] = copie_distante(_derniere_sauvegarde_run())
    return Response(donnees)
