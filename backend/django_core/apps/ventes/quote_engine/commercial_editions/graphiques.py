# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Dessins SVG en ligne des éditions commerciales.

Même doctrine que ``ci/graphiques.py`` : chaque nombre DESSINÉ est servi
(``synthese_ci``), la seule opération est la mise à l'échelle ; chaque nombre
IMPRIMÉ est la chaîne déjà formatée passée par l'appelant. Pas de
bibliothèque : WeasyPrint rend le SVG comme un dessin vectoriel.

Lecture (lane recherche 04, 29/10/2026) : barres GROUPÉES (Cleveland &
McGill : la position bat la surface), facture « avant / après » en deux
barres alignées, cumul net réservé au point de retour (MeasuringU : les
cumuls trompent sur la pente), pictogrammes toujours accompagnés du nombre
(Garcia-Retamero & Galesic 2009).
"""
from __future__ import annotations


def _r(x, y, w, h, fill, rx=0, extra=""):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
            f'height="{max(h, 0):.1f}" rx="{rx}" fill="{fill}" {extra}/>')


def _t(x, y, texte, taille, fill, anchor="start", poids=400, extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{taille}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{poids}" '
            f'{extra}>{texte}</text>')


def barres_mensuelles(mois, couleurs, police, reperes, graduation_txt,
                      largeur_mm=120, hauteur_mm=52, legende=None, contour=None,
                      echelle_texte=1.0):
    """Barres GROUPÉES par mois : consommation (claire à contour encre) à
    gauche, production (accent) à droite — la part autoconsommée pleine, le
    surplus en or par-dessus. Corps de texte PHYSIQUES (7,5 pt) quelle que
    soit la largeur du dessin (critique 29/10). ``couleurs`` = (conso, auto,
    surplus, axe, texte) ; ``reperes`` = 12 étiquettes de mois ;
    ``graduation_txt`` = le plus grand kWh servi, déjà formaté."""
    conso_c, auto_c, surplus_c, axe_c, texte_c = couleurs
    um = 520.0 / largeur_mm            # unités du dessin par mm
    upt = um * 0.3528                  # unités par point typographique
    t_axe, t_leg, t_grad = 7.5 * upt, 7.5 * upt, 7 * upt
    W, H = 520.0, 520.0 * hauteur_mm / largeur_mm
    mg, md, mh = 1.5 * um, 1.5 * um, 5 * um
    mb = (12 if legende else 6) * um
    plafond = max(max(m["consommation_kwh"], m["production_kwh"])
                  for m in mois) or 1
    zone = H - mh - mb
    pas = (W - mg - md) / 12.0
    barre = pas * 0.30
    base = H - mb
    f = []
    f.append(f'<line x1="{mg:.1f}" y1="{mh:.1f}" x2="{W - md:.1f}" y2="{mh:.1f}" '
             f'stroke="{axe_c}" stroke-width="0.5" stroke-dasharray="2 3"/>')
    f.append(_t(mg, mh - 0.8 * um, graduation_txt, t_grad, texte_c))
    f.append(f'<line x1="{mg:.1f}" y1="{base:.1f}" x2="{W - md:.1f}" y2="{base:.1f}" '
             f'stroke="{axe_c}" stroke-width="0.8"/>')
    for i, m in enumerate(mois):
        x0 = mg + i * pas + (pas - 2 * barre - 2) / 2
        hc = zone * m["consommation_kwh"] / plafond
        ha = zone * m["autoconso_kwh"] / plafond
        hp = zone * m["production_kwh"] / plafond
        f.append(_r(x0, base - hc, barre, hc, conso_c, 1.2,
                    f'stroke="{contour}" stroke-width="0.7"' if contour else ""))
        xp = x0 + barre + 2
        f.append(_r(xp, base - hp, barre, hp, surplus_c, 1.2))
        f.append(_r(xp, base - ha, barre, ha, auto_c, 1.2))
        f.append(_t(x0 + barre + 1, base + 3.2 * um, reperes[i], t_axe, texte_c, "middle"))
    if legende:
        y = H - 2.2 * um
        x = mg
        carre = 2.4 * um
        for col, lib in zip((conso_c, auto_c, surplus_c), legende):
            f.append(_r(x, y - carre + 0.3 * um, carre, carre, col, 1.5,
                        f'stroke="{contour}" stroke-width="0.7"' if (contour and col == conso_c) else ""))
            f.append(_t(x + carre + 1.2 * um, y, lib, t_leg, texte_c))
            x += carre + 1.2 * um + len(lib) * 0.52 * t_leg + 4 * um
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} '
            f'{H:.0f}" width="{largeur_mm}mm" height="{hauteur_mm}mm" '
            f'font-family="{police}">{"".join(f)}</svg>')


def facture_avant_apres(avant, apres, textes, couleurs, police,
                        largeur_mm=68, hauteur_mm=26):
    """Deux barres horizontales alignées : la facture d'énergie AVANT
    (grise) et APRÈS (accent) ; ``avant``/``apres`` = nombres servis
    (échelle seulement), ``textes`` = (lib_avant, lib_apres, val_avant,
    val_apres, lib_economie) déjà formatés — ``lib_economie`` (la part
    servie, « −35 % ») s'imprime en grand au bout de la barre « avec »
    (critique 29/10). ``couleurs`` = (gris, accent, ligne, texte)."""
    gris, accent, ligne, texte = couleurs
    um = 400.0 / largeur_mm
    upt = um * 0.3528
    W, H = 400.0, 400.0 * hauteur_mm / largeur_mm
    lib_avant, lib_apres, val_avant, val_apres, lib_eco = textes
    x0 = 16 * um
    larg_pct = 21 * um if lib_eco else 0
    larg = W - x0 - larg_pct - 1 * um
    h = 5.5 * um
    y1, y2 = 1.5 * um, 1.5 * um + h + 3.5 * um
    w1 = larg
    w2 = larg * (apres / avant) if avant else 0
    f = [
        _t(0, y1 + h * 0.72, lib_avant, 7.5 * upt, texte),
        _r(x0, y1, w1, h, gris, 1.5),
        _t(0, y2 + h * 0.72, lib_apres, 7.5 * upt, texte),
        _r(x0, y2, w2, h, accent, 1.5),
    ]
    if val_avant:
        f.append(_t(x0 + w1 + 1.5 * um, y1 + h * 0.72, val_avant, 7.5 * upt, texte, poids=600))
    if val_apres:
        f.append(_t(x0 + w2 + 1.5 * um, y2 + h * 0.72, val_apres, 7.5 * upt, texte, poids=600))
    if lib_eco:
        f.append(_t(x0 + w1 + 1.5 * um, y2 + h * 0.95, lib_eco, 20 * upt, accent, "start", 600,
                    'font-family="EdDisplay"'))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} '
            f'{H:.0f}" width="{largeur_mm}mm" height="{hauteur_mm}mm" '
            f'font-family="{police}">{"".join(f)}</svg>')


def frise_cumul(serie, jalons, retour, textes, couleurs, police,
                largeur_mm=120, hauteur_mm=56, origine_txt="", lib_annees=""):
    """La position nette cumulée année par année (``flux.cumul_mad`` servi)
    : aire sous zéro en sable, aire au-dessus en accent, ligne du zéro
    étiquetée « 0 MAD », montant de départ servi (``origine_txt``) à
    l'origine, étoile khatam au point de retour DÉCIMAL servi (ou au
    croisement de zéro interpolé entre les deux années qui l'encadrent),
    jalons étiquetés, unité « années » sous l'axe. ``textes`` =
    (lib_retour, lib_fin, lib_zero) ; ``couleurs`` = (negatif, positif,
    axe, texte, point)."""
    neg_c, pos_c, axe_c, texte_c, point_c = couleurs
    um = 520.0 / largeur_mm
    upt = um * 0.3528
    W, H = 520.0, 520.0 * hauteur_mm / largeur_mm
    mg, md, mh, mb = 20 * um, 1.5 * um, 7 * um, 11 * um
    annees = [a for a, _ in serie]
    valeurs = [c for _, c in serie]
    a_max = max(annees) or 1
    v_max, v_min = max(valeurs + [0]), min(valeurs + [0])
    amplitude = (v_max - v_min) or 1
    zone = H - mh - mb

    def X(a):
        return mg + (W - mg - md) * a / a_max

    def Y(v):
        return mh + zone * (v_max - v) / amplitude

    y0 = Y(0)
    f = []
    pts = " ".join(f"{X(a):.1f},{Y(c):.1f}" for a, c in serie)
    f.append(f'<clipPath id="pos"><rect x="0" y="0" width="{W}" height="{y0:.1f}"/></clipPath>')
    f.append(f'<clipPath id="neg"><rect x="0" y="{y0:.1f}" width="{W}" height="{H}"/></clipPath>')
    poly = (f'<polygon points="{X(annees[0]):.1f},{y0:.1f} {pts} '
            f'{X(annees[-1]):.1f},{y0:.1f}" ')
    f.append(poly + f'fill="{pos_c}" fill-opacity="0.16" clip-path="url(#pos)"/>')
    f.append(poly + f'fill="{neg_c}" clip-path="url(#neg)"/>')
    f.append(f'<polyline points="{pts}" fill="none" stroke="{pos_c}" '
             f'stroke-width="2.2" stroke-linejoin="round"/>')
    f.append(f'<line x1="{mg:.1f}" y1="{y0:.1f}" x2="{W - md:.1f}" y2="{y0:.1f}" '
             f'stroke="{axe_c}" stroke-width="1"/>')
    lib_retour, lib_fin, lib_zero = textes
    f.append(_t(mg - 1.5 * um, y0 + 2.5 * upt, lib_zero, 7.5 * upt, texte_c, "end"))
    if origine_txt:
        f.append(_t(mg - 1.5 * um, Y(valeurs[0]) + 2.5 * upt, origine_txt, 7.5 * upt, texte_c, "end"))
    # Point de retour : la valeur décimale servie, sinon le croisement de zéro.
    xr = None
    if retour is not None and 0 < float(retour) <= a_max:
        xr = X(float(retour))
    else:
        for (a1, c1), (a2, c2) in zip(serie, serie[1:]):
            if c1 < 0 <= c2 and c2 != c1:
                xr = X(a1 + (0 - c1) / (c2 - c1) * (a2 - a1)); break
    if xr is not None:
        f.append(f'<line x1="{xr:.1f}" y1="{mh:.1f}" x2="{xr:.1f}" y2="{H - mb:.1f}" '
                 f'stroke="{point_c}" stroke-width="0.8" stroke-dasharray="2 3"/>')
        from .commun import ETOILE_D
        r = 1.4 * um
        f.append(f'<path d="{ETOILE_D}" transform="translate({xr - r:.1f},{y0 - r:.1f}) scale({r / 20:.3f})" '
                 f'fill="{point_c}"/>')
        if lib_retour:
            f.append(_t(xr + 2 * um, mh - 1.5 * um + 7.5 * upt, lib_retour, 7.5 * upt, texte_c, "start", 600))
    for a, lib in jalons:
        if 0 < a <= a_max:
            f.append(f'<line x1="{X(a):.1f}" y1="{H - mb:.1f}" x2="{X(a):.1f}" '
                     f'y2="{H - mb + 0.8 * um:.1f}" stroke="{axe_c}" stroke-width="0.8"/>')
            f.append(_t(X(a), H - mb + 3.6 * um, str(a), 7.5 * upt, texte_c, "middle"))
    if lib_annees:
        f.append(_t(W - md, H - mb + 7.2 * um, lib_annees, 7 * upt, texte_c, "end"))
    if lib_fin:
        f.append(_t(X(annees[-1]) - 1 * um, Y(valeurs[-1]) - 2 * um, lib_fin, 7.5 * upt,
                    texte_c, "end", 600))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} '
            f'{H:.0f}" width="{largeur_mm}mm" height="{hauteur_mm}mm" '
            f'font-family="{police}">{"".join(f)}</svg>')


def pictogrammes(pct, couleurs, largeur_mm=60, n=10):
    """Une rangée de ``n`` pictogrammes « soleil » : ``round(pct/100·n)``
    pleins (accent), le reste en contour — toujours imprimée À CÔTÉ du
    nombre servi (jamais seule). ``couleurs`` = (accent, contour)."""
    accent, contour = couleurs
    pleins = max(0, min(n, round(float(pct) / 100.0 * n)))
    W = 40.0 * n
    f = []
    for i in range(n):
        cx = 20 + 40 * i
        fill = accent if i < pleins else "none"
        stroke = accent if i < pleins else contour
        f.append(f'<circle cx="{cx}" cy="20" r="9" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="2"/>')
        for k in range(8):
            import math
            ang = k * math.pi / 4
            x1, y1 = cx + 13 * math.cos(ang), 20 + 13 * math.sin(ang)
            x2, y2 = cx + 17 * math.cos(ang), 20 + 17 * math.sin(ang)
            f.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
                     f'y2="{y2:.1f}" stroke="{stroke}" stroke-width="2" '
                     f'stroke-linecap="round"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} 40" '
            f'width="{largeur_mm}mm" height="{largeur_mm * 40 / W:.1f}mm">'
            f'{"".join(f)}</svg>')


def jauge(pct, couleurs, largeur_mm=50, hauteur_mm=3):
    """Une barre 100 % : la part ``pct`` servie en accent, le reste en
    teinte claire. ``couleurs`` = (accent, fond)."""
    accent, fond = couleurs
    p = max(0.0, min(100.0, float(pct)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 6" '
            f'width="{largeur_mm}mm" height="{hauteur_mm}mm" '
            f'preserveAspectRatio="none">'
            f'<rect x="0" y="0" width="100" height="6" rx="3" fill="{fond}"/>'
            f'<rect x="0" y="0" width="{p:.1f}" height="6" rx="3" fill="{accent}"/>'
            f'</svg>')
