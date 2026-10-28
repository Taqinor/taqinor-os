# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""SPL168 — format UNE PAGE du moteur legacy (move only).

Déplacés tels quels de ``generate_devis_premium.py`` : ``_proposition_link``,
``_onepage_qr_uri``, ``_onepage_header_html``, ``page_onepage`` et
``build_html_onepage``. RESTENT dans ``generate_devis_premium`` (lus ``G.*``
par les tests, ou partagés avec la page complète) : ``ONEPAGE_HEADER_MM`` /
``ONEPAGE_FOOTER_PX``, ``_mesure_onepage`` et ``_render_pdf_weasyprint`` (liste
ARC11), ``_onepage_html_qui_tient``, ``_renvoi_detail_complet``, ``_fdec_fr``,
les polices, et ``_css_arabe`` / ``_attributs_langue_html`` (aussi lus par
``build_html``).

LIAISON TARDIVE : toute référence à un nom de niveau module de
``generate_devis_premium`` s'écrit ``_g.NOM`` — ``apply_quote_data`` réaffecte
ces globales à chaque rendu et les tests posent ``G.X`` ; un
``from .generate_devis_premium import KWC`` figerait le chiffre d'un AUTRE
devis (seul ``logger``, objet jamais réaffecté, est lié une fois). Seule autre
réécriture : ``globals().get("MODE_INSTALLATION")`` devient
``getattr(_g, "MODE_INSTALLATION", None)`` (déplacé tel quel, il lirait le
dictionnaire de CE module). Rendu seulement (règle #4) : aucun statut, aucun
nouveau chemin de PDF client.
"""
from . import generate_devis_premium as _g

#: Le logger de ``generate_devis_premium`` (même objet, jamais réaffecté) : les
#: journaux du une-page gardent leur nom de logger d'origine.
logger = _g.logger


# ── ONE-PAGE MODE ─────────────────────────────────────────────────────────────
def _proposition_link():
    """QRP1 — (href, forme courte) du lien TOKENISÉ de la proposition en ligne,
    ou ('', '') quand le devis n'en porte pas.

    Le lien vient EXCLUSIVEMENT de ``data['links']['signer']`` (builder QX6 :
    ShareLink + ``utils.client_links.chemin_proposition``) : ce module ne forge
    aucune URL et n'ajoute AUCUN paramètre de requête. Ce que l'URL contient :
    le SLUG du nom du client dans le CHEMIN (PV84 — cosmétique, jamais vérifié
    côté serveur) puis le jeton ; aucune adresse, aucune coordonnée GPS. La
    forme AFFICHÉE, elle, est tronquée à « <hôte>/proposition » — ni le nom ni
    le jeton ne s'impriment en clair. Le repli historique « <site>/signer/<réf> »
    (jamais servi par le site) est exclu : sans vraie proposition en ligne, la
    vignette s'omet plutôt que de porter un QR qui mène à un 404.
    """
    url = (_g.LINKS.get("signer") or "").strip()
    if "/proposition/" not in url:
        return "", ""
    # QJR162 (a) — EXIGER un schéma http(s) ET un hôte non vide. ``SITE_URL``
    # n'est pas protégé contre la variable d'environnement PRÉSENTE MAIS VIDE
    # (``PUBLIC_SITE_URL`` l'est, pas elle) : la base devenait '', le lien
    # relatif, et « "https://" + url » imprimait un QR
    # « https:///proposition/… » — MORT chez le client. La docstring promet
    # d'omettre la vignette plutôt que de porter un QR qui mène à un 404 :
    # on l'applique au lieu de fabriquer une URL.
    if not _g.re.match(r"^https?://", url, _g.re.I):
        return "", ""
    court = url.split("://", 1)[1]
    if not court.split("/", 1)[0].strip():
        return "", ""
    morceaux = court.split("/")
    return url, ("/".join(morceaux[:2]) if len(morceaux) > 2 else court)


def _onepage_qr_uri(href):
    """QRP1 — QR PNG data-URI de la proposition (correction M, sans logo
    central : le même lien tient en bien moins de modules qu'en H, donc reste
    scannable à 18 mm). A6 — ``border=4`` : la zone de silence par défaut (2
    modules) est trop courte pour un QR posé sur un aplat NAVY ; 4 modules de
    blanc, plus la platine blanche du gabarit, rendent la lecture fiable.
    '' si la roue ``qrcode`` manque — la vignette s'omet alors et le document
    reste identique à aujourd'hui."""
    if not href:
        return ""
    try:
        from .residential import theme as _rtheme
        return _rtheme.qr_data_uri(href, logo=False, correction="M",
                                   box_size=10, border=4)
    except Exception:
        logger.warning("generate_devis_premium._onepage_qr_uri : erreur ignorée (mode dégradé)", exc_info=True)
        return ""


def _onepage_header_html():
    """QRP1 — en-tête navy du format UNE PAGE.

    Sans lien tokenisé (ou sans ``qrcode``), renvoie le balisage historique à
    la hauteur imposée près — aucun contenu ne bouge. Avec le lien, la vignette
    QR se pose entre le logo et la référence, dans une TABLE CSS
    (RENDERING_NOTES §1 : le flex de WeasyPrint sous-estime la hauteur de flux
    d'une rangée de cartes et ignore ``gap``).

    A4 — la rangée porte une HAUTEUR EXPLICITE (``ONEPAGE_HEADER_MM``) sur la
    cellule du logo : elle vaut donc exactement la même chose avec ou sans
    ``logo.png``, et avec ou sans QR. La légende passe À GAUCHE du code (et non
    dessous) : la pile tient ainsi sous la bande sans rétrécir le QR, qui garde
    18 mm — la seule dimension qui décide de sa lisibilité.
    """
    href, court = _proposition_link()
    qr = _onepage_qr_uri(href)
    h = f"{_g.ONEPAGE_HEADER_MM}mm"
    ref_html = (
        '<div style="text-align:right;">'
        f'<div style="color:white;font-size:11pt;font-weight:700;">'
        f'{_g._L("op_devis")}&nbsp;'
        f'<span style="color:{_g.CA};">{_g._L("op_numero")}&#160;{_g.REF}</span></div>'
        f'<div style="color:rgba(255,255,255,0.6);font-size:8pt;'
        f'margin-top:2px;">{_g.DATE_STR}</div>'
        + _g._marques_correction_html(
            'color:rgba(255,255,255,0.6);font-size:6.5pt;margin-top:1px;')
        + '</div>')
    if not qr:
        return (
            f'<div style="background:{_g.CN};padding:14px 24px;display:table;'
            'width:100%;table-layout:fixed;">'
            '<div style="display:table-cell;vertical-align:middle;width:50%;'
            f'height:{h};">{_g.logo_html("onepage")}</div>'
            '<div style="display:table-cell;vertical-align:middle;width:50%;">'
            f'{ref_html}</div></div>')
    # A6 — platine BLANCHE derrière le code (aplat navy) et AUCUN arrondi sur
    # l'image : un rayon rognait ~2 modules dans les coins, précisément là où
    # vivent les trois motifs de repérage.
    qr_cell = (
        '<div style="display:table;margin:0 auto;">'
        '<div style="display:table-cell;vertical-align:middle;'
        'text-align:right;padding-right:3mm;">'
        '<div style="color:rgba(255,255,255,0.80);font-size:6.2pt;'
        f'line-height:1.25;">{_g._L("op_consultez_proposition")}'
        f'<br><span style="color:{_g.CA};">{court}</span></div></div>'
        '<div style="display:table-cell;vertical-align:middle;">'
        '<div style="background:#FFFFFF;padding:0.7mm;display:inline-block;">'
        f'<img src="{qr}" alt="QR — votre proposition en ligne" '
        'style="height:18mm;width:18mm;display:block;"></div></div></div>')
    return (
        f'<div style="background:{_g.CN};padding:14px 24px;display:table;'
        'width:100%;table-layout:fixed;">'
        '<div style="display:table-cell;vertical-align:middle;width:26%;'
        f'height:{h};">{_g.logo_html("onepage")}</div>'
        '<div style="display:table-cell;vertical-align:middle;width:48%;">'
        f'{qr_cell}</div>'
        '<div style="display:table-cell;vertical-align:middle;width:26%;">'
        f'{ref_html}</div></div>')


def page_onepage(items, tronquees=0):
    """Single A4 page: header + summary strip + client block + HT product table + footer.

    QJR161 — ``tronquees`` : nombre de lignes d'équipement RETIRÉES de la table
    parce qu'elles ne tenaient pas dans la zone visible. Elles sont DÉCLARÉES
    par une ligne finale ; les totaux, eux, restent ceux du devis ENTIER
    (chaîne canonique du builder) — on n'a jamais retiré une ligne d'un total.
    """
    # Totaux CANONIQUES du builder (chaîne HT → remise → TVA par taux → TTC,
    # calculée UNE fois) ; recalcul local uniquement en mode autonome.
    # QJR162 (c) — le recalcul local portait le MÊME défaut que
    # ``_fallback_totaux`` : un taux de TVA unique et ``tva_par_taux`` vide,
    # alors que la colonne du tableau imprime le taux de CHAQUE ligne. Sans
    # totaux canoniques, la page LÈVE plutôt que d'imprimer une chaîne qui
    # n'additionne pas celle qu'elle affiche juste au-dessus.
    if not _g.TOTAUX_ALL:
        raise ValueError(
            "page_onepage: totaux canoniques manquants (totaux_all) — le "
            "moteur ne fabrique pas de chaîne de totaux (QJR162).")
    totaux = _g.TOTAUX_ALL
    total_ht = totaux["ht_brut"]
    remise = totaux["remise"]
    net_ht = totaux["ht_net"]
    tva_amt = totaux["tva"]
    total = totaux["ttc"]
    # QA-FIGURES — l'option que chiffre ce une-page : ``ONEPAGE_BRANCHE`` quand
    # ses totaux SONT ceux de cette option ; sinon (liste libre, pompage) la
    # chaîne décrit le devis entier (``totaux_all``) → marqueurs sans option.
    _tot_branche = {"sans": _g.TOTAUX_SANS, "avec": _g.TOTAUX_AVEC}.get(
        _g.ONEPAGE_BRANCHE) or {}
    try:
        _meme = abs(float(_tot_branche.get("ttc")) - float(total)) < 0.005
    except (TypeError, ValueError):
        _meme = False
    _op_opt = _g.ONEPAGE_BRANCHE if _meme else ""

    # ── Bloc résumé système (style devis concurrent) ──
    if _g.SYNTHESE_AGRICOLE is not None:
        _sum_cells = _g._cartes_pompage_synthese(_g.SYNTHESE_AGRICOLE)
    elif _g.ETUDE.get("pompe_cv"):
        # Chiffres CANONIQUES calculés à la création du devis (courbe
        # constructeur) — rendus tels quels. Une carte sans valeur est
        # OMISE : jamais de tiret ni de m³/jour inventé sans courbe.
        # AGR302 — chiffres à la française partout (« 5,5 CV (3,7 kW) »,
        # « 62,5 m »), libellés passés par ``_L()`` (fr/en/ar), et la carte
        # eau dit qu'elle est une ESTIMATION sur des heures SUPPOSÉES. Aucun
        # nouveau chiffre : seul le format change.
        _sum_cells = []
        _pkw = _g.ETUDE.get("pompe_kw")
        _pcv = _g._fdec_fr(_g.ETUDE.get("pompe_cv"))
        _sum_cells.append((
            _g._L("puissance_pompe"),
            f"{_pcv} CV ({_g._fdec_fr(_pkw)} kW)" if _pkw else f"{_pcv} CV"))
        _hmt = _g.ETUDE.get("hmt_m")
        if _hmt:
            _sum_cells.append(("HMT", f"{_g._fdec_fr(_hmt)} m",
                               _g._ancre_figure("pompe_hmt_m", _hmt)))
        _dq = _g.ETUDE.get("debit_hmt_m3h")
        if _dq and _hmt:
            _sum_cells.append(
                (_g._L("debit_a_hmt").format(hmt=_g._fdec_fr(_hmt)),
                 f"{_g._fdec_fr(_dq, 1)} m&#179;/h",
                 _g._ancre_figure("pompe_debit_m3h", _g._fdec_fr(_dq, 1))))
        elif _g.ETUDE.get("debit_m3j"):  # anciens devis (saisie manuelle)
            _sum_cells.append(
                (_g._L("rpdf_debit_estime"),
                 _g._L("rpdf_m3_jour").format(n=_g._fdec_fr(_g.ETUDE.get('debit_m3j')))))
        _m3j = _g.ETUDE.get("m3_jour")
        _hrs = _g.ETUDE.get("heures_pompage")
        if _m3j and _hrs:
            _sum_cells.append(
                (f"{_g._L('eau_jour')} &#8212; {_g._L('estimation')}, "
                 f"{_g._L('sur_heures_pompage').format(heures=_g._fdec_fr(_hrs, 1))}",
                 f"&#8776; {_g.fnum(_m3j)} m&#179;",
                 _g._ancre_figure("pompe_volume_m3_jour", _g.fnum(_m3j))))
        if _g.KWC > 0:
            _sum_cells.append((_g._L("champ_pv"), f"{_g.kwc_fr(_g.KWC)} kWc",
                               _g._ancre_figure("puissance_kwc", _g.kwc_fr(_g.KWC))))
    elif _g.KWC > 0:
        _sum_cells = [
            (_g._L("op_puissance_crete"), _g.ci_onepage.kwc(_g.kwc_fr(_g.KWC), _g._L, _g.CHIFFRES_CI),
             _g._ancre_figure("puissance_kwc", _g.kwc_fr(_g.KWC))),
        ]
        if _g.CHIFFRES_CI is not None:
            # CIQ210 (complément) — commercial / industriel : les chiffres de
            # la couverture du document complet (``chiffres_cles``) ; absents
            # ⇒ omis, jamais la production par ville ni l'économie BT/60 %.
            _sum_cells += _g._cartes_ci_onepage(_g.CHIFFRES_CI)
        else:
            _sum_cells.append(
                (_g._L("op_production_annuelle"), _g._L("rpdf_kwh_an").format(n=_g.fnum(_g.PROD_KWH)),
                 _g._ancre_figure("production_annuelle_kwh", _g.fnum(_g.PROD_KWH))))
            # QXMT — dossier raccordé en MOYENNE TENSION sans économies d'étude :
            # la vignette « Économie annuelle » est OMISE. La valeur disponible
            # (``ECO_S_ANN``/``ECO_A_ANN``) sort de ``calculate_savings_roi``, au
            # barème BASSE TENSION de l'ONEE : l'imprimer sur un dossier MT donne
            # au client un chiffre qui n'est pas le sien.
            # M4 (audit du 19/08/2026) — L'ÉCONOMIE VIENT DE LA MÊME BRANCHE QUE LES
            # LIGNES. ``max(ECO_S_ANN, ECO_A_ANN)`` affichait l'économie de l'option
            # AVEC batterie sur un document qui chiffre l'option SANS — et qui le
            # dit, quelques centimètres plus bas (« voir la proposition complète »).
            # Deux histoires d'argent sur une seule page. Branche non identifiable
            # ⇒ vignette OMISE, jamais un maximum arbitraire.
            _eco_branche = {"sans": _g.ECO_S_ANN, "avec": _g.ECO_A_ANN}.get(
                _g.ONEPAGE_BRANCHE)
            if not _g.MASQUER_ECONOMIES and _eco_branche:
                _sum_cells.append(
                    (_g._L("op_economie_annuelle"),
                     _g._L("rpdf_mad_an").format(n=_g.fnum(_eco_branche))
                     + (_g._L("op_estimation") if _g.SAVINGS_ESTIMATED else ""),
                     _g._ancre_figure("economie_annuelle", _g.fnum(_eco_branche),
                                   _g.ONEPAGE_BRANCHE)))
        _pkwc_txt = _g.fnum(round(total / _g.KWC))
        # AMOT86 (D-ACI-2=a) — postes « à chiffrer après la visite » hors
        # total : aucun « Prix par kWc » sur un prix incomplet.
        _sum_cells += [] if (_g.CHIFFRES_CI or {}).get("postes_hors_total") else [
            (_g._L("op_prix_par_kwc"), _g._L("rpdf_mad_par").format(
                n=_pkwc_txt, u=_g.ci_onepage.unite_kwc(_g._L, _g.CHIFFRES_CI)),
             _g._ancre_figure("prix_kwc", _pkwc_txt, _op_opt))]
        # CJ2b-bis — mention falaise/tranche en UNE cellule, seulement si le
        # contrat DIM2 est posé (voir _falaise_context) : le budget densité
        # adaptative de cette page ne dépend que du nombre de LIGNES produit
        # (ci-dessous), pas du nombre de vignettes du résumé — une cellule de
        # plus dans cette rangée fixe ne fait jamais déborder la page.
        from .legacy_etude import _falaise_context  # SPL169 — import local
        _fctx_onepage = _falaise_context()
        if _fctx_onepage and _fctx_onepage.get("residuel_kwh_mois") is not None:
            _rtxt = _g._L("lg_kwh_mois").format(n=_g.fnum(_fctx_onepage['residuel_kwh_mois']))
            if _fctx_onepage.get("tranche_apres"):
                # QJR163 (b) — ÉCHAPPÉ comme sur la page étude : ce libellé
                # vient du contrat de dimensionnement, pas d'une constante.
                _rtxt += f" ({_g._esc(_fctx_onepage['tranche_apres'])})"
            _sum_cells.append((_g._L("op_residuel_vise"), _rtxt))
    else:
        _sum_cells = []
    summary_html = ""
    if _sum_cells:
        cells = "".join(
            f'<div style="flex:1;text-align:center;">'
            f'<div style="font-size:5.5pt;font-weight:700;color:{_g.CG4};'
            f'text-transform:uppercase;letter-spacing:.8px;">{label}</div>'
            f'<div style="font-size:9pt;font-weight:800;color:{_g.CN};margin-top:2px;">{val}</div>'
            f'{"".join(_fig)}</div>'
            for label, val, *_fig in _sum_cells)
        # AMOT82 (D-ACI-10=a) — une-page C&I « sous réserve de visite » : le
        # bandeau de la couverture puis la ligne de méthode des taux, sous les
        # cartes (deux lignes fines ; la densité adaptative des lignes produit
        # garde la page unique). Décision fondateur 26/10/2026 : le bandeau
        # « Devis préliminaire » est imprimé même sans réserve.
        summary_html = (
            f'<div style="display:flex;background:{_g.CAL};border-bottom:2px solid {_g.CA};'
            f'padding:8px 24px;">{cells}</div>'
            + "".join(
                f'<div style="padding:2px 24px;font-size:6.5pt;color:{_g.CG7};'
                f'line-height:1.3;">{texte}</div>'
                for texte in (
                    # Décision fondateur 26/10/2026 — « Devis préliminaire »
                    # sur TOUT une-page C&I ; la méthode, seulement sous
                    # réserve (inchangé).
                    [f"<b>{_g._L('op_reserve_visite')}</b>"]
                    + ([_g._L(f"ci_methode_{_g.CHIFFRES_CI['methode']}")
                        if f"ci_methode_{_g.CHIFFRES_CI['methode']}"
                        in _g.i18n_labels.LIBELLES
                        else _g.CHIFFRES_CI["libelle_methode"]]
                       if _g.CHIFFRES_CI.get("libelle_methode")
                       and _g.CHIFFRES_CI.get("sous_reserve") else [])
                    if isinstance(_g.CHIFFRES_CI, dict) else ())))

    # Build table rows (per-line HT, with description + warranty detail lines).
    # Densité ADAPTATIVE pour tenir sur UNE page quoi qu'il arrive :
    #   ≤ 8 lignes  → descriptions complètes (4 lignes) + garantie
    #   9–12 lignes → descriptions courtes (2 lignes) + garantie
    #   > 12 lignes → table compacte (désignation + marque seulement)
    visible = [it for it in items if float(it.get("quantite", 0)) > 0]
    # XSAL14 — intercale les lignes de section/note (rendu seul, hors totaux)
    # dans la liste, ordonnées par ``ordre`` (stable) puis par l'ordre d'origine.
    # Absentes → séquence STRICTEMENT identique à avant (byte-identique).
    # QJR617 — UNE fonction pure partagée (``quote_engine/sequence.py``).
    _seq = _g.sequence_affichage(visible, _g.LIGNES_STRUCTURE)
    n_items = len(visible) + len(_g.LIGNES_STRUCTURE or [])
    if n_items <= 8:
        max_desc, desc_pt, pad_px, show_gar = 4, 6.5, 6, True
    elif n_items <= 12:
        max_desc, desc_pt, pad_px, show_gar = 2, 6, 4, True
    else:
        max_desc, desc_pt, pad_px, show_gar = 0, 6, 3, False

    rows_html = ""
    row_idx = 0
    for _kind, _obj in _seq:
        if _kind == "struct":
            # XSAL14 — ligne de SECTION (intertitre) ou de NOTE (texte), sur
            # toute la largeur, sans prix (jamais comptée dans les totaux).
            _txt = _obj.get("texte", "") or ""
            if _obj.get("type") == "note":
                rows_html += (
                    f'<tr><td colspan="6" style="padding:{pad_px}px 10px;'
                    f'font-style:italic;font-size:7.5pt;color:{_g.CG4};">{_txt}</td></tr>')
            else:
                rows_html += (
                    f'<tr><td colspan="6" style="padding:{pad_px + 1}px 10px;'
                    f'background:{_g.CG1};font-weight:800;font-size:8pt;color:{_g.CN};'
                    f'text-transform:uppercase;letter-spacing:.6px;'
                    f'border-top:1px solid {_g.CA};">{_txt}</td></tr>')
            continue
        it = _obj
        qty = float(it.get("quantite", 0))
        bg = "white" if row_idx % 2 == 0 else _g.CG1
        pu_ht = _g._item_pu_ht(it)
        line_total = qty * pu_ht
        marque = it.get("marque", "") or ""
        des = it.get("designation", "")
        qty_str = str(int(qty)) if qty == int(qty) else _g.fnum(qty)
        marque_html = _g.badge(marque) if marque else ""
        detail_html = _g._desc_lines_html(it, max_lines=max_desc, font_pt=desc_pt) if max_desc else ""
        gar = _g.garantie_ligne_onepage(
            it, _g._L, (getattr(_g, "MODE_INSTALLATION", None) or "").strip().lower() == "agricole")
        if gar and show_gar:
            detail_html += (
                f'<div style="font-size:{desc_pt}pt;color:{_g.CGR};font-weight:600;'
                f'padding-left:6px;">&#10003; {gar}</div>')
        _taux = it.get("taux_tva", _g.TVA_PCT)
        _taux_s = f"{_g.pct_fr(_taux)}&#37;"  # AMOT24
        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:{pad_px}px 10px;word-break:break-word;">'
            f'<div style="font-weight:700;color:{_g.CN};">{des}</div>{detail_html}'
            f'{_g.ci_tableau.sous_lignes_html(it, desc_pt, _g.CG4)}</td>'
            f'<td style="padding:{pad_px}px 10px;">{marque_html}</td>'
            f'<td style="padding:{pad_px}px 10px;text-align:center;color:{_g.CG7};">{qty_str}</td>'
            f'<td style="padding:{pad_px}px 10px;text-align:right;color:{_g.CG7};">'
            f'{_g._cellule_prix_remise(pu_ht, _g._item_pu_ht_remise(it))}</td>'
            f'<td style="padding:{pad_px}px 10px;text-align:center;color:{_g.CG4};font-size:7.5pt;">{_taux_s}</td>'
            f'<td style="padding:{pad_px}px 10px;text-align:right;font-weight:500;color:{_g.CN};">'
            f'{_g._cellule_prix_remise(line_total, _g._item_total_ht_remise(it))}</td>'
            f'</tr>'
        )
        row_idx += 1

    # QJR161 — les lignes RETIRÉES faute de place sont DÉCLARÉES, jamais
    # coupées en silence : le lecteur sait que la table n'est pas exhaustive et
    # que le total, lui, porte bien TOUT le devis.
    if tronquees > 0:
        rows_html += (
            f'<tr><td colspan="6" style="padding:{pad_px}px 10px;'
            f'font-style:italic;font-size:7pt;color:{_g.CG4};">'
            # ERR-APDF-LIBELLES-FR-RESTANTS-EN-AR — phrase du catalogue.
            + _g._L("op_lignes_tronquees_n" if tronquees > 1
                 else "op_lignes_tronquees_1").format(
                n=tronquees, renvoi=_g._renvoi_detail_complet())
            + '</td></tr>')

    # ── Bloc totaux : Sous-total HT → Remise visible → Total HT → TVA → TTC ──
    def _tot_line(label, value, navy=False, neg=False, fig=None, taux=None):
        color = _g.CGR if neg else (_g.CN if not navy else _g.CN)
        size = "13pt" if navy else "8.5pt"
        weight = 800 if navy else 600
        _a = _g._ancre_figure(fig, value, _op_opt, taux) if fig else ""
        return (
            f'<div style="margin-top:2px;">'
            f'<span style="font-size:8pt;font-weight:700;color:{_g.CG4 if not navy else _g.CN};'
            f'text-transform:uppercase;letter-spacing:.5px;margin-right:18px;">{label}</span>'
            f'<span style="display:inline-block;min-width:110px;text-align:right;'
            f'font-size:{size};font-weight:{weight};color:{color};white-space:nowrap;">{value}</span>'
            f'{_a}</div>')

    # NTI18N5 — SEULS LES MOTS changent avec la langue : chaque montant reste
    # produit par `_fmt2` et la ponctuation des pourcentages (espace fine
    # `&#8201;`) est celle du document français, dans les trois langues.
    # Le COMMENTAIRE HTML qui annonce ce bloc plus bas dérive lui aussi de
    # `_L(...)` : écrit en dur, il laissait « Sous-total HT » dans le document
    # anglais et arabe (un littéral français voyage dans le HTML livré, même
    # invisible à l'impression). Aucun libellé de ce bloc ne s'écrit en dur.
    totals_html = _tot_line(_g._L("sous_total_ht"), _g._fmt2(total_ht) + "&nbsp;MAD",
                            fig="sous_total_ht")
    if _g.DISCOUNT_PCT > 0:
        _pct = _g.pct_fr(_g.DISCOUNT_PCT)  # AMOT24
        totals_html += _tot_line(
            f"{_g._L('remise')} ({_pct}&#8201;%)",
            "&#8722;" + _g._fmt2(remise) + "&nbsp;MAD", neg=True, fig="remise")
    # ARRONDI-100 — même ligne visible que le bloc multi-pages.
    _arrondi = totaux.get("arrondi") or 0
    if _arrondi > 0:
        totals_html += _tot_line(
            _g._L("arrondi"), "&#8722;" + _g._fmt2(_arrondi) + "&nbsp;MAD",
            neg=True, fig="arrondi")
    if _g.DISCOUNT_PCT > 0 or _arrondi > 0:
        totals_html += _tot_line(_g._L("total_ht"), _g._fmt2(net_ht) + "&nbsp;MAD",
                                 fig="total_ht")
    # TVA éclatée par taux présent (réforme 10/20) ; un seul taux → ligne
    # unique identique aux devis historiques.
    _buckets = totaux.get("tva_par_taux") or []
    if len(_buckets) > 1:
        for _b in _buckets:
            _r = _g.pct_fr(_b["taux"])  # AMOT24
            totals_html += _tot_line(
                f"{_g._L('tva')} ({_r}&#8201;%)", _g._fmt2(_b["montant"]) + "&nbsp;MAD",
                fig="tva_taux", taux=_b["taux"])
    else:
        _rate = _buckets[0]["taux"] if _buckets else _g.TVA_PCT
        _tva_pct = _g.pct_fr(_rate)  # AMOT24
        totals_html += _tot_line(f"{_g._L('tva')} ({_tva_pct}&#8201;%)",
                                 _g._fmt2(tva_amt) + "&nbsp;MAD", fig="tva")
    # QJR122 — même chaîne additive que la page 2 : le Total TTC du une-page
    # s'imprime au CENTIME (il était seul arrondi à l'unité de son bloc).
    # AMOT86 — postes « à chiffrer après la visite » : titre servi + postes.
    totals_html = _g.ci_onepage.totaux_hors_total(totals_html + _tot_line(
        _g._L("total_ttc"), _g._fmt2(total) + "&nbsp;MAD", navy=True, fig="total_ttc"),
        _g.CHIFFRES_CI, _g.SYNTHESE_CI, _g.LANGUE_SORTIE, _g.LIBELLES_DOC, (_g.CN, _g.CG7))

    # ── XSAL5 — Bloc « Options proposées » (opt-in, HORS total) ──────────────
    # Rendu SEUL : n'affiche que les add-ons proposés (P.U. + total TTC), jamais
    # ajoutés au total ci-dessus. Absent → byte-identique (aucun bloc).
    options_html = ""
    if _g.OPTIONS_PROPOSEES:
        _opt_rows = ""
        for _o in _g.OPTIONS_PROPOSEES:
            _oq = float(_o.get("quantite", 0) or 0)
            _oq_s = str(int(_oq)) if _oq == int(_oq) else _g.fnum(_oq)
            _obadge = _g.badge(_o.get("marque", "")) if _o.get("marque") else ""
            _opt_rows += (
                f'<tr>'
                f'<td style="padding:4px 10px;color:{_g.CN};font-weight:600;">'
                f'{_o.get("designation", "")} {_obadge}</td>'
                f'<td style="padding:4px 10px;text-align:center;color:{_g.CG7};">{_oq_s}</td>'
                f'<td style="padding:4px 10px;text-align:right;color:{_g.CN};font-weight:600;">'
                # QJR616 — le supplément canonique du builder (remise globale
                # comprise), plus un P.U. × qté recalculé ici.
                f'{_g.fmt(round(float(_o.get("total_ttc", 0) or 0)))}</td>'
                f'</tr>')
        options_html = (
            f'<div style="padding:8px 24px 0;">'
            f'<div style="font-size:7pt;font-weight:800;color:{_g.CA};'
            f'text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px;">'
            f'{_g._L("lg_options_proposees")}</div>'
            f'<table style="width:100%;border-collapse:collapse;font-size:8pt;'
            f'border:1px dashed {_g.CA};">{_opt_rows}</table>'
            f'<div style="font-size:6.5pt;color:{_g.CG4};font-style:italic;'
            f'margin-top:2px;">{_g._L("lg_activez_option")}</div></div>')

    # LANE CHOIX-AVEC (fondateur, 25/08/2026) — le mot de la note SUIT
    # ``ONEPAGE_BRANCHE`` au lieu de le supposer « sans » : builder.py rend
    # maintenant l'option AVEC batterie sur cette page quand elle est
    # servable (la règle « choisis l'option avec quand tu dois choisir »),
    # donc le texte qui dit CE QUE CE DOCUMENT CHIFFRE doit dire la même
    # chose que les lignes réellement imprimées au-dessus. Un texte figé sur
    # « sans batterie » aurait décrit une page en réalité chiffrée avec.
    # BAT-DIFF — l'option « avec » porte le libellé du builder (« Hybride,
    # batterie plus tard » quand elle est servie sans batterie chiffrée).
    # ERR-APDF-LIBELLES-FR-RESTANTS-EN-AR — noms d'option du catalogue.
    _libelle_avec_min = _g.i18n_labels.nom_option(_g.LIBELLE_AVEC, _g.LANGUE_SORTIE,
                                               minuscule=True)
    _onepage_note_ceci = (_libelle_avec_min if _g.ONEPAGE_BRANCHE == "avec"
                          else _g.i18n_labels.nom_option(
                              "Sans batterie", _g.LANGUE_SORTIE, minuscule=True))
    _onepage_note_autre = (_g.i18n_labels.nom_option(
        "Sans batterie", _g.LANGUE_SORTIE, minuscule=True)
        if _g.ONEPAGE_BRANCHE == "avec" else _libelle_avec_min)

    header_html = _onepage_header_html()
    # AGR313 — « Bon pour accord » compact du une-page agricole (nom, date,
    # signature) ; les options à cocher et le schéma restent au 3 pages.
    # CPDF — même bloc sur le une-page commercial / industriel (D-CIQ-11 : le
    # client signe aussi le document court) ; l'autre option y est déjà dite.
    bpa_html = (_g._bon_pour_accord_compact_html()
                if _g.SYNTHESE_AGRICOLE is not None
                or _g.CHIFFRES_CI is not None else "")

    return f"""
<div class="page" style="position:relative;display:block;">

  <!-- CONTENT AREA: block flow, footer space reserved (WeasyPrint-robuste :
       pas de flex:1 ni de gap, qui rendaient le total par-dessus le footer) -->
  <div style="position:absolute;top:0;left:0;right:0;bottom:{_g.ONEPAGE_FOOTER_PX}px;overflow:hidden;">

  <!-- HEADER: navy (QRP1 — variante avec vignette QR quand le devis porte un
       lien de proposition tokenisé ; sinon rendu historique au bit près) -->
  {header_html}

  <!-- CLIENT BLOCK -->
  <div style="background:{_g.CG1};padding:12px 24px;border-bottom:1px solid {_g.CG2};">
    <div style="font-size:6.5pt;font-weight:700;color:{_g.CG4};text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">{_g._L("client")}</div>
    <div style="font-size:11pt;font-weight:700;color:{_g.CN};">{_g.CLIENT_NAME}</div>
    <div style="font-size:8.5pt;color:{_g.CG7};margin-top:2px;">{_g.CLIENT_ADDR}</div>
    <div style="font-size:8.5pt;color:{_g.CG4};margin-top:1px;">{_g.ci_onepage.telephone(_g.CLIENT_PHONE, _g.CHIFFRES_CI)}</div>
    {'<div style="font-size:8pt;color:' + _g.CG7 + ';margin-top:3px;"><span style="color:' + _g.CG4 + ';font-weight:600;">ICE&#160;:</span>&#160;' + _g.CLIENT_ICE + '</div>' if _g.CLIENT_ICE else ''}
  </div>

  <!-- SYSTEM SUMMARY (kWc / production / économie / prix par kWc, ou pompage) -->
  {summary_html}

  <!-- PRODUCT TABLE (per-line HT) -->
  <div style="padding:12px 24px 0;">
    <table style="width:100%;border-collapse:collapse;font-size:8.5pt;table-layout:fixed;">
      <colgroup>
        <col style="width:39%">
        <col style="width:12%">
        <col style="width:7%">
        <col style="width:16%">
        <col style="width:7%">
        <col style="width:19%">
      </colgroup>
      <thead>
        <tr style="background:{_g.CN};">
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:left;text-transform:uppercase;letter-spacing:.5px;">{_g._L("designation")}</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:left;text-transform:uppercase;letter-spacing:.5px;">{_g._L("marque")}</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:center;text-transform:uppercase;letter-spacing:.5px;">{_g._L("qte")}</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:right;text-transform:uppercase;letter-spacing:.5px;">{_g._L("pu_ht")} (MAD)</th>
          <th style="padding:8px 6px;color:white;font-weight:700;font-size:7.5pt;text-align:center;text-transform:uppercase;letter-spacing:.5px;">{_g._L("tva")}</th>
          <th style="padding:8px 10px;color:white;font-weight:700;font-size:7.5pt;text-align:right;text-transform:uppercase;letter-spacing:.5px;">{_g._L("total_ht")} (MAD)</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

  <!-- TOTALS: {_g._L("sous_total_ht")} → {_g._L("remise")} visible → {_g._L("total_ht")} → {_g._L("tva")} → {_g._L("total_ttc")} -->
  <div style="background:{_g.CAL};border-top:2px solid {_g.CA};padding:10px 14px;margin:12px 24px 0;text-align:right;">
    {totals_html}
  </div>

  <!-- XSAL5 — Options proposées (opt-in, hors total ; absent = byte-identique) -->
  {options_html}

  <!-- QJ30 — ×N propriétés identiques (ligne compacte ; une page préservée) -->
  <div style="padding:6px 24px 0;">{_g._multi_proprietes_line_html()}</div>

  <!-- CONDITIONS : sous le total -->
  <div style="padding:8px 24px;">
    {_g._note_client_html("7.5")}{_g._clauses_cgv_html("7")}
    {'<div style="font-size:7.5pt;color:' + _g.CG4 + ';font-style:italic;margin-bottom:3px;">' + _g._L('op_note_batterie').format(ceci=_onepage_note_ceci, autre=_onepage_note_autre) + '</div>' if _g.ONEPAGE_NOTE_BATTERIE else ''}
    <div style="font-size:7pt;color:{_g.CG4};">
      {_g._conditions_onepage_html()}
    </div>
  </div>
  {bpa_html}

  </div><!-- /CONTENT AREA -->

  <!-- FOOTER: navy + legal identity, toujours en bas de page, jamais chevauché -->
  <div style="position:absolute;left:0;right:0;bottom:0;background:{_g.CN};padding:6px 24px 5px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
      <div style="font-size:9pt;font-weight:800;color:{_g.CA};letter-spacing:1px;">{_g.ENT_NOM_MARQUE}</div>
      <div style="font-size:7pt;color:#888;text-align:center;">
        {_g.ENT_CONTACT_LINE}
      </div>
      <div style="font-size:7pt;color:#888;">{_g._L("reference")}&#160;{_g.REF}{(" &#183; " + _g._L("res_page") + " 1&nbsp;/&nbsp;2") if _g.SIGNE_AU_DOMICILE else ""}</div>
    </div>
    <div style="font-size:7.5px;color:#888;text-align:center;font-style:italic;">
      {_g.ENT_LEGAL_LINE}
    </div>
  </div>

</div>
"""


def build_html_onepage(items, tronquees=0):
    """Minimal HTML shell for the one-page PDF.

    AMOT53 (D-AMOT-2 = a) — bon de commande signé au domicile : l'annexe de
    rétractation (``page_annexe_domicile``, corps partagé AMOT23) suit en 2ᵉ
    page DÉCLARÉE ; jamais une copie de son HTML."""
    return f"""<!DOCTYPE html>
<html {_g._attributs_langue_html()} style="background:#FFFFFF !important;"><head><meta charset="UTF-8">
<title>{_g._L("rpdf_titre_doc").format(marque=_g.ENT_NOM_MARQUE, ref=_g.REF)}</title>
<style>{_g.CSS}{_g._css_arabe() if _g.i18n_labels.est_rtl(_g.LANGUE_SORTIE) else ""}</style></head>
<body style="background:#FFFFFF !important;">
{page_onepage(items, tronquees)}{_g.page_annexe_domicile(pied=f"{_g._L('lg_ret_pied').format(ref=_g.REF)} &#183; {_g._L('res_page')} 2&nbsp;/&nbsp;2") if _g.SIGNE_AU_DOMICILE else ""}
</body></html>"""
