"""T9 — import réutilisable CSV/XLSX (leads, clients, produits).

Flux en deux temps, multi-tenant :
  1. dry-run : on lit les 10 premières lignes, on mappe colonne → champ (par
     en-tête, insensible à la casse/accents), et on liste ce qui n'a PAS été
     mappé — pour validation AVANT le batch complet.
  2. commit : création UNIQUEMENT (jamais d'écrasement silencieux). Les doublons
     (email/téléphone pour leads/clients, SKU pour produits) sont signalés et
     ignorés. Les enregistrements créés sont marqués d'origine (import).

Séparé de la migration ponctuelle des 619 leads Odoo (gardée à part).
"""
import csv
import io
import unicodedata

from django.db import transaction

# Mapping en-tête (normalisé) → champ modèle, par cible.
FIELD_MAPS = {
    'leads': {
        'nom': 'nom', 'prenom': 'prenom', 'societe': 'societe',
        'email': 'email', 'telephone': 'telephone', 'tel': 'telephone',
        'ville': 'ville', 'whatsapp': 'whatsapp', 'adresse': 'adresse',
    },
    'clients': {
        'nom': 'nom', 'prenom': 'prenom', 'email': 'email',
        'telephone': 'telephone', 'tel': 'telephone', 'adresse': 'adresse',
        'ice': 'ice',
    },
    'products': {
        'nom': 'nom', 'sku': 'sku', 'reference': 'sku', 'marque': 'marque',
        'prix_vente': 'prix_vente', 'prix': 'prix_vente',
        'prix_achat': 'prix_achat', 'quantite': 'quantite_stock',
        'quantite_stock': 'quantite_stock', 'stock': 'quantite_stock',
        'description': 'description',
    },
}

TARGETS = set(FIELD_MAPS)

# ERR53 — Plafond de lignes : au-delà, on refuse proprement (ValueError → 400
# clair côté vue) plutôt que de charger un fichier géant en mémoire et risquer
# un OOM. Doit rester aligné avec `views.MAX_ROWS`.
MAX_ROWS = 10000


class ImportTooLarge(ValueError):
    """Le fichier dépasse le plafond de lignes autorisé (ERR53)."""


def _norm(s):
    """Normalise un en-tête : minuscules, sans accents, espaces → underscore."""
    s = (s or '').strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')
    return s.replace(' ', '_').replace('-', '_')


def parse_rows(file_bytes, filename):
    """Renvoie (headers, rows[list[dict]]) depuis un CSV ou XLSX."""
    name = (filename or '').lower()
    if name.endswith('.xlsx'):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        headers = [str(h) if h is not None else '' for h in next(it, [])]
        rows = []
        for r in it:
            rows.append({headers[i]: r[i] for i in range(len(headers)) if i < len(r)})
        return headers, rows
    # CSV (utf-8, séparateur , ou ;)
    text = file_bytes.decode('utf-8-sig', errors='replace')
    sample = text[:2000]
    delim = ';' if sample.count(';') > sample.count(',') else ','
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    headers = reader.fieldnames or []
    return headers, list(reader)


def _map_headers(headers, target):
    fmap = FIELD_MAPS[target]
    mapped, unmapped = {}, []
    for h in headers:
        field = fmap.get(_norm(h))
        if field:
            mapped[h] = field
        else:
            unmapped.append(h)
    return mapped, unmapped


def dry_run(file_bytes, filename, target):
    """Aperçu : mapping colonne→champ + 10 premières lignes mappées + non-mappés."""
    if target not in TARGETS:
        raise ValueError("Cible d'import inconnue.")
    headers, rows = parse_rows(file_bytes, filename)
    if len(rows) > MAX_ROWS:
        raise ImportTooLarge(
            f'Trop de lignes : {len(rows)} (max {MAX_ROWS}).')
    mapped, unmapped = _map_headers(headers, target)
    preview = []
    for row in rows[:10]:
        preview.append({field: row.get(col) for col, field in mapped.items()})
    return {
        'target': target,
        'colonnes': headers,
        'mapping': mapped,
        'non_mappees': unmapped,
        'apercu': preview,
        'total_lignes': len(rows),
    }


def _row_to_fields(row, mapped):
    return {field: row.get(col) for col, field in mapped.items()
            if row.get(col) not in (None, '')}


def commit(file_bytes, filename, target, company, user):
    """Crée les enregistrements (jamais d'écrasement). Renvoie un récapitulatif."""
    if target not in TARGETS:
        raise ValueError("Cible d'import inconnue.")
    headers, rows = parse_rows(file_bytes, filename)
    if len(rows) > MAX_ROWS:
        raise ImportTooLarge(
            f'Trop de lignes : {len(rows)} (max {MAX_ROWS}).')
    mapped, _ = _map_headers(headers, target)
    created, skipped = 0, []

    # ERR51 — Tout l'import est atomique : une erreur en cours de boucle annule
    # l'intégralité du lot (jamais de demi-import laissant le compteur perdu et
    # une partie des lignes déjà créées).
    with transaction.atomic():
        if target == 'leads':
            from apps.crm.models import Lead
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                if not f.get('nom') and not f.get('email') and not f.get('telephone'):
                    skipped.append({'ligne': i, 'raison': 'ligne vide'})
                    continue
                dup = Lead.objects.filter(company=company)
                if f.get('email'):
                    dup = dup.filter(email__iexact=f['email'])
                elif f.get('telephone'):
                    dup = dup.filter(telephone=f['telephone'])
                else:
                    dup = Lead.objects.none()
                if dup.exists():
                    skipped.append({'ligne': i, 'raison': 'doublon (existe déjà)'})
                    continue
                tags = (f.pop('tags', '') or '')
                f['tags'] = (tags + (', ' if tags else '') + 'Import').strip(', ')[:500]
                Lead.objects.create(company=company, **f)
                created += 1

        elif target == 'clients':
            from apps.crm.models import Client
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                if not f.get('nom'):
                    skipped.append({'ligne': i, 'raison': 'nom manquant'})
                    continue
                if f.get('email') and Client.objects.filter(
                        company=company, email__iexact=f['email']).exists():
                    skipped.append({'ligne': i, 'raison': 'doublon (email existe)'})
                    continue
                Client.objects.create(company=company, **f)
                created += 1

        elif target == 'products':
            from decimal import Decimal, InvalidOperation
            from apps.stock.models import MouvementStock, Produit
            for i, row in enumerate(rows, 1):
                f = _row_to_fields(row, mapped)
                if not f.get('nom'):
                    skipped.append({'ligne': i, 'raison': 'nom manquant'})
                    continue
                if f.get('sku') and Produit.objects.filter(
                        company=company, sku=f['sku']).exists():
                    skipped.append({'ligne': i, 'raison': 'doublon (SKU existe)'})
                    continue
                for k in ('prix_vente', 'prix_achat'):
                    if k in f:
                        raw = (str(f[k]).replace('\xa0', '').replace(' ', '')
                               .replace(',', '.'))
                        try:
                            f[k] = Decimal(raw)
                        except (InvalidOperation, ValueError):
                            f.pop(k)
                # ERR52 — Le stock d'ouverture ne peut jamais être négatif et
                # passe par le registre des mouvements (audit) comme partout
                # ailleurs : on crée le produit à 0 puis on enregistre un
                # MouvementStock ENTREE pour la quantité importée.
                opening = 0
                if 'quantite_stock' in f:
                    try:
                        opening = int(float(f.pop('quantite_stock')))
                    except (ValueError, TypeError):
                        opening = 0
                    if opening < 0:
                        skipped.append(
                            {'ligne': i, 'raison': 'stock négatif refusé'})
                        continue
                f.setdefault('prix_vente', Decimal('0'))
                produit = Produit.objects.create(
                    company=company, quantite_stock=0, **f)
                if opening > 0:
                    produit.quantite_stock = opening
                    produit.save(update_fields=['quantite_stock'])
                    MouvementStock.objects.create(
                        company=company, produit=produit,
                        type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                        quantite=opening, quantite_avant=0,
                        quantite_apres=opening, created_by=user,
                        note='Stock initial (import)')
                created += 1

    return {'ok': True, 'target': target, 'created': created,
            'skipped': skipped, 'total': len(rows)}
