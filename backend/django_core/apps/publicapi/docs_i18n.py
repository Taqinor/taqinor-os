"""NTI18N44 — référence + OpenAPI de l'API publique en FR ou EN (métadonnées).

``docs.py`` reste la source de vérité UNIQUE, en français. Ce module n'ajoute
qu'une COUCHE DE TRADUCTION appliquée APRÈS construction, à la demande
(``?lang=en`` sur ``GET /api/public/v1/openapi.json`` et sur la référence
Paramètres → API & Webhooks) :

* elle ne traduit que des TEXTES descriptifs (titres, descriptions, libellés de
  scopes et d'évènements, résumés OpenAPI) — jamais un chemin, un code de scope,
  un nom de champ, un statut, un en-tête, ni aucune logique ;
* elle ne retire, ne renomme et n'ajoute AUCUNE clé : la structure EN est
  identique à la structure FR (un test compare les deux arbres clé par clé) ;
* un texte sans traduction retombe sur le français (jamais une clé perdue ni un
  texte vide) — et un test exige qu'aucune description d'endpoint ne soit
  restée sans traduction, donc un endpoint ajouté sans sa version EN fait
  rougir la CI.

Langue inconnue → français (comportement historique inchangé).
"""
import copy
import re

LANGUE_DEFAUT = 'fr'
LANGUES_DOC = ('fr', 'en')


def langue_doc(valeur):
    """Normalise une valeur ``?lang=`` : ``'en'`` ou, sinon, ``'fr'``."""
    return 'en' if str(valeur or '').strip().lower().startswith('en') else LANGUE_DEFAUT


# ── Textes de tête (clé = chemin pointé dans la référence) ──────────────────
TEXTES_EN = {
    'titre': "Taqinor public API — Reference",
    'introduction': (
        "REST API authenticated by API key and scoped to your company. "
        "Mostly read-only; a write subset exists (see « endpoints_ecriture », "
        "dedicated `*:write` scopes). No purchase price or internal "
        "profitability data is ever returned."
    ),
    'authentification.methode': "API key in the Authorization HTTP header.",
    'authentification.obtention': (
        "Create a key in Settings → API & Webhooks. The full key is shown "
        "only once, at creation."
    ),
    'authentification.note_scope': (
        "Each key is limited to the scopes ticked; calling an endpoint "
        "outside its scope returns 403."
    ),
    'authentification.note_societe': (
        "The company is derived from the key: there is no way to read "
        "another company's data."
    ),
    'authentification.oauth2': (
        "Recommended alternative for an enterprise integration: "
        "`POST /api/public/v1/oauth/token/` (`client_credentials` grant) "
        "exchanges `client_id` + `client_secret`, once, for a SHORT-lived "
        "token, then presented as `Authorization: Bearer <token>`. A "
        "permanent secret no longer travels with every call. The token's "
        "scopes are the client's (or the subset requested via `scope`); "
        "removing a scope from the client takes effect IMMEDIATELY, without "
        "waiting for already-issued tokens to expire."
    ),
    'parametres_communs.pagination': "?page=<n>&page_size=<n> (standard DRF pagination).",
    'parametres_communs.tri': (
        "?ordering=<field> or ?ordering=-<field> (descending). Only the "
        "fields listed per endpoint are allowed; a disallowed field is "
        "ignored."
    ),
    'parametres_communs.filtres': (
        "Equality filter on whitelisted fields (e.g. ?statut=payee). An "
        "unknown parameter returns 400."
    ),
    'parametres_communs.synchro_incrementale': (
        "?updated_since=<ISO-8601> (e.g. 2026-06-30 or 2026-06-30T12:00:00Z) "
        "returns only records modified since that timestamp — ideal for "
        "incremental polling without re-scanning the whole list."
    ),
    'parametres_communs.langue': (
        "?lang=fr|en on `GET /api/public/v1/openapi.json` and on this "
        "reference: endpoint, scope and event descriptions in French "
        "(default) or English. Same structure, same fields, same paths: only "
        "the texts change (returned data is never translated)."
    ),
    'sous_ressources.description': (
        "Read-only sub-resources of an already published object, served "
        "under the read scope of their resource."
    ),
    'endpoints_ecriture.description': (
        "XPLT5 — WRITE endpoints (dedicated scopes `leads:write` / "
        "`activities:write`). Company forced from the key, never from the "
        "body. Optional `Idempotency-Key` header: an identical replay (same "
        "key, same body) returns the stored response without recreating the "
        "object; a different body → 409."
    ),
    'endpoints_bulk.description': (
        "NTAPI14/15/16/43 — BULK jobs (export/import) processed OUTSIDE the "
        "request: the response is an immediate 202 (never an HTTP time-out "
        "even on a very large volume), tracked via `jobs/`. The required "
        "scope depends on the requested entity (same scope as the "
        "synchronous read/write of that resource)."
    ),
    'endpoints_lecture_simple.description': (
        "NTADM42 — simple read endpoints: a SINGLE OBJECT (never a paginated "
        "list), company-scoped. No pagination/sort/filter."
    ),
    'webhooks.description': (
        "Signed HTTP POST notifications to an https URL you provide, "
        "subscribed per event. Configuration in Settings → API & Webhooks."
    ),
    'webhooks.livraison': (
        "Each event carries a stable `event_id` (uuid4) in the body, "
        "identical across all attempts (exponential backoff, up to 8 "
        "retries) — deduplicate on it."
    ),
    'webhooks.securite': (
        "The secret is shown only at creation (or rotation). Internal/"
        "loopback targets and the http scheme are refused."
    ),
    'webhooks.verification_signature.algorithme': (
        "HMAC-SHA256 of `f\"{timestamp}.\".encode() + body` (the raw HTTP "
        "body prefixed by the X-Taqinor-Timestamp header), with the webhook "
        "secret; compare the hexadecimal result to the X-Taqinor-Signature "
        "header (constant-time comparison), and reject a timestamp outside "
        "tolerance (anti-replay)."
    ),
    'webhooks.verification_signature_v2.algorithme': (
        "Recommended (NTAPI9) — the X-Taqinor-Signature-V2 header alone "
        "carries `t=<epoch>,v1=<hex>`: same HMAC computation as the legacy "
        "format, but timestamp + signature in ONE header. Reject a `t` "
        "outside tolerance (default 300 s) — the legacy X-Taqinor-Signature "
        "format is still sent IN PARALLEL, unchanged, for any existing "
        "integration."
    ),
}

# ── Libellés de scopes (clé = code, inchangé) ───────────────────────────────
SCOPES_EN = {
    'read:leads': 'Read leads',
    'read:devis': 'Read quotes',
    'read:factures': 'Read invoices',
    'read:chantiers': 'Read job sites',
    'read:stock': 'Read stock (availability, no costs)',
    'read:licence': 'Read licence status (plan, modules, seats)',
    'read:events': 'Read the event feed (limited to the families already authorised)',
    'read:favoris': "Read a consenting user's pinned favourites (?owner=)",
    'read:vues': "Read team saved views, or a consenting user's (?owner=)",
    'read:calepinages': 'Read roof layouts (no raw geometry or internal cost)',
    'lecture_achats': 'Read purchase requests and price requests (no purchase price)',
    'fiabilite:lecture': 'Read reliability (backups, monthly SLA report, limits & usage)',
    'read:clients': "Read a client's document language (language only, no record)",
    'leads:write': 'Create/update leads',
    'activities:write': 'Create activities (notes) on a lead',
    'devis:write': 'Create a draft quote (never sent/accepted)',
    'tickets:write': 'Create a corrective service ticket',
}

# ── Libellés d'évènements webhook (clé = code, inchangé) ────────────────────
EVENEMENTS_EN = {
    'lead.created': 'New lead',
    'lead.lost': 'Lost lead',
    'lead.stage_changed': 'Lead — stage changed',
    'devis.sent': 'Quote sent',
    'devis.accepted': 'Quote accepted',
    'facture.created': 'Invoice created',
    'facture.paid': 'Invoice paid',
    'paiement.recorded': 'Payment recorded',
    'chantier.completed': 'Job site closed',
    'intervention.completed': 'Intervention completed',
    'ticket.created': 'Service ticket created',
    'ticket.resolved': 'Service ticket resolved',
    'stock.seuil_atteint': 'Stock — threshold reached',
    'livraison.livree': 'Delivery — delivered',
    'plan.changed': 'Licence plan — changed',
    'sieges.quota_atteint': 'Seats — quota reached',
    'saved_view_shared': 'View shared with the team',
    'record_restored': 'Item restored from the recycle bin',
    'calepinage.valide': 'Roof layout — variant selected',
    'calepinage.simule': 'Roof layout — simulation completed',
    'langue_changed': 'Language changed (client or company)',
    'incident_opened': 'Incident — opened',
    'incident_resolved': 'Incident — resolved',
    'maintenance_window_announced': 'Maintenance window — announced',
    'onboarding.item_complete': 'Onboarding — checklist item completed',
}

# ── Descriptions d'endpoints (clé = chemin, inchangé) ───────────────────────
ENDPOINTS_EN = {
    '/api/public/v1/leads/': "CRM leads (sales pipeline).",
    '/api/public/v1/devis/': "Quotes (with lines, selling prices only).",
    '/api/public/v1/factures/': "Invoices (with lines).",
    '/api/public/v1/chantiers/': "Job sites / installations.",
    '/api/public/v1/produits/': (
        "Product availability (SKU/name/brand/category/available quantity). "
        "Never a purchase price or cost."),
    '/api/public/v1/calepinages/': (
        "CAL214 — roof layouts (roof designs): identity, lead/client/quote "
        "link, status, layout fingerprint, power (kWp) and number of modules "
        "ACTUALLY computed, output links. Never the raw geometry "
        "(`roof_layout`, engine planes/rows), never an internal cost."),
    '/api/public/v1/saved-views/': (
        "NTUX33 — saved views (NTUX1): only views already shared with the "
        "team; ?owner=<id> filters among them those of THAT user. A personal "
        "view is never published (AANA38)."),
    '/api/public/v1/favoris/': (
        "NTUX33 — pinned favourites (NTUX12), STRICTLY personal: "
        "?owner=<id> is MANDATORY (400 without it), it is the user's "
        "explicit consent. `libelle` is null if the key lacks the read scope "
        "of the target entity (AANA38)."),
    '/api/public/v1/achats/demandes-achat/': (
        "NTP2P39 — purchase requests (requisitions, FG310): reference, "
        "subject, status, priority, required date, job site/programme and "
        "ESTIMATED amount (order of magnitude of commitment). Lines are not "
        "exposed: their estimated unit price is an internal purchase price."),
    '/api/public/v1/achats/rfq/': (
        "NTP2P39 — price requests (RFQ, FG311): reference, subject, status, "
        "deadline, CONSULTED suppliers (with « has answered ») and the "
        "SELECTED offer by identity (supplier + lead time). Never an offer "
        "amount (internal purchase price), never the consultation token (it "
        "opens the answer page without login)."),
    '/api/public/v1/calepinages/<id>/resultat/': (
        "CALX369 — SIMULATION result of a roof layout: annual production, "
        "specific yield, performance ratio, P50/P75/P90, loss items (label, "
        "percentage, source) and calculation timestamp. Not simulated or "
        "stale simulation (the design changed since) ⇒ quantities null, "
        "never 0, and `motif` says why. The `read:calepinages` scope allows "
        "NEITHER writing NOR launching a simulation: the computation is "
        "still triggered from the workshop. The hourly series is not "
        "published here (volume: 8,760 points per simulated year). Never "
        "the geometry, never a cost."),
    '/api/public/v1/leads-write/': "Creates a lead.",
    '/api/public/v1/leads-write/<id>/': "Updates an existing lead.",
    '/api/public/v1/leads-write/<id>/activites/': "Adds a note (chatter) on a lead.",
    '/api/public/v1/devis-write/': (
        "NTAPI18 — creates a DRAFT quote linked to an existing lead (body: "
        "`lead`, plus `numero`/`montant_ht`/`montant_tva`/`montant_ttc`/"
        "`date` as input aids). The client is resolved server-side from the "
        "lead, without duplicates. No line is created and no downstream "
        "status is touched: the quote stays `brouillon` and the client PDF "
        "is still served by `/proposal`."),
    '/api/public/v1/tickets-write/': (
        "NTAPI18 — opens a corrective service ticket (body: `client`, "
        "`description`, optional `installation`). All linked entities are "
        "bounded to the key's company."),
    '/api/public/v1/exports/': (
        "Starts an asynchronous bulk export (leads/quotes/invoices/job "
        "sites/products, CSV or JSONL). Body: entite, format, filtres (same "
        "filters as the synchronously read resource)."),
    '/api/public/v1/imports/': (
        "Starts an asynchronous bulk import (leads/activities) from a "
        "CSV/JSONL file (multipart, `file` field). Body: entite, mode "
        "(create/upsert), dedup_key (email/telephone) if upsert."),
    '/api/public/v1/jobs/': "Paginated list of the company's bulk jobs.",
    '/api/public/v1/jobs/<id>/': (
        "Bulk job tracking: status, progress %, counters, result/error "
        "links (presigned, short-lived)."),
    '/api/public/v1/jobs/<id>/relancer/': (
        "Resumes a failed job from its persistent cursor — never a "
        "duplicate, never a skip."),
    '/api/public/v1/exports/<entite>.csv': (
        "NTAPI30 — SYNCHRONOUS live CSV pull (leads/quotes/invoices/job "
        "sites/products), usable with Google Sheets/Excel Web =IMPORTDATA(). "
        "Authentication by ?token=<key> (query string — no header possible "
        "on the spreadsheet side), strict read-only scope."),
    '/api/public/v1/events/': (
        "NTAPI17 — event feed consumable by CURSOR "
        "(`?after=<sequence>&limit=<n>`), fed by the same signals as the "
        "webhooks. NTAPI32 — `?type=facture.paid` (several codes separated "
        "by a comma) restricts the feed to those events, for a no-code "
        "trigger subscribed to ONE event; a code unknown to the vocabulary "
        "returns 400, a code not covered by the key's scopes simply stays "
        "absent. PULL counterpart of push: for an integration that cannot "
        "expose a public URL, and as a catch-up net. `read:events` scope to "
        "open the channel; each event stays filtered by the read scope of "
        "ITS family (`lead.*` → `read:leads`, `facture.*` → "
        "`read:factures`…) — the feed is never a way around the read scopes."),
    '/api/public/v1/oauth/token/': (
        "NTAPI19 — exchanges `client_id`/`client_secret` for a SHORT-lived "
        "token (`client_credentials` grant). Body: "
        "`grant_type=client_credentials`, `client_id`, `client_secret`, "
        "optional `scope` (subset). The token is then used as "
        "`Authorization: Bearer <token>` on ALL public endpoints, as an "
        "alternative to `Authorization: Api-Key <key>`. Invalid credentials "
        "→ 401, identical message whatever the reason."),
    '/api/public/v1/licence/statut/': (
        "Company licence status (plan_code, modules_inclus, sieges_max, "
        "sieges_utilises). No internal field (price, history)."),
    '/api/public/v1/clients/{id}/langue/': (
        "NTI18N42 — a client's document language: "
        "``{client_id, langue_document, langue_sortie}``. "
        "``langue_document`` is the preference stored on the record (fr/ar), "
        "``langue_sortie`` the language RESOLVED for its documents (client "
        "preference, else company fallback, else fr — fr/en/ar). No other "
        "field of the client record. Client of another company or unknown "
        "→ 404."),
    '/api/public/v1/fiabilite/sauvegardes/': (
        "Last backup and last restore drill (NTOBS5) — "
        "``{derniere_sauvegarde, dernier_drill, rpo_planifie, "
        "rto_annonce_heures}``, each field ``null`` when the data does not "
        "exist yet. System-wide runs return only date + status: never the "
        "artefact, the storage object key, the size or the internal "
        "manifest."),
    '/api/public/v1/fiabilite/sla/{periode}/': (
        "Monthly SLA report (NTOBS3) for the ``{periode}`` period in "
        "``YYYY-MM`` format — availability, P95 latency, credit due and its "
        "status. Invalid period format → 400; no report for that month → "
        "404 (never an empty object). ``latence_p95_ms`` and "
        "``credit_du_montant`` are ``null`` when the measurement or the "
        "invoiced amount is unknown."),
    '/api/public/v1/fiabilite/usage/': (
        "Limits & usage (NTOBS8) — ``{ressources: [...], genere_le}``. A "
        "resource whose source is unavailable is simply OMITTED, never "
        "filled with an invented value."),
}

# ── Charge utile de webhook : description par code d'évènement ──────────────
CHARGES_UTILES_EN = {
    'calepinage.simule': (
        "A roof-layout simulation has just succeeded and its result is "
        "recorded (never for an « already computed », a refusal or a dry "
        "run). Signed JSON POST (X-Taqinor-Signature-V2 + "
        "X-Taqinor-Timestamp) — no value is carried in the URL. Same read "
        "scope as the resource: `read:calepinages` for the feed. Neither "
        "geometry nor cost."),
}

# ── Champs décrits (clé = (propriétaire, nom)) ──────────────────────────────
CHAMPS_EN = {
    ('/api/public/v1/calepinages/<id>/resultat/', 'calepinage_id'): "Roof layout identifier.",
    ('/api/public/v1/calepinages/<id>/resultat/', 'simule'): (
        "True only if a simulated production is served AND still describes "
        "today's design."),
    ('/api/public/v1/calepinages/<id>/resultat/', 'production_annuelle_kwh'): (
        "Simulated annual energy (median year) — same quantity as `p50_kwh`."),
    ('/api/public/v1/calepinages/<id>/resultat/', 'rendement_specifique_kwh_kwc'): (
        "kWh produced per installed kWp per year."),
    ('/api/public/v1/calepinages/<id>/resultat/', 'ratio_performance'): (
        "Performance ratio (PR), as a fraction (0.80 = 80 %)."),
    ('/api/public/v1/calepinages/<id>/resultat/', 'p50_kwh'): "P50 annual production.",
    ('/api/public/v1/calepinages/<id>/resultat/', 'p75_kwh'): "P75 annual production.",
    ('/api/public/v1/calepinages/<id>/resultat/', 'p90_kwh'): "P90 annual production.",
    ('/api/public/v1/calepinages/<id>/resultat/', 'pertes'): (
        "Loss chain applied: `{code, libelle, pourcentage, source, gain, "
        "motif}` per item; `pourcentage` null for an omitted step (its "
        "`motif` says why). Null if not simulated."),
    ('/api/public/v1/calepinages/<id>/resultat/', 'calcule_le'): (
        "Timestamp (UTC) recorded by the served simulation."),
    ('/api/public/v1/calepinages/<id>/resultat/', 'simulation_perimee'): (
        "True when a simulation exists but the design has changed since: "
        "its quantities are then not published."),
    ('/api/public/v1/calepinages/<id>/resultat/', 'motif'): (
        "Why nothing is published (empty when `simule`)."),
    ('/api/public/v1/calepinages/<id>/resultat/', 'complet'): (
        "False when the physical basis of the losses is not entered: the "
        "production is then an upper bound and `ratio_performance`, "
        "`p75_kwh`, `p90_kwh` are null. Null if not simulated."),
    ('/api/public/v1/calepinages/<id>/resultat/', 'mention_production'): (
        "Mention published with the production (« upper bound — N losses "
        "not entered »), empty otherwise."),
    ('calepinage.simule', 'id'): "Roof layout identifier.",
    ('calepinage.simule', 'titre'): "Roof layout title.",
    ('calepinage.simule', 'statut'): "Roof layout status (unchanged by the simulation).",
    ('calepinage.simule', 'lead_id'): "Linked lead.",
    ('calepinage.simule', 'client_id'): "Linked client.",
    ('calepinage.simule', 'devis_id'): "Linked quote.",
    ('calepinage.simule', 'appel_offre_id'): "Linked tender.",
    ('calepinage.simule', 'layout_hash'): "Fingerprint of the simulated design.",
    ('calepinage.simule', 'version_moteur'): "Roof-layout engine version.",
    ('calepinage.simule', 'kwc'): "Peak power ACTUALLY computed.",
    ('calepinage.simule', 'modules'): "Number of modules ACTUALLY computed.",
    ('calepinage.simule', 'p50_kwh'): "Simulated P50 annual production.",
    ('calepinage.simule', 'performance_ratio'): "Simulated performance ratio, as a fraction.",
}

# ── Chaînes statiques de openapi.py (valeur exacte FR -> EN) ────────────────
OPENAPI_EXACT_EN = {
    'API publique Taqinor': 'Taqinor public API',
    'Quota maximal de la fenêtre courante.': 'Maximum quota of the current window.',
    'Requêtes restantes sur la fenêtre courante.': 'Requests remaining in the current window.',
    'Epoch (secondes) de réinitialisation du quota.': 'Epoch (seconds) at which the quota resets.',
    'Requête invalide (filtre inconnu, validation).': 'Invalid request (unknown filter, validation).',
    'Clé API absente ou invalide.': 'API key missing or invalid.',
    'Scope manquant pour cette clé.': 'Scope missing for this key.',
    'Ressource introuvable pour cette société.': 'Resource not found for this company.',
    "Conflit d'idempotence (corps différent).": 'Idempotency conflict (different body).',
    'Quota dépassé.': 'Quota exceeded.',
    'Numéro de page.': 'Page number.',
    'Taille de page.': 'Page size.',
    'Synchro incrémentale (ISO-8601).': 'Incremental sync (ISO-8601).',
    'Liste paginée.': 'Paginated list.',
    'Objet trouvé.': 'Object found.',
    'Créé/mis à jour.': 'Created/updated.',
    'Identifiant stable de l’évènement (dédup).': 'Stable event identifier (deduplication).',
    'Toute réponse 2xx acquitte la livraison.': 'Any 2xx response acknowledges the delivery.',
    'Format : « Api-Key <votre_cle> ».': 'Format: « Api-Key <your_key> ».',
    ('Un rejeu identique (même clé, même corps) renvoie la réponse '
     'mémorisée sans recréer l’objet.'): (
        'An identical replay (same key, same body) returns the stored '
        'response without recreating the object.'),
    ('Clé API en clair (scope lecture seule) — aucun en-tête possible côté '
     'tableur (=IMPORTDATA()).'): (
        'Plain API key (read-only scope) — no header possible on the '
        'spreadsheet side (=IMPORTDATA()).'),
}
_OPENAPI_MOTIFS_EN = [
    (re.compile(r'^Champs triables : (.*)\.$'), r'Sortable fields: \1.'),
    (re.compile(r'^Filtre par égalité sur « (.*) ».$'), r'Equality filter on « \1 ».'),
    (re.compile(r'^(.*) \(détail\)$'), r'\1 (detail)'),
]


def _texte(table, cle, defaut):
    return table.get(cle, defaut)


def _poser(ref, chemin_pointe, valeur_en):
    """Pose ``valeur_en`` à ``chemin_pointe`` si la clé existe (sinon rien :
    la couche ne crée jamais de clé)."""
    *parents, derniere = chemin_pointe.split('.')
    noeud = ref
    for cle in parents:
        noeud = noeud.get(cle) if isinstance(noeud, dict) else None
        if noeud is None:
            return
    if isinstance(noeud, dict) and derniere in noeud:
        noeud[derniere] = valeur_en


def traduire_reference(ref, langue):
    """Copie de ``ref`` dont les TEXTES sont en ``langue`` (``fr`` : inchangée).

    Même arbre, mêmes clés, mêmes valeurs non textuelles ; un texte sans
    traduction reste en français."""
    if langue_doc(langue) != 'en':
        return ref
    out = copy.deepcopy(ref)
    for chemin, texte in TEXTES_EN.items():
        _poser(out, chemin, texte)
    for scope in out.get('scopes', []):
        scope['libelle'] = _texte(SCOPES_EN, scope['code'], scope['libelle'])
    for endpoint in out.get('endpoints', []):
        endpoint['description'] = _texte(
            ENDPOINTS_EN, endpoint['chemin'], endpoint['description'])
    for groupe in ('endpoints_ecriture', 'endpoints_bulk',
                   'endpoints_lecture_simple', 'sous_ressources'):
        for entree in (out.get(groupe) or {}).get('liste', []):
            entree['description'] = _texte(
                ENDPOINTS_EN, entree['chemin'], entree['description'])
            for champ in entree.get('champs', []):
                champ['description'] = _texte(
                    CHAMPS_EN, (entree['chemin'], champ['nom']),
                    champ['description'])
    webhooks = out.get('webhooks') or {}
    for evenement in webhooks.get('evenements', []):
        evenement['libelle'] = _texte(
            EVENEMENTS_EN, evenement['code'], evenement['libelle'])
    for charge in webhooks.get('charges_utiles', []):
        charge['description'] = _texte(
            CHARGES_UTILES_EN, charge['code'], charge['description'])
        for champ in charge.get('champs', []):
            champ['description'] = _texte(
                CHAMPS_EN, (charge['code'], champ['nom']), champ['description'])
    return out


def _traduire_chaine(texte):
    if texte in OPENAPI_EXACT_EN:
        return OPENAPI_EXACT_EN[texte]
    for motif, remplacement in _OPENAPI_MOTIFS_EN:
        if motif.match(texte):
            return motif.sub(remplacement, texte)
    return texte


def _parcourir(noeud):
    if isinstance(noeud, dict):
        return {cle: _parcourir(valeur) for cle, valeur in noeud.items()}
    if isinstance(noeud, list):
        return [_parcourir(valeur) for valeur in noeud]
    if isinstance(noeud, str):
        return _traduire_chaine(noeud)
    return noeud


def traduire_openapi(schema, langue):
    """Document OpenAPI avec ses chaînes statiques en EN (``fr`` : inchangé).

    Les résumés/descriptions issus de la référence arrivent déjà traduits (le
    document est construit depuis ``public_api_reference(langue)``) ; ce passage
    ne couvre que les chaînes fixes de ``openapi.py``. Seules des VALEURS
    textuelles changent — jamais une clé, un chemin ou un schéma."""
    if langue_doc(langue) != 'en':
        return schema
    return _parcourir(schema)
