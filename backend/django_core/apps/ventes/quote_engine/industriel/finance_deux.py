"""quote_engine industriel — PAGE 3 d'un devis à DEUX options (fondateur,
19/11/2026 : « the page 3 is still all about the ongrid option »).

Quand le document porte l'offre réseau ET l'option « avec batterie », chacune
avec son flux 25 ans servi, la page finance les montre à POIDS ÉGAL : deux
cartes (économie de l'année 1, délai de retour, TRI, cumul net,
investissement), UNE courbe du cumul net à deux lignes avec le point de retour
de chacune, le tableau des flux année par année côte à côte, les indicateurs
et les bases du calcul des deux.

Chaque nombre imprimé est LU : ``synthese_ci['argent']`` pour l'offre réseau,
``ci.synthese._argent_option_avec`` (``etude_ci.option_avec`` : son
``economie_ci`` et son ``economie_flux``) pour l'option batterie — les blocs
que lisent déjà les pages 1 et 2. Seules des POSITIONS de dessin sont mises à
l'échelle. Rendu seul, aucun statut touché (règle #4). Sans seconde option
entièrement chiffrée : ``''`` — la page à une option reste celle d'hier, octet
pour octet.
"""
import re
from functools import partial

from .. import premium_base
from ..ci import blocs as ci_blocs
from ..ci import couverture as ci_couverture
from ..ci import options_cote
from ..figures import ancre
from ..lecture_pure import nombre_ou_none as _num
from ..montants import decimale, regles_avant_2710

#: Libellés propres à cette page (fr / en / ar), comme
#: ``ci.blocs.LIBELLES_OPTION_AVEC``.
LIBELLES = {
    "batterie": {"fr": "batterie de {kwh}&#160;kWh utiles",
                 "en": "{kwh}&#160;kWh usable battery",
                 "ar": "بطارية بسعة مفيدة {kwh}&#160;كيلوواط ساعة"},
    "kwh_evite": {"fr": "Prix moyen de votre kWh évité",
                  "en": "Average price of the kWh you avoid",
                  "ar": "متوسط سعر الكيلوواط ساعة الذي تتجنبونه"},
    "sensibilites": {"fr": "Sensibilités", "en": "Sensitivities",
                     "ar": "تحليل الحساسية"},
}

#: Dessin de la courbe (unités du ``viewBox``) : largeur, hauteurs (pleine,
#: puis compacte quand la page est longue — libellés arabes), marges.
LARGEUR, HAUTEUR, HAUTEUR_COMPACTE = 1000, 200, 132
MARGE_G, MARGE_D, MARGE_H, MARGE_B = 118, 172, 18, 26


def _tout_cede(d):
    """Dernier recours du rendu adaptatif : tous les blocs optionnels cèdent."""
    return d.get("_sans_graphiques") is True


def _texte_svg(texte):
    """Un libellé pour un ``<text>`` du dessin : sans balise (l'arabe du
    catalogue arrive dans un ``<span dir="rtl">``, qu'un SVG ne lit pas)."""
    return re.sub(r"<[^>]+>", "", str(texte or ""))


def _mots_dans_le_dessin(d):
    """Le moteur de rendu ne met pas en forme un texte de droite à gauche
    dans un ``<text>`` SVG : en arabe, le dessin ne porte que des nombres et
    les noms des options passent dans une légende sous la courbe."""
    from .. import i18n_labels
    return not i18n_labels.est_rtl(ci_blocs.langue(d))


def _t(d, cle, **valeurs):
    textes = LIBELLES[cle]
    return (textes.get(ci_blocs.langue(d)) or textes["fr"]).format(**valeurs)


def _argent_avec(d):
    """L'argent PUBLIC de l'option « avec batterie » (même forme que
    ``synthese_ci['argent']``), ou ``None`` quand l'étude ne le sert pas."""
    from ..ci.synthese import _argent_option_avec
    etude_ci = (d.get("etude") or {}).get("etude_ci") \
        if isinstance(d.get("etude"), dict) else None
    option = (etude_ci or {}).get("option_avec") \
        if isinstance(etude_ci, dict) else None
    if not isinstance(option, dict):
        return None
    argent, _motif = _argent_option_avec(option, "industriel")
    return argent if isinstance(argent, dict) else None


def options(d, argent):
    """``[sans, avec]`` — chaque option avec son argent, son flux principal
    et ses indicateurs — ou ``None`` : document à une option, économies
    masquées, option batterie sans flux 25 ans, ou bases / horizons
    différents (une courbe et un tableau communs n'auraient pas de sens),
    devis envoyé sous les règles d'avant le 27/10 (il garde sa page)."""
    from . import finance as F
    if not options_cote.deux_options(d, "ind") \
            or d.get("ind_masquer_economies") or regles_avant_2710():
        return None
    sorties = []
    for cle, bloc in (("sans", argent), ("avec", _argent_avec(d))):
        cle_flux, flux = F.flux_principal(bloc)
        lignes = [f for f in flux.get("flux") or [] if isinstance(f, dict)
                  and _num(f.get("annee")) is not None
                  and _num(f.get("cumul_mad")) is not None]
        indicateurs = (bloc or {}).get("indicateurs") or {}
        horizon = _num(indicateurs.get("tri_horizon_ans")) or \
            _num(flux.get("horizon_ans"))
        if len(lignes) < 2 or horizon is None:
            return None
        sorties.append({"cle": cle, "argent": bloc, "cle_flux": cle_flux,
                        "flux": lignes, "indicateurs": indicateurs,
                        "horizon": horizon})
    sans, avec = sorties
    if sans["cle_flux"] != avec["cle_flux"] \
            or sans["horizon"] != avec["horizon"]:
        return None
    return sorties


def _valeur_avec(d):
    option = (d.get("ind_synthese") or {}).get("option_batterie") or {}
    valeur = option.get("valeur_chiffree")
    return option, valeur if isinstance(valeur, dict) else {}


def _economie(d, o, fmt):
    """``(valeur, base « HT » / « TTC » | None, « soit N MAD TTC » | '')`` de
    l'économie de l'année 1 — les lectures des cartes de la couverture
    (``options_cote.lignes_sans`` / ``lignes_avec``)."""
    from ..ci.mentions import economie_ttc_option_avec
    if o["cle"] == "sans":
        return (d.get("ind_economies"), d.get("ind_economie_base"),
                ci_couverture.economie_ttc(d, "ind", fmt))
    _option, valeur = _valeur_avec(d)
    economie = _num(valeur.get("economie_annuelle_mad"))
    ttc = economie_ttc_option_avec(d) if economie else None
    if ttc and d.get("ind_economie_base") == "TTC" \
            and not d.get("regles_0411_historique"):
        return ttc, "TTC", ""
    return economie, "HT", (ci_couverture.economie_ttc(d, "ind", fmt, ttc)
                            if ttc else "")


def _retour(d, o):
    if o["cle"] == "sans":
        return ci_couverture.retour_dixieme(
            o["argent"], _num(o["indicateurs"].get("retour_ans")))
    return _num(_valeur_avec(d)[1].get("retour_simple_ans"))


def _investissement(d, o, fmt_mad, L):
    """CIQ315 — ``(titre, montant, précision)`` de l'investissement de
    l'option sur la base SERVIE (les mots du pied de la page à une option),
    ou ``None`` quand le montant n'est pas servi (jamais « 0 MAD »)."""
    if o["cle"] == "sans":
        ht = _num((d.get("totaux_all") or {}).get("ht_net"))
        ttc = _num(d.get("_invest_ttc"))
    else:
        option, _valeur = _valeur_avec(d)
        totaux = (option.get("totaux")
                  if isinstance(option.get("totaux"), dict)
                  else (d.get("totaux_avec") or {}))
        ht, ttc = _num(totaux.get("ht_net")), _num(totaux.get("ttc"))
    base = o["argent"].get("base")
    synthese = d.get("ind_synthese")
    if base == "ht" and ht:
        return (ci_couverture.titre_investissement(d, synthese, "ht"),
                f"{fmt_mad(ht)}&#160;MAD", "")
    if not ttc:
        return None
    if base == "deux" and ht:
        return (ci_couverture.titre_investissement(d, synthese, "deux"),
                f"{fmt_mad(ttc)}&#160;MAD&#160;{L('ci_ttc', 'TTC')}",
                f"{L('ci_soit', 'soit')} {fmt_mad(ht)}&#160;MAD&#160;"
                f"{L('ci_ht', 'HT')}")
    return (ci_couverture.titre_investissement(d, synthese, "ttc"),
            f"{fmt_mad(ttc)}&#160;MAD", "")


def _titre_option(d, o, L):
    """« Option 1 — Sans batterie » / « Option 2 — Avec batterie » (les
    titres de la page équipements) et le système : puissance, batterie."""
    rang = 1 if o["cle"] == "sans" else 2
    nom = (L("ci_opt_sans_batterie", "Sans batterie") if o["cle"] == "sans"
           else options_cote._titre_avec(d))
    kwc = d.get("ind_kwc") if o["cle"] == "sans" else d.get("puissance_kwc_avec")
    puissance = options_cote._ligne_puissance(d, kwc, False)
    details = [puissance[1]] if puissance else []
    capacite = (_num(_valeur_avec(d)[1].get("capacite_utile_kwh"))
                if o["cle"] == "avec" else None)
    if capacite:
        details.append(_t(d, "batterie", kwh=decimale(f"{capacite:.1f}")))
    return (f'{L("ci_opt_option", "Option")} {rang} — {nom}',
            " · ".join(details))


def _bas_de_carte(d, o, systeme, fmt_mad, L):
    """Sous les chiffres : l'investissement (titre et système à gauche,
    montants à droite) ; sans montant servi, le système seul."""
    titre, montant, precision = _investissement(d, o, fmt_mad, L) or ("", "", "")
    droite = (f'<td class="i2d-im"><b>{montant}</b>'
              f'<div class="i2d-sys">{precision}</div></td>') if montant else ""
    return (f'<table class="i2d-inv"><tr><td>{titre}'
            f'<div class="i2d-sys">{systeme}</div></td>{droite}</tr></table>')


def _petit_kpi(valeur, unite, libelle, fig=""):
    return (f'<td><div class="i2d-kv">{valeur}<span class="i2d-u">{unite}'
            f'</span></div>{fig}<div class="i2d-kl">{libelle}</div></td>')


def _carte(d, o, fmt, fmt_mad, L):
    """La carte d'une option : économie de l'année 1 en grand, puis délai de
    retour, TRI et cumul net de la dernière année, puis l'investissement."""
    option = None if o["cle"] == "sans" else "avec"
    titre, systeme = _titre_option(d, o, L)
    badge = options_cote._badge_non_rentable(d, "ind") if option else ""
    economie, base_eco, soit_ttc = _economie(d, o, fmt)
    if base_eco in ("HT", "TTC"):
        base_eco = L(f"ci_{base_eco.lower()}", base_eco)
    grand = ""
    if economie is not None:
        grand = (
            f'<div class="i2d-big">{fmt(economie)}<span class="i2d-u">&#160;MAD'
            f'</span></div>{ancre("economie_annuelle", fmt(economie), option=option)}'
            '<div class="i2d-bl">'
            + L("ci_ind_economie_an1", "Économie de l'année 1")
            + (f" ({base_eco})" if base_eco else "")
            + (f" — {soit_ttc}" if soit_ttc else "") + "</div>")
    horizon_txt = f'{o["horizon"]:g}'
    cellules = []
    retour = _retour(d, o)
    if retour is not None:
        txt = ci_couverture.ans(retour)
        cellules.append(_petit_kpi(
            txt, ci_couverture.unite_ans(d, txt),
            L("ci_ind_delai_retour", "Délai de retour"),
            ancre("payback_ans", txt, option=option)))
    tri = _num(o["indicateurs"].get("tri_pct"))
    if tri is not None:
        txt = decimale(f"{tri:.1f}")
        cellules.append(_petit_kpi(
            txt, "&#160;%", L("ci_ind_tri_sur", "TRI sur {n} ans", n=horizon_txt),
            ancre("tri_pct", txt, option=option)))
    cellules.append(_petit_kpi(
        fmt(_num(o["flux"][-1].get("cumul_mad"))), "&#160;MAD",
        L("ci_sens_cumul", "Cumul net sur {n} ans", n=horizon_txt)
        ).replace("<td>", '<td class="i2d-kc">', 1))
    return (
        f'<td class="i2d-opt"><div class="i2d-h i2d-h-{o["cle"]}">'
        f'{titre}{badge}</div>'
        f'<div class="i2d-b">{grand}<table class="i2d-k"><tr>'
        + "".join(cellules) + "</tr></table>"
        + _bas_de_carte(d, o, systeme, fmt_mad, L) + "</div></td>")


def _cartes(d, opts, fmt, fmt_mad, L):
    return ('<table class="i2d-opts"><tr>'
            + '<td class="i2d-gap"></td>'.join(
                _carte(d, o, fmt, fmt_mad, L) for o in opts)
            + "</tr></table>")


def _echelles(opts, hauteur):
    """Les deux fonctions de position ``x(année)`` / ``y(cumul)`` et les
    bornes servies ``(a_max, c_max, c_min)`` de la courbe."""
    points = [(_num(f["annee"]), _num(f["cumul_mad"]))
              for o in opts for f in o["flux"]]
    a_max = max(a for a, _c in points) or 1
    c_max = max(max(c for _a, c in points), 0.0)
    c_min = min(min(c for _a, c in points), 0.0)
    etendue = (c_max - c_min) or 1.0
    zone_w = LARGEUR - MARGE_G - MARGE_D
    zone_h = hauteur - MARGE_H - MARGE_B

    def x(annee):
        return MARGE_G + annee / a_max * zone_w

    def y(cumul):
        return MARGE_H + (c_max - cumul) / etendue * zone_h
    return x, y, (a_max, c_max, c_min)


def _axes(x, y, bornes, fmt, teintes, hauteur):
    """L'axe du zéro, les trois montants de l'axe vertical (le plus haut et
    le plus bas ``cumul_mad`` servis, recopiés) et les années par pas de 5."""
    a_max, c_max, c_min = bornes
    axe_c, texte_c, grille_c = teintes[:3]
    droite = LARGEUR - MARGE_D
    formes = []
    for cumul in (c_max, c_min):
        formes.append(
            f'<line x1="{MARGE_G}" y1="{y(cumul):.1f}" x2="{droite}" '
            f'y2="{y(cumul):.1f}" stroke="{grille_c}" stroke-width="1" '
            'stroke-dasharray="3 4"/>')
    formes.append(
        f'<line x1="{MARGE_G}" y1="{y(0):.1f}" x2="{droite}" y2="{y(0):.1f}" '
        f'stroke="{axe_c}" stroke-width="1.4"/>')
    for cumul, texte in ((c_max, f"{fmt(c_max)}&#160;MAD"), (0, "0"),
                         (c_min, fmt(c_min))):
        formes.append(
            f'<text x="{MARGE_G - 8}" y="{y(cumul) + 4.5:.1f}" font-size="13" '
            f'text-anchor="end" fill="{texte_c}">{texte}</text>')
    for annee in range(0, int(a_max) + 1, 5):
        formes.append(
            f'<line x1="{x(annee):.1f}" y1="{y(0) - 3:.1f}" x2="{x(annee):.1f}" '
            f'y2="{y(0) + 3:.1f}" stroke="{axe_c}" stroke-width="1"/>'
            f'<text x="{x(annee):.1f}" y="{hauteur - 6}" font-size="13" '
            f'text-anchor="middle" fill="{texte_c}">{annee}</text>')
    return formes


def _etiquettes_fin(d, opts, x, y, bornes, fmt, noms, encre, hauteur):
    """À droite de chaque ligne : le nom de l'option et son cumul net de la
    dernière année (servi). Deux étiquettes trop proches sont écartées."""
    a_max = bornes[0]
    fins = [y(_num(o["flux"][-1]["cumul_mad"])) for o in opts]
    ecart = 34 - abs(fins[0] - fins[1])
    if ecart > 0:
        haut = 0 if fins[0] <= fins[1] else 1
        fins[haut] -= ecart / 2
        fins[1 - haut] += ecart / 2
    mots = _mots_dans_le_dessin(d)
    # Le nom se pose au-dessus du montant : jamais hors du haut du dessin.
    remontee = (14 if mots else 6) - min(fins)
    descente = max(fins) + (16 if mots else 7) - hauteur
    if remontee > 0:
        fins = [fin + remontee for fin in fins]
    elif descente > 0:
        fins = [fin - descente for fin in fins]
    formes = []
    gauche = x(a_max) + 10
    for o, fin in zip(opts, fins):
        montant = fmt(_num(o["flux"][-1]["cumul_mad"]))
        formes.append(
            f'<rect x="{gauche:.1f}" y="{fin - (11 if mots else 5):.1f}" '
            f'width="9" height="9" rx="2" fill="{o["couleur"]}"/>')
        if mots:
            formes.append(
                f'<text x="{gauche + 14:.1f}" y="{fin - 1:.1f}" '
                f'font-size="13.5" font-weight="700" fill="{encre}">'
                f'{_texte_svg(noms[o["cle"]])}</text>')
        formes.append(
            f'<text x="{gauche + 14:.1f}" y="{fin + (14 if mots else 5):.1f}" '
            f'font-size="13.5" fill="{encre}">{montant}&#160;MAD</text>')
    return formes


def _points_retour(d, opts, x, y, encre):
    """Le point de retour de chaque option sur l'axe du zéro, à l'abscisse du
    délai de retour IMPRIMÉ sur sa carte, avec ce délai en clair. La première
    étiquette se pose au-dessus à gauche, la seconde au-dessous à droite :
    deux retours proches ne se recouvrent pas."""
    retours = sorted(((_retour(d, o), o) for o in opts if _retour(d, o)),
                     key=lambda paire: paire[0])
    formes = []
    for rang, (retour, o) in enumerate(retours):
        txt = ci_couverture.ans(retour)
        if _mots_dans_le_dessin(d):
            txt = _texte_svg(txt + ci_couverture.unite_ans(d, txt))
        dessus = rang == 0
        formes.append(
            f'<circle cx="{x(retour):.1f}" cy="{y(0):.1f}" r="5.5" fill="#fff" '
            f'stroke="{o["couleur"]}" stroke-width="2.6"/>'
            f'<text x="{x(retour) + (-9 if dessus else 9):.1f}" '
            f'y="{y(0) + (-9 if dessus else 19):.1f}" font-size="13.5" '
            f'font-weight="700" text-anchor="{"end" if dessus else "start"}" '
            f'fill="{encre}">{txt}</text>')
    return formes


def _svg_cumul(d, opts, fmt, police, teintes, noms, hauteur):
    """La courbe du cumul net, une ligne par option. Chaque point est un
    ``cumul_mad`` SERVI ; rien d'autre que sa position n'est calculé."""
    x, y, bornes = _echelles(opts, hauteur)
    formes = _axes(x, y, bornes, fmt, teintes, hauteur)
    for o in opts:
        trace = " ".join(f'{x(_num(f["annee"])):.1f},{y(_num(f["cumul_mad"])):.1f}'
                         for f in o["flux"])
        formes.append(
            f'<polyline points="{trace}" fill="none" stroke="{o["couleur"]}" '
            'stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round"/>')
    encre = teintes[3]
    formes += _points_retour(d, opts, x, y, encre)
    formes += _etiquettes_fin(d, opts, x, y, bornes, fmt, noms, encre,
                              hauteur)
    largeur_mm = 182
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {LARGEUR} {hauteur}" style="width:{largeur_mm}mm;'
            f'height:{largeur_mm * hauteur / LARGEUR:.1f}mm;'
            f'font-family:{police};display:block;">' + "".join(formes) + "</svg>")


def _legende(d, opts, L, noms):
    """Sous la courbe, quand le dessin ne porte pas de mots : la pastille de
    chaque option, son nom et son délai de retour (celui de sa carte)."""
    from ..ci.graphiques import _pastille
    if _mots_dans_le_dessin(d):
        return ""
    morceaux = []
    for o in opts:
        retour = _retour(d, o)
        texte = ci_couverture.ans(retour) if retour else ""
        suite = (f" — {L('ci_gr_rembourse_en', 'remboursé en')} {texte}"
                 + ci_couverture.unite_ans(d, texte)) if texte else ""
        morceaux.append(_pastille(o["couleur"], noms[o["cle"]] + suite))
    return f'<div class="i2d-note">{"".join(morceaux)}</div>'


def _courbe(d, opts, fmt, L, police, teintes, noms, base_txt):
    """Le bloc de la courbe. La page cède par PALIERS (``commercial.equip``) :
    pleine hauteur (seul bloc cédable « courbe_cumul ») ; la page déborde ⇒ la
    courbe COMPACTE, sans sa note — contenu de la page, plus un bloc cédable ;
    elle déborde encore ⇒ ce sont les bases du calcul (« hypotheses ») qui
    cèdent, la courbe compacte et les sensibilités restent ; dernier recours
    (tout cède) ⇒ rien : le tableau porte déjà le cumul."""
    from ..ci.graphiques import cede
    if _tout_cede(d):
        return ""
    if cede(d, "courbe_cumul"):
        return ('<div class="i2d-compacte">' + _svg_cumul(
            d, opts, fmt, police, teintes, noms, HAUTEUR_COMPACTE)
            + _legende(d, opts, L, noms) + "</div>")
    note = L("ci_gr_retour_note",
             "Gain cumulé ({base}) année par année : économies moins "
             "investissement et remplacements ; au-dessus de 0, "
             "l'installation est remboursée.", base=base_txt)
    return ('<div data-graphique="courbe_cumul">'
            + _svg_cumul(d, opts, fmt, police, teintes, noms, HAUTEUR)
            + _legende(d, opts, L, noms)
            + f'<div class="i2d-note">{note}</div></div>')


def _colonnes_flux(opts):
    """Les colonnes de charges communes aux deux options : ``(O&M ou
    entretien déduit ?, remplacement ?)`` et, par option, ses charges."""
    from . import finance as F
    charges = [F._charges_par_annee(o["argent"], o["cle_flux"]) for o in opts]
    return (any(om for om, _r in charges),
            any(remplacements for _om, remplacements in charges), charges)


def _cellules_annee(f, annee, charges, avec_om, avec_rempl, fmt_mad, fig):
    """Les cellules d'UNE option pour UNE année — chaque nombre est celui de
    la ligne servie (aucun recalcul)."""
    if f is None:
        return "<td></td>" * (3 + avec_om + avec_rempl)
    om_an, remplacements = charges
    cumul = _num(f.get("cumul_mad"))
    cellules = [fmt_mad(_num(f.get("economie_mad")) or 0) if annee else "—"]
    if avec_om:
        cellules.append(fmt_mad(-om_an) if annee and om_an else "—")
    if avec_rempl:
        cellules.append(fmt_mad(-remplacements[annee])
                        if annee in remplacements else "—")
    cellules.append(fmt_mad(_num(f.get("flux_mad")) or 0))
    cls = "i2-pos" if cumul >= 0 else "i2-neg"
    return ('<td class="i2-n i2d-g">' + cellules[0] + "</td>"
            + "".join(f'<td class="i2-n">{c}</td>' for c in cellules[1:])
            + f'<td class="i2-c {cls}">{fmt_mad(cumul)}{fig}</td>')


def _tableau(opts, fmt_mad, L, noms, base_txt):
    """AMOT94 — le flux de trésorerie servi année par année, les deux
    options côte à côte : économie, charges (si servies), flux net et cumul
    net ; le cumul de la dernière année est ancré pour chaque option."""
    from . import finance as F
    avec_om, avec_rempl, charges = _colonnes_flux(opts)
    colonnes = [L("ci_fx_economie", "Économie")]
    if avec_om:
        colonnes.append(L("ci_fx_entretien", "Entretien") if any(
            F._entretien_deduit(o["argent"]) for o in opts)
            else L("ci_fx_om", "O&amp;M"))
    if avec_rempl:
        colonnes.append(L("ci_fx_remplacement", "Remplacement"))
    colonnes += [L("ci_fx_flux", "Flux net"),
                 f'{L("ci_ind_cumul_net", "Cumul net")} ({base_txt})']
    groupes = "".join(
        f'<th colspan="{len(colonnes)}" class="i2d-gt i2d-gt-{o["cle"]}">'
        f'{noms[o["cle"]]}</th>' for o in opts)
    titres = "".join(
        f'<th class="i2-r{" i2d-g" if rang == 0 else ""}">{c}</th>'
        for _o in opts for rang, c in enumerate(colonnes))
    par_annee = [{int(_num(f["annee"])): f for f in o["flux"]} for o in opts]
    derniere = max(max(lignes) for lignes in par_annee)
    rangees = ""
    for annee in range(0, derniere + 1):
        rangees += f"<tr><td>{annee}</td>"
        for o, lignes, charge in zip(opts, par_annee, charges):
            f = lignes.get(annee)
            fig = (ancre("cumul_net_25_ans_mad", fmt_mad(_num(f["cumul_mad"])),
                         option=None if o["cle"] == "sans" else "avec")
                   if f is not None and annee == 25 else "")
            rangees += _cellules_annee(f, annee, charge, avec_om, avec_rempl,
                                       fmt_mad, fig)
        rangees += "</tr>"
    return ('<table class="i2-tbl i2-fx i2d-fx">'
            f'<tr><th></th>{groupes}</tr>'
            f'<tr><th>{L("ci_fx_annee", "Année")}</th>{titres}</tr>'
            f'{rangees}</table>')


def _rangee_lcoe(opts, L, base_txt):
    """Le coût du kWh produit de chaque option (ancré), ou ``None``."""
    from . import finance as F
    from .cover import _taux_declare
    lcoes = [_num(o["indicateurs"].get("lcoe_mad_kwh")) for o in opts]
    if all(v is None for v in lcoes):
        return None
    actualise = all(o["indicateurs"].get("lcoe_actualise")
                    or _taux_declare(o["argent"]) is not None
                    for o, v in zip(opts, lcoes) if v is not None)
    libelle = (L("ci_ind_lcoe", "Coût du kWh solaire (LCOE, {base})",
                 base=base_txt) if actualise else
               L("ci_ind_lcoe_non_actualise",
                 "Coût moyen non actualisé du kWh produit ({base})",
                 base=base_txt))
    return libelle, [
        "—" if v is None else
        f"<b>{F._decimal_3(v)}&#160;MAD/kWh</b>" + ancre(
            "lcoe_mad_kwh", F._decimal_3(v),
            option=None if o["cle"] == "sans" else "avec")
        for v, o in zip(lcoes, opts)]


def _rangees_indicateurs(d, opts, fmt_mad, L, base_txt):
    """``[(libellé, [valeur sans, valeur avec])]`` : coût du kWh produit,
    prix moyen du kWh évité, VAN sur le taux déclaré — tels que servis ; une
    valeur qu'une option ne sert pas est un tiret, jamais une rangée perdue
    pour l'autre."""
    from . import finance as F
    from .cover import _taux_declare
    rangees = [r for r in (_rangee_lcoe(opts, L, base_txt),) if r]
    tarifs = [_num(o["indicateurs"].get("tarif_kwh_evite_moyen")) for o in opts]
    if any(v is not None for v in tarifs):
        rangees.append((f'{_t(d, "kwh_evite")} ({base_txt})', [
            "—" if v is None else f"{F._decimal_3(v)}&#160;MAD/kWh"
            for v in tarifs]))
    taux = [_taux_declare(o["argent"]) for o in opts]
    vans = [_num(o["indicateurs"].get("van_mad")) if t is not None else None
            for o, t in zip(opts, taux)]
    declares = {t for t, v in zip(taux, vans) if v is not None}
    if len(declares) == 1:
        rangees.append((
            L("ci_ind_van", "VAN au taux déclaré de {taux} %",
              taux=F._decimal_txt(declares.pop())),
            ["—" if v is None else f"<b>{fmt_mad(v)}&#160;MAD</b>"
             for v in vans]))
    return rangees


def _retour_scenario(d, scenario):
    """Le délai de retour d'un scénario, lu comme la page à une option
    (``finance._retour_scenario`` : au dixième servi dès le niveau 14, sinon
    l'année servie)."""
    from . import finance as F
    return _num(F._retour_scenario(d, scenario))


def _cellules_scenario(d, valeurs, fmt_mad):
    """Les trois cellules d'une option pour un scénario : délai de retour, TRI,
    cumul net — un tiret pour une valeur non servie, jamais un nombre de repli."""
    retour, tri, cumul = valeurs
    textes = []
    if retour is None:
        textes.append("—")
    else:
        txt = ci_couverture.ans(retour)
        textes.append(txt + ci_couverture.unite_ans(d, txt))
    textes.append("—" if tri is None else decimale(f"{tri:.1f}") + "&#160;%")
    textes.append("—" if cumul is None else fmt_mad(cumul) + "&#160;MAD")
    return "".join(f'<td class="i2-n{" i2d-g" if rang == 0 else ""}">{t}</td>'
                   for rang, t in enumerate(textes))


def _rangees_sensibilites(d, opts, L):
    """``[(nom du scénario, [(retour, TRI, cumul) par option])]`` — le central
    (les chiffres des cartes) puis chaque scénario de l'offre réseau avec celui
    de l'option batterie de même clé et même variation ; ``None`` dès qu'une
    option ne sert aucun scénario (le rendu par option reste)."""
    from . import finance as F
    listes = [[sc for sc in o["argent"].get("sensibilites") or []
               if isinstance(sc, dict)] for o in opts]
    if not all(listes):
        return None
    avec = {(sc.get("cle"), sc.get("variation_pct")): sc for sc in listes[1]}
    rangees = [(L("ci_sens_central", "Scénario central"), [
        (_retour(d, o), _num(o["indicateurs"].get("tri_pct")),
         _num(o["flux"][-1].get("cumul_mad"))) for o in opts])]
    for sc in listes[0]:
        paire = (sc, avec.get((sc.get("cle"), sc.get("variation_pct"))))
        rangees.append((F._nom_scenario(sc, L), [
            (None, None, None) if x is None else
            (_retour_scenario(d, x), _num(x.get("tri_pct")),
             _num(x.get("cumul_25_ans_mad"))) for x in paire]))
    return rangees


def _sensibilites_deux(d, opts, fmt_mad, L, noms):
    """AMOT97 — UN tableau des sensibilités pour les deux options (fondateur
    19/11/2026) : chaque scénario saisi par la société, ses trois chiffres
    SERVIS par option. '' quand une option n'en sert pas, ou en dernier recours
    du rendu adaptatif (les bases du calcul cèdent avant lui)."""
    rangees = None if _tout_cede(d) else _rangees_sensibilites(d, opts, L)
    if not rangees:
        return ""
    horizon = f'{opts[0]["horizon"]:g}'
    titres = (L("ci_ind_delai_retour", "Délai de retour"),
              L("ci_ind_tri_sur", "TRI sur {n} ans", n=horizon),
              L("ci_sens_cumul", "Cumul net sur {n} ans", n=horizon))
    groupes = "".join(
        f'<th colspan="3" class="i2d-gt i2d-gt-{o["cle"]}">{noms[o["cle"]]}</th>'
        for o in opts)
    entete = "".join(f'<th class="i2-r{" i2d-g" if rang == 0 else ""}">{t}</th>'
                     for _o in opts for rang, t in enumerate(titres))
    lignes = "".join(
        f"<tr><td>{nom}</td>"
        + "".join(_cellules_scenario(d, v, fmt_mad) for v in valeurs) + "</tr>"
        for nom, valeurs in rangees)
    base = L("ci_ind_sens_base", "Sensibilités saisies par la société ; "
             "base : 0 % d'indexation du tarif.")
    return (f'<div class="i2d-st">{_t(d, "sensibilites")}'
            f'<span class="i2d-stn"> — {base}</span></div>'
            f'<table class="i2-tbl i2-fx i2d-fx i2d-sens"><tr><th></th>{groupes}</tr>'
            f'<tr><th>{L("ci_sens_scenario", "Scénario")}</th>{entete}</tr>'
            f'{lignes}</table>')


def _indicateurs(d, opts, fmt, fmt_mad, L, noms, base_txt, teintes_cfo):
    """CIQ343 — « Indicateurs pour votre direction financière », les deux
    options en colonnes ; puis les sensibilités de chaque option qui en sert
    (nommée), la P90 et l'offre de financement du document."""
    from . import finance as F
    rangees = _rangees_indicateurs(d, opts, fmt_mad, L, base_txt)
    tableau = ""
    if rangees:
        tableau = (
            '<table class="i2-tbl i2-fx i2d-ind"><tr><th></th>'
            + "".join(f'<th class="i2-r">{noms[o["cle"]]}</th>' for o in opts)
            + "</tr>" + "".join(
                f"<tr><td>{libelle}</td>"
                + "".join(f'<td class="i2-n">{v}</td>' for v in valeurs)
                + "</tr>" for libelle, valeurs in rangees) + "</table>")
    # Les deux options servent leurs scénarios : UN tableau, sous les
    # indicateurs ; sinon celui de chaque option qui en sert, nommée.
    communes = _sensibilites_deux(d, opts, fmt_mad, L, noms)
    sensibilites = ""
    for o in () if communes else opts:
        bloc = F._tableau_sensibilites(d, o["argent"], fmt_mad, L)
        if bloc:
            sensibilites += (f'<div class="i2d-st">{_t(d, "sensibilites")} — '
                             f'{noms[o["cle"]]}</div>{bloc}')
    p90 = F._p90_bancable(d)
    p90_html = ('<div class="i2-cfo-i">'
                + L("ci_ind_p90", "Production à 90 % de probabilité (P90) : "
                    "{kwh} kWh/an", kwh=fmt(p90)) + "</div>") \
        if p90 is not None else ""
    financement = ci_blocs.bloc_financement(
        d.get("ind_synthese") or {}, "i2", *teintes_cfo, doc=d)
    if not (tableau or sensibilites or communes or p90_html or financement):
        return ""
    titre = L("ci_ind_indicateurs", "Indicateurs pour votre direction financière")
    gauche, droite = tableau + p90_html, sensibilites
    cote_a_cote = (f'<table class="i2d-cfo"><tr><td class="i2d-cg">{gauche}</td>'
                   f'<td class="i2d-cgap"></td><td>{droite}</td></tr></table>'
                   if gauche and droite else gauche + droite)
    if communes:
        # Les indicateurs en lignes (le tableau des sensibilités porte déjà
        # les deux colonnes d'options) : la courbe garde sa pleine hauteur.
        lignes = "".join(
            f'<div class="i2-cfo-i">{libelle}&#160;: ' + " · ".join(
                f'{noms[o["cle"]]} {v}' for o, v in zip(opts, valeurs)) + "</div>"
            for libelle, valeurs in rangees)
        cote_a_cote = lignes + p90_html + communes
    return (f'<div class="i2-cfo i2d-cfob"><div class="i2-hyp-t">{titre}</div>'
            f'{cote_a_cote}{financement}</div>')


def _libelle_base(ligne):
    return ligne.split("&#160;:", 1)[0]


def _lignes_bases(d, o, fmt, fmt_mad, L):
    """``(hypothèses générales, remplacements)`` d'une option — les lignes de
    ``finance._hypotheses`` ; les remplacements sont celles qui disparaissent
    quand on retire ``argent.remplacements`` et ``argent.batterie_duree``
    (niveau 13 : la durée de vie de la batterie, sous le nom de SON option)."""
    from . import finance as F
    flux = F.flux_principal(o["argent"])[1]
    toutes = F._hypotheses(o["argent"], flux, fmt, fmt_mad, L, d)
    generales = F._hypotheses(dict(o["argent"], remplacements=[], batterie_duree=None), flux,
                              fmt, fmt_mad, L, d)
    return generales, [li for li in toutes if li not in generales]


def _bases(d, opts, fmt, fmt_mad, L, noms):
    """« Bases du calcul » : les hypothèses communes UNE fois ; sous le nom
    de chaque option, ses remplacements (toujours : l'onduleur et son année
    diffèrent) et ses hypothèses de valeur différente. Une hypothèse que
    seule l'offre réseau sert (tarif, valorisation : faits du document) est
    commune. Aucune ligne n'est écrite ici."""
    from ..ci.graphiques import cede
    from . import finance as F
    if cede(d, "hypotheses"):
        return ""
    (sans, rempl_sans), (avec, rempl_avec) = (
        _lignes_bases(d, o, fmt, fmt_mad, L) for o in opts)
    libelles_avec = {_libelle_base(li) for li in avec}
    communes = [li for li in sans
                if li in avec or _libelle_base(li) not in libelles_avec]
    propres = {"sans": [li for li in sans if li not in communes] + rempl_sans,
               "avec": [li for li in avec if li not in sans] + rempl_avec}
    if not communes and not any(propres.values()):
        return ""
    items = "".join(f'<div class="i2-hyp-i">{li}</div>' for li in communes)
    par_option = "".join(
        f'<div class="i2d-hp"><b>{noms[cle]}</b> — {" · ".join(lignes)}</div>'
        for cle, lignes in propres.items() if lignes)
    return ('<div class="i2-hyp" data-graphique="hypotheses">'
            f'<div class="i2-hyp-t">{L("ci_bases_calcul", F.TITRE_HYPOTHESES)}'
            f'</div><div class="i2-hyp-c">{items}</div>{par_option}</div>')


def _reventes(d, opts, fmt, L, noms):
    """Revente 82-21 servie (MT) — par option, nommée ; '' en basse tension."""
    from . import finance as F
    blocs = []
    for o in opts:
        html = F._ligne_revente(o["argent"], fmt, L, ci_blocs.langue(d))
        if html:
            blocs.append(html.replace(
                '<div class="i2-inj">',
                f'<div class="i2-inj"><b>{noms[o["cle"]]}</b> — ', 1))
    return "".join(blocs)


def _pied(d, opts, fmt_mad, L, noms):
    """Le pied de la page : l'O&M telle que servie (par option si elle
    diffère), la méthode du TRI, la mention MT."""
    from . import finance as F
    om = [F._ligne_om(o["argent"], fmt_mad, L) for o in opts]
    if om[0] == om[1]:
        om_txt = f"{om[0]}. " if om[0] else ""
    else:
        om_txt = "".join(f'{noms[o["cle"]]} — {txt}. '
                         for o, txt in zip(opts, om) if txt)
    mt_source = (f'<br><span class="i2-mini">'
                 f'{ci_couverture.mention_client(d["ind_mt_mention"])}</span>'
                 if d.get("ind_mt_mention") else "")
    methode = L("ci_ind_methode_tri_client",
                "TRI et délai de retour calculés sur ces flux annuels "
                "(méthode actuarielle).")
    return f'<div class="i2-foot">{om_txt}{methode}{mt_source}</div>'


def _palette(ctx):
    return premium_base.couleurs(
        ctx["C"], "navy gold ink muted muted_2 line line_soft")


def css(ctx, argent):
    """La feuille propre aux deux options — ``''`` sur toute autre page."""
    if options(ctx["d"], argent) is None:
        return ""
    navy, gold, ink, muted, muted_2, line, line_soft = _palette(ctx)
    f_display, _f_serif, _f_sans = premium_base.polices(ctx["fonts"])
    return f"""
.i2d-opts{{width:100%;margin-top:9px;border-spacing:0;border-collapse:separate;
  table-layout:fixed;}}
.i2d-opt{{vertical-align:top;border:1px solid {line};border-radius:12px;
  padding:0;background:#fff;}}
.i2d-gap{{width:10px;}}
.i2d-h{{padding:5px 12px;color:#fff;font-size:9pt;font-weight:700;
  border-radius:11px 11px 0 0;}}
.i2d-h-sans{{background:{navy};}}
.i2d-h-avec{{background:{gold};}}
.i2d-b{{padding:8px 12px 7px 12px;}}
.i2d-big{{font-family:{f_display};font-size:20pt;color:{navy};line-height:1;}}
.i2d-u{{font-size:7.5pt;color:{muted};}}
.i2d-bl{{font-size:7.5pt;color:{muted};margin-top:3px;}}
.i2d-k{{width:100%;margin-top:6px;border-collapse:collapse;table-layout:fixed;}}
.i2d-k td{{vertical-align:top;padding:5px 4px 0 0;border-top:1px solid {line_soft};
  width:24%;}}
.i2d-k td + td{{width:31%;}}
.i2d-k td.i2d-kc{{width:45%;}}
.i2d-kv{{font-family:{f_display};font-size:12.5pt;color:{navy};line-height:1;}}
.i2d-kl{{font-size:6.8pt;color:{muted};margin-top:2px;}}
.i2d-inv{{width:100%;margin-top:6px;border-collapse:collapse;font-size:7.3pt;
  color:{ink};}}
.i2d-inv td{{padding:5px 0 0 0;vertical-align:top;border-top:1px solid {line_soft};}}
.i2d-inv b{{color:{navy};font-size:8pt;}}
.i2d-im{{text-align:right;white-space:nowrap;}}
.i2d-sys{{font-size:6.8pt;color:{muted};margin-top:1px;}}
.i2d-note{{font-size:6.8pt;color:{muted};line-height:1.35;margin-top:3px;}}
.i2d-fx{{margin-top:7px;}}
.i2d-fx td.i2-n,.i2d-fx td.i2-c{{direction:ltr;}}
.i2d-fx td:first-child{{color:{muted};}}
.i2d-gt{{text-align:center !important;color:#fff !important;font-size:6.5pt !important;
  padding:2.5px 5px !important;border-bottom:none !important;}}
.i2d-gt-sans{{background:{navy};}}
.i2d-gt-avec{{background:{gold};}}
.i2d-g{{border-left:1px solid {muted_2};}}
.i2d-ind td{{padding:1.5px 5px !important;}}
.i2d-cfo{{width:100%;border-collapse:collapse;table-layout:fixed;}}
.i2d-cfo td{{padding:0;vertical-align:top;}}
.i2d-cfo td.i2d-cgap{{width:14px;}}
.i2d-cfo td.i2d-cg{{width:40%;}}
.i2d-cfo .i2-n,.i2d-ind th{{white-space:nowrap;}}
.i2d-cfo .i2-fx td{{padding-top:1.2px;padding-bottom:1.2px;}}
.i2d-ind td:first-child{{width:46%;}}
.i2d-cfob{{border-left-color:{muted_2};}}
[dir="rtl"] .i2d-cfob{{border-left:1px solid {line};border-right:4px solid {muted_2};}}
[dir="rtl"] .i2-hyp-i{{padding-left:0;padding-right:10px;}}
[dir="rtl"] .i2-hyp-i:before{{left:auto;right:0;}}
.i2d-cfo .i2-cfo-i{{font-size:6.6pt;}}
.i2d-st{{margin-top:4px;font-size:6.5pt;font-weight:700;color:{navy};}}
.i2d-sens{{margin-top:2px;}}
.i2d-sens td.i2-n{{direction:inherit;}}
.i2-cfo{{margin-top:6px;}}
.i2-hyp{{margin-top:6px;padding:6px 12px;}}
.i2-foot{{margin-top:5px;}}
.i2d-stn{{font-weight:400;color:{muted};}}
.i2d-cfob .i2d-sens td{{padding-top:1.2px;padding-bottom:1.2px;}}
.i2d-hp{{font-size:6.6pt;color:{muted};line-height:1.3;margin-top:3px;}}
.i2d-hp b{{color:{ink};}}
"""


def corps(ctx, argent):
    """Le corps de la page finance à deux options, ou ``''`` (page à une
    option, option batterie sans flux 25 ans : la page d'hier)."""
    d = ctx["d"]
    opts = options(d, argent)
    if opts is None:
        return ""
    L = partial(ci_blocs.libelle, d)
    fmt = ctx["fmt"]
    fmt_mad = ctx.get("fmt_mad") or fmt
    navy, gold, ink, muted, muted_2, line, _line_soft = _palette(ctx)
    _f_display, _f_serif, f_sans = premium_base.polices(ctx["fonts"])
    for o, couleur in zip(opts, (navy, gold)):
        o["couleur"] = couleur
    noms = {"sans": L("ci_opt_sans_batterie", "Sans batterie"),
            "avec": options_cote._titre_avec(d)}
    base_txt = {"ttc": L("ci_ttc", "TTC")}.get(argent.get("base"),
                                               L("ci_ht", "HT"))
    titre_courbe = L("ci_ind_cumul_titre",
                     "Cumul net de l'investissement ({base})", base=base_txt)
    return f"""
  {_cartes(d, opts, fmt, fmt_mad, L)}
  {_reventes(d, opts, fmt, L, noms)}
  <div class="i2-cfhead">{titre_courbe}</div>
  {_courbe(d, opts, fmt, L, f_sans, (muted_2, muted, line, navy), noms, base_txt)}
  {_tableau(opts, fmt_mad, L, noms, base_txt)}
  {_indicateurs(d, opts, fmt, fmt_mad, L, noms, base_txt, (navy, ink))}
  {_bases(d, opts, fmt, fmt_mad, L, noms)}
  {_pied(d, opts, fmt_mad, L, noms)}"""
