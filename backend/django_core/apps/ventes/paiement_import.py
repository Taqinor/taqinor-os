"""FG42 — Import de relevé bancaire / rapprochement de paiements.

Flux en deux temps (dry-run + commit) :
  1. dry-run  : parse le fichier XLSX/CSV, matche chaque ligne, PERSISTE la
                liste complète des décisions dans une ``ReleveImportSession``
                et renvoie un aperçu + un JETON. Aucune écriture d'argent.
  2. commit   : rejoue les décisions d'un JETON de dry-run — il ne matche
                plus rien lui-même. Réutilise la garde sur-paiement existante
                et le chatter facture.

Colonnes reconnues (insensible à la casse, accent-tolérant) :
  date, reference / ref / ref_virement, montant / amount, mode,
  libelle / donneur_ordre / emetteur (texte bancaire libre), ice

AUD121 — CE QUI A CHANGÉ ET POURQUOI (trois défauts d'argent) :

  * **Plus de rapprochement par MONTANT SEUL.** L'ancien ``_match_facture``
    prenait, après l'échec du match par référence, la PREMIÈRE facture
    ouverte de la société dont le reste dû égalait le montant à ±0,01 —
    sans aucun filtre client. Deux clients devant chacun 12 000 MAD : le
    virement du premier soldait la facture du second, qui cessait d'être
    relancé pendant que le vrai payeur l'était. Le rapprochement par
    montant exige désormais un client IDENTIFIABLE (ICE ou nom du donneur
    d'ordre lu dans le libellé, via ``crm.selectors``).
  * **Ambiguïté détectée, jamais tranchée toute seule.** Dès que plus d'une
    facture ouverte partage le montant à la tolérance, la ligne part en
    ``ambigu`` et n'est JAMAIS affectée automatiquement.
  * **``commit`` est un import de DÉCISIONS.** Il re-parsait et re-matchait
    le fichier INDÉPENDAMMENT du dry-run, jusqu'à 5 000 lignes alors que
    l'aperçu n'en montrait que 10, sans jeton ni hash — donc sans aucune
    déduplication du même fichier importé deux fois. Il exige maintenant le
    jeton d'un dry-run, n'écrit que les lignes validées, et refuse un
    contenu de fichier déjà importé pour cette société.

Le libellé bancaire n'est plus mappé sur ``reference`` (il ne matchait
jamais la référence exacte et retombait donc systématiquement sur le
montant — c'était le carburant du défaut) : il alimente l'identification du
donneur d'ordre.

ARC13 — la lecture bas niveau (CSV/XLSX, encodage, séparateur, en-têtes) est
déléguée à ``apps.dataimport.parsing`` (parseur générique partagé) au lieu
d'un ``csv.DictReader``/``openpyxl`` local ; comportement inchangé. Seule la
logique MÉTIER (mapping colonnes → champs paiement, matching facture, écriture
``Paiement``) reste ici, propre à ``ventes``.
"""
import hashlib
import logging
import secrets
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
    # AUD121 — le libellé bancaire est un TEXTE LIBRE, pas une référence de
    # facture : le mapper sur `reference` le condamnait à échouer au match
    # exact puis à retomber sur le montant seul. Il sert désormais à
    # identifier le donneur d'ordre.
    'libelle': 'libelle',
    'donneur_ordre': 'libelle',
    'donneur_dordre': 'libelle',
    'emetteur': 'libelle',
    'ice': 'ice',
    'montant': 'montant',
    'amount': 'montant',
    'credit': 'montant',
    'mode': 'mode',
    'type': 'mode',
}

MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024  # 5 Mo

TOLERANCE_CENTIME = Decimal('0.01')

# Statuts de ligne qui EXIGENT une décision humaine — la « file de revue ».
# Aucune de ces lignes n'est jamais affectée automatiquement.
STATUTS_REVUE = ('ambigu', 'client_non_identifie')
# Le seul statut qu'un commit accepte d'écrire.
STATUT_IMPORTABLE = 'a_importer'


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


def _match_facture(ref, montant, company, libelle='', ice=''):
    """AUD121 — rapproche UNE ligne de relevé, ou refuse de trancher.

    Renvoie ``(facture, match_type, statut_match, candidats)`` :
      * ``facture``      — la facture rapprochée, ou None ;
      * ``match_type``   — 'reference' | 'montant_client' | None ;
      * ``statut_match`` — None (rapproché), 'ambigu', 'client_non_identifie'
        ou 'non_trouve' ;
      * ``candidats``    — références des factures candidates (pour la file
        de revue : l'opérateur voit ENTRE QUOI il doit choisir).

    Ordre :
      1. **référence exacte** — le seul match sûr, inchangé ;
      2. **montant + client identifié** (ICE, sinon nom du donneur d'ordre
         dans le libellé) : une seule candidate → rapproché ; plusieurs →
         ``ambigu`` ;
      3. **montant sans client identifié** : plusieurs candidates →
         ``ambigu`` ; une seule → ``client_non_identifie``. JAMAIS
         d'affectation automatique — c'est le fallback montant-seul qui
         créditait la facture d'un autre client, retiré ici.
    """
    from apps.crm.selectors import find_client_by_ice_or_libelle
    from .models import Facture
    OPEN_STATUTS = (Facture.Statut.EMISE.value, Facture.Statut.EN_RETARD.value)
    qs = Facture.objects.filter(company=company, statut__in=OPEN_STATUTS)

    # 1) Référence exacte (insensible à la casse) — match sûr.
    if ref:
        ref_clean = (str(ref) or '').strip()
        hit = qs.filter(reference__iexact=ref_clean).first()
        if hit:
            return hit, 'reference', None, []

    if montant is None:
        return None, None, 'non_trouve', []

    # 2) Client identifiable ? (ICE d'abord, sinon nom dans le libellé.)
    client = find_client_by_ice_or_libelle(company, ice=ice, libelle=libelle)

    scoped = qs.filter(client=client) if client is not None else qs
    candidats = [
        f for f in scoped.prefetch_related('paiements', 'avoirs')
        if abs(f.montant_du - montant) <= TOLERANCE_CENTIME
    ]
    refs = [f.reference for f in candidats]

    if len(candidats) > 1:
        # Plusieurs factures ouvertes partagent ce montant : trancher serait
        # deviner. La ligne part en revue humaine.
        return None, None, 'ambigu', refs
    if len(candidats) == 1:
        if client is not None:
            return candidats[0], 'montant_client', None, refs
        # Une candidate mais AUCUN donneur d'ordre identifié : c'est
        # exactement le cas qui créditait le mauvais client. Revue humaine.
        return None, None, 'client_non_identifie', refs
    return None, None, 'non_trouve', []


def _normaliser_mode(mode_raw):
    """Normalise le libellé de mode du relevé vers un choix ``Paiement.Mode``."""
    mode_map = {
        'virement': 'virement', 'wire': 'virement',
        'cheque': 'cheque', 'chèque': 'cheque',
        'especes': 'especes', 'espèces': 'especes', 'cash': 'especes',
        'carte': 'carte', 'card': 'carte',
        'prelevement': 'prelevement', 'prélèvement': 'prelevement',
    }
    return mode_map.get((mode_raw or 'virement').strip().lower(), 'virement')


def dry_run(file_bytes, filename, company, max_preview=10, user=None):
    """Aperçu + DÉCISIONS jetonnées. Aucune écriture d'argent.

    AUD121 — le dry-run persiste désormais la liste COMPLÈTE des décisions
    de rapprochement (pas seulement l'aperçu tronqué) dans une
    ``ReleveImportSession``, et renvoie son ``token`` : c'est ce jeton, et
    lui seul, que ``commit`` accepte. Un `Paiement` n'est toujours créé
    ici — la seule écriture est la session elle-même.

    Renvoie un dict :
      - ``token``         : jeton à repasser au commit (usage unique)
      - ``columns``       : mapping en-tête → champ reconnu
      - ``unmapped``      : en-têtes non reconnus
      - ``preview``       : jusqu'à max_preview lignes avec statut
      - ``revue``         : la FILE DE REVUE — toutes les lignes ambiguës ou
        sans donneur d'ordre identifié, jamais affectées automatiquement
      - ``total_rows``    : nombre total de lignes dans le fichier
      - ``matched``       : nombre de lignes avec une facture rapprochée
      - ``ambigus``       : nombre de lignes en file de revue
      - ``already_paid``  : nombre de lignes dont la facture est déjà payée
      - ``deja_importe``  : True si ce CONTENU de fichier a déjà été importé
        pour cette société (le commit le refusera)
    """
    from .models import ReleveImportSession

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

    decisions = []
    matched = 0
    already_paid = 0

    for i, raw_row in enumerate(rows):
        mapped = _map_row(raw_row, col_to_field)
        montant = _parse_montant(mapped.get('montant'))
        date = _parse_date(mapped.get('date'))
        ref = (mapped.get('reference') or '').strip()
        libelle = (mapped.get('libelle') or '').strip()
        ice = (mapped.get('ice') or '').strip()

        if montant is None:
            # Ligne sans montant valide — souvent une ligne de total/en-tête.
            decisions.append({
                'ligne': i + 2, 'date': date, 'reference': ref,
                'libelle': libelle, 'montant': None,
                'mode': _normaliser_mode(mapped.get('mode')),
                'statut': 'montant_invalide',
                'facture_id': None, 'facture_reference': None,
                'match_type': None, 'candidats': [],
            })
            continue

        facture, match_type, statut_match, candidats = _match_facture(
            ref, montant, company, libelle=libelle, ice=ice)
        if facture is not None:
            matched += 1
            reste = facture.montant_du
            if reste <= TOLERANCE_CENTIME:
                already_paid += 1
                statut = 'deja_regle'
            elif montant - reste > TOLERANCE_CENTIME:
                statut = 'surpaiement'
            else:
                statut = STATUT_IMPORTABLE
        else:
            statut = statut_match or 'non_trouve'

        decisions.append({
            'ligne': i + 2, 'date': date, 'reference': ref,
            'libelle': libelle, 'montant': str(montant),
            'mode': _normaliser_mode(mapped.get('mode')),
            'statut': statut,
            'facture_id': facture.id if facture else None,
            'facture_reference': facture.reference if facture else None,
            'match_type': match_type, 'candidats': candidats,
        })

    fichier_hash = hashlib.sha256(file_bytes).hexdigest()
    session = ReleveImportSession.objects.create(
        company=company,
        token=secrets.token_urlsafe(32),
        fichier_hash=fichier_hash,
        fichier_nom=(filename or '')[:255],
        decisions=decisions,
        created_by=user,
    )
    revue = [d for d in decisions if d['statut'] in STATUTS_REVUE]

    return {
        'token': session.token,
        'columns': {h: f for h, f in col_to_field.items()},
        'unmapped': unmapped,
        'preview': decisions[:max_preview],
        'revue': revue,
        'total_rows': len(rows),
        'matched': matched,
        'ambigus': len(revue),
        'already_paid': already_paid,
        'deja_importe': ReleveImportSession.objects.filter(
            company=company, fichier_hash=fichier_hash,
            consomme_at__isnull=False).exists(),
    }


def commit(company, user, token, lignes=None):
    """Import effectif — rejoue les DÉCISIONS d'un dry-run jetonné.

    AUD121 — ce service ne parse plus rien et ne matche plus rien : il
    exécute ce que l'opérateur a vu et validé. Il exige donc :
      * un ``token`` de dry-run appartenant à la MÊME société (sinon
        ``ValueError`` → 400 côté vue) ;
      * un jeton NON consommé (usage unique) ;
      * un contenu de fichier jamais importé pour cette société
        (``fichier_hash``) — c'est ce qui referme le double-import.

    ``lignes`` (optionnel) restreint l'import aux numéros de ligne que
    l'opérateur a cochés ; par défaut, toutes les lignes importables. Une
    ligne en file de revue (``ambigu``/``client_non_identifie``) n'est
    JAMAIS écrite, même explicitement demandée.

    Renvoie un dict : {created, skipped, errors, results[{ligne, statut}]}.
    Chaque paiement est créé dans sa propre transaction (pas de rollback global).
    """
    from django.db import transaction as db_transaction
    from django.utils import timezone as dj_timezone
    from .models import Facture, Paiement, ReleveImportSession
    from . import activity

    token = (token or '').strip()
    if not token:
        raise ValueError(
            "Jeton de dry-run requis : lancez d'abord l'aperçu, vérifiez les "
            "lignes, puis validez.")
    session = ReleveImportSession.objects.filter(
        company=company, token=token).first()
    if session is None:
        raise ValueError('Jeton de dry-run inconnu ou expiré.')
    if session.consomme_at is not None:
        raise ValueError('Ce dry-run a déjà été importé.')
    if ReleveImportSession.objects.filter(
            company=company, fichier_hash=session.fichier_hash,
            consomme_at__isnull=False).exists():
        raise ValueError('Ce relevé a déjà été importé (contenu identique).')

    OPEN_STATUTS = (Facture.Statut.EMISE.value, Facture.Statut.EN_RETARD.value)
    demandees = None if lignes is None else {int(x) for x in lignes}

    created = 0
    skipped = 0
    errors = 0
    results = []

    for decision in (session.decisions or []):
        i = int(decision.get('ligne', 0)) - 2
        montant = _parse_montant(decision.get('montant'))
        date_str = decision.get('date')
        ref = (decision.get('reference') or '').strip()
        mode = _normaliser_mode(decision.get('mode'))
        match_type = decision.get('match_type')

        if demandees is not None and decision.get('ligne') not in demandees:
            skipped += 1
            results.append({'ligne': i + 2, 'statut': 'non_selectionnee'})
            continue

        if decision.get('statut') != STATUT_IMPORTABLE or montant is None:
            skipped += 1
            results.append({'ligne': i + 2,
                            'statut': decision.get('statut') or 'non_trouve'})
            continue

        from datetime import date as _date
        try:
            date_obj = _date.fromisoformat(date_str) if date_str else _date.today()
        except (ValueError, TypeError):
            date_obj = _date.today()

        facture = Facture.objects.filter(
            company=company, pk=decision.get('facture_id')).first()
        if facture is None:
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

    # Jeton à usage unique : consommé même si rien n'a été créé (l'opérateur
    # a bien exécuté sa décision). Un ré-import du MÊME contenu sera refusé
    # par la garde de hash en tête de fonction.
    session.consomme_at = dj_timezone.now()
    session.save(update_fields=['consomme_at', 'updated_at'])

    return {
        'token': session.token,
        'created': created, 'skipped': skipped, 'errors': errors,
        'results': results}
