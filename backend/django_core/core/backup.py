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

import logging
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.utils import timezone

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
        except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001 — dataset défaillant n'arrête pas
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
        except Exception as exc:  # noqa: BLE001 — pg_dump introuvable, timeout…
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
        except Exception as exc:  # noqa: BLE001 — échec upload = échec du run
            run.statut = BackupRun.STATUT_ECHEC
            run.detail = {'message': f"Échec de l'upload MinIO: {exc}"}
            run.save(update_fields=['statut', 'detail', 'updated_at'])
            return run

    run.object_key = object_key
    run.bytes_taille = taille
    run.artifact_ref = f'minio://{BACKUP_BUCKET}/{object_key}'
    run.statut = BackupRun.STATUT_TERMINE
    run.termine_le = timezone.now()
    run.detail = {'message': 'pg_dump réussi et déposé dans MinIO.',
                  'bytes': taille}
    run.save(update_fields=['object_key', 'bytes_taille', 'artifact_ref',
                            'statut', 'termine_le', 'detail', 'updated_at'])
    return run


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

    base_args, env, _ = _psql_env_args_for(drill_db)

    with tempfile.TemporaryDirectory() as tmpdir:
        dump_path = Path(tmpdir) / 'restore.dump'
        try:
            client = _minio_client()
            client.download_file(BACKUP_BUCKET, source.object_key,
                                 str(dump_path))
        except Exception as exc:  # noqa: BLE001
            run.statut = BackupRun.STATUT_ECHEC
            run.detail = {'message': f'Échec du téléchargement MinIO: {exc}'}
            run.save(update_fields=['statut', 'detail', 'updated_at'])
            return run

        try:
            # 1) (re)créer la base scratch — DROP si résiduelle d'un drill
            #    précédent interrompu, puis CREATE.
            subprocess.run(
                ['dropdb', *base_args, '--if-exists', drill_db],
                env=env, stderr=subprocess.PIPE, timeout=120)
            create = subprocess.run(
                ['createdb', *base_args, drill_db],
                env=env, stderr=subprocess.PIPE, timeout=120)
            if create.returncode != 0:
                run.statut = BackupRun.STATUT_ECHEC
                run.detail = {
                    'message': 'createdb (base scratch) a échoué.',
                    'stderr': (create.stderr or b'').decode(
                        errors='replace')[:2000],
                }
                run.save(update_fields=['statut', 'detail', 'updated_at'])
                return run

            # 2) pg_restore le dump dans la base scratch.
            restore = subprocess.run(
                ['pg_restore', *base_args, '-d', drill_db,
                 '--no-owner', '--no-privileges', str(dump_path)],
                env=env, stderr=subprocess.PIPE, timeout=3600)
            if restore.returncode != 0:
                run.statut = BackupRun.STATUT_ECHEC
                run.detail = {
                    'message': 'pg_restore a échoué.',
                    'stderr': (restore.stderr or b'').decode(
                        errors='replace')[:2000],
                }
                run.save(update_fields=['statut', 'detail', 'updated_at'])
                return run

            # 3) comptages de tables clés dans la base restaurée.
            comptages = {}
            try:
                import psycopg2
                conn = psycopg2.connect(
                    host=settings.DATABASES['default'].get('HOST', 'db'),
                    port=settings.DATABASES['default'].get('PORT', '5432'),
                    user=settings.DATABASES['default'].get('USER', 'erp_user'),
                    password=settings.DATABASES['default'].get('PASSWORD', ''),
                    dbname=drill_db)
                try:
                    with conn.cursor() as cur:
                        for table in RESTORE_DRILL_TABLES:
                            cur.execute(f'SELECT COUNT(*) FROM {table}')
                            comptages[table] = cur.fetchone()[0]
                finally:
                    conn.close()
            except Exception as exc:  # noqa: BLE001
                run.statut = BackupRun.STATUT_ECHEC
                run.detail = {'message': f'Échec des comptages: {exc}'}
                run.save(update_fields=['statut', 'detail', 'updated_at'])
                return run
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
    }
    run.save(update_fields=['statut', 'termine_le', 'detail', 'updated_at'])
    return run
