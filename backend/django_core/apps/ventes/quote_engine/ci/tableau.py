"""Lignes « Tableau de protection AC/DC » (R2) et « Supervision & comptage »
(R3) du document CLIENT C&I.

Demande fondateur (Reda, 28/10/2026 — le devis 460, boulangerie, lisait 21
lignes) : sur un devis COMMERCIAL ou INDUSTRIEL, le client lit UNE ligne
« Tableau de protection AC/DC » qui regroupe le coffret DC, le coffret AC, le
disjoncteur AC, la protection DC et le parafoudre DC (par chaîne), le
parafoudre AC et la mise à la terre — les lignes dont le produit porte un
``role_ci`` de ``moteur_ci.composition.ROLES_TABLEAU_CI``, jamais reconnues à
leur désignation.

R3 (fondateur, 28/10/2026 soir) — le Smart Meter SORT du tableau : le
comptage / limitation d'injection et la supervision (clé wifi par onduleur,
logger central) forment UNE ligne « Supervision & comptage »
(``ROLES_SUPERVISION_CI``), même mécanique.

Quantité 1, P.U. HT = Σ (quantité × P.U. HT), une ligne PAR TAUX de TVA, et
un champ ``sous_lignes`` (désignation, quantité, unité, jamais un prix) que
les PDF impriment en détail indenté sous la ligne ; la page publique peut
l'ignorer sans casser. Fait de RENDU seul : les ``LigneDevis`` restent une
par composant (prix catalogue, stock, marge, chantier intacts) et les totaux
``totaux_*`` ne sont jamais recalculés. Résidentiel et agricole : inchangés.

Module PUR (même patron que ``ci/installation.py``).
"""
from __future__ import annotations

from html import escape

from apps.ventes.moteur_ci.composition import (
    ROLES_SUPERVISION_CI, ROLES_TABLEAU_CI,
)

from .installation import regrouper_roles

#: Libellé de la ligne regroupée, dans la langue du document.
LIBELLE_TABLEAU = {
    "fr": "Tableau de protection AC/DC",
    "en": "AC/DC protection switchboard",
    "ar": "لوحة الحماية AC/DC",
}

ROLE_TABLEAU = "tableau_ci"


#: R3.4 — libellé de la ligne « Supervision & comptage ».
LIBELLE_SUPERVISION = {
    "fr": "Supervision & comptage",
    "en": "Monitoring & metering",
    "ar": "المراقبة والعدّ",
}

ROLE_SUPERVISION = "supervision_ci"


def regrouper_tableau(items, langue="fr"):
    """``items`` avec les organes du tableau regroupés (une ligne par taux de
    TVA, ``sous_lignes`` = les composants). Sans organe : ``items`` tel quel
    (même objet)."""
    return regrouper_roles(items, ROLES_TABLEAU_CI, LIBELLE_TABLEAU,
                           ROLE_TABLEAU, langue, sous_lignes=True)


def regrouper_supervision(items, langue="fr"):
    """R3.4 — ``items`` avec le comptage (Smart Meter) et la supervision (clé
    wifi, logger) regroupés en « Supervision & comptage » (une ligne par taux
    de TVA, ``sous_lignes`` = les composants). Sans ligne du groupe :
    ``items`` tel quel (même objet)."""
    return regrouper_roles(items, ROLES_SUPERVISION_CI, LIBELLE_SUPERVISION,
                           ROLE_SUPERVISION, langue, sous_lignes=True)


def _quantite(valeur):
    try:
        q = float(valeur or 0)
    except (TypeError, ValueError):
        return ""
    return str(int(q)) if q == int(q) else f"{q:g}"


def sous_lignes_html(it, font_pt, couleur, retrait_px=6):
    """Le détail indenté d'une ligne regroupée pour les gabarits PDF (un
    ``<div>`` par composant : « 2 × Coffret DC »), ou '' sans sous-lignes.
    Les désignations arrivent DÉJÀ échappées par le gabarit (un seul
    échappement, jamais deux) ; l'unité, qui ne passe par aucun gabarit, est
    échappée ici."""
    sous_lignes = it.get("sous_lignes") if isinstance(it, dict) else None
    if not sous_lignes:
        return ""
    return "".join(
        f'<div class="ci-sl" style="font-size:{font_pt}pt;color:{couleur};'
        f'font-weight:400;padding-left:{retrait_px}px;line-height:1.25;">'
        f'{_quantite(sl.get("quantite"))}&#160;×&#160;'
        f'{sl.get("designation") or ""}'
        + (f' {escape(str(sl["unite"]))}'
           if sl.get("unite") not in (None, "", "u") else "")
        + '</div>'
        for sl in sous_lignes if isinstance(sl, dict))
