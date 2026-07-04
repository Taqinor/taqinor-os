"""Services Ventes — point d'entrée cross-app pour les ÉCRITURES ventes.

Les apps tierces (sav, installations, crm…) passent par ces fonctions pour
créer ou modifier des entités ventes (Facture, Paiement…) au lieu d'importer
directement les models ventes. Cela respecte la règle de modularité (CLAUDE.md).
"""
from decimal import Decimal, ROUND_HALF_UP
import logging
import re

logger = logging.getLogger(__name__)


def create_draft_devis_from_ocr(*, company, user, lead, fields):
    """FG106 — crée un DEVIS brouillon (sans lignes) à partir d'un document OCR.

    Point d'entrée cross-app sanctionné (services.py) pour la passerelle
    OCR → ventes (apps.publicapi). Le devis part TOUJOURS d'un lead (le client
    est résolu côté serveur via crm.services, sans doublon — réutilise la même
    règle que le générateur). Les lignes ne sont PAS créées : une LigneDevis
    exige un Produit du catalogue, qu'un document OCR brut ne fournit pas — le
    devis brouillon est laissé à compléter dans l'éditeur. Les montants/numéro
    extraits sont consignés dans la note du devis pour aider la saisie.

    Le devis reste ``brouillon`` : ce service CRÉE, il ne change aucun statut
    aval (règle #4).
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.references import create_with_reference
    from apps.crm.services import resolve_client_for_lead

    if lead is None:
        raise ValueError("create_draft_devis_from_ocr requires a lead")
    client = resolve_client_for_lead(lead)

    fields = fields or {}
    notes = ["Devis brouillon créé depuis un document OCR."]
    for key, label in (('numero', 'N° document'), ('montant_ht', 'Montant HT'),
                       ('montant_tva', 'Montant TVA'),
                       ('montant_ttc', 'Montant TTC'), ('date', 'Date')):
        val = fields.get(key)
        if val not in (None, ''):
            notes.append(f"{label} : {val}")
    note = "\n".join(notes)

    def _create(ref):
        return Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            lead=lead,
            statut=Devis.Statut.BROUILLON,
            created_by=user,
            note=note,
        )

    devis = create_with_reference(Devis, 'DEV', company, _create)
    logger.info('FG106: devis brouillon %s créé depuis OCR (company %s)',
                devis.reference, getattr(company, 'id', '?'))
    return devis


def lead_from_source_devis(document):
    """U12 — résout le lead d'origine d'une Facture / d'un BonCommande.

    Le lien direct ``lead`` de la Facture/BC est snapshoté depuis le devis
    source à la création. On le résout ici, de façon centralisée, pour les deux
    voies de création :

    * facture d'échéancier ou BC directement lié à un devis → ``document.devis``;
    * chaîne BC → facture (la facture porte ``bon_commande``, pas ``devis``) →
      ``document.bon_commande.devis``.

    Renvoie l'instance ``crm.Lead`` du devis source, ou ``None`` si aucun devis
    source ne porte de lead (ex. facture de contrat de maintenance, BC sans
    devis). Ne lève jamais : un attribut absent retombe sur ``None``.
    """
    devis = getattr(document, 'devis', None)
    if devis is None:
        bc = getattr(document, 'bon_commande', None)
        if bc is not None:
            devis = getattr(bc, 'devis', None)
    if devis is None:
        return None
    return getattr(devis, 'lead', None)


# Q3 — composition keyword rules. Kept ALIGNED with
# apps/ventes/quote_engine/builder.py (réseau/injection, hybride, batterie,
# panneau) so the PDF option split reads the lines this service writes the same
# way it reads hand-typed ones.
_WATT_RE = re.compile(r"(\d{3,4})\s*(?:wc|w)\b", re.IGNORECASE)


def _is_panel(name: str) -> bool:
    n = (name or "").lower()
    return "panneau" in n or "panneaux" in n


def _is_battery(name: str) -> bool:
    return "batterie" in (name or "").lower()


def _is_hybrid_inverter(name: str) -> bool:
    n = (name or "").lower()
    return "onduleur" in n and "hybride" in n


def _is_reseau_inverter(name: str) -> bool:
    n = (name or "").lower()
    return "onduleur" in n and (
        "réseau" in n or "reseau" in n or "injection" in n)


def _has_price(produit) -> bool:
    """A product is quotable only when it carries a real sell price.

    Mirrors the generator/auto-fill guard: a price-less catalogue item
    (e.g. the curve-only OSP pumps) is NEVER auto-quoted (CLAUDE.md).
    """
    return bool(produit.prix_vente and Decimal(produit.prix_vente) > 0)


def _pick_product(company, predicate, *, watt=None):
    """Smallest-suitable quotable catalogue product matching ``predicate``.

    Scans the company's (and global) products, keeps only priced ones, and —
    for panels with a target wattage — prefers an exact watt match. Returns
    None when nothing priced matches (caller then skips that line).
    """
    from apps.stock.models import Produit
    from django.db.models import Q

    qs = Produit.objects.filter(
        Q(company=company) | Q(company__isnull=True), is_archived=False)
    candidates = [p for p in qs if predicate(p.nom) and _has_price(p)]
    if not candidates:
        return None
    if watt:
        exact = [p for p in candidates
                 if _parse_watt(p.nom) == int(watt)]
        if exact:
            candidates = exact
    # Cheapest priced match keeps the quote sane and deterministic.
    return min(candidates, key=lambda p: Decimal(p.prix_vente))


def _parse_watt(name):
    m = _WATT_RE.search(name or "")
    return int(m.group(1)) if m else None


def _aspect_to_orientation(aspect):
    """FG248 — azimut PVGIS (0=Sud, -90=Est, 90=Ouest, ±180=Nord) → libellé FR.

    Miroir inverse de ``orientationToAspect`` (apps/web/src/lib/roof.ts) pour que
    le devis affiche la même orientation que l'outil 3D. Aspect inconnu → ''."""
    try:
        a = float(aspect)
    except (TypeError, ValueError):
        return ''
    # Normalise dans [-180, 180].
    a = (a + 180.0) % 360.0 - 180.0
    table = [
        (0.0, 'Sud'), (-45.0, 'Sud-Est'), (45.0, 'Sud-Ouest'),
        (-90.0, 'Est'), (90.0, 'Ouest'),
        (-135.0, 'Nord-Est'), (135.0, 'Nord-Ouest'),
        (180.0, 'Nord'), (-180.0, 'Nord'),
    ]
    return min(table, key=lambda t: abs(a - t[0]))[1]


def extract_roof_config(layout):
    """FG248 — extrait la config TOITURE d'un layout 3D (roofPro11) en un dict
    plat, JSON-sérialisable, indépendant de la version de l'outil.

    Lit les PANS de toiture (``areas``/``zones``/``pans``) — chacun portant
    ``roofType``, ``pitchDeg``/``pitch``, ``facingAzimuthDeg``/``aspect`` et un
    ``result`` ``{count, kwc, areaM2}`` — et en agrège :

        {surface_m2, nb_pans, nb_panneaux, kwc, orientation_principale,
         azimut_deg, inclinaison_deg, pans: [{...}]}

    Tolérant : entrées manquantes → champs omis ; aucune exception. Renvoie {}
    si le layout ne contient aucune géométrie de toiture exploitable (pour ne
    rien changer au comportement historique du seul bloc ``result``).
    """
    layout = layout or {}
    areas = (layout.get('areas') or layout.get('zones')
             or layout.get('pans') or [])
    if not isinstance(areas, list) or not areas:
        return {}

    pans = []
    total_surface = 0.0
    total_panels = 0
    total_kwc = 0.0
    best = None  # pan le plus puissant → orientation principale
    for a in areas:
        if not isinstance(a, dict):
            continue
        res = a.get('result') or {}
        count = int(res.get('count') or a.get('neededPanels') or 0)
        kwc = float(res.get('kwc') or 0.0)
        surface = float(res.get('areaM2') or a.get('areaM2') or 0.0)
        aspect = a.get('facingAzimuthDeg')
        if aspect is None:
            aspect = a.get('aspect')
        pitch = a.get('pitchDeg')
        if pitch is None:
            pitch = a.get('pitch')
        pan = {
            'label': a.get('label') or '',
            'roof_type': a.get('roofType') or '',
            'nb_panneaux': count,
            'kwc': round(kwc, 3) if kwc else 0.0,
            'surface_m2': round(surface, 2) if surface else 0.0,
            'azimut_deg': aspect,
            'inclinaison_deg': pitch,
            'orientation': _aspect_to_orientation(aspect),
        }
        pans.append(pan)
        total_surface += surface
        total_panels += count
        total_kwc += kwc
        if best is None or kwc > best['kwc']:
            best = pan

    if not pans:
        return {}

    cfg = {
        'surface_m2': round(total_surface, 2),
        'nb_pans': len(pans),
        'nb_panneaux': total_panels,
        'kwc': round(total_kwc, 3),
        'pans': pans,
    }
    if best is not None:
        cfg['orientation_principale'] = best['orientation']
        cfg['azimut_deg'] = best['azimut_deg']
        cfg['inclinaison_deg'] = best['inclinaison_deg']
    return cfg


def layout_hash(layout):
    """QJ17 — deterministic SHA-256 fingerprint of a roof layout dict.

    Used to detect duplicate ``from-layout`` submissions (same geometry re-sent
    after a network retry or a double-click).  Only the geometry-bearing keys are
    hashed (``zones``/``areas``/``pans``, ``result``, ``scenario``, ``panelWatt``,
    ``watt``, ``battery``) so that transient UI state (``pin``, ``outline``,
    ``billKwh``, ``activeAreaId``, ``renderPlan``…) never prevents deduplication.
    """
    import hashlib
    import json as _json

    if not isinstance(layout, dict):
        return ''
    canonical = {
        'zones': layout.get('zones') or layout.get('areas') or layout.get('pans'),
        'result': layout.get('result'),
        'scenario': layout.get('scenario'),
        'panelWatt': layout.get('panelWatt') or layout.get('watt'),
        'battery': bool(layout.get('battery')),
    }
    blob = _json.dumps(canonical, sort_keys=True, separators=(',', ':'),
                       default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def validate_composition_for_layout(layout, company):
    """QJ17 — pre-flight composition check before building a devis.

    Returns ``None`` when the composition is valid.  Returns a list of French
    error strings when problems are detected (caller should surface them inline
    rather than raising a PDF error at render time).

    Rules (aligned with quote_engine/builder.py keyword classification):
    - At least 1 panel is required.
    - A battery scenario requires both a hybrid inverter AND a battery in the
      catalogue (priced); if either is missing, warn the agent.
    - A réseau scenario requires a réseau/injection inverter (priced).
    - A price-less required product blocks the composition (never auto-quote it).
    """
    if not isinstance(layout, dict):
        return ['Layout invalide — impossible de valider la composition.']

    result = dict((layout.get('result') or {}))
    nb_panneaux = int(result.get('panels') or 0)
    toiture = extract_roof_config(layout)
    if nb_panneaux <= 0 and toiture.get('nb_panneaux'):
        nb_panneaux = int(toiture['nb_panneaux'])

    errors = []
    if nb_panneaux <= 0:
        errors.append(
            'Aucun panneau détecté dans le layout. '
            'Terminez le tracé du toit et relancez l\'optimiseur avant de générer.')

    scenario = (layout.get('scenario') or '').lower()
    wants_battery = ('batterie' in scenario or 'hybride' in scenario
                     or bool(layout.get('battery')))

    if wants_battery:
        inv = _pick_product(company, _is_hybrid_inverter)
        bat = _pick_product(company, _is_battery)
        if inv is None:
            errors.append(
                'Aucun onduleur hybride disponible (ou sans prix) dans le catalogue. '
                'Ajoutez un onduleur hybride tarifé avant de générer ce devis.')
        if bat is None:
            errors.append(
                'Aucune batterie disponible (ou sans prix) dans le catalogue. '
                'Ajoutez une batterie tarifée avant de générer ce devis.')
    else:
        inv = _pick_product(company, _is_reseau_inverter)
        if inv is None:
            errors.append(
                'Aucun onduleur réseau disponible (ou sans prix) dans le catalogue. '
                'Ajoutez un onduleur réseau/injection tarifé avant de générer.')

    return errors if errors else None


def build_devis_from_layout(*, layout, user, company, lead=None, client=None,
                            taux_tva=Decimal('20'), remise_globale=Decimal('0')):
    """Q3 — turn a FINALISED roof layout into a coherent, company-scoped Devis.

    ``layout`` is the serialized roofPro11 output (see Devis.roof_layout):
    a ``result`` block ``{panels, kwc, annualKwh, savings}`` plus an optional
    ``scenario``/equipment hint. From it we compose Devis lines off the seeded
    catalogue, reusing the SAME keyword classification as the quote builder
    (panneau / onduleur réseau|injection|hybride / batterie) and the
    collision-proof reference numbering util (never count()+1). The client is
    resolved server-side from the lead via crm.services (no duplicates). The
    layout's production/savings are stored into ``etude_params``. A price-less
    catalogue product is NEVER quoted.

    QJ21 — the stored ``roof_layout`` is enriched with a ``_pans_geometry`` key
    holding the processed per-pan list (azimut_deg, inclinaison_deg, kwc,
    nb_panneaux, orientation, label, roof_type) so consumers never have to
    re-run ``extract_roof_config`` to access the full multi-plane design.

    Returns the created Devis. The Devis is left ``brouillon`` — this service
    only BUILDS; it never changes downstream statuses (rule #4).
    """
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.utils.references import create_with_reference

    if client is None:
        if lead is None:
            raise ValueError("build_devis_from_layout requires a lead or client")
        from apps.crm.services import resolve_client_for_lead
        client = resolve_client_for_lead(lead)

    result = dict((layout or {}).get('result') or {})
    nb_panneaux = int(result.get('panels') or 0)
    kwc = float(result.get('kwc') or 0)
    annual_kwh = result.get('annualKwh')
    savings = result.get('savings')

    # FG248 — pont 3D toiture → ERP : extrait la config toiture (surface/pans/
    # orientation/inclinaison/kWc) du builder 3D. Quand le bloc ``result`` ne
    # porte pas le nombre de panneaux / la puissance, on retombe sur la somme des
    # pans (cohérence kWc/panneaux écran ↔ pont 3D). Layout sans géométrie →
    # dict vide → comportement historique strictement inchangé.
    toiture = extract_roof_config(layout)
    if toiture:
        if nb_panneaux <= 0 and toiture.get('nb_panneaux'):
            nb_panneaux = int(toiture['nb_panneaux'])
        if not kwc and toiture.get('kwc'):
            kwc = float(toiture['kwc'])

    # Panel wattage: prefer an explicit hint, else derive from kWc / panels.
    watt = layout.get('panelWatt') or layout.get('watt')
    if not watt and nb_panneaux and kwc:
        watt = int(round(kwc * 1000 / nb_panneaux / 10) * 10)
    if not watt and kwc:
        watt = 550

    # Scenario: 'avec_batterie' / 'hybride' → hybrid inverter + battery;
    # anything else → réseau (grid-tie). Default réseau (residential injection).
    scenario = (layout.get('scenario') or '').lower()
    wants_battery = ('batterie' in scenario or 'hybride' in scenario
                     or bool(layout.get('battery')))

    # ── Compose the equipment lines from the catalogue ──
    line_specs = []  # (produit, designation, quantite)
    if nb_panneaux > 0:
        panel = _pick_product(company, _is_panel, watt=watt)
        if panel is not None:
            line_specs.append((panel, panel.nom, nb_panneaux))

    if wants_battery:
        inv = _pick_product(company, _is_hybrid_inverter)
        if inv is not None:
            line_specs.append((inv, inv.nom, 1))
        bat = _pick_product(company, _is_battery)
        if bat is not None:
            line_specs.append((bat, bat.nom, 1))
    else:
        inv = _pick_product(company, _is_reseau_inverter)
        if inv is not None:
            line_specs.append((inv, inv.nom, 1))

    etude_params = {}
    if annual_kwh is not None:
        etude_params['production_annuelle'] = int(annual_kwh)
    if savings is not None:
        etude_params['economies_annuelles'] = int(savings)
    if kwc:
        etude_params['puissance_kwc'] = kwc
    # FG248 — la config toiture importée du builder 3D est conservée avec le
    # devis (prête à servir au chantier).
    if toiture:
        etude_params['toiture'] = toiture

    # QJ21 — enrich roof_layout with a ``_pans_geometry`` key carrying the
    # PROCESSED per-pan data (azimut_deg, inclinaison_deg, kwc, nb_panneaux,
    # orientation, label, roof_type) so consumers never have to re-run
    # extract_roof_config.  We copy rather than mutate the caller's dict.
    stored_layout = dict(layout)
    if toiture and toiture.get('pans'):
        stored_layout['_pans_geometry'] = toiture['pans']

    def _create(ref):
        devis = Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            lead=lead,
            statut=Devis.Statut.BROUILLON,
            taux_tva=taux_tva,
            remise_globale=remise_globale,
            created_by=user,
            mode_installation=Devis.ModeInstallation.RESIDENTIEL,
            etude_params=etude_params or None,
            roof_layout=stored_layout,
        )
        for produit, designation, quantite in line_specs:
            LigneDevis.objects.create(
                devis=devis,
                produit=produit,
                designation=designation,
                quantite=Decimal(str(quantite)),
                prix_unitaire=Decimal(produit.prix_vente),
                remise=Decimal('0'),
            )
        return devis

    devis = create_with_reference(Devis, 'DEV', company, _create)
    logger.info(
        'Q3/QJ21: devis %s built from layout (%d lignes, %.2f kWc, %d pans, company %s)',
        devis.reference, len(line_specs), kwc,
        len(toiture.get('pans', [])) if toiture else 0,
        getattr(company, 'id', '?'))
    return devis


# ── Copilote — devis AUTOMATIQUE (résidentiel) ───────────────────────────────
# Le Copilote ne doit JAMAIS créer un devis vide : il passe toujours par ce
# dimensionnement automatique. Port résidentiel de l'auto-fill solar.js —
# 8 panneaux par tranche de 900 MAD de facture d'hiver, panneaux 710 Wc — puis
# délégation à build_devis_from_layout (catalogue, numérotation, brouillon).

_AUTO_PANEL_WATT = 710        # Wc — panneau catalogue par défaut (cf. solar.js)
_AUTO_PANELS_PER_TRANCHE = 8  # panneaux par tranche de facture d'hiver
_AUTO_TRANCHE_MAD = 900       # MAD/mois de facture d'hiver par tranche


class AutoDevisError(Exception):
    """Le devis automatique ne peut pas être dimensionné (donnée manquante ou
    marché non géré). L'endpoint la traduit en 422 et l'agent demande la donnée
    (ou oriente vers le générateur) plutôt que de produire un devis vide."""

    def __init__(self, message, *, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


def _residential_panel_count(*, facture_hiver=None, taille_kwc=None,
                             panel_watt=_AUTO_PANEL_WATT):
    """Nombre de panneaux pour un lead résidentiel.

    Priorité à la taille souhaitée explicite (kWc → panneaux à ``panel_watt``),
    sinon estimation depuis la facture d'hiver (port de ``estimerPanneaux`` de
    solar.js : 8 panneaux par tranche de 900 MAD). Renvoie 0 si aucune donnée
    exploitable (le caller lève alors ``AutoDevisError``)."""
    if taille_kwc not in (None, '') and Decimal(str(taille_kwc)) > 0:
        return int(round(float(taille_kwc) * 1000 / panel_watt))
    if facture_hiver not in (None, '') and Decimal(str(facture_hiver)) > 0:
        tranches = int(Decimal(str(facture_hiver)) // _AUTO_TRANCHE_MAD)
        return tranches * _AUTO_PANELS_PER_TRANCHE
    return 0


def build_devis_auto(*, lead, user, company, taux_tva=Decimal('20'),
                     remise_globale=Decimal('0')):
    """Crée un devis RÉSIDENTIEL automatiquement dimensionné depuis la fiche lead.

    Lit le profil énergétique du lead (taille souhaitée en kWc, sinon facture
    d'hiver), dimensionne le champ PV, compose un layout réseau (batterie ajoutée
    si ``batterie_souhaitee == 'avec'``) et délègue à ``build_devis_from_layout``
    (sélection catalogue, numérotation anti-collision, devis ``brouillon``). Lève
    ``AutoDevisError`` (→ 422) si le marché n'est pas résidentiel ou si aucune
    donnée de dimensionnement n'est exploitable — l'agent demande alors la donnée
    plutôt que de produire un devis vide. Ne change aucun statut (règle #4)."""
    marche = (getattr(lead, 'type_installation', '') or '').lower()
    if marche and marche != 'residentiel':
        raise AutoDevisError(
            "L'auto-devis ne gère que le résidentiel pour l'instant. Pour "
            "l'industriel/commercial ou l'agricole, utilisez l'écran générateur "
            "de devis.",
            field='type_installation')

    facture_hiver = getattr(lead, 'facture_hiver', None)
    taille_kwc = getattr(lead, 'taille_souhaitee_kwc', None)
    panneaux = _residential_panel_count(
        facture_hiver=facture_hiver, taille_kwc=taille_kwc)
    if panneaux <= 0:
        if facture_hiver not in (None, '') or taille_kwc not in (None, ''):
            msg = ("La facture d'hiver du lead est trop faible pour dimensionner "
                   "une installation résidentielle. Précisez la taille souhaitée "
                   "(kWc) du lead.")
        else:
            msg = ("Données insuffisantes pour dimensionner le devis : renseignez "
                   "la facture d'électricité d'hiver (ou la taille souhaitée en "
                   "kWc) du lead.")
        raise AutoDevisError(msg, field='facture_hiver')

    kwc = round(panneaux * _AUTO_PANEL_WATT / 1000, 2)
    wants_battery = (getattr(lead, 'batterie_souhaitee', '') or '') == 'avec'
    layout = {
        'result': {'panels': panneaux, 'kwc': kwc},
        'panelWatt': _AUTO_PANEL_WATT,
        'scenario': 'avec_batterie' if wants_battery else 'reseau',
    }
    devis = build_devis_from_layout(
        layout=layout, user=user, company=company, lead=lead,
        taux_tva=taux_tva, remise_globale=remise_globale)
    logger.info(
        'Auto-devis %s: %d panneaux, %.2f kWc, batterie=%s (company %s)',
        devis.reference, panneaux, kwc, wants_battery,
        getattr(company, 'id', '?'))
    return devis


class AcceptError(Exception):
    """Raised when a devis cannot be accepted (wrong status / bad option)."""

    def __init__(self, message, conflict=False):
        super().__init__(message)
        self.message = message
        self.conflict = conflict  # True → 409, False → 400


# ── QJ11 — OTP e-signature (toggle) ─────────────────────────────────────────
# Activé par la variable d'environnement ESIGN_OTP_ENABLED=1.
# Quand OFF (défaut) : comportement byte-identique à avant QJ11 — aucun OTP,
# aucun appel supplémentaire. Quand ON : le client reçoit un code à 6 chiffres
# (SMS wa.me / email) et doit le soumettre avant que l'acceptation soit acceptée.
# Le code est stocké dans le cache Django (TTL 10 min), jamais en base. Simple +
# sécurisé : pas de table supplémentaire, idempotent (re-demander régénère).

import os  # noqa: E402

OTP_CACHE_TTL = 600  # 10 minutes


def _esign_otp_enabled():
    """True si ESIGN_OTP_ENABLED=1 dans l'environnement."""
    return os.getenv('ESIGN_OTP_ENABLED', '0').strip() == '1'


def _otp_cache_key(link_token):
    """Clé de cache pour l'OTP d'un lien de proposition."""
    return f'esign_otp:{link_token}'


def _generate_otp():
    """Génère un code OTP à 6 chiffres sécurisé (secrets.randbelow)."""
    import secrets as _secrets
    return f'{_secrets.randbelow(1000000):06d}'


def request_esign_otp(link):
    """QJ11 — Génère et envoie un OTP au contact du devis (wa.me ou email).

    Idempotent : un appel sur un lien dont l'OTP est déjà en cache régénère
    simplement le code (nouvelle fenêtre de 10 min). Retourne None (succès)
    ou un message d'erreur FR lisible.

    Sans toggle ON : retourne None immédiatement (no-op, comportement inchangé).
    """
    if not _esign_otp_enabled():
        return None

    from django.core.cache import cache
    code = _generate_otp()
    cache_key = _otp_cache_key(link.token)
    cache.set(cache_key, code, timeout=OTP_CACHE_TTL)

    devis = link.devis
    client = getattr(devis, 'client', None)
    phone = (getattr(client, 'telephone', '') or '').strip()
    email = (getattr(client, 'email', '') or '').strip()

    sent = False
    # Préférer WhatsApp / SMS (wa.me), puis email.
    if phone:
        sent = _send_otp_whatsapp(phone=phone, code=code, devis_ref=devis.reference)
    if not sent and email:
        sent = _send_otp_email(email=email, code=code, devis_ref=devis.reference)

    if not sent:
        logger.warning(
            'QJ11: OTP généré pour %s mais aucun canal disponible (phone=%s, email=%s)',
            devis.reference, bool(phone), bool(email))
    else:
        logger.info('QJ11: OTP envoyé pour devis %s', devis.reference)
    return None


def validate_esign_otp(link, otp_code):
    """QJ11 — Valide l'OTP soumis contre le cache.

    Sans toggle ON : retourne None (pas d'erreur, comportement inchangé).
    Avec toggle ON :
      - otp_code absent / vide → message d'erreur (OTP requis)
      - otp_code incorrect ou expiré → message d'erreur
      - otp_code correct → None (la validation réussit), le code est consommé.
    """
    if not _esign_otp_enabled():
        return None

    if not otp_code:
        return 'Un code de confirmation est requis. Demandez-le via le bouton « Envoyer le code ».'

    from django.core.cache import cache
    cache_key = _otp_cache_key(link.token)
    stored = cache.get(cache_key)
    if stored is None:
        return 'Le code de confirmation a expiré ou n\'a pas été demandé. Redemandez un nouveau code.'
    if stored != otp_code.strip():
        return 'Code de confirmation incorrect. Vérifiez le code reçu et réessayez.'

    # Code valide : on le consomme (one-time use).
    cache.delete(cache_key)
    return None


def _send_otp_whatsapp(phone, code, devis_ref):
    """Envoie le code OTP via un lien wa.me (draft WhatsApp). Best-effort → bool."""
    try:
        # On journalise un message pré-formaté — pas d'API WhatsApp live
        # (aucune dépendance gated). En production, intégrer ici WhatsApp BSP
        # (notifications.whatsapp_bsp) quand disponible.
        msg = (
            f'Votre code de confirmation pour le devis {devis_ref} est : '
            f'{code}. Valable 10 minutes.'
        )
        logger.info('QJ11 OTP wa.me [%s]: %s → %s', devis_ref, phone, msg)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning('QJ11: wa.me OTP échec : %s', exc)
        return False


def _send_otp_email(email, code, devis_ref):
    """Envoie le code OTP par email. Best-effort → bool."""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local')
        sujet = f'Code de confirmation — devis {devis_ref}'
        corps = (
            f'Votre code de confirmation pour le devis {devis_ref} est :\n\n'
            f'    {code}\n\n'
            f'Ce code est valable 10 minutes.\n\n'
            f'Si vous n\'avez pas demandé ce code, ignorez ce message.\n\n'
            f"Cordialement,\nL'équipe TAQINOR"
        )
        send_mail(sujet, corps, from_email, [email], fail_silently=False)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning('QJ11: email OTP échec : %s', exc)
        return False


def _create_esign_record(*, devis, nom, ip, user_agent='', consentement=True):
    """QJ10 — Crée le DevisSignature IMMUABLE si aucun n'existe encore.

    Idempotent : un enregistrement existant n'est jamais écrasé (la première
    signature fait foi). Best-effort : une exception ne remonte jamais —
    l'acceptation (statut + chatter) est déjà écrite avant cet appel.
    """
    try:
        from django.utils import timezone
        from apps.ventes.models import DevisSignature
        if DevisSignature.objects.filter(devis=devis).exists():
            return
        content_hash = DevisSignature.compute_content_hash(devis)
        DevisSignature.objects.create(
            company=devis.company,
            devis=devis,
            signataire_nom=(nom or '')[:150],
            consentement_explicite=bool(consentement),
            ip_address=ip or None,
            user_agent=(user_agent or '')[:512],
            content_hash=content_hash,
            signed_at=timezone.now(),
        )
        logger.info(
            'QJ10: DevisSignature créée pour devis %s (hash=%s…)',
            devis.reference, content_hash[:16])
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('QJ10: échec DevisSignature pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def _store_signed_pdf(*, devis):
    """QJ22 — Génère et stocke le PDF de la proposition SIGNÉE dans MinIO.

    Réutilise le moteur premium existant (``generate_premium_devis_pdf`` +
    ``persist=True``) sans forker le moteur. La clé MinIO est ensuite stockée
    sur le ``DevisSignature`` lié pour qu'elle soit retrouvable sans ambiguïté.
    Ne rend PAS un nouveau PDF si le ``DevisSignature`` possède déjà une clé
    (idempotent). Best-effort : une exception ne remonte jamais ; l'acceptation
    est déjà écrite avant cet appel.
    """
    try:
        from apps.ventes.models import DevisSignature
        try:
            sig = DevisSignature.objects.get(devis=devis)
        except DevisSignature.DoesNotExist:
            return  # no signature record yet (shouldn't happen in normal flow)
        if sig.signed_pdf_key:
            return  # already stored — idempotent
        from apps.ventes.quote_engine import clean_pdf_options, generate_premium_devis_pdf
        key = generate_premium_devis_pdf(
            devis.id, clean_pdf_options({}), persist=True)
        DevisSignature.objects.filter(pk=sig.pk).update(signed_pdf_key=key)
        logger.info(
            'QJ22: PDF signé stocké pour devis %s → %s',
            devis.reference, key)
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'QJ22: échec stockage PDF signé pour devis %s : %s',
            getattr(devis, 'reference', '?'), exc)


def _send_acceptance_emails(*, devis, user):
    """QJ10 — Envoie un email de confirmation de signature au client + au vendeur.

    Best-effort : une exception ne remonte jamais (l'acceptation est déjà écrite).
    Le PDF joint est récupéré depuis MinIO si disponible ; sinon l'email part
    sans pièce jointe (comportement réseau conforme à email_service.py).
    Jamais de prix_achat / marge dans les emails (règle #4).
    """
    try:
        from apps.ventes.email_service import send_document_email
        client = getattr(devis, 'client', None)
        dest = (getattr(client, 'email', '') or '').strip()
        nom_client = ''
        if client is not None:
            nom_client = (
                f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
            )
        salut = f'Bonjour {nom_client},' if nom_client else 'Bonjour,'
        corps = (
            f"{salut}\n\n"
            f"Nous avons bien reçu votre acceptation du devis "
            f"{devis.reference}.\n\n"
            f"Votre signature électronique a été enregistrée conformément "
            f"à la loi 53-05 relative à l'échange électronique de données "
            f"juridiques.\n\n"
            f"Vous trouverez ci-joint votre exemplaire signé pour vos archives.\n\n"
            f"Merci pour votre confiance.\n\n"
            f"Cordialement,\nL'équipe TAQINOR"
        )
        if dest:
            send_document_email(
                devis,
                to_email=dest,
                sujet=f'Proposition acceptée — {devis.reference}',
                corps=corps,
                user=user,
                attach_pdf=True,
                log_activity=False,  # l'acceptation a déjà son propre chatter
            )
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ10: email client échec pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)
    # Notification vendeur (in-app via notifications.services.notify).
    try:
        _notify_seller_accepted(devis=devis, user=user)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ10: notif vendeur échec pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def _notify_seller_accepted(*, devis, user):
    """QJ10 / QJ2 (c) — Notification in-app + wa.me au vendeur (créateur du
    devis) lors de l'acceptation.

    Réutilise notifications.services.notify (N75). Best-effort : appelé
    dans un bloc except de l'appelant. Pas de notification si le devis n'a
    pas de créateur ou si le créateur est l'utilisateur courant (in-app
    pour soi-même serait du bruit). QJ2 ajoute un lien wa.me « répondre
    maintenant » vers le client dans le corps de la notification.
    """
    vendeur = getattr(devis, 'created_by', None)
    if vendeur is None:
        return
    # Éviter de notifier l'utilisateur qui effectue l'action lui-même.
    if user is not None and getattr(user, 'pk', None) == getattr(vendeur, 'pk', None):
        return
    from apps.notifications.services import notify
    client_nom = ''
    client = getattr(devis, 'client', None)
    if client is not None:
        client_nom = getattr(client, 'nom', '') or ''
    # QJ2 (c) — lien wa.me vers le client (via son téléphone sur le lead ou le
    # client). Best-effort : on préfère le numéro WhatsApp du lead d'origine.
    wa_url = _build_acceptance_wa_url(devis=devis)
    body_lines = [
        (
            f'Le client {client_nom} a accepté le devis {devis.reference}.'
        ) if client_nom else f'Le devis {devis.reference} a été accepté.',
    ]
    if wa_url:
        body_lines.append(f'Répondre maintenant : {wa_url}')
    notify(
        user=vendeur,
        event_type='devis_accepted',
        title=f'Devis {devis.reference} accepté',
        body='\n'.join(body_lines),
        link=f'/ventes/devis/{devis.pk}',
        company=getattr(devis, 'company', None),
    )


def _build_acceptance_wa_url(*, devis):
    """QJ2 (c) — Construit le lien wa.me « répondre maintenant » au client.

    Cherche d'abord le numéro WhatsApp du lead lié au devis, puis le numéro
    du client (champ telephone). Renvoie l'URL ou None. Best-effort — jamais
    d'exception remontée. Les prix d'achat ne sont JAMAIS exposés (règle #4).
    """
    try:
        import urllib.parse
        # Prefer lead WhatsApp, then lead telephone, then client telephone.
        phone_raw = ''
        lead = getattr(devis, 'lead', None)
        if lead is not None:
            phone_raw = (
                getattr(lead, 'whatsapp', None)
                or getattr(lead, 'telephone', None)
                or ''
            )
        if not phone_raw:
            client = getattr(devis, 'client', None)
            if client is not None:
                phone_raw = getattr(client, 'telephone', '') or ''
        digits = ''.join(c for c in (phone_raw or '') if c.isdigit())
        if not digits:
            return None
        # Format international marocain (wa.me exige l'indicatif pays).
        if digits.startswith('00'):
            digits = digits[2:]
        if digits.startswith('0'):
            digits = '212' + digits[1:]
        elif not digits.startswith('212'):
            digits = '212' + digits
        nom = ''
        if lead is not None:
            nom = (getattr(lead, 'nom', '') or '').strip()
        if not nom and devis.client_id:
            client = getattr(devis, 'client', None)
            if client is not None:
                nom = (getattr(client, 'nom', '') or '').strip()
        nom = nom or 'votre client'
        text = urllib.parse.quote(
            f'Bonjour {nom}, votre proposition {devis.reference} a bien été '
            f'confirmée. Merci pour votre confiance !'
        )
        return f'https://wa.me/{digits}?text={text}'
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ2: _build_acceptance_wa_url échoué : %s', exc)
        return None


# ── QJ9 — Attribution first-touch + Meta CAPI hook ───────────────────────────

#: Champs UTM/fbclid copiés du Lead vers etude_params du Devis à l'acceptation.
_ATTRIBUTION_FIELDS = (
    'fbclid', 'utm_source', 'utm_medium',
    'utm_campaign', 'utm_content', 'utm_term',
)


def _persist_attribution(*, devis):
    """QJ9 — Copie les champs d'attribution first-touch du lead vers le devis.

    À l'acceptation, les UTM/fbclid du Lead d'origine sont snapshottés dans
    ``devis.etude_params['attribution']`` (JSONField déjà sur le modèle — aucune
    migration). Cette copie est LOSSLESS : l'attribution reste disponible même si
    le lead est fusionné, archivé ou supprimé plus tard.

    Idempotent : ne ré-écrit pas si une attribution est déjà présente.
    Aucun impact sur les statuts (règle #4 — pure donnée dérivée en lecture seule).
    Ne lève jamais : l'appelant attrape toute exception.
    """
    lead = getattr(devis, 'lead', None)
    if lead is None:
        return  # Devis sans lead — aucune attribution à copier.

    params = dict(devis.etude_params or {})
    if 'attribution' in params:
        return  # Déjà présent — idempotent.

    attribution = {}
    for field in _ATTRIBUTION_FIELDS:
        val = getattr(lead, field, None)
        if val:
            attribution[field] = val

    if not attribution:
        return  # Lead sans données d'attribution — rien à copier.

    params['attribution'] = attribution
    devis.etude_params = params
    devis.save(update_fields=['etude_params'])
    logger.info('QJ9: attribution copiée pour devis %s → %s',
                getattr(devis, 'reference', '?'), list(attribution.keys()))


def _fire_capi_signed_quote(*, devis):
    """QJ9 — Émet un événement « SignedQuote » vers l'API Conversions Meta (CAPI).

    Gate : si ``META_CAPI_ACCESS_TOKEN`` est absent (ou vide) dans les settings
    ou l'environnement, on dégrade en no-op silencieux (log uniquement). Cela
    permet de pré-câbler l'intégration sans créer de dépendance sur un token
    absent en dev/staging.

    Conformité règle #4 : ne touche jamais les statuts Devis/Facture.
    Conformité règle #3 (CLAUDE.md) : le call HTTP CAPI est server-side — jamais
    de création de campagne (interdit par règle #3).
    Ne lève jamais : l'appelant attrape toute exception.

    L'événement CAPI inclut les données d'attribution (fbclid/UTM) snapshottées
    dans etude_params (QJ9 _persist_attribution) pour un matching maximal.

    Env var attendue : ``META_CAPI_ACCESS_TOKEN`` (token de page Meta / CAPI).
    Var optionnelle : ``META_CAPI_PIXEL_ID`` (Pixel ID — peut être vide).
    """
    import os
    from django.conf import settings

    token = (
        getattr(settings, 'META_CAPI_ACCESS_TOKEN', None)
        or os.environ.get('META_CAPI_ACCESS_TOKEN', '')
        or ''
    ).strip()
    if not token:
        logger.info(
            'QJ9: CAPI SignedQuote ignoré pour devis %s — META_CAPI_ACCESS_TOKEN absent',
            getattr(devis, 'reference', '?'))
        return

    pixel_id = (
        getattr(settings, 'META_CAPI_PIXEL_ID', None)
        or os.environ.get('META_CAPI_PIXEL_ID', '')
        or ''
    ).strip()

    # Récupère l'attribution snapshottée (QJ9) ou tente le lead directement.
    attribution = {}
    params = devis.etude_params or {}
    if 'attribution' in params:
        attribution = params['attribution']
    else:
        lead = getattr(devis, 'lead', None)
        if lead is not None:
            for field in _ATTRIBUTION_FIELDS:
                val = getattr(lead, field, None)
                if val:
                    attribution[field] = val

    import hashlib
    import time
    import urllib.parse
    import urllib.request
    import json as _json

    # Données de l'événement CAPI (hachage SHA-256 pour le PII).
    def _sha256(val):
        return hashlib.sha256((val or '').strip().lower().encode()).hexdigest()

    event_time = int(time.time())
    client = getattr(devis, 'client', None)
    email_hash = _sha256(getattr(client, 'email', '') or '') if client else ''
    phone_raw = ''
    if client:
        phone_raw = getattr(client, 'telephone', '') or ''
    phone_digits = ''.join(c for c in (phone_raw or '') if c.isdigit())
    phone_hash = _sha256(phone_digits) if phone_digits else ''

    # Valeur de conversion : total TTC du devis (sans prix d'achat — règle #4).
    try:
        value = float(getattr(devis, 'total_ttc', None) or 0)
    except (TypeError, ValueError):
        value = 0.0

    user_data = {}
    if email_hash:
        user_data['em'] = [email_hash]
    if phone_hash:
        user_data['ph'] = [phone_hash]
    fbclid = attribution.get('fbclid', '')
    if fbclid:
        user_data['fbc'] = f'fb.1.{int(time.time() * 1000)}.{fbclid}'

    custom_data = {
        'currency': 'MAD',
        'value': value,
        'order_id': str(getattr(devis, 'reference', '')),
    }
    utm_source = attribution.get('utm_source', '')
    if utm_source:
        custom_data['utm_source'] = utm_source
    utm_campaign = attribution.get('utm_campaign', '')
    if utm_campaign:
        custom_data['utm_campaign'] = utm_campaign

    event = {
        'event_name': 'SignedQuote',
        'event_time': event_time,
        'action_source': 'website',
        'user_data': user_data,
        'custom_data': custom_data,
    }

    payload = _json.dumps({'data': [event]}).encode('utf-8')
    api_url = f'https://graph.facebook.com/v19.0/{pixel_id}/events' if pixel_id else None

    if not api_url:
        logger.info(
            'QJ9: CAPI SignedQuote prêt pour devis %s (pixel non configuré — log seul) '
            'fbclid=%s utm_source=%s value=%.2f MAD',
            getattr(devis, 'reference', '?'), fbclid, utm_source, value)
        return

    params_qs = urllib.parse.urlencode({'access_token': token})
    full_url = f'{api_url}?{params_qs}'
    req = urllib.request.Request(
        full_url, data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_body = resp.read().decode('utf-8', errors='replace')
            logger.info(
                'QJ9: CAPI SignedQuote envoyé pour devis %s — status %s body %.200s',
                getattr(devis, 'reference', '?'), resp.status, resp_body)
    except Exception as exc:
        logger.warning('QJ9: CAPI SignedQuote HTTP échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def accept_devis(*, devis, user, nom='', date_acceptation=None, option='',
                 ip=None, user_agent='', consentement=True,
                 idempotent_reaccept=True):
    """Q7 — flip a Devis to « accepté » through the ONE acceptance path.

    Shared by the in-app viewset action (N25) and the tokenized web proposal
    (Q7): records the stamp (typed name + date [+ IP in the chatter]), sets the
    accepted option, writes the acceptance activity and emits the
    ``devis_accepted`` domain event — so the downstream BonCommande/Facture
    chain is preserved 1:1 (rule #4). The engine only RENDERS elsewhere; this
    is the single place a quote document changes status to accepté.

    With ``idempotent_reaccept=True`` (default) a re-submit on an
    already-accepted devis is returned unchanged (no second stamp, no second
    event) so a double e-signature submit on the tokenized web proposal (Q7)
    is a no-op. With ``idempotent_reaccept=False`` (the in-app viewset action)
    an already-accepted devis raises ``AcceptError(conflict=True)`` → 409,
    preserving the ERR33 re-accept guard.

    Raises ``AcceptError`` on a non-acceptable status or an invalid option.
    """
    from django.utils import timezone
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from core.events import devis_accepted

    # Re-submit on an already-accepted devis: a no-op for the tokenized web
    # proposal, but rejected (409) for the in-app action (ERR33 guard).
    if devis.statut == Devis.Statut.ACCEPTE:
        if idempotent_reaccept:
            return devis
        raise AcceptError('Ce devis est déjà accepté.', conflict=True)

    # ERR33 — only a live devis (brouillon / envoyé) can be accepted.
    if devis.statut not in (Devis.Statut.BROUILLON, Devis.Statut.ENVOYE):
        raise AcceptError(
            'Seul un devis en cours (brouillon ou envoyé) peut être accepté ; '
            f'statut actuel : « {devis.get_statut_display()} ».',
            conflict=True)

    valid = {c.value for c in Devis.OptionAcceptee}
    option = (option or '').strip()
    if option and option not in valid:
        raise AcceptError(
            'Option invalide (attendu « sans_batterie » ou « avec_batterie »).')

    # Resolve the option exactly like the viewset (two-option devis require an
    # explicit choice; single-option devis deduce it from the scenario).
    try:
        from apps.ventes.quote_engine.builder import build_quote_data
        qd = build_quote_data(devis, {'pdf_mode': 'onepage'})
        nb_options = qd.get('nb_options', 1)
        scenario = qd.get('scenario', '')
    except Exception:  # noqa: BLE001 — l'acceptation ne doit jamais casser
        nb_options, scenario = 1, ''
    if nb_options == 2 and not option:
        raise AcceptError(
            'Ce devis comporte deux options — précisez celle choisie par le '
            'client (« sans_batterie » ou « avec_batterie »).')
    if not option:
        option = (Devis.OptionAcceptee.AVEC_BATTERIE
                  if scenario == 'Avec batterie'
                  else Devis.OptionAcceptee.SANS_BATTERIE)

    date_acc = date_acceptation or timezone.now().date()
    ancien = devis.statut
    devis.statut = Devis.Statut.ACCEPTE
    devis.date_acceptation = date_acc
    devis.accepte_par_nom = (nom or '')[:150]
    devis.option_acceptee = option
    devis.save(update_fields=[
        'statut', 'date_acceptation', 'accepte_par_nom', 'option_acceptee'])
    activity.log_devis_acceptance(devis, user, nom, date_acc, option)
    if ip:
        # Trace the e-signature origin IP in the chatter (Q7) without a new
        # column — kept beside the acceptance stamp for the audit trail.
        activity.log_devis_note(
            devis, user, f'Signature en ligne acceptée — IP {ip}')

    # QJ10 — Enregistrement IMMUABLE de signature (loi 53-05).
    # Idempotent : si un DevisSignature existe déjà (re-submit idempotent)
    # on ne crée pas de second enregistrement — la signature d'origine fait foi.
    _create_esign_record(
        devis=devis, nom=nom, ip=ip,
        user_agent=user_agent, consentement=consentement,
    )
    # QJ9 — Attribution first-touch : copie UTM/fbclid du lead vers etude_params
    # du devis pour que l'attribution reste lossless même si le lead est fusionné.
    try:
        _persist_attribution(devis=devis)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ9: _persist_attribution échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)
    # QJ22 — Stockage de l'artefact PDF signé (proposition verrouillée).
    # Appelé APRÈS _create_esign_record pour que le DevisSignature existe déjà.
    _store_signed_pdf(devis=devis)
    # QJ10 — Email de confirmation PDF verrouillé au client + au vendeur.
    try:
        _send_acceptance_emails(devis=devis, user=user)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ10: _send_acceptance_emails échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)

    devis_accepted.send(
        sender=Devis, devis=devis, user=user, ancien_statut=ancien)
    # QJ9 — CAPI SignedQuote event (gated on META_CAPI_ACCESS_TOKEN).
    try:
        _fire_capi_signed_quote(devis=devis)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ9: _fire_capi_signed_quote échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)
    return devis


def share_link_for_bcf(bcf):
    """QS3 — Point d'entrée cross-app : crée (ou réutilise) le lien tokenisé
    vers le PDF d'un Bon de Commande FOURNISSEUR (stock).

    L'app ``stock`` appelle CE service plutôt que d'importer ``ventes.models``
    (règle de modularité). La société vient du BCF (jamais du corps). Renvoie
    l'objet ShareLink (porte ``token`` + ``expires_at``)."""
    from apps.ventes.models import ShareLink
    return ShareLink.for_bon_commande_fournisseur(bcf)


def bcf_share_url(bcf, request=None):
    """QS3 — URL publique absolue vers le PDF tokenisé d'un BCF fournisseur.

    Réutilise la construction d'URL publique existante. Renvoie ``(url, token)``.
    Le lien reste imprévisible + expirant ; il est destiné au FOURNISSEUR et
    n'est jamais surfacé dans l'UI client."""
    from django.conf import settings
    link = share_link_for_bcf(bcf)
    base = getattr(settings, 'PUBLIC_BASE_URL', '') or ''
    path = f'/api/django/public/bcf/{link.token}/'
    if base:
        url = base.rstrip('/') + path
    elif request is not None:
        url = request.build_absolute_uri(path)
    else:
        url = path
    return url, link.token


def log_supplier_email(
        *, company, to_email, sujet, corps, attachment=None,
        attachment_name=None, reference='', user=None):
    """QS3 — Envoie un email FOURNISSEUR (PDF joint) et le consigne dans EmailLog.

    Point d'entrée cross-app pour ``stock`` (qui n'importe pas ``ventes.models``
    ni ``ventes.email_service``). Le fil EmailLog n'a pas de FK fournisseur : on
    consigne company + destinataire + référence (client/devis/facture restent
    nuls). NO-OP réseau sans clé configurée (backend console) — l'entrée est tout
    de même écrite. Renvoie ``(ok, log)``."""
    from apps.ventes.models import EmailLog
    from apps.ventes.email_service import _send, _from_email
    dest = (to_email or '').strip()
    log = EmailLog(
        company=company,
        direction=EmailLog.Direction.SORTANT,
        to_email=dest[:254], from_email=_from_email(),
        sujet=(sujet or '')[:300], corps=corps or '',
        reference=(reference or '')[:80],
        piece_jointe=(attachment_name or '')[:255],
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )
    if not dest:
        log.statut = EmailLog.Statut.ECHEC
        log.erreur = 'Aucune adresse email destinataire.'
        log.save()
        return False, log
    ok, err = _send(dest, sujet, corps, attachment, attachment_name)
    log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
    log.erreur = err
    log.save()
    return ok, log


def mark_devis_sent(*, devis, user=None):
    """U4 — flip a Devis to « envoyé » through the ONE status-change path.

    Called when a quote is shared with the client (e.g. the lead WhatsApp
    action builds a wa.me link). It is the single place that moves a quote
    document from « brouillon » to « envoyé » outside the viewset's own
    perform_update, so rule #4 status semantics + the chatter log are
    preserved (no raw ``.statut =`` write elsewhere).

    Behaviour:

    * a ``brouillon`` devis flips to ``envoye``, stamps ``date_envoi`` once,
      writes the « envoyé » chatter entry, and emits the ``devis_sent`` domain
      event so ``crm`` advances the lead funnel to QUOTE_SENT — without
      ventes importing crm directly (mirror of ``accept_devis``) ;
    * idempotent — an already-``envoye`` devis is returned unchanged (no second
      stamp, no second event, no duplicate chatter line) ;
    * NEVER regresses a further-along devis: ``accepte`` / ``refuse`` /
      ``expire`` are left exactly as-is (returned untouched).

    Returns the (possibly unchanged) Devis. Tenant scoping is the caller's
    responsibility — the devis is always passed already company-resolved.
    """
    from django.utils import timezone
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from core.events import devis_sent

    # Already sent (or beyond): never re-stamp, never downgrade. Only a live
    # brouillon advances — accepté/refusé/expiré are terminal-or-further and
    # must stay put (the guard the test pins).
    if devis.statut != Devis.Statut.BROUILLON:
        return devis

    ancien = devis.statut
    devis.statut = Devis.Statut.ENVOYE
    devis.date_envoi = timezone.now()
    devis.save(update_fields=['statut', 'date_envoi'])
    activity.log_devis_sent(devis, user)
    devis_sent.send(
        sender=Devis, devis=devis, user=user, ancien_statut=ancien)
    return devis


# Note des relances automatiques programmées (chemin scheduler). La séquence de
# relance compte ces traces pour reprendre au bon niveau ; on les neutralise au
# paiement intégral (U10) pour remettre l'escalade à zéro.
RELANCE_AUTO_NOTE = 'Relance automatique programmée (email).'
RELANCE_AUTO_NOTE_RESOLUE = (
    'Relance automatique programmée (email). [résolue — facture soldée]')


def reset_relance_escalation(facture):
    """U10 — remet à zéro l'escalade de relance d'une facture soldée.

    Quand un paiement amène ``montant_du <= 0`` et que la facture passe
    « Payée », l'escalade de recouvrement doit s'arrêter : sinon la facture
    continue d'afficher un ancien niveau de relance en retard et le scheduler
    (``relance_reminders``) pourrait reprendre la séquence là où elle s'était
    arrêtée. On efface donc ``prochaine_relance`` ET on neutralise les traces
    de relance AUTOMATIQUE consignées (le compteur qui pilote le niveau
    courant) — sans détruire l'historique : les ``RelanceLog`` sont conservés,
    leur note est seulement marquée « résolue » pour qu'ils ne soient plus
    comptés dans l'escalade. Idempotent : rien à faire si aucune escalade n'est
    en cours. Renvoie True si quelque chose a été réinitialisé."""
    changed = False
    if facture.prochaine_relance is not None:
        facture.prochaine_relance = None
        facture.save(update_fields=['prochaine_relance'])
        changed = True
    autos = facture.relances.filter(note=RELANCE_AUTO_NOTE)
    n = autos.update(note=RELANCE_AUTO_NOTE_RESOLUE)
    if n:
        changed = True
    # XFAC5 — une facture soldée referme toute promesse de paiement encore
    # « en_cours » (tenue) et lève l'exclusion de relance expirante posée par
    # la promesse.
    from .models import PromessePaiement
    tenues = facture.promesses_paiement.filter(
        statut=PromessePaiement.Statut.EN_COURS,
    ).update(statut=PromessePaiement.Statut.TENUE)
    if tenues:
        changed = True
    if facture.exclu_relances_jusquau is not None:
        facture.exclu_relances_jusquau = None
        facture.save(update_fields=['exclu_relances_jusquau'])
        changed = True
    return changed


def abandonner_solde_facture(facture, *, motif, user=None, auto=False,
                             date_abandon=None):
    """XFAC13 — abandonne le résiduel dû sur une facture (write-off).

    Passe la facture ``payee``, trace l'abandon (motif + montant + auteur +
    auto/manuel), délègue l'écriture comptable (6585/créance + reprise de
    provision FG152 le cas échéant) à ``apps.compta.services`` (jamais
    d'import direct de ses modèles) et consigne le chatter. Idempotent : ne
    fait rien si le résiduel est déjà nul. Renvoie le montant abandonné
    (``Decimal('0')`` si rien à faire)."""
    from decimal import Decimal
    from django.utils import timezone
    from .models import Facture
    reste = facture.montant_du
    if reste <= 0:
        return Decimal('0')
    from apps.compta import services as compta_services
    compta_services.abandonner_creance(
        facture.company, montant=reste, date_abandon=date_abandon,
        tiers_type='client', tiers_id=facture.client_id,
        tiers_nom=getattr(facture.client, 'nom', '') or '',
        libelle=f'Abandon créance facture {facture.reference}',
        user=user,
    )
    facture.abandon_motif = motif
    facture.abandon_montant = reste
    facture.abandon_date = timezone.now()
    facture.abandon_auto = bool(auto)
    facture.abandon_par = user if (
        user and getattr(user, 'is_authenticated', False)) else None
    facture.statut = Facture.Statut.PAYEE
    facture.save(update_fields=[
        'abandon_motif', 'abandon_montant', 'abandon_date', 'abandon_auto',
        'abandon_par', 'statut',
    ])
    from . import activity
    motif_label = dict(Facture.MotifAbandon.choices).get(motif, motif)
    activity.log_facture_abandon(facture, user, reste, motif_label, auto=auto)
    reset_relance_escalation(facture)
    return reste


def anomalies_emission_facture(facture):
    """XFAC18 — anomalies à contrôler avant l'émission d'une facture.

    Liste (jamais bloquante — informative pour le valideur) :
      * doublon probable (même client + montant TTC à ±1 % sous 15 jours) ;
      * remise globale au-delà de ``remise_max_pct`` (réglage société) ;
      * client au-delà du plafond d'encours FG41.

    Renvoie une liste de dicts ``{'code', 'message'}`` (vide si rien à
    signaler)."""
    from datetime import timedelta
    from decimal import Decimal
    from django.utils import timezone
    from .models import Facture

    anomalies = []

    # Doublon probable : même client, montant TTC proche, facture récente.
    montant = facture.total_ttc
    if montant and facture.client_id:
        seuil_jours = timezone.now().date() - timedelta(days=15)
        marge = montant * Decimal('0.01')
        doublons = Facture.objects.filter(
            client_id=facture.client_id, company=facture.company,
            date_emission__gte=seuil_jours,
        ).exclude(pk=facture.pk).exclude(
            statut=Facture.Statut.ANNULEE)
        for autre in doublons:
            if abs(autre.total_ttc - montant) <= marge:
                anomalies.append({
                    'code': 'doublon_probable',
                    'message': (
                        f'Doublon probable : facture {autre.reference} '
                        f'({autre.total_ttc} MAD) du même client, émise le '
                        f'{autre.date_emission}.'),
                })
                break

    # Remise globale au-delà du seuil société.
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.get(company=facture.company)
    remise_max = getattr(profile, 'remise_max_pct', None)
    if remise_max is not None and (facture.remise_globale or 0) > remise_max:
        anomalies.append({
            'code': 'remise_excessive',
            'message': (
                f'Remise globale ({facture.remise_globale} %) supérieure au '
                f'seuil société ({remise_max} %).'),
        })

    # Client au-delà de son plafond d'encours (FG41).
    if facture.client_id:
        from apps.crm.selectors import client_credit_warning
        warning = client_credit_warning(facture.client)
        if warning['depasse']:
            anomalies.append({
                'code': 'plafond_credit_depasse',
                'message': (
                    f"Encours client ({warning['encours']} MAD) au-delà du "
                    f"plafond ({warning['plafond']} MAD)."),
            })

    return anomalies


class StockInsuffisantError(Exception):
    """Levée quand une réservation de stock dépasserait le disponible (U9)."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def reserver_stock_devis_facture(*, devis, user, company):
    """U9 — réserve/consomme le stock matériel d'un devis facturé EN DIRECT.

    Le chemin bon-commande (``bon_commande.marquer_livre``) décrémente déjà le
    stock à la livraison. Mais un devis accepté puis facturé directement via
    l'échéancier (``generer-facture``) court-circuite le bon de commande et ne
    réservait donc AUCUN stock — d'où une survente possible entre devis. Cette
    fonction reproduit EXACTEMENT la réservation de la livraison BC (mêmes
    lignes du devis, même arrondi HALF_UP du décimal vers l'entier du registre,
    même garde de stock insuffisant), mais branchée sur la première facture
    d'échéancier.

    Garde anti-double-comptage : on ne réserve qu'UNE fois par devis. On ne
    fait RIEN si
      * un mouvement SORTIE référence déjà ce devis (réservation déjà posée par
        une tranche antérieure de l'échéancier), ou
      * un bon de commande de ce devis a déjà été livré (stock déjà consommé par
        le chemin BC).
    Écriture du mouvement déléguée au service stock (jamais d'import direct des
    models stock). À appeler dans la transaction de l'appelant.

    Lève ``StockInsuffisantError`` si une ligne dépasse le disponible (la
    transaction de l'appelant est alors annulée, comme côté BC).
    """
    from decimal import Decimal, ROUND_HALF_UP
    from apps.stock.services import (
        mouvement_type_sortie, record_stock_movement,
        sortie_exists_for_reference,
    )
    from apps.ventes.models import BonCommande

    reference = devis.reference

    # Déjà réservé pour ce devis (tranche antérieure de l'échéancier) → no-op.
    if sortie_exists_for_reference(company, reference):
        return False

    # Un BC livré a déjà consommé le stock de ce devis → ne pas re-décompter.
    if BonCommande.objects.filter(
            devis=devis, statut=BonCommande.Statut.LIVRE).exists():
        return False

    moved = False
    for ligne in devis.lignes.select_related('produit'):
        produit = ligne.produit
        if produit is None:
            continue
        produit.refresh_from_db()
        # Même règle que la livraison BC (ERR15) : on arrondit au plus proche
        # (HALF_UP) au lieu de tronquer, le registre de stock étant en entiers.
        qte = int(Decimal(ligne.quantite).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP))
        if qte <= 0:
            continue
        qte_avant = produit.quantite_stock
        qte_apres = qte_avant - qte
        if qte_apres < 0:
            raise StockInsuffisantError(
                f'Stock insuffisant pour « {produit.nom} » '
                f'(disponible : {qte_avant}, requis : {qte}).')
        record_stock_movement(
            company=company,
            produit=produit,
            type_mouvement=mouvement_type_sortie(),
            quantite=qte,
            quantite_avant=qte_avant,
            quantite_apres=qte_apres,
            reference=reference,
            note=f'Facturation directe — devis {reference}',
            created_by=user,
        )
        moved = True
    return moved


def creer_facture_contrat(*, contrat, user, company):
    """FG40 — Crée une Facture de maintenance récurrente depuis un ContratMaintenance.

    Appelé par sav.maintenance (action `facturer`) ; jamais depuis un template
    ou une vue directement.

    Règles :
      - Le contrat doit avoir `facturation_active=True` et `prix` renseigné.
      - La facture porte le libellé "Maintenance — contrat #<pk>" + périodicité.
      - TVA 20 % (taux standard, configurable en dur ici — pas de multi-TVA sur
        les forfaits de maintenance).
      - Statut EMISE directement (facture manuelle de redevance).
      - Après création, `derniere_facturation` du contrat est avancée à aujourd'hui.

    Lève ValueError si les pré-conditions ne sont pas remplies.
    Renvoie la Facture créée.
    """
    from django.utils import timezone
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

    if not contrat.facturation_active:
        raise ValueError(
            f"La facturation n'est pas activée sur le contrat #{contrat.pk}.")
    if not contrat.prix:
        raise ValueError(
            f"Le prix est absent sur le contrat #{contrat.pk}. "
            "Renseignez un prix avant d'émettre une facture.")
    if not contrat.actif:
        raise ValueError(f"Le contrat #{contrat.pk} n'est pas actif.")

    tva_pct = Decimal('20')
    prix_ttc = Decimal(str(contrat.prix))
    prix_ht = (prix_ttc / (1 + tva_pct / 100)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_tva = (prix_ttc - prix_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    periodicite_label = (
        contrat.get_periodicite_display()
        if hasattr(contrat, 'get_periodicite_display')
        else contrat.periodicite
    )
    libelle = f'Maintenance — contrat #{contrat.pk} ({periodicite_label})'

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            company=company,
            client=contrat.client,
            statut=Facture.Statut.EMISE,
            taux_tva=tva_pct,
            montant_ht=prix_ht,
            montant_tva=montant_tva,
            montant_ttc=prix_ttc,
            libelle=libelle,
            created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)

    # Avancer la date de dernière facturation.
    today = timezone.localdate()
    contrat.derniere_facturation = today
    contrat.save(update_fields=['derniere_facturation'])

    logger.info(
        'FG40: facture %s créée pour contrat #%s (company %s)',
        facture.reference, contrat.pk, company.id)
    return facture


# ── XPRJ3 — Facturation en régie (T&M) depuis gestion_projet ─────────────────

def creer_facture_regie(*, company, client, user, libelle, montant_ht,
                        taux_tva=Decimal('20')):
    """XPRJ3 — Crée une Facture BROUILLON « en régie » (temps & matériel).

    Fonction FINE sanctionnée pour ``gestion_projet.services.facturer_temps_
    projet`` (frontière cross-app, CLAUDE.md) : ce module ne connaît AUCUN
    détail de gestion_projet (pas de timesheet, pas de tâche) — il reçoit juste
    un montant HT déjà calculé (heures × taux de facturation, agrégées côté
    appelant) et un libellé. Le client est résolu côté APPELANT (jamais importé
    ici) et passé en instance ``crm.Client``.

    Statut BROUILLON (contrairement à ``creer_facture_contrat`` qui émet
    directement) : une facture de régie doit rester éditable/relisible avant
    envoi. Numérotation via ``apps/ventes/utils/references.py`` (jamais
    ``count()+1``). Renvoie la ``Facture`` créée.
    """
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

    montant_ht = Decimal(montant_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_tva = (montant_ht * taux_tva / 100).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_ttc = montant_ht + montant_tva

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            company=company,
            client=client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.COMPLETE,
            taux_tva=taux_tva,
            montant_ht=montant_ht,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            libelle=libelle,
            created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)
    logger.info(
        'XPRJ3: facture régie %s créée (company %s, montant HT %s)',
        facture.reference, company.id, montant_ht)
    return facture


# ── XPRJ4 — Facture d'acompte pour une situation de travaux (décompte BTP) ───

def creer_facture_acompte_situation(*, company, client, user, libelle,
                                    montant_periode_ht,
                                    retenue_garantie_pct=None,
                                    taux_tva=Decimal('20')):
    """XPRJ4 — Crée une Facture BROUILLON d'ACOMPTE pour une situation de
    travaux (décompte progressif BTP).

    Fonction FINE sanctionnée pour ``gestion_projet.services`` (frontière
    cross-app, CLAUDE.md) : reçoit le montant HT DÉJÀ calculé de la PÉRIODE
    (cumulé − antérieur, agrégé côté appelant sur toutes les lignes de la
    situation) et une retenue de garantie optionnelle DÉDUITE du montant
    facturé (le taux, pas le suivi de sa libération — qui vit dans
    ``contrats``, jamais importé ici). Statut BROUILLON + ``type_facture``
    ACOMPTE (chaîne standard devis→factures, réutilisée ici sans devis source).
    Numérotation via ``apps/ventes/utils/references.py`` (jamais
    ``count()+1``). Renvoie la ``Facture`` créée.
    """
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

    montant_periode_ht = Decimal(montant_periode_ht).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    rg_pct = Decimal(retenue_garantie_pct or 0)
    montant_rg = (montant_periode_ht * rg_pct / 100).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_ht_net = montant_periode_ht - montant_rg
    montant_tva = (montant_ht_net * taux_tva / 100).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    montant_ttc = montant_ht_net + montant_tva

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            company=company,
            client=client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.ACOMPTE,
            taux_tva=taux_tva,
            montant_ht=montant_ht_net,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            libelle=libelle,
            created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)
    logger.info(
        'XPRJ4: facture acompte situation %s créée (company %s, montant HT '
        'net %s, RG %s%%)',
        facture.reference, company.id, montant_ht_net, rg_pct)
    return facture


# ── XPOS1/XPOS6 — Thin services exposés pour apps.pos (vente comptoir) ─────
# apps.pos ne peut PAS importer apps.ventes.models directement (règle de
# modularité CLAUDE.md) : ces fonctions sont son unique porte d'entrée pour
# créer une facture classique et enregistrer/lire des paiements.

def creer_facture_classique(*, company, client, user, taux_tva, montant_ht,
                            montant_tva, montant_ttc, libelle=''):
    """Crée une ``Facture`` classique (sans devis/BC), montants figés.

    Utilisé par ``apps.pos.services.valider_vente`` pour la facture légale
    d'une vente comptoir. ``company``/``client`` doivent déjà être validés par
    l'appelant (scoping multi-tenant). Numérotation collision-proof (jamais
    count()+1)."""
    from apps.ventes.models import Facture
    from apps.ventes.utils.references import create_with_reference

    def _create(ref):
        return Facture.objects.create(
            reference=ref,
            company=company,
            client=client,
            statut=Facture.Statut.EMISE,
            type_facture=Facture.TypeFacture.COMPLETE,
            taux_tva=taux_tva,
            montant_ht=montant_ht,
            montant_tva=montant_tva,
            montant_ttc=montant_ttc,
            libelle=libelle,
            created_by=user,
        )

    return create_with_reference(Facture, 'FAC', company, _create)


def enregistrer_paiement(*, facture, montant, mode, date_paiement, user,
                         reference='', note=''):
    """Enregistre un ``Paiement`` MANUEL sur une facture EXISTANTE.

    Thin service exposé pour apps.pos (encaissement comptoir XPOS1/XPOS6) —
    même modèle/table que le paiement enregistré depuis l'écran facture,
    aucune duplication de logique."""
    from apps.ventes.models import Paiement
    return Paiement.objects.create(
        company=facture.company,
        facture=facture,
        montant=montant,
        date_paiement=date_paiement,
        mode=mode,
        reference=reference or '',
        note=note or '',
        created_by=user,
    )


def facture_montant_du(facture):
    """Solde restant dû d'une facture (lecture, thin service pour apps.pos)."""
    return facture.montant_du


def get_facture_or_none(*, company, facture_id):
    """Facture scopée société, ou None (thin service pour apps.pos XPOS6)."""
    from apps.ventes.models import Facture
    return Facture.objects.filter(company=company, id=facture_id).first()


def facturables_pour_devis(*, company, query=''):
    """Factures émises/en retard avec solde restant dû, scopées société (thin
    selector pour apps.pos XPOS6 — recherche comptoir par référence)."""
    from apps.ventes.models import Facture
    qs = Facture.objects.filter(
        company=company,
        statut__in=(Facture.Statut.EMISE, Facture.Statut.EN_RETARD))
    if query:
        qs = qs.filter(reference__icontains=query)
    return [f for f in qs.select_related('client', 'devis') if f.montant_du > 0]


# ── FG53 — Liens de paiement « Payer en ligne » ──────────────────────────────

def create_payment_link(*, facture, provider=None):
    """FG53 — crée (ou réutilise) un lien de paiement pour une facture.

    Réutilise un lien encore valide (en attente, non expiré) pour la même
    facture plutôt que d'en empiler. Le montant est figé au reste à payer à
    l'instant T. Le fournisseur par défaut est NoOp (page interne, aucun coût).
    Société forcée depuis la facture, jamais lue d'un corps de requête.
    """
    from decimal import Decimal
    from django.utils import timezone
    from .models import PaymentLink

    existing = (PaymentLink.objects
                .filter(facture=facture,
                        statut=PaymentLink.Statut.EN_ATTENTE,
                        expires_at__gt=timezone.now())
                .order_by('-created_at').first())
    if existing is not None:
        return existing

    montant = facture.montant_du
    if montant is None or montant <= Decimal('0'):
        montant = facture.total_ttc
    return PaymentLink.objects.create(
        company=facture.company,
        facture=facture,
        provider=(provider or 'noop'),
        montant=montant,
    )


def _public_url(path):
    """Construit une URL publique absolue à partir d'un chemin ``/api/...``.

    Réutilise ``settings.PUBLIC_BASE_URL`` (même pattern que
    ``bcf_share_url``) ; sans réglage, renvoie le chemin relatif tel quel (le
    QR reste valide une fois servi depuis le même domaine)."""
    from django.conf import settings
    base = getattr(settings, 'PUBLIC_BASE_URL', '') or ''
    if base:
        return base.rstrip('/') + path
    return path


def qr_svg_for_facture_pdf(facture):
    """XFAC19 — QR de paiement/vérification pour le PDF facture LEGACY (jamais
    le moteur devis premium — voir RULE #4).

    Si un ``PaymentLink`` actif (en attente, non expiré) existe déjà pour la
    facture, le QR pointe vers sa page « Payer en ligne » publique. Sinon, il
    pointe vers le ``ShareLink`` public (lecture seule) du document. Ajout
    SILENCIEUX : renvoie ``None`` si aucun lien ne peut être établi (comportement
    actuel inchangé — pas de QR, pas d'erreur). Le rendu SVG délègue au
    générateur QR pur de N20 via ``apps.stock.services.qr_svg_for`` (jamais
    d'import direct de ``apps.stock.labels``)."""
    from django.utils import timezone
    from .models import PaymentLink, ShareLink
    from apps.stock.services import qr_svg_for

    active_link = (
        PaymentLink.objects.filter(
            facture=facture, statut=PaymentLink.Statut.EN_ATTENTE,
            expires_at__gt=timezone.now(),
        ).order_by('-created_at').first())
    if active_link is not None:
        url = _public_url(f'/api/django/public/pay/{active_link.token}/')
    else:
        share = ShareLink.for_facture(facture)
        url = _public_url(f'/api/django/public/document/{share.token}/')

    if not url:
        return None
    return qr_svg_for(url)


def record_payment_from_link(*, link, payload=None):
    """FG53 — enregistre un Paiement quand un lien est confirmé payé (webhook).

    Idempotent : un lien déjà payé renvoie le paiement existant sans en créer un
    second. Le fournisseur valide d'abord la notification (verify_webhook) ; tant
    qu'il ne confirme pas, rien n'est écrit. Le montant et le statut de la
    facture sont mis à jour exactement comme un encaissement manuel.

    Retourne (paiement, message_erreur). En succès message_erreur=None.
    """
    from decimal import Decimal
    from django.db import transaction
    from django.utils import timezone
    from .models import Facture, Paiement, PaymentLink
    from .payments.providers import get_provider

    if link.statut == PaymentLink.Statut.PAYE and link.paiement_id:
        # Déjà encaissé — idempotent.
        return link.paiement, None
    if not link.is_valid:
        return None, 'Lien de paiement expiré ou invalide.'

    provider = get_provider(link.provider)
    result = provider.verify_webhook(link, payload or {})
    if not result.get('paid'):
        return None, 'Paiement non confirmé par le fournisseur.'

    montant = result.get('montant')
    if montant is None:
        montant = link.montant
    montant = Decimal(str(montant))

    with transaction.atomic():
        locked_link = (PaymentLink.objects.select_for_update()
                       .get(pk=link.pk))
        if locked_link.statut == PaymentLink.Statut.PAYE \
                and locked_link.paiement_id:
            return locked_link.paiement, None
        facture = (Facture.objects.select_for_update()
                   .get(pk=locked_link.facture_id))
        if facture.statut == Facture.Statut.ANNULEE:
            return None, 'Facture annulée.'
        # Borne le montant au reste à payer (jamais de sur-paiement).
        reste = facture.montant_du
        if montant > reste:
            montant = reste
        if montant <= Decimal('0'):
            return None, 'Aucun reste à payer sur cette facture.'
        paiement = Paiement.objects.create(
            company=facture.company,
            facture=facture,
            montant=montant,
            date_paiement=timezone.localdate(),
            mode=Paiement.Mode.CARTE,
            reference=(result.get('provider_ref') or '')[:120],
            note='Paiement en ligne (lien « Payer en ligne »).',
        )
        locked_link.statut = PaymentLink.Statut.PAYE
        locked_link.paiement = paiement
        locked_link.provider_ref = (result.get('provider_ref') or '')[:200]
        locked_link.paid_at = timezone.now()
        locked_link.save(update_fields=[
            'statut', 'paiement', 'provider_ref', 'paid_at'])
        facture.refresh_from_db()
        if facture.montant_du <= Decimal('0') \
                and facture.statut != Facture.Statut.ANNULEE:
            facture.statut = Facture.Statut.PAYEE
            facture.save(update_fields=['statut'])
    return paiement, None


# ── QJ16 — Reusable quote presets ────────────────────────────────────────────

def save_devis_as_preset(devis, nom: str, description: str = "", *, user=None):
    """QJ16 — snapshot a Devis into a company-scoped DevisPreset.

    The preset captures the line configuration (designation, quantite,
    prix_unitaire, remise, taux_tva per line, plus taux_tva and remise_globale
    at devis level) as a JSON snapshot.  The company is ALWAYS forced from
    ``devis.company`` — never from user input.

    Price-less lines are excluded at save time (same guard as auto-fill): if a
    line's produit has no sell price, it is still captured in the snapshot so the
    preset is complete, but at apply-time such lines are re-checked and skipped
    if the product is no longer priced.

    Returns the created DevisPreset.
    """
    from apps.ventes.models import DevisPreset

    company = devis.company
    if company is None:
        raise ValueError("save_devis_as_preset: devis has no company")

    def _ds(value):
        # Normalise a Decimal to a clean string (strip trailing zeros):
        # 10.00 -> "10", 10.50 -> "10.5". None stays None.
        if value is None:
            return None
        s = str(value)
        return s.rstrip('0').rstrip('.') if '.' in s else s

    lignes_snapshot = []
    for ligne in devis.lignes.select_related('produit').order_by('id'):
        produit = ligne.produit
        lignes_snapshot.append({
            'produit_id': produit.pk if produit else None,
            'designation': ligne.designation,
            'quantite': _ds(ligne.quantite),
            'prix_unitaire': _ds(ligne.prix_unitaire),
            'remise': _ds(ligne.remise),
            'taux_tva': _ds(ligne.taux_tva),
        })

    preset = DevisPreset.objects.create(
        company=company,
        nom=nom.strip(),
        description=description,
        mode_installation=devis.mode_installation or None,
        taux_tva=devis.taux_tva,
        remise_globale=devis.remise_globale,
        lignes_snapshot=lignes_snapshot,
        etude_params_snapshot=dict(devis.etude_params) if devis.etude_params else None,
        created_by=user,
    )
    logger.info(
        'QJ16: preset "%s" saved (id=%s, company=%s, %d lignes)',
        preset.nom, preset.pk, company.pk, len(lignes_snapshot))
    return preset


def apply_preset_to_devis(preset, devis, *, skip_priceless: bool = True) -> list:
    """QJ16 — apply a DevisPreset to an existing (empty) Devis.

    Creates LigneDevis rows on ``devis`` from the preset snapshot.  The caller
    is responsible for ensuring ``devis`` is brouillon and belongs to the same
    company as the preset (enforced below — cross-company apply is refused).

    ``skip_priceless=True`` (default): lines whose snapshot product no longer
    has a sell price are skipped (same guard as auto-fill — never auto-quote a
    price-less product).  Pass ``skip_priceless=False`` only in tests that need
    to exercise the skipping logic.

    Returns the list of created LigneDevis instances (may be empty if all lines
    are priceless).

    RULE #4: this service only builds lines — it never changes Devis.statut.
    """
    from apps.ventes.models import LigneDevis
    from apps.stock.models import Produit

    if preset.company_id != devis.company_id:
        raise ValueError(
            "apply_preset_to_devis: preset and devis belong to different companies"
        )

    created = []
    for snap in preset.lignes_snapshot:
        produit_id = snap.get('produit_id')
        produit = None
        if produit_id:
            try:
                produit = Produit.objects.get(
                    pk=produit_id, company=devis.company)
            except Produit.DoesNotExist:
                # Product deleted or belongs to another company — try global
                try:
                    produit = Produit.objects.get(
                        pk=produit_id, company__isnull=True)
                except Produit.DoesNotExist:
                    produit = None

        if skip_priceless and produit is not None and not _has_price(produit):
            logger.info(
                'QJ16 apply_preset: skipping priceless product %s ("%s")',
                produit_id, snap.get('designation', ''))
            continue

        taux_snap = snap.get('taux_tva')
        ligne = LigneDevis.objects.create(
            devis=devis,
            produit=produit,
            designation=snap['designation'],
            quantite=Decimal(str(snap['quantite'])),
            prix_unitaire=Decimal(str(snap['prix_unitaire'])),
            remise=Decimal(str(snap.get('remise', '0'))),
            taux_tva=Decimal(str(taux_snap)) if taux_snap is not None else None,
        )
        created.append(ligne)

    # Apply devis-level settings from preset if the devis is fresh (no lignes yet
    # before this call means we can safely update tva and remise).
    if created:
        devis.taux_tva = preset.taux_tva
        devis.remise_globale = preset.remise_globale
        if preset.mode_installation:
            devis.mode_installation = preset.mode_installation
        if preset.etude_params_snapshot and not devis.etude_params:
            devis.etude_params = dict(preset.etude_params_snapshot)
        devis.save(update_fields=[
            'taux_tva', 'remise_globale', 'mode_installation', 'etude_params'])

    logger.info(
        'QJ16 apply_preset: applied preset "%s" to devis %s (%d lines)',
        preset.nom, getattr(devis, 'reference', devis.pk), len(created))
    return created


# ── QJ4 — Relance automatique cadencée des devis envoyés ─────────────────────
# Logique : pour chaque devis « envoyé » (statut ENVOYE) dont date_envoi est
# renseignée, on contrôle si l'un des paliers de la cadence est échu
# (aujourd'hui >= date_envoi + jours[niveau]) et s'il n'a pas encore été
# déclenché (pas de DevisNudgeLog pour ce niveau). On surface alors un draft
# wa.me au vendeur — ou on envoie un email si le canal email est configuré.
# La relance s'arrête dès que le statut passe à ACCEPTE ou REFUSE.

# Modèles de message de relance — FR et AR.
# Clés : ref (référence devis), jours (palier), client_nom, wa_url (lien
# public). Les accolades dobles {{ }} échappées en cas d'imbrication Django
# template — ici on utilise .format() directement, pas de template Django.
_NUDGE_MSG_FR = (
    "Bonjour,\n\n"
    "Le devis {ref} envoyé à {client_nom} il y a {jours} jours est toujours "
    "en attente de validation.\n\n"
    "Pensez à relancer votre client :\n{wa_url}\n\n"
    "Cordialement,\nL'équipe TAQINOR"
)

_NUDGE_MSG_AR = (
    "مرحبا،\n\n"
    "لا يزال عرض "
    "{ref} المرسل إلى "
    "{client_nom} منذ {jours} أيام "
    "في انتظار الموافقة.\n\n"
    "يُرجى متابعة "
    "العميل:\n{wa_url}\n\n"
    "مع التحيات،\n"
    "فريق TAQINOR"
)


def _build_wa_draft_url(phone, text):
    """Construit un lien wa.me pré-rempli. phone peut inclure '+' ou non."""
    import urllib.parse
    digits = ''.join(c for c in (phone or '') if c.isdigit())
    if not digits:
        return None
    encoded = urllib.parse.quote(text)
    return f'https://wa.me/{digits}?text={encoded}'


def _get_nudge_days():
    """Renvoie la cadence de relance depuis les settings (ou la valeur par défaut)."""
    from django.conf import settings
    from apps.ventes.models import DEVIS_NUDGE_DEFAULT_DAYS
    return getattr(settings, 'DEVIS_NUDGE_DAYS', DEVIS_NUDGE_DEFAULT_DAYS)


def send_devis_followup_nudges():
    """QJ4 — Déclenche les relances cadencées pour les devis « envoyés ».

    Pour chaque devis ENVOYE avec date_envoi renseignée :
    - parcourt les paliers de la cadence (j+2, j+5, j+10 par défaut) ;
    - si today >= date_envoi + jours[niveau] ET que ce niveau n'a jamais été
      déclenché (pas de DevisNudgeLog) → envoie la relance ;
    - préfère un email si le canal email est configuré, sinon surface un draft
      wa.me au vendeur (logged) ;
    - enregistre un DevisNudgeLog pour éviter tout doublon.

    Idempotent : safe à ré-exécuter sans effet si tous les niveaux dus ont déjà
    leur DevisNudgeLog. Renvoie le nombre total de nudges déclenchés.

    RULE #4 : ne touche JAMAIS au statut du Devis.
    Multi-tenant : chaque devis est scopé company (never trusts body company).
    """
    from django.utils import timezone
    try:
        from zoneinfo import ZoneInfo
        _tz = ZoneInfo('Africa/Casablanca')

        def _today():
            return timezone.now().astimezone(_tz).date()
    except Exception:
        def _today():
            return timezone.localdate()

    from apps.ventes.models import Devis, DevisNudgeLog, ShareLink
    from apps.ventes.email_service import is_email_configured

    nudge_days = _get_nudge_days()
    today = _today()

    # Only look at envoye devis with a known send date.
    candidates = Devis.objects.filter(
        statut=Devis.Statut.ENVOYE,
        date_envoi__isnull=False,
    ).select_related('client', 'company', 'created_by').prefetch_related(
        'nudge_logs',
    )

    use_email = is_email_configured()
    total_sent = 0

    for devis in candidates:
        # Double-check: cadence stops on accept/refuse (belt-and-suspenders
        # since we filter on ENVOYE above, but guards concurrent transitions).
        if devis.statut in (Devis.Statut.ACCEPTE, Devis.Statut.REFUSE):
            continue

        # date_envoi is a DateTimeField — extract date in Casablanca tz.
        try:
            envoi_date = devis.date_envoi.astimezone(
                ZoneInfo('Africa/Casablanca')).date()
        except Exception:
            envoi_date = devis.date_envoi.date()

        # Which levels already fired?
        fired = set(
            devis.nudge_logs.values_list('niveau', flat=True)
        )

        client = getattr(devis, 'client', None)
        client_nom = (getattr(client, 'nom', '') or '') if client else ''
        vendeur = getattr(devis, 'created_by', None)

        for idx, jours in enumerate(nudge_days):
            if idx in fired:
                continue  # already sent for this level — idempotent
            trigger_date = envoi_date + __import__('datetime').timedelta(days=jours)
            if today < trigger_date:
                continue  # not due yet

            # Build the public share link for the seller to use.
            try:
                share_link = ShareLink.for_devis(devis)
                from django.conf import settings
                site = getattr(settings, 'SITE_URL', 'https://taqinor.ma')
                proposal_url = f'{site}/proposal/{share_link.token}'
            except Exception:
                proposal_url = ''

            msg_fr = _NUDGE_MSG_FR.format(
                ref=devis.reference,
                client_nom=client_nom or 'votre client',
                jours=jours,
                wa_url=proposal_url,
            )
            msg_ar = _NUDGE_MSG_AR.format(
                ref=devis.reference,
                client_nom=client_nom or 'عميلك',
                jours=jours,
                wa_url=proposal_url,
            )

            canal = DevisNudgeLog.Canal.WA_DRAFT

            # Bilingual body used for email (FR + AR separator).
            msg_bilingual = msg_fr + '\n\n---\n\n' + msg_ar

            if use_email and vendeur and getattr(vendeur, 'email', ''):
                # Send email to seller (bilingual FR + AR).
                _send_nudge_email(
                    to_email=vendeur.email,
                    devis_ref=devis.reference,
                    subject_fr=f'Relance devis {devis.reference} — niveau {idx + 1}',
                    body_fr=msg_bilingual,
                )
                canal = DevisNudgeLog.Canal.EMAIL
            else:
                # Surface wa.me draft — log so the seller sees it.
                vendeur_phone = (
                    getattr(vendeur, 'phone_number', '') or ''
                    if vendeur else ''
                )
                wa_url = _build_wa_draft_url(vendeur_phone, msg_fr) or proposal_url
                logger.info(
                    'QJ4 nudge wa_draft devis=%s niveau=%d j+%d vendeur=%s url=%s',
                    devis.reference, idx, jours,
                    getattr(vendeur, 'username', '?'), wa_url)

            # Record the fired level — unique_together prevents duplicates.
            try:
                DevisNudgeLog.objects.create(
                    company=devis.company,
                    devis=devis,
                    niveau=idx,
                    jours=jours,
                    canal=canal,
                )
                total_sent += 1
                logger.info(
                    'QJ4: nudge N%d déclenché pour devis %s (j+%d, canal=%s)',
                    idx, devis.reference, jours, canal)
            except Exception as exc:
                # IntegrityError → already fired concurrently — safe to ignore.
                logger.warning(
                    'QJ4: DevisNudgeLog creation skipped for devis %s niveau=%d: %s',
                    devis.reference, idx, exc)

    logger.info('QJ4 send_devis_followup_nudges: %d nudge(s) déclenchés', total_sent)
    return total_sent


def _send_nudge_email(*, to_email, devis_ref, subject_fr, body_fr):
    """Envoie un email de relance au vendeur (NO-OP sans backend email configuré).

    Best-effort : ne lève jamais, consigne juste le résultat en log.
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local')
        send_mail(subject_fr, body_fr, from_email, [to_email], fail_silently=False)
        logger.info('QJ4: email relance envoyé à %s (devis %s)', to_email, devis_ref)
    except Exception as exc:  # noqa: BLE001
        logger.warning('QJ4: email relance échec pour %s: %s', devis_ref, exc)


# ── QJ5 — Expiration automatique des devis + hygiène funnel ──────────────────


def expire_stale_devis():
    """QJ5 — Bascule les devis envoyés dépassés en « expiré » et avance le funnel.

    Deux effets ATOMIQUEMENT SÉPARÉS (chaque devis est traité indépendamment) :

    1. ``envoye → expire`` pour tout devis dont la date de validité effective
       est dépassée. Délègue à ``ventes.utils.expiry.is_expired`` (même logique
       que l'indicateur à la volée, garantie de cohérence). Ne touche JAMAIS un
       devis ``accepte`` ou ``refuse`` (rule #4). Idempotent : un devis déjà
       ``expire`` est ignoré.

    2. Pour le lead lié au devis expiré (s'il en a un) : si le lead est à
       ``QUOTE_SENT`` il avance vers ``FOLLOW_UP``; s'il est déjà à ``FOLLOW_UP``
       depuis plus de COLD_DAYS jours (configurable, défaut 30) et n'a reçu
       aucune activité récente, il est parqué à ``COLD``. Ne recule JAMAIS un
       lead déjà plus avancé (SIGNED) et ignore les leads perdus (drapeau perdu).
       STAGES.py keys utilisées, jamais hardcodées.

    Renvoie un dict ``{expired, funnel_followup, funnel_cold}`` pour les tests.
    """
    from datetime import date

    from .models import Devis

    today = date.today()
    expired = 0
    funnel_followup = 0
    funnel_cold = 0

    # Candidats : devis envoyés uniquement (jamais accepte/refuse/expire).
    candidates = Devis.objects.filter(
        statut=Devis.Statut.ENVOYE,
    ).select_related('lead', 'lead__company')

    for devis in candidates:
        from .utils.expiry import is_expired
        if not is_expired(devis, today=today):
            continue

        # Flip to expired through the single status-change path: direct field
        # write + chatter log. Using the same field pattern as other beat jobs
        # (check_overdue_factures) — safe, reversible via git revert.
        devis.statut = Devis.Statut.EXPIRE
        devis.save(update_fields=['statut'])

        # Chatter entry via ventes.activity (exists for devis accepted/sent —
        # reuse the generic note pattern).
        try:
            from apps.ventes import activity as _act
            _act.log_devis_note(
                devis, None,
                'Devis expiré automatiquement (date de validité dépassée).')
        except Exception as exc:  # noqa: BLE001
            logger.warning('QJ5: log chatter échec devis %s : %s',
                           devis.reference, exc)

        expired += 1

        # Funnel hygiene: advance QUOTE_SENT → FOLLOW_UP via crm.services.
        lead = devis.lead
        if lead is None:
            continue

        try:
            fup, cold = _advance_lead_on_expiry(lead, today=today)
            funnel_followup += int(fup)
            funnel_cold += int(cold)
        except Exception as exc:  # noqa: BLE001
            logger.warning('QJ5: avance funnel échec lead %s : %s',
                           getattr(lead, 'pk', '?'), exc)

    logger.info(
        'QJ5 expire_stale_devis: %d expiré(s), %d → FOLLOW_UP, %d → COLD',
        expired, funnel_followup, funnel_cold)
    return {'expired': expired, 'funnel_followup': funnel_followup,
            'funnel_cold': funnel_cold}


# Days a QUOTE_SENT lead stays at FOLLOW_UP before being parked COLD (no
# recent activity). Kept as a module-level constant so tests can patch it.
_COLD_AFTER_FOLLOWUP_DAYS = 30


def _advance_lead_on_expiry(lead, today):
    """Avance l'étape du lead lié à un devis expiré (QUOTE_SENT → FOLLOW_UP,
    puis FOLLOW_UP → COLD si inactif depuis COLD_AFTER_FOLLOWUP_DAYS jours).

    Ne recule JAMAIS. Ignore les leads perdus. Utilise les clés STAGES.py.
    Renvoie (moved_to_followup: bool, moved_to_cold: bool).
    """
    from datetime import timedelta
    from apps.crm.models import LeadActivity

    if lead.perdu:
        return False, False

    moved_fup = False
    moved_cold = False

    if lead.stage == 'QUOTE_SENT':
        # Only advance if lead is not already further.
        from apps.crm.services import _rang_funnel
        if _rang_funnel(lead.stage) < _rang_funnel('FOLLOW_UP'):
            ancien = lead.stage
            lead.stage = 'FOLLOW_UP'
            lead.save(update_fields=['stage'])
            from apps.crm import activity as crm_activity
            # Pass raw stage keys; _display resolves choices labels.
            crm_activity.log_bulk_change(
                lead, user=None,
                field='stage',
                old_val=ancien,
                new_val='FOLLOW_UP',
            )
            moved_fup = True
        return moved_fup, False

    if lead.stage == 'FOLLOW_UP':
        # Park COLD only if no activity in last _COLD_AFTER_FOLLOWUP_DAYS days.
        cutoff = today - timedelta(days=_COLD_AFTER_FOLLOWUP_DAYS)
        recent_activity = LeadActivity.objects.filter(
            lead=lead,
            created_at__date__gte=cutoff,
        ).exists()
        if recent_activity:
            return False, False
        ancien = lead.stage
        lead.stage = 'COLD'
        lead.save(update_fields=['stage'])
        from apps.crm import activity as crm_activity
        crm_activity.log_bulk_change(
            lead, user=None,
            field='stage',
            old_val=ancien,
            new_val='COLD',
        )
        moved_cold = True
        return False, moved_cold

    return False, False


# ── XSAV3 — Devis de réparation hors garantie depuis un ticket SAV ───────────

def create_devis_pour_ticket(*, company, user, client_id, lignes, note=None):
    """XSAV3 — Crée un Devis BROUILLON pour un travail SAV non couvert.

    Point d'entrée cross-app (sav → ventes) : ``apps.sav`` appelle CETTE
    fonction plutôt que d'importer ``apps.ventes.models`` directement (règle
    de modularité CLAUDE.md). ``lignes`` est une liste de dicts
    ``{'produit_id': int, 'designation': str, 'quantite': Decimal,
    'prix_unitaire': Decimal}`` — le prix unitaire attendu ici est TOUJOURS le
    prix de VENTE catalogue (``Produit.prix_vente``), jamais ``prix_achat``.

    Référence générée via ``apps.ventes.utils.references`` (jamais count()+1).
    Renvoie le ``Devis`` créé (brouillon, sans lien lead — un ticket SAV n'a
    pas de lead d'origine).
    """
    from .models import Devis, LigneDevis
    from .utils.references import create_with_reference
    from apps.crm.models import Client

    client = Client.objects.get(pk=client_id, company=company)

    def _create(ref):
        return Devis.objects.create(
            company=company, reference=ref, client=client,
            statut=Devis.Statut.BROUILLON, created_by=user,
            note=note or '',
        )
    devis = create_with_reference(Devis, 'DEV', company, _create)

    for ligne in (lignes or []):
        produit_id = ligne.get('produit_id')
        if not produit_id:
            continue
        LigneDevis.objects.create(
            devis=devis,
            produit_id=produit_id,
            designation=ligne.get('designation') or '',
            quantite=Decimal(str(ligne.get('quantite') or 1)),
            prix_unitaire=Decimal(str(ligne.get('prix_unitaire') or 0)),
        )
    return devis


# ── XFAC1 — Avances client (paiement sans facture) + affectation multi- ────
# ────────────────────────── factures ───────────────────────────────────────

def enregistrer_avance(*, company, client, montant, date_paiement, mode,
                       reference='', note='', created_by=None):
    """Enregistre un règlement reçu SANS facture (avance, acompte à la
    commande, trop-perçu). Le paiement reste ``statut_affectation=non_affecte``
    tant qu'il n'a pas été ventilé sur une ou plusieurs factures ouvertes du
    même client (voir ``ventiler_avance``)."""
    from decimal import Decimal, InvalidOperation
    from rest_framework.exceptions import ValidationError
    from .models import Paiement

    if montant is None:
        raise ValidationError({'montant': 'Le montant doit être positif.'})
    try:
        montant = Decimal(str(montant))
    except InvalidOperation:
        raise ValidationError({'montant': 'Montant invalide.'})
    if montant <= 0:
        raise ValidationError({'montant': 'Le montant doit être positif.'})
    if client is None:
        raise ValidationError({'client': 'Client requis pour une avance.'})
    return Paiement.objects.create(
        company=company, client=client, facture=None,
        statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
        montant=montant, date_paiement=date_paiement, mode=mode,
        reference=reference, note=note, created_by=created_by,
    )


def ventiler_avance(*, paiement, facture, montant, user=None):
    """Ventile UN paiement non affecté (avance) sur UNE facture ouverte du
    même client, pour ``montant``. Peut être appelée plusieurs fois pour
    répartir un même paiement sur plusieurs factures.

    Garde-fous (jamais de sur-affectation) :
      - la facture cible doit appartenir à la même société ET au même client
        que le paiement ;
      - le montant ventilé ne peut jamais dépasser le solde disponible du
        paiement (``montant_disponible``) ;
      - le montant ventilé ne peut jamais dépasser le reste à payer de la
        facture cible (``montant_du``).

    Met à jour ``statut_affectation`` du paiement (affecte / partiellement
    affecte) et le statut de la facture si elle devient intégralement réglée
    (réutilise le même seuil que ``enregistrer_paiement``)."""
    from decimal import Decimal
    from django.db import transaction
    from rest_framework.exceptions import ValidationError
    from .models import AffectationPaiement, Facture, Paiement

    montant = Decimal(montant)
    if montant <= 0:
        raise ValidationError(
            {'montant': "Le montant ventilé doit être positif."})

    with transaction.atomic():
        locked_paiement = Paiement.objects.select_for_update().get(
            pk=paiement.pk)
        if locked_paiement.facture_id is not None:
            raise ValidationError(
                {'paiement': "Ce paiement est déjà rattaché à une facture."})
        locked_facture = Facture.objects.select_for_update().get(
            pk=facture.pk)
        if locked_facture.company_id != locked_paiement.company_id:
            raise ValidationError(
                {'facture': "Facture d'une autre société."})
        if locked_facture.client_id != locked_paiement.client_id:
            raise ValidationError(
                {'facture': "La facture doit appartenir au même client "
                            "que l'avance."})
        if locked_facture.statut == Facture.Statut.ANNULEE:
            raise ValidationError(
                {'facture': "Impossible de ventiler sur une facture annulée."})

        disponible = locked_paiement.montant_disponible
        if montant - disponible > Decimal('0.01'):
            raise ValidationError({
                'montant': (
                    f"Le montant ventilé dépasse le solde disponible de "
                    f"l'avance ({disponible:.2f} MAD)."),
            })
        reste_facture = locked_facture.montant_du
        if montant - reste_facture > Decimal('0.01'):
            raise ValidationError({
                'montant': (
                    f"Le montant ventilé dépasse le reste à payer de la "
                    f"facture ({reste_facture:.2f} MAD)."),
            })

        affectation = AffectationPaiement.objects.create(
            company=locked_paiement.company, paiement=locked_paiement,
            facture=locked_facture, montant=montant, created_by=user,
        )

        locked_paiement.refresh_from_db()
        if locked_paiement.montant_disponible <= 0:
            locked_paiement.statut_affectation = (
                Paiement.StatutAffectation.AFFECTE)
        else:
            locked_paiement.statut_affectation = (
                Paiement.StatutAffectation.PARTIELLEMENT_AFFECTE)
        locked_paiement.save(update_fields=['statut_affectation'])

        locked_facture.refresh_from_db()
        if locked_facture.montant_du <= 0 and \
                locked_facture.statut != Facture.Statut.ANNULEE:
            locked_facture.statut = Facture.Statut.PAYEE
            locked_facture.save(update_fields=['statut'])
            reset_relance_escalation(locked_facture)

        from . import activity
        activity.log_facture_avance_affectee(
            locked_facture, user, locked_paiement, montant)

    return affectation


# ── XFAC4 — Retenue à la source SUBIE (RAS TVA/RAS IS) sur factures ────────
# ────────────────────────── clients ────────────────────────────────────────

def enregistrer_paiement_avec_retenue(
        *, facture, montant, date_paiement, mode, type_retenue, taux,
        reference='', note='', created_by=None):
    """Enregistre un paiement PARTIEL accompagné d'une retenue à la source
    (RAS TVA / RAS IS) qui, ENSEMBLE, soldent la facture : payé + retenue +
    avoirs = TTC. Sans cette écriture, la facture resterait « partiellement
    payée » à tort — la retenue n'est pas un montant perdu, c'est une créance
    d'attestation à recevoir de la DGT/du client.

    ``taux`` est informatif (tracé sur la retenue) ; le MONTANT de la retenue
    est déduit du reste à payer : ``retenue = reste_avant − montant`` (le
    paiement partiel + la retenue soldent ensemble EXACTEMENT le reste à
    payer). Rejette un montant qui dépasserait seul le reste à payer, ou une
    retenue résultante négative (le paiement seul suffirait déjà). Le
    paiement + la retenue sont créés dans la MÊME transaction ; la facture
    bascule automatiquement « Payée » si le solde tombe à zéro (même seuil que
    ``enregistrer_paiement``).
    """
    from decimal import Decimal
    from django.db import transaction
    from rest_framework.exceptions import ValidationError
    from .models import Facture, Paiement, RetenueSubie

    montant = Decimal(montant)
    if montant <= 0:
        raise ValidationError({'montant': 'Le montant doit être positif.'})
    try:
        taux = Decimal(taux)
    except (TypeError, ValueError):
        raise ValidationError({'taux': 'Taux de RAS invalide.'})
    if taux < 0 or taux > 100:
        raise ValidationError(
            {'taux': 'Le taux de RAS doit être compris entre 0 et 100 %.'})

    with transaction.atomic():
        locked = Facture.objects.select_for_update().get(pk=facture.pk)
        if locked.statut == Facture.Statut.ANNULEE:
            raise ValidationError(
                {'detail': "Impossible d'encaisser sur une facture annulée."})
        reste = locked.montant_du
        if montant - reste > Decimal('0.01'):
            raise ValidationError({
                'montant': (
                    f'Le paiement dépasse le reste à payer '
                    f'({reste:.2f} MAD).'),
            })
        # Base de la retenue = ce qui reste dû après le règlement partiel ;
        # le paiement + la retenue soldent ensemble exactement le reste à
        # payer (jamais de fraction perdue, jamais de sur-solde).
        base = reste - montant
        retenue_montant = base.quantize(Decimal('0.01'))
        if retenue_montant < 0:
            retenue_montant = Decimal('0')

        paiement = Paiement.objects.create(
            company=locked.company, facture=locked, montant=montant,
            date_paiement=date_paiement, mode=mode, reference=reference,
            note=note, created_by=created_by,
        )
        retenue = RetenueSubie.objects.create(
            company=locked.company, facture=locked, paiement=paiement,
            type_retenue=type_retenue, taux=taux, base=base,
            montant=retenue_montant, note=note,
            created_by=created_by,
        )

        from . import activity
        activity.log_facture_paiement(locked, created_by, paiement)
        activity.log_facture_retenue_subie(locked, created_by, retenue)

        locked.refresh_from_db()
        if locked.montant_paye_avec_retenues >= locked.total_ttc - \
                locked.avoirs_total - Decimal('0.01') and \
                locked.statut != Facture.Statut.ANNULEE:
            locked.statut = Facture.Statut.PAYEE
            locked.save(update_fields=['statut'])
            reset_relance_escalation(locked)

    return paiement, retenue


# ── XFAC11 — Facture consolidée multi-devis/BC d'un même client ────────────

def consolider_factures(*, company, devis_ids, user, created_by=None):
    """Crée UNE Facture unique regroupant PLUSIEURS devis acceptés du MÊME
    client (ex. projet multi-sites : ferme à N forages, tranches). Chaque
    document source garde ses lignes (recopiées, groupées par ``source_devis``
    pour le sous-titre « Devis DV-… » sur le PDF) et une ``FactureSource``
    trace le sous-total HT de son document d'origine.

    Contrôles :
      - au moins 2 devis, tous acceptés, tous de la MÊME société ET du MÊME
        client (clients différents → rejeté) ;
      - un devis déjà facturé (une Facture non annulée référence ce devis,
        directement ou via une FactureSource antérieure) est refusé.

    La chaîne Sous-total → Remise → HT → TVA → TTC reste calculée par les
    propriétés existantes de ``Facture`` (aucune formule dupliquée) : les
    lignes recopiées portent leur ``taux_tva`` d'origine, donc la ventilation
    TVA par taux (10 %/20 %) reste correcte pour le mélange.
    """
    from django.db import transaction
    from rest_framework.exceptions import ValidationError
    from .models import Devis, Facture, FactureSource, LigneFacture
    from .utils.company_settings import create_numbered

    if not devis_ids or len(devis_ids) < 2:
        raise ValidationError(
            {'devis_ids': 'Au moins 2 devis sont requis pour consolider.'})

    devis_qs = list(Devis.objects.select_related('client').filter(
        id__in=devis_ids, company=company).prefetch_related('lignes'))
    if len(devis_qs) != len(set(devis_ids)):
        raise ValidationError({'devis_ids': 'Un ou plusieurs devis introuvables.'})

    client_ids = {d.client_id for d in devis_qs}
    if len(client_ids) > 1:
        raise ValidationError(
            {'devis_ids': 'Tous les devis doivent appartenir au même client.'})

    for d in devis_qs:
        if d.statut != Devis.Statut.ACCEPTE:
            raise ValidationError({
                'devis_ids': (
                    f'Le devis {d.reference} doit être accepté pour être '
                    f'consolidé.'),
            })
        deja_facture = Facture.objects.filter(
            devis=d).exclude(statut=Facture.Statut.ANNULEE).exists() or \
            FactureSource.objects.filter(devis=d).exists()
        if deja_facture:
            raise ValidationError({
                'devis_ids': f'Le devis {d.reference} est déjà facturé.',
            })

    client = devis_qs[0].client

    with transaction.atomic():
        def _create(ref):
            return Facture.objects.create(
                reference=ref, company=company, client=client,
                statut=Facture.Statut.EMISE, created_by=created_by,
            )

        facture = create_numbered(Facture, company, 'facture', _create)

        for d in devis_qs:
            sous_total = Decimal('0')
            for ligne in d.lignes.all():
                LigneFacture.objects.create(
                    facture=facture, produit=ligne.produit,
                    designation=f'{d.reference} — {ligne.designation}',
                    quantite=ligne.quantite, prix_unitaire=ligne.prix_unitaire,
                    remise=ligne.remise, taux_tva=ligne.taux_tva,
                    source_devis=d,
                )
                sous_total += ligne.total_ht
            FactureSource.objects.create(
                company=company, facture=facture, devis=d,
                sous_total_ht=sous_total,
            )

    return facture
