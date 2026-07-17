"""ADSENG-ODOO — Normalisation + mise en forme des données Odoo pour le moteur.

Lit Odoo UNIQUEMENT via ``odoo_client`` (JSON-RPC lecture seule) et façonne des
DICTS PURS pour ``odoo_metrics`` (jamais d'objet Odoo ni de modèle exposé).

DÉTECTION D'UNE SIGNATURE (build to reality — voir la tâche) : « signé » = un
``sale.order`` CONFIRMÉ (``state in ('sale','done')``) OU un ``crm.lead`` GAGNÉ
(``probability == 100``, une étape « Won/Gagné », ou ``date_closed`` posé sur un
lead actif). Le MONTANT vient de préférence du ``sale.order`` confirmé
(``amount_total``) ; à défaut (lead gagné sans commande confirmée) on retombe sur
``expected_revenue`` du lead.

TÉLÉPHONE : normalisé via ``apps.crm.selectors.normalize_phone_key`` — la MÊME
normalisation QW10 que ``reconciliation_lead_rows`` (``phone_key``), pour que les
numéros Odoo se rapprochent 1:1 des téléphones des leads Meta capturés par l'ERP
(matching signature ↔ campagne côté ``odoo_metrics``). On ne réinvente JAMAIS la
normalisation.

Sans configuration Odoo, ``OdooClient.from_env()`` renvoie ``None`` et toutes ces
fonctions renvoient vide (no-op propre — jamais un appel réseau ni un 500).
"""
from __future__ import annotations

import re as _re
from decimal import Decimal, InvalidOperation

from .odoo_client import OdooClient

# États d'un ``sale.order`` qui comptent comme SIGNÉ (devis confirmé en commande).
SIGNED_ORDER_STATES = ('sale', 'done')

# Fragments (minuscule, sans accent) qui désignent un lead GAGNÉ dans les
# libellés d'étape EXTERNES d'Odoo — RIEN à voir avec les étapes canoniques de
# STAGES.py (règle #2) : Odoo a son propre pipeline (New → … → Won). Utilisés
# seulement en repli de ``probability``/``date_closed`` pour détecter une
# signature côté Odoo. Nommé sans « STAGE » pour ne pas être confondu avec une
# liste d'étapes ERP.
_WON_ODOO_LABEL_FRAGMENTS = ('won', 'gagn')


def _m2o_id(value):
    """Id d'un champ Odoo many2one ``[id, label]`` (ou ``False``), sinon None."""
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return None


def _m2o_label(value):
    """Libellé d'un many2one ``[id, label]`` (ou ``False``), sinon ''."""
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return value[1] or ''
    return ''


def _amount(value):
    """Montant MAD en ``Decimal`` (0 si vide/illisible — jamais d'exception)."""
    if value in (None, False, ''):
        return Decimal('0')
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _stage_is_won(stage_value):
    """L'étape (``[id, label]``) est-elle une étape « gagné » ?"""
    label = _m2o_label(stage_value).lower()
    return any(frag in label for frag in _WON_ODOO_LABEL_FRAGMENTS)


def is_won_lead(lead):
    """Un ``crm.lead`` Odoo est-il GAGNÉ (signé) ? Trois signaux (l'un suffit) :
    ``probability == 100``, une étape « Won/Gagné », ou ``date_closed`` posé sur
    un lead ACTIF (``active`` non-faux)."""
    if lead.get('probability') == 100:
        return True
    if _stage_is_won(lead.get('stage_id')):
        return True
    if lead.get('date_closed') and lead.get('active', True):
        return True
    return False


def _resolve_client(client):
    """Client injecté (tests) ou construit depuis l'env ; None si non configuré."""
    return client if client is not None else OdooClient.from_env()


def signed_deals(since=None, client=None):
    """Liste des DEALS SIGNÉS Odoo, normalisée pour l'attribution.

    Renvoie une liste de dicts ::

        {'phone_norm': str,      # clé QW10 (matchable aux leads Meta de l'ERP)
         'amount_mad': Decimal,  # amount_total (sale.order) ou expected_revenue
         'date': str|None,       # date_order / date_closed
         'source_name': str,     # nom du lead (encode souvent la campagne) / cmde
         'origin': 'sale_order'|'won_lead',
         'lead_id': int|None}    # id crm.lead d'origine si connu

    Le MONTANT vient de préférence du ``sale.order`` confirmé ; un lead gagné SANS
    commande confirmée est ajouté en repli (montant = ``expected_revenue``).

    UNE SIGNATURE = UN CLIENT (dédoublonnage, calibré sur les données réelles du
    fondateur — 9 « deals » bruts pour 6 clients signés réels) :
      1. commandes DUPLIQUÉES (même partner + même numéro, ex. S00158 saisi deux
         fois) → une seule, la plus récente ;
      2. commande NON attribuable (aucun lead lié, aucun téléphone résolvable)
         alors que des leads gagnés existent → facturation d'un client déjà
         compté côté leads, pas une signature de plus ;
      3. un lead gagné déjà représenté (``opportunity_id``, même ``partner_id``
         OU même téléphone normalisé) n'est pas recompté.

    ``since`` (date/datetime/str) borne la lecture. Sans config Odoo → ``[]``.
    """
    from apps.crm.selectors import normalize_phone_key

    client = _resolve_client(client)
    if client is None:
        return []

    leads = client.read_leads(since)
    lead_by_id = {lead['id']: lead for lead in leads if lead.get('id')}
    won_lead_ids = {lid for lid, lead in lead_by_id.items()
                    if is_won_lead(lead)}

    orders = client.read_sale_orders(since)
    confirmed = [o for o in orders if o.get('state') in SIGNED_ORDER_STATES]
    # DÉDOUBLONNAGE 1 — enregistrements de commande DUPLIQUÉS : même
    # ``(partner, name)`` = le même document saisi deux fois (observé en réel :
    # S00158 en double chez le fondateur → 2 « signatures » pour 1 client). On
    # garde la plus récente (``date_order``).
    uniq = {}
    for order in confirmed:
        key = (_m2o_id(order.get('partner_id')),
               (order.get('name') or '').strip())
        prev = uniq.get(key)
        if prev is None or ((order.get('date_order') or '')
                            > (prev.get('date_order') or '')):
            uniq[key] = order
    confirmed = sorted(uniq.values(), key=lambda o: o.get('id') or 0)
    order_partner_ids = {_m2o_id(o.get('partner_id')) for o in confirmed}
    order_partner_ids.discard(None)

    # Résoudre en UN seul appel les téléphones partenaires des commandes qui n'ont
    # pas de lead lié porteur d'un téléphone (le lead reste la meilleure source).
    partner_ids_needed = []
    for order in confirmed:
        opp = _m2o_id(order.get('opportunity_id'))
        lead = lead_by_id.get(opp) if opp else None
        if lead and (lead.get('phone') or lead.get('mobile')):
            continue
        pid = _m2o_id(order.get('partner_id'))
        if pid:
            partner_ids_needed.append(pid)
    partner_map = client.read_partners(partner_ids_needed)

    deals = []
    covered_lead_ids = set()
    seen_phones = set()

    for order in confirmed:
        opp = _m2o_id(order.get('opportunity_id'))
        lead = lead_by_id.get(opp) if opp else None
        source_name = order.get('name') or ''
        phone_raw = ''
        if lead is not None:
            phone_raw = lead.get('phone') or lead.get('mobile') or ''
            # Le nom du lead encode souvent la campagne/formulaire — plus utile
            # comme libellé de traçabilité que le simple numéro de commande.
            source_name = lead.get('name') or source_name
            if opp in won_lead_ids:
                covered_lead_ids.add(opp)
        if not phone_raw:
            partner = partner_map.get(_m2o_id(order.get('partner_id'))) or {}
            phone_raw = partner.get('phone') or partner.get('mobile') or ''
            if not source_name:
                source_name = _m2o_label(order.get('partner_id'))
        phone_norm = normalize_phone_key(phone_raw)
        # DÉDOUBLONNAGE 2 — commande NON attribuable (aucun lead lié, aucun
        # téléphone résolvable) alors que des leads gagnés existent : vérifié en
        # réel chez le fondateur, c'est la facturation d'un client DÉJÀ compté
        # côté leads gagnés (partner sans téléphone, ``opportunity_id`` vide).
        # La compter en plus DOUBLE le client. Sans aucun lead gagné, elle reste
        # comptée (rien contre quoi dédoublonner).
        if lead is None and not phone_norm and won_lead_ids:
            continue
        if phone_norm:
            seen_phones.add(phone_norm)
        deals.append({
            'phone_norm': phone_norm,
            'amount_mad': _amount(order.get('amount_total')),
            'date': order.get('date_order') or order.get('create_date') or None,
            'source_name': source_name,
            'origin': 'sale_order',
            'lead_id': opp or None,
        })

    # Repli : leads GAGNÉS sans commande confirmée (ni via opportunity_id ni via
    # le même client) → montant = expected_revenue, téléphone du lead.
    # DÉDOUBLONNAGE 3 — un même TÉLÉPHONE = un même client : un lead gagné dont
    # le téléphone est déjà porté par un deal (commande ou autre lead gagné)
    # n'est pas recompté.
    for lid in sorted(won_lead_ids):
        if lid in covered_lead_ids:
            continue
        lead = lead_by_id[lid]
        if _m2o_id(lead.get('partner_id')) in order_partner_ids:
            continue  # même client déjà couvert par une commande confirmée
        phone_raw = lead.get('phone') or lead.get('mobile') or ''
        phone_norm = normalize_phone_key(phone_raw)
        if phone_norm and phone_norm in seen_phones:
            continue  # même téléphone = même client, déjà compté
        if phone_norm:
            seen_phones.add(phone_norm)
        deals.append({
            'phone_norm': phone_norm,
            'amount_mad': _amount(lead.get('expected_revenue')),
            'date': lead.get('date_closed') or lead.get('create_date') or None,
            'source_name': lead.get('name') or '',
            'origin': 'won_lead',
            'lead_id': lid,
        })
    return deals


def signed_count(since=None, client=None):
    """Nombre de deals signés Odoo (``len(signed_deals)``). 0 sans config."""
    return len(signed_deals(since=since, client=client))


def lead_stage_counts(client=None):
    """Répartition des ``crm.lead`` Odoo par étape (libellé → compte). Utile au
    diagnostic. ``{}`` sans config Odoo."""
    client = _resolve_client(client)
    if client is None:
        return {}
    counts = {}
    for lead in client.read_leads():
        label = _m2o_label(lead.get('stage_id')) or '(sans étape)'
        counts[label] = counts.get(label, 0) + 1
    return counts


# ── ADSDEEP21 — Parser des noms de leads Odoo (attribution ESTIMÉE) ──────────
# Les noms de leads Odoo encodent souvent le formulaire/la campagne/la date, p.
# ex. « DAZZLEMEDAI-TAQINOR FORM-26/03/2026 ». Pour les deals SANS match
# téléphone (les seuls exacts), on en tire une SUGGESTION d'attribution —
# TOUJOURS étiquetée « estimation », JAMAIS fondue dans les chiffres exacts.
_DATE_RE = _re.compile(r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b')


def parse_odoo_lead_name(name):
    """Extrait ``{source, form_hint, campaign_hint, date, raw}`` d'un nom de lead
    Odoo encodé, ou ``None`` si le nom ne porte aucun indice exploitable.

    Heuristique tolérante (jamais d'erreur) : segments séparés par ``-``, date au
    format ``jj/mm/aaaa`` isolée, segment contenant « FORM » retenu comme
    ``form_hint``. Le premier segment alphanumérique fait office de ``source``
    (agence/canal), et le ``campaign_hint`` = concat des segments non-date
    (signature stable pour regrouper des deals estimés d'une même origine)."""
    if not name or not str(name).strip():
        return None
    raw = str(name).strip()
    date = None
    m = _DATE_RE.search(raw)
    if m:
        date = m.group(1)
    segments = [s.strip() for s in raw.split('-') if s.strip()]
    non_date_segments = [s for s in segments if not _DATE_RE.fullmatch(s)]
    form_hint = ''
    for seg in non_date_segments:
        if 'FORM' in seg.upper():
            form_hint = seg
            break
    source = non_date_segments[0] if non_date_segments else ''
    campaign_hint = ' '.join(non_date_segments)
    if not (source or form_hint or date):
        return None
    return {
        'source': source,
        'form_hint': form_hint,
        'campaign_hint': campaign_hint,
        'date': date,
        'raw': raw,
    }


def estimated_attribution_from_names(deals, *, matched_phone_keys=None):
    """ADSDEEP21 — Suggestion d'attribution par NOM pour les deals SANS match
    téléphone exact.

    ``matched_phone_keys`` = ensemble des clés téléphone déjà attribuées de façon
    EXACTE (par ``odoo_metrics``). Chaque deal dont le téléphone n'y figure pas
    (ou est vide) voit son ``source_name`` parsé ; les deals sont regroupés par
    ``campaign_hint``. Renvoie ::

        {'estimations': [{campaign_hint, form_hint, date, count, deal_ids,
                          attribution_type: 'estimation'}, ...],
         'unparseable': int}

    Le champ ``attribution_type`` vaut TOUJOURS ``'estimation'`` : ces chiffres ne
    doivent JAMAIS être fondus avec l'attribution exacte (deux colonnes distinctes
    côté UI). Ne lève jamais."""
    matched = set(matched_phone_keys or ())
    groups = {}
    unparseable = 0
    for deal in deals or []:
        phone = deal.get('phone_norm') or ''
        if phone and phone in matched:
            continue  # déjà attribué de façon EXACTE — jamais ré-estimé
        parsed = parse_odoo_lead_name(deal.get('source_name'))
        if parsed is None:
            unparseable += 1
            continue
        key = parsed['campaign_hint']
        bucket = groups.setdefault(key, {
            'campaign_hint': parsed['campaign_hint'],
            'form_hint': parsed['form_hint'],
            'date': parsed['date'],
            'count': 0,
            'deal_ids': [],
            'attribution_type': 'estimation',
        })
        bucket['count'] += 1
        if deal.get('lead_id') is not None:
            bucket['deal_ids'].append(deal['lead_id'])
    return {
        'estimations': [groups[k] for k in sorted(groups)],
        'unparseable': unparseable,
    }
