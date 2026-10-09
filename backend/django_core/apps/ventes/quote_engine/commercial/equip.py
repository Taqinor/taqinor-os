# flake8: noqa
"""quote_engine commercial — PAGE 2 (équipements + totaux + bloc catégorie).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``c2-`` (+ ``c2b-`` for the category block CSS,
whose markup is emitted by ``categories.category_block``). RULE #4 : jamais de
prix_achat/marge — on ne rend que designation/quantité/P.U. HT/TVA %/Total HT.
QJR615 — les lignes sont en HT (prix_unit_ht, remise de ligne déjà incluse par le
builder) : la somme des Total HT imprimés est le « Sous-total HT » de la chaîne.
AMOT45 — avec une remise GLOBALE, chaque ligne montre le P.U. catalogue barré et
le P.U. remisé (``montants.lignes_remisees``) : Σ lignes remisées = Total HT.
"""
from . import categories
# QA-FIGURES — ancres ``data-figure`` masquées À CÔTÉ des chiffres client
# (aucune chaîne existante ne change) — voir ``quote_engine/figures.py``.
from ..figures import ancre
from ..ci.mentions import mentions_revente, texte_revente
from ..ci.synthese import chiffres_cles
# CIQ333 — libellés STRUCTURELS dans la langue du document.
from ..ci.blocs import langue as _langue, libelle as _libelle
from ..sequence import sequence_affichage
from .. import premium_base
from ..montants import deux_prix, lignes_remisees


def _num(v, default=0.0):
    try:
        f = float(v)
        return f if f == f else default
    except (TypeError, ValueError):
        return default


# ── CIQ317 — densité adaptative de la page équipements ─────────────────────
#: Paliers ``(police pt, padding vertical px, interligne)`` du tableau, des
#: totaux et des blocs sous le tableau. Palier 0 = le rendu d'hier, octet pour
#: octet. Le renderer choisit le premier palier qui TIENT, mesuré sur le rendu
#: réel (``deborde``) ; si le dernier déborde encore, il refuse le devis
#: (``Unsupported('nomenclature trop longue')``) et le dispatch prend le repli
#: NOMMÉ (QJR235) — jamais une ligne, un total ou une option perdue.
PALIERS_DENSITE = (None, (7.5, 4, 1.25), (6.8, 2.5, 1.15), (6.0, 1.2, 1.05))
#: Bande de pied fixe des pages premium (``theme`` › ``.foot``, 13 mm).
PIED_MM = 13.0
_PX_PAR_MM = 96 / 25.4


def css_densite(palier):
    """Surcharge CSS du palier ``palier`` (``''`` au palier 0)."""
    if not palier or palier >= len(PALIERS_DENSITE):
        return ""
    pt, pad, lh = PALIERS_DENSITE[palier]
    return (
        "<style>.c2-tot{display:block;}.c2-tot-sp{display:none;}"
        ".c2-tot-box{display:block;width:45%;margin-left:55%;}"
        f".c2-sec{{font-size:{pt + 5:g}pt;}}"
        f".c2-tbl{{margin-top:4px;font-size:{pt:g}pt;line-height:{lh:g};}}"
        f".c2-tbl th,.c2-tbl td{{padding:{pad:g}px 6px;}}"
        f".c2-mq{{font-size:{max(pt - 1.5, 5):g}pt;"
        + ("display:inline;margin-left:4px;" if palier >= 2 else "") + "}"
        f".c2-tot{{margin-top:{pad:g}px;}}"
        f".c2-tot-tbl{{font-size:{pt:g}pt;}}"
        f".c2-tot-tbl td{{padding:{max(pad - 1, 1):g}px 8px;}}"
        f".c2-tot-ttc td{{font-size:{pt + 3:g}pt;padding-top:{pad:g}px;}}"
        f".c2-note,.c2-inj{{margin-top:{pad:g}px;font-size:{pt:g}pt;}}"
        f".c2b{{margin-top:{pad + 2:g}px;padding:{pad + 2:g}px 10px;}}"
        f".c2b-li{{font-size:{pt:g}pt;margin-top:1px;line-height:{lh:g};}}"
        "</style>")


def _boites_texte(boite, dans_pied=False):
    element = getattr(boite, "element", None)
    classes = ""
    if element is not None and hasattr(element, "get"):
        classes = element.get("class") or ""
    pied = dans_pied or "foot" in classes.split()
    if type(boite).__name__ == "TextBox" and not pied:
        yield boite
    for enfant in getattr(boite, "children", None) or []:
        yield from _boites_texte(enfant, pied)


def deborde(page):
    """Vrai quand un TEXTE de la page (hors pied) descend sous le haut de la
    bande de pied : la page fixe en ``overflow:hidden`` le couperait en
    silence. ``page`` : une page de ``HTML(...).render().pages``."""
    limite = page.height - PIED_MM * _PX_PAR_MM
    for boite in _boites_texte(page._page_box):
        if boite.position_y + boite.margin_height() > limite + 0.5:
            return True
    return False


def pdf_adaptatif(d, build_html, rendre, index_page=1):
    """Les octets PDF au PREMIER palier de densité qui tient, ou ``None``
    quand même le dernier déborde (le renderer lève alors ``Unsupported``).
    ``rendre(html)`` : le document WeasyPrint rendu par le RENDERER — aucun
    import WeasyPrint ici (ARC11)."""
    for palier in range(len(PALIERS_DENSITE)):
        donnees = d if palier == 0 else dict(d, _palier_equip=palier)
        doc = _rendu_qui_tient(donnees, build_html, rendre)
        if doc is not None:
            return doc.write_pdf()
    # AMOT36 — les conditions (liste VARIABLE : ``cgv_ci`` gelées, ou puces
    # société) ne tiennent pas : leurs dernières puces sont remplacées par le
    # renvoi DÉCLARÉ « suite des conditions : proposition en ligne » (le plus
    # de puces possible, recherche dichotomique), au palier 0 puis au dernier.
    from ..ci.blocs import puces_conditions, renvoi_suite_conditions
    puces = list(puces_conditions(d))
    if len(puces) > 1:
        renvoi = renvoi_suite_conditions(d)
        for palier in (0, len(PALIERS_DENSITE) - 1):
            base = d if palier == 0 else dict(d, _palier_equip=palier)
            bas, haut, retenu = 1, len(puces) - 1, None
            while bas <= haut:
                garde = (bas + haut) // 2
                doc = _rendu_qui_tient(
                    dict(base, cgv_ci=puces[:garde] + [renvoi]),
                    build_html, rendre)
                if doc is not None:
                    retenu, bas = doc, garde + 1
                else:
                    haut = garde - 1
            if retenu is not None:
                return retenu.write_pdf()
    return None


def _rendu_qui_tient(donnees, build_html, rendre):
    """AMOT36 — le document WeasyPrint de ``donnees`` s'il tient son contrat
    de pages, sinon ``None`` : exactement ses pages (une page qui déborde
    peut en POUSSER une de plus) et aucun texte sous le haut du pied sur
    AUCUNE page (``any(deborde(p))`` — la page équipements seule laissait
    passer la bande légale sous le pied de la page conditions)."""
    html = build_html(donnees)
    doc = rendre(html)
    attendu = html.count('<div class="page">')
    if len(doc.pages) == attendu and not any(deborde(p) for p in doc.pages):
        return doc
    return None


def build(ctx):
    d = ctx["d"]

    def L(cle, fr, **valeurs):
        return _libelle(d, cle, fr, **valeurs)

    C = ctx["C"]
    fmt = ctx["fmt"]
    # QJR614 — prix, totaux de ligne et chaîne de totaux au centime.
    fmt_mad = ctx.get("fmt_mad") or fmt
    fonts = ctx["fonts"]

    navy, gold, green, green_bg, ink, muted, muted_2, line, line_soft, wash = premium_base.couleurs(
        C, "navy gold green green_bg ink muted muted_2 line line_soft wash")

    f_display, f_serif, f_sans = premium_base.polices(fonts)

    items = [it for it in (d.get("all_items") or []) if _num(it.get("quantite")) > 0]
    # QJR619 — sections et notes intercalées à leur ``ordre`` par la MÊME
    # fonction pure que le une-page (QJR617). Sans structure ⇒ items tels quels.
    _structure = d.get("lignes_structure") or []
    seq = (sequence_affichage(items, _structure) if _structure
           else [("item", it) for it in items])
    # AMOT45 — la remise globale portée sur chaque ligne (P.U. catalogue barré
    # + P.U. remisé, Σ lignes = Total HT) ; règles d'origine : le catalogue.
    _remisees = {id(r["item"]): r for r in lignes_remisees(
        items, catalogue_seul=bool(d.get("regles_calcul_origine")))}
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
        # QJR615 — P.U. HT (remise de LIGNE déjà incluse par le builder) ×
        # quantité, aucun calcul TTC par ligne. AMOT45 — la remise GLOBALE est
        # portée en plus (catalogue barré + remisé) : les Total HT imprimés
        # s'additionnent au « Total HT » (le catalogue barré, au Sous-total).
        _r = _remisees.get(id(it)) or lignes_remisees([it], catalogue_seul=True)[0]
        pu_txt = deux_prix(fmt_mad, _r["pu_catalogue"], _r["pu"])
        total_txt = deux_prix(fmt_mad, _r["total_catalogue"], _r["total"])
        taux = _num(it.get("taux_tva"))
        taux_txt = f"{taux:g}\u202f%"
        marque = (it.get("marque") or "").strip()
        desig = it.get("designation") or ""
        m = f'<span class="c2-mq">{marque}</span>' if marque else ""
        rows += (
            f'<tr><td class="c2-d">{desig}{m}</td>'
            f'<td class="c2-q">{qte:g}</td>'
            f'<td class="c2-p">{pu_txt}</td>'
            f'<td class="c2-v">{taux_txt}</td>'
            f'<td class="c2-t">{total_txt}</td></tr>')

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
        f'<tr><td>{L("remise", "Remise")}{ancre("remise", _f_remise)}</td>'
        f'<td class="c2-tr">- {_f_remise} MAD</td></tr>'
        if remise > 0 else "")
    # ARRONDI-100 — la baisse au palier de 100 MAD inférieur, ligne visible.
    arrondi = _num(tot.get("arrondi"))
    _f_arrondi = fmt_mad(arrondi)
    arrondi_row = (
        f'<tr><td>{L("arrondi", "Arrondi commercial")}{ancre("arrondi", _f_arrondi)}</td>'
        f'<td class="c2-tr">- {_f_arrondi} MAD</td></tr>'
        if arrondi > 0 else "")
    _f_ht_brut = fmt_mad(ht_brut)
    _f_ht_net = fmt_mad(ht_net)
    _f_tva = fmt_mad(tva)
    _f_ttc = fmt_mad(ttc)

    # QX50 — ligne injection 82-21 (rendue SEULEMENT si l'étude la porte, avec
    # sa mention obligatoire ; jamais affichée sans la mention).
    # CIQ129 — la valeur de l'injection est celle du moteur C&I
    # (``synthese_ci.argent.revente``, la projection ``chiffres_cles`` que
    # lisent couverture et /proposition), jamais une clé d'étude écran v1.
    _syn = d.get("com_synthese") or d.get("ind_synthese") or {}
    _inj = _num(chiffres_cles(_syn)["revente_mad_an"])
    injection_html = ""
    if _inj and _inj > 0:
        # AMOT40 — CHAQUE mention servie par ``revente.mentions`` (dont
        # « potentiel non garanti »), dans la langue du document ; la mention
        # 82-21 seule en repli si le moteur n'en sert aucune.
        _revente = ((_syn.get("argent") or {}).get("revente") or {}) \
            if isinstance(_syn, dict) else {}
        _mentions = mentions_revente(_revente.get("mentions"), _langue(d)) \
            if isinstance(_revente, dict) else []
        _mentions_txt = (" ".join(_mentions) if _mentions
                         else texte_revente(_langue(d)) + ".")
        injection_html = (
            '<div class="c2-inj"><b>+ ' + fmt(round(_inj)) + ' '
            + L("ci_mad_an", "MAD/an") + '</b> — '
            + L("ci_surplus_injecte", "surplus injecté") + '. <span class="c2-inj-m">'
            # CIQ305 — les mentions sont LUES (une table), jamais recopiées.
            + _mentions_txt + '</span></div>')

    # QJR619 — « Options proposées (non incluses) » : le SEUL ``total_ttc`` du
    # builder (supplément canonique, QJR616), aucun recalcul. Sans option ⇒ ''.
    options_html = ""
    _opts = d.get("options_proposees") or []
    if _opts:
        _orows = ""
        for _o in _opts:
            _oq = _num(_o.get("quantite"))
            _oq_txt = f"{_oq:g}× " if _oq and _oq != 1 else ""
            # CIQ316 — en HT avec leur taux, comme le reste du tableau : les
            # ``total_ht`` / ``taux_tva`` / ``total_ttc`` SERVIS par le builder
            # (supplément canonique QJR616), aucun recalcul ici ; TTC en petit.
            _o_taux = _num(_o.get("taux_tva"))
            _orows += (
                f'<tr><td class="c2-d">{_oq_txt}{_o.get("designation", "")}</td>'
                f'<td class="c2-v">{_o_taux:g} %</td>'
                f'<td class="c2-t">{fmt_mad(_num(_o.get("total_ht")))} MAD {L("ci_ht", "HT")}'
                f'<div style="font-size:6.5pt;font-weight:400;">'
                f'{fmt_mad(_num(_o.get("total_ttc")))} MAD {L("ci_ttc", "TTC")}</div></td></tr>')
        options_html = (
            '<div style="margin-top:12px;"><div class="c2-kicker">'
            + L("ci_options_proposees",
                "Options propos&eacute;es (non incluses dans le total)")
            + '</div>'
            '<table class="c2-tbl"><tr><th>' + L("designation", "D&eacute;signation") + '</th>'
            '<th class="c2-rr">' + L("ci_tva_pct", "TVA %") + '</th><th class="c2-rr">'
            + L("total_ht", "Total HT") + '</th></tr>'
            f'{_orows}</table></div>')

    # CIQ330 — le bloc RENDU depuis ``synthese_ci['categorie']`` (table
    # trilingue de ``ci/categories.py``), le même contenu que /proposition.
    block = categories.category_block(
        d.get("com_category"), d.get("etude"), C, fmt,
        note_pointe=d.get("com_note_pointe") or d.get("ind_note_pointe"),
        categorie=(d.get("com_synthese") or {}).get("categorie"),
        langue=_langue(d),
        synthese=d.get("com_synthese") or d.get("ind_synthese"))

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
    note_html = (f'<div class="c2-note"><b>{L("ci_note", "Note")}</b>{_note_client}</div>'
                 if _note_client else "")
    # QJR668 — clauses/CGV de l'affaire gelées (déjà échappées) ; aucune → "".
    from ..clauses_cgv import bloc_clauses_html
    clauses_html = bloc_clauses_html(
        d.get("clauses_cgv"), couleur_titre=navy, couleur_texte=ink)
    html = f"""{css}{css_densite(d.get("_palier_equip"))}
<div class="c2-root">
  <div class="c2-kicker">{L("ci_votre_installation", "Votre installation")}</div>
  <div class="c2-sec">{L("ci_equipements_investissement", "Équipements &amp; investissement")}</div>

  <table class="c2-tbl">
    <tr><th>{L("designation", "Désignation")}</th><th class="c2-rr">{L("qte", "Qté")}</th><th class="c2-rr">{L("pu_ht", "P.U. HT")}</th><th class="c2-rr">{L("ci_tva_pct", "TVA %")}</th><th class="c2-rr">{L("total_ht", "Total HT")}</th></tr>
    {rows}
  </table>

  <div class="c2-tot">
    <div class="c2-tot-sp"></div>
    <div class="c2-tot-box">
      <table class="c2-tot-tbl">
        <tr><td>{L("sous_total_ht", "Sous-total HT")}{ancre("sous_total_ht", _f_ht_brut)}</td><td>{_f_ht_brut} MAD</td></tr>
        {remise_row}{arrondi_row}
        <tr><td>{L("total_ht", "Total HT")}{ancre("total_ht", _f_ht_net)}</td><td>{_f_ht_net} MAD</td></tr>
        <tr><td>{L("tva", "TVA")}{ancre("tva", _f_tva)}</td><td>{_f_tva} MAD</td></tr>
        <tr class="c2-tot-ttc"><td>{L("total_ttc", "Total TTC")}{ancre("total_ttc", _f_ttc)}</td><td>{_f_ttc} MAD</td></tr>
      </table>
    </div>
  </div>

  {note_html}{clauses_html}
  {options_html}{injection_html}
  {block}
</div>
"""
    return html
