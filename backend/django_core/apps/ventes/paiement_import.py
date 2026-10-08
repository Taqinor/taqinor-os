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
STATUTS_REVUE = ('ambigu', 'client_non_identifie', 'date_invalide')
# AFAC5 — ligne déjà importée par un relevé antérieur (même clé
# d'idempotence) : jamais importable, jamais en revue.
STATUT_DOUBLON = 'doublon_import'
STATUT_DATE_INVALIDE = 'date_invalide'
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
    """Convertit une valeur en str ISO AAAA-MM-JJ, ou None si non reconnue.

    AFAC5 (C-AFAC-016) — une date NON reconnue renvoie désormais ``None``
    (elle renvoyait la chaîne brute, que le commit remplaçait en silence par
    la date du JOUR : un paiement daté d'un jour où il n'a pas eu lieu). La
    ligne part en ``date_invalide`` (file de revue) et n'est jamais écrite.
    Appelants : ``dry_run`` seul (le commit relit l'ISO de la décision)."""
    if v is None:
        return None
    if hasattr(v, 'strftime'):  # datetime/date (openpyxl)
        return v.strftime('%Y-%m-%d')
    s = str(v).strip()
    if not s:
        return None
    # Accepte DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _cle_contenu(decision):
    """AFAC5 — empreinte NORMALISÉE d'une ligne de relevé (sans son rang).

    Ne dépend que du SENS de la ligne — date ISO, montant à 2 décimales,
    référence et libellé normalisés — jamais de la forme du fichier : un
    relevé ré-encodé (CRLF/BOM), ré-exporté au format FR (« 20/06/2026 »,
    « 5 000,00 »), aux colonnes réordonnées ou chevauchant un import
    antérieur donne la MÊME empreinte pour la même opération bancaire."""
    montant = _parse_montant(decision.get('montant'))
    montant_txt = (str(montant.quantize(Decimal('0.01')))
                   if montant is not None else '')
    ref = ' '.join(str(decision.get('reference') or '').split()).upper()
    libelle = ' '.join(str(decision.get('libelle') or '').split()).upper()
    return f"{decision.get('date') or ''}|{montant_txt}|{ref}|{libelle}"


def _cles_idempotence(decisions):
    """AFAC5 — clé d'idempotence PAR LIGNE, alignée sur ``decisions``.

    Clé = ``releve:`` + sha256(empreinte normalisée + rang d'occurrence de
    cette empreinte dans le fichier). Le rang garde deux lignes identiques
    LÉGITIMES d'un même relevé (deux virements du même montant le même jour)
    comme deux paiements, tout en reconnaissant la même ligne réimportée.
    Posée en ``Paiement.idempotency_key`` (contrainte
    ``uniq_paiement_idempotency_par_societe``)."""
    vus = {}
    cles = []
    for decision in decisions:
        contenu = _cle_contenu(decision)
        rang = vus.get(contenu, 0)
        vus[contenu] = rang + 1
        empreinte = hashlib.sha256(
            f'{contenu}|{rang}'.encode('utf-8')).hexdigest()
        cles.append(f'releve:{empreinte}')
    return cles


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


def _marquer_doublons(decisions, company):
    """AFAC5 — passe en ``doublon_import`` toute ligne déjà importée.

    Seules les lignes porteuses d'un montant ET d'une date valides peuvent
    être des doublons (les autres ne sont jamais écrites). La facture
    rapprochée est effacée : la ligne n'est plus importable."""
    from .models import Paiement
    cles = _cles_idempotence(decisions)
    candidates = {
        cle for cle, d in zip(cles, decisions)
        if d.get('statut') not in ('montant_invalide', STATUT_DATE_INVALIDE)}
    if not candidates:
        return
    existantes = set(Paiement.objects.filter(
        company=company, idempotency_key__in=candidates,
    ).values_list('idempotency_key', flat=True))
    for cle, d in zip(cles, decisions):
        if cle in existantes and d.get('statut') not in (
                'montant_invalide', STATUT_DATE_INVALIDE):
            d['statut'] = STATUT_DOUBLON
            d['facture_id'] = None
            d['facture_reference'] = None
            d['match_type'] = None
            d['candidats'] = []


def dry_run(file_bytes, filename, company, max_preview=None, user=None):
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
      - ``preview``       : TOUTES les lignes avec leur statut (AFAC6 —
        plus de troncature à 10 : l'opérateur valide ce qu'il voit ;
        ``max_preview`` reste un plafond optionnel pour un appelant)
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

        if date is None:
            # AFAC5 — date vide ou non reconnue (« 15.06.2026 ») : jamais
            # inventée (plus de repli sur la date du jour au commit). La
            # ligne part en revue humaine.
            decisions.append({
                'ligne': i + 2, 'date': None, 'reference': ref,
                'libelle': libelle, 'montant': str(montant),
                'mode': _normaliser_mode(mapped.get('mode')),
                'statut': STATUT_DATE_INVALIDE,
                'facture_id': None, 'facture_reference': None,
                'match_type': None, 'candidats': [],
            })
            continue

        facture, match_type, statut_match, candidats = _match_facture(
            ref, montant, company, libelle=libelle, ice=ice)
        if facture is not None:
            reste = facture.montant_du
            if reste <= TOLERANCE_CENTIME:
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

    # AFAC5 — idempotence PAR LIGNE : une ligne dont la clé est déjà posée
    # sur un paiement de la société a déjà été importée (relevé ré-encodé,
    # ré-exporté ou chevauchant — que le hash de fichier ne voit pas).
    _marquer_doublons(decisions, company)

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
        'preview': (decisions if max_preview is None
                    else decisions[:max_preview]),
        'revue': revue,
        'total_rows': len(rows),
        'matched': sum(1 for d in decisions if d.get('facture_id')),
        'ambigus': len(revue),
        'already_paid': sum(1 for d in decisions if d.get('statut') == 'deja_regle'),
        'deja_importe': ReleveImportSession.objects.filter(
            company=company, fichier_hash=fichier_hash,
            consomme_at__isnull=False).exists(),
    }


def _appliquer_resolutions(session, company, lignes):
    """AFAC6 — lit ``lignes`` (numéros ou ``{ligne, facture_reference}``).

    Renvoie l'ensemble des numéros de ligne demandés (None = toutes les
    lignes importables). Une forme objet RÉSOUT une ligne en revue
    (``ambigu`` / ``client_non_identifie``) en choisissant UNE facture parmi
    ses ``candidats`` : la décision de la session est réécrite (facture
    choisie, ``match_type: "manuel"``, statut ``a_importer`` — les gardes
    reste/sur-paiement du commit s'appliquent ensuite comme à toute ligne).
    Lève ``ValueError`` (400, message français) pour une forme invalide, une
    ligne inconnue, une ligne non ambiguë sous forme objet ou une facture
    hors candidates — avant toute écriture."""
    from .models import Facture
    if lignes is None:
        return None
    par_ligne = {d.get('ligne'): d for d in (session.decisions or [])}
    demandees = set()
    for element in lignes:
        if isinstance(element, dict):
            try:
                numero = int(element.get('ligne'))
            except (TypeError, ValueError):
                raise ValueError(
                    'Résolution invalide : chaque objet porte un numéro de '
                    '« ligne » et une « facture_reference ».')
            choix = str(element.get('facture_reference') or '').strip()
            decision = par_ligne.get(numero)
            if decision is None:
                raise ValueError(f'Ligne {numero} : absente de ce relevé.')
            if decision.get('statut') not in ('ambigu', 'client_non_identifie'):
                raise ValueError(
                    f'Ligne {numero} : seule une ligne en revue (ambiguë ou '
                    "sans donneur d'ordre identifié) se résout en choisissant "
                    'une facture ; transmettez son numéro seul.')
            candidats = list(decision.get('candidats') or [])
            if choix not in candidats:
                raise ValueError(
                    f'Ligne {numero} : la facture {choix or "(vide)"} ne fait '
                    'pas partie des candidates de cette ligne '
                    f'({", ".join(candidats) or "aucune"}).')
            facture = Facture.objects.filter(
                company=company, reference=choix).first()
            if facture is None:
                raise ValueError(
                    f'Ligne {numero} : facture {choix} introuvable.')
            decision.update({
                'statut': STATUT_IMPORTABLE,
                'facture_id': facture.id,
                'facture_reference': facture.reference,
                'match_type': 'manuel',
            })
            demandees.add(numero)
        else:
            try:
                demandees.add(int(element))
            except (TypeError, ValueError):
                raise ValueError(
                    'lignes doit contenir des numéros de ligne ou des objets '
                    '{ligne, facture_reference}.')
    return demandees


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
    JAMAIS écrite sur son seul numéro : AFAC6 — l'opérateur la RÉSOUT en
    transmettant ``{ligne, facture_reference}`` (une facture parmi ses
    candidates, voir ``_appliquer_resolutions``). Chaque ligne créée est
    nommée dans ``results`` (``facture_reference`` + ``paiement_id``).

    Renvoie un dict : {created, skipped, errors, results[{ligne, statut}]}.
    Chaque paiement est créé dans sa propre transaction (pas de rollback global).
    """
    from django.db import IntegrityError, transaction as db_transaction
    from django.utils import timezone as dj_timezone
    from .models import Facture, Paiement, ReleveImportSession
    from . import activity

    token = (token or '').strip()
    if not token:
        raise ValueError(
            "Jeton de dry-run requis : lancez d'abord l'aperçu, vérifiez les "
            "lignes, puis validez.")
    # AFAC5 — la session est VERROUILLÉE puis CONSOMMÉE en tête, avant toute
    # écriture : deux commits concurrents du même jeton ne peuvent plus
    # passer tous les deux le contrôle « non consommé » puis importer deux
    # fois (le second voit `consomme_at` posé et est refusé).
    with db_transaction.atomic():
        session = ReleveImportSession.objects.select_for_update().filter(
            company=company, token=token).first()
        if session is None:
            raise ValueError('Jeton de dry-run inconnu ou expiré.')
        if session.consomme_at is not None:
            raise ValueError('Ce dry-run a déjà été importé.')
        if ReleveImportSession.objects.filter(
                company=company, fichier_hash=session.fichier_hash,
                consomme_at__isnull=False).exists():
            raise ValueError(
                'Ce relevé a déjà été importé (contenu identique).')
        # AFAC6 — les lignes ambiguës RÉSOLUES par l'opérateur sont
        # validées (refus 400 avant toute écriture, jeton non consommé) puis
        # réécrites dans la session (facture choisie, match « manuel »).
        demandees = _appliquer_resolutions(session, company, lignes)
        session.consomme_at = dj_timezone.now()
        session.save(update_fields=['consomme_at', 'decisions', 'updated_at'])

    cles = _cles_idempotence(session.decisions or [])

    OPEN_STATUTS = (Facture.Statut.EMISE.value, Facture.Statut.EN_RETARD.value)

    created = 0
    skipped = 0
    errors = 0
    results = []

    for decision, cle in zip(session.decisions or [], cles):
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

        # AFAC5 — plus AUCUN repli sur la date du jour : une décision sans
        # date ISO valide n'est jamais écrite (elle est en revue).
        from datetime import date as _date
        try:
            date_obj = _date.fromisoformat(date_str) if date_str else None
        except (ValueError, TypeError):
            date_obj = None
        if date_obj is None:
            skipped += 1
            results.append({'ligne': i + 2, 'statut': STATUT_DATE_INVALIDE})
            continue

        # AFAC5 — idempotence par ligne, re-vérifiée au commit (un autre
        # import a pu passer entre l'aperçu et la validation).
        if Paiement.objects.filter(
                company=company, idempotency_key=cle).exists():
            skipped += 1
            results.append({'ligne': i + 2, 'statut': STATUT_DOUBLON})
            continue

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
                    idempotency_key=cle,
                    created_by=user)
                activity.log_facture_paiement(locked, user, paiement)
                # YLEDG1 — événement documentaire générique (pose du seam
                # pour compta.ecriture_pour_paiement).
                from core.events import paiement_enregistre
                paiement_enregistre.send(
                    sender=Paiement, instance=paiement, company=company)
                locked.refresh_from_db()
                # AUD102 (P8) — l'import de relevé soldait en silence : la
                # bascule passe par LE service unique (donc `facture_payee`,
                # donc lettrage compta, et les relances ré-armées).
                from .domain.encaissements import marquer_facture_soldee
                marquer_facture_soldee(
                    locked, montant=montant, user=user,
                    source='import_releve')
            created += 1
            results.append({
                'ligne': i + 2, 'statut': 'created',
                'facture': facture.reference,
                'facture_reference': facture.reference,
                'paiement_id': paiement.id,
                'montant': str(montant),
                'match_type': match_type})
        except IntegrityError:
            # AFAC5 — course : la même ligne vient d'être importée par un
            # autre commit (contrainte uniq_paiement_idempotency_par_societe).
            skipped += 1
            results.append({'ligne': i + 2, 'statut': STATUT_DOUBLON})
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
        'token': session.token,
        'created': created, 'skipped': skipped, 'errors': errors,
        'results': results}
