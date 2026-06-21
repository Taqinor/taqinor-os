"""Services Ventes — point d'entrée cross-app pour les ÉCRITURES ventes.

Les apps tierces (sav, installations, crm…) passent par ces fonctions pour
créer ou modifier des entités ventes (Facture, Paiement…) au lieu d'importer
directement les models ventes. Cela respecte la règle de modularité (CLAUDE.md).
"""
from decimal import Decimal, ROUND_HALF_UP
import logging
import re

logger = logging.getLogger(__name__)

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
            roof_layout=layout,
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
        'Q3: devis %s built from layout (%d lignes, %.2f kWc, company %s)',
        devis.reference, len(line_specs), kwc, getattr(company, 'id', '?'))
    return devis


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
