# flake8: noqa
"""Commercial renderer selection + data augmentation for the single engine.

``generate_premium_devis_pdf`` builds the quote data once, then asks this module
whether the premium multi-page COMMERCIAL (category-aware) layout applies. If so
it renders PDF bytes; otherwise it raises ``Unsupported`` and the engine falls
back to the legacy renderer (the off-switch / one-page path).

Renders only — never changes a devis status (CLAUDE.md rule #4).
"""
from __future__ import annotations
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from ..ci.synthese import chiffres_cles, synthese_ci


class Unsupported(Exception):
    """The devis/options are outside the commercial renderer's scope."""


def is_commercial(devis, options=None) -> bool:
    """True when the premium multi-page COMMERCIAL layout should render this quote.

    Commercial market mode + the full/premium format. The one-page format stays
    on the legacy engine, exactly like the residential/agricole/industriel split.

    CIQ332 (D-CIQ-9) — ``include_etude`` est IGNORÉ : l'étude est déjà dans
    les 3 pages (production, taux, argent et retour lus sur ``synthese_ci``).
    Le garde QJR621 envoyait au legacy 4 pages tout devis commercial demandé
    « avec l'étude » : un même devis avait DEUX documents (C3-06). Le legacy
    ne reste que l'interrupteur de secours (règle #4) et le une-page.
    """
    mode = (getattr(devis, "mode_installation", None) or "").strip().lower()
    if mode != "commercial":
        return False
    opts = options or {}
    if (opts.get("pdf_mode") or "full") not in ("full", "premium"):
        return False
    return True


def _num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _augment(data: dict) -> dict:
    """Add the commercial layout's derived fields onto the built quote data.
    Raises Unsupported when the quote has no priced investment to render."""
    items = data.get("all_items") or []
    if not any((it.get("quantite") or 0) > 0 for it in items):
        raise Unsupported("commercial quote has no priced lines")

    # ── QJR146 (g) — LA CHAÎNE DE TOTAUX EST EXIGÉE, PAS REPLIÉE SUR ZÉRO ───
    # ``equip.py`` lisait ``totaux_all`` clé par clé avec un repli à 0 : une
    # charge utile privée de ce bloc imprimait « Sous-total HT 0 · Remise 0 ·
    # TVA 0 » sous un Total TTC réel (repris de ``_invest_ttc``) — une chaîne
    # de totaux fausse, en bas d'un tableau d'équipements juste. Même doctrine
    # que le moteur legacy (QJR162) : sans totaux canoniques, ce renderer
    # REFUSE le devis, et le dispatch retombe sur le moteur legacy en le
    # DISANT (repli journalisé), au lieu de publier des zéros.
    _totaux = data.get("totaux_all")
    if not isinstance(_totaux, dict) or not _totaux:
        raise Unsupported("commercial quote has no canonical totals "
                          "(totaux_all)")

    invest = _num(data.get("display_total")) or 0.0
    if invest <= 0:
        invest = _num(_totaux.get("ttc")) or 0.0
    if invest <= 0:
        raise Unsupported("commercial quote has no investment total")

    etude = data.get("etude") or {}
    d = dict(data)
    # ERR-QJR614-CI-INVESTISSEMENT-DIRHAM-VS-CENTIME — au CENTIME (ROUND_HALF_UP,
    # la règle de la chaîne canonique) : l'ancien ``round(invest)`` imprimait
    # « 1 201 » en couverture sous un Total TTC « 1 200,85 » page 2.
    d["_invest_ttc"] = float(Decimal(str(invest)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP))
    d.setdefault("client_full", d.get("client_name") or "Client")
    # M7 (audit du 19/08/2026) — la validité vient du DEVIS
    # (``date_validite``, sinon création + réglage société
    # ``quote_validity_days``), jamais d'un « 30 jours » codé ici.
    # Indéterminable ⇒ None ⇒ la pastille/ligne est OMISE.
    d.setdefault("validity_days", None)
    d.setdefault("valid_until", None)

    d["com_category"] = (etude.get("categorie_commerciale") or "").strip().lower() or None
    # CIQ307 — UNE SOURCE : ``synthese_ci(data)``, la fonction que sert aussi
    # /proposition (CIQ306) ; plus aucun taux ni argent lu dans l'étude JS.
    synthese = synthese_ci(d) or {}
    chiffres = chiffres_cles(synthese)
    d["com_synthese"] = synthese
    # QJR625 — la puissance DES LIGNES (``systeme.kwc`` en est la lecture) ;
    # ``etude['kwc']`` n'est plus qu'un repli.
    d["com_kwc"] = chiffres["kwc"] or _num(d.get("puissance_kwc")) \
        or _num(etude.get("kwc"))
    # CIQ331 — la production annuelle de la couverture : celle du moteur C&I
    # (``synthese_ci.systeme``), jamais la production « par ville ».
    d["com_production"] = chiffres["production_kwh_an"]
    d["com_conso"] = _num(etude.get("conso_annuelle")) or _num(d.get("conso_annuelle_kwh"))
    d["com_autoconso"] = chiffres["taux_autoconso_pct"]
    d["com_couverture"] = chiffres["taux_couverture_pct"]
    d["com_methode"] = chiffres["libelle_methode"]
    d["com_sous_reserve"] = chiffres["sous_reserve"]
    d["com_a_confirmer"] = chiffres["a_confirmer"]
    d["com_note_pointe"] = chiffres["note_pointe"]
    d["com_motif_argent"] = chiffres["motif_argent"]
    d["com_argent_mt"] = chiffres["argent_mt"]
    # QXMT — DOSSIER MT SANS ÉCONOMIES D'ÉTUDE : aucun repli sur le chiffre BT
    # (``eco_s_ann``/``roi_s`` sortent du barème BASSE TENSION de l'ONEE). Le
    # bloc est OMIS — jamais un « 0 », jamais un chiffre qui n'est pas le sien.
    masque = bool(d.get("masquer_economies"))
    d["com_masquer_economies"] = masque
    d["com_mt_mention"] = d.get("tarif_mt_mention") or ""
    # CIQ301 — AUCUN REPLI SUR LE MODÈLE RÉSIDENTIEL/BT (``eco_s_ann``/
    # ``roi_s``, étude JS). CIQ307 — l'argent vient SEULEMENT de
    # ``synthese_ci.argent`` (bloc ``economie_ci`` du moteur C&I) ; absent ⇒
    # ``None`` ⇒ tuile OMISE (jamais un « 0 », QJR119).
    d["com_economies"] = chiffres["economie_annuelle_mad"]
    d["com_economie_base"] = chiffres["base_economie"]
    d["com_payback"] = chiffres["payback_ans"]

    d["site_url"] = d.get("site_url") or "taqinor.ma"
    return d


def render_pdf_bytes(data: dict) -> bytes:
    """Render the premium commercial proposal to PDF bytes, or raise Unsupported."""
    from weasyprint import HTML
    from . import render as commercial_render
    from ..commercial.equip import pdf_adaptatif
    d = _augment(data)
    base = str(Path(commercial_render.__file__).resolve().parent)
    # CIQ317 — densité adaptative de la page équipements, mesurée sur le
    # rendu réel ; trop longue même au dernier palier ⇒ repli NOMMÉ.
    pdf = pdf_adaptatif(
        d, commercial_render.build_html,
        lambda html: HTML(string=html, base_url=f"file://{base}/").render())
    if pdf is None:
        raise Unsupported("nomenclature trop longue")
    return pdf
