"""CPDF3 — les deux options d'un devis C&I côte à côte en couverture :
deux cartes de même gabarit « Sans batterie » / « Avec batterie » (puissance,
investissement, économie annuelle, retour, part de la consommation couverte).

Fonction PURE → HTML. Tout est LU sur les données servies : l'offre sans
batterie sur ``<cle>_*`` (``chiffres_cles(synthese_ci)``, posés par le
renderer) et la chaîne canonique des totaux ; l'option avec batterie sur
``synthese_ci['option_batterie']`` (``totaux``, ``valeur_chiffree``) et
``puissance_kwc_avec``. Valeur absente ⇒ ligne OMISE (jamais un « 0 », jamais
un chiffre recalculé). Un document mono-option ne reçoit aucune carte
(``deux_options`` faux). Rendu seul — aucun statut touché (règle #4).
"""
from __future__ import annotations

import html

from .. import i18n_labels_ci  # noqa: F401 — libellés CPDF des couvertures
from ..figures import ancre
from ..lecture_pure import nombre_ou_none
from ..premium_base import kwc_str
from . import couverture
from .blocs import libelle


def deux_options(d, cle):
    """Le document porte-t-il les deux offres (réseau seul servi en titre,
    option batterie servie à côté, CIQ302) ?"""
    synthese = d.get(f"{cle}_synthese")
    return (d.get("option_servie") == "sans" and isinstance(synthese, dict)
            and isinstance(synthese.get("option_batterie"), dict))


def _pct(valeur):
    return f"{round(valeur)}&#160;%"


def _base_ht(synthese):
    argent = synthese.get("argent") if isinstance(synthese, dict) else None
    return isinstance(argent, dict) and argent.get("base") == "ht"


def _ligne_prix(d, synthese, ht, ttc, fmt_mad, ancrer):
    """« Investissement TTC » (HT quand la TVA est récupérable, base ``ht``
    servie), ou None sans montant servi."""
    hors_visite = couverture.postes_hors_total(synthese)
    if _base_ht(synthese) and ht is not None:
        montant, cle_fig = ht, "total_ht"
        titre = (couverture.titre_investissement(d, synthese, "ht")
                 if hors_visite else
                 libelle(d, "ci_opt_investissement_ht", "Investissement HT"))
    elif ttc:
        montant, cle_fig = ttc, "total_affiche"
        titre = (couverture.titre_investissement(d, synthese, "ttc")
                 if hors_visite else
                 libelle(d, "ci_opt_investissement_ttc", "Investissement TTC"))
    else:
        return None
    texte = fmt_mad(montant)
    return titre, (f"{texte}&#160;MAD"
                   + (ancre(cle_fig, texte) if ancrer else ""))


def _ligne_economie(d, valeur, base, fmt, ancrer):
    texte = fmt(valeur)
    unite = f"&#160;{libelle(d, f'ci_{base.lower()}', base)}" \
        if base in ("HT", "TTC") else ""
    return (libelle(d, "ci_opt_economie_annuelle", "Économie annuelle"),
            f"{texte}&#160;MAD{unite}"
            + (ancre("economie_annuelle", texte) if ancrer else ""))


def _ligne_retour(d, ans_valeur, ancrer):
    texte = couverture.ans(ans_valeur)
    return (libelle(d, "ci_opt_retour", "Retour sur investissement"),
            texte + couverture.unite_ans(d, texte)
            + (ancre("payback_ans", texte) if ancrer else ""))


def _ligne_puissance(d, kwc, ancrer):
    texte = kwc_str(kwc, "")
    if not texte:
        return None
    return (libelle(d, "ci_opt_puissance", "Puissance"),
            texte + libelle(d, "res_unite_kwc", "&nbsp;kWc")
            + (ancre("puissance_kwc", texte) if ancrer else ""))


def _ligne_couverture(d, pct, ancrer):
    return (libelle(d, "ci_opt_couverture",
                    "Part de votre consommation couverte"),
            _pct(pct) + (ancre("couverture_pct", f"{round(pct)}")
                         if ancrer else ""))


def lignes_sans(d, cle, fmt, fmt_mad, invest_ttc):
    """Les rangées de la carte « Sans batterie » (l'offre servie en titre :
    ses chiffres portent les ancres ``data-figure`` de la couverture)."""
    synthese = d.get(f"{cle}_synthese") or {}
    lignes = [_ligne_puissance(d, d.get(f"{cle}_kwc"), True),
              _ligne_prix(d, synthese, (d.get("totaux_all") or {}).get(
                  "ht_net"), invest_ttc, fmt_mad, True)]
    if not d.get(f"{cle}_masquer_economies"):
        economie = d.get(f"{cle}_economies")
        if economie is not None:
            lignes.append(_ligne_economie(
                d, economie, d.get(f"{cle}_economie_base"), fmt, True))
        retour = couverture.retour_affiche(d, cle)
        if retour is not None:
            lignes.append(_ligne_retour(d, retour, True))
    couverture_pct = d.get(f"{cle}_couverture")
    if couverture_pct is not None:
        lignes.append(_ligne_couverture(d, couverture_pct, True))
    return [li for li in lignes if li]


def lignes_avec(d, cle, fmt, fmt_mad):
    """Les rangées de la carte « Avec batterie » : ``option_batterie`` servi
    (totaux de l'option, valeur chiffrée par le moteur C&I)."""
    synthese = d.get(f"{cle}_synthese") or {}
    option = synthese.get("option_batterie") or {}
    totaux = option.get("totaux") if isinstance(option.get("totaux"), dict) \
        else (d.get("totaux_avec") or {})
    valeur = option.get("valeur_chiffree")
    valeur = valeur if isinstance(valeur, dict) else {}
    lignes = [_ligne_puissance(d, d.get("puissance_kwc_avec"), False),
              _ligne_prix(d, synthese, nombre_ou_none(totaux.get("ht_net")),
                          nombre_ou_none(totaux.get("ttc")), fmt_mad, False)]
    if not d.get(f"{cle}_masquer_economies"):
        # ``valeur_option_avec`` : l'économie annuelle HT de l'option.
        economie = nombre_ou_none(valeur.get("economie_annuelle_mad"))
        if economie:
            lignes.append(_ligne_economie(d, economie, "HT", fmt, False))
        retour = nombre_ou_none(valeur.get("retour_simple_ans"))
        if retour:
            lignes.append(_ligne_retour(d, retour, False))
    couverture_pct = nombre_ou_none(valeur.get("taux_couverture_pct"))
    if couverture_pct is not None:
        lignes.append(_ligne_couverture(d, couverture_pct, False))
    return [li for li in lignes if li]


def _titre_avec(d):
    """« Avec batterie », ou le libellé servi d'une batterie différée
    (BAT-DIFF : ``libelle_avec``, imprimé par tous les renderers)."""
    if d.get("avec_batterie_differee") and d.get("libelle_avec"):
        return html.escape(str(d["libelle_avec"]), quote=False)
    return libelle(d, "ci_opt_avec_batterie", "Avec batterie")


def cartes_options(d, cle, prefixe, fmt, fmt_mad, invest_ttc):
    """``<table>`` des deux cartes, ou '' sur un document mono-option."""
    if not deux_options(d, cle):
        return ""
    cartes = (
        (libelle(d, "ci_opt_sans_batterie", "Sans batterie"),
         lignes_sans(d, cle, fmt, fmt_mad, invest_ttc)),
        (_titre_avec(d), lignes_avec(d, cle, fmt, fmt_mad)))
    cellules = []
    for titre, lignes in cartes:
        rangees = "".join(
            f'<tr><td class="{prefixe}-opt-l">{lib}</td>'
            f'<td class="{prefixe}-opt-v">{val}</td></tr>'
            for lib, val in lignes)
        cellules.append(
            f'<td class="{prefixe}-opt"><div class="{prefixe}-opt-t">'
            f'{titre}</div><table class="{prefixe}-opt-tbl">{rangees}'
            f'</table></td>')
    return (f'<table class="{prefixe}-opts"><tr>'
            + f'<td class="{prefixe}-opt-gap"></td>'.join(cellules)
            + '</tr></table>')


def css_options(prefixe, couleurs, marge_px):
    """La feuille des deux cartes (même gabarit). ``couleurs`` = (line,
    wash, muted, navy, ink, gold)."""
    line, wash, muted, navy, ink, gold = couleurs
    return (
        f".{prefixe}-opts{{width:100%;margin-top:{marge_px}px;"
        f"border-collapse:separate;border-spacing:0;table-layout:fixed;}}"
        f".{prefixe}-opt{{vertical-align:top;border:1px solid {line};"
        f"border-top:4px solid {gold};border-radius:12px;background:{wash};"
        f"padding:8px 12px;}}"
        f".{prefixe}-opt-gap{{width:10px;}}"
        f".{prefixe}-opt-t{{font-weight:700;font-size:10pt;color:{navy};"
        f"margin-bottom:3px;}}"
        f".{prefixe}-opt-tbl{{width:100%;border-collapse:collapse;"
        f"font-size:8pt;}}"
        f".{prefixe}-opt-tbl td{{padding:1.5px 0;vertical-align:top;}}"
        f".{prefixe}-opt-l{{color:{muted};padding-right:6px !important;}}"
        f".{prefixe}-opt-v{{color:{ink};font-weight:700;text-align:right;"
        f"white-space:nowrap;}}")
