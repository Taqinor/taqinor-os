"""Le UNE-PAGE d'un devis commercial ou industriel (moteur legacy
``generate_devis_premium``) : les morceaux propres au C&I, en fonctions
PURES (données et libellés en entrée, valeur ou fragment HTML en sortie).

Rendu SEUL — aucun calcul d'argent, aucun accès base, aucun statut touché
(règle #4). ``chiffres`` est ``chiffres_cles(synthese_ci)`` (``None`` hors
C&I : chaque fonction rend alors la valeur résidentielle d'hier, octet pour
octet).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: ACAL1217 / ACAL1266 — drapeau de RENDU (``etude_params``) posé par la
#: migration ventes 0164 sur tout devis NON brouillon : son PDF garde le texte
#: que le client a reçu (adresse et téléphone bruts du une-page, double liste
#: du point d'eau agricole). Un devis neuf ne le porte pas : texte corrigé.
DRAPEAU_PDF_HISTORIQUE_LOT10 = "regles_pdf_historique_lot10"


def pdf_historique_lot10(etude):
    """Rendre le texte d'AVANT le lot 10 ? Vrai pour un devis marqué par la
    migration 0164 et pour une étude vide (la migration n'y écrit rien : un
    envoyé sans étude garde lui aussi le texte reçu, à l'octet)."""
    return not isinstance(etude, dict) or not etude or bool(etude.get(DRAPEAU_PDF_HISTORIQUE_LOT10))


def adresse(adresse_esc, ville_esc, historique=True):
    """ACAL1217 — l'adresse du une-page : jointe à la ville sans répéter un
    morceau (``theme.join_meta``, comme ``couverture.identite_client``) ;
    ``historique`` : l'adresse brute d'hier, octet pour octet."""
    if historique:
        return adresse_esc
    from ..residential import theme
    return theme.join_meta(adresse_esc, ville_esc, sep=", ")


def lire_synthese(data, mode_installation):
    """``(synthese_ci, chiffres_cles)`` d'un devis commercial / industriel,
    ``(None, None)`` hors C&I. CIQ210 — une synthèse illisible ⇒ dicts VIDES
    ⇒ vignettes omises, jamais un repli sur la production par ville ou
    l'économie BT/60 %."""
    if str(mode_installation or "").strip().lower() not in (
            "commercial", "industriel"):
        return None, None
    try:
        from .synthese import chiffres_cles, synthese_ci
        synthese = synthese_ci(data) or {}
        return synthese, chiffres_cles(synthese)
    except Exception:  # noqa: BLE001 — un rendu ne casse jamais ici (D-ENF22-BLE001)
        logger.warning("ci.onepage.lire_synthese : erreur ignorée (mode "
                       "dégradé)", exc_info=True)
        return {}, {}


def _doc(langue, libelles):
    """La langue et les libellés du document sous la forme que lisent les
    morceaux partagés des couvertures C&I (``ci.couverture``)."""
    return {"langue_sortie": langue, "libelles_document": libelles}


def kwc(kwc_txt, L, chiffres):
    """AMOT84 — « 65,32 kWp » dans un une-page C&I anglais (comme son
    titre) ; « 65,32 kWc » en français et en résidentiel."""
    if chiffres is None:
        return f"{kwc_txt} kWc"
    return L("res_n_kwc").format(n=kwc_txt)


def unite_kwc(L, chiffres):
    """AMOT84 — l'unité du « Prix par kWc » (« MAD/kWp » en anglais)."""
    return "kWc" if chiffres is None else L("res_n_kwc").format(n="").strip()


def unite_kwh_an(langue, L):
    """AMOT84 — « kWh/yr » en anglais ; « kWh/an » français inchangé."""
    return " kWh/an" if langue == "fr" else L("ci_unite_kwh_an")


def annees(texte_unite, langue, valeur):
    """CPDF — « ans » du une-page C&I accordé au nombre (arabe « سنة » hors
    3..10 ans entiers), la règle des couvertures C&I."""
    from .couverture import annees_accordees
    return annees_accordees(texte_unite, langue, valeur)


def legende_retour(chiffres, L):
    """AMOT86 (D-ACI-2=a) — postes hors total : sous l'économie, la légende
    de la couverture (sur quel prix le retour sera calculé), sinon ''."""
    if not (chiffres or {}).get("postes_hors_total"):
        return ""
    return ('<div style="font-size:5pt;font-weight:600;'
            'text-transform:none;letter-spacing:0;margin-top:1px;">'
            + L("ci_retour_prix_complet") + "</div>")


def argent(valeur, fnum):
    """AMOT126 (C-AMOT-VER4-040) — l'argent ENTIER du une-page C&I :
    ``montants.fmt_dirhams`` (moitié vers le haut, séparateur de la langue),
    comme la couverture C&I ; devis avant le niveau 12 : ``fnum`` d'hier."""
    try:
        from ..montants import fmt_dirhams, regles_0411_historique
    except ImportError:  # exécution directe du moteur depuis son dossier
        from montants import fmt_dirhams, regles_0411_historique
    return fnum(valeur) if regles_0411_historique() else fmt_dirhams(valeur)


def economie_ttc(chiffres, fnum, L):
    """AMOT95 — base « deux » : sous l'économie HT, « soit N MAD TTC » (la
    TTC servie par ``chiffres_cles``), sinon ''."""
    ttc = (chiffres or {}).get("economie_annuelle_ttc_mad")
    if ttc is None:
        return ""
    return ('<div style="font-size:5pt;font-weight:600;text-transform:none;'
            f'letter-spacing:0;margin-top:1px;">{L("ci_soit")} {argent(ttc, fnum)} '
            f'MAD {L("ci_ttc")}</div>')


def totaux_hors_total(totaux_html, chiffres, synthese, langue, libelles,
                      couleurs):
    """AMOT86 (D-ACI-2=a) — une-page C&I dont des postes restent « à chiffrer
    après la visite » : le bloc de totaux porte le TITRE servi de la
    couverture (``titre_investissement`` : « Investissement hors postes à
    chiffrer après la visite ») et, sous le total, UNE ligne qui nomme ces
    postes sans montant (``ligne_postes_hors_total``). Sans poste : le bloc
    tel quel, octet pour octet. ``couleurs`` = (titre, ligne)."""
    if not (chiffres or {}).get("postes_hors_total"):
        return totaux_html
    from .couverture import ligne_postes_hors_total, titre_investissement
    navy, gris = couleurs
    doc = _doc(langue, libelles)
    base = ((synthese or {}).get("argent") or {}).get("base")
    return (f'<div style="font-size:8pt;font-weight:800;color:{navy};'
            f'margin-bottom:2px;">'
            f'{titre_investissement(doc, synthese, base)}</div>'
            + totaux_html
            + f'<div style="font-size:6.5pt;color:{gris};margin-top:3px;'
              f'line-height:1.3;">'
              f'{ligne_postes_hors_total(doc, synthese)}</div>')


def telephone(brut, chiffres, historique=True):
    """AMOT92 — une-page C&I : le téléphone mis en forme comme sur les
    couvertures (« +212 6 61 23 45 93 ») ; ACAL1217 — le résidentiel aussi,
    sauf ``historique`` (devis envoyé : le brut reçu)."""
    if chiffres is None and historique:
        return brut
    from .couverture import format_telephone
    return format_telephone(brut)
