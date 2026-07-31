"""FG377/NTAPI37 — Pont comptable Sage / CEGID / QuickBooks (one-way), fondation.

Exporte des écritures de journal (ventes/achats) au format importable par Sage
ou CEGID — SANS que ``core`` n'importe l'app ``ventes``/``compta`` qui produit
ces écritures (contrat import-linter ``core-foundation-is-a-base-layer``).
L'appelant (côté compta) passe une liste d'écritures sous forme de DICTS purs ;
``core`` ne fait que le FORMATAGE (transformation de données pure).

Format d'une écriture (dict attendu)
------------------------------------

    {
        "journal": "VT",            # code journal (VT ventes, AC achats…)
        "date": "2026-06-30",       # AAAA-MM-JJ
        "compte": "411000",         # numéro de compte général/auxiliaire
        "libelle": "Facture F-001",
        "debit": 1200.00,           # montant débit (0 si crédit)
        "credit": 0.00,             # montant crédit (0 si débit)
        "piece": "F-001",           # référence pièce (optionnel)
    }

Deux formats one-way sont produits :

* ``to_sage_pnm`` — format PNM/texte délimité par tabulations, large compat
  Sage Ligne 100 (import « écritures »).
* ``to_cegid_csv`` — CSV point-virgule, compat import CEGID Loop/Quadra.
* ``to_quickbooks_iif`` (NTAPI37) — format IIF QuickBooks Desktop (import
  « General Journal », blocs TRNS/SPL/ENDTRNS tabulés) : les écritures
  PARTAGEANT la même ``piece`` (référence pièce) forment UNE transaction
  équilibrée (1re ligne = TRNS, les suivantes = SPL), montant signé (débit
  positif, crédit négatif — convention IIF), date au format US MM/JJ/AAAA.

Aucune écriture sur la base, aucun appel réseau : transformation pure et
déterministe (testable hors DB).
"""
from __future__ import annotations

import csv
import io


# Colonnes du format Sage PNM (ordre fixe).
_SAGE_COLS = ['journal', 'date', 'compte', 'piece', 'libelle', 'debit',
              'credit']
# Colonnes du format CEGID CSV (ordre fixe, en-têtes lisibles).
_CEGID_HEADER = ['Journal', 'Date', 'Compte', 'Piece', 'Libelle', 'Debit',
                 'Credit']


def _fmt_amount(value) -> str:
    """Montant à 2 décimales, point décimal (vide → 0,00 équivalent 0.00)."""
    try:
        return f'{float(value or 0):.2f}'
    except (TypeError, ValueError):
        return '0.00'


def _norm_date(value) -> str:
    """Date AAAA-MM-JJ → JJ/MM/AAAA (format comptable FR), tolérant."""
    s = str(value or '')
    parts = s.split('-')
    if len(parts) == 3 and len(parts[0]) == 4:
        y, m, d = parts
        return f'{d}/{m}/{y}'
    return s


def _norm_date_us(value) -> str:
    """NTAPI37 — Date AAAA-MM-JJ → MM/JJ/AAAA (convention QuickBooks US),
    tolérant (comme ``_norm_date``)."""
    s = str(value or '')
    parts = s.split('-')
    if len(parts) == 3 and len(parts[0]) == 4:
        y, m, d = parts
        return f'{m}/{d}/{y}'
    return s


def _signed_amount(entry) -> str:
    """NTAPI37 — convention IIF : débit POSITIF, crédit NÉGATIF."""
    try:
        debit = float(entry.get('debit') or 0)
        credit = float(entry.get('credit') or 0)
    except (TypeError, ValueError):
        debit = credit = 0.0
    return f'{debit - credit:.2f}'


def validate_entries(entries) -> list[str]:
    """Contrôles de base : champs requis + équilibre débit/crédit global.

    Retourne la liste des erreurs (vide = OK). N'écrit rien, ne lève pas.
    """
    errors = []
    total_debit = 0.0
    total_credit = 0.0
    for i, e in enumerate(entries):
        if not e.get('journal'):
            errors.append(f'Écriture {i}: journal manquant.')
        if not e.get('compte'):
            errors.append(f'Écriture {i}: compte manquant.')
        try:
            total_debit += float(e.get('debit') or 0)
            total_credit += float(e.get('credit') or 0)
        except (TypeError, ValueError):
            errors.append(f'Écriture {i}: montant invalide.')
    if abs(total_debit - total_credit) > 0.01:
        errors.append(
            f'Déséquilibre débit/crédit : {total_debit:.2f} ≠ '
            f'{total_credit:.2f}.')
    return errors


def to_sage_pnm(entries) -> str:
    """Sérialise les écritures au format Sage PNM (texte tabulé, en-tête inclus)."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter='\t', lineterminator='\n')
    writer.writerow(_SAGE_COLS)
    for e in entries:
        writer.writerow([
            e.get('journal', ''),
            _norm_date(e.get('date')),
            e.get('compte', ''),
            e.get('piece', ''),
            e.get('libelle', ''),
            _fmt_amount(e.get('debit')),
            _fmt_amount(e.get('credit')),
        ])
    return out.getvalue()


def to_cegid_csv(entries) -> str:
    """Sérialise les écritures au format CEGID (CSV point-virgule, en-tête)."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=';', lineterminator='\n')
    writer.writerow(_CEGID_HEADER)
    for e in entries:
        writer.writerow([
            e.get('journal', ''),
            _norm_date(e.get('date')),
            e.get('compte', ''),
            e.get('piece', ''),
            e.get('libelle', ''),
            _fmt_amount(e.get('debit')),
            _fmt_amount(e.get('credit')),
        ])
    return out.getvalue()


def to_quickbooks_iif(entries) -> str:
    """NTAPI37 — sérialise ``entries`` au format QuickBooks IIF (import
    General Journal), tabulé (``\\t``), fin de ligne ``\\n``.

    Les écritures sont regroupées PAR ``piece`` (dans l'ordre d'apparition,
    jamais retriées — un groupe = UNE pièce comptable) : la 1re ligne du
    groupe devient ``TRNS`` (l'écriture d'ouverture), les suivantes ``SPL``
    (contre-parties), le groupe se referme par ``ENDTRNS``. Un ``TRNSID``
    entier auto-incrémenté identifie chaque transaction (QuickBooks l'exige,
    même s'il n'est pas réutilisé au ré-import). Le document produit reste
    ÉQUILIBRÉ transaction par transaction dès lors que les ``entries``
    d'entrée le sont déjà (même contrat que ``validate_entries``).
    """
    out = io.StringIO()
    writer = csv.writer(out, delimiter='\t', lineterminator='\n')
    writer.writerow(['!TRNS', 'TRNSID', 'TRNSTYPE', 'DATE', 'ACCNT', 'NAME',
                     'AMOUNT', 'DOCNUM', 'MEMO'])
    writer.writerow(['!SPL', 'SPLID', 'TRNSTYPE', 'DATE', 'ACCNT', 'NAME',
                     'AMOUNT', 'DOCNUM', 'MEMO'])
    writer.writerow(['!ENDTRNS'])

    groups: dict = {}
    order: list = []
    for e in entries:
        piece = e.get('piece') or ''
        if piece not in groups:
            groups[piece] = []
            order.append(piece)
        groups[piece].append(e)

    trns_id = 0
    for piece in order:
        lines = groups[piece]
        if not lines:
            continue
        trns_id += 1
        first, rest = lines[0], lines[1:]
        writer.writerow([
            'TRNS', trns_id, 'GENERAL JOURNAL', _norm_date_us(first.get('date')),
            first.get('compte', ''), first.get('libelle', ''),
            _signed_amount(first), piece, first.get('libelle', ''),
        ])
        for i, e in enumerate(rest, start=1):
            writer.writerow([
                'SPL', f'{trns_id}-{i}', 'GENERAL JOURNAL',
                _norm_date_us(e.get('date')), e.get('compte', ''),
                e.get('libelle', ''), _signed_amount(e), piece,
                e.get('libelle', ''),
            ])
        writer.writerow(['ENDTRNS'])
    return out.getvalue()


FORMATS = {
    'sage': to_sage_pnm,
    'cegid': to_cegid_csv,
    'quickbooks_iif': to_quickbooks_iif,
}


def export_entries(entries, fmt='sage') -> str:
    """Exporte ``entries`` au format demandé (``'sage'`` | ``'cegid'``).

    Format inconnu → ``ValueError``. Transformation pure (pas de DB/réseau).
    """
    serializer = FORMATS.get(fmt)
    if serializer is None:
        raise ValueError(f'Format comptable inconnu : {fmt!r}')
    return serializer(entries)
