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
    residential/agricole split.

    CIQ340 (convention 4, D-QJR5-12, D-CIQ-10) — ``include_etude`` est
    IGNORÉ : le document industriel est TOUJOURS le premium 4 pages, étude
    intégrée (synthèse, équipements + chaîne de totaux, rentabilité,
    conditions et signature). Le garde du 2026-08-14 envoyait au legacy tout
    devis demandé « avec l'étude » — dont la page d'étude, pour un devis
    neuf, lisait des clés jamais persistées (C3-VA-04) — pendant que le lien
    du client et la copie signée recevaient le premium (C3-06). Le legacy ne
    reste que l'interrupteur de secours (règle #4) et le une-page.
    """
    mode = (getattr(devis, "mode_installation", None) or "").strip().lower()
    if mode != "industriel":
        return False
    opts = options or {}
    if (opts.get("pdf_mode") or "full") not in ("full", "premium"):
        return False
    return True


# CIQ317 — le MÊME lecteur numérique que le renderer commercial (une
# seule définition : la page équipements est partagée).
from ..commercial.renderer import _num  # noqa: E402,F401


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
    # AMOT41 (C-AMOT-051) — la consommation imprimée est celle du MOTEUR C&I
    # (``synthese_ci.baseline.kwh_an``, Σ des 12 mois résolus), jamais la
    # saisie d'écran ``etude.conso_annuelle`` (sonde VC ci1 : « ≈ 1 kWh/an »
    # à côté d'une production de 79 482 kWh). Absente ⇒ ligne omise.
    d["ind_conso"] = chiffres["conso_kwh_an"]
    d["ind_autoconso"] = chiffres["taux_autoconso_pct"]
    d["ind_couverture"] = chiffres["taux_couverture_pct"]
    d["ind_methode"] = chiffres["libelle_methode"]
    d["ind_sous_reserve"] = chiffres["sous_reserve"]
    d["ind_a_confirmer"] = chiffres["a_confirmer"]
    # CIQ333 / CIQ345 — les CLÉS de la méthode et des points à confirmer :
    # la langue du document choisit leur libellé (``i18n_labels``).
    d["ind_methode_cle"] = chiffres["methode"]
    d["ind_a_confirmer_cles"] = [
        a.get("cle") for a in synthese.get("a_confirmer") or []
        if isinstance(a, dict) and a.get("libelle")]
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

    # CIQ342 — la page finance lit la revente et l'O&M sur
    # ``synthese_ci['argent']`` (revente « hors cashflow », O&M déduite
    # seulement si chiffrée) : plus aucune clé d'étude écran reprise ici.

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
    pdf = pdf_adaptatif(
        d, industriel_render.build_html,
        lambda html: HTML(string=html, base_url=f"file://{base}/").render())
    if pdf is None:
        raise Unsupported("nomenclature trop longue")
    return pdf
