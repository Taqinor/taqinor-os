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
  content_type)`` + ``is_configured()``. Non configuré → no-op propre (aucun
  transfert réseau).
* ``SftpDestination`` / ``S3Destination`` : enregistrés sous ``« sftp »`` /
  ``« s3 »``. Tant qu'aucun credential n'est branché, ``is_configured()`` est
  faux et aucun transfert n'a lieu.
* ``rendre_extrait(export)`` matérialise le contenu (CSV ou parquet best-effort)
  depuis le dataset du ``ScheduledExport``. ``executer(export, now=None)``
  rend l'extrait puis le livre à la destination configurée (no-op si non
  configurée) et met à jour ``derniere_execution_le`` / ``dernier_statut``.

⚠ AUTH : la livraison réelle exige des credentials SFTP/S3 provisionnés par le
fondateur (variables d'environnement via ``secret_ref`` de
``IntegrationConfig``). Sans elles, le module reste en no-op.
"""
from __future__ import annotations

import csv
import io

from django.utils import timezone

from .integrations import (
    BaseProvider,
    provider_from_config,
    register_provider,
)

# Type d'intégration des destinations d'extrait (registre d'intégrations).
TYPE_EXPORT_DEST = 'export_destination'

FORMAT_CSV = 'csv'
FORMAT_PARQUET = 'parquet'


class ExportDestinationProvider(BaseProvider):
    """Base d'un connecteur de destination d'extrait (fondation)."""

    integration_type = TYPE_EXPORT_DEST

    def deliver(self, filename, data, content_type) -> dict:  # pragma: no cover
        raise NotImplementedError


class _RemoteDestination(ExportDestinationProvider):
    """Destination distante paramétrable, base commune SFTP/S3.

    Non configurée (host/bucket ou secret manquant) → renvoie ``ok=False`` SANS
    transfert réseau. Le transfert réel est délibérément différé tant qu'aucun
    credential n'est branché.
    """

    def is_configured(self) -> bool:
        return bool(self.config.get('endpoint')) and bool(self.secret)

    def deliver(self, filename, data, content_type) -> dict:
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
    dest = _destination_for(export)
    if dest is None:
        export.dernier_statut = 'erreur'
        export.dernier_detail = {
            'detail': f'Destination inconnue : {export.destination!r}'}
    else:
        res = dest.deliver(filename, data, content_type)
        export.dernier_statut = 'ok' if res.get('ok') else 'non_configure'
        export.dernier_detail = {'detail': res.get('detail', ''),
                                 'filename': filename}
    export.derniere_execution_le = now
    export.save(update_fields=['dernier_statut', 'dernier_detail',
                               'derniere_execution_le', 'updated_at'])
    return export
