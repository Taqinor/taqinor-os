"""Synchronisation des leads avec Odoo — moteur SANS IA (ordre fondateur
2026-09-01, session « erp-crm-odoo-sync »).

Deux directions, exposées par deux commandes de gestion qui restent minces :

  * ``sync_odoo_leads``  — Odoo → ERP : rapatrie tous les leads ``crm.lead``
    via l'API JSON-2, crée les manquants (en réutilisant la commande
    idempotente ``import_odoo_leads``) puis AVANCE les étapes ERP sur le
    pipeline Odoo — jamais en arrière (D-CRX3, 02/09/2026) : une étape Odoo
    en retrait est signalée au rapport, sans aucune écriture.
  * ``push_odoo_stages`` — ERP → Odoo : pousse les étapes ERP vers Odoo.

Règles absolues :
  * CLAUDE.md règle #1 — toute écriture Odoo passe par l'API JSON-2
    (``POST /json/2/<model>/<method>``), JAMAIS de SQL.
  * Règle #2 — les clés d'étape canoniques viennent de STAGES.py ; la table
    intitulé Odoo → clé canonique vit dans ``import_odoo_leads``
    (``_ODOO_STAGE_TO_KEY``) et n'est jamais dupliquée.
  * Le push n'écrit QUE ``stage_id`` sur ``crm.lead`` — jamais de création,
    de suppression ni d'archivage côté Odoo, et seulement quand l'étape
    Odoo actuelle est INCOHÉRENTE au niveau des 6 étapes canoniques (le
    détail fin des colonnes Odoo déjà cohérentes n'est pas écrasé).

Config (.env — clé créée dans Odoo : Préférences ▸ Sécurité du compte ▸
Nouvelle clé API ; durée max 3 mois, valeur affichée UNE seule fois) :
  ODOO_SYNC_URL      l'URL de la base Odoo (https://<base>.odoo.com)
  ODOO_SYNC_API_KEY  la clé API (jamais committée)
  ODOO_SYNC_DB       optionnel (en-tête X-Odoo-Database)

Sans config complète, les commandes n'écrivent RIEN et affichent l'usage —
même contrat « sans fichier → ne rien faire » que ``import_odoo_leads``.
"""
import html
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field

from django.db import transaction

from apps.crm import services, stages
from apps.crm.models import Lead

ODOO_USER_AGENT = 'erp-os-odoo-sync'

# Champs crm.lead rapatriés (le champ `mobile` n'existe plus sur les Odoo
# récents — relevé le 2026-09-01 sur la base du fondateur).
ODOO_LEAD_FIELDS = [
    'id', 'name', 'contact_name', 'partner_name', 'email_from', 'phone',
    'street', 'street2', 'city', 'stage_id', 'active', 'expected_revenue',
    'create_date', 'user_id', 'tag_ids', 'lost_reason_id', 'description',
]

# Emails « bouche-trou » posés par les formulaires Meta — à purger AVANT tout
# rapprochement (243 leads partageaient no-email@example.com : sans purge, le
# rapprochement par email les fusionnerait tous sur une seule fiche).
PLACEHOLDER_EMAILS = {'no-email@example.com'}

# Les « adresses » des leads Meta contiennent en fait les réponses du
# formulaire (fourchette de facture, usage) — jamais dans `adresse`.
_JUNK_STREET_RE = re.compile(
    r'_dh|entre_|moins_|plus_|pour_m|dh$', re.IGNORECASE)

_HTML_TAG_RE = re.compile(r'<[^>]*>')

# « Sociétés » que le connecteur Meta invente sur chaque lead publicitaire —
# ce n'est pas une raison sociale. Comparé en minuscules.
SOCIETES_FICTIVES = {'facebook lead'}


# ── CRX10 — assainissement PARTAGÉ par les deux chemins d'entrée ────────────
# Ces trois règles étaient enfermées dans ``build_rows`` (chemin JSON-2) : un
# export FICHIER des mêmes leads Odoo entrait donc sale — 243 leads fusionnés
# sur le même email bouche-trou, « Facebook Lead » en raison sociale, et les
# réponses du formulaire Meta rangées dans l'adresse postale. Les deux chemins
# appellent désormais les mêmes fonctions.

def email_reel(raw):
    """Email exploitable (minuscule) ou ``None`` — bouche-trous Meta purgés.

    Sans cette purge, le rapprochement par email fusionne TOUS les leads
    partageant ``no-email@example.com`` sur une seule fiche.
    """
    email = (raw or '').strip().lower()
    if not email or email in PLACEHOLDER_EMAILS:
        return None
    return email


def societe_reelle(raw):
    """Raison sociale exploitable ou ``None`` (« Facebook Lead » n'en est pas)."""
    societe = (raw or '').strip()
    if not societe or societe.lower() in SOCIETES_FICTIVES:
        return None
    return societe


def est_reponse_formulaire(street):
    """``street`` Odoo contient-il en fait les réponses d'un formulaire Meta
    (fourchette de facture, usage…) plutôt qu'une adresse postale ?"""
    street = (street or '').strip()
    return bool(street) and bool(_JUNK_STREET_RE.search(street))


# Cible Odoo par défaut pour chaque étape canonique ERP (push ERP → Odoo).
# Noms d'étapes Odoo = données du pipeline réel du fondateur (2026-09-01),
# résolus en ids à l'exécution — jamais d'id codé en dur.
PUSH_STAGE_TARGETS = {
    stages.NEW: 'New',
    stages.CONTACTED: 'Lead Qualified',
    stages.QUOTE_SENT: 'prilimanary quote sent',
    stages.FOLLOW_UP: 'Quote Discussed',
    stages.SIGNED: 'Contract Signed + Deposit',
    stages.COLD: 'Cold Lead',
}


# ── CRX11 — allowlist STRUCTURELLE des écritures Odoo ──────────────────────
# Méthodes de LECTURE de l'API Odoo : toujours autorisées.
_READ_METHODS = frozenset({
    'search_read', 'search', 'search_count', 'read', 'read_group',
    'fields_get', 'name_search', 'name_get', 'default_get',
})

# La SEULE écriture Odoo autorisée dans tout le dépôt : le déplacement
# d'étape de ``push_odoo_stages`` (``stage_id`` seul, à blanc par défaut,
# ``--apply`` explicite). Ajouter une entrée ici est une DÉCISION : elle doit
# être déclarée dans le même commit à ``scripts/check_odoo_writes.py``, qui
# refuse toute écriture non déclarée.
_WRITE_ALLOWED = frozenset({('crm.lead', 'write')})


class OdooSyncError(Exception):
    """Erreur d'appel JSON-2 (transport, auth ou réponse d'erreur Odoo)."""


class OdooConfig:
    """Config lue de l'environnement ; ``incomplete`` si un élément manque."""

    def __init__(self, url=None, api_key=None, db=None):
        self.url = (url if url is not None
                    else os.environ.get('ODOO_SYNC_URL', '')).strip()
        self.api_key = (api_key if api_key is not None
                        else os.environ.get('ODOO_SYNC_API_KEY', '')).strip()
        self.db = (db if db is not None
                   else os.environ.get('ODOO_SYNC_DB', '')).strip()

    @property
    def incomplete(self):
        return not (self.url and self.api_key)


def odoo_call(config, model, method, payload, timeout=120):
    """POST ``/json/2/<model>/<method>`` (API JSON-2 — la SEULE voie d'accès
    à Odoo, CLAUDE.md règle #1). ``payload`` : paramètres NOMMÉS de la
    méthode (+ ``ids``/``context``), conformément à la doc JSON-2.

    CRX11 — GARDE STRUCTURELLE : ce transport est générique (``model`` et
    ``method`` sont des paramètres), donc rien n'empêchait un appelant futur
    d'écrire ce qu'il voulait dans la base Odoo du fondateur. Toute méthode
    hors ``_READ_METHODS`` doit désormais figurer dans ``_WRITE_ALLOWED``,
    qui ne contient QU'UNE entrée : ``crm.lead.write`` (déplacement d'étape
    de ``push_odoo_stages``, à blanc par défaut, ``--apply`` explicite,
    ``stage_id`` seul). Le refus tombe AVANT le moindre octet réseau.
    ``scripts/check_odoo_writes.py`` vérifie la même règle statiquement.
    """
    if method not in _READ_METHODS and (model, method) not in _WRITE_ALLOWED:
        raise OdooSyncError(
            f"Écriture Odoo refusée : {model}.{method} n'est pas une méthode "
            f"de lecture et ne figure pas dans l'allowlist "
            f"{sorted(_WRITE_ALLOWED)}. Toute écriture Odoo doit être "
            f"déclarée ici ET dans scripts/check_odoo_writes.py.")
    url = config.url.rstrip('/') + f'/json/2/{model}/{method}'
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'bearer {config.api_key}',
        'User-Agent': ODOO_USER_AGENT,
    }
    if config.db:
        headers['X-Odoo-Database'] = config.db
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode('utf-8'),
        headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode('utf-8'))
            message = detail.get('message') or detail.get('name') or str(exc)
        except Exception:
            message = str(exc)
        raise OdooSyncError(
            f'Odoo {model}.{method} → HTTP {exc.code} : {message}') from exc
    except urllib.error.URLError as exc:
        raise OdooSyncError(
            f'Odoo injoignable ({url}) : {exc.reason}') from exc


def fetch_odoo_leads(config, batch=500):
    """Rapatrie TOUS les crm.lead (archivés compris) + le nom des tags."""
    leads = []
    offset = 0
    while True:
        page = odoo_call(config, 'crm.lead', 'search_read', {
            'domain': [],
            'fields': ODOO_LEAD_FIELDS,
            'limit': batch,
            'offset': offset,
            'order': 'id',
            'context': {'active_test': False},
        })
        leads.extend(page)
        if len(page) < batch:
            break
        offset += batch
    tags = odoo_call(config, 'crm.tag', 'search_read', {
        'domain': [], 'fields': ['id', 'name']})
    return leads, {t['id']: t['name'] for t in tags}


def _clean_phone(raw):
    """Téléphone plausible ou None. Les saisies aberrantes (0 chiffre, ou
    plus de 20 — ``Lead.telephone``/``phone_normalise`` sont varchar(20) et
    l'insert CASSE au-delà, invisible en dry-run) partent en note."""
    text = (raw or '').strip()
    if not text:
        return None, None
    digits = re.sub(r'[^0-9]', '', text)
    if not digits or len(digits) > 20 or len(text) > 50:
        return None, text
    return text, None


def build_rows(odoo_leads, tag_names):
    """Projette les leads Odoo bruts vers les lignes d'import de l'ERP.

    Reproduit EXACTEMENT les règles de l'opération validée du 2026-09-01 :
    emails bouche-trou purgés, « adresses » du formulaire Meta redirigées en
    note, téléphones aberrants en note, note = trace Odoo complète (étape
    d'origine, date, responsable, tags, motif de perte, revenu attendu).
    L'étape part en clair (nom Odoo) : la table de ``import_odoo_leads``
    fait foi pour la conversion en clé canonique."""
    rows = []
    for lead in odoo_leads:
        stage_odoo = lead['stage_id'][1] if lead.get('stage_id') else ''
        street = (lead.get('street') or '').strip()
        street2 = (lead.get('street2') or '').strip()
        junk_street = est_reponse_formulaire(street)
        tags = [tag_names.get(tid) for tid in (lead.get('tag_ids') or [])]
        tags = [t for t in tags if t]
        telephone, tel_invalide = _clean_phone(lead.get('phone'))

        note_lines = []
        description = _HTML_TAG_RE.sub(' ', str(lead.get('description') or ''))
        # Balises retirées PUIS entités décodées (&nbsp; & co) — le HTML
        # d'Odoo contient les deux.
        description = html.unescape(description)
        description = re.sub(r'\s+', ' ', description).strip()[:2000]
        if description:
            note_lines.append(description)
        if junk_street:
            note_lines.append(
                'Formulaire Meta: ' + street
                + (' | ' + street2 if street2 else ''))
        note_lines.append('Étape Odoo: ' + stage_odoo)
        if lead.get('create_date'):
            note_lines.append('Créé dans Odoo: ' + str(lead['create_date']))
        if lead.get('user_id'):
            note_lines.append('Responsable Odoo: ' + str(lead['user_id'][1]))
        if tags:
            note_lines.append('Tags Odoo: ' + ', '.join(tags))
        if lead.get('lost_reason_id'):
            note_lines.append(
                'Motif de perte Odoo: ' + str(lead['lost_reason_id'][1]))
        if (lead.get('expected_revenue') or 0) > 0:
            note_lines.append(
                'Revenu attendu Odoo: %s DH' % lead['expected_revenue'])
        if not lead.get('active', True):
            note_lines.append('Archivé dans Odoo')
        if tel_invalide:
            note_lines.append('Téléphone Odoo invalide: ' + tel_invalide)

        email = email_reel(lead.get('email_from'))
        societe = societe_reelle(lead.get('partner_name'))
        adresse = None
        if street and not junk_street:
            adresse = street + (', ' + street2 if street2 else '')
        row = {
            'id': lead['id'],
            'nom': ((lead.get('contact_name') or '').strip()
                    or (lead.get('name') or '').strip() or None),
            'societe': societe,
            'email': email,
            'telephone': telephone,
            'adresse': adresse,
            'ville': (lead.get('city') or '').strip()[:120] or None,
            'stage': stage_odoo,
            'note': '\n'.join(note_lines),
        }
        rows.append({k: v for k, v in row.items() if v is not None})
    return rows


@dataclass
class RapportAlignement:
    """Ce que l'alignement Odoo → ERP a fait — et ce qu'il a REFUSÉ de faire.

    ``regressions`` est la liste des leads dont l'étape Odoo est EN RETRAIT
    sur l'étape ERP : rien n'est écrit pour eux (D-CRX3), ils sont signalés
    pour arbitrage humain. Chaque entrée est
    ``(pk, nom, stage ERP, intitulé Odoo brut, clé canonique visée)``.
    """
    moves: Counter = field(default_factory=Counter)
    deja_ok: int = 0
    introuvables: int = 0
    corbeille: int = 0
    inconnus: int = 0
    # Lignes Odoo qui retombent sur une fiche ERP déjà traitée dans la même
    # passe (doublons INTERNES au pipeline Odoo) — la première ligne gagne.
    doublons_odoo: int = 0
    regressions: list = field(default_factory=list)


def align_stages_from_rows(company, rows, apply_changes):
    """Aligne l'étape ERP de chaque lead rapproché sur l'étape Odoo mappée —
    EN AVANT SEULEMENT (D-CRX3, décision fondateur du 02/09/2026).

    Même rapprochement 3 étages que ``import_odoo_leads`` (clé odoo, email,
    téléphone) — indispensable : les leads venus du bridge Meta portent déjà
    une clé externe Meta et ne sont retrouvables QUE par email/téléphone.
    En doublon Odoo interne, la première ligne gagne.

    Trois garanties (CRX8) :

      * **Avance seulement.** Le rang vient de l'ordre canonique de STAGES.py
        (``services._rang_funnel`` — jamais une liste d'étapes en dur ici).
        Une étape Odoo EN RETRAIT sur l'ERP n'écrit RIEN : elle part en ligne
        de rapport (``RapportAlignement.regressions``). Un pipeline Odoo tenu
        à la main ne peut donc plus faire reculer le funnel de l'ERP — y
        compris vers « Froid », qui est classé SOUS « Nouveau ».
      * **Étape Odoo inconnue = lead intouché.** ``_map_stage_connu`` renvoie
        ``None`` au lieu du défaut ``NEW`` ; ce défaut ne survit que pour la
        CRÉATION d'un lead.
      * **Écriture par le chemin canonique.** ``services.avancer_stage_lead_vers``
        écrit, journalise le chatter via la façade ``activity`` ET émet
        ``core.events.lead_stage_changed`` — les playbooks (crm) et les
        séquences (compta) se déclenchent enfin sur un mouvement venu d'Odoo
        (l'ancienne ``LeadActivity`` artisanale était muette). La provenance
        reste tracée par une note « alignement sur le pipeline Odoo ».

    CRX7 — ``_find_existing`` voit aussi les leads SOFT-SUPPRIMÉS (sans quoi
    l'import amont crashait sur la contrainte d'unicité) : un lead en
    corbeille est ici IGNORÉ et compté, jamais déplacé ni restauré."""
    from apps.crm import activity
    from apps.crm.management.commands.import_odoo_leads import (
        _find_existing, _map_stage_connu)

    rapport = RapportAlignement()
    deja_traites = set()
    with transaction.atomic():
        for row in rows:
            ext_id = str(row.get('id') or '').strip()
            if not ext_id:
                continue
            stage_odoo = row.get('stage')
            target = _map_stage_connu(stage_odoo)
            lead, _ambigu = _find_existing(company, ext_id, {
                'email': row.get('email'),
                'telephone': row.get('telephone')})
            if lead is None:
                rapport.introuvables += 1
                continue
            if lead.is_deleted:
                rapport.corbeille += 1
                continue
            if lead.pk in deja_traites:
                # CRX10 — DEUX lignes Odoo pointent la même fiche ERP : la
                # première gagne, mais le silence cachait des doublons INTERNES
                # au pipeline Odoo. Compté et remonté au rapport.
                rapport.doublons_odoo += 1
                continue
            deja_traites.add(lead.pk)
            if target is None:
                # Intitulé Odoo hors table : on ne devine pas, on ne touche pas.
                rapport.inconnus += 1
                continue
            if lead.stage == target:
                rapport.deja_ok += 1
                continue
            if services._rang_funnel(target) <= services._rang_funnel(
                    lead.stage):
                rapport.regressions.append(
                    (lead.pk, lead.nom, lead.stage,
                     str(stage_odoo or ''), target))
                continue
            rapport.moves[(lead.stage, target)] += 1
            if apply_changes:
                # Chemin canonique : écrit, journalise via la façade et émet
                # `lead_stage_changed` (user=None — c'est la machine).
                if services.avancer_stage_lead_vers(lead, None, target):
                    activity.log_bulk_note(
                        lead, None, 'auto — alignement sur le pipeline Odoo')
        if not apply_changes:
            transaction.set_rollback(True)
    return rapport


def compute_push_moves(company, odoo_leads):
    """ERP → Odoo : liste les déplacements d'étape à faire CÔTÉ ODOO.

    Un lead Odoo bouge seulement si son étape actuelle, convertie en clé
    canonique, DIFFÈRE de l'étape ERP du lead rapproché — la colonne cible
    est alors ``PUSH_STAGE_TARGETS[étape ERP]``. Rapprochement : clé odoo,
    puis email normalisé, puis téléphone normalisé (mêmes étages que
    l'import, dans le même ordre)."""
    from apps.crm.management.commands.import_odoo_leads import _map_stage

    par_ext = {}
    par_email = {}
    par_tel = {}
    for lead in Lead.objects.filter(company=company):
        if lead.external_system == 'odoo' and lead.external_id:
            par_ext[str(lead.external_id)] = lead
        email = services.normalize_email(lead.email)
        if email and email not in PLACEHOLDER_EMAILS:
            par_email.setdefault(email, lead)
        tel = services.normalize_phone(lead.telephone)
        if tel:
            par_tel.setdefault(tel, lead)

    moves = {}          # nom d'étape Odoo cible -> [ids crm.lead]
    coherents = 0
    non_rapproches = 0
    for odoo_lead in odoo_leads:
        erp = par_ext.get(str(odoo_lead['id']))
        if erp is None:
            email = services.normalize_email(
                (odoo_lead.get('email_from') or '').strip().lower())
            if email and email not in PLACEHOLDER_EMAILS:
                erp = par_email.get(email)
        if erp is None:
            tel = services.normalize_phone(odoo_lead.get('phone'))
            if tel:
                erp = par_tel.get(tel)
        if erp is None:
            non_rapproches += 1
            continue
        stage_odoo = (odoo_lead['stage_id'][1]
                      if odoo_lead.get('stage_id') else '')
        if _map_stage(stage_odoo) == erp.stage:
            coherents += 1
            continue
        cible = PUSH_STAGE_TARGETS.get(erp.stage)
        if not cible:
            continue
        moves.setdefault(cible, []).append(odoo_lead['id'])
    return moves, coherents, non_rapproches


def push_stage_moves(config, moves):
    """Écrit les déplacements dans Odoo — UNIQUEMENT ``crm.lead.write`` sur
    ``stage_id``, via JSON-2 (règle #1). Un appel par colonne cible."""
    stage_rows = odoo_call(config, 'crm.stage', 'search_read', {
        'domain': [], 'fields': ['id', 'name']})
    par_nom = {s['name']: s['id'] for s in stage_rows}
    manquantes = [nom for nom in moves if nom not in par_nom]
    if manquantes:
        raise OdooSyncError(
            'Étape(s) cible introuvable(s) dans Odoo : %s — étapes '
            'disponibles : %s' % (manquantes, sorted(par_nom)))
    ecrits = 0
    for nom, ids in sorted(moves.items()):
        odoo_call(config, 'crm.lead', 'write', {
            'ids': ids, 'vals': {'stage_id': par_nom[nom]}})
        ecrits += len(ids)
    return ecrits
