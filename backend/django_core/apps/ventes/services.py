"""Services Ventes — point d'entrée cross-app pour les ÉCRITURES ventes.

Les apps tierces (sav, installations, crm…) passent par ces fonctions pour
créer ou modifier des entités ventes (Facture, Paiement…) au lieu d'importer
directement les models ventes. Cela respecte la règle de modularité (CLAUDE.md).
"""
from decimal import Decimal, ROUND_HALF_UP
import logging
import re

from apps.stock.services import qr_svg_for

logger = logging.getLogger(__name__)


def _add_months(d, months):
    """YSUBS9 — `d` décalée de `months` mois (jour recadré fin de mois).

    Fonction pure stdlib (pas de dépendance ajoutée), même calcul que
    `apps.sav.dateutils.add_months` mais gardée locale pour ne pas coupler
    `ventes` à `sav` pour une simple arithmétique de date."""
    if d is None or months is None:
        return None
    import calendar
    total = d.month - 1 + int(months)
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    from datetime import date
    return date(year, month, day)


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


def dupliquer_devis(devis, *, user):
    """NTUX13 — Duplique ``devis`` en un devis BROUILLON totalement
    INDÉPENDANT (nouveau numéro, jamais le statut de la source — même un
    devis ``accepte``/``envoye`` redémarre en ``brouillon``).

    À la différence de ``dupliquer-variante`` (QJ15, ``views/devis.py``) qui
    groupe ses copies avec l'original via ``version_parent``/``version`` pour
    une comparaison côte-à-côte, CE duplicata est délibérément SANS lien de
    version : ``version=1``, ``version_parent=None``. Aucun chantier/
    BonCommande/Facture n'est jamais copié — ces objets naissent en aval d'un
    devis ACCEPTÉ (rule #4) et ne sont référencés nulle part sur ``Devis``
    lui-même, donc un brouillon frais n'en hérite jamais.

    Les lignes sont clonées à l'identique (mêmes quantités/prix/sections)."""
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.utils.company_settings import create_numbered

    company = devis.company
    holder = {}

    def _save(ref):
        obj = Devis.objects.create(
            company=company, reference=ref,
            client=devis.client, lead=devis.lead,
            statut=Devis.Statut.BROUILLON,
            taux_tva=devis.taux_tva,
            remise_globale=devis.remise_globale,
            note=(f'[Copie de {devis.reference}] ' + (devis.note or '')).strip(),
            mode_installation=devis.mode_installation,
            etude_params=devis.etude_params,
            prix_cible_kwc=devis.prix_cible_kwc,
            devise=devis.devise,
            taux_change=devis.taux_change,
            created_by=user,
            # Duplicata indépendant : jamais de groupe de version (à la
            # différence de dupliquer-variante, QJ15).
            version=1, version_parent=None, is_active=True,
        )
        holder['obj'] = obj
        return obj

    create_numbered(Devis, company, 'devis', _save)
    copie = holder['obj']

    for ligne in devis.lignes.all():
        LigneDevis.objects.create(
            devis=copie, produit=ligne.produit, designation=ligne.designation,
            quantite=ligne.quantite, prix_unitaire=ligne.prix_unitaire,
            remise=ligne.remise, type_ligne=ligne.type_ligne, ordre=ligne.ordre,
            taux_tva=ligne.taux_tva, groupe_index=ligne.groupe_index,
            groupe_label=ligne.groupe_label,
        )
    logger.info('NTUX13: devis %s dupliqué en %s (company %s)',
                devis.reference, copie.reference, getattr(company, 'id', '?'))
    return copie


def create_devis_from_reserve(*, reserve, user):
    """XFSM18 — crée un DEVIS brouillon de réparation à partir d'une réserve
    d'intervention (`installations.Reserve`), pour donner un chemin de devis
    payant au pipeline de réparation.

    Le client est celui du CHANTIER (`reserve.intervention.installation.client`,
    déjà résolu — aucune re-résolution lead nécessaire ici, à la différence de
    `create_draft_devis_from_ocr`). La description est pré-remplie depuis la
    réserve ; aucune ligne n'est créée (une LigneDevis exige un Produit du
    catalogue) — le devis brouillon est laissé à compléter dans l'éditeur.

    Le devis reste ``brouillon`` : ce service CRÉE, il ne change aucun statut
    aval (règle #4). Aucun impact sur `/proposal`.
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.references import create_with_reference

    installation = reserve.intervention.installation
    if installation is None or installation.client_id is None:
        raise ValueError(
            "create_devis_from_reserve requires a reserve whose intervention "
            "is attached to a chantier with a resolved client")
    client = installation.client
    company = reserve.company or installation.company

    description = (reserve.description or '').strip()
    note_lines = ["Devis de réparation généré depuis une réserve d'intervention."]
    if description:
        note_lines.append(f"Description : {description}")
    if reserve.photo_id:
        note_lines.append(f"Photo référencée : pièce jointe #{reserve.photo_id}")
    note = "\n".join(note_lines)

    def _create(ref):
        return Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            statut=Devis.Statut.BROUILLON,
            created_by=user,
            note=note,
        )

    devis = create_with_reference(Devis, 'DEV', company, _create)
    logger.info(
        'XFSM18: devis de réparation %s créé depuis la réserve %s (company %s)',
        devis.reference, reserve.id, getattr(company, 'id', '?'))
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
    ``result`` ``{count, kwc, areaM2}`` (PV14 : à défaut, le bloc ``geometry``
    par pan de la sérialisation v1) — et en agrège :

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
        # PV14 — les layouts DÉJÀ STOCKÉS (sérialisation roofPro11 v1) ne
        # portent PAS de bloc ``result`` par pan : la puissance et le compte
        # RÉELS y vivent dans le bloc ``geometry`` de la zone (WJ24 :
        # {azimuthDeg, tiltDeg, family, flush, kwc, count, origin, panels}).
        # Sans cette lecture un tel blob remontait 0 kWc — et le devis
        # reconstruit perdait le wattage panneau (aucun watt déductible, donc
        # plus de choix de produit à wattage exact). L'ordre est STRICT :
        # ``result`` d'abord (comportement historique inchangé au bit près),
        # ``geometry`` ensuite, ``neededPanels`` en tout dernier recours (le
        # compte SOUHAITÉ, pas le compte POSÉ).
        geo = a.get('geometry')
        if not isinstance(geo, dict):
            geo = {}
        count = int(res.get('count') or geo.get('count')
                    or a.get('neededPanels') or 0)
        kwc = float(res.get('kwc') or geo.get('kwc') or 0.0)
        surface = float(res.get('areaM2') or geo.get('areaM2')
                        or a.get('areaM2') or 0.0)
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


# ── PV16 — la CIBLE de calepinage se lit dans les LIGNES du devis ───────────
#
# L'écran de conception 3D doit repartir de ce que le devis DIT AUJOURD'HUI
# (combien de panneaux, quelle puissance unitaire, quel scénario), pas d'un
# blob de layout qui peut être absent, périmé ou d'une version antérieure de
# l'outil. Les lignes du devis, elles, sont la source vivante — c'est ce qui a
# été chiffré et, pour un devis envoyé, ce que le client a sous les yeux.
#
# Fonction PURE de lecture : elle ne touche NI le statut, NI les lignes, NI
# l'étude. Elle expose ses doutes plutôt que de les cacher — d'où la liste
# ``avertissements`` en français, affichable telle quelle.

#: Wattage retenu quand plus rien n'est lisible (panneau catalogue courant).
CIBLE_WATT_DEFAUT = 550


def _lignes_produit(devis):
    """Lignes PRODUIT d'un devis — les sections/notes n'en sont pas.

    Une ligne de SECTION/NOTE (XSAL14) ne porte ni produit, ni prix, ni
    quantité : elle ne peut donc ni compter dans une cible ni recevoir un
    écart de calepinage.
    """
    if devis is None:
        return []
    return [ligne for ligne in devis.lignes.all()
            if getattr(ligne, 'type_ligne', 'produit') == 'produit']


def _classe_ligne(ligne, predicat):
    """Classe une ligne sur sa DÉSIGNATION, à défaut sur le nom du produit.

    La désignation est ce que lit ``quote_engine/builder.py`` (contrat
    d'alignement des mots-clés, CLAUDE.md règle #4) ; le nom du produit n'est
    consulté qu'en second, pour rattraper une désignation réécrite à la main
    (« Modules PV posés » sur un produit « Panneau Jinko 550W »).
    """
    return (predicat(ligne.designation or '')
            or predicat(getattr(ligne.produit, 'nom', '') or ''))


def _pmax_wc_du_produit(produit):
    """Pmax (Wc) de la fiche technique d'un produit, ou ``None``.

    Passe par ``apps.stock.selectors.specs_for_produit`` — le point d'entrée
    cross-app SANCTIONNÉ pour lire une ``FicheTechnique`` (jamais un import de
    ``apps.stock.models`` ici). Ce sélecteur peut ne pas encore exister dans
    l'arbre : son absence est un NON-ÉVÉNEMENT (on retombe simplement sur la
    lecture du wattage dans le libellé), jamais une exception.
    """
    if produit is None:
        return None
    try:
        from apps.stock import selectors as _stock_selectors
    except Exception:  # noqa: BLE001 — app absente / import cassé : on ignore
        return None
    lire = getattr(_stock_selectors, 'specs_for_produit', None)
    if lire is None:
        return None
    try:
        specs = lire(produit)
    except TypeError:
        # Le sélecteur peut attendre un id plutôt que l'objet.
        try:
            specs = lire(getattr(produit, 'id', None))
        except Exception:  # noqa: BLE001
            return None
    except Exception:  # noqa: BLE001
        return None
    if specs is None:
        return None
    pmax = (specs.get('pmax_wc') if isinstance(specs, dict)
            else getattr(specs, 'pmax_wc', None))
    try:
        pmax = int(round(float(pmax)))
    except (TypeError, ValueError):
        return None
    return pmax if pmax > 0 else None


def cible_depuis_lignes(devis):
    """PV16 — cible de calepinage LUE DANS LES LIGNES du devis.

    Rend toujours le même dict, quelles que soient les données :

        {panneaux, kwc, panel_watt, scenario, batterie, avertissements}

    * ``panneaux`` — somme des quantités des lignes classées « panneau » par le
      classifieur partagé ``_is_panel`` (aligné sur ``quote_engine/builder.py``).
      Les lignes de SECTION/NOTE (sans prix ni quantité) sont ignorées.
    * ``panel_watt`` — wattage unitaire, dans cet ordre : la fiche technique du
      produit dominant (``pmax_wc``), sinon le wattage lu dans le libellé
      (désignation puis nom du produit), sinon déduit du kWc de l'étude, sinon
      ``CIBLE_WATT_DEFAUT`` — et là SEULEMENT un avertissement est levé.
    * ``kwc`` — puissance recalculée DEPUIS LES LIGNES (``panneaux × watt``),
      pas recopiée de l'étude : c'est le devis qui fait foi ici, pas un
      paramètre d'étude qui a pu se désynchroniser.
    * ``scenario`` — ``avec_batterie`` dès qu'une batterie est présente, sinon
      ``hybride`` si un onduleur hybride l'est, sinon ``reseau`` (défaut
      résidentiel, même arbitrage que ``build_devis_from_layout``).
    * ``avertissements`` — messages FRANÇAIS affichables tels quels.

    LECTURE PURE : aucun statut, aucune ligne, aucune étude n'est écrite.
    """
    lignes = _lignes_produit(devis)

    def _nom(ligne):
        return ligne.designation or getattr(ligne.produit, 'nom', '') or ''

    lignes_panneau = [li for li in lignes if _classe_ligne(li, _is_panel)]
    panneaux = 0
    for ligne in lignes_panneau:
        try:
            # ArithmeticError couvre decimal.InvalidOperation.
            panneaux += int(Decimal(str(ligne.quantite or 0)))
        except (ArithmeticError, TypeError, ValueError):
            continue

    batterie = any(_classe_ligne(li, _is_battery) for li in lignes)
    hybride = any(_classe_ligne(li, _is_hybrid_inverter) for li in lignes)
    if batterie:
        scenario = 'avec_batterie'
    elif hybride:
        scenario = 'hybride'
    else:
        scenario = 'reseau'

    avertissements = []
    if not lignes_panneau:
        avertissements.append(
            'Aucune ligne de panneau dans ce devis : la cible de calepinage '
            'est vide. Ajoutez les panneaux au devis avant de concevoir la '
            'toiture.')

    # Ligne dominante = la plus GROSSE quantité : c'est elle qui porte le
    # wattage de référence, et c'est elle que PV18 ajustera en cas d'écart.
    dominante = None
    if lignes_panneau:
        dominante = max(
            lignes_panneau,
            key=lambda li: Decimal(str(li.quantite or 0)))

    # Deux modèles de panneau différents dans un même devis : le calepinage ne
    # sait pas répartir l'écart — on le DIT au lieu de choisir en silence.
    identites = {
        (li.produit_id, (li.designation or '').strip().lower())
        for li in lignes_panneau
    }
    if len(identites) > 1:
        avertissements.append(
            'Ce devis porte %d modèles de panneau différents : l\'écart de '
            'calepinage sera appliqué à la ligne la plus grosse (« %s »).'
            % (len(identites), _nom(dominante)))

    panel_watt = None
    if dominante is not None:
        panel_watt = _pmax_wc_du_produit(dominante.produit)
        if not panel_watt:
            panel_watt = (_parse_watt(dominante.designation or '')
                          or _parse_watt(
                              getattr(dominante.produit, 'nom', '') or ''))

    if not panel_watt and panneaux > 0:
        # Dernier repli chiffré : la puissance de l'étude, divisée par le
        # nombre de panneaux réellement en ligne.
        etude = getattr(devis, 'etude_params', None) or {}
        try:
            kwc_etude = float(etude.get('puissance_kwc') or 0)
        except (TypeError, ValueError):
            kwc_etude = 0.0
        if kwc_etude > 0:
            panel_watt = int(round(kwc_etude * 1000 / panneaux / 10) * 10)

    if not panel_watt:
        panel_watt = CIBLE_WATT_DEFAUT
        if lignes_panneau:
            avertissements.append(
                'Puissance unitaire du panneau illisible (ni fiche technique '
                'ni wattage dans le libellé) : %d Wc retenus par défaut.'
                % CIBLE_WATT_DEFAUT)

    kwc = round(panneaux * panel_watt / 1000.0, 3) if panneaux else 0.0

    return {
        'panneaux': panneaux,
        'kwc': kwc,
        'panel_watt': int(panel_watt),
        'scenario': scenario,
        'batterie': bool(batterie),
        'avertissements': avertissements,
    }


# ── AOF164 — bascule du calcul résidentiel sur le MOTEUR PARTAGÉ ────────────
#
# Le compte de panneaux du devis résidentiel vient aujourd'hui du cerveau
# TypeScript de roofPro11 (``layout['result']['panels']``). Le moteur
# ``core/calepinage`` sait faire le même travail, en exact et avec sa preuve —
# mais on ne remplace pas un calcul en production sur une intuition : la
# bascule vit derrière un DRAPEAU (défaut OFF) et se juge sur des écarts
# JOURNALISÉS, pas sur une conviction.
#
# Trois invariants tiennent cette tâche :
#   * drapeau OFF -> comportement BIT-IDENTIQUE (retour immédiat, avant tout
#     appel moteur et avant toute écriture de journal) ;
#   * un devis DÉJÀ ÉMIS n'est jamais recalculé (voir
#     ``apps.ventes.selectors.comparaison_calepinage_devis``) ;
#   * une panne du moteur ne fait JAMAIS échouer une création de devis : on
#     journalise et on garde le compte historique.
#
# Les mots-clés de classification (panneau / onduleur réseau|injection|hybride
# / batterie) ne bougent pas : ils sont le contrat d'alignement avec
# ``quote_engine/builder.py`` dont dépend le découpage des options du PDF
# (CLAUDE.md, règle #4). Cette tâche ne touche QUE le COMPTE.

#: Nom du drapeau — lu par ``getattr`` pour que l'ABSENCE du réglage vaille OFF.
DRAPEAU_MOTEUR_CALEPINAGE = 'USE_MOTEUR_CALEPINAGE'


def moteur_calepinage_actif():
    """Le drapeau de bascule est-il levé ? ABSENT = OFF (jamais l'inverse)."""
    from django.conf import settings

    return bool(getattr(settings, DRAPEAU_MOTEUR_CALEPINAGE, False))


def _zone_villa_depuis_pan(pan):
    """``AreaRecord`` roofPro11 -> ``AreaRecord`` attendu par l'adaptateur villa.

    roofPro11 sérialise ``vertices: LngLat[]`` (``[lng, lat]``) et des obstacles
    ``{centerLng, centerLat, lengthM (nord-sud), widthM (est-ouest)}``.
    L'adaptateur d'AOF162 attend ``polygon`` / ``center`` / ``widthM`` /
    ``heightM`` avec ``heightM`` = étendue NORD-SUD : la correspondance est
    faite ICI, explicitement, et jamais devinée ailleurs.

    Rend ``None`` quand le pan ne porte pas de contour exploitable — un layout
    sans géométrie n'est pas une erreur, c'est simplement un cas où le moteur
    n'a rien à dire.
    """
    if not isinstance(pan, dict):
        return None
    sommets = pan.get('vertices') or pan.get('polygon') or pan.get('points')
    if not isinstance(sommets, (list, tuple)) or len(sommets) < 3:
        return None

    obstacles = []
    for brut in (pan.get('obstacles') or ()):
        if not isinstance(brut, dict):
            continue
        lng = brut.get('centerLng')
        lat = brut.get('centerLat')
        if lng is None or lat is None:
            continue
        obstacles.append({
            'id': brut.get('id') or 'OBS',
            'center': [lng, lat],
            # widthM = est-ouest (axe x du moteur villa) ;
            # lengthM = nord-sud (axe y).
            'widthM': brut.get('widthM') or 1.0,
            'heightM': brut.get('lengthM') or brut.get('heightM') or 1.0,
        })

    type_toit = (pan.get('roofType') or '').lower()
    pente = pan.get('pitchDeg')
    if pente is None:
        pente = pan.get('pitch') or 0.0
    azimut = pan.get('facingAzimuthDeg')
    if azimut is None:
        azimut = pan.get('aspect')
    return {
        'id': str(pan.get('id') or pan.get('label') or 'ZONE'),
        'polygon': [list(p) for p in sommets],
        'flat': type_toit != 'pitched',
        'tilt': float(pente or 0.0),
        'azimuth': float(azimut if azimut is not None else 180.0),
        'obstacles': obstacles,
    }


def compte_moteur_du_layout(layout):
    """Compte de modules rendu par le MOTEUR pour ce layout, ou ``None``.

    Somme les pans : chacun passe par ``apps.ao.selectors.calepinage_villa``
    (lecture cross-app sanctionnée — jamais ``apps.ao.models``), qui délègue au
    moteur partagé d'AOF163. Aucune ligne AO n'est créée.

    Rend ``None`` (et jamais une exception) dès que la géométrie manque ou que
    le moteur refuse : l'appelant garde alors le compte historique.
    """
    pans = ((layout or {}).get('areas') or (layout or {}).get('zones')
            or (layout or {}).get('pans') or [])
    if not isinstance(pans, list) or not pans:
        return None

    from apps.ao.selectors import calepinage_villa

    modules = 0
    detail = []
    for pan in pans:
        zone = _zone_villa_depuis_pan(pan)
        if zone is None:
            continue
        try:
            sortie = calepinage_villa(zone, ordre='lnglat')
        except Exception:
            logger.warning(
                'AOF164: le moteur a refusé le pan %s — compte historique '
                'conservé pour ce pan', zone.get('id'), exc_info=True)
            continue
        resultat = sortie['resultat']
        modules += int(resultat.modules)
        detail.append({
            'zone': zone['id'],
            'modules': int(resultat.modules),
            'hash_entree': resultat.hash_entree,
            'version_moteur': resultat.version_moteur,
            'methode': sortie['preuve']['methode'],
            'compte_optimal': sortie['preuve']['compte_optimal'],
        })
    if not detail:
        return None
    return {'modules': modules, 'pans': tuple(detail)}


def arbitrer_compte_calepinage(layout, compte_historique):
    """Compare ancien et nouveau compte et JOURNALISE l'écart, ou rend ``None``.

    ``None`` signifie « ne change rien » : drapeau baissé (cas par défaut,
    retour AVANT tout calcul et tout journal) ou moteur sans réponse.
    Sinon rend ``{'ancien', 'nouveau', 'ecart', 'retenu', 'pans'}`` où
    ``retenu`` est le compte du MOTEUR — c'est le sens même de la bascule.
    """
    if not moteur_calepinage_actif():
        return None
    try:
        mesure = compte_moteur_du_layout(layout)
    except Exception:
        # Une panne du moteur ne fait JAMAIS échouer une création de devis :
        # on journalise et on garde le compte historique.
        logger.warning('AOF164: moteur indisponible — compte historique '
                       'conservé pour ce devis', exc_info=True)
        return None
    if mesure is None:
        return None
    ancien = int(compte_historique or 0)
    nouveau = int(mesure['modules'])
    ecart = nouveau - ancien
    logger.info(
        'AOF164: bascule moteur ACTIVE — compte TypeScript %d, compte moteur '
        '%d, écart %+d (%d pan(s) calepiné(s))',
        ancien, nouveau, ecart, len(mesure['pans']))
    return {'ancien': ancien, 'nouveau': nouveau, 'ecart': ecart,
            'retenu': nouveau, 'pans': mesure['pans']}


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

    # AOF164 — BASCULE A/B sur le moteur de calepinage partagé, derrière le
    # drapeau ``USE_MOTEUR_CALEPINAGE`` (défaut OFF). Drapeau OFF : la fonction
    # rend ``None`` AVANT tout calcul — aucun appel moteur, aucun journal,
    # comportement bit-identique à aujourd'hui. Drapeau ON : le compte vient du
    # moteur et l'écart ancien/nouveau est journalisé pour arbitrage.
    arbitrage = arbitrer_compte_calepinage(layout, nb_panneaux)
    if arbitrage is not None and arbitrage['retenu'] != nb_panneaux:
        watt_reference = layout.get('panelWatt') or layout.get('watt')
        if not watt_reference and nb_panneaux and kwc:
            watt_reference = kwc * 1000.0 / nb_panneaux
        nb_panneaux = arbitrage['retenu']
        # Le kWc SUIT le compte : laisser l'ancien kWc face au nouveau compte
        # produirait un devis dont la puissance ne correspond plus aux panneaux.
        if watt_reference:
            kwc = round(nb_panneaux * float(watt_reference) / 1000.0, 3)

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
    # QX23be — fige la marge interne dès la création (manager-only).
    refresh_marge_snapshot(devis)
    logger.info(
        'Q3/QJ21: devis %s built from layout (%d lignes, %.2f kWc, %d pans, company %s)',
        devis.reference, len(line_specs), kwc,
        len(toiture.get('pans', [])) if toiture else 0,
        getattr(company, 'id', '?'))
    return devis


# ── PV18 — RESYNCHRONISER un devis existant sur un nouveau calepinage ───────
#
# `build_devis_from_layout` CRÉE un devis. Ici on en MET À JOUR un qui existe
# déjà, et la différence est tout le sujet : un devis vivant porte des prix
# négociés, des remises, des sections, des notes, un ordre d'affichage et des
# groupes multi-villa que personne n'a le droit de perdre parce que la toiture a
# bougé de deux panneaux. La mise à jour est donc CHIRURGICALE — on touche les
# quantités de panneaux et la présence de la batterie, RIEN d'autre — et jamais,
# sous aucune condition, le STATUT (règle #4 : ce chemin LIT les statuts, il ne
# les écrit pas ; `save(update_fields=...)` ci-dessous le rend structurel).


class SyncLayoutError(Exception):
    """Le devis n'est pas dans un état où son calepinage peut être resynchronisé.

    ``revision_possible`` distingue les deux refus : un devis ENVOYÉ peut être
    révisé (une nouvelle version repart en brouillon), un devis
    accepté/refusé/expiré est clos.
    """

    def __init__(self, detail, *, revision_possible=False):
        super().__init__(detail)
        self.detail = detail
        self.revision_possible = revision_possible


def _cible_panneaux_du_layout(layout, toiture):
    """Nombre de panneaux VOULU par un layout (même lecture que la création)."""
    result = dict((layout or {}).get('result') or {})
    cible = int(result.get('panels') or result.get('count') or 0)
    if cible <= 0 and toiture.get('nb_panneaux'):
        cible = int(toiture['nb_panneaux'])
    return cible


def _watt_du_layout(layout, toiture, cible_panneaux):
    """Wattage unitaire annoncé par le layout, ou déduit de son kWc."""
    watt = (layout or {}).get('panelWatt') or (layout or {}).get('watt')
    if watt:
        try:
            return int(round(float(watt)))
        except (TypeError, ValueError):
            pass
    result = dict((layout or {}).get('result') or {})
    kwc = float(result.get('kwc') or toiture.get('kwc') or 0.0)
    if kwc and cible_panneaux:
        return int(round(kwc * 1000 / cible_panneaux / 10) * 10)
    return CIBLE_WATT_DEFAUT


def sync_devis_from_layout(devis, layout, user=None):
    """PV18 — aligne les LIGNES d'un devis brouillon sur un nouveau calepinage.

    Sous ``transaction.atomic()`` + ``select_for_update`` sur la ligne du devis
    (deux commerciaux sur le même devis ne peuvent pas s'écraser l'un l'autre).

    Comportement par statut — le statut est LU, JAMAIS écrit (règle #4) :

    * ``brouillon`` — mise à jour chirurgicale (voir plus bas) ;
    * ``envoye``    — ``SyncLayoutError(revision_possible=True)`` : le client a
      déjà cette version sous les yeux, le bon geste est « Réviser » ;
    * ``accepte`` / ``refuse`` / ``expire`` — ``SyncLayoutError`` : document
      clos, aucune révision de calepinage possible.

    Mise à jour chirurgicale, sur un brouillon :

    * les lignes PANNEAU sont portées au compte du layout ; quand il y en a
      plusieurs, l'écart va sur la PLUS GROSSE seule (les autres, souvent une
      seconde marque ou un second pan négocié, ne bougent pas) ;
    * aucune ligne panneau et un compte à poser → UNE ligne est créée depuis le
      catalogue au wattage du layout (``_pick_product``, catalogue société OU
      global, jamais un produit sans prix) ;
    * la BATTERIE suit le scénario : ajoutée si le layout en veut une et qu'il
      n'y en a pas, supprimée s'il n'en veut plus ;
    * TOUT le reste est intact — prix unitaires, remises, TVA de ligne,
      sections, notes, ordre d'affichage, groupes multi-villa, et les produits
      des lignes non touchées ne sont JAMAIS re-choisis ;
    * ``roof_layout`` / ``layout_hash`` sont re-posés, et ``etude_params`` ne
      reçoit que ``puissance_kwc`` / ``production_annuelle`` /
      ``economies_annuelles`` / ``toiture`` — les champs d'étude du générateur
      (autoconsommation, payback, pompe…) ne sont jamais touchés.

    Re-soumettre le MÊME layout (même empreinte) ne fait AUCUNE écriture et
    renvoie ``inchange=True``.

    Renvoie toujours le même dict :
    ``{inchange, panneaux, kwc, scenario, batterie, lignes_modifiees,
    avertissements}``.
    """
    from django.db import transaction

    from apps.ventes.models import Devis, LigneDevis

    layout = layout if isinstance(layout, dict) else {}
    nouveau_hash = layout_hash(layout)
    toiture = extract_roof_config(layout)
    cible_panneaux = _cible_panneaux_du_layout(layout, toiture)
    watt = _watt_du_layout(layout, toiture, cible_panneaux)

    scenario_brut = (layout.get('scenario') or '').lower()
    veut_batterie = ('batterie' in scenario_brut or 'hybride' in scenario_brut
                     or bool(layout.get('battery')))

    with transaction.atomic():
        verrou = (Devis.objects.select_for_update()
                  .filter(pk=getattr(devis, 'pk', None)).first())
        if verrou is None:
            raise SyncLayoutError('Devis introuvable.')

        # ── Garde de statut : LECTURE du statut, jamais une écriture ──
        if verrou.statut == Devis.Statut.ENVOYE:
            raise SyncLayoutError(
                'Devis « Envoyé » : le client a déjà cette version sous les '
                'yeux. Créez une révision (« Réviser ») pour en changer le '
                'calepinage.',
                revision_possible=True)
        if verrou.statut != Devis.Statut.BROUILLON:
            raise SyncLayoutError(
                'Devis « %s » : son calepinage est figé, ce document est '
                'clos.' % verrou.get_statut_display(),
                revision_possible=False)

        lignes = _lignes_produit(verrou)
        lignes_panneau = [li for li in lignes
                          if _classe_ligne(li, _is_panel)]
        lignes_batterie = [li for li in lignes
                           if _classe_ligne(li, _is_battery)]
        a_batterie = bool(lignes_batterie)
        total_panneaux = sum(int(li.quantite or 0) for li in lignes_panneau)

        avertissements = []
        # Cohérence avec PV17 : ces deux cas y sont déclarés NON modifiables.
        if verrou.mode_installation == Devis.ModeInstallation.AGRICOLE:
            avertissements.append(
                'Devis agricole (pompage) — le calepinage de toiture ne '
                's\'applique pas.')
        if verrou.lignes.filter(groupe_index__gte=1).exists():
            avertissements.append(
                'Devis multi-villa : l\'écart de calepinage porte sur la ligne '
                'de panneaux la plus grosse, tous groupes confondus.')

        # ── Court-circuit : même géométrie → ZÉRO écriture ──
        if nouveau_hash and verrou.layout_hash == nouveau_hash:
            return {
                'inchange': True,
                'panneaux': total_panneaux,
                'kwc': round(total_panneaux * watt / 1000.0, 3),
                'scenario': 'avec_batterie' if a_batterie else 'reseau',
                'batterie': a_batterie,
                'lignes_modifiees': 0,
                'avertissements': avertissements,
            }

        lignes_modifiees = 0

        # ── Panneaux : porter le compte à la cible ──
        if cible_panneaux > 0 and not lignes_panneau:
            panneau = _pick_product(verrou.company, _is_panel, watt=watt)
            if panneau is None:
                avertissements.append(
                    'Aucun panneau tarifé au catalogue : la ligne de panneaux '
                    'n\'a pas pu être créée. Ajoutez un panneau tarifé.')
            else:
                LigneDevis.objects.create(
                    devis=verrou, produit=panneau, designation=panneau.nom,
                    quantite=Decimal(str(cible_panneaux)),
                    prix_unitaire=Decimal(panneau.prix_vente),
                    remise=Decimal('0'))
                lignes_modifiees += 1
                total_panneaux = cible_panneaux
        elif cible_panneaux <= 0:
            # Un layout sans compte de panneaux ne DÉTRUIT pas les lignes en
            # place : « 0 » veut dire « inconnu », pas « enlève tout ».
            avertissements.append(
                'Ce calepinage ne porte aucun panneau : les lignes de '
                'panneaux du devis n\'ont pas été modifiées.')
        elif lignes_panneau and cible_panneaux != total_panneaux:
            # L'écart va sur la PLUS GROSSE ligne, elle seule : les autres
            # lignes panneau restent telles que le commercial les a posées.
            dominante = max(lignes_panneau,
                            key=lambda li: Decimal(str(li.quantite or 0)))
            ecart = cible_panneaux - total_panneaux
            nouvelle = int(dominante.quantite or 0) + ecart
            if nouvelle < 0:
                # Un retrait plus grand que la ligne dominante : on ne descend
                # jamais sous zéro (et le compte final est renvoyé tel quel).
                nouvelle = 0
                avertissements.append(
                    'Le retrait demandé dépasse la plus grosse ligne de '
                    'panneaux : elle a été ramenée à 0, les autres lignes '
                    'n\'ont pas été touchées.')
            dominante.quantite = Decimal(str(nouvelle))
            dominante.save(update_fields=['quantite'])
            lignes_modifiees += 1
            total_panneaux = sum(
                int(li.quantite or 0) for li in lignes_panneau)

        # ── Batterie : présente si (et seulement si) le layout en veut une ──
        if veut_batterie and not a_batterie:
            batterie = _pick_product(verrou.company, _is_battery)
            if batterie is None:
                avertissements.append(
                    'Aucune batterie tarifée au catalogue : la ligne batterie '
                    'n\'a pas pu être ajoutée. Ajoutez une batterie tarifée.')
            else:
                LigneDevis.objects.create(
                    devis=verrou, produit=batterie, designation=batterie.nom,
                    quantite=Decimal('1'),
                    prix_unitaire=Decimal(batterie.prix_vente),
                    remise=Decimal('0'))
                lignes_modifiees += 1
                a_batterie = True
        elif not veut_batterie and a_batterie:
            for ligne in lignes_batterie:
                ligne.delete()
            lignes_modifiees += len(lignes_batterie)
            a_batterie = False

        # ── Étude : QUATRE clés, jamais les champs d'étude du générateur ──
        result = dict(layout.get('result') or {})
        kwc = float(result.get('kwc') or toiture.get('kwc') or 0.0)
        if not kwc and total_panneaux:
            kwc = round(total_panneaux * watt / 1000.0, 3)
        etude = dict(verrou.etude_params or {})
        if result.get('annualKwh') is not None:
            etude['production_annuelle'] = int(result['annualKwh'])
        if result.get('savings') is not None:
            etude['economies_annuelles'] = int(result['savings'])
        if kwc:
            etude['puissance_kwc'] = kwc
        if toiture:
            etude['toiture'] = toiture

        # QJ21 — le layout stocké porte la géométrie par pan DÉJÀ traitée, pour
        # que ses consommateurs n'aient pas à ré-extraire. Copie, jamais une
        # mutation du dict de l'appelant. L'empreinte, elle, est calculée sur
        # le layout D'ORIGINE (clés géométriques seules) : cet enrichissement
        # ne peut donc pas casser le court-circuit au prochain envoi.
        layout_stocke = dict(layout)
        if toiture and toiture.get('pans'):
            layout_stocke['_pans_geometry'] = toiture['pans']

        verrou.roof_layout = layout_stocke
        verrou.layout_hash = nouveau_hash or verrou.layout_hash
        verrou.etude_params = etude
        # `update_fields` EXCLUT `statut` : le statut ne peut pas partir d'ici,
        # même par accident (règle #4).
        verrou.save(update_fields=[
            'roof_layout', 'layout_hash', 'etude_params'])

        logger.info(
            'PV18: devis %s resynchronisé sur son calepinage (%d panneaux, '
            '%.2f kWc, %d ligne(s) touchée(s), société %s, par %s)',
            verrou.reference, total_panneaux, kwc, lignes_modifiees,
            getattr(verrou.company, 'id', '?'),
            getattr(user, 'username', '?'))

        return {
            'inchange': False,
            'panneaux': total_panneaux,
            'kwc': kwc,
            'scenario': 'avec_batterie' if a_batterie else 'reseau',
            'batterie': a_batterie,
            'lignes_modifiees': lignes_modifiees,
            'avertissements': avertissements,
        }


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


def activate_optional_line(*, devis, ligne_id, user=None):
    """XSAL5 — active une ligne OPTIONNELLE d'un devis (self-service client sur
    la proposition, ou vendeur en interne).

    Bascule ``optionnelle=False`` sur la ligne existante : elle devient une
    ligne normale et entre alors dans les totaux (HT/TVA/TTC) et les documents
    avals. Ne CRÉE ni ne DUPLIQUE jamais de ligne. Company-scopé : la ligne doit
    appartenir au ``devis`` fourni (déjà borné à sa société par l'appelant / le
    jeton public). Idempotent : ré-activer une ligne déjà active est un no-op
    silencieux (aucun second chatter). Verrou anti-course (select_for_update).

    Seul un devis encore vivant (brouillon / envoyé) peut voir ses options
    activées — après acceptation, le contenu est figé (règle #4, chaîne de
    statuts préservée). Consigne le chatter du devis.

    Renvoie la ``LigneDevis`` mise à jour, ou lève ``AcceptError`` (statut
    figé) / renvoie None si la ligne est introuvable ou n'est pas optionnelle.
    """
    from django.db import transaction
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes import activity

    with transaction.atomic():
        try:
            ligne = (LigneDevis.objects
                     .select_for_update()
                     .select_related('devis')
                     .get(pk=ligne_id, devis=devis))
        except LigneDevis.DoesNotExist:
            return None

        # Devis figé (accepté/refusé/expiré) : les options ne sont plus
        # activables (le contenu est verrouillé — règle #4).
        if ligne.devis.statut not in (
                Devis.Statut.BROUILLON, Devis.Statut.ENVOYE):
            raise AcceptError(
                'Ce devis est figé — ses options ne sont plus modifiables.',
                conflict=True)

        # Idempotent : ligne non optionnelle (jamais optionnelle, ou déjà
        # activée) → no-op silencieux, aucun second chatter.
        if not ligne.optionnelle:
            return ligne

        ligne.optionnelle = False
        ligne.save(update_fields=['optionnelle'])

    # Chatter (hors transaction — miroir de accept_devis).
    try:
        activity.log_devis_note(
            devis, user,
            f'Option activée par le client : « {ligne.designation} » '
            '— désormais incluse dans le total.')
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        pass
    return ligne


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
    # QX10 — un nouveau code réinitialise le compteur de tentatives (brute-force).
    cache.delete(_otp_attempts_key(link.token))

    devis = link.devis
    client = getattr(devis, 'client', None)
    phone = (getattr(client, 'telephone', '') or '').strip()
    email = (getattr(client, 'email', '') or '').strip()

    sent = False
    # Préférer WhatsApp / SMS (wa.me), puis email. QX10 — le repli email est
    # TOUJOURS tenté quand WhatsApp échoue, même si le client n'a pas d'email
    # renseigné : sinon un client téléphone-seul (stub WhatsApp figé à False)
    # ne recevrait JAMAIS son code, verrouillé hors de la signature. Un email
    # vide/absent échoue simplement (best-effort, cf. _send_otp_email).
    if phone:
        sent = _send_otp_whatsapp(phone=phone, code=code, devis_ref=devis.reference)
    if not sent:
        sent = _send_otp_email(email=email, code=code, devis_ref=devis.reference,
                               company=devis.company)

    if not sent:
        logger.warning(
            'QJ11: OTP généré pour %s mais aucun canal disponible (phone=%s, email=%s)',
            devis.reference, bool(phone), bool(email))
    else:
        logger.info('QJ11: OTP envoyé pour devis %s', devis.reference)
    return None


#: QX10 — nombre de tentatives OTP erronées avant verrouillage temporaire.
OTP_MAX_ATTEMPTS = 5


def _otp_attempts_key(link_token):
    """QX10 — clé de cache du compteur de tentatives OTP erronées par jeton."""
    return f'esign_otp_attempts:{link_token}'


def validate_esign_otp(link, otp_code):
    """QJ11 — Valide l'OTP soumis contre le cache.

    Sans toggle ON : retourne None (pas d'erreur, comportement inchangé).
    Avec toggle ON :
      - otp_code absent / vide → message d'erreur (OTP requis)
      - otp_code incorrect ou expiré → message d'erreur
      - otp_code correct → None (la validation réussit), le code est consommé.

    QX10 — protection brute-force : un compteur par jeton (cache) verrouille
    la validation après ``OTP_MAX_ATTEMPTS`` échecs (l'espace 6 chiffres est
    trivial à balayer sans limite). Une validation réussie remet le compteur
    à zéro ; un nouveau code doit être redemandé après verrouillage.
    """
    if not _esign_otp_enabled():
        return None

    if not otp_code:
        return 'Un code de confirmation est requis. Demandez-le via le bouton « Envoyer le code ».'

    from django.core.cache import cache
    attempts_key = _otp_attempts_key(link.token)
    attempts = cache.get(attempts_key, 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        return ('Trop de tentatives incorrectes. Redemandez un nouveau code '
                'de confirmation et réessayez.')

    cache_key = _otp_cache_key(link.token)
    stored = cache.get(cache_key)
    if stored is None:
        return 'Le code de confirmation a expiré ou n\'a pas été demandé. Redemandez un nouveau code.'
    if stored != otp_code.strip():
        # QX10 — incrémente le compteur d'échecs (TTL = fenêtre du code).
        cache.set(attempts_key, attempts + 1, timeout=OTP_CACHE_TTL)
        restantes = max(0, OTP_MAX_ATTEMPTS - (attempts + 1))
        if restantes == 0:
            return ('Trop de tentatives incorrectes. Redemandez un nouveau '
                    'code de confirmation et réessayez.')
        return 'Code de confirmation incorrect. Vérifiez le code reçu et réessayez.'

    # Code valide : on le consomme (one-time use) et on réinitialise le compteur.
    cache.delete(cache_key)
    cache.delete(attempts_key)
    return None


def _send_otp_whatsapp(phone, code, devis_ref):
    """Envoie le code OTP via WhatsApp. Best-effort → bool.

    QX10 — CORRECTIF : ce canal est un STUB (aucune API WhatsApp live n'est
    câblée — GATÉ derrière QXG1/le BSP). Il renvoie désormais ``False`` au lieu
    de ``True`` : sinon un client SANS email (téléphone seul) ne recevait
    JAMAIS son code (le stub prétendait l'avoir envoyé et coupait le repli
    email), le verrouillant hors de la signature quand ``ESIGN_OTP_ENABLED``
    est actif. En renvoyant False, ``request_esign_otp`` retombe sur l'email.
    Quand le BSP WhatsApp sera disponible, envoyer réellement ici et renvoyer
    True."""
    logger.info(
        'QJ11 OTP WhatsApp NON envoyé (stub, aucun BSP câblé) pour devis %s '
        '— repli email', devis_ref)
    return False


def _send_otp_email(email, code, devis_ref, company=None):
    """Envoie le code OTP par email. Best-effort → bool.

    N100(c) white-label : la signature vient de la société du devis
    (``email_service._signature`` — BrandedTemplate ou « L'équipe {nom} »),
    jamais d'une marque codée en dur."""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from .email_service import _signature
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local')
        sujet = f'Code de confirmation — devis {devis_ref}'
        corps = (
            f'Votre code de confirmation pour le devis {devis_ref} est :\n\n'
            f'    {code}\n\n'
            f'Ce code est valable 10 minutes.\n\n'
            f'Si vous n\'avez pas demandé ce code, ignorez ce message.\n\n'
            f"Cordialement,\n{_signature(company)}"
        )
        send_mail(sujet, corps, from_email, [email], fail_silently=False)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning('QJ11: email OTP échec : %s', exc)
        return False


def _create_esign_record(*, devis, nom, ip, user_agent='', consentement=True,
                         signature_image='', signed_at_client=None,
                         on_behalf_of=''):
    """QJ10 — Crée le DevisSignature IMMUABLE si aucun n'existe encore.

    Idempotent : un enregistrement existant n'est jamais écrasé (la première
    signature fait foi). Best-effort : une exception ne remonte jamais —
    l'acceptation (statut + chatter) est déjà écrite avant cet appel.

    QX9 — persiste désormais la vraie preuve de signature (image manuscrite,
    consentement e-signature explicite, horodatage client, « au nom de ») que
    le front envoie et qui était auparavant jetée.

    WIR138 — CE N'EST PAS UN SOCLE E-SIGNATURE CONCURRENT. ``DevisSignature``
    est la PREUVE d'une acceptation faite EN LIGNE sur notre proposition (loi
    53-05) ; ``core.esign``, le socle canonique désigné, gère les DEMANDES
    envoyées à un prestataire externe (Yousign/DocuSign), aujourd'hui parquées
    faute de compte provisionné. Les deux ne fusionnent pas : ce chemin ne
    migrera jamais vers ``core.esign``. Voir ``core/esign.py`` et
    ``docs/esign-socle.md``.
    """
    try:
        from django.utils import timezone
        from apps.ventes.models import DevisSignature
        if DevisSignature.objects.filter(devis=devis).exists():
            return
        content_hash = DevisSignature.compute_content_hash(devis)
        # ``signature_image`` peut être une data-URL volumineuse — on la borne
        # raisonnablement (les payloads canvas font ~quelques Ko).
        img = (signature_image or '')
        if len(img) > 200000:
            img = img[:200000]
        DevisSignature.objects.create(
            company=devis.company,
            devis=devis,
            signataire_nom=(nom or '')[:150],
            consentement_explicite=bool(consentement),
            ip_address=ip or None,
            user_agent=(user_agent or '')[:512],
            content_hash=content_hash,
            signed_at=timezone.now(),
            signature_image=img,
            consent_esign=bool(consentement),
            signed_at_client=signed_at_client or None,
            on_behalf_of=(on_behalf_of or '')[:150],
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


def _acceptance_deposit_block(devis):
    """QX33be — bloc texte « acompte + RIB » pour l'email de confirmation.

    Acompte = 1ʳᵉ tranche de l'échéancier (sur le TTC REMISÉ, chaîne QX1). RIB
    depuis ``settings.COMPANY_RIB`` si configuré. Chaîne VIDE quand rien n'est
    configurable (pas de tranche, pas de RIB) → email inchangé. Best-effort."""
    from decimal import Decimal
    try:
        from .utils.echeancier import next_tranche
        tr = next_tranche(devis)
        if tr is None:
            return ''
        acompte = Decimal(str(tr['ttc']))
        montant_str = f'{acompte:,.2f}'.replace(',', ' ') + ' MAD'
        from django.conf import settings
        rib = (getattr(settings, 'COMPANY_RIB', '') or '').strip()
        lignes = [
            f"Pour démarrer votre installation, un acompte de {montant_str} "
            f"est à régler.",
        ]
        if rib:
            lignes.append(
                f"Vous pouvez l'effectuer par virement sur : {rib}")
            lignes.append(
                "Une fois le virement effectué, signalez-le depuis votre "
                "espace proposition pour informer votre conseiller.")
        return '\n'.join(lignes) + '\n\n'
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return ''


def _send_acceptance_emails(*, devis, user):
    """QJ10 — Envoie un email de confirmation de signature au client + au vendeur.

    Best-effort : une exception ne remonte jamais (l'acceptation est déjà écrite).
    Le PDF joint est récupéré depuis MinIO si disponible ; sinon l'email part
    sans pièce jointe (comportement réseau conforme à email_service.py).
    Jamais de prix_achat / marge dans les emails (règle #4).
    """
    try:
        from apps.ventes.email_service import send_document_email
        from apps.ventes.email_service import _signature as _signature_societe
        client = getattr(devis, 'client', None)
        dest = (getattr(client, 'email', '') or '').strip()
        nom_client = ''
        if client is not None:
            nom_client = (
                f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
            )
        salut = f'Bonjour {nom_client},' if nom_client else 'Bonjour,'
        # QX33be — bloc acompte (tranche 1 sur le TTC REMISÉ per QX1) + RIB si
        # configuré. Vide (aucune ligne) quand rien n'est configurable → texte
        # de confirmation inchangé.
        acompte_bloc = _acceptance_deposit_block(devis)
        corps = (
            f"{salut}\n\n"
            f"Nous avons bien reçu votre acceptation du devis "
            f"{devis.reference}.\n\n"
            f"Votre signature électronique a été enregistrée conformément "
            f"à la loi 43-20 relative à l'échange électronique de données "
            f"juridiques.\n\n"
            f"{acompte_bloc}"
            f"Vous trouverez ci-joint votre exemplaire signé pour vos archives.\n\n"
            f"Merci pour votre confiance.\n\n"
            f"Cordialement,\n{_signature_societe(devis.company)}"
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


def _fire_capi_signed_quote(*, devis, ip=None, user_agent=''):
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

    # Valeur de conversion : TTC REMISÉ de l'option acceptée (QX2 — chaîne
    # canonique QX1), jamais le TTC brut du devis (mal calibré sur un devis à
    # 2 options ou avec remise globale). Sans prix d'achat (règle #4).
    try:
        from apps.ventes.utils.options import option_totaux
        value = float(option_totaux(devis)['ttc'])
    except Exception:  # noqa: BLE001 — CAPI ne casse jamais l'acceptation
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
    # ADSENG2 — EMQ (Event Match Quality) : ip + user_agent NON hachés (Meta les
    # recommande tels quels). Déjà disponibles au point d'acceptation (accept_devis
    # les reçoit), auparavant abandonnés ici. Aucune nouvelle collecte de donnée.
    if ip:
        user_data['client_ip_address'] = str(ip)
    if user_agent:
        user_data['client_user_agent'] = str(user_agent)

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

    # ADSENG2 — event_id DÉTERMINISTE (dedup) : Meta dé-duplique deux événements
    # de même event_name + event_id dans une fenêtre de 48 h. La référence du
    # devis est unique et déjà la clé d'idempotence naturelle ailleurs — la
    # réutiliser ferme d'avance tout double-comptage si un Pixel navigateur est
    # un jour ajouté sur /proposal.
    event_id = f'signedquote:{getattr(devis, "reference", "") or devis.pk}'

    event = {
        'event_name': 'SignedQuote',
        'event_time': event_time,
        'event_id': event_id,
        'action_source': 'website',
        'user_data': user_data,
        'custom_data': custom_data,
    }

    payload = _json.dumps({'data': [event]}).encode('utf-8')
    # ADSENG2 — version depuis la SOURCE UNIQUE partagée (v25 courante), jamais
    # la v19.0 codée en dur (expirée 02/2025 → 400 garanti dès qu'un pixel est
    # configuré). Constante plain (aucun modèle adsengine importé dans ventes).
    from apps.adsengine.api_version import GRAPH_BASE_URL
    api_url = f'{GRAPH_BASE_URL}/{pixel_id}/events' if pixel_id else None

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
                 signature_image='', signed_at_client=None, on_behalf_of='',
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
    from django.db import transaction
    from django.utils import timezone
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from core.events import devis_accepted

    # QX41 — verrou anti-course sur le chemin public d'acceptation : deux POST
    # concurrents (double-clic / rejeu) pouvaient tous deux passer le contrôle
    # de statut et double-émettre ``devis_accepted`` (effets aval doublés). On
    # relit le devis VERROUILLÉ (select_for_update) et on recontrôle son statut
    # SOUS le verrou : le second appel voit ACCEPTE et devient un no-op.
    valid = {c.value for c in Devis.OptionAcceptee}
    option = (option or '').strip()
    if option and option not in valid:
        raise AcceptError(
            'Option invalide (attendu « sans_batterie » ou « avec_batterie »).')

    # QX41 — TOUT le contrôle-puis-bascule de statut se fait SOUS le même verrou
    # (select_for_update) : deux acceptations concurrentes ne peuvent plus
    # toutes deux voir « envoyé » et double-basculer/double-émettre l'événement.
    date_acc = date_acceptation or timezone.now().date()
    with transaction.atomic():
        try:
            devis = Devis.objects.select_for_update().get(pk=devis.pk)
        except Devis.DoesNotExist:
            raise AcceptError('Devis introuvable.', conflict=True)

        # Re-submit on an already-accepted devis: a no-op for the tokenized
        # web proposal, but rejected (409) for the in-app action (ERR33 guard).
        if devis.statut == Devis.Statut.ACCEPTE:
            if idempotent_reaccept:
                return devis
            raise AcceptError('Ce devis est déjà accepté.', conflict=True)

        # ERR33 — only a live devis (brouillon / envoyé) can be accepted.
        if devis.statut not in (Devis.Statut.BROUILLON, Devis.Statut.ENVOYE):
            raise AcceptError(
                'Seul un devis en cours (brouillon ou envoyé) peut être '
                f'accepté ; statut actuel : « {devis.get_statut_display()} ».',
                conflict=True)

        # Resolve the option exactly like the viewset (two-option devis require
        # an explicit choice; single-option devis deduce it from the scenario).
        try:
            from apps.ventes.quote_engine.builder import build_quote_data
            qd = build_quote_data(devis, {'pdf_mode': 'onepage'})
            nb_options = qd.get('nb_options', 1)
            scenario = qd.get('scenario', '')
        except Exception:  # noqa: BLE001 — l'acceptation ne doit jamais casser
            nb_options, scenario = 1, ''
        if nb_options == 2 and not option:
            raise AcceptError(
                'Ce devis comporte deux options — précisez celle choisie par '
                'le client (« sans_batterie » ou « avec_batterie »).')
        if not option:
            option = (Devis.OptionAcceptee.AVEC_BATTERIE
                      if scenario == 'Avec batterie'
                      else Devis.OptionAcceptee.SANS_BATTERIE)

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
        signature_image=signature_image, signed_at_client=signed_at_client,
        on_behalf_of=on_behalf_of,
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
    # QX9 — le PDF signé est persisté sur une AUTRE instance (via le moteur) ;
    # on rafraîchit ``fichier_pdf`` sur l'instance courante pour que la pièce
    # jointe de l'email ne parte pas sur un état périmé (bug de l'exemplaire
    # signé manquant).
    try:
        devis.refresh_from_db(fields=['fichier_pdf'])
    except Exception:  # noqa: BLE001 — best-effort
        pass
    # QJ10 — Email de confirmation PDF verrouillé au client + au vendeur.
    try:
        _send_acceptance_emails(devis=devis, user=user)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ10: _send_acceptance_emails échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)

    # YDOCF3 — variantes (QJ15 dupliquer-variante) : accepter l'une d'elles
    # doit effondrer ses SŒURS (même groupe version_parent=root) plutôt que
    # de les laisser is_active=True et elles-mêmes acceptables (double
    # comptage du funnel). Ne touche jamais un devis d'un autre groupe ni les
    # révisions déjà terminales. Un devis sans variante est inchangé.
    from django.db.models import Q
    root = devis.version_parent_id or devis.id
    siblings = Devis.objects.filter(
        company=devis.company, is_active=True,
        statut__in=(Devis.Statut.BROUILLON, Devis.Statut.ENVOYE),
    ).filter(
        Q(version_parent_id=root) | Q(pk=root)
    ).exclude(pk=devis.pk)
    for sibling in siblings:
        sibling.statut = Devis.Statut.REFUSE
        sibling.date_refus = date_acc
        sibling.motif_refus = 'variante non retenue'
        sibling.is_active = False
        sibling.save(update_fields=[
            'statut', 'date_refus', 'motif_refus', 'is_active'])
        activity.log_devis_refusal(
            sibling, user, 'variante non retenue', date_acc)

    devis_accepted.send(
        sender=Devis, devis=devis, user=user, ancien_statut=ancien)
    # QJ9 — CAPI SignedQuote event (gated on META_CAPI_ACCESS_TOKEN).
    # ADSENG2 — thread ip/user_agent (EMQ) déjà reçus par accept_devis.
    try:
        _fire_capi_signed_quote(devis=devis, ip=ip, user_agent=user_agent)
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


# ── PUB69 — Carte de partage client trackable (« mon installation ») ────────
# Canal UTM dédié, remonte dans l'attribution existante comme canal DISTINCT
# (`apps.adsengine.attribution.referral_share_channel_summary`).
INSTALLATION_SHARE_UTM_CAMPAIGN = 'parrainage_whatsapp'


def installation_share_link(devis, *, base_url=''):
    """PUB69 — Réutilise l'infra ``ShareLink``/UTM EXISTANTE de ventes
    (``ShareLink.for_devis``, QJ1 — RÉUTILISÉE, aucun nouveau modèle) pour
    générer (ou récupérer) le lien « mon installation » du client APRÈS
    SIGNATURE — un devis ACCEPTÉ seulement (avant signature, ce n'est pas
    encore « son installation »). ``None`` si le devis n'est pas accepté.

    Renvoie ``(ShareLink, url)`` ; ``url`` porte les UTM canal
    ``parrainage_whatsapp`` (bouche-à-oreille organique mesuré) — remonte
    dans l'attribution existante comme canal DISTINCT, sans toucher le
    canal Meta."""
    from django.conf import settings

    from .models import Devis, ShareLink

    if devis is None or devis.statut != Devis.Statut.ACCEPTE:
        return None, ''
    link = ShareLink.for_devis(devis)
    base = base_url or getattr(settings, 'PUBLIC_BASE_URL', '') or ''
    query = (
        'utm_source=client&utm_medium=whatsapp'
        f'&utm_campaign={INSTALLATION_SHARE_UTM_CAMPAIGN}')
    path = f'/proposition/{link.token}?{query}'
    url = (base.rstrip('/') + path) if base else path
    return link, url


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


def refresh_etude_consistency(devis):
    """QX24 — garde ``etude_params`` cohérent quand les lignes/remise changent.

    Problème : ``production_annuelle``/``economies_annuelles`` sont figés à la
    création tandis que le TOTAL du devis flotte avec les éditions de lignes/la
    remise globale — le payback (= total ÷ économies) devient alors incohérent.

    Correctif (option b) : on RECALCULE et REPERSISTE le payback dérivé à
    partir du TTC canonique COURANT (chaîne QX1) et des économies annuelles
    stockées, à chaque changement de ligne/remise. On garde tel quel toute
    valeur explicitement saisie par le vendeur (préfixe ``*_override`` ou clé
    ``etude_overrides``), qui reste autoritative.

    Best-effort : jamais d'exception remontée. No-op si aucune économie connue
    (rien à dériver) — comportement historique inchangé pour ces devis.
    """
    from decimal import Decimal
    try:
        params = dict(devis.etude_params or {})
        eco = params.get('economies_annuelles')
        if not eco:
            return
        eco = Decimal(str(eco))
        if eco <= 0:
            return
        # Le vendeur a figé un payback à la main → on ne l'écrase jamais.
        overrides = set(params.get('etude_overrides') or [])
        if 'payback_annees' in overrides or 'payback_override' in params:
            return
        from apps.ventes.utils.options import option_totaux
        ttc = Decimal(str(option_totaux(devis)['ttc']))
        if ttc <= 0:
            return
        payback = (ttc / eco).quantize(Decimal('0.1'))
        if params.get('payback_annees') != float(payback):
            params['payback_annees'] = float(payback)
            devis.etude_params = params
            devis.save(update_fields=['etude_params'])
    except Exception as exc:  # noqa: BLE001 — jamais bloquant
        logger.warning('QX24: refresh étude échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def compute_marge_snapshot(devis):
    """QX23be — marge HT interne figée d'un devis (usage MANAGER UNIQUEMENT).

    marge = Σ(HT ligne, option acceptée si applicable) − Σ(qté × prix_achat).
    Renvoie un Decimal, ou None si AUCUN produit lié ne porte de prix_achat
    exploitable (on ne veut pas figer une fausse marge = 100 % du CA). Best-
    effort : jamais d'exception remontée.

    RÈGLE #4 : ``prix_achat`` ne quitte JAMAIS cette fonction interne — le
    résultat (une marge) n'est exposé qu'au responsable dans la vue liste,
    jamais dans un PDF/une sortie client.
    """
    from decimal import Decimal
    try:
        from apps.ventes.utils.options import option_lines
        lignes = option_lines(devis)
    except Exception:  # noqa: BLE001
        try:
            lignes = list(devis.lignes.select_related('produit').all())
        except Exception:  # noqa: BLE001
            return None
    ht = Decimal('0')
    cout = Decimal('0')
    a_un_cout = False
    for li in lignes:
        try:
            ht += Decimal(str(li.total_ht))
        except Exception:  # noqa: BLE001
            continue
        produit = getattr(li, 'produit', None)
        prix_achat = getattr(produit, 'prix_achat', None) if produit else None
        if prix_achat is not None and Decimal(str(prix_achat)) > 0:
            a_un_cout = True
            cout += Decimal(str(li.quantite)) * Decimal(str(prix_achat))
    if not a_un_cout:
        return None
    return (ht - cout).quantize(Decimal('0.01'))


def refresh_marge_snapshot(devis):
    """QX23be — recalcule et persiste ``marge_snapshot`` (best-effort)."""
    try:
        marge = compute_marge_snapshot(devis)
        if devis.marge_snapshot != marge:
            devis.marge_snapshot = marge
            devis.save(update_fields=['marge_snapshot'])
    except Exception as exc:  # noqa: BLE001 — jamais bloquant
        logger.warning('QX23: marge_snapshot échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def verifier_devis_envoyable(devis):
    """NTCPQ7 — lève ``ValidationError`` si une étape d'approbation de remise
    est encore ``en_attente`` (blocage envoi/génération PDF).

    Lecture cross-app cpq via import LOCAL (aucun cycle au niveau module).
    Aucune étape en attente ⇒ ne lève rien (comportement inchangé)."""
    from rest_framework.exceptions import ValidationError
    from apps.cpq.selectors import premiere_etape_en_attente
    etape = premiere_etape_en_attente(devis)
    if etape is not None:
        raise ValidationError({'statut': (
            f"Approbation de remise en attente (étape {etape.niveau}) : "
            "l'envoi est bloqué tant qu'elle n'est pas approuvée.")})


def contexte_clauses_devis(devis):
    """NTCPQ11 — Contexte plat servant à évaluer les clauses/CGV dynamiques.

    Clés exposées : ``type_deal`` (= ``mode_installation``), ``montant``
    (= total TTC), ``total_ht``, ``total_ttc``, ``remise_globale``,
    ``puissance_kwc``, ``devise``. Aucun prix d'achat / aucune marge (donnée
    interne — jamais dans un texte destiné au client)."""
    from decimal import Decimal, InvalidOperation

    etude = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    try:
        kwc = float(etude.get('puissance_kwc') or 0)
    except (TypeError, ValueError):
        kwc = 0.0
    try:
        total_ht = float(devis.total_ht or 0)
        total_ttc = float(devis.total_ttc or 0)
    except (TypeError, ValueError, InvalidOperation):
        total_ht = total_ttc = 0.0
    return {
        'type_deal': devis.mode_installation or '',
        'mode_installation': devis.mode_installation or '',
        'montant': total_ttc,
        'total_ht': total_ht,
        'total_ttc': total_ttc,
        'remise_globale': float(devis.remise_globale or Decimal('0')),
        'puissance_kwc': kwc,
        'devise': devis.devise or 'MAD',
    }


def figer_clauses_devis(devis):
    """NTCPQ11 — FIGE les clauses/CGV applicables sur le devis (snapshot).

    Appelé au passage brouillon → envoyé. Idempotent et WRITE-ONCE : si
    ``clauses_appliquees`` porte déjà une valeur (même une liste vide figée),
    rien n'est recalculé — modifier une clause plus tard n'altère jamais un
    devis déjà envoyé. Lecture cross-app cpq via import LOCAL (selectors).
    Ne lève jamais : un incident de configuration ne doit pas bloquer un envoi.
    Renvoie la liste figée."""
    if devis.clauses_appliquees is not None:
        return devis.clauses_appliquees
    try:
        from apps.cpq.selectors import clauses_applicables
        clauses = clauses_applicables(
            company=devis.company, context=contexte_clauses_devis(devis))
    except Exception:  # noqa: BLE001 — un envoi ne casse jamais sur les CGV
        logger.exception(
            'NTCPQ11 : figeage des clauses ignoré (devis %s)', devis.pk)
        return None
    devis.clauses_appliquees = clauses
    devis.save(update_fields=['clauses_appliquees'])
    return clauses


def configuration_devis_contenu(devis):
    """NTCPQ20 — Représentation JSON-safe de la configuration d'un devis.

    Uniquement des données de configuration (ligne, désignation, quantité,
    P.U., remise) — JAMAIS de prix d'achat ni de marge."""
    return {
        'lignes': [{
            'ligne_id': li.id,
            'produit_id': li.produit_id,
            'designation': li.designation,
            'quantite': str(li.quantite) if li.quantite is not None else None,
            'prix_unitaire': (str(li.prix_unitaire)
                              if li.prix_unitaire is not None else None),
            'remise': str(li.remise) if li.remise is not None else None,
        } for li in devis.lignes.all().order_by('ordre', 'id')],
    }


def capturer_configuration_devis(devis, *, user=None):
    """NTCPQ20 — Enregistre un instantané de configuration si le devis est
    BROUILLON et que la configuration a RÉELLEMENT changé.

    No-op (renvoie ``None``) hors brouillon ou quand le contenu est identique
    au dernier instantané — un simple re-save ne pollue pas l'historique.
    Ne lève jamais : l'historique ne doit jamais bloquer une écriture."""
    from apps.ventes.models import ConfigurationDevisSnapshot, Devis

    if devis is None or devis.pk is None:
        return None
    if devis.statut != Devis.Statut.BROUILLON:
        return None
    try:
        contenu = configuration_devis_contenu(devis)
        dernier = ConfigurationDevisSnapshot.objects.filter(
            devis_id=devis.pk).order_by('-date_creation', '-id').first()
        if dernier is not None and dernier.contenu == contenu:
            return None
        return ConfigurationDevisSnapshot.objects.create(
            company=devis.company, devis=devis, contenu=contenu, auteur=user)
    except Exception:  # noqa: BLE001 — l'historique n'est jamais bloquant
        logger.exception(
            'NTCPQ20 : instantané de configuration ignoré (devis %s)',
            devis.pk)
        return None


def diff_configurations_devis(snapshot_a, snapshot_b):
    """NTCPQ20 — Diff des LIGNES entre deux instantanés de configuration.

    Renvoie ``{ajoutees, retirees, modifiees}`` : ``modifiees`` porte, pour
    chaque ligne présente des deux côtés, les champs qui ont changé
    (``{champ: [avant, apres]}``)."""
    def _index(snap):
        contenu = (snap or {}).get('lignes') or []
        return {li.get('ligne_id'): li for li in contenu}

    avant = _index(getattr(snapshot_a, 'contenu', snapshot_a))
    apres = _index(getattr(snapshot_b, 'contenu', snapshot_b))
    modifiees = []
    for ligne_id, ligne in apres.items():
        precedente = avant.get(ligne_id)
        if precedente is None:
            continue
        champs = {
            champ: [precedente.get(champ), ligne.get(champ)]
            for champ in ('designation', 'quantite', 'prix_unitaire', 'remise')
            if precedente.get(champ) != ligne.get(champ)}
        if champs:
            modifiees.append({'ligne_id': ligne_id, 'champs': champs})
    return {
        'ajoutees': [li for lid, li in apres.items() if lid not in avant],
        'retirees': [li for lid, li in avant.items() if lid not in apres],
        'modifiees': modifiees,
    }


def renouveler_devis(devis, *, user=None):
    """NTCPQ13 — Renouvelle un devis déjà ACCEPTÉ (ou expiré/clos).

    Crée un NOUVEAU ``Devis`` en ``brouillon`` reprenant les lignes actuelles
    avec les prix COURANTS recalculés (``prix_applicable`` — jamais une simple
    copie figée), lié au devis source par ``devis_origine`` (racine de chaîne)
    et portant ``numero_renouvellement`` = source + 1.

    DISTINCT de ``reviser`` (T10) : celui-ci corrige un devis non encore
    accepté et supersède l'original ; ``renouveler`` laisse le devis source
    strictement intact (statut, chaîne BC/Facture, historique).

    Lève ``ValidationError`` si le devis n'est pas dans un état renouvelable.
    Renvoie le nouveau devis."""
    from rest_framework.exceptions import ValidationError
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes import activity
    from apps.ventes.utils.company_settings import create_numbered

    RENOUVELABLES = (Devis.Statut.ACCEPTE, Devis.Statut.EXPIRE)
    if devis.statut not in RENOUVELABLES:
        raise ValidationError({'statut': (
            'Seul un devis accepté ou expiré peut être renouvelé '
            '(un devis en cours se corrige avec « réviser »).')})

    company = devis.company
    racine = devis.devis_origine or devis
    cree = {}

    def _save(ref):
        cree['obj'] = Devis.objects.create(
            company=company, reference=ref, client=devis.client,
            lead=devis.lead, statut=Devis.Statut.BROUILLON,
            taux_tva=devis.taux_tva, remise_globale=devis.remise_globale,
            note=devis.note, mode_installation=devis.mode_installation,
            etude_params=devis.etude_params,
            prix_cible_kwc=devis.prix_cible_kwc,
            echeancier=devis.echeancier, devise=devis.devise,
            taux_change=devis.taux_change, entite=devis.entite,
            created_by=user, devis_origine=racine,
            numero_renouvellement=(devis.numero_renouvellement or 0) + 1)
        return cree['obj']

    create_numbered(Devis, company, 'devis', _save)
    nouveau = cree['obj']

    for ligne in devis.lignes.all().select_related('produit'):
        prix = ligne.prix_unitaire
        if ligne.produit_id is not None:
            try:
                prix = prix_applicable(
                    produit=ligne.produit, client=devis.client,
                    quantite=ligne.quantite)['prix']
            except Exception:  # noqa: BLE001 — repli sur le prix historique
                logger.exception(
                    'NTCPQ13 : prix courant indisponible (ligne %s)', ligne.pk)
                prix = ligne.prix_unitaire
        LigneDevis.objects.create(
            devis=nouveau, produit=ligne.produit,
            designation=ligne.designation, quantite=ligne.quantite,
            prix_unitaire=prix, remise=ligne.remise,
            taux_tva=ligne.taux_tva, type_ligne=ligne.type_ligne,
            ordre=ligne.ordre, groupe_index=ligne.groupe_index,
            groupe_label=ligne.groupe_label, optionnelle=ligne.optionnelle)

    activity.log_devis_note(
        nouveau, user,
        f'Renouvellement n° {nouveau.numero_renouvellement} du devis '
        f'{devis.reference} — prix catalogue actuels appliqués.')
    activity.log_devis_note(
        devis, user,
        f'Renouvelé par le devis {nouveau.reference} '
        f'(renouvellement n° {nouveau.numero_renouvellement}).')
    return nouveau


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

    # NTCPQ7 — bloque l'envoi tant qu'une étape d'approbation de remise reste
    # en attente (matrice à paliers, remplace/étend le seuil unique T17).
    verifier_devis_envoyable(devis)

    # NTCPQ11 — fige les clauses/CGV dynamiques AVANT le basculement (snapshot
    # write-once ; jamais recalculé après envoi).
    figer_clauses_devis(devis)

    ancien = devis.statut
    devis.statut = Devis.Statut.ENVOYE
    devis.date_envoi = timezone.now()
    devis.save(update_fields=['statut', 'date_envoi'])
    # QX23be — fige la marge interne au moment de l'envoi (manager-only).
    refresh_marge_snapshot(devis)
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


class PaiementRejectError(Exception):
    """YLEDG5 — erreur métier au rejet d'un paiement (message + conflict)."""

    def __init__(self, message, conflict=False):
        super().__init__(message)
        self.message = message
        self.conflict = conflict


def rejeter_paiement(*, paiement, motif, frais=None, date_rejet=None, user=None):
    """YLEDG5 — chemin d'exception « paiement rejeté » (chèque impayé /
    virement rejeté).

    Le paiement N'EST JAMAIS supprimé (piste d'audit) : il passe
    ``statut=rejete`` et sort du calcul ``Facture.montant_paye``/``statut`` —
    la facture redevient ouverte/en retard (recalculée : émise si l'échéance
    n'est pas dépassée, sinon en retard) et les relances existantes sont
    ré-armées (symétrique de ``reset_relance_escalation``). Émet
    ``paiement_rejete`` sur le bus core pour que compta contre-passe
    l'écriture d'encaissement (YLEDG4) et délettre (YLEDG6). Idempotent côté
    garde : rejeter un paiement déjà rejeté est refusé (jamais un double
    rejet)."""
    from django.utils import timezone
    from django.db import transaction
    from .models import Facture, Paiement
    from core.events import paiement_rejete

    motif = (motif or '').strip()
    if not motif:
        raise PaiementRejectError('Le motif du rejet est obligatoire.')
    if paiement.statut == Paiement.Statut.REJETE:
        raise PaiementRejectError(
            'Ce paiement est déjà marqué rejeté.', conflict=True)

    with transaction.atomic():
        paiement.statut = Paiement.Statut.REJETE
        paiement.motif_rejet = motif[:255]
        paiement.frais_rejet = frais
        paiement.date_rejet = date_rejet or timezone.now().date()
        paiement.save(update_fields=[
            'statut', 'motif_rejet', 'frais_rejet', 'date_rejet'])

        facture = paiement.facture
        if facture is not None:
            facture.refresh_from_db()
            # Rouvre la facture : reste dû > 0 → repasse émise (ou en
            # retard si l'échéance est déjà dépassée), jamais « payée » ni
            # « annulée » (états terminaux préservés à part la réouverture).
            if facture.statut not in (
                    Facture.Statut.ANNULEE,) and facture.montant_du > 0:
                today = timezone.now().date()
                if facture.date_echeance and facture.date_echeance < today:
                    facture.statut = Facture.Statut.EN_RETARD
                else:
                    facture.statut = Facture.Statut.EMISE
                facture.save(update_fields=['statut'])
            from . import activity
            activity.log_facture_paiement_rejete(facture, user, paiement, motif)

        paiement_rejete.send(
            sender=Paiement, paiement=paiement, facture=facture,
            montant=paiement.montant, company=paiement.company)
    return paiement


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


class CreditHoldError(Exception):
    """XFAC28 — levée quand un client est en hold crédit dur (sans override).

    Porte le détail chiffré (``motif``) pour un message 403 explicite."""

    def __init__(self, motif):
        super().__init__(motif)
        self.motif = motif


def verifier_credit_hold(client, *, override=False, user=None,
                         chatter_target=None, contexte=''):
    """XFAC28 — vérifie le hold crédit dur (étend FG41) avant une action
    sensible (accepter un devis, générer une facture).

    Flag OFF (``CompanyProfile.credit_hold_actif``) → no-op, comportement FG41
    intact (avertissement seul, jamais consulté ici). Flag ON et le client est
    en dépassement (plafond et/ou retard, voir
    ``apps.crm.selectors.credit_hold_check``) : lève ``CreditHoldError`` SAUF
    si ``override=True`` (responsable/admin explicite) — l'override est
    journalisé (chatter du devis si fourni + audit) mais laisse passer
    l'action. Ne renvoie rien ; lève ou passe silencieusement.

    WIR93 — COEXISTENCE AVEC ``apps.credit`` (décision consignée en tête de
    ``apps/credit/services.py``). Ce moteur (FG41/XFAC28) reste le SEUL branché
    en production ; ``apps.credit.services.verifier_hold_credit`` (NTCRD6)
    n'a aucun appelant tant que NTCRD7/NTCRD8 ne sont pas livrés. Les deux
    consomment la MÊME assiette de factures, à un écart près, volontaire et
    unique : ce chemin ne compte que les factures ``emise``/``en_retard``,
    quand ``apps.credit`` inclut aussi les ``brouillon``. Cet écart est
    verrouillé par ``apps/credit/tests/test_wir93_encours_non_divergence.py``
    (via ``apps.credit.services.ecart_encours_moteurs``) : élargir ou
    rétrécir l'assiette d'un seul côté rend ce test rouge. Ne JAMAIS
    dupliquer ici un troisième calcul d'encours."""
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.get(company=client.company)
    if not getattr(profile, 'credit_hold_actif', False):
        return

    from apps.crm.selectors import credit_hold_check
    seuil = getattr(profile, 'credit_hold_retard_jours', 0) or 0
    result = credit_hold_check(client, retard_jours_seuil=seuil)
    if not result['bloque']:
        return

    if not override:
        raise CreditHoldError(result['motif'])

    # Override responsable/admin : journalise (chatter + audit société).
    from apps.parametres.models_audit import SettingsAuditLog
    qui = getattr(user, 'username', '?') if user else '?'
    SettingsAuditLog.log_change(
        company=client.company, user=user, section='credit_hold',
        field='override', field_label='Blocage crédit — override',
        old='bloque', new=f'débloqué par {qui} ({contexte})',
    )
    if chatter_target is not None:
        from . import activity
        activity.log_devis_credit_hold_override(
            chatter_target, user, result['motif'])


class SaleWarningError(Exception):
    """ZSAL9 — levée quand un devis porte un avertissement de vente BLOQUANT
    (produit et/ou client) sans override responsable/admin.

    Porte le message concaténé (``motif``) pour un 403 explicite."""

    def __init__(self, motif):
        super().__init__(motif)
        self.motif = motif


def verifier_sale_warnings(devis, *, override=False, user=None,
                           chatter_target=None):
    """ZSAL9 — vérifie les avertissements de vente (« sale warnings ») avant une
    action sensible (accepter un devis, générer une facture).

    Collecte les messages BLOQUANTS du client du devis et des produits de ses
    lignes (lus via ``stock.selectors`` — jamais d'import de ``stock.models``).
    Sans message bloquant → no-op. Avec au moins un message bloquant : lève
    ``SaleWarningError`` SAUF si ``override=True`` (responsable/admin explicite),
    auquel cas l'override est journalisé (chatter du devis si fourni). Les
    avertissements NON bloquants n'empêchent jamais l'action (ils ne sont
    qu'affichés côté écran). Ne renvoie rien ; lève ou passe silencieusement."""
    motifs = []

    client = getattr(devis, 'client', None)
    if client is not None and getattr(client, 'avertissement_bloquant', False) \
            and (getattr(client, 'avertissement_vente', '') or '').strip():
        motifs.append(f'Client — {client.avertissement_vente.strip()}')

    from apps.stock import selectors as stock_selectors
    produit_ids = list(
        devis.lignes.exclude(produit__isnull=True)
        .values_list('produit_id', flat=True)
    )
    for row in stock_selectors.produits_avertissements(devis.company, produit_ids):
        if row.get('avertissement_bloquant') \
                and (row.get('avertissement_vente') or '').strip():
            motifs.append(
                f"Produit « {row.get('nom', '')} » — "
                f"{row['avertissement_vente'].strip()}")

    if not motifs:
        return

    motif = ' ; '.join(motifs)
    if not override:
        raise SaleWarningError(motif)

    # Override responsable/admin : journalise au chatter du devis.
    if chatter_target is not None:
        from . import activity
        activity.log_devis_sale_warning_override(chatter_target, user, motif)


def _s2(x):
    from decimal import Decimal
    return str(Decimal(x or 0).quantize(Decimal('0.01')))


def dossier_contentieux_data(factures):
    """XFAC21 — assemble les données du pack contentieux pour un jeu de
    factures en souffrance (toutes du MÊME client — vérifié par l'appelant).

    Renvoie un dict prêt pour le template ``dossier_contentieux.html`` :
    factures concernées, total réclamé, historique des relances (RelanceLog) +
    emails (EmailLog), promesses de paiement ROMPUES (PromessePaiement).
    Lecture seule."""
    from django.utils import timezone
    from .models import PromessePaiement

    factures = list(factures)
    client = factures[0].client if factures else None

    lignes_factures = []
    total_du = 0
    relances = []
    emails = []
    promesses_rompues = []

    for f in factures:
        total_du += f.montant_du
        lignes_factures.append({
            'reference': f.reference,
            'date_echeance': (
                f.date_echeance.isoformat() if f.date_echeance else ''),
            'jours_retard': f.jours_retard,
            'total_ttc': _s2(f.total_ttc),
            'du': _s2(f.montant_du),
        })
        for r in f.relances.all().order_by('-date', '-id'):
            relances.append({
                'date': r.date.isoformat() if r.date else '',
                'facture_reference': f.reference,
                'niveau_nom': r.niveau_nom or '',
                'note': r.note or '',
            })
        for e in f.email_logs.all().order_by('-created_at'):
            emails.append({
                'date': e.created_at.isoformat() if e.created_at else '',
                'direction': e.get_direction_display(),
                'sujet': e.sujet or '',
            })
        for p in f.promesses_paiement.filter(
                statut=PromessePaiement.Statut.ROMPUE):
            promesses_rompues.append({
                'facture_reference': f.reference,
                'date_promise': p.date_promise.isoformat(),
                'montant_promis': _s2(p.montant_promis),
            })

    return {
        'client': {
            'nom': f'{client.nom} {client.prenom or ""}'.strip() if client else '',
            'email': getattr(client, 'email', '') or '',
            'telephone': getattr(client, 'telephone', '') or '',
            'adresse': getattr(client, 'adresse', '') or '',
        },
        'factures': lignes_factures,
        'total_du': _s2(total_du),
        'relances': relances,
        'emails': emails,
        'promesses_rompues': promesses_rompues,
        'date_creation': timezone.now().date().isoformat(),
    }


def ouvrir_dossier_contentieux(*, factures, user=None):
    """XFAC21 — passage en recouvrement externe pour un jeu de factures.

    (a) assemble les données du pack (voir ``dossier_contentieux_data``) ;
    (b) ouvre une ``litiges.Reclamation`` de type recouvrement via
        ``apps.litiges.services.creer_dossier_recouvrement`` (jamais un import
        de son modèle) ;
    (c) marque les factures ``exclu_relances`` (comms ordinaires gelées) avec
        trace chatter « passé au contentieux le … ».

    Toutes les factures DOIVENT appartenir au même client + à la même société
    (vérifié par l'appelant — la vue scope déjà par client). Renvoie
    ``(dossier_data, reclamation)``."""
    from django.utils import timezone
    from .models import Facture

    factures = list(factures)
    if not factures:
        raise ValueError('Aucune facture sélectionnée.')
    client = factures[0].client
    company = factures[0].company

    dossier = dossier_contentieux_data(factures)

    from apps.litiges.services import creer_dossier_recouvrement
    references = ', '.join(f.reference for f in factures)
    reclamation = creer_dossier_recouvrement(
        company=company, source_type='client', source_id=client.id,
        objet=f'Recouvrement externe — {client.nom} ({references})',
        montant_conteste=sum((f.montant_du for f in factures), 0),
        description=f'Factures concernées : {references}.',
        user=user,
    )

    from . import activity
    qui = getattr(user, 'username', '?') if user else 'automatique'
    today = timezone.now().date().isoformat()
    for f in factures:
        if f.statut == Facture.Statut.ANNULEE:
            continue
        f.exclu_relances = True
        f.save(update_fields=['exclu_relances'])
        activity.log_facture_activity_contentieux(f, user, qui, today)

    return dossier, reclamation


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
        # XSAL5/XSAL14 — ne réserve QUE les lignes produit effectives : pas les
        # options non activées ni les lignes de section/note (sans produit).
        if not ligne.compte_dans_totaux:
            continue
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

    # YSUBS9 — période de service couverte par CETTE facture : du dernier
    # cycle facturé (ou date_debut si jamais facturé) à aujourd'hui + la
    # durée de la périodicité (mois, table MONTHS déjà utilisée pour les
    # visites). Best-effort : une périodicité/date absente laisse les deux
    # champs à NULL (comportement actuel intact).
    periode_debut = contrat.derniere_facturation or contrat.date_debut
    periode_fin = None
    if periode_debut is not None:
        mois = getattr(contrat, 'MONTHS', {}).get(contrat.periodicite)
        if mois:
            periode_fin = _add_months(periode_debut, mois)

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
            periode_service_debut=periode_debut,
            periode_service_fin=periode_fin,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)

    # Avancer la date de dernière facturation.
    today = timezone.localdate()
    contrat.derniere_facturation = today
    contrat.save(update_fields=['derniere_facturation'])

    # YSUBS6 — cette facture est créée EMISE directement (redevance de
    # maintenance récurrente, jamais de passage par brouillon/`emettre`) : le
    # bus documentaire de YLEDG1 ne la voit donc jamais sans émission
    # explicite ici. Émettre `facture_emise` pour que l'auto-écriture
    # compta (togglée par COMPTA_AUTO_ECRITURES, OFF par défaut) se déclenche
    # comme sur une facture émise via l'écran (comportement inchangé si le
    # toggle reste OFF).
    from core.events import facture_emise
    facture_emise.send(sender=Facture, instance=facture, company=company)

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


# ── XACC28 — Refacturation des frais au client (billable expenses) ────────
# Thin service exposé pour apps.compta (frontière cross-app, CLAUDE.md) :
# compta connaît le montant/la marge déjà calculés côté frais, jamais les
# détails de facturation — il pousse juste des lignes sur une facture
# EXISTANTE du client. Un produit générique « Frais refacturés » (service,
# sans stock) est créé une fois par société (idempotent) pour porter ces
# lignes, à l'image du produit catalogue utilisé pour les lignes classiques.

_PRODUIT_FRAIS_REFACTURES_NOM = 'Frais refacturés'


def _produit_frais_refactures(company):
    from apps.stock.models import Produit

    produit, _ = Produit.objects.get_or_create(
        company=company, nom=_PRODUIT_FRAIS_REFACTURES_NOM,
        defaults={'prix_vente': Decimal('0'), 'quantite_stock': 0,
                  'seuil_alerte': 0})
    return produit


def ajouter_lignes_frais_refactures(*, facture, lignes, user=None):
    """Ajoute des lignes de frais refacturés sur une ``Facture`` EXISTANTE.

    ``lignes`` est une liste de dicts ``{'designation', 'montant_ht',
    'taux_tva'?}`` (montant déjà majoré de la marge, calculé côté appelant —
    ``apps.compta``). Chaque ligne devient une ``LigneFacture`` (quantité=1,
    prix_unitaire=montant_ht) rattachée au produit générique « Frais
    refacturés » de la société de la facture ; les totaux de la facture sont
    recalculés. Renvoie la liste des ``LigneFacture`` créées. Ne vérifie PAS
    l'anti-doublon (fait côté appelant, sur les frais eux-mêmes)."""
    from apps.ventes.models import LigneFacture

    if not lignes:
        return []
    produit = _produit_frais_refactures(facture.company)
    creees = []
    for ligne in lignes:
        creees.append(LigneFacture.objects.create(
            facture=facture,
            produit=produit,
            designation=ligne.get('designation', '') or _PRODUIT_FRAIS_REFACTURES_NOM,
            quantite=Decimal('1'),
            prix_unitaire=Decimal(ligne.get('montant_ht') or 0),
            taux_tva=ligne.get('taux_tva'),
        ))
    _recalculer_totaux_facture(facture)
    return creees


def _recalculer_totaux_facture(facture):
    """Recalcule les totaux HT/TVA/TTC d'une facture depuis ses lignes.

    Réutilisé par XACC28 après ajout de lignes de frais refacturés — même
    logique de sommation que les autres chemins de création de ligne (taux
    TVA par ligne si renseigné, sinon le taux global de la facture)."""
    total_ht = Decimal('0')
    total_tva = Decimal('0')
    for ligne in facture.lignes.all():
        ht_ligne = ligne.total_ht
        taux = ligne.taux_tva if ligne.taux_tva is not None else facture.taux_tva
        total_ht += ht_ligne
        total_tva += (ht_ligne * Decimal(taux or 0) / Decimal('100'))
    facture.montant_ht = total_ht.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    facture.montant_tva = total_tva.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    facture.montant_ttc = facture.montant_ht + facture.montant_tva
    facture.save(update_fields=['montant_ht', 'montant_tva', 'montant_ttc'])
    return facture


def enregistrer_paiement(*, facture, montant, mode, date_paiement, user,
                         reference='', note=''):
    """Enregistre un ``Paiement`` MANUEL sur une facture EXISTANTE.

    Thin service exposé pour apps.pos (encaissement comptoir XPOS1/XPOS6) —
    même modèle/table que le paiement enregistré depuis l'écran facture,
    aucune duplication de logique."""
    from apps.ventes.models import Paiement
    paiement = Paiement.objects.create(
        company=facture.company,
        facture=facture,
        montant=montant,
        date_paiement=date_paiement,
        mode=mode,
        reference=reference or '',
        note=note or '',
        created_by=user,
    )
    # YLEDG1 — événement documentaire générique (pose du seam pour
    # compta.ecriture_pour_paiement, jamais d'import de son service ici).
    from core.events import paiement_enregistre
    paiement_enregistre.send(
        sender=Paiement, instance=paiement, company=facture.company)
    return paiement


def facture_montant_du(facture):
    """Solde restant dû d'une facture (lecture, thin service pour apps.pos)."""
    return facture.montant_du


def affecter_encaissement_groupe(
        *, company, client, montant, mode, date_paiement, user, factures,
        reference='', repartition=None):
    """ZFAC6 — un seul règlement client réparti sur PLUSIEURS factures.

    Crée un ``Paiement`` par facture réglée : par défaut FIFO (la facture à
    l'échéance la plus ancienne d'abord, jusqu'à épuisement du montant) ; ou
    une répartition EXPLICITE si ``repartition`` (dict facture_id -> montant)
    est fournie. Toutes les factures doivent appartenir à ``company`` ET
    ``client`` (sinon ValueError — le viewset traduit en 400). Atomique :
    échec partiel = rollback total. Bascule le statut « Payée » sur toute
    facture intégralement soldée par ce geste (comportement identique à un
    encaissement facture-par-facture)."""
    from decimal import Decimal

    from django.db import transaction

    from apps.ventes.models import Facture

    montant = Decimal(str(montant))
    if montant <= 0:
        raise ValueError("Le montant doit être positif.")
    if not factures:
        raise ValueError("Aucune facture fournie.")

    for f in factures:
        if f.company_id != company.id or f.client_id != client.id:
            raise ValueError(
                f"La facture {f.reference} n'appartient pas à ce client.")

    paiements = []
    with transaction.atomic():
        locked = list(
            Facture.objects.select_for_update()
            .filter(id__in=[f.id for f in factures])
        )
        by_id = {f.id: f for f in locked}

        if isinstance(repartition, dict) and repartition:
            # Répartition explicite fournie par l'appelant.
            for fid, part in repartition.items():
                facture = by_id.get(int(fid))
                if facture is None:
                    raise ValueError(f"Facture {fid} inconnue dans ce lot.")
                part = Decimal(str(part))
                if part <= 0:
                    continue
                paiements.append(_creer_paiement_groupe(
                    facture, part, mode, date_paiement, user, reference))
        else:
            # FIFO : échéance la plus ancienne d'abord (None en dernier).
            ordonnees = sorted(
                locked,
                key=lambda f: (f.date_echeance is None, f.date_echeance))
            restant = montant
            for facture in ordonnees:
                if restant <= 0:
                    break
                reste_facture = facture.montant_du
                if reste_facture <= 0:
                    continue
                part = min(restant, reste_facture)
                paiements.append(_creer_paiement_groupe(
                    facture, part, mode, date_paiement, user, reference))
                restant -= part

        for facture in locked:
            facture.refresh_from_db()
            if facture.montant_du <= Decimal('0') and \
                    facture.statut not in (
                        Facture.Statut.ANNULEE, Facture.Statut.PAYEE):
                facture.statut = Facture.Statut.PAYEE
                facture.save(update_fields=['statut'])

    return paiements


def _creer_paiement_groupe(facture, montant, mode, date_paiement, user,
                           reference):
    from apps.ventes.models import Paiement

    paiement = Paiement.objects.create(
        company=facture.company, facture=facture, montant=montant,
        date_paiement=date_paiement, mode=mode,
        reference=reference or '', created_by=user,
    )
    # YLEDG1 — événement documentaire générique (même seam que
    # enregistrer_paiement / le geste facture-par-facture).
    from core.events import paiement_enregistre
    paiement_enregistre.send(
        sender=Paiement, instance=paiement, company=facture.company)
    return paiement


def enregistrer_contestation_portail(facture, *, motif_label, commentaire=''):
    """XFAC27 — Trace côté ventes la contestation d'une facture ouverte par
    le client depuis le portail self-service (``apps.compta`` appelle CETTE
    fonction, jamais un import direct de ``apps.ventes.models``/``activity``).
    Ne change AUCUN statut de la facture — seule la réclamation créée côté
    ``apps.litiges`` suspend les relances (LITIGE3)."""
    from . import activity
    return activity.log_facture_contestation_portail(
        facture, motif_label, commentaire=commentaire)


def calculer_date_echeance(*, client, date_emission):
    """XFAC23 — dérive la date d'échéance depuis les conditions de paiement du
    client (délai en jours + report fin de mois).

    Renvoie ``None`` quand le client n'a pas de délai négocié (``crm.Client.
    delai_paiement_jours`` vide) — l'appelant retombe alors sur le comportement
    historique (repli +30 j calculé ailleurs, ex. ``scheduled.
    _echeance_effective``). Ne calcule JAMAIS à la place d'une échéance déjà
    saisie manuellement — c'est à l'appelant de ne pas écraser une valeur
    existante (input freedom).

    Cross-app lecture seule via ``apps.crm.selectors`` (jamais d'import de
    ``apps.crm.models``).
    """
    if client is None or date_emission is None:
        return None
    from apps.crm.selectors import delai_paiement_client
    reglage = delai_paiement_client(client)
    delai = reglage.get('delai_jours')
    if not delai:
        return None
    from datetime import timedelta
    echeance = date_emission + timedelta(days=int(delai))
    if reglage.get('fin_de_mois'):
        import calendar
        last_day = calendar.monthrange(echeance.year, echeance.month)[1]
        echeance = echeance.replace(day=last_day)
    return echeance


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
        # YLEDG1 — événement documentaire générique (pose du seam pour
        # compta.ecriture_pour_paiement).
        from core.events import paiement_enregistre
        paiement_enregistre.send(
            sender=Paiement, instance=paiement, company=facture.company)
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
            # YDOCF4 — facture_paid, exactement une fois au passage
            # résiduel→0 via le webhook de lien de paiement.
            from core.events import facture_paid, facture_payee
            facture_paid.send(
                sender=Facture, facture=facture, montant=montant,
                company=facture.company)
            # YEVNT6 — événement documentaire générique (même transition).
            facture_payee.send(
                sender=Facture, instance=facture, company=facture.company)
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


def _nudge_suppressed(devis, today, engagement_days=3):
    """QX13 — une relance de devis doit-elle être différée/sautée ?

    Trois signaux de réalité (la cadence était aveugle à l'activité) :
      * ``lead.relance_date`` est dans le FUTUR (le vendeur a déjà planifié un
        contact) → on ne double pas ;
      * une activité de contact MANUELLE existe récemment sur le lead (via un
        sélecteur crm optionnel, jamais un import de modèle crm) ;
      * un engagement proposition récent (< engagement_days) sur le ShareLink
        (le client vient de regarder → laisser respirer).

    Retourne True pour SUPPRIMER/différer, False pour laisser passer. Best-
    effort : toute erreur → False (on ne bloque jamais une relance par bug)."""
    from datetime import timedelta
    try:
        lead_id = getattr(devis, 'lead_id', None)
        if lead_id:
            from apps.crm import selectors as crm_selectors
            lead = crm_selectors.get_company_lead(devis.company, lead_id)
            if lead is not None:
                relance = getattr(lead, 'relance_date', None)
                if relance and relance > today:
                    return True
                # Activité de contact manuelle récente — via sélecteur crm si
                # disponible (jamais un import de modèle crm). Coordination :
                # une fonction dédiée ``lead_recent_manual_contact`` pourra être
                # ajoutée côté crm ; en son absence, ce signal est ignoré.
                fn = getattr(crm_selectors, 'lead_recent_manual_contact', None)
                if callable(fn):
                    try:
                        if fn(devis.company, lead_id):
                            return True
                    except Exception:  # noqa: BLE001
                        pass
    except Exception:  # noqa: BLE001
        pass
    # Engagement proposition récent (ShareLink — in-lane).
    try:
        from apps.ventes.models import ShareLink
        link = (ShareLink.objects
                .filter(devis=devis)
                .order_by('-created_at')
                .first())
        seen = getattr(link, 'last_viewed_at', None) if link else None
        if seen is not None:
            seen_date = seen.date() if hasattr(seen, 'date') else seen
            if seen_date >= today - timedelta(days=engagement_days):
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _journaliser_relance_marketing(devis, *, jours, canal, niveau):
    """WIR96 — miroir marketing d'une relance de devis abandonné.

    ``marketing.RelanceDevisAbandonne`` + son service
    ``enregistrer_relance_devis_abandonne`` existaient sans AUCUN appelant :
    aucune relance n'était jamais journalisée côté marketing (le calendrier
    marketing lisait une table toujours vide). On les alimente ici, au moment
    exact où la relance part réellement (après création du ``DevisNudgeLog``,
    qui reste la source de vérité anti-doublon côté ventes).

    Écriture via la frontière ``apps.marketing.services`` uniquement (jamais un
    import des modèles marketing) ; ``devis_id`` reste une référence OPAQUE
    côté marketing. Best-effort : une erreur ne doit jamais faire échouer la
    relance elle-même."""
    if not getattr(devis, 'company_id', None):
        return
    try:
        from apps.marketing.services import (
            enregistrer_relance_devis_abandonne)
        enregistrer_relance_devis_abandonne(
            devis.company,
            devis_id=devis.pk,
            devis_reference=devis.reference or '',
            jours_sans_reponse=jours or 0,
            canal=str(canal or ''),
            note=f'Relance automatique niveau {niveau + 1} (QJ4).',
        )
    except Exception as exc:  # noqa: BLE001 — miroir best-effort
        logger.warning(
            'WIR96: journalisation marketing de la relance échouée '
            'pour devis %s : %s', getattr(devis, 'reference', '?'), exc)


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

        # QX13 — respecte la réalité : relance planifiée, contact manuel
        # récent, ou engagement proposition récent → on diffère ce tour.
        if _nudge_suppressed(devis, today):
            continue

        for idx, jours in enumerate(nudge_days):
            if idx in fired:
                continue  # already sent for this level — idempotent
            trigger_date = envoi_date + __import__('datetime').timedelta(days=jours)
            if today < trigger_date:
                continue  # not due yet

            # Build the public share link for the seller to use.
            # QX13 — via le builder UNIQUE client_links (chemin /proposition/,
            # jamais /proposal/ qui 404 sur le site).
            try:
                share_link = ShareLink.for_devis(devis)
                from apps.ventes.utils.client_links import proposition_url
                proposal_url = proposition_url(share_link.token)
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
                # QX13 — brouillon wa.me vers le CLIENT (le lien proposition à
                # partager), et non le téléphone du vendeur.
                client_phone = (getattr(client, 'telephone', '') or ''
                                if client else '')
                wa_url = (_build_wa_draft_url(client_phone, msg_fr)
                          or proposal_url)
                logger.info(
                    'QJ4 nudge wa_draft devis=%s niveau=%d j+%d vendeur=%s url=%s',
                    devis.reference, idx, jours,
                    getattr(vendeur, 'username', '?'), wa_url)
                # QX13 — le brouillon wa.me ne partait qu'en LOG (invisible) :
                # crée une vraie Notification in-app au vendeur, avec le lien
                # proposition + le brouillon wa.me prêts et un deep-link devis.
                if vendeur is not None:
                    try:
                        from apps.notifications.services import notify
                        from apps.notifications.models import EventType
                        notify(
                            vendeur, EventType.DEVIS_NUDGE_DUE,
                            title=(f'Relance à faire — devis {devis.reference} '
                                   f'(niveau {idx + 1})'),
                            body=(f'Aucune réponse depuis {jours} j. '
                                  f'Proposition : {proposal_url or "—"}'
                                  + (f'\nBrouillon WhatsApp : {wa_url}'
                                     if wa_url else '')),
                            link=f'/ventes/devis?devis={devis.id}',
                            company=devis.company)
                    except Exception as exc:  # noqa: BLE001 — best-effort
                        logger.warning(
                            'QX13: notification relance échec devis %s : %s',
                            devis.reference, exc)

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
                _journaliser_relance_marketing(
                    devis, jours=jours, canal=canal, niveau=idx)
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
    from .models import Devis

    # QX11 — date Casablanca-aware (comme ses tâches sœurs), plus
    # ``date.today()`` (fuseau serveur) qui pouvait décaler l'expiration d'un
    # jour selon l'UTC.
    from .scheduled import casablanca_today
    today = casablanca_today()
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

        # YEVNT10 — une mutation AUTOMATIQUE (cron, hors requête HTTP) échappe
        # à l'audit par signaux request-scopé. Cette expiration est journalisée
        # « système » CÔTÉ audit, via un abonnement à l'événement
        # `devis_expired` émis ci-dessous (apps/audit/receivers.py) — jamais par
        # un import direct ventes→audit (M4 : les réactions passent par
        # core.events).

        # YEVNT2 — événement métier (notifications/audit s'abonnent), jamais
        # réémis pour un devis déjà expiré (garde amont via le queryset ENVOYE
        # + is_expired). Best-effort : ne casse jamais le sweep.
        try:
            from core.events import devis_expired
            devis_expired.send(
                sender=Devis, devis=devis, ancien_statut='envoye')
        except Exception as exc:  # noqa: BLE001
            logger.warning('YEVNT2: devis_expired échoué pour devis %s : %s',
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


# ── XFSM1 — Facturation SAV hors garantie depuis le ticket ──────────────────
# apps.sav ne peut PAS importer apps.ventes.models directement (règle de
# modularité CLAUDE.md) : cette fonction est son unique porte d'entrée pour
# générer une facture brouillon depuis un ticket SAV.

def _main_oeuvre_produit(company):
    """Produit catalogue (service, non stocké) porteur de la ligne
    main-d'œuvre SAV — get-or-create idempotent, un seul par société.
    Jamais décrémenté (aucun mouvement de stock ne le référence)."""
    from apps.stock.models import Produit
    produit, _created = Produit.objects.get_or_create(
        company=company, sku='SAV-MO', defaults={
            'nom': "Main-d'œuvre SAV",
            'prix_vente': Decimal('0'),
            'quantite_stock': 0,
        })
    return produit


def generer_facture_ticket_sav(*, ticket, sous_garantie, pieces, user):
    """XFSM1 — construit une ``Facture`` BROUILLON pour un ticket SAV hors
    garantie (réels → facture) : lignes pièces (prix de VENTE catalogue,
    jamais ``prix_achat``) + ligne main-d'œuvre (taux horaire
    ``CompanyProfile.taux_horaire_sav`` × ``ticket.heures_main_oeuvre``).

    Quand ``sous_garantie`` est vrai (ticket sous garantie ou contrat actif
    couvrant), TOUTES les lignes sont posées à 0 DH avec la mention
    « couvert garantie/contrat » dans leur désignation — le document reste
    traçable sans jamais facturer un client couvert.

    ``pieces`` : itérable d'objets exposant ``produit`` (stock.Produit) et
    ``quantite`` (déjà scopés société par l'appelant — sav.views). Référence
    via ``apps.ventes.utils.references`` (jamais count()+1).

    IDEMPOTENT : si ``ticket.facture_id_ext`` pointe déjà vers une facture
    non annulée, la renvoie telle quelle plutôt que d'en créer une seconde.
    Renvoie la ``Facture`` créée (ou réutilisée)."""
    from .models import Facture, LigneFacture
    from .utils.company_settings import tva_standard
    from .utils.references import create_with_reference

    if ticket.facture_id_ext:
        existante = Facture.objects.filter(
            pk=ticket.facture_id_ext, company=ticket.company
        ).exclude(statut=Facture.Statut.ANNULEE).first()
        if existante is not None:
            return existante

    company = ticket.company
    taux_tva_defaut = tva_standard(company)

    def _create(ref):
        return Facture.objects.create(
            reference=ref, company=company, client=ticket.client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.COMPLETE,
            libelle=f'SAV {ticket.reference} — hors garantie',
            created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)

    suffixe_couvert = ' (couvert garantie/contrat)' if sous_garantie else ''

    for piece in pieces:
        produit = piece.produit
        quantite = piece.quantite
        prix_unitaire = (
            Decimal('0') if sous_garantie
            else Decimal(str(produit.prix_vente or 0)))
        LigneFacture.objects.create(
            facture=facture, produit=produit,
            designation=f'{produit.nom}{suffixe_couvert}',
            quantite=quantite, prix_unitaire=prix_unitaire,
            taux_tva=(produit.tva if produit.tva is not None
                      else taux_tva_defaut),
        )

    heures = ticket.heures_main_oeuvre
    if heures:
        profile_taux = None
        try:
            from apps.parametres.models import CompanyProfile
            profile_taux = CompanyProfile.get(company).taux_horaire_sav
        except Exception:  # pragma: no cover - défensif
            profile_taux = None
        taux_horaire = (
            Decimal('0') if sous_garantie
            else Decimal(str(profile_taux)) if profile_taux is not None
            else None)
        if taux_horaire is not None:
            mo_produit = _main_oeuvre_produit(company)
            LigneFacture.objects.create(
                facture=facture, produit=mo_produit,
                designation=f"Main-d'œuvre{suffixe_couvert}",
                quantite=heures, prix_unitaire=taux_horaire,
                taux_tva=taux_tva_defaut,
            )

    ticket.facture_id_ext = facture.id
    ticket.save(update_fields=['facture_id_ext'])
    return facture


# ── XCTR22 — Encaissement récurrent automatique (tokenisation / mandat) ────

def mandat_actif_pour_client(client):
    """Renvoie le ``MandatPaiement`` ACTIF du client, ou None.

    Lecture pure ; jamais d'effet de bord. Sert de garde d'entrée pour
    ``debiter_mandat_pour_facture`` — un client sans mandat actif (le cas
    par défaut) fait strictement l'encaissement manuel actuel."""
    from apps.ventes.models import MandatPaiement
    return (
        MandatPaiement.objects
        .filter(client=client, statut=MandatPaiement.Statut.ACTIF)
        .exclude(token='')
        .order_by('-created_at')
        .first()
    )


DUNNING_RETRY_DAYS = (1, 3, 7)


def debiter_mandat_pour_facture(*, facture, periode, retry_index=0):
    """XCTR22 — débite le mandat actif du client de ``facture`` pour la
    période donnée, via `payments.providers`.

    Appelé APRÈS la création d'une facture de cycle récurrent
    (`creer_facture_contrat`/`facturer_ligne_echeance` — contrats/sav restent
    les points d'entrée existants ; ceci est un branchement ADDITIF appelé
    depuis leurs services). Sans mandat actif → no-op silencieux (retourne
    None, comportement actuel intact). Avec mandat :
      - succès → crée un `Paiement` rapproché (comme un encaissement manuel)
        + une `TentativeDebitMandat` `reussi` ; jamais deux débits RÉUSSIS
        pour la même (mandat, periode) — idempotent.
      - échec → `TentativeDebitMandat` `echec` avec motif + programme la
        prochaine retentative (`DUNNING_RETRY_DAYS`, défaut J+1/J+3/J+7) et
        notifie le client (lien de mise à jour de carte — best-effort).

    Renvoie le `Paiement` créé en cas de succès, sinon None.
    """
    from django.db import transaction
    from django.utils import timezone
    from datetime import timedelta
    from apps.ventes.models import TentativeDebitMandat, Paiement
    from apps.ventes.payments.providers import get_provider

    mandat = mandat_actif_pour_client(facture.client)
    if mandat is None:
        return None

    # Jamais deux débits RÉUSSIS pour la même période — idempotence.
    deja_reussi = TentativeDebitMandat.objects.filter(
        mandat=mandat, periode=periode,
        statut=TentativeDebitMandat.Statut.REUSSI).exists()
    if deja_reussi:
        return None

    provider = get_provider(mandat.provider)
    result = provider.charge(token=mandat.token, montant=facture.montant_ttc)

    with transaction.atomic():
        if result.get('ok'):
            paiement = Paiement.objects.create(
                company=facture.company, facture=facture,
                montant=facture.montant_ttc,
                date_paiement=timezone.localdate(),
                mode=Paiement.Mode.CARTE,
                reference=(result.get('provider_ref') or '')[:120],
                note='Débit automatique (mandat de paiement récurrent).',
            )
            TentativeDebitMandat.objects.create(
                company=facture.company, mandat=mandat, periode=periode,
                statut=TentativeDebitMandat.Statut.REUSSI,
                paiement=paiement,
            )
            return paiement

        tentatives_precedentes = TentativeDebitMandat.objects.filter(
            mandat=mandat, periode=periode,
            statut=TentativeDebitMandat.Statut.ECHEC).count()
        idx = min(tentatives_precedentes, len(DUNNING_RETRY_DAYS) - 1)
        prochaine = (
            timezone.localdate() + timedelta(days=DUNNING_RETRY_DAYS[idx]))
        TentativeDebitMandat.objects.create(
            company=facture.company, mandat=mandat, periode=periode,
            statut=TentativeDebitMandat.Statut.ECHEC,
            motif_echec=(result.get('motif_echec') or '')[:255],
            prochaine_retentative=prochaine,
        )

    try:
        from apps.notifications.services import notify
        client = facture.client
        if client is not None and getattr(client, 'created_by', None):
            notify(
                client.created_by, 'mandat_debit_echec',
                f'Débit automatique échoué — {facture.reference}',
                body=(f'Le débit automatique de {facture.montant_ttc} MAD '
                      f'a échoué pour {client.nom}. Mettez à jour la carte.'),
                link='/ventes/factures',
                company=facture.company,
            )
    except Exception:  # noqa: BLE001 — best-effort
        pass

    return None


# ── ZFSM4 — Facturation directe d'une intervention hors contrat/ticket ──────
# apps.installations ne peut PAS importer apps.ventes.models directement
# (règle de modularité CLAUDE.md) : cette fonction est son unique porte
# d'entrée pour générer une facture brouillon depuis une intervention payante
# (dépannage résidentiel facturé sur place, prestation ponctuelle) — DISTINCT
# de XFSM1/XCTR4 qui facturent depuis un TICKET SAV.

def generer_facture_intervention(*, intervention, user):
    """ZFSM4 — construit une ``Facture`` BROUILLON pour une intervention hors
    contrat/ticket : lignes matériel depuis ``ConsommationLigne`` (prix de
    VENTE catalogue, JAMAIS ``prix_achat``) + ligne main-d'œuvre (durée F15
    ``field_capture.crew_time`` × ``CompanyProfile.taux_horaire_sav``, le
    taux horaire paramétrable réutilisé de XFSM1 — pas de nouveau champ).

    Référence via ``apps.ventes.utils.references`` (jamais count()+1). PDF
    legacy (pas ``/proposal`` — règle #4 : ce chemin ne touche jamais le
    moteur de devis client).

    IDEMPOTENT : si ``intervention.facture_id`` pointe déjà vers une facture
    non annulée, la renvoie telle quelle plutôt que d'en créer une seconde.
    Renvoie la ``Facture`` créée (ou réutilisée)."""
    from .models import Facture, LigneFacture
    from .utils.company_settings import tva_standard
    from .utils.references import create_with_reference

    if intervention.facture_id:
        existante = Facture.objects.filter(
            pk=intervention.facture_id, company=intervention.company
        ).exclude(statut=Facture.Statut.ANNULEE).first()
        if existante is not None:
            return existante

    installation = intervention.installation
    if installation is None or installation.client_id is None:
        raise ValueError(
            "generer_facture_intervention requires an intervention attached "
            "to a chantier with a resolved client")
    client = installation.client
    company = intervention.company or installation.company
    taux_tva_defaut = tva_standard(company)

    def _create(ref):
        return Facture.objects.create(
            reference=ref, company=company, client=client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.COMPLETE,
            libelle=(f'Intervention {intervention.get_type_intervention_display()} '
                     f'— {installation.reference}'),
            created_by=user,
        )

    facture = create_with_reference(Facture, 'FAC', company, _create)

    consommation = getattr(intervention, 'consommation', None)
    if consommation is not None:
        for ligne in consommation.lignes.all():
            produit = ligne.produit
            quantite = ligne.quantite_utilisee
            if produit is None or not quantite:
                continue
            LigneFacture.objects.create(
                facture=facture, produit=produit,
                designation=ligne.designation or produit.nom,
                quantite=quantite,
                prix_unitaire=Decimal(str(produit.prix_vente or 0)),
                taux_tva=(produit.tva if produit.tva is not None
                          else taux_tva_defaut),
            )

    from apps.installations import field_capture
    heures_min = field_capture.crew_time(intervention).get('duree_sur_site_min')
    if heures_min:
        profile_taux = None
        try:
            from apps.parametres.models import CompanyProfile
            profile_taux = CompanyProfile.get(company).taux_horaire_sav
        except Exception:  # pragma: no cover - défensif
            profile_taux = None
        if profile_taux is not None:
            heures = (Decimal(heures_min) / Decimal(60)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
            mo_produit = _main_oeuvre_produit(company)
            LigneFacture.objects.create(
                facture=facture, produit=mo_produit,
                designation="Main-d'œuvre",
                quantite=heures, prix_unitaire=Decimal(str(profile_taux)),
                taux_tva=taux_tva_defaut,
            )

    intervention.facture_id = facture.id
    intervention.save(update_fields=['facture_id'])
    logger.info(
        'ZFSM4: facture %s créée depuis intervention %s (company %s)',
        facture.reference, intervention.id, getattr(company, 'id', '?'))
    return facture


# ── ZFSM5 — Devis d'upsell créé sur place depuis l'intervention ────────────
# apps.installations ne peut PAS importer apps.ventes.models directement
# (règle de modularité CLAUDE.md) : cette fonction est son unique porte
# d'entrée pour générer un devis brouillon d'upsell depuis une intervention
# (opportunité vue sur place — 2ᵉ site, batterie, extension) — DISTINCT de
# XFSM18 (réserve → devis de RÉPARATION, reprise d'un défaut).

def create_devis_upsell_from_intervention(*, intervention, user):
    """ZFSM5 — crée un DEVIS brouillon d'upsell à partir d'une intervention,
    pour le cas où le technicien voit une opportunité sur place. Le client
    est celui du CHANTIER (`intervention.installation.client`, déjà résolu —
    pattern `create_devis_from_reserve`, aucune re-résolution lead
    nécessaire). La description est pré-remplie depuis le chantier/type
    d'intervention ; aucune ligne n'est créée (une LigneDevis exige un
    Produit du catalogue) — le devis brouillon est laissé à compléter dans
    l'éditeur.

    Le devis reste ``brouillon`` : ce service CRÉE, il ne change aucun statut
    aval (règle #4). Aucun impact sur `/proposal`.

    IDEMPOTENT : si ``intervention.devis_upsell_id`` pointe déjà vers un
    devis existant, le renvoie tel quel plutôt que d'en créer un second.
    Renvoie le ``Devis`` créé (ou réutilisé)."""
    from .models import Devis
    from .utils.references import create_with_reference

    if intervention.devis_upsell_id:
        existant = Devis.objects.filter(
            pk=intervention.devis_upsell_id, company=intervention.company
        ).first()
        if existant is not None:
            return existant

    installation = intervention.installation
    if installation is None or installation.client_id is None:
        raise ValueError(
            "create_devis_upsell_from_intervention requires an intervention "
            "attached to a chantier with a resolved client")
    client = installation.client
    company = intervention.company or installation.company

    note = (
        "Devis d'upsell généré depuis une intervention sur place.\n"
        f"Chantier : {installation.reference}\n"
        f"Type d'intervention : {intervention.get_type_intervention_display()}")

    def _create(ref):
        return Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            statut=Devis.Statut.BROUILLON,
            created_by=user,
            note=note,
        )

    devis = create_with_reference(Devis, 'DEV', company, _create)
    intervention.devis_upsell_id = devis.id
    intervention.save(update_fields=['devis_upsell_id'])
    logger.info(
        'ZFSM5: devis upsell %s créé depuis intervention %s (company %s)',
        devis.reference, intervention.id, getattr(company, 'id', '?'))
    return devis


def _round2(x):
    """Arrondi MAD à 2 décimales, HALF_UP (comme le reste du module)."""
    return Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _regle_applicable(regles, produit, quantite):
    """XSAL2 — la règle la plus spécifique dont le palier est atteint.

    Ordre : spécificité de portée (produit > catégorie > marque > catalogue)
    d'abord, puis priorité explicite, puis palier le plus élevé atteint par
    `quantite`. Une règle inactive ou dont le palier n'est pas atteint est
    ignorée."""
    candidates = [
        r for r in regles
        if r.actif and r.matches_produit(produit) and quantite >= r.quantite_min
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda r: (r.specificite, r.priorite, r.quantite_min), reverse=True)
    return candidates[0]


def _appliquer_regle(regle, prix_base):
    """XSAL2 — applique une règle résolue au prix de base (jamais à
    `prix_achat`)."""
    if regle.type_regle == regle.TypeRegle.PRIX_FIXE:
        return _round2(regle.valeur)
    if regle.type_regle == regle.TypeRegle.REMISE_PCT:
        return _round2(prix_base * (1 - regle.valeur / 100))
    if regle.type_regle == regle.TypeRegle.FORMULE_SUR_PRIX_VENTE:
        return _round2(prix_base * regle.valeur)
    return _round2(prix_base)  # pragma: no cover - défensif, type inconnu


def _prix_contractuel(client, produit):
    """NTCPQ5 — Prix contractuel actif pour un couple client/produit.

    Lecture cross-app cpq via import LOCAL (aucun import de cpq.models au niveau
    module ; évite tout cycle ventes↔cpq). Renvoie l'instance ``PrixContractuel``
    active la plus récente, ou ``None``."""
    if client is None or produit is None:
        return None
    company_id = getattr(client, 'company_id', None)
    if company_id is None:
        return None
    from apps.cpq.models import PrixContractuel
    candidates = PrixContractuel.objects.filter(
        company_id=company_id, client_id=client.id, produit_id=produit.id,
    ).order_by('-date_creation')
    for candidate in candidates:
        if candidate.est_actif:
            return candidate
    return None


def _resolve_liste_prix(client):
    """NTCPQ4 — Sélectionne la liste de prix applicable à un client.

    Priorité : liste explicitement assignée au client (``client.liste_prix``)
    si elle est active > liste de la société correspondant au SEGMENT du client
    (la plus récente active) > aucune. Les listes hors fenêtre de validité ou
    archivées (``est_active`` False) ne sont JAMAIS retenues, même si leur
    segment correspond au client (NTCPQ4). Renvoie une ``ListePrix`` active ou
    ``None``."""
    if client is None:
        return None
    liste = getattr(client, 'liste_prix', None)
    if liste is not None and liste.est_active:
        return liste
    # Segment du client : champ dédié s'il existe, sinon type de client.
    segment = (getattr(client, 'segment_client', '')
               or getattr(client, 'type_client', '') or '')
    company_id = getattr(client, 'company_id', None)
    if segment and company_id is not None:
        from apps.ventes.models import ListePrix
        candidates = ListePrix.objects.filter(
            company_id=company_id, segment_client=segment, archived=False,
        ).order_by('-created_at')
        for candidate in candidates:
            if candidate.est_active:
                return candidate
    return None


def prix_applicable(*, produit, client=None, quantite=1):
    """XSAL1/XSAL2 — Prix unitaire résolu pour un produit/client/quantité.

    Ordre de résolution :
      1. `client.liste_prix` (si assignée et active) → règles de paliers/
         portée (XSAL2, la plus spécifique satisfaite par `quantite`) →
         sinon le prix de ligne fixe (`LignePrixListe`) → sinon
         `produit.prix_vente`.
      2. Sans liste (client=None, `liste_prix` vide, ou liste inactive) →
         `produit.prix_vente` (comportement historique, octet-identique).

    Ne renvoie et ne consulte JAMAIS `produit.prix_achat`. Renvoie un dict
    `{"prix": Decimal, "source": "liste"|"regle"|"standard",
    "liste_nom": str|None}` pour que l'appelant (endpoint XSAL3) puisse
    afficher le badge « Tarif : <nom de la liste> »."""
    quantite = Decimal(str(quantite or 1))
    prix_standard = produit.prix_vente

    # NTCPQ5 — priorité 1 : prix contractuel négocié (client + produit). Écrase
    # toute liste de prix générique (segment/assignée) pour ce couple.
    contractuel = _prix_contractuel(client, produit)
    if contractuel is not None:
        return {
            'prix': contractuel.prix_ht,
            'source': 'contractuel',
            'liste_nom': contractuel.motif or None,
        }

    liste = _resolve_liste_prix(client)
    if liste is None:
        return {'prix': prix_standard, 'source': 'standard', 'liste_nom': None}

    regles = list(liste.regles.filter(actif=True).select_related('produit'))
    regle = _regle_applicable(regles, produit, quantite)
    if regle is not None:
        prix_ligne = liste.lignes.filter(produit=produit).values_list(
            'prix_unitaire', flat=True).first()
        base = prix_ligne if prix_ligne is not None else prix_standard
        return {
            'prix': _appliquer_regle(regle, base),
            'source': 'regle',
            'liste_nom': liste.nom,
        }

    ligne = liste.lignes.filter(produit=produit).first()
    if ligne is not None:
        return {'prix': ligne.prix_unitaire, 'source': 'liste', 'liste_nom': liste.nom}

    return {'prix': prix_standard, 'source': 'standard', 'liste_nom': None}


# ═════════════════════════════════════════════════════════════════════════════
# PV47 — Le BORDEREAU électrique en LIGNES DE DEVIS (opt-in, jamais silencieux)
# ═════════════════════════════════════════════════════════════════════════════
# La conception électrique (PV41) produit un bordereau TECHNIQUE : câbles,
# fusibles, parafoudres, sectionneurs, disjoncteurs, différentiels, coffrets.
# Le devis, lui, porte des lignes CHIFFRÉES. Le pont entre les deux est
# DÉLIBÉRÉMENT un geste explicite de l'utilisateur (une action, un clic) et
# jamais un effet de bord d'un recalcul d'étude : sans cela, chaque
# re-conception ferait bouger le prix d'un devis sous les yeux du client.
#
# Deux issues par ligne de bordereau, aucune troisième :
#   * un produit du catalogue correspond → ligne PRODUIT à SON prix. Les SKU
#     PVG3 (câbles/protections) ont un prix VIDE tant que le fondateur ne les a
#     pas renseignés : la ligne part donc à 0 et son intitulé le DIT
#     (« — à chiffrer »). On n'invente jamais un prix ;
#   * aucun produit ne correspond → ligne de NOTE « à chiffrer », sans produit
#     ni prix, ET la ligne est reportée dans les MANQUES du catalogue (c'est la
#     donnée qui dit au fondateur ce qu'il lui reste à référencer).
#
# Les lignes de bordereau NON électriques (structure : rails, pinces, crochets)
# sont IGNORÉES : elles relèvent des postes « Structures & fixation » que le
# devis compose déjà, et les recopier en notes ne ferait que du bruit.

#: Catégories catalogue où l'on cherche une correspondance (taxonomie de
#: ``stock.seed_catalogue.TAXONOMIE``).
BOQ_CATEGORIES = ('Câbles', 'Protection & accessoires')

#: Familles d'organes reconnues, du motif le plus SPÉCIFIQUE au plus général —
#: le PREMIER motif satisfait gagne. L'ordre est porteur de sens :
#: « porte-fusible » avant « fusible » (sinon tout porte-fusible serait classé
#: fusible), « sectionneur-fusible » avant « fusible » de même, et les CÂBLES
#: sont éclatés par usage : un câble solaire DC et un câble AC U-1000 R2V ont
#: la même section possible mais ne sont PAS interchangeables.
#: Chaque motif est un tuple de fragments dont TOUS doivent être présents.
#: Une désignation sans famille connue est ignorée (lignes de structure).
_BOQ_FAMILLES = (
    ('porte_fusible', (('porte-fusible',), ('porte fusible',))),
    ('sectionneur', (('sectionneur',),)),
    ('fusible', (('fusible',),)),
    ('cable_solaire', (('cable', 'solaire'), ('cable', 'h1z2z2'))),
    ('cable_terre', (('cable', 'terre'),)),
    ('cable_batterie', (('cable', 'batterie'),)),
    ('cable_ac', (('cable', 'u-1000'), ('cable', 'r2v'))),
    ('cable', (('cable',),)),
    ('parafoudre', (('parafoudre',),)),
    ('differentiel', (('differentiel',), ('ddr',))),
    ('disjoncteur', (('disjoncteur',),)),
    ('coffret', (('coffret',),)),
)

#: Familles pour lesquelles la SECTION (mm²) est la grandeur dimensionnante.
_BOQ_FAMILLES_CABLE = frozenset({
    'cable_solaire', 'cable_terre', 'cable_batterie', 'cable_ac', 'cable'})

#: Familles pour lesquelles le CALIBRE (A) est la grandeur dimensionnante — et
#: donc une CONDITION d'appariement. Un parafoudre ou un coffret, eux, ne se
#: choisissent pas au calibre : exiger une égalité d'ampères sur eux
#: fabriquerait de faux manques (le coffret AC porte le calibre du disjoncteur
#: qu'il abrite, pas le sien).
_BOQ_FAMILLES_CALIBREES = frozenset({
    'fusible', 'porte_fusible', 'sectionneur', 'disjoncteur', 'differentiel'})

#: Suffixe apposé à toute ligne que le catalogue ne sait pas encore chiffrer.
BOQ_SUFFIXE_A_CHIFFRER = ' — à chiffrer'

_BOQ_NOMBRE_RE = re.compile(r'\d+(?:[.,]\d+)?')


def _boq_normaliser(texte):
    """Minuscules sans accents — la comparaison ne dépend pas d'un « é »."""
    texte = (texte or '').lower()
    for source, cible in (('é', 'e'), ('è', 'e'), ('ê', 'e'), ('â', 'a'),
                          ('à', 'a'), ('î', 'i'), ('ï', 'i'), ('ô', 'o'),
                          ('û', 'u'), ('ù', 'u'), ('ç', 'c'), ('²', '2')):
        texte = texte.replace(source, cible)
    return texte


def _boq_famille(texte):
    """Famille d'organe d'une désignation, ou ``None`` si non électrique."""
    normalise = _boq_normaliser(texte)
    for famille, motifs in _BOQ_FAMILLES:
        for motif in motifs:
            if all(fragment in normalise for fragment in motif):
                return famille
    return None


def _boq_polarite(texte):
    """``'mono'`` / ``'tri'`` / ``None`` — nombre de pôles d'un organe AC.

    Le moteur écrit « bipolaire »/« tétrapolaire » (NF C 15-100), le catalogue
    « monophasé »/« tétrapolaire », et la tension réseau tranche aussi
    (230 V ↔ 400 V). Poser un tétrapolaire sur du monophasé n'est pas une
    approximation de prix : c'est un organe qui ne se câble pas.
    """
    normalise = _boq_normaliser(texte)
    if any(motif in normalise for motif in
           ('triphas', 'tetrapolaire', '400 v', ' 4p')):
        return 'tri'
    if any(motif in normalise for motif in
           ('monophas', 'bipolaire', '230 v', ' 1p')):
        return 'mono'
    return None


def _boq_nombres(texte):
    """Les nombres d'un texte, normalisés (« 6,0 mm² » et « 6 mm² » → 6)."""
    valeurs = set()
    for brut in _BOQ_NOMBRE_RE.findall(_boq_normaliser(texte)):
        try:
            valeurs.add(float(brut.replace(',', '.')))
        except ValueError:
            continue
    return valeurs


def _boq_courant(texte):
    """Le CALIBRE en ampères d'un texte (« 32 A »), ou ``None``."""
    trouve = re.search(r'(\d+(?:[.,]\d+)?)\s*a\b', _boq_normaliser(texte))
    if not trouve:
        return None
    try:
        return float(trouve.group(1).replace(',', '.'))
    except ValueError:
        return None


def _boq_section(texte):
    """La SECTION en mm² d'un texte (« 6,0 mm² »), ou ``None``."""
    trouve = re.search(r'(\d+(?:[.,]\d+)?)\s*mm2', _boq_normaliser(texte))
    if not trouve:
        return None
    try:
        return float(trouve.group(1).replace(',', '.'))
    except ValueError:
        return None


def _boq_courant_alternatif(texte):
    """``True`` (AC) / ``False`` (DC) / ``None`` — discriminant d'un organe.

    Un parafoudre DC posé à la place d'un parafoudre AC n'est pas une
    approximation, c'est une erreur de dossier : le discriminant est donc une
    CONDITION de correspondance, jamais un simple critère de tri.
    """
    normalise = _boq_normaliser(texte)
    a_dc = bool(re.search(r'\bdc\b|\bvdc\b', normalise))
    a_ac = bool(re.search(r'\bac\b', normalise))
    if a_dc and not a_ac:
        return False
    if a_ac and not a_dc:
        return True
    return None


def _boq_candidats(company):
    """Produits catalogue quotables des catégories du bordereau.

    Portée identique à ``_pick_product`` (PV15) : société de l'utilisateur OU
    catalogue global — jamais celui d'un autre tenant.
    """
    from django.db.models import Q
    from apps.stock.models import Produit

    filtre = Q(company=company) | Q(company__isnull=True)
    qs = Produit.objects.filter(
        filtre, categorie__nom__in=BOQ_CATEGORIES, is_archived=False)
    return list(qs.select_related('categorie').order_by('nom'))


def _boq_apparier(designation, spec, candidats):
    """Produit catalogue correspondant à une ligne de bordereau, ou ``None``.

    Quatre conditions CUMULATIVES :

    1. même FAMILLE d'organe (câble solaire, câble AC, fusible, parafoudre…) ;
    2. même nature de courant quand les deux la portent (un parafoudre DC ne
       remplace pas un parafoudre AC) ;
    3. même POLARITÉ quand les deux la portent (un tétrapolaire ne se câble
       pas sur du monophasé) ;
    4. même grandeur DIMENSIONNANTE quand la ligne en porte une — la section
       pour un câble, le calibre en ampères pour un organe de coupure. Une
       ligne calibrée sans calibre correspondant au catalogue N'EST PAS
       appariée : proposer un 15 A à la place d'un 16 A calculé serait une
       erreur d'étude déguisée en commodité.
    """
    famille = _boq_famille(designation)
    if famille is None:
        return None
    texte = '%s %s' % (designation or '', spec or '')
    alternatif = _boq_courant_alternatif(texte)
    polarite = _boq_polarite(texte)
    section = (_boq_section(designation)
               if famille in _BOQ_FAMILLES_CABLE else None)
    calibre = (_boq_courant(spec) or _boq_courant(designation)
               if famille in _BOQ_FAMILLES_CALIBREES else None)

    meilleur = None
    meilleur_score = None
    for produit in candidats:
        nom = produit.nom or ''
        if _boq_famille(nom) != famille:
            continue
        nature = _boq_courant_alternatif(nom)
        if alternatif is not None and nature is not None \
                and nature != alternatif:
            continue
        pole = _boq_polarite(nom)
        if polarite is not None and pole is not None and pole != polarite:
            continue
        if section is not None:
            if _boq_section(nom) != section:
                continue
        elif calibre is not None:
            if _boq_courant(nom) != calibre:
                continue
        # À conditions égales, le nom au recouvrement de nombres le plus
        # large gagne, puis le plus court (le moins spécifié inutilement).
        score = (len(_boq_nombres(nom) & _boq_nombres(texte)), -len(nom))
        if meilleur_score is None or score > meilleur_score:
            meilleur_score = score
            meilleur = produit
    return meilleur


def _boq_prix(produit):
    try:
        return Decimal(str(getattr(produit, 'prix_vente', 0) or 0))
    except (ArithmeticError, TypeError, ValueError):
        return Decimal('0')


def ajouter_lignes_boq_electrique(devis, user=None):
    """PV47 — ajoute au devis les lignes issues du bordereau électrique (PV41).

    Rend TOUJOURS le même dict ``{creees, lignes, manques, deja_presentes}`` :

    * ``creees`` — nombre de lignes ajoutées ;
    * ``lignes`` — une entrée par ligne créée (``designation``, ``produit``,
      ``quantite``, ``type_ligne``, ``a_chiffrer``) ;
    * ``manques`` — les lignes de bordereau qu'AUCUN produit du catalogue ne
      couvre. C'est la liste de courses du référencement, pas une erreur ;
    * ``deja_presentes`` — lignes ignorées parce que le devis les portait déjà
      (garde anti-double-clic : ré-appeler l'action ne duplique rien).

    N'écrit QUE des lignes : ni statut, ni prix inventé (règle #4). Un produit
    sans prix part à 0 avec « à chiffrer » dans son intitulé — visible à
    l'écran comme sur le PDF.
    """
    from django.db import transaction
    from .models import LigneDevis

    design = getattr(devis, 'electrical_design', None)
    bom = (design or {}).get('bom') if isinstance(design, dict) else None
    if not isinstance(bom, list) or not bom:
        return {'creees': 0, 'lignes': [], 'manques': [], 'deja_presentes': []}

    candidats = _boq_candidats(devis.company)
    lignes_existantes = list(devis.lignes.all())
    existantes = {(li.designation or '').strip() for li in lignes_existantes}
    ordre = max([int(li.ordre or 0) for li in lignes_existantes] or [0]) + 1

    creees = []
    manques = []
    deja = []
    with transaction.atomic():
        for item in bom:
            if not isinstance(item, dict):
                continue
            designation = (item.get('designation') or '').strip()
            if not designation or _boq_famille(designation) is None:
                continue
            spec = item.get('spec') or ''
            produit = _boq_apparier(designation, spec, candidats)
            a_chiffrer = produit is None or _boq_prix(produit) <= 0
            intitule = (designation + (BOQ_SUFFIXE_A_CHIFFRER
                                       if a_chiffrer else ''))[:255]
            if intitule in existantes:
                deja.append(designation)
                continue
            try:
                quantite = (Decimal(str(item.get('quantite')))
                            if item.get('quantite') not in (None, '')
                            else Decimal('1'))
            except (ArithmeticError, TypeError, ValueError):
                quantite = Decimal('1')

            if produit is None:
                manques.append({'designation': designation,
                                'quantite': float(quantite), 'spec': spec})
                LigneDevis.objects.create(
                    devis=devis, produit=None, designation=intitule,
                    quantite=None, prix_unitaire=None, remise=Decimal('0'),
                    taux_tva=None, type_ligne=LigneDevis.TypeLigne.NOTE,
                    ordre=ordre)
                creees.append({'designation': intitule, 'produit': None,
                               'quantite': None, 'type_ligne': 'note',
                               'a_chiffrer': True})
            else:
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=intitule,
                    quantite=quantite, prix_unitaire=_boq_prix(produit),
                    remise=Decimal('0'), taux_tva=None,
                    type_ligne=LigneDevis.TypeLigne.PRODUIT, ordre=ordre)
                creees.append({'designation': intitule, 'produit': produit.pk,
                               'quantite': float(quantite),
                               'type_ligne': 'produit',
                               'a_chiffrer': a_chiffrer})
            existantes.add(intitule)
            ordre += 1

    if creees:
        logger.info('PV47 — %d ligne(s) de bordereau électrique ajoutées au '
                    'devis %s par %s', len(creees), devis.pk, user)
    return {'creees': len(creees), 'lignes': creees, 'manques': manques,
            'deja_presentes': deja}
