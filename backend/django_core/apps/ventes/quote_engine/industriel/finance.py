# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""quote_engine industriel — PAGE 3 (rentabilité : jalons 5/10/15/20/25,
courbe du cumul sur tout l'horizon, TRI avec son horizon, payback ancré).

``build(ctx) -> str`` returns the INNER HTML of one A4 page (no wrapper/footer).
CSS tables only. Classes prefixed ``i2-``.

CIQ342 (D-CIQ-10) — la page REND ``synthese_ci['argent']`` tel que servi
(bloc ``economie_ci`` du moteur C&I, CIQ3/CIQ304) : flux 25 ans de la base
principale, jalons, indicateurs (TRI + horizon, retour), revente « hors
cashflow » (le moteur ne l'additionne jamais au flux), O&M déduite
SEULEMENT si l'option est chiffrée, hypothèses du moteur, pied de page sur la
base servie (CIQ315). Plus AUCUNE arithmétique privée : ni solveur de TRI,
ni troncature à 15 ans, ni flux reconstruit. Sans série servie, le motif.

CIQ343 (D-CIQ-10, D-CIQ-15) — sous le tableau, un bloc compact pour la
direction financière : LCOE face au prix du kWh du client, VAN seulement
sur le taux DÉCLARÉ, sensibilités saisies par la société, P90 du bloc
bancable (PDF seulement), offre de financement (CIQ318).
Rendu seul — aucun statut touché (règle #4).
"""
from functools import partial

from ..ci import blocs as ci_blocs
from .. import premium_base
from ..ci import couverture as ci_couverture
from ..figures import ancre
from ..lecture_pure import nombre_ou_none
from ..montants import decimale
# AMOT90 — l'énergie mois par mois (SVG en ligne, données servies).
from ..ci.graphiques import bloc_energie_mensuelle, cede, css_graphique

#: Années des jalons (D-CIQ-10) — l'ordre d'impression, pas un calcul.
JALONS_ANS = (5, 10, 15, 20, 25)

#: Hypothèses du flux servi (``flux_*.hypotheses[].cle``) → libellé imprimé.
LIBELLES_HYPOTHESES = {
    "investissement_mad": ("ci_ind_h_investissement", "Investissement"),
    "economie_annee1_mad": ("ci_ind_h_economie", "Économie de l'année 1"),
    "production_annee1_kwh": ("ci_ind_h_production",
                              "Production de l'année 1"),
    "horizon_ans": ("ci_ind_h_horizon", "Horizon"),
    "taux_actualisation_pct": ("ci_ind_h_taux", "Taux d'actualisation"),
    "indexation_pct": ("ci_ind_h_indexation", "Indexation du tarif"),
    "degradation_pct": ("ci_ind_h_degradation", "Dégradation des panneaux"),
    # AMOT99 — la perte de la 1re année publiée par la fiche module.
    "degradation_annee1_pct": ("ci_ind_h_degradation_annee1",
                               "Dégradation de la 1re année"),
}
UNITES_HYPOTHESES = {
    "investissement_mad": "MAD", "economie_annee1_mad": "MAD",
    "production_annee1_kwh": "kWh", "horizon_ans": None,
    "taux_actualisation_pct": "%", "indexation_pct": "% / an",
    "degradation_pct": "% / an", "degradation_annee1_pct": "%",
}

_num = nombre_ou_none

#: AMOT88 — le titre du bloc d'hypothèses, en mots du client.
TITRE_HYPOTHESES = "Hypothèses de l'estimation"


def flux_principal(argent):
    """``(clé, bloc)`` du flux de la base principale servie (``flux_ttc``
    en base TTC, ``flux_ht`` sinon — la règle du moteur ``economie_ci``)."""
    if not isinstance(argent, dict):
        return None, {}
    cle = "flux_ttc" if argent.get("base") == "ttc" else "flux_ht"
    bloc = argent.get(cle)
    return cle, bloc if isinstance(bloc, dict) else {}


def _courbe(flux, couleurs):
    """Courbe du cumul net, une barre par année sur TOUT l'horizon servi
    (au-dessus de l'axe : positif ; en dessous : négatif). Seule la HAUTEUR
    des barres est mise à l'échelle — aucun montant n'est calculé."""
    points = [(_num(f.get("annee")), _num(f.get("cumul_mad")))
              for f in flux if isinstance(f, dict)]
    points = [(a, c) for a, c in points if a is not None and c is not None]
    if len(points) < 2:
        return ""
    echelle = max(abs(c) for _a, c in points) or 1.0
    haut, bas = "", ""
    for annee, cumul in points:
        h = round(abs(cumul) / echelle * 18.0, 1)
        if cumul >= 0:
            haut += (f'<td class="i2-cb"><div class="i2-bp" '
                     f'style="height:{h}mm"></div></td>')
            bas += '<td class="i2-ct"></td>'
        else:
            haut += '<td class="i2-cb"></td>'
            bas += (f'<td class="i2-ct"><div class="i2-bn" '
                    f'style="height:{h}mm"></div></td>')
    etiquettes = "".join(
        f'<td class="i2-ca">{int(a) if a in (0,) + JALONS_ANS else ""}</td>'
        for a, _c in points)
    return (f'<table class="i2-courbe"><tr>{haut}</tr>'
            f'<tr class="i2-axe">{bas}</tr><tr>{etiquettes}</tr></table>')


def _charges_par_annee(argent, cle_flux):
    """AMOT94 — ``(O&M annuelle | None, {année: remplacement})`` du flux
    servi : l'O&M seulement souscrite et chiffrée (CIQ342 — sinon elle n'est
    pas déduite, la colonne est omise) ; chaque remplacement au montant de
    la base du flux (HT pour ``flux_ht``, TTC pour ``flux_ttc``)."""
    om = argent.get("om") if isinstance(argent.get("om"), dict) else {}
    om_an = (_num(om.get("montant_mad_an"))
             if om.get("statut") == "souscrit" else None)
    # AMOT96 — sans O&M souscrite : l'entretien minimum DÉDUIT par le moteur.
    om_an = om_an or _entretien_deduit(argent)
    cle_montant = "montant_ttc_mad" if cle_flux == "flux_ttc" \
        else "montant_ht_mad"
    remplacements = {}
    for r in argent.get("remplacements") or []:
        if isinstance(r, dict) and _num(r.get("annee")) is not None \
                and _num(r.get(cle_montant)) is not None:
            annee = int(_num(r["annee"]))
            remplacements[annee] = remplacements.get(annee, 0.0) \
                + _num(r[cle_montant])
    return om_an or None, remplacements


def _tableau_flux(argent, lignes_flux, fmt, fmt_mad, L, base_txt):
    """AMOT94 — le flux de trésorerie servi, année par année (0 → horizon) :
    année, production (kWh), économie, O&M (si déduite), remplacement (si
    servi), flux net et cumul — chaque nombre est celui de la ligne servie
    par ``economie_ci`` (aucun recalcul) ; le cumul de l'année 25 est ancré
    (``cumul_net_25_ans_mad``). Typographie compacte : le contrat de 4 pages
    tient."""
    cle_flux, _bloc = flux_principal(argent)
    om_an, remplacements = _charges_par_annee(argent, cle_flux)
    colonnes = [L("ci_fx_production", "Production (kWh)"),
                L("ci_fx_economie", "Économie")]
    colonnes += [L("ci_fx_entretien", "Entretien") if _entretien_deduit(argent)
                 else L("ci_fx_om", "O&amp;M")] if om_an else []
    colonnes += [L("ci_fx_remplacement", "Remplacement")] \
        if remplacements else []
    colonnes += [L("ci_fx_flux", "Flux net"),
                 f'{L("ci_ind_cumul_net", "Cumul net")} ({base_txt})']
    entete = (f'<tr><th>{L("ci_fx_annee", "Année")}</th>'
              + "".join(f'<th class="i2-r">{c}</th>' for c in colonnes)
              + "</tr>")
    rangees = ""
    for f in lignes_flux:
        annee = int(_num(f.get("annee")) or 0)
        cumul = _num(f.get("cumul_mad"))
        if cumul is None:
            continue
        txt = fmt_mad(cumul)
        production = _num(f.get("production_kwh"))
        cellules = [fmt(production) if production else "—",
                    fmt_mad(_num(f.get("economie_mad")) or 0) if annee
                    else "—"]
        # Les charges sont des SORTIES du flux : le signe du formateur.
        if om_an:
            cellules.append(fmt_mad(-om_an) if annee else "—")
        if remplacements:
            cellules.append(fmt_mad(-remplacements[annee])
                            if annee in remplacements else "—")
        cellules.append(fmt_mad(_num(f.get("flux_mad")) or 0))
        fig = ancre("cumul_net_25_ans_mad", txt) if annee == 25 else ""
        cls = "i2-pos" if cumul >= 0 else "i2-neg"
        rangees += (f'<tr><td>{L("ci_ind_annee", "Année {n}", n=annee)}</td>'
                    + "".join(f'<td class="i2-n">{c}</td>' for c in cellules)
                    + f'<td class="i2-c {cls}">{txt}{fig}</td></tr>')
    return (f'<table class="i2-tbl i2-fx">{entete}{rangees}</table>'
            if rangees else "")


def _valeur_hypothese(h, fmt, L):
    valeur = h.get("valeur")
    cle = h.get("cle")
    if valeur is None:
        return None
    unite = UNITES_HYPOTHESES.get(cle)
    if isinstance(valeur, (int, float)):
        if cle == "horizon_ans":
            return L("ci_ind_n_ans", "{n} ans", n=f"{valeur:g}")
        texte = fmt(valeur) if unite in ("MAD", "kWh") else \
            decimale(f"{valeur:g}")
        if unite == "% / an":
            unite = L("ci_ind_pct_an", unite)
        return f"{texte}&nbsp;{unite}" if unite else texte
    return ci_blocs._txt(valeur)


#: Décision fondateur 26/10/2026 — codes de source (AMOT84) qui ne sont
#: qu'une réserve interne : la valeur est imprimée, jamais cette source.
CODES_SOURCES_RESERVE = frozenset({
    "indexation_constante", "degradation_defaut_fiche_muette",
    "degradation_fiche_sans_annee1"})

#: AMOT91 — hypothèses du flux dont le montant est déjà imprimé ailleurs sur
#: le document commercial (couverture, page 2) : hors du tableau compact.
CLES_MONTANTS_FLUX = ("investissement_mad", "economie_annee1_mad",
                      "production_annee1_kwh")


def _texte_code(d, L, code, servi):
    """AMOT84 — le libellé ``ci_code_<code>`` dans la langue du document
    (le texte ``servi`` en français, octet pour octet), ou ``servi`` tel
    quel sans code connu du catalogue."""
    cle = f"ci_code_{code}" if code else ""
    if cle and cle in _cles_catalogue():
        return L(cle, servi)
    return servi


def _rangees_flux(flux, fmt, L, d, compact):
    """``(libellé, valeur — source)`` des hypothèses du flux servi."""
    rangees = []
    for h in flux.get("hypotheses") or []:
        if not isinstance(h, dict) or h.get("cle") not in LIBELLES_HYPOTHESES \
                or (compact and h["cle"] in CLES_MONTANTS_FLUX):
            continue
        valeur = _valeur_hypothese(h, fmt, L)
        if valeur is None:
            continue
        cat, fr = LIBELLES_HYPOTHESES[h["cle"]]
        if h["cle"] == "horizon_ans" and ci_couverture.SOURCES_CLIENT.get(
                str(h.get("source") or "").strip()) == "ci_src_horizon":
            # « Horizon : 25 ans » — la source servie (« durée d'analyse :
            # 25 ans ») ne ferait que le répéter.
            rangees.append((L(cat, fr), valeur))
            continue
        # AMOT80 — chaque source dans les mots du client (aucun code interne).
        # AMOT84 — une source servie sous un code stable (``source_code``)
        # est imprimée dans la langue du document ; le texte servi en repli.
        source = _texte_code(d, L, h.get("source_code"),
                             ci_couverture.texte_client(d, h.get("source")))
        # Décision fondateur 26/10/2026 — une source qui n'est qu'une
        # réserve interne (« défaut, fiche muette », « tarif de vente
        # constant (hypothèse) »…) n'est pas imprimée : la valeur seule.
        if h.get("source_code") in CODES_SOURCES_RESERVE:
            source = ""
        source = ci_couverture.sans_reserve(source)
        rangees.append((L(cat, fr), valeur + (f" — {source}" if source
                                              else "")))
    return rangees


def _rangees_argent(argent, fmt_mad, L, d):
    """``(libellé | None, valeur)`` : valorisation, prix du kWh (AMOT88 :
    grille publiée datée ou votre facture, jamais « repli »), remplacements
    au montant réel de la ligne du devis."""
    from ..ci.mentions import ligne_tarif_client
    rangees = []
    for h in argent.get("hypotheses") or []:
        if not isinstance(h, dict):
            continue
        tarif_txt = (ligne_tarif_client(argent.get("tarif"),
                                        ci_blocs.langue(d))
                     if h.get("cle") == "tarif" else None)
        if tarif_txt:
            rangees.append((L("ci_h_prix_kwh", "Prix du kWh"), tarif_txt))
        elif h.get("valeur"):
            source = ci_couverture.sans_reserve(
                ci_couverture.texte_client(d, h.get("source")))
            rangees.append((
                L("ci_h_valorisation", "Valorisation de vos kWh")
                if h.get("cle") == "valorisation" else None,
                _texte_code(d, L, h.get("valeur_code"),
                            ci_blocs._txt(h.get("valeur")))
                + (f" — {source}" if source else "")))
    # AMOT94 — le montant du remplacement sur la BASE servie : HT quand la
    # TVA est récupérable (``argent.base == 'ht'``, D-CIQ-3), TTC sinon.
    en_ht = argent.get("base") == "ht"
    for r in argent.get("remplacements") or []:
        if not isinstance(r, dict) or r.get("annee") is None:
            continue
        montant = r.get("montant_ttc_mad")
        unite = L("ci_ttc", "TTC")
        if en_ht and r.get("montant_ht_mad") is not None:
            montant, unite = r.get("montant_ht_mad"), L("ci_ht", "HT")
        composant = ci_blocs._txt(r.get("composant"))
        cle_composant = f"ci_garantie_{composant}"
        if ci_blocs.langue(d) != "fr" and cle_composant in _cles_catalogue():
            composant = L(cle_composant, composant)
        motif = ci_couverture.sans_reserve(
            ci_couverture.texte_client(d, r.get("motif")))
        motif = f" — {motif}" if motif else ""
        rangees.append((
            L("ci_ind_remplacement", "Remplacement {composant} en année "
              "{annee}", composant=composant,
              annee=f"{r['annee']:g}" if isinstance(r["annee"], (int, float))
              else r["annee"]),
            (f"{fmt_mad(montant)}&nbsp;MAD {unite}"
             if montant is not None else "") + motif))
    return rangees


def _rangees_estimation(synthese, L):
    """AMOT91 — la base de production (« 30° d'inclinaison, plein sud — à
    confirmer au calepinage », ou le calepinage retenu) et la règle de
    dimensionnement (D-CIQ-2 : « chaque palier de 5 kWc retenu se rembourse
    en moins de 10 ans »), lues sur ``synthese_ci['estimation']``."""
    estimation = (synthese or {}).get("estimation") if isinstance(
        synthese, dict) else None
    estimation = estimation if isinstance(estimation, dict) else {}
    rangees = []
    prod = estimation.get("production") or {}
    titre = L("ci_h_base_production", "Base de production")
    if prod.get("source") == "calepinage":
        rangees.append((titre, L("ci_h_base_calepinage", "production du "
                                 "calepinage retenu pour votre toiture")))
    elif _num(prod.get("inclinaison_deg")) is not None \
            and _num(prod.get("azimut_deg")) is not None:
        azimut = _num(prod["azimut_deg"])
        orientation = (L("ci_h_plein_sud", "plein sud") if azimut == 0 else
                       L("ci_h_azimut", "azimut {a}° (0° = plein sud)",
                         a=_decimal_txt(azimut)))
        rangees.append((titre, L(
            "ci_h_base_pvgis", "{incl}° d'inclinaison, {orientation}",
            orientation=orientation,
            incl=_decimal_txt(_num(prod["inclinaison_deg"])))))
    rangees += _rangee_methode(estimation, L)
    dim = estimation.get("dimensionnement") or {}
    if _num(dim.get("pas_kwc")) and _num(dim.get("horizon_annees")):
        rangees.append((L("ci_h_dimensionnement", "Règle de dimensionnement"),
                        L("ci_h_regle_taille", "chaque palier de {pas} kWc "
                          "retenu se rembourse en moins de {n} ans",
                          pas=_decimal_txt(_num(dim["pas_kwc"])),
                          n=_decimal_txt(_num(dim["horizon_annees"])))))
    return rangees


def _rangee_methode(estimation, L):
    """AMOT99 (D-ACI-18=a) — la méthode d'autoconsommation retenue par le
    moteur : 8 760 h de l'année type, ou le repli sur journées moyennes."""
    methode = estimation.get("methode_autoconso")
    if methode not in ("horaire_8760", "journees_moyennes"):
        return []
    valeur = (L("ci_h_methode_8760", "autoconsommation calculée heure par "
                "heure sur l'année type (8 760 h)")
              if methode == "horaire_8760" else
              L("ci_h_methode_journees", "autoconsommation : estimation sur "
                "journées moyennes"))
    return [(L("ci_h_methode_autoconso", "Méthode de calcul"), valeur)]


def _rangee_om(argent, fmt_mad, L):
    """AMOT91 — l'entretien (O&M) : « déduit des économies : N MAD/an »
    seulement souscrit et chiffré (CIQ342), sinon « non déduit »
    (accordé à « entretien »)."""
    om = argent.get("om") if isinstance(argent, dict) else None
    # AMOT96 — l'entretien minimum servi : déduit (il remplace la phrase).
    # Décision fondateur 26/10/2026 — « entretien non chiffré » n'est plus
    # imprimé (réserve interne) : avec une option O&M au devis, la rangée dit
    # « non déduit des économies » ; SANS option O&M, aucune rangée (la règle
    # d'hier : aucun mot « O&M » sans option).
    entretien = _ligne_entretien(argent, fmt_mad, L)
    if not isinstance(om, dict) and entretien:
        return [(None, entretien)]
    if not isinstance(om, dict) and isinstance(
            (argent or {}).get("entretien"), dict):
        return []
    om = om if isinstance(om, dict) else {}
    montant = _num(om.get("montant_mad_an"))
    valeur = (L("ci_h_om_deduite", "déduit des économies : {montant} MAD/an",
                montant=fmt_mad(montant))
              if om.get("statut") == "souscrit" and montant else
              L("ci_h_om_non_deduite", "non déduit des économies"))
    if _entretien_deduit(argent):
        valeur = entretien
    elif entretien and om.get("statut") != "souscrit":
        valeur += f" — {entretien}"
    return [(L("ci_h_om", "Entretien (O&amp;M)"), valeur)]


def _entretien_deduit(argent):
    """AMOT96 — le montant annuel de l'entretien minimum DÉDUIT du flux servi
    (``argent.entretien``, réglage société), sinon None."""
    entretien = argent.get("entretien") if isinstance(argent, dict) else None
    entretien = entretien if isinstance(entretien, dict) else {}
    return (_num(entretien.get("montant_mad_an"))
            if entretien.get("statut") == "deduit" else None)


def _ligne_entretien(argent, fmt_mad, L):
    """AMOT96 — « entretien minimum à votre charge (réglage société) : N
    MAD/an, déduit des économies », « entretien non chiffré », ou ''."""
    entretien = argent.get("entretien") if isinstance(argent, dict) else None
    if not isinstance(entretien, dict):
        return ""
    if _entretien_deduit(argent):
        return L("ci_entretien_minimum", "entretien minimum à votre charge "
                 "(réglage société) : {montant} MAD/an, déduit des économies",
                 montant=fmt_mad(_entretien_deduit(argent)))
    # Décision fondateur 26/10/2026 — « entretien non chiffré » (réserve
    # interne) n'est plus imprimé au client.
    return ""


def rangees_hypotheses(d, synthese, fmt, fmt_mad, L, *, compact=False,
                       om=False):
    """AMOT91 — LES hypothèses de l'estimation, ``[(libellé | None, valeur)]``,
    toutes lues sur ``synthese_ci`` (flux servi, valorisation, prix du kWh,
    remplacements, entretien si ``om``, base de production, règle de
    dimensionnement) — UNE source pour la page finance industrielle, la page
    énergie industrielle et le tableau de la page 3 commerciale. ``compact`` :
    sans les montants déjà imprimés ailleurs (investissement, économie et
    production de l'année 1)."""
    argent = (synthese or {}).get("argent") if isinstance(synthese, dict) \
        else None
    argent = argent if isinstance(argent, dict) else {}
    _cle, flux = flux_principal(argent)
    rangees = _rangees_flux(flux, fmt, L, d, compact) + _rangees_argent(
        argent, fmt_mad, L, d)
    if om and argent:
        rangees += _rangee_om(argent, fmt_mad, L)
    return rangees + _rangees_estimation(synthese, L)


def _hypotheses(argent, flux, fmt, fmt_mad, L, d=None):
    """Les hypothèses de l'estimation en lignes « Libellé : valeur — source »
    (page finance industrielle) — aucune n'est écrite ici."""
    synthese = dict((d or {}).get("ind_synthese") or {}, argent=argent)
    return [f"{libelle}&#160;: {valeur}" if libelle and valeur
            else (libelle or valeur)
            for libelle, valeur in rangees_hypotheses(
                d, synthese, fmt, fmt_mad, L,
                # AMOT96 — l'entretien servi (déduit / non chiffré) est dit.
                om=isinstance((argent or {}).get("entretien"), dict))]


def tableau_hypotheses(d, synthese, fmt, fmt_mad, L, prefixe,
                       optionnel=False, **options):
    """AMOT91 — le tableau compact « Hypothèses de l'estimation »
    (``rangees_hypotheses``), ou '' sans aucune hypothèse servie.
    ``optionnel`` : le bloc cède sa place (``data-graphique``, retiré par le
    rendu adaptatif) avant que les conditions ne soient tronquées."""
    rangees = rangees_hypotheses(d, synthese, fmt, fmt_mad, L, **options)
    if not rangees or (optionnel and cede(d, "hypotheses")):
        return ""
    lignes = "".join(
        f'<tr><td class="{prefixe}-hy-l">{libelle or ""}</td>'
        f'<td class="{prefixe}-hy-v">{valeur}</td></tr>'
        for libelle, valeur in rangees)
    marque = ' data-graphique="hypotheses"' if optionnel else ""
    return (f'<div class="{prefixe}-hy"{marque}><div class="{prefixe}-hy-t">'
            f'{L("ci_hypotheses_estimation", TITRE_HYPOTHESES)}</div>'
            f'<table class="{prefixe}-hy-tbl">{lignes}</table></div>')


def css_tableau_hypotheses(prefixe, navy, muted, ink, line_soft):
    """La feuille du tableau compact, une définition par préfixe."""
    return (
        f".{prefixe}-hy{{margin-top:10px;}}"
        f".{prefixe}-hy-t{{font-size:9pt;font-weight:700;color:{navy};}}"
        f".{prefixe}-hy-tbl{{width:100%;border-collapse:collapse;"
        f"margin-top:3px;font-size:7pt;line-height:1.3;}}"
        f".{prefixe}-hy-tbl td{{padding:2px 4px;border-bottom:1px solid "
        f"{line_soft};vertical-align:top;}}"
        f".{prefixe}-hy-l{{color:{muted};width:30%;}}"
        f".{prefixe}-hy-v{{color:{ink};}}")


def _ligne_om(argent, fmt_mad, L):
    """CIQ342 — l'O&M n'est dite DÉDUITE que si l'option est chiffrée
    (``argent.om`` souscrite avec un montant) ; proposée ou à chiffrer ⇒
    « non déduite » ; absente du devis ⇒ rien (D-CIQ-12)."""
    om = argent.get("om") if isinstance(argent, dict) else None
    if not isinstance(om, dict):
        return ""
    montant = _num(om.get("montant_mad_an"))
    if om.get("statut") == "souscrit" and montant:
        return L("ci_ind_om_deduite", "O&amp;M déduite du flux : {montant} MAD/an",
                 montant=fmt_mad(montant))
    if _entretien_deduit(argent):
        return _ligne_entretien(argent, fmt_mad, L)
    if om.get("statut") in ("propose", "tarif_a_renseigner"):
        return L("ci_ind_om_non_deduite",
                 "O&amp;M proposée, non déduite de ces montants")
    return ""


def _ligne_revente(argent, fmt, L, langue):
    """Revente 82-21 (MT seulement) telle que servie : le moteur ne
    l'additionne JAMAIS au flux — elle est dite « hors cashflow », avec sa
    mention (CIQ305). Jamais « le surplus n'est pas rémunéré » à côté."""
    revente = argent.get("revente") if isinstance(argent, dict) else None
    if not isinstance(revente, dict) or revente.get("statut") != "calculee":
        return ""
    valeur = _num(revente.get("valeur_mad_an"))
    if not valeur:
        return ""
    # AMOT40 (C-AMOT-049) — CHAQUE mention servie, dans la langue du
    # document (table trilingue ``ci.mentions``) : plus jamais deux mentions
    # seulement en anglais, « non garanti » compris.
    from ..ci.mentions import mentions_revente
    mentions = mentions_revente(revente.get("mentions"), langue)
    mention = (f' <span class="i2-mini">{" ".join(mentions)}</span>'
               if mentions else "")
    return (f'<div class="i2-inj"><b>+ {fmt(valeur)} '
            f'{L("ci_mad_an", "MAD/an")}</b> — '
            + L("ci_ind_revente_hors_flux",
                "revente du surplus, hors flux annuels (non comptée dans "
                "le délai de retour ni le TRI).")
            + f'{mention}</div>')


def _decimal_txt(valeur):
    """« 0,1221 » — un nombre servi, sans arrondi propre."""
    return decimale(f"{valeur:g}")


def _p90_bancable(d):
    """La P90 du bloc bancable du devis (``etude['bankable']``, PV77 —
    la dispersion du moteur, aucune nouvelle), ou None. Permise sur le PDF,
    jamais dans la charge utile publique (``_sans_internes_bancables``)."""
    bank = (d.get("etude") or {}).get("bankable")
    # AMOT35 — une P90 n'est imprimée que si la simulation décrit le champ
    # VENDU et reste cohérente avec la production imprimée (LA règle
    # partagée avec le legacy, ``bankable.bankable_imprimable``) ; sinon
    # omise, motif dit en interne.
    from ..bankable import bankable_imprimable
    # Décision fondateur 08/10/2026 — devis envoyé avant AMOT35
    # (``regles_calcul_origine``) : la P90 d'hier, sans le nouveau contrôle.
    if bank and not d.get("regles_calcul_origine"):
        ok, motif = bankable_imprimable(
            bank, d.get("ind_kwc") or d.get("puissance_kwc"),
            d.get("ind_prod"))
        if not ok:
            if motif and motif not in (d.get("avertissements_internes") or []):
                d.setdefault("avertissements_internes", []).append(motif)
            return None
    pr = bank.get("pr") if isinstance(bank, dict) else None
    return _num((pr or {}).get("p90_kwh")) if isinstance(pr, dict) else None


def _bloc_cfo(d, argent, base_txt, fmt, fmt_mad, L, couleurs):
    """CIQ343 (D-CIQ-10, D-CIQ-15) — le bloc compact « Indicateurs » sous le
    tableau, lu dans ``synthese_ci['argent']`` : coût du kWh solaire face au
    prix du kWh du client (tous deux servis, avec leur base), VAN SEULEMENT
    sur le taux déclaré par le client (sinon omise avec son motif),
    sensibilités SAISIES par la société (aucune par défaut ; base = 0 %
    d'indexation), P90 du bloc bancable, puis l'offre de financement
    (CIQ318). Aucun nombre calculé ici."""
    navy, ink = couleurs
    indicateurs = argent.get("indicateurs") or {}
    lignes = []
    lcoe = _num(indicateurs.get("lcoe_mad_kwh"))
    from .cover import _taux_declare
    taux = _taux_declare(argent)
    if lcoe is not None:
        lcoe_txt = _decimal_txt(lcoe)
        # AMOT80 — sans taux déclaré, le coût est NON actualisé : dit tel.
        ligne = ((L("ci_ind_lcoe", "Coût du kWh solaire (LCOE, {base})",
                    base=base_txt)
                  if indicateurs.get("lcoe_actualise") or taux is not None else
                  L("ci_ind_lcoe_non_actualise",
                    "Coût moyen non actualisé du kWh produit ({base})",
                    base=base_txt))
                 + f"&#160;: <b>{lcoe_txt}&#160;MAD/kWh</b>"
                 + ancre("lcoe_mad_kwh", lcoe_txt))
        tarif = _num(indicateurs.get("tarif_kwh_evite_moyen"))
        if tarif is not None:
            ligne += (" — " + L("ci_ind_tarif_client",
                               "prix moyen de votre kWh évité : {tarif} "
                               "MAD/kWh", tarif=_decimal_txt(tarif)))
        lignes.append(ligne)
    van = _num(indicateurs.get("van_mad"))
    if van is not None and taux is not None:
        lignes.append(L("ci_ind_van", "VAN au taux déclaré de {taux} %",
                        taux=_decimal_txt(taux))
                      + f"&#160;: <b>{fmt_mad(van)}&#160;MAD</b>")
    else:
        motif = ci_couverture.texte_client(d, indicateurs.get("van_motif"))
        if motif and ci_blocs.langue(d) != "fr":
            # La seule cause d'omission servie : aucun taux déclaré.
            motif = L("ci_ind_van_motif", motif)
        lignes.append(L("ci_ind_van_omise", "VAN non calculée")
                      + (f"&#160;: {motif}" if motif else ""))
    # AMOT97 (D-ACI-15=a) — central + scénarios servis, en tableau.
    sensibilites = _tableau_sensibilites(d, argent, fmt_mad, L)
    p90 = _p90_bancable(d)
    if p90 is not None:
        lignes.append(L("ci_ind_p90",
                        "Production à 90 % de probabilité (P90) : {kwh} kWh/an",
                        kwh=fmt(p90)))
    financement = ci_blocs.bloc_financement(
        d.get("ind_synthese") or {}, "i2", navy, ink, doc=d)
    if not lignes and not financement and not sensibilites:
        return ""
    items = "".join(f'<div class="i2-cfo-i">{li}</div>' for li in lignes)
    return (f'<div class="i2-cfo"><div class="i2-hyp-t">'
            f'{L("ci_ind_indicateurs", "Indicateurs pour votre direction financière")}'
            f'</div>{items}{sensibilites}{financement}</div>')


def _nom_scenario(s, L):
    """« Production -7,7 % » — le nom du paramètre varié (catalogue
    ``ci_ind_sens_<clé>``) et la variation SERVIE."""
    catalogue = _cles_catalogue()
    variation = _num(s.get("variation_pct"))
    cle_sens = f"ci_ind_sens_{s.get('cle')}"
    nom = (L(cle_sens, catalogue[cle_sens]["fr"]) if cle_sens in catalogue
           else ci_blocs._txt(s.get("cle")))
    return (decimale(f"{nom} {variation:+g}&#160;%")
            if variation is not None else nom)


def _tableau_sensibilites(d, argent, fmt_mad, L):
    """AMOT97 (D-ACI-15=a) — le scénario central puis chaque scénario servi
    (``argent.sensibilites``) : délai de retour, TRI, cumul net de la dernière
    année du flux et la source, TELS QUE servis par ``economie_ci`` (aucun
    recalcul) ; '' sans scénario. Cède sa place avec les hypothèses."""
    scenarios = [s for s in argent.get("sensibilites") or []
                 if isinstance(s, dict)]
    if not scenarios or cede(d, "hypotheses"):
        return ""
    indicateurs = argent.get("indicateurs") or {}
    flux = [f for f in flux_principal(argent)[1].get("flux") or []
            if isinstance(f, dict)]
    rangees = [(L("ci_sens_central", "Scénario central"),
                indicateurs.get("retour_ans"), indicateurs.get("tri_pct"),
                (flux[-1] if flux else {}).get("cumul_mad"), "")]
    rangees += [(_nom_scenario(s, L), s.get("retour_ans"), s.get("tri_pct"),
                 s.get("cumul_25_ans_mad"), ci_couverture.texte_client(
                     d, s.get("motif") if s.get("motif") and s.get(
                         "retour_ans") is None else s.get("source")))
                for s in scenarios]

    unite_ans = L("ci_unite_ans", "&nbsp;ans")
    formats = (lambda v: ci_couverture.ans(v) + unite_ans,
               lambda v: decimale(f"{v:.1f}") + "&#160;%",
               lambda v: fmt_mad(v) + "&#160;MAD")
    lignes = ""
    for nom, *valeurs, source in rangees:
        cellules = "".join(
            f'<td class="i2-n">{f(_num(v)) if _num(v) is not None else "—"}'
            '</td>' for f, v in zip(formats, valeurs))
        lignes += (f'<tr><td>{nom}</td>{cellules}'
                   f'<td class="i2-mini">{source}</td></tr>')
    entete = "".join(f"<th>{x}</th>" for x in (
        L("ci_sens_scenario", "Scénario"),
        L("ci_ind_delai_retour", "Délai de retour"),
        L("ci_ind_tri_sur", "TRI sur {n} ans", n="25"),
        L("ci_sens_cumul", "Cumul net sur {n} ans", n="25"),
        L("ci_source", "Source")))
    base = L("ci_ind_sens_base", "Sensibilités saisies par la société ; "
             "base : 0 % d'indexation du tarif.")
    return (f'<table class="i2-tbl i2-fx"><tr>{entete}</tr>{lignes}</table>'
            f'<div class="i2-cfo-i">{base}</div>')


def _cles_catalogue():
    from .. import i18n_labels
    return i18n_labels.LIBELLES


def _pied_investissement(d, argent, fmt_mad, L):
    """CIQ315 — l'investissement du pied de page sur la base SERVIE."""
    base = argent.get("base") if isinstance(argent, dict) else None
    ht = (d.get("totaux_all") or {}).get("ht_net")
    ttc = d.get("_invest_ttc") or 0
    l_ht, l_ttc = L("ci_ht", "HT"), L("ci_ttc", "TTC")
    # AMOT86 — jamais « clé en main » quand des postes sont hors total.
    synthese = d.get("ind_synthese")
    if base == "ht" and ht is not None:
        # Le titre dit déjà « HT » : le montant ne le répète pas.
        return (ci_couverture.titre_investissement(d, synthese, "ht")
                + f" : <b>{fmt_mad(ht)} MAD</b>")
    if base == "deux" and ht is not None:
        return (ci_couverture.titre_investissement(d, synthese, "deux")
                + f" : <b>{fmt_mad(ttc)} MAD {l_ttc}</b> "
                  f"({L('ci_soit', 'soit')} {fmt_mad(ht)} MAD {l_ht})")
    return (ci_couverture.titre_investissement(d, synthese, "ttc")
            + f" : <b>{fmt_mad(ttc)} MAD</b>")


def _motif_non_chiffre(d, L):
    """``(texte, ligne de motif)`` quand la rentabilité n'est pas chiffrée.
    QJR119 / QXMT — jamais une table de zéros ; CIQ341 — un site MT demande
    ses 12 factures MT ; AMOT80 (D-ACI-8=a) — investissement non chiffré ⇒
    SON motif, jamais « économies pas encore calculées »."""
    motif = ci_couverture.ligne_non_chiffre(d, "ind", "i2")
    motif_inv = ci_couverture.motif_investissement(d, "ind")
    if motif_inv:
        return L("ci_ind_motif_invest_client",
                 "<b>{motif}</b> : le délai de retour, le TRI et les flux "
                 "annuels ne sont publiés que sur un investissement "
                 "entièrement chiffré.", motif=motif_inv), ""
    if ci_couverture._argent_mt(d, "ind"):
        return L(
            "ci_ind_motif_mt",
            "Votre installation est raccordée en <b>MOYENNE TENSION</b> : "
            "ses économies se chiffrent sur le barème MT par poste "
            "horaire, pas sur le barème basse tension. Nous préférons ne "
            "rien afficher plutôt qu'un chiffre qui n'est pas le vôtre."), \
            motif
    return L("ci_ind_motif_bt_client",
             "Les <b>économies annuelles</b> de cette installation n'ont "
             "pas encore été calculées sur vos données. Nous préférons ne "
             "rien afficher plutôt que des flux annuels, un point mort ou "
             "un TRI qui ne reposeraient sur aucune mesure."), motif


def _corps_non_chiffre(d, L, pied, couleurs_gr, police, fmt, fmt_mad):
    """``(corps, chapeau, titre)`` de la page 3 quand la rentabilité n'est pas
    chiffrable. AMOT90 — la page n'est plus une page blanche « Rentabilité non
    chiffrée » : quand le bilan horaire est servi, elle porte l'analyse
    énergétique (l'énergie mois par mois, le surplus) sous une petite ligne
    de motif ; sans bilan, l'encadré d'hier."""
    corps_txt, motif = _motif_non_chiffre(d, L)
    chapeau = L("ci_ind_lead_non_chiffre",
                "Aucune rentabilité n'est publiée tant qu'elle n'est pas "
                "calculée sur vos données.")
    graphique = bloc_energie_mensuelle(
        d, d.get("ind_synthese"), couleurs_gr, police, fmt, "i2",
        hauteur=170, largeur_mm=182)
    if not graphique:
        return (f"""
  <div class="i2-mt">
    <div class="i2-mt-t">{L("ci_ind_non_chiffre_titre", "Rentabilité non chiffrée sur ce dossier")}</div>
    <div class="i2-mt-b">{corps_txt}</div>
    {motif}
  </div>
  <div class="i2-foot">{pied}.</div>""", chapeau, "")
    titre = L("ci_ind_energie_titre", "Ce que la centrale produit pour "
              "votre site")
    return (f"""
  <div class="i2-motif">{corps_txt}{motif}</div>
  {graphique}
  {ci_couverture.ligne_surplus(d, "ind", "i2")}
  {tableau_hypotheses(d, d.get("ind_synthese"), fmt, fmt_mad, L, "i2", compact=True, om=True)}
  <div class="i2-foot">{pied}.</div>""", chapeau, titre)


def build(ctx):
    d = ctx["d"]
    # CIQ345 — libellés STRUCTURELS dans la langue du document.
    L = partial(ci_blocs.libelle, d)
    C = ctx["C"]
    fmt = ctx["fmt"]
    fmt_mad = ctx.get("fmt_mad") or fmt
    fonts = ctx["fonts"]

    navy, gold, green, green_bg, ink, muted, muted_2, line, line_soft, wash, blue = premium_base.couleurs(
        C, "navy gold green green_bg ink muted muted_2 line line_soft wash blue")

    f_display, f_serif, f_sans = premium_base.polices(fonts)

    synthese = d.get("ind_synthese") or {}
    argent = synthese.get("argent") if isinstance(synthese, dict) else None
    argent = argent if isinstance(argent, dict) else {}
    _cle, flux = flux_principal(argent)
    lignes_flux = [f for f in flux.get("flux") or [] if isinstance(f, dict)]
    indicateurs = argent.get("indicateurs") or {}
    horizon = _num(indicateurs.get("tri_horizon_ans")) or \
        _num(flux.get("horizon_ans"))
    chiffrable = (bool(lignes_flux) and not d.get("ind_masquer_economies")
                  and horizon is not None)
    horizon_txt = f"{horizon:g}" if horizon else "25"
    base_txt = {"ttc": L("ci_ttc", "TTC")}.get(argent.get("base"),
                                               L("ci_ht", "HT"))

    css = f"""
<style>
.i2-root{{font-family:{f_sans};color:{ink};width:210mm;min-height:283mm;
  padding:13mm 14mm 0 14mm;background:#fff;}}
.i2-root *{{box-sizing:border-box;}}
.i2-kicker{{font-size:7.5pt;letter-spacing:2.4px;text-transform:uppercase;
  color:{muted_2};font-weight:700;}}
.i2-sec{{font-family:{f_serif};font-weight:700;font-size:16pt;color:{navy};margin-top:2px;}}
.i2-lead{{font-size:8.5pt;color:{muted};margin-top:4px;}}
.i2-kpis{{width:100%;margin-top:10px;border-spacing:0;border-collapse:separate;}}
.i2-kpi{{vertical-align:top;border:1px solid {line};border-left:4px solid {gold};
  border-radius:12px;padding:11px 14px;background:#fff;}}
.i2-kgap{{width:12px;}}
.i2-kv{{font-family:{f_display};font-size:19pt;color:{navy};line-height:1;}}
.i2-kl{{font-size:7.5pt;color:{muted};margin-top:4px;}}
.i2-inj{{margin-top:10px;border:1px solid {green_bg};border-left:4px solid {green};
  border-radius:12px;background:{green_bg};padding:8px 14px;font-size:8pt;color:{ink};}}
.i2-inj b{{color:{green};}}
.i2-mini{{color:{muted};font-size:7pt;}}
.i2-cfhead{{margin-top:12px;font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};}}
.i2-tbl{{width:100%;border-collapse:collapse;margin-top:6px;font-size:8pt;}}
.i2-tbl th{{text-align:left;color:{muted};font-size:7pt;text-transform:uppercase;
  letter-spacing:.4px;padding:5px 8px;border-bottom:1px solid {line};}}
.i2-tbl th.i2-r,.i2-tbl td.i2-c{{text-align:right;}}
.i2-tbl td{{padding:4px 8px;border-bottom:1px solid {line_soft};}}
.i2-c{{font-weight:700;}}
.i2-fx{{margin-top:4px;font-size:6.3pt;line-height:1.05;}}
.i2-fx th{{font-size:5.8pt;padding:2px 5px;}}
.i2-fx td{{padding:0.4px 5px;border-bottom:none;}}
.i2-fx tr:nth-child(even) td{{background:{wash};}}
.i2-n{{text-align:right;white-space:nowrap;}}
.i2-fx td.i2-c{{text-align:right;white-space:nowrap;}}
.i2-pos{{color:{green};}}
.i2-neg{{color:{muted_2};}}
.i2-courbe{{width:100%;border-collapse:collapse;margin-top:8px;table-layout:fixed;}}
.i2-cb{{height:18mm;vertical-align:bottom;padding:0 1px;}}
.i2-ct{{height:7mm;vertical-align:top;padding:0 1px;}}
.i2-axe td{{border-top:1px solid {muted_2};}}
.i2-bp{{background:{green};border-radius:2px 2px 0 0;}}
.i2-bn{{background:{muted_2};border-radius:0 0 2px 2px;max-height:7mm;}}
.i2-ca{{font-size:6pt;color:{muted};text-align:center;}}
.i2-foot{{margin-top:9px;font-size:7.5pt;color:{muted};line-height:1.4;}}
.i2-foot b{{color:{navy};}}
.i2-mt{{margin-top:13px;border:1px solid {line};border-left:4px solid {gold};
  border-radius:12px;background:{wash};padding:13px 16px;}}
.i2-mt-t{{font-family:{f_serif};font-weight:700;font-size:12pt;color:{navy};}}
.i2-mt-b{{margin-top:6px;font-size:8.5pt;color:{ink};line-height:1.45;}}
.i2-mt-b b{{color:{navy};}}
.i2-cfo{{margin-top:8px;border:1px solid {line};border-left:4px solid {navy};
  border-radius:10px;padding:7px 12px;}}
.i2-cfo-i{{font-size:7.5pt;color:{ink};line-height:1.35;margin-top:2px;}}
.i2-cfo .i2-fin{{margin-top:5px !important;font-size:7.5pt !important;}}
.i2-hyp{{margin-top:8px;border:1px solid {line_soft};border-radius:10px;
  background:{wash};padding:8px 12px;}}
.i2-hyp-t{{font-size:8pt;font-weight:700;color:{navy};}}
.i2-hyp-c{{column-count:2;column-gap:14px;}}
.i2-hyp-i{{font-size:6.6pt;color:{muted};line-height:1.25;margin-top:2px;
  padding-left:10px;position:relative;break-inside:avoid;}}
.i2-hyp-i:before{{content:'';position:absolute;left:0;top:4px;width:4px;
  height:4px;border-radius:50%;background:{blue};}}
.i2-motif{{margin-top:6px;font-size:7.5pt;color:{muted};line-height:1.4;}}
.i2-motif b{{color:{navy};}}
.i2-mtsrc{{margin-top:4px;font-size:7pt;color:{muted};line-height:1.35;}}
{css_graphique("i2", navy, muted)}
{css_tableau_hypotheses("i2", navy, muted, ink, line_soft)}
</style>
"""

    pied = _pied_investissement(d, argent, fmt_mad, L)
    # AMOT90 — l'énergie mois par mois (kWh du bilan horaire servi).
    couleurs_gr = (navy, green, gold, line, muted)
    if not chiffrable:
        corps, lead_txt, titre = _corps_non_chiffre(
            d, L, pied, couleurs_gr, f_sans, fmt, fmt_mad)
    else:
        economie = d.get("ind_economies")
        base_eco = d.get("ind_economie_base")
        if base_eco in ("HT", "TTC"):
            base_eco = L(f"ci_{base_eco.lower()}", base_eco)
        payback = _num(indicateurs.get("retour_ans"))
        tri = _num(indicateurs.get("tri_pct"))
        tri_txt = decimale(f"{tri:.1f}") if tri is not None else None

        def kpi(valeur, unite, libelle, cle_fig=None, texte_fig=None):
            a = ancre(cle_fig, texte_fig) if cle_fig else ""
            return (f'<td class="i2-kpi"><div class="i2-kv">{valeur}'
                    f'<span class="i2-kl">{unite}</span></div>{a}'
                    f'<div class="i2-kl">{libelle}</div></td>')

        cellules = []
        if economie is not None:
            cellules.append(kpi(
                fmt(economie), "&nbsp;MAD",
                L("ci_ind_economie_an1", "Économie de l'année 1")
                + (f" ({base_eco})" if base_eco else "")
                + (f" — {ci_couverture.economie_ttc(d, 'ind', fmt)}"
                   if ci_couverture.economie_ttc(d, "ind", fmt) else ""),
                "economie_annuelle", fmt(economie)))
        if payback is not None:
            cellules.append(kpi(
                ci_couverture.ans(payback), L("ci_unite_ans", "&nbsp;ans"),
                L("ci_ind_delai_retour", "Délai de retour"),
                "payback_ans", ci_couverture.ans(payback)))
        if tri_txt is not None:
            cellules.append(kpi(
                tri_txt, "&nbsp;%",
                L("ci_ind_tri_sur", "TRI sur {n} ans", n=horizon_txt),
                "tri_pct", tri_txt))
        kpis = ('<table class="i2-kpis"><tr>'
                + '<td class="i2-kgap"></td>'.join(cellules)
                + '</tr></table>') if cellules else ""

        # AMOT94 — le tableau des 25 ans (flux servi, ligne par ligne) à la
        # place des 5 jalons ; la courbe du cumul cède sa place si la page
        # déborde (le tableau porte déjà le cumul).
        table = _tableau_flux(argent, lignes_flux, fmt, fmt_mad, L, base_txt)
        courbe = ("" if cede(d, "courbe_cumul") else
                  '<div data-graphique="courbe_cumul">'
                  + _courbe(lignes_flux, None) + "</div>")
        lignes_hyp = _hypotheses(argent, flux, fmt, fmt_mad, L, d)
        cfo_html = _bloc_cfo(d, argent, base_txt, fmt, fmt_mad, L,
                             (navy, ink))
        # AMOT94 — cédable (``data-graphique="hypotheses"``) APRÈS les deux
        # dessins de la page (``commercial.equip.ORDRE_CEDABLES``) : jamais
        # une 5ᵉ page ni un texte sous le pied.
        hypotheses_html = (
            f'<div class="i2-hyp" data-graphique="hypotheses">'
            f'<div class="i2-hyp-t">'
            f'{L("ci_hypotheses_estimation", TITRE_HYPOTHESES)}</div>'
            # AMOT94 — sur deux colonnes : le tableau des 25 ans tient.
            + '<div class="i2-hyp-c">'
            + "".join(f'<div class="i2-hyp-i">{h}</div>' for h in lignes_hyp)
            + '</div></div>') if lignes_hyp and not cede(d, "hypotheses")             else ""
        om_txt = _ligne_om(argent, fmt_mad, L)
        revente_html = _ligne_revente(argent, fmt, L, ci_blocs.langue(d))
        mt_source = (f'<br><span class="i2-mini">{d["ind_mt_mention"]}</span>'
                     if d.get("ind_mt_mention") else "")
        corps = f"""
  {kpis}
  {revente_html}
  <div class="i2-cfhead">{L("ci_ind_cumul_titre", "Cumul net de l'investissement ({base})", base=base_txt)}</div>
  {courbe}
  {table}
  {cfo_html}
  {hypotheses_html}
  {bloc_energie_mensuelle(d, synthese, couleurs_gr, f_sans, fmt, "i2", hauteur=90, largeur_mm=182)}
  <div class="i2-foot">
    {(om_txt + '. ') if om_txt else ''}{pied}.
    {L("ci_ind_methode_tri_client", "TRI et délai de retour calculés sur ces flux annuels (méthode actuarielle).")}
    {mt_source}
  </div>"""
        lead_txt = L("ci_ind_lead_client",
                     "Projection sur {n} ans : flux annuels, délai de retour "
                     "et TRI tirés de la même série ; hypothèses détaillées "
                     "ci-dessous.", n=horizon_txt)
        titre = L("ci_ind_rentabilite_sur", "Rentabilité sur {n} ans",
                  n=horizon_txt)

    html = f"""{css}
<div class="i2-root">
  <div class="i2-kicker">{L("ci_ind_analyse_financiere", "Analyse financière")}</div>
  {f'<div class="i2-sec">{titre}</div>' if titre else ""}
  <div class="i2-lead">{lead_txt}</div>
{corps}
</div>
"""
    return html
