# flake8: noqa
"""Commercial renderer selection + data augmentation for the single engine.

``generate_premium_devis_pdf`` builds the quote data once, then asks this module
whether the premium multi-page COMMERCIAL (category-aware) layout applies. If so
it renders PDF bytes; otherwise it raises ``Unsupported`` and the engine falls
back to the legacy renderer (the off-switch / one-page path).

Renders only — never changes a devis status (CLAUDE.md rule #4).
"""
from __future__ import annotations
from pathlib import Path


class Unsupported(Exception):
    """The devis/options are outside the commercial renderer's scope."""


def is_commercial(devis, options=None) -> bool:
    """True when the premium multi-page COMMERCIAL layout should render this quote.

    Commercial market mode + the full/premium format. The one-page format stays
    on the legacy engine, exactly like the residential/agricole/industriel split.
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
    d["_invest_ttc"] = round(invest)
    d.setdefault("client_full", d.get("client_name") or "Client")
    # M7 (audit du 19/08/2026) — la validité vient du DEVIS
    # (``date_validite``, sinon création + réglage société
    # ``quote_validity_days``), jamais d'un « 30 jours » codé ici.
    # Indéterminable ⇒ None ⇒ la pastille/ligne est OMISE.
    d.setdefault("validity_days", None)
    d.setdefault("valid_until", None)

    d["com_category"] = (etude.get("categorie_commerciale") or "").strip().lower() or None
    d["com_kwc"] = _num(etude.get("kwc")) or _num(d.get("puissance_kwc"))
    # QJR145 (g) — ``com_prod`` SUPPRIMÉ : calculé et lu par aucun gabarit
    # commercial (la production s'affiche depuis ``com_kwc``/l'étude).
    d["com_conso"] = _num(etude.get("conso_annuelle")) or _num(d.get("conso_annuelle_kwh"))
    d["com_autoconso"] = _num(etude.get("taux_autoconso"))
    d["com_couverture"] = _num(etude.get("taux_couverture"))
    # QXMT — DOSSIER MT SANS ÉCONOMIES D'ÉTUDE : aucun repli sur le chiffre BT
    # (``eco_s_ann``/``roi_s`` sortent du barème BASSE TENSION de l'ONEE). Le
    # bloc est OMIS — jamais un « 0 », jamais un chiffre qui n'est pas le sien.
    masque = bool(d.get("masquer_economies"))
    d["com_masquer_economies"] = masque
    d["com_mt_mention"] = d.get("tarif_mt_mention") or ""
    # QJR119 — voir ``industriel/renderer.py`` : ``None`` traverse jusqu'au
    # gabarit, qui omet la carte, au lieu d'être écrasé en un « 0 MAD » qui se
    # lit comme un chiffre mesuré.
    eco = _num(etude.get("economies_annuelles"))
    if eco is None and not masque:
        eco = _num(d.get("eco_s_ann"))
    d["com_economies"] = round(eco) if eco else None
    pb = _num(etude.get("payback"))
    if pb is None and not masque:
        pb = _num(d.get("roi_s"))
    # QJR145 (g) — ``com_payback`` est CONSERVÉ bien qu'aucun gabarit ne
    # l'imprime : sa nullité EST le contrat vérifié des gardes QXMT/QJR119
    # (« aucun repli sur le chiffre basse tension », « jamais un 0 »), épinglé
    # par test_quote_engine_builder et test_qjr119_zero_fabrique. Le retirer
    # supprimerait la garde, pas du code mort.
    d["com_payback"] = pb if pb else None

    d["site_url"] = d.get("site_url") or "taqinor.ma"
    return d


def render_pdf_bytes(data: dict) -> bytes:
    """Render the premium commercial proposal to PDF bytes, or raise Unsupported."""
    from weasyprint import HTML
    from . import render as commercial_render
    d = _augment(data)
    html = commercial_render.build_html(d)
    base = str(Path(commercial_render.__file__).resolve().parent)
    return HTML(string=html, base_url=f"file://{base}/").write_pdf()
