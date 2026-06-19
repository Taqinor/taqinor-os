"""N97 — Sérialiseurs d'export : CSV, XLSX (openpyxl, pré-approuvé), JSON.

Chaque fonction prend une ``ExportSpec`` (cf. ``export_registry``) + la société
et renvoie ``bytes`` prêts à streamer. Aucune donnée n'est persistée sur disque
ni dans le stockage objet : tout est généré à la demande et streamé à
l'utilisateur (HttpResponse). Le prix d'achat n'apparaît jamais — il est exclu
en amont par le registre.
"""
import csv
import datetime
import io
import json
from decimal import Decimal

# Formats supportés -> (extension, content-type).
FORMATS = {
    'csv': ('csv', 'text/csv; charset=utf-8'),
    'xlsx': ('xlsx',
             'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    'json': ('json', 'application/json; charset=utf-8'),
}

DEFAULT_FORMAT = 'csv'


def _cell(value):
    """Rendu d'une valeur en texte sûr pour CSV (non typé Excel)."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _json_value(value):
    """Rendu d'une valeur pour JSON (types natifs quand possible)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def export_csv(spec, company):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(spec.header())
    for row in spec.rows(company):
        writer.writerow([_cell(v) for v in row])
    # BOM UTF-8 : Excel ouvre alors correctement les accents FR.
    return ('﻿' + buf.getvalue()).encode('utf-8')


def export_json(spec, company):
    header = spec.header()
    records = []
    for row in spec.rows(company):
        records.append({
            col: _json_value(v) for col, v in zip(header, row)
        })
    payload = {
        'object': spec.key,
        'label': spec.label,
        'columns': header,
        'count': len(records),
        'records': records,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')


def _xlsx_cell(value):
    """Valeur acceptable par openpyxl (pas de Decimal/objets exotiques)."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return value
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def export_xlsx(spec, company):
    # Import local : openpyxl n'est requis que pour ce format.
    from openpyxl import Workbook

    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title=spec.key[:31] or 'export')
    ws.append(spec.header())
    for row in spec.rows(company):
        ws.append([_xlsx_cell(v) for v in row])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_bytes(spec, company, fmt):
    """Sérialise un objet dans le format demandé -> bytes."""
    if fmt == 'csv':
        return export_csv(spec, company)
    if fmt == 'xlsx':
        return export_xlsx(spec, company)
    if fmt == 'json':
        return export_json(spec, company)
    raise ValueError(f'Format non supporté : {fmt}')


def filename_for(spec, fmt, stamp=None):
    ext = FORMATS[fmt][0]
    stamp = stamp or datetime.date.today().isoformat()
    return f'{spec.key}_{stamp}.{ext}'


def backup_filename(company, stamp=None):
    """Nom du bundle ZIP de sauvegarde d'une société."""
    stamp = stamp or datetime.date.today().isoformat()
    slug = (getattr(company, 'slug', '') or 'societe').replace('/', '-')
    return f'sauvegarde_{slug}_{stamp}.zip'


def build_backup_zip(specs, company, fmt, stamp=None):
    """Sauvegarde complète : bundle ZIP (un fichier par objet) + MANIFEST.txt.

    ``specs`` est une liste d'``ExportSpec``. Rien n'est persisté : le ZIP est
    construit en mémoire et renvoyé en ``bytes`` pour streaming.
    """
    import zipfile

    stamp = stamp or datetime.date.today().isoformat()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        manifest_lines = [
            'Sauvegarde TAQINOR OS',
            f'Société : {getattr(company, "nom", "")}',
            f'Date : {stamp}',
            f'Format : {fmt}',
            '',
            'Objets inclus :',
        ]
        for spec in specs:
            data = export_bytes(spec, company, fmt)
            zf.writestr(filename_for(spec, fmt, stamp), data)
            manifest_lines.append(f'  - {spec.label} ({spec.key})')
        zf.writestr('MANIFEST.txt', '\n'.join(manifest_lines) + '\n')
    return buf.getvalue()
