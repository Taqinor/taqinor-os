"""FG42 — Import de relevé bancaire / rapprochement de paiements.

Flux en deux temps (dry-run + commit) :
  1. dry-run  : parse le fichier XLSX/CSV, matche chaque ligne par référence
                ou montant/date → renvoie un aperçu (10 lignes, colonnes
                reconnues, factures trouvées, statut par ligne) SANS écriture.
  2. commit   : crée les Paiement manquants sur les lignes matchées. Réutilise
                la garde sur-paiement existante et le chatter facture.

Colonnes reconnues (insensible à la casse, accent-tolérant) :
  date, reference / ref / ref_virement, montant / amount, mode

ARC13 — la lecture bas niveau (CSV/XLSX, encodage, séparateur, en-têtes) est
déléguée à ``apps.dataimport.parsing`` (parseur générique partagé) au lieu
d'un ``csv.DictReader``/``openpyxl`` local ; comportement inchangé. Seule la
logique MÉTIER (mapping colonnes → champs paiement, matching facture, écriture
``Paiement``) reste ici, propre à ``ventes``.
"""
import logging
from decimal import Decimal, InvalidOperation

from apps.dataimport.parsing import iter_rows, normalize_header

logger = logging.getLogger(__name__)

# Colonnes attendues dans le relevé.
COLUMN_MAP = {
    'date': 'date',
    'reference': 'reference',
    'ref': 'reference',
    'ref_virement': 'reference',
    'reference_virement': 'reference',
    'libelle': 'reference',
    'montant': 'montant',
    'amount': 'montant',
    'credit': 'montant',
    'mode': 'mode',
    'type': 'mode',
}

MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024  # 5 Mo


def _norm(s):
    """Normalise un en-tête : minuscules, sans accents, espaces/tirets → _.

    ARC13 — délègue à ``apps.dataimport.parsing.normalize_header`` (logique
    partagée) ; comportement inchangé."""
    return normalize_header(s)


def _parse_rows(file_bytes, filename):
    """Renvoie (headers, rows) depuis un CSV ou XLSX.

    ARC13 — délègue à ``apps.dataimport.parsing.iter_rows`` (parseur
    générique partagé) ; comportement inchangé."""
    return iter_rows(file_bytes, filename)


def _map_row(raw_row, col_to_field):
    """Convertit une ligne brute en dict normalisé {field: raw_value}."""
    mapped = {}
    for raw_col, field in col_to_field.items():
        val = raw_row.get(raw_col)
        if val is not None and field not in mapped:
            mapped[field] = val
    return mapped


def _parse_montant(v):
    """Convertit une valeur en Decimal (accepte virgule / espace) ou None."""
    if v is None:
        return None
    s = str(v).strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
    try:
        d = Decimal(s)
        return d if d > 0 else None
    except InvalidOperation:
        return None


def _parse_date(v):
    """Convertit une valeur en str ISO AAAA-MM-JJ ou None."""
    if v is None:
        return None
    if hasattr(v, 'strftime'):  # datetime/date (openpyxl)
        return v.strftime('%Y-%m-%d')
    s = str(v).strip()
    # Accepte DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return s  # renvoie brut si non reconnu (signalé dans l'aperçu)


def _match_facture(ref, montant, company):
    """Cherche une facture ouverte matching par référence (priorité) ou montant.

    Renvoie la première facture trouvée (emise ou en_retard, même société) ou None.
    """
    from .models import Facture
    OPEN_STATUTS = (Facture.Statut.EMISE.value, Facture.Statut.EN_RETARD.value)
    qs = Facture.objects.filter(company=company, statut__in=OPEN_STATUTS)

    # 1) Référence exacte (insensible à la casse)
    if ref:
        ref_clean = (str(ref) or '').strip()
        hit = qs.filter(reference__iexact=ref_clean).first()
        if hit:
            return hit, 'reference'

    # 2) Montant TTC correspondant au reste à payer (tolerances 1 centime)
    if montant is not None:
        candidates = qs.prefetch_related('paiements', 'avoirs')
        for f in candidates:
            if abs(f.montant_du - montant) <= Decimal('0.01'):
                return f, 'montant'

    return None, None


def dry_run(file_bytes, filename, company, max_preview=10):
    """Aperçu sans écriture.

    Renvoie un dict :
      - ``columns``       : mapping en-tête → champ reconnu
      - ``unmapped``      : en-têtes non reconnus
      - ``preview``       : jusqu'à max_preview lignes avec statut
      - ``total_rows``    : nombre total de lignes dans le fichier
      - ``matched``       : nombre de lignes avec une facture trouvée
      - ``already_paid``  : nombre de lignes dont la facture est déjà intégralement payée
    """
    if len(file_bytes) > MAX_BYTES:
        raise ValueError(f'Fichier trop volumineux (max {MAX_BYTES // 1024 // 1024} Mo).')
    raw_headers, rows = _parse_rows(file_bytes, filename)
    if len(rows) > MAX_ROWS:
        raise ValueError(f'Trop de lignes (max {MAX_ROWS}).')

    # Mapper les colonnes.
    col_to_field = {}
    unmapped = []
    for h in raw_headers:
        field = COLUMN_MAP.get(_norm(h))
        if field:
            col_to_field[h] = field
        else:
            unmapped.append(h)

    preview = []
    matched = 0
    already_paid = 0

    for i, raw_row in enumerate(rows):
        mapped = _map_row(raw_row, col_to_field)
        montant = _parse_montant(mapped.get('montant'))
        date = _parse_date(mapped.get('date'))
        ref = (mapped.get('reference') or '').strip()

        if montant is None:
            # Ligne sans montant valide — souvent une ligne de total/en-tête.
            item = {
                'ligne': i + 2, 'date': date, 'reference': ref,
                'montant': None, 'statut': 'montant_invalide',
                'facture_reference': None, 'match_type': None,
            }
        else:
            facture, match_type = _match_facture(ref, montant, company)
            if facture:
                matched += 1
                reste = facture.montant_du
                if reste <= Decimal('0.01'):
                    already_paid += 1
                    statut = 'deja_regle'
                elif montant - reste > Decimal('0.01'):
                    statut = 'surpaiement'
                else:
                    statut = 'a_importer'
            else:
                statut = 'non_trouve'

            item = {
                'ligne': i + 2, 'date': date, 'reference': ref,
                'montant': str(montant),
                'statut': statut,
                'facture_reference': facture.reference if facture else None,
                'match_type': match_type,
            }

        if len(preview) < max_preview:
            preview.append(item)

    return {
        'columns': {h: f for h, f in col_to_field.items()},
        'unmapped': unmapped,
        'preview': preview,
        'total_rows': len(rows),
        'matched': matched,
        'already_paid': already_paid,
    }


def commit(file_bytes, filename, company, user):
    """Import effectif — crée les Paiement manquants.

    Renvoie un dict : {created, skipped, errors, results[{ligne, statut}]}.
    Chaque paiement est créé dans sa propre transaction (pas de rollback global).
    """
    from django.db import transaction as db_transaction
    from .models import Facture, Paiement
    from . import activity

    if len(file_bytes) > MAX_BYTES:
        raise ValueError(f'Fichier trop volumineux (max {MAX_BYTES // 1024 // 1024} Mo).')
    raw_headers, rows = _parse_rows(file_bytes, filename)
    if len(rows) > MAX_ROWS:
        raise ValueError(f'Trop de lignes (max {MAX_ROWS}).')

    col_to_field = {h: COLUMN_MAP[_norm(h)] for h in raw_headers
                    if _norm(h) in COLUMN_MAP}
    OPEN_STATUTS = (Facture.Statut.EMISE.value, Facture.Statut.EN_RETARD.value)

    created = 0
    skipped = 0
    errors = 0
    results = []

    for i, raw_row in enumerate(rows):
        mapped = _map_row(raw_row, col_to_field)
        montant = _parse_montant(mapped.get('montant'))
        date_str = _parse_date(mapped.get('date'))
        ref = (mapped.get('reference') or '').strip()
        mode_raw = (mapped.get('mode') or 'virement').strip().lower()
        # Normalise le mode vers les choix Paiement.Mode.
        mode_map = {
            'virement': 'virement', 'wire': 'virement',
            'cheque': 'cheque', 'chèque': 'cheque',
            'especes': 'especes', 'espèces': 'especes', 'cash': 'especes',
            'carte': 'carte', 'card': 'carte',
            'prelevement': 'prelevement', 'prélèvement': 'prelevement',
        }
        mode = mode_map.get(mode_raw, 'virement')

        if montant is None:
            skipped += 1
            results.append({'ligne': i + 2, 'statut': 'montant_invalide'})
            continue

        from datetime import date as _date
        try:
            date_obj = _date.fromisoformat(date_str) if date_str else _date.today()
        except (ValueError, TypeError):
            date_obj = _date.today()

        facture, match_type = _match_facture(ref, montant, company)
        if not facture:
            skipped += 1
            results.append({
                'ligne': i + 2, 'statut': 'non_trouve',
                'reference': ref, 'montant': str(montant)})
            continue

        try:
            with db_transaction.atomic():
                locked = Facture.objects.select_for_update().get(
                    pk=facture.pk, company=company, statut__in=OPEN_STATUTS)
                reste = locked.montant_du
                if reste <= Decimal('0.01'):
                    skipped += 1
                    results.append({
                        'ligne': i + 2, 'statut': 'deja_regle',
                        'facture': locked.reference})
                    continue
                # Garde sur-paiement (identique à enregistrer-paiement).
                if montant - reste > Decimal('0.01'):
                    skipped += 1
                    results.append({
                        'ligne': i + 2, 'statut': 'surpaiement',
                        'facture': locked.reference,
                        'montant': str(montant),
                        'reste': str(reste)})
                    continue
                paiement = Paiement.objects.create(
                    company=company, facture=locked,
                    montant=montant, date_paiement=date_obj,
                    mode=mode, reference=ref or None,
                    note=f'Import relevé bancaire (ligne {i + 2})',
                    created_by=user)
                activity.log_facture_paiement(locked, user, paiement)
                # YLEDG1 — événement documentaire générique (pose du seam
                # pour compta.ecriture_pour_paiement).
                from core.events import paiement_enregistre
                paiement_enregistre.send(
                    sender=Paiement, instance=paiement, company=company)
                locked.refresh_from_db()
                if locked.montant_du <= Decimal('0') and \
                        locked.statut != Facture.Statut.ANNULEE.value:
                    locked.statut = Facture.Statut.PAYEE.value
                    locked.save(update_fields=['statut'])
            created += 1
            results.append({
                'ligne': i + 2, 'statut': 'created',
                'facture': facture.reference,
                'montant': str(montant),
                'match_type': match_type})
        except Facture.DoesNotExist:
            # Race: facture payée entre le match et l'atomic.
            skipped += 1
            results.append({'ligne': i + 2, 'statut': 'deja_regle',
                            'facture': facture.reference})
        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.warning('Import paiement ligne %d : %s', i + 2, exc,
                           exc_info=True)
            results.append({'ligne': i + 2, 'statut': 'erreur',
                            'detail': str(exc)})

    return {
        'created': created, 'skipped': skipped, 'errors': errors,
        'results': results}
