# flake8: noqa
"""quote_engine commercial — PAGE 2 (équipements + totaux + bloc catégorie).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``c2-`` (+ ``c2b-`` for the category block CSS,
whose markup is emitted by ``categories.category_block``). RULE #4 : jamais de
prix_achat/marge — on ne rend que designation/quantité/P.U. HT/TVA %/Total HT.
QJR615 — les lignes sont en HT (prix_unit_ht, remise de ligne déjà incluse par le
builder) : la somme des Total HT imprimés est le « Sous-total HT » de la chaîne.
"""
from . import categories
# QA-FIGURES — ancres ``data-figure`` masquées À CÔTÉ des chiffres client
# (aucune chaîne existante ne change) — voir ``quote_engine/figures.py``.
from ..figures import ancre
from ..ci.mentions import texte_revente
from ..sequence import sequence_affichage


def _num(v, default=0.0):
    try:
        f = float(v)
        return f if f == f else default
    except (TypeError, ValueError):
        return default


def build(ctx):
    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    # QJR614 — prix, totaux de ligne et chaîne de totaux au centime.
    fmt_mad = ctx.get("fmt_mad") or fmt
    fonts = ctx["fonts"]

    navy = C["navy"]
    gold = C["gold"]
    green = C["green"]
    green_bg = C.get("green_bg", "#E8F5EC")
    ink = C.get("ink", "#1F2937")
    muted = C.get("muted", "#6B7280")
    muted_2 = C.get("muted_2", "#9BA3AE")
    line = C.get("line", "#E5E7EB")
    line_soft = C.get("line_soft", "#EFF1F4")
    wash = C.get("wash", "#F7F9FC")

    f_display = fonts["display"]
    f_serif = fonts["serif"]
    f_sans = fonts["sans"]

    items = [it for it in (d.get("all_items") or []) if _num(it.get("quantite")) > 0]
    # QJR619 — sections et notes intercalées à leur ``ordre`` par la MÊME
    # fonction pure que le une-page (QJR617). Sans structure ⇒ items tels quels.
    _structure = d.get("lignes_structure") or []
    seq = (sequence_affichage(items, _structure) if _structure
           else [("item", it) for it in items])
    rows = ""
    for kind, it in seq:
        if kind == "struct":
            txt = it.get("texte", "") or ""
            if it.get("type") == "note":
                rows += (f'<tr><td class="c2-d" colspan="5" '
                         f'style="font-style:italic;color:{muted};">{txt}</td></tr>')
            else:
                rows += (f'<tr><td class="c2-d" colspan="5" '
                         f'style="font-weight:700;color:{navy};text-transform:uppercase;'
                         f'letter-spacing:.5px;background:{wash};">{txt}</td></tr>')
            continue
        qte = _num(it.get("quantite"))
        # QJR615 — P.U. HT (déjà remisé ligne par le builder) × quantité : la
        # colonne s'additionne au « Sous-total HT » ; aucun calcul TTC par ligne.
        pu_ht = _num(it.get("prix_unit_ht"))
        total = pu_ht * qte
        taux = _num(it.get("taux_tva"))
        taux_txt = f"{taux:g}\u202f%"
        marque = (it.get("marque") or "").strip()
        desig = it.get("designation") or ""
        m = f'<span class="c2-mq">{marque}</span>' if marque else ""
        rows += (
            f'<tr><td class="c2-d">{desig}{m}</td>'
            f'<td class="c2-q">{qte:g}</td>'
            f'<td class="c2-p">{fmt_mad(pu_ht)}</td>'
            f'<td class="c2-v">{taux_txt}</td>'
            f'<td class="c2-t">{fmt_mad(total)}</td></tr>')

    tot = d.get("totaux_all") or {}
    ht_brut = _num(tot.get("ht_brut"))
    remise = _num(tot.get("remise"))
    ht_net = _num(tot.get("ht_net"))
    tva = _num(tot.get("tva"))
    ttc = _num(tot.get("ttc")) or d.get("_invest_ttc") or 0
    # QA-FIGURES — chaque montant est formaté UNE fois : le texte imprimé et
    # son ancre ``data-figure`` sont la même chaîne.
    _f_remise = fmt_mad(remise)
    remise_row = (
        f'<tr><td>Remise{ancre("remise", _f_remise)}</td>'
        f'<td class="c2-tr">- {_f_remise} MAD</td></tr>'
        if remise > 0 else "")
    # ARRONDI-100 — la baisse au palier de 100 MAD inférieur, ligne visible.
    arrondi = _num(tot.get("arrondi"))
    _f_arrondi = fmt_mad(arrondi)
    arrondi_row = (
        f'<tr><td>Arrondi commercial{ancre("arrondi", _f_arrondi)}</td>'
        f'<td class="c2-tr">- {_f_arrondi} MAD</td></tr>'
        if arrondi > 0 else "")
    _f_ht_brut = fmt_mad(ht_brut)
    _f_ht_net = fmt_mad(ht_net)
    _f_tva = fmt_mad(tva)
    _f_ttc = fmt_mad(ttc)

    # QX50 — ligne injection 82-21 (rendue SEULEMENT si l'étude la porte, avec
    # sa mention obligatoire ; jamais affichée sans la mention).
    _etude = d.get("etude") or {}
    _inj = _num(_etude.get("injection_dh_an"))
    injection_html = ""
    if _inj and _inj > 0:
        injection_html = (
            '<div class="c2-inj"><b>+ ' + fmt(round(_inj)) + ' MAD/an</b> — '
            'surplus injecté. <span class="c2-inj-m">'
            # CIQ305 — la mention 82-21 est LUE (une table), jamais recopiée.
            + texte_revente() + '.</span></div>')

    # QJR619 — « Options proposées (non incluses) » : le SEUL ``total_ttc`` du
    # builder (supplément canonique, QJR616), aucun recalcul. Sans option ⇒ ''.
    options_html = ""
    _opts = d.get("options_proposees") or []
    if _opts:
        _orows = ""
        for _o in _opts:
            _oq = _num(_o.get("quantite"))
            _oq_txt = f"{_oq:g}× " if _oq and _oq != 1 else ""
            _orows += (
                f'<tr><td class="c2-d">{_oq_txt}{_o.get("designation", "")}</td>'
                f'<td class="c2-t">{fmt_mad(_num(_o.get("total_ttc")))} MAD TTC</td></tr>')
        options_html = (
            '<div style="margin-top:12px;"><div class="c2-kicker">Options propos&eacute;es '
            '(non incluses dans le total)</div>'
            f'<table class="c2-tbl">{_orows}</table></div>')

    block = categories.category_block(d.get("com_category"), d.get("etude"), C, fmt)

    css = f"""
<style>
.c2-root{{font-family:{f_sans};color:{ink};width:210mm;min-height:283mm;
  padding:13mm 14mm 0 14mm;background:#fff;}}
.c2-root *{{box-sizing:border-box;}}
.c2-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{muted_2};font-weight:700;}}
.c2-sec{{font-family:{f_serif};font-weight:700;font-size:16pt;color:{navy};margin-top:2px;}}
.c2-tbl{{width:100%;border-collapse:collapse;margin-top:9px;font-size:8.5pt;}}
.c2-tbl th{{text-align:left;color:{muted};font-size:7pt;text-transform:uppercase;
  letter-spacing:.4px;padding:6px 8px;border-bottom:1px solid {line};}}
.c2-tbl th.c2-rr{{text-align:right;}}
.c2-tbl td{{padding:6px 8px;border-bottom:1px solid {line_soft};vertical-align:top;}}
.c2-d{{color:{ink};}}
.c2-mq{{display:block;font-size:7pt;color:{muted_2};margin-top:1px;}}
.c2-q,.c2-p,.c2-v,.c2-t{{text-align:right;white-space:nowrap;}}
.c2-t{{font-weight:700;color:{navy};}}
.c2-tot{{margin-top:10px;display:table;width:100%;}}
.c2-note{{margin-top:8px;font-size:8pt;line-height:1.35;white-space:pre-line;}}
.c2-note b{{text-transform:uppercase;letter-spacing:.08em;font-size:7pt;margin-right:6px;}}
.c2-tot-sp{{display:table-cell;width:55%;}}
.c2-tot-box{{display:table-cell;width:45%;}}
.c2-tot-tbl{{width:100%;font-size:8.5pt;border-collapse:collapse;}}
.c2-tot-tbl td{{padding:4px 8px;}}
.c2-tot-tbl td:last-child{{text-align:right;white-space:nowrap;}}
.c2-tr{{text-align:right;}}
.c2-tot-ttc td{{border-top:2px solid {navy};font-family:{f_display};font-size:13pt;
  color:{navy};padding-top:6px;}}
/* Bloc catégorie (markup émis par categories.category_block) */
.c2b{{margin-top:14px;border:1px solid {line};border-left:4px solid {gold};
  border-radius:12px;background:{wash};padding:11px 14px;}}
.c2b-h{{font-size:9pt;font-weight:700;color:{navy};}}
.c2b-badge{{display:inline-block;margin-left:8px;background:{green_bg};color:{green};
  border-radius:20px;padding:2px 9px;font-size:7pt;font-weight:700;}}
.c2b-body{{margin-top:6px;}}
.c2b-meta{{font-size:7.5pt;color:{muted};margin-bottom:5px;}}
.c2b-li{{font-size:8pt;color:{ink};line-height:1.4;margin-top:4px;padding-left:12px;position:relative;}}
.c2b-li:before{{content:'';position:absolute;left:0;top:5px;width:6px;height:6px;
  border-radius:50%;background:{green};}}
.c2b-li b{{color:{navy};}}
.c2b-tbl{{width:100%;border-collapse:collapse;margin-top:4px;font-size:8pt;}}
.c2b-tbl td{{padding:4px 6px;border-bottom:1px solid {line_soft};vertical-align:top;}}
.c2b-tbl td:first-child{{font-weight:700;color:{navy};white-space:nowrap;width:32%;}}
.c2-inj{{margin-top:12px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:{green_bg};padding:9px 14px;font-size:8pt;color:{ink};line-height:1.4;}}
.c2-inj b{{color:{green};}}
.c2-inj-m{{color:{muted};font-size:7pt;}}
</style>
"""

    # QJR627 (D-QJR5-6) — le texte CLIENT du champ « Notes » (déjà échappé
    # par ``builder.echapper_textes_client``) ; vide → aucun bloc.
    _note_client = (d.get("note_client") or "").strip()
    note_html = (f'<div class="c2-note"><b>Note</b>{_note_client}</div>'
                 if _note_client else "")
    # QJR668 — clauses/CGV de l'affaire gelées (déjà échappées) ; aucune → "".
    from ..clauses_cgv import bloc_clauses_html
    clauses_html = bloc_clauses_html(
        d.get("clauses_cgv"), couleur_titre=navy, couleur_texte=ink)
    html = f"""{css}
<div class="c2-root">
  <div class="c2-kicker">Votre installation</div>
  <div class="c2-sec">Équipements &amp; investissement</div>

  <table class="c2-tbl">
    <tr><th>Désignation</th><th class="c2-rr">Qté</th><th class="c2-rr">P.U. HT</th><th class="c2-rr">TVA %</th><th class="c2-rr">Total HT</th></tr>
    {rows}
  </table>

  <div class="c2-tot">
    <div class="c2-tot-sp"></div>
    <div class="c2-tot-box">
      <table class="c2-tot-tbl">
        <tr><td>Sous-total HT{ancre("sous_total_ht", _f_ht_brut)}</td><td>{_f_ht_brut} MAD</td></tr>
        {remise_row}{arrondi_row}
        <tr><td>Total HT{ancre("total_ht", _f_ht_net)}</td><td>{_f_ht_net} MAD</td></tr>
        <tr><td>TVA{ancre("tva", _f_tva)}</td><td>{_f_tva} MAD</td></tr>
        <tr class="c2-tot-ttc"><td>Total TTC{ancre("total_ttc", _f_ttc)}</td><td>{_f_ttc} MAD</td></tr>
      </table>
    </div>
  </div>

  {note_html}{clauses_html}
  {options_html}{injection_html}
  {block}
</div>
"""
    return html
