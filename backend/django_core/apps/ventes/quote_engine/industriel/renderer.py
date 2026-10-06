# flake8: noqa
"""Industriel renderer selection + data augmentation for the single engine.

``generate_premium_devis_pdf`` builds the quote data once, then asks this module
whether the premium multi-page INDUSTRIEL (CFO) layout applies. If so it renders
PDF bytes; otherwise it raises ``Unsupported`` and the engine falls back to the
legacy renderer (which still serves the industriel one-page format and is the
automatic off-switch). One engine, one data builder.

Renders only — never changes a devis status (CLAUDE.md rule #4).
"""
from __future__ import annotations
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from ..ci.synthese import chiffres_cles, synthese_ci


class Unsupported(Exception):
    """The devis/options are outside the industriel renderer's scope."""


def is_industrial(devis, options=None) -> bool:
    """True when the premium multi-page INDUSTRIEL layout should render this quote.

    Industriel market mode + the full/premium format. The industriel ONE-PAGE
    format stays on the legacy engine (fast field send), exactly like the
    residential/agricole split. The ``include_etude`` format ALSO stays on the
    legacy engine (see the guard below), exactly like ``residential.is_residential``.
    """
    mode = (getattr(devis, "mode_installation", None) or "").strip().lower()
    if mode != "industriel":
        return False
    opts = options or {}
    if (opts.get("pdf_mode") or "full") not in ("full", "premium"):
        return False
    # 2026-08-14 — RÉGRESSION PRODUIT CORRIGÉE (format « étude », 4 pages).
    # Ce garde manquait depuis QX45 (commit 6fcce23b, 16/07/2026) : le renderer
    # CFO interceptait AUSSI les devis demandés avec ``include_etude``, que le
    # dispatch destine explicitement au moteur legacy (cf. le commentaire de
    # ``builder.generate_premium_devis_pdf`` : « the legacy renderer serves every
    # other market mode / format (industriel, agricole, one-page, étude) ») et que
    # ``residential.is_residential`` écarte déjà de la même façon.
    # Conséquences mesurées sur le devis industriel + étude :
    #   · la page d'étude d'autoconsommation disparaissait (3 pages au lieu des
    #     4 exigées par CLAUDE.md — « premium 'full' = 3 pages, +include_etude = 4 ») ;
    #   · la chaîne de totaux Sous-total HT → Remise → Total HT → TVA → Total TTC,
    #     elle aussi exigée par CLAUDE.md, n'était plus imprimée du tout : les
    #     pages CFO n'affichent qu'un « Investissement (TTC, clé en main) ».
    # Les 4 baselines PNG ``industriel_full_etude_p1..p4`` (committées le
    # 10/07/2026, AVANT QX45) prouvent le rendu attendu à 4 pages.
    # Le renderer CFO garde tout son périmètre : industriel full/premium SANS étude.
    if opts.get("include_etude"):
        return False
    return True


def _num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _augment(data: dict) -> dict:
    """Add the industriel layout's derived CFO fields onto the built quote data.
    Raises Unsupported when the quote has no priced investment to render."""
    items = data.get("all_items") or []
    if not any((it.get("quantite") or 0) > 0 for it in items):
        raise Unsupported("industriel quote has no priced lines")
    # QJR620 — la page équipements (``commercial.equip``) imprime la chaîne
    # de totaux depuis ``totaux_all`` : même doctrine que le commercial
    # (QJR146 g) — sans totaux canoniques, repli legacy DIT, jamais des zéros.
    _totaux = data.get("totaux_all")
    if not isinstance(_totaux, dict) or not _totaux:
        raise Unsupported("industriel quote has no canonical totals "
                          "(totaux_all)")

    invest = _num(data.get("display_total")) or 0.0
    if invest <= 0:
        # repli sûr : total canonique TTC si display_total absent
        invest = _num(_totaux.get("ttc")) or 0.0
    if invest <= 0:
        raise Unsupported("industriel quote has no investment total")

    etude = data.get("etude") or {}
    d = dict(data)
    # ERR-QJR614-CI-INVESTISSEMENT-DIRHAM-VS-CENTIME — au CENTIME (ROUND_HALF_UP,
    # la règle de la chaîne canonique) : l'ancien ``round(invest)`` faisait
    # imprimer au dirham le pied de la page finance et la base des tranches.
    d["_invest_ttc"] = float(Decimal(str(invest)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))
    # QJR620 — la page équipements partagée lit ``com_category`` : un devis
    # industriel n'a pas de catégorie commerciale (bloc générique honnête).
    d["com_category"] = None
    d.setdefault("client_full", d.get("client_name") or "Client")
    # M7 (audit du 19/08/2026) — la validité vient du DEVIS
    # (``date_validite``, sinon création + réglage société
    # ``quote_validity_days``), jamais d'un « 30 jours » codé ici.
    # Indéterminable ⇒ None ⇒ la pastille/ligne est OMISE.
    d.setdefault("validity_days", None)
    d.setdefault("valid_until", None)

    # CIQ307 — UNE SOURCE : ``synthese_ci(data)``, la fonction que sert aussi
    # /proposition (CIQ306). Plus de production « par ville » (``prod_kwh``)
    # imprimée à côté de taux d'un autre modèle (C3-04) : la production est
    # celle du moteur C&I, ou elle est omise ; plus aucun taux d'étude JS.
    synthese = synthese_ci(d) or {}
    chiffres = chiffres_cles(synthese)
    d["ind_synthese"] = synthese
    # QJR625 — la puissance DES LIGNES (``systeme.kwc`` en est la lecture).
    d["ind_kwc"] = chiffres["kwc"] or _num(d.get("puissance_kwc"))         or _num(etude.get("kwc"))
    d["ind_prod"] = chiffres["production_kwh_an"]
    d["ind_conso"] = _num(etude.get("conso_annuelle")) or _num(d.get("conso_annuelle_kwh"))
    d["ind_autoconso"] = chiffres["taux_autoconso_pct"]
    d["ind_couverture"] = chiffres["taux_couverture_pct"]
    d["ind_methode"] = chiffres["libelle_methode"]
    d["ind_sous_reserve"] = chiffres["sous_reserve"]
    d["ind_a_confirmer"] = chiffres["a_confirmer"]
    d["ind_note_pointe"] = chiffres["note_pointe"]
    d["ind_motif_argent"] = chiffres["motif_argent"]
    d["ind_argent_mt"] = chiffres["argent_mt"]
    # QXMT — DOSSIER MT SANS ÉCONOMIES D'ÉTUDE : aucun repli sur le chiffre BT.
    # ``eco_s_ann``/``roi_s`` sortent de ``calculate_savings_roi``, au barème
    # BASSE TENSION de l'ONEE. Les reprendre sur un dossier raccordé en MT
    # imprimait sur le document client une économie et un payback qui ne sont
    # pas les siens. Le bloc est OMIS (jamais un « 0 », jamais un chiffre BT).
    masque = bool(d.get("masquer_economies"))
    d["ind_masquer_economies"] = masque
    d["ind_mt_mention"] = d.get("tarif_mt_mention") or ""
    # CIQ301 — AUCUN REPLI SUR LE MODÈLE RÉSIDENTIEL/BT. ``eco_s_ann``,
    # ``roi_s``, ``cashflow_sans/avec`` et ``cashflow_assumptions`` sortent de
    # ``calculate_savings_roi`` (barème BT résidentiel × ``AUTOCONSO_SANS``
    # 0,60) — dont la note « le surplus injecté n'est pas rémunéré » contredit
    # la ligne d'injection de la même page — et ``etude['payback']`` de l'étude
    # JS. Aucun ne décrit un site industriel : tuile économies, payback,
    # cashflow, TRI et hypothèses sont OMIS (``None`` ⇒ la page 3 bascule sur
    # son motif d'omission, jamais un « 0 », QJR119) jusqu'à ce que
    # ``synthese_ci.argent`` les serve (CIQ307). La page reste : 4 pages.
    # CIQ307 — tuile économies (base dite) et payback du flux : lus sur
    # ``synthese_ci.argent`` ; la page finance garde son motif d'omission
    # tant qu'aucune série n'est servie (``ind_cashflow``).
    d["ind_economies"] = chiffres["economie_annuelle_mad"]
    d["ind_economie_base"] = chiffres["base_economie"]
    d["ind_payback"] = chiffres["payback_ans"]
    d["ind_cashflow"] = None
    d["ind_cashflow_branche"] = None
    d["ind_cashflow_hypotheses"] = None

    # Injection 82-21 (QX50) — rendue UNIQUEMENT si l'étude la porte, avec la
    # mention ``MENTION_82_21`` (CIQ305). Absente → aucune ligne inventée.
    d["ind_injection_dh"] = _num(etude.get("injection_dh_an"))
    d["ind_injection_kwh"] = _num(etude.get("injection_kwh_an"))
    # O&M annuel : rendu seulement si fourni (sinon note « inclus »).
    d["ind_om_annuel"] = _num(etude.get("om_annuel"))

    # site + liens (repli résidentiel/théme).
    d["site_url"] = d.get("site_url") or "taqinor.ma"
    return d


def render_pdf_bytes(data: dict) -> bytes:
    """Render the premium industriel proposal to PDF bytes, or raise Unsupported."""
    from weasyprint import HTML
    from . import render as industriel_render
    from ..commercial.equip import pdf_adaptatif
    d = _augment(data)
    base = str(Path(industriel_render.__file__).resolve().parent)
    # CIQ317 — densité adaptative de la page équipements, mesurée sur le
    # rendu réel ; trop longue même au dernier palier ⇒ repli NOMMÉ.
    pdf = pdf_adaptatif(d, industriel_render.build_html, f"file://{base}/")
    if pdf is None:
        raise Unsupported("nomenclature trop longue")
    return pdf
