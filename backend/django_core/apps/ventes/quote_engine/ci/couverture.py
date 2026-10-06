"""CIQ307 — morceaux HTML COMMUNS aux couvertures commerciale (``c1c``) et
industrielle (``i1``), lus sur ``synthese_ci`` (via ``chiffres_cles``).

Un seul endroit pour : le bandeau « Estimation sous réserve de la visite
technique » + la liste ``a_confirmer`` (D-CIQ-5, W4-22), la ligne de
méthode des taux (C3-07), la tuile payback, la note sur la pointe (CIQ305)
et le motif quand l'argent n'est pas chiffré. Rendu seul — aucun calcul,
aucun statut touché (règle #4).
"""
from __future__ import annotations

from .mentions import TEXTES_POINTE_SANS, TEXTES_VISITE

#: Bandeau (sans le point final de la phrase de la table des mentions).
BANDEAU_RESERVE = TEXTES_VISITE["fr"].rstrip(".")

#: Le texte MT historique (QXMT), gardé tel quel pour un site MT non chiffré.
TEXTE_MT_NON_CHIFFRE = (
    "Dossier raccordé en MOYENNE TENSION : les économies et le retour sur "
    "investissement ne sont pas chiffrés au barème basse tension. "
    "Communiquez-nous {motif} et nous les calculons sur le barème MT.")
TEXTE_NON_CHIFFRE = (
    "Économies et retour sur investissement non chiffrés à ce stade : "
    "communiquez-nous {motif}.")


def bandeau_reserve(d, cle, prefixe):
    """``<div>`` du bandeau quand l'étude est « sous réserve », sinon ''."""
    if not d.get(f"{cle}_sous_reserve"):
        return ""
    a_confirmer = [a for a in d.get(f"{cle}_a_confirmer") or [] if a]
    liste = (f'<div class="{prefixe}-reserve-l">À confirmer : '
             + " · ".join(a_confirmer) + "</div>") if a_confirmer else ""
    return (f'<div class="{prefixe}-reserve"><b>{BANDEAU_RESERVE}</b>'
            f'{liste}</div>')


def css_bandeau(prefixe, gold, ink, muted):
    return (
        f".{prefixe}-reserve{{margin-bottom:8px;border:1px solid {gold};"
        f"border-radius:10px;background:#FFF9EC;padding:7px 12px;"
        f"font-size:8pt;color:{ink};line-height:1.35;}}"
        f".{prefixe}-reserve-l{{font-size:7pt;color:{muted};margin-top:2px;}}")


def ligne_methode(d, cle, prefixe):
    """Ligne de méthode des taux sous la rangée KPI, ou ''."""
    methode = d.get(f"{cle}_methode")
    return f'<div class="{prefixe}-mtsrc">{methode}</div>' if methode else ""


def _argent_mt(d, cle):
    """Le motif MT s'applique-t-il ? ``synthese_ci`` le dit quand elle existe
    (``<cle>_motif_argent`` posé). Sans synthèse (aucun motif servi), le masque
    ne vient que de la garde QXMT du builder — un dossier dont la tension de
    raccordement DÉCLARÉE est MT : il garde sa mention MOYENNE TENSION."""
    if d.get(f"{cle}_motif_argent"):
        return bool(d.get(f"{cle}_argent_mt"))
    etude = d.get("etude") if isinstance(d.get("etude"), dict) else {}
    tension = str(etude.get("tension_raccordement") or "").strip().lower()
    return tension in ("mt", "ht")


def ligne_non_chiffre(d, cle, prefixe):
    """Le motif quand l'argent n'est pas chiffré (``masquer_economies``)."""
    motif = d.get(f"{cle}_motif_argent") or "vos 12 dernières factures"
    gabarit = (TEXTE_MT_NON_CHIFFRE if _argent_mt(d, cle)
               else TEXTE_NON_CHIFFRE)
    return f'<div class="{prefixe}-mtsrc">{gabarit.format(motif=motif)}</div>'


def note_pointe(d, cle):
    """La note sur la pointe selon la composition servie (CIQ305)."""
    return d.get(f"{cle}_note_pointe") or TEXTES_POINTE_SANS["fr"]


def ans(valeur):
    """« 3 » / « 3,4 » — le payback servi, sans arrondi propre."""
    texte = f"{valeur:g}" if isinstance(valeur, (int, float)) else str(valeur)
    return texte.replace(".", ",")


def tuiles_argent(d, cle, kpi, fmt):
    """Tuiles « Économies estimées / an (base) » et « Retour estimé », ou []
    (argent non servi ⇒ tuiles OMISES, jamais un « 0 », QJR119)."""
    if d.get(f"{cle}_masquer_economies"):
        return []
    tuiles = []
    economies = d.get(f"{cle}_economies")
    if economies is not None:
        base = d.get(f"{cle}_economie_base")
        libelle = "Économies estimées / an" + (f" ({base})" if base else "")
        tuiles.append(kpi(fmt(economies), "&nbsp;MAD", libelle,
                          "economie_annuelle"))
    payback = d.get(f"{cle}_payback")
    if payback is not None:
        tuiles.append(kpi(ans(payback), "&nbsp;ans", "Retour estimé",
                          "payback_ans"))
    return tuiles
