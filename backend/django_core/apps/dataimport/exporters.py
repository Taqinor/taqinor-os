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


def export_csv(spec, company, neutralize=True):
    """CSV de l'objet. AUD802 — neutralisé par défaut (un .csv s'ouvre dans
    Excel exactement comme un .xlsx : ``=HYPERLINK(...)`` s'y exécute pareil).
    ``neutralize=False`` est l'opt-out NOMMÉ du round-trip de sauvegarde."""
    from apps.records.xlsx import neutralize_cell

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(spec.header())
    for row in spec.rows(company):
        # La neutralisation s'applique à la valeur BRUTE, avant ``_cell`` :
        # ``neutralize_cell`` ne touche QUE les chaînes, donc un Decimal
        # négatif (« -10 » une fois sérialisé) n'est jamais préfixé — même
        # sémantique exacte que le chemin xlsx.
        valeurs = [neutralize_cell(v) for v in row] if neutralize else row
        writer.writerow([_cell(v) for v in valeurs])
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


def export_xlsx(spec, company, neutralize=True):
    """L879 — passe par le builder .xlsx PARTAGÉ (apps.records.xlsx) pour que
    l'export configurable/ZIP ait exactement le même format (en-têtes en gras,
    largeurs, coercition fr-MA) que les exports de listes.

    AUD802 — neutralisé par défaut ; ``neutralize=False`` est l'opt-out NOMMÉ
    du round-trip de sauvegarde (cf. ``build_backup_zip``)."""
    from apps.records.xlsx import workbook_bytes

    return workbook_bytes(
        spec.header(), spec.rows(company), sheet_title=spec.key,
        neutralize=neutralize)


def export_bytes(spec, company, fmt, neutralize=True):
    """Sérialise un objet dans le format demandé -> bytes.

    AUD802 — ``neutralize`` traverse jusqu'au sérialiseur : le TÉLÉCHARGEMENT
    (``export_views.exporter``, la commande ``export_company_data --object``)
    part neutralisé, la SAUVEGARDE ZIP passe ``False``.
    """
    if fmt == 'csv':
        return export_csv(spec, company, neutralize=neutralize)
    if fmt == 'xlsx':
        return export_xlsx(spec, company, neutralize=neutralize)
    if fmt == 'json':
        # JSON n'est pas ouvert par un tableur : neutraliser y corromprait les
        # valeurs sans rien protéger.
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

    AUD802 — SEUL opt-out de la neutralisation anti-formule
    (``neutralize=False``) : ce bundle est fait pour être RE-IMPORTÉ. Le
    neutraliser préfixerait une apostrophe à chaque « +212… » et corromprait la
    restauration. Tous les autres chemins (téléchargement unitaire, pièce
    jointe e-mail, lien public) restent neutralisés.
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
            data = export_bytes(spec, company, fmt, neutralize=False)
            zf.writestr(filename_for(spec, fmt, stamp), data)
            manifest_lines.append(f'  - {spec.label} ({spec.key})')
        zf.writestr('MANIFEST.txt', '\n'.join(manifest_lines) + '\n')
    return buf.getvalue()
