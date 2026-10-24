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
                           hauteur=150, largeur_mm=118):
    """AMOT90 — le bloc « Votre énergie mois par mois » : titre, barres
    mensuelles et légende sur deux lignes, lus sur
    ``synthese['energie']['par_mois']`` ; '' quand les 12 mois ne sont pas
    servis, ou quand le rendu adaptatif l'a retiré (``_sans_graphiques``)."""
    mois = mois_servis(synthese)
    if mois is None or cede(d, "energie_mensuelle"):
        return ""
    reperes = REPERES_MOIS.get(langue(d)) or [str(i) for i in range(1, 13)]
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


def css_graphique(prefixe, navy, muted):
    """La feuille du bloc (titre, légende) — une définition par préfixe."""
    return (
        f".{prefixe}-gr{{margin-top:8px;}}"
        f".{prefixe}-gr-t{{font-size:8.5pt;font-weight:700;color:{navy};"
        f"margin-bottom:3px;}}"
        f".{prefixe}-gr-l{{font-size:6.8pt;color:{muted};line-height:1.35;"
        f"margin-top:2px;}}")
