"""AMOT90 — graphiques SVG EN LIGNE des documents commercial et industriel.

Le SVG est écrit ici en Python, sans bibliothèque : WeasyPrint le rend comme
un dessin vectoriel. Chaque nombre DESSINÉ vient des données servies
(``synthese_ci['energie']['par_mois']`` — les kWh mensuels du bilan horaire
du moteur C&I, recopiés par ``ci.synthese._par_mois``) ; la seule opération
est la mise à l'échelle des hauteurs de barres. Aucun nombre IMPRIMÉ n'est
calculé ici : la graduation haute est le plus grand kWh servi, recopié.

Garde de mise en page : le bloc porte ``data-graphique`` — le rendu adaptatif
(``commercial.equip.pdf_adaptatif``) le retire (``_sans_graphiques``) si une
page déborde : jamais une page de plus, jamais un texte coupé. Rendu seul,
aucun statut touché (règle #4).
"""
from __future__ import annotations

from .blocs import langue, libelle

#: Repères de l'axe des mois : initiales (fr/en), numéros (ar).
REPERES_MOIS = {"fr": "JFMAMJJASOND", "en": "JFMAMJJASOND"}
#: Largeur du ``viewBox`` et marges (unités du dessin).
LARGEUR = 520
MARGE_G, MARGE_D, MARGE_H, MARGE_B = 6, 6, 16, 16


def cede(d, nom):
    """Le bloc cédable ``nom`` (son ``data-graphique``) est-il retiré par le
    rendu adaptatif ? ``d['_sans_graphiques']`` : ``True`` (tous) ou
    l'ensemble des noms posés sur les pages qui débordaient."""
    retires = d.get("_sans_graphiques") if isinstance(d, dict) else None
    if retires is True:
        return True
    return isinstance(retires, (set, frozenset, list, tuple)) \
        and nom in retires


def _rect(x, y, largeur, hauteur, couleur):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{largeur:.1f}" '
            f'height="{max(hauteur, 0):.1f}" fill="{couleur}"/>')


def svg_barres_mensuelles(mois, couleurs, police, reperes, graduation,
                          hauteur=150, largeur_mm=118):
    """Le ``<svg>`` des 12 mois : pour chaque mois, une barre CONSOMMATION
    et une barre PRODUCTION empilée (autoconsommée en bas, surplus en
    haut). ``couleurs`` = (consommation, autoconsommée, surplus, axe,
    texte) ; ``graduation`` = le texte déjà formaté du plus grand kWh ;
    ``hauteur`` = hauteur du ``viewBox`` (la largeur est fixe) ; le dessin
    mesure ``largeur_mm`` de large et garde ses proportions."""
    conso_c, auto_c, surplus_c, axe_c, texte_c = couleurs
    plafond = max(max(m["consommation_kwh"], m["production_kwh"])
                  for m in mois) or 1
    zone_h = hauteur - MARGE_H - MARGE_B
    pas = (LARGEUR - MARGE_G - MARGE_D) / 12.0
    barre = pas * 0.34
    base_y = hauteur - MARGE_B
    formes = [
        f'<line x1="{MARGE_G}" y1="{MARGE_H}" x2="{LARGEUR - MARGE_D}" '
        f'y2="{MARGE_H}" stroke="{axe_c}" stroke-width="0.6" '
        f'stroke-dasharray="3 3"/>',
        f'<text x="{MARGE_G}" y="{MARGE_H - 4}" font-size="9" '
        f'fill="{texte_c}">{graduation}</text>',
    ]
    for i, m in enumerate(mois):
        x0 = MARGE_G + i * pas + (pas - 2 * barre - 2) / 2
        h_conso = m["consommation_kwh"] / plafond * zone_h
        h_auto = m["autoconso_kwh"] / plafond * zone_h
        h_surplus = m["surplus_kwh"] / plafond * zone_h
        x1 = x0 + barre + 2
        formes += [
            _rect(x0, base_y - h_conso, barre, h_conso, conso_c),
            _rect(x1, base_y - h_auto, barre, h_auto, auto_c),
            _rect(x1, base_y - h_auto - h_surplus, barre, h_surplus,
                  surplus_c),
            f'<text x="{MARGE_G + i * pas + pas / 2:.1f}" y="{hauteur - 3}" '
            f'font-size="9" text-anchor="middle" fill="{texte_c}">'
            f'{reperes[i]}</text>',
        ]
    formes.append(
        f'<line x1="{MARGE_G}" y1="{base_y}" x2="{LARGEUR - MARGE_D}" '
        f'y2="{base_y}" stroke="{axe_c}" stroke-width="0.8"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {LARGEUR} {hauteur}" '
            f'style="width:{largeur_mm:g}mm;'
            f'height:{largeur_mm * hauteur / LARGEUR:.1f}mm;'
            f'font-family:{police};display:block;">'
            + "".join(formes) + "</svg>")


def svg_barres_mensuelles_deux(mois, mois_avec, couleurs, couleurs_avec,
                               police, reperes, graduation, hauteur=150,
                               largeur_mm=118):
    """Lead nada (13/11/2026) — deux options : pour chaque mois, la barre
    CONSOMMATION puis la production empilée (autoconsommée / surplus) SANS
    batterie, puis la même AVEC batterie (bilan de l'option). Mêmes règles
    que :func:`svg_barres_mensuelles` : seules les hauteurs sont mises à
    l'échelle, aucun nombre imprimé n'est calculé."""
    conso_c, auto_c, surplus_c, axe_c, texte_c = couleurs
    auto_a, surplus_a = couleurs_avec
    plafond = max(max(m["consommation_kwh"], m["production_kwh"], a["production_kwh"])
                  for m, a in zip(mois, mois_avec)) or 1
    zone_h = hauteur - MARGE_H - MARGE_B
    pas = (LARGEUR - MARGE_G - MARGE_D) / 12.0
    barre = pas * 0.26
    base_y = hauteur - MARGE_B
    formes = [
        f'<line x1="{MARGE_G}" y1="{MARGE_H}" x2="{LARGEUR - MARGE_D}" '
        f'y2="{MARGE_H}" stroke="{axe_c}" stroke-width="0.6" '
        f'stroke-dasharray="3 3"/>',
        f'<text x="{MARGE_G}" y="{MARGE_H - 4}" font-size="9" '
        f'fill="{texte_c}">{graduation}</text>',
    ]
    for i, (m, a) in enumerate(zip(mois, mois_avec)):
        x0 = MARGE_G + i * pas + (pas - 3 * barre - 4) / 2
        x1, x2 = x0 + barre + 2, x0 + 2 * barre + 4
        h = {cle: v / plafond * zone_h for cle, v in m.items() if cle != "mois"}
        ha = {cle: v / plafond * zone_h for cle, v in a.items() if cle != "mois"}
        formes += [
            _rect(x0, base_y - h["consommation_kwh"], barre, h["consommation_kwh"], conso_c),
            _rect(x1, base_y - h["autoconso_kwh"], barre, h["autoconso_kwh"], auto_c),
            _rect(x1, base_y - h["autoconso_kwh"] - h["surplus_kwh"], barre,
                  h["surplus_kwh"], surplus_c),
            _rect(x2, base_y - ha["autoconso_kwh"], barre, ha["autoconso_kwh"], auto_a),
            _rect(x2, base_y - ha["autoconso_kwh"] - ha["surplus_kwh"], barre,
                  ha["surplus_kwh"], surplus_a),
            f'<text x="{MARGE_G + i * pas + pas / 2:.1f}" y="{hauteur - 3}" '
            f'font-size="9" text-anchor="middle" fill="{texte_c}">'
            f'{reperes[i]}</text>',
        ]
    formes.append(
        f'<line x1="{MARGE_G}" y1="{base_y}" x2="{LARGEUR - MARGE_D}" '
        f'y2="{base_y}" stroke="{axe_c}" stroke-width="0.8"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {LARGEUR} {hauteur}" '
            f'style="width:{largeur_mm:g}mm;'
            f'height:{largeur_mm * hauteur / LARGEUR:.1f}mm;'
            f'font-family:{police};display:block;">'
            + "".join(formes) + "</svg>")


def mois_option_avec(d):
    """Les 12 mois du bilan de l'option « avec batterie »
    (``etude.etude_ci.option_avec.bilan``, recopiés par ``synthese._par_mois``)
    ou None — lu comme ``mentions.valeur_option_avec`` lit l'option."""
    from .synthese import _par_mois  # paresseux : synthese importe beaucoup
    etude = d.get("etude") if isinstance(d, dict) else None
    etude_ci = (etude or {}).get("etude_ci") if isinstance(etude, dict) else None
    avec = (etude_ci or {}).get("option_avec") if isinstance(etude_ci, dict) else None
    bilan = (avec or {}).get("bilan") if isinstance(avec, dict) else None
    return _par_mois(bilan) if isinstance(bilan, dict) else None


def _pastille(couleur, texte):
    return (f'<span style="display:inline-block;width:7px;height:7px;'
            f'border-radius:2px;background:{couleur};margin:0 3px 0 8px;'
            f'vertical-align:middle;"></span>{texte}')


def mois_servis(synthese):
    """Les 12 mois servis (``synthese['energie']['par_mois']``), ou None."""
    energie = (synthese or {}).get("energie") if isinstance(synthese, dict) \
        else None
    mois = (energie or {}).get("par_mois") if isinstance(energie, dict) \
        else None
    return mois if isinstance(mois, list) and len(mois) == 12 else None


def bloc_energie_mensuelle(d, synthese, couleurs, police, fmt, prefixe,
                           hauteur=150, largeur_mm=118, couleurs_avec=None):
    """AMOT90 — le bloc « Votre énergie mois par mois » : titre, barres
    mensuelles et légende sur deux lignes, lus sur
    ``synthese['energie']['par_mois']`` ; '' quand les 12 mois ne sont pas
    servis, ou quand le rendu adaptatif l'a retiré (``_sans_graphiques``).

    ``couleurs_avec`` = (autoconsommée, surplus) de l'option « avec
    batterie » : donné ET les 12 mois de l'option servis ⇒ les deux options
    côte à côte, nommées (lead nada, 13/11/2026)."""
    mois = mois_servis(synthese)
    if mois is None or cede(d, "energie_mensuelle"):
        return ""
    reperes = REPERES_MOIS.get(langue(d)) or [str(i) for i in range(1, 13)]
    mois_avec = mois_option_avec(d) if couleurs_avec else None
    if mois_avec is not None:
        return _bloc_energie_deux(d, mois, mois_avec, couleurs, couleurs_avec,
                                  police, fmt, prefixe, reperes, hauteur,
                                  largeur_mm)
    plafond = max(max(m["consommation_kwh"], m["production_kwh"])
                  for m in mois)
    conso_c, auto_c, surplus_c, _axe, _texte = couleurs
    svg = svg_barres_mensuelles(mois, couleurs, police, reperes,
                                f"{fmt(round(plafond))} kWh", hauteur,
                                largeur_mm)
    legende = (
        _pastille(conso_c, libelle(d, "ci_gr_consommation",
                                   "Votre consommation"))
        + _pastille(auto_c, libelle(d, "ci_gr_autoconsommee",
                                    "Production autoconsommée"))
        + _pastille(surplus_c, libelle(d, "ci_gr_surplus",
                                       "Surplus non consommé sur place")))
    return (
        f'<div class="{prefixe}-gr" data-graphique="energie_mensuelle">'
        f'<div class="{prefixe}-gr-t">'
        + libelle(d, "ci_gr_titre", "Votre énergie mois par mois")
        + f'</div>{svg}<div class="{prefixe}-gr-l">{legende}</div>'
        f'<div class="{prefixe}-gr-l">'
        + libelle(d, "ci_gr_note", "kWh par mois : votre consommation et la "
                  "production estimée de la centrale, calculées heure par "
                  "heure.")
        + '</div></div>')


def _bloc_energie_deux(d, mois, mois_avec, couleurs, couleurs_avec, police,
                       fmt, prefixe, reperes, hauteur, largeur_mm):
    plafond = max(max(m["consommation_kwh"], m["production_kwh"], a["production_kwh"])
                  for m, a in zip(mois, mois_avec))
    conso_c, auto_c, surplus_c, _axe, _texte = couleurs
    auto_a, surplus_a = couleurs_avec
    svg = svg_barres_mensuelles_deux(mois, mois_avec, couleurs, couleurs_avec,
                                     police, reperes,
                                     f"{fmt(round(plafond))} kWh", hauteur,
                                     largeur_mm)
    sans = libelle(d, "ci_opt_sans_batterie", "Sans batterie")
    avec = libelle(d, "ci_opt_avec_batterie", "Avec batterie")
    sur_place = libelle(d, "ci_gr_sur_place", "consommé sur place")
    surplus = libelle(d, "ci_gr_surplus_court", "surplus")
    legende = (
        _pastille(conso_c, libelle(d, "ci_gr_consommation", "Votre consommation"))
        + "<br>" + f"<b>{sans}</b> :" + _pastille(auto_c, sur_place)
        + _pastille(surplus_c, surplus)
        + "<br>" + f"<b>{avec}</b> :" + _pastille(auto_a, sur_place)
        + _pastille(surplus_a, surplus))
    return (
        f'<div class="{prefixe}-gr" data-graphique="energie_mensuelle">'
        f'<div class="{prefixe}-gr-t">'
        + libelle(d, "ci_gr_titre", "Votre énergie mois par mois")
        + f'</div>{svg}<div class="{prefixe}-gr-l">{legende}</div>'
        f'<div class="{prefixe}-gr-l">'
        + libelle(d, "ci_gr_note_deux", "kWh par mois, sans et avec batterie : "
                  "votre consommation et la production estimée, calculées "
                  "heure par heure.")
        + '</div></div>')


def courbes_retour(d, cle):
    """Lead nada (13/11/2026) — ``(base, [(option, retour, flux)])`` des
    courbes de retour de la couverture ``cle`` : le flux de l'offre servie
    (``synthese.argent``, base principale : ``flux_ttc`` en base « ttc »,
    ``flux_ht`` sinon) et, document à deux options, celui de l'option
    « avec batterie » sur la MÊME base (``option_avec.economie_flux``).
    Chaque point est un ``cumul_mad`` SERVI ; chaque retour celui des
    cartes. ``None`` quand aucun flux n'est servi ou les économies sont
    masquées."""
    from . import couverture
    from .options_cote import deux_options
    from ..lecture_pure import nombre_ou_none
    if d.get(f"{cle}_masquer_economies"):
        return None
    argent = (d.get(f"{cle}_synthese") or {}).get("argent")
    if not isinstance(argent, dict):
        return None
    base = "ttc" if argent.get("base") == "ttc" else "ht"
    cle_flux = f"flux_{base}"

    def points(bloc):
        flux = (bloc or {}).get("flux") if isinstance(bloc, dict) else None
        pts = [(nombre_ou_none(f.get("annee")), nombre_ou_none(f.get("cumul_mad")))
               for f in flux or [] if isinstance(f, dict)]
        pts = [(a, c) for a, c in pts if a is not None and c is not None]
        return pts if len(pts) >= 2 else None

    sans = points(argent.get(cle_flux))
    if sans is None:
        return None
    if not deux_options(d, cle):
        return base, [(None, couverture.retour_affiche(d, cle), sans)]
    etude_ci = ((d.get("etude") or {}).get("etude_ci") or {})
    avec_bloc = (etude_ci.get("option_avec") or {}) if isinstance(etude_ci, dict) else {}
    avec = points((avec_bloc.get("economie_flux") or {}).get(cle_flux))
    option = ((d.get(f"{cle}_synthese") or {}).get("option_batterie") or {})
    valeur = option.get("valeur_chiffree") if isinstance(option.get("valeur_chiffree"), dict) else {}
    courbes = [("sans", couverture.retour_affiche(d, cle), sans)]
    if avec is not None:
        courbes.append(("avec", nombre_ou_none(valeur.get("retour_simple_ans")), avec))
    return base, courbes


def svg_cumul(courbes, couleurs, axe_c, texte_c, police, fmt_mad,
              hauteur=200, largeur_mm=76):
    """Le ``<svg>`` du cumul net année par année, une ligne par option.
    Seules les positions sont mises à l'échelle ; les deux montants imprimés
    (haut et bas de l'axe) sont des ``cumul_mad`` servis, recopiés."""
    tous = [p for _o, _r, pts in courbes for p in pts]
    a_max = max(a for a, _c in tous) or 1
    c_max = max(max(c for _a, c in tous), 0.0)
    c_min = min(min(c for _a, c in tous), 0.0)
    etendue = (c_max - c_min) or 1.0
    # Marge gauche large : les montants de l'axe (« -384 300 MAD ») tiennent.
    g, dr, h, b = 112, 8, 14, 18
    zone_w, zone_h = LARGEUR - g - dr, hauteur - h - b

    def x(a):
        return g + a / a_max * zone_w

    def y(c):
        return h + (c_max - c) / etendue * zone_h

    formes = [
        f'<line x1="{g}" y1="{y(0):.1f}" x2="{LARGEUR - dr}" y2="{y(0):.1f}" '
        f'stroke="{axe_c}" stroke-width="1"/>',
        f'<text x="{g - 4}" y="{y(c_max) + 3:.1f}" font-size="11" '
        f'text-anchor="end" fill="{texte_c}">{fmt_mad(round(c_max))}</text>',
        f'<text x="{g - 4}" y="{y(c_min) + 3:.1f}" font-size="11" '
        f'text-anchor="end" fill="{texte_c}">{fmt_mad(round(c_min))}</text>',
        f'<text x="{g - 4}" y="{y(0) + 3:.1f}" font-size="11" '
        f'text-anchor="end" fill="{texte_c}">0</text>',
    ]
    for annee in range(0, int(a_max) + 1, 5):
        formes.append(
            f'<text x="{x(annee):.1f}" y="{hauteur - 4}" font-size="11" '
            f'text-anchor="middle" fill="{texte_c}">{annee}</text>')
    for (_o, _r, pts), couleur in zip(courbes, couleurs):
        trace = " ".join(f"{x(a):.1f},{y(c):.1f}" for a, c in pts)
        formes.append(f'<polyline points="{trace}" fill="none" '
                      f'stroke="{couleur}" stroke-width="2.4" '
                      f'stroke-linejoin="round"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {LARGEUR} {hauteur}" '
            f'style="width:{largeur_mm:g}mm;'
            f'height:{largeur_mm * hauteur / LARGEUR:.1f}mm;'
            f'font-family:{police};display:block;">'
            + "".join(formes) + "</svg>")


def bloc_retour_cumul(d, cle, couleurs, axe_c, texte_c, police, fmt_mad,
                      prefixe, hauteur=200, largeur_mm=76):
    """Lead nada (13/11/2026) — le bloc « Votre retour sur investissement » :
    le cumul net servi année par année (une courbe par option), et la
    légende avec le retour des cartes. '' sans flux servi ou cédé
    (``data-graphique="courbe_cumul"``)."""
    from . import couverture
    if cede(d, "courbe_cumul"):
        return ""
    lu = courbes_retour(d, cle)
    if lu is None:
        return ""
    base, courbes = lu
    svg = svg_cumul(courbes, couleurs, axe_c, texte_c, police, fmt_mad,
                    hauteur, largeur_mm)
    noms = {"sans": libelle(d, "ci_opt_sans_batterie", "Sans batterie"),
            "avec": libelle(d, "ci_opt_avec_batterie", "Avec batterie")}
    morceaux = []
    for (option, retour, _pts), couleur in zip(courbes, couleurs):
        nom = noms.get(option) or libelle(d, "ci_gr_votre_installation",
                                          "Votre installation")
        texte = couverture.ans(retour) if retour else ""
        suite = (f" — {libelle(d, 'ci_gr_rembourse_en', 'remboursé en')} {texte}"
                 + couverture.unite_ans(d, texte)) if texte else ""
        morceaux.append(_pastille(couleur, f"{nom}{suite}"))
    base_txt = libelle(d, f"ci_{base}", base.upper())
    return (
        f'<div class="{prefixe}-gr" data-graphique="courbe_cumul">'
        f'<div class="{prefixe}-gr-t">'
        + libelle(d, "ci_gr_retour_titre", "Votre retour sur investissement")
        + f'</div>{svg}<div class="{prefixe}-gr-l">{"<br>".join(morceaux)}</div>'
        f'<div class="{prefixe}-gr-l">'
        + libelle(d, "ci_gr_retour_note", "Gain cumulé ({base}) année par année : "
                  "économies moins investissement et remplacements ; "
                  "au-dessus de 0, l'installation est remboursée.", base=base_txt)
        + '</div></div>')


def css_graphique(prefixe, navy, muted):
    """La feuille du bloc (titre, légende) — une définition par préfixe."""
    return (
        f".{prefixe}-gr{{margin-top:8px;}}"
        f".{prefixe}-gr-t{{font-size:8.5pt;font-weight:700;color:{navy};"
        f"margin-bottom:3px;}}"
        f".{prefixe}-gr-l{{font-size:6.8pt;color:{muted};line-height:1.35;"
        f"margin-top:2px;}}")
