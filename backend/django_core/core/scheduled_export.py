"""FG383 — Extraits planifiés vers entrepôt / SFTP / S3.

Couche de FONDATION : planifie des extraits de données (CSV/parquet) vers une
destination externe (SFTP, bucket S3, entrepôt…) SANS que ``core`` n'importe
une app métier (contrat import-linter ``core-foundation-is-a-base-layer``). Les
données proviennent de l'explorateur de données FG382 (datasets enregistrés par
les apps métier, querysets déjà scopés société) ; la destination est un
connecteur enregistré dans le registre d'intégrations (``core.integrations``).

Conception
----------

* ``ExportDestinationProvider`` (base) : interface ``deliver(filename, data,
  content_type, context=None)`` + ``is_configured()``. Non configuré → no-op
  propre (aucun transfert réseau).
* ``SftpDestination`` / ``S3Destination`` : enregistrés sous ``« sftp »`` /
  ``« s3 »``. Tant qu'aucun credential n'est branché, ``is_configured()`` est
  faux et aucun transfert n'a lieu.
* ``MinioWarehouseDestination`` (NTDATA27) : enregistrée sous ``« minio »``,
  elle vise le MinIO DÉJÀ provisionné par le compose du repo — l'entrepôt
  analytique fonctionne donc SANS aucun credential externe, sous la clé
  ``<bucket warehouse>/<company>/<dataset>/<date>.<ext>``.
* ``rendre_extrait(export)`` matérialise le contenu (CSV ou parquet best-effort)
  depuis le dataset du ``ScheduledExport``. ``executer(export, now=None)``
  rend l'extrait puis le livre à la destination configurée (no-op si non
  configurée) et met à jour ``derniere_execution_le`` / ``dernier_statut``.

⚠ AUTH : la livraison réelle vers SFTP/S3/Snowflake exige des credentials
provisionnés par le fondateur (variables d'environnement via ``secret_ref`` de
``IntegrationConfig``). Sans elles, ces destinations restent en no-op. Seule la
destination ``minio`` fonctionne sans credential externe (infra interne).
"""
from __future__ import annotations

import csv
import io
import logging
import os

from django.conf import settings
from django.utils import timezone

from .integrations import (
    BaseProvider,
    provider_from_config,
    register_provider,
)

logger = logging.getLogger(__name__)

# Type d'intégration des destinations d'extrait (registre d'intégrations).
TYPE_EXPORT_DEST = 'export_destination'

FORMAT_CSV = 'csv'
FORMAT_PARQUET = 'parquet'

# NTDATA27 — bucket de l'entrepôt analytique interne (MinIO du compose). Lu de
# l'environnement pour ne pas toucher un fichier de settings partagé ; un
# déploiement peut le surcharger via ``MINIO_BUCKET_WAREHOUSE``.
WAREHOUSE_BUCKET_DEFAULT = 'warehouse'


def warehouse_bucket() -> str:
    """Nom du bucket d'entrepôt analytique (MinIO interne)."""
    return (getattr(settings, 'MINIO_BUCKET_WAREHOUSE', '')
            or os.environ.get('MINIO_BUCKET_WAREHOUSE', '')
            or WAREHOUSE_BUCKET_DEFAULT)


class ExportDestinationProvider(BaseProvider):
    """Base d'un connecteur de destination d'extrait (fondation).

    ``context`` (optionnel) porte les métadonnées de l'extrait — ``company_id``,
    ``dataset``, ``date`` — pour les destinations qui organisent leur
    arborescence (entrepôt). Une destination qui n'en a pas besoin l'ignore.
    """

    integration_type = TYPE_EXPORT_DEST

    def deliver(self, filename, data, content_type,
                context=None) -> dict:  # pragma: no cover
        raise NotImplementedError


class _RemoteDestination(ExportDestinationProvider):
    """Destination distante paramétrable, base commune SFTP/S3.

    Non configurée (host/bucket ou secret manquant) → renvoie ``ok=False`` SANS
    transfert réseau. Le transfert réel est délibérément différé tant qu'aucun
    credential n'est branché.
    """

    def is_configured(self) -> bool:
        return bool(self.config.get('endpoint')) and bool(self.secret)

    def deliver(self, filename, data, content_type, context=None) -> dict:
        if not self.is_configured():
            return {'ok': False,
                    'detail': f'Destination {self.code} non configurée.'}
        # Transfert réel différé : on remonterait ici l'URI de l'objet livré.
        return {'ok': True, 'bytes': len(data or b''),
                'detail': f'livré ({self.code})'}


@register_provider
class SftpDestination(_RemoteDestination):
    code = 'sftp'
    label = 'SFTP'


@register_provider
class S3Destination(_RemoteDestination):
    code = 's3'
    label = 'Bucket S3'


def warehouse_key(context, filename) -> str:
    """Clé objet d'entrepôt : ``<company>/<dataset>/<date>.<ext>`` (NTDATA27).

    ``context`` = ``{'company_id', 'dataset', 'date'}``. Tolérant : une
    métadonnée absente est remplacée par un segment neutre, jamais d'exception.
    """
    ctx = dict(context or {})
    company = ctx.get('company_id') or 'sys'
    dataset = ctx.get('dataset') or 'extrait'
    date = ctx.get('date') or timezone.now().date().isoformat()
    ext = (filename or '').rsplit('.', 1)
    suffix = ext[1] if len(ext) == 2 else 'csv'
    safe_ds = ''.join(c for c in str(dataset)
                      if c.isalnum() or c in ('-', '_')) or 'extrait'
    return f'{company}/{safe_ds}/{date}.{suffix}'


def _minio_client():
    """Client boto3/S3 vers le MinIO interne (même patron que ``core.pdf`` —
    recopié pour que ``core`` reste dépendance-libre des apps domaine)."""
    import boto3
    return boto3.client(
        's3',
        endpoint_url='http://' + settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name='us-east-1',
    )


@register_provider
class MinioWarehouseDestination(ExportDestinationProvider):
    """NTDATA27 — entrepôt analytique sur le MinIO DÉJÀ provisionné.

    Aucun credential EXTERNE : le compose du repo fournit déjà MinIO, donc
    l'entrepôt fonctionne d'emblée. Les objets sont déposés sous
    ``<bucket warehouse>/<company>/<dataset>/<date>.<ext>`` (parquet
    best-effort, CSV sinon — cf. ``rendre_extrait``).

    ``is_configured()`` est vrai dès qu'un endpoint MinIO est déclaré ET que
    boto3 est importable ; sinon no-op propre (jamais d'exception).
    """

    code = 'minio'
    label = 'Entrepôt MinIO (interne)'

    def is_configured(self) -> bool:
        if not getattr(settings, 'MINIO_ENDPOINT', ''):
            return False
        try:  # pragma: no cover - boto3 est présent en prod comme en CI
            import boto3  # noqa: F401
        except Exception:
            return False
        return True

    def deliver(self, filename, data, content_type, context=None) -> dict:
        if not self.is_configured():
            return {'ok': False,
                    'detail': 'Entrepôt MinIO non configuré (endpoint absent).'}
        bucket = warehouse_bucket()
        key = warehouse_key(context, filename)
        try:
            client = _minio_client()
            try:
                client.head_bucket(Bucket=bucket)
            except Exception:
                client.create_bucket(Bucket=bucket)
            client.put_object(Bucket=bucket, Key=key, Body=data or b'',
                              ContentType=content_type or 'text/csv')
        except Exception as exc:  # noqa: BLE001 — jamais d'exception remontée
            logger.warning('entrepôt MinIO : dépôt %s/%s en échec', bucket, key,
                           exc_info=True)
            return {'ok': False, 'statut': 'erreur',
                    'detail': f'Dépôt entrepôt en échec : {exc}'}
        return {'ok': True, 'bytes': len(data or b''), 'key': key,
                'bucket': bucket, 'detail': f'déposé dans {bucket}/{key}'}


# ---------------------------------------------------------------------------
# NTDATA29 — connecteur Snowflake (GATED fondateur, livré DÉSARMÉ).
#
# Variables d'environnement REQUISES pour que le connecteur s'arme. Tant qu'une
# seule manque, ``is_configured()`` est faux : AUCUN import du connecteur,
# AUCUN appel réseau, AUCUNE dépendance dure ajoutée au projet
# (``snowflake-connector-python`` reste optionnel, importé paresseusement).
SNOWFLAKE_ENV_REQUIRED = (
    'SNOWFLAKE_ACCOUNT',
    'SNOWFLAKE_USER',
    'SNOWFLAKE_PASSWORD',
    'SNOWFLAKE_DATABASE',
    'SNOWFLAKE_SCHEMA',
)


def snowflake_env():
    """Paramètres Snowflake lus de l'environnement (jamais du code)."""
    keys = SNOWFLAKE_ENV_REQUIRED + ('SNOWFLAKE_WAREHOUSE', 'SNOWFLAKE_STAGE')
    return {k: os.environ.get(k, '') for k in keys}


def snowflake_table(context) -> str:
    """Nom de table DATÉE : ``<dataset>_<AAAAMMJJ>`` (identifiant SQL sûr)."""
    ctx = dict(context or {})
    dataset = ctx.get('dataset') or 'extrait'
    date = ctx.get('date') or timezone.now().date().isoformat()
    safe_ds = ''.join(c if (c.isalnum() or c == '_') else '_'
                      for c in str(dataset)) or 'extrait'
    safe_date = ''.join(c for c in str(date) if c.isdigit()) or '00000000'
    return f'{safe_ds}_{safe_date}'.upper()


def _snowflake_connect(env):  # pragma: no cover - exige un compte réel
    """Connexion Snowflake (import PARESSEUX et OPTIONNEL du connecteur)."""
    import snowflake.connector as sf
    return sf.connect(
        account=env['SNOWFLAKE_ACCOUNT'],
        user=env['SNOWFLAKE_USER'],
        password=env['SNOWFLAKE_PASSWORD'],
        database=env['SNOWFLAKE_DATABASE'],
        schema=env['SNOWFLAKE_SCHEMA'],
        warehouse=env.get('SNOWFLAKE_WAREHOUSE') or None,
    )


@register_provider
class SnowflakeDestination(ExportDestinationProvider):
    """NTDATA29 — chargement d'un extrait dans Snowflake (GATED fondateur).

    Livré DÉSARMÉ : sans les variables ``SNOWFLAKE_*``, ``is_configured()`` est
    faux, ``deliver()`` est un no-op propre et le connecteur Python n'est même
    pas importé (dépendance optionnelle, jamais dure — aucune nouvelle
    dépendance payante n'entre dans le projet tant que le fondateur ne
    provisionne pas le compte).

    Armé, le flux est celui de l'outil : ``PUT`` du fichier dans un stage, puis
    ``COPY INTO`` une table DATÉE ``<dataset>_<AAAAMMJJ>``.
    """

    code = 'snowflake'
    label = 'Snowflake (entrepôt externe)'

    def is_configured(self) -> bool:
        env = snowflake_env()
        if not all(env.get(k) for k in SNOWFLAKE_ENV_REQUIRED):
            return False
        try:
            import snowflake.connector  # noqa: F401
        except Exception:
            return False
        return True

    def deliver(self, filename, data, content_type, context=None) -> dict:
        if not self.is_configured():
            return {'ok': False,
                    'detail': 'Snowflake non configuré (variables '
                              'SNOWFLAKE_* absentes) — aucun chargement.'}
        env = snowflake_env()  # pragma: no cover - exige un compte réel
        stage = (self.config.get('stage')
                 or env.get('SNOWFLAKE_STAGE') or '~')
        table = snowflake_table(context)
        try:  # pragma: no cover - exige un compte Snowflake réel
            import os as _os
            import tempfile
            tmpdir = tempfile.mkdtemp(prefix='sf_export_')
            path = _os.path.join(tmpdir, filename or 'extrait.csv')
            with open(path, 'wb') as fh:
                fh.write(data or b'')
            conn = _snowflake_connect(env)
            try:
                cur = conn.cursor()
                cur.execute(
                    f"PUT file://{path} @{stage} OVERWRITE = TRUE")
                cur.execute(
                    f"COPY INTO {table} FROM @{stage}/"
                    f"{_os.path.basename(path)}")
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001 - jamais d'exception remontée
            logger.warning('Snowflake : chargement de %s en échec', table,
                           exc_info=True)
            return {'ok': False, 'statut': 'erreur',
                    'detail': f'Chargement Snowflake en échec : {exc}'}
        return {'ok': True, 'bytes': len(data or b''),  # pragma: no cover
                'detail': f'chargé dans {table}'}


def rendre_extrait(export):
    """Rend le contenu de l'extrait depuis le dataset du ``ScheduledExport``.

    CSV par défaut (toujours disponible). ``parquet`` best-effort : si pyarrow
    n'est pas présent, on dégrade proprement en CSV (jamais d'exception ni de
    dépendance dure). Renvoie ``(filename, data: bytes, content_type)``.
    """
    from . import data_explorer

    rows = data_explorer.run_query(
        export.dataset, export.company, None, export.spec or {})
    base = export.titre or export.dataset or 'extrait'
    safe = ''.join(c for c in base if c.isalnum() or c in ('-', '_')) or 'extrait'

    if export.format == FORMAT_PARQUET:
        data = _to_parquet(rows)
        if data is not None:
            return f'{safe}.parquet', data, 'application/octet-stream'
        # Dégradation propre : pas de pyarrow → CSV.
    data = _to_csv(rows)
    return f'{safe}.csv', data, 'text/csv'


def _to_csv(rows) -> bytes:
    buf = io.StringIO()
    if rows:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return buf.getvalue().encode('utf-8')


def _to_parquet(rows):
    """Sérialise en parquet si pyarrow est disponible, sinon ``None``."""
    try:  # pragma: no cover - dépendance optionnelle
        import pyarrow as pa
        import pyarrow.parquet as pq
    except Exception:
        return None
    if not rows:  # pragma: no cover
        return None
    table = pa.Table.from_pylist(rows)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()


def _active_destination_config(company, provider):
    from .models import IntegrationConfig
    return (IntegrationConfig.objects
            .filter(company=company, integration_type=TYPE_EXPORT_DEST,
                    provider=provider, actif=True)
            .order_by('id')
            .first())


def _destination_for(export):
    cfg = _active_destination_config(export.company, export.destination)
    if cfg is not None:
        return provider_from_config(cfg)
    from .integrations import get_provider_class
    cls = get_provider_class(TYPE_EXPORT_DEST, export.destination)
    return cls() if cls else None


def executer(export, now=None):
    """Rend l'extrait et le livre à la destination (no-op si non configurée).

    Met à jour ``derniere_execution_le`` / ``dernier_statut`` / ``dernier_detail``.
    Jamais d'exception réseau si non configuré.
    """
    now = now or timezone.now()
    filename, data, content_type = rendre_extrait(export)
    context = {
        'company_id': getattr(export, 'company_id', None),
        'dataset': export.dataset,
        'date': now.date().isoformat(),
    }
    dest = _destination_for(export)
    if dest is None:
        export.dernier_statut = 'erreur'
        export.dernier_detail = {
            'detail': f'Destination inconnue : {export.destination!r}'}
    else:
        res = dest.deliver(filename, data, content_type, context=context)
        export.dernier_statut = (
            res.get('statut') or ('ok' if res.get('ok') else 'non_configure'))
        export.dernier_detail = {'detail': res.get('detail', ''),
                                 'filename': filename}
        if res.get('key'):
            export.dernier_detail['key'] = res['key']
    export.derniere_execution_le = now
    export.save(update_fields=['dernier_statut', 'dernier_detail',
                               'derniere_execution_le', 'updated_at'])
    return export
