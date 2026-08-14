"""PV82 — KPI « conçu vs vendu » (Ventes) pour le hub fédéré (ARC40).

Trois tuiles, dérivées UNIQUEMENT du kWc déjà stocké sur ``Devis`` — aucun
recalcul solaire, aucune nouvelle donnée :

  * **kWc conçus** — somme du kWc de tout devis qui porte un layout 3D
    finalisé (``Devis.roof_layout`` non nul, Q1/Q5). C'est la puissance
    RÉELLEMENT dessinée par un commercial, pas une estimation de simulateur.
  * **kWc signés** — même somme, restreinte aux devis ``statut='accepte'``.
  * **Taux de conversion des devis conçus** — signés / conçus (en %), CALCULÉ
    à chaque appel, jamais saisi.

Le kWc d'un devis suit exactement la même priorité que
``quote_engine/builder.py`` (Q5) : ``etude_params.puissance_kwc`` d'abord (la
valeur éventuellement affinée/saisie), sinon ``roof_layout.result.kwc`` (la
sortie brute de l'outil roofPro11). Un devis avec layout mais sans kWc
résoluble des deux côtés est ignoré (il ne compterait ni pour conçu ni pour
signé — mieux qu'une fausse valeur zéro).

**Aucun prix, aucune marge, aucun ``prix_achat`` ne transite ici** (règle
générateur-only de ``Produit.prix_achat``) : ce module ne lit que
``Devis.roof_layout``, ``Devis.etude_params`` et ``Devis.statut``.
"""
from __future__ import annotations

__all__ = ['kwc_concu_devis', 'kpi_ventes']


def kwc_concu_devis(devis):
    """kWc d'UN devis « conçu » (layout 3D finalisé), ou ``None`` si irrésoluble.

    Même priorité que ``quote_engine/builder.py`` (Q5) :
    ``etude_params.puissance_kwc`` d'abord, sinon ``roof_layout.result.kwc``.
    """
    etude = devis.etude_params or {}
    kwc = etude.get('puissance_kwc')
    if kwc:
        return float(kwc)

    roof_layout = devis.roof_layout
    if isinstance(roof_layout, dict):
        resultat = roof_layout.get('result') or {}
        kwc = resultat.get('kwc')
        if kwc:
            return float(kwc)
    return None


def kpi_ventes(company):
    """Tuiles KPI « conçu vs vendu » du domaine Ventes pour le hub fédéré (ARC40).

    Contrat de tuile : ``{id, label, valeur, unite?}``. Le hub
    (``apps/reporting/reports.py::kpi_federes``) résout ce callable par son
    chemin dotted déclaré dans ``apps/ventes/platform.py`` — il n'importe
    AUCUN modèle d'``apps.ventes`` avant l'appel.
    """
    from .models import Devis

    kwc_concus = []
    kwc_signes = []
    for devis in Devis.objects.filter(
            company=company, roof_layout__isnull=False).only(
                'etude_params', 'roof_layout', 'statut'):
        kwc = kwc_concu_devis(devis)
        if kwc is None:
            continue
        kwc_concus.append(kwc)
        if devis.statut == Devis.Statut.ACCEPTE:
            kwc_signes.append(kwc)

    nb_concus = len(kwc_concus)
    nb_signes = len(kwc_signes)
    taux_conversion = round(nb_signes / nb_concus * 100, 2) if nb_concus else 0.0

    return [
        {'id': 'ventes_kwc_concus', 'label': 'kWc conçus',
         'valeur': round(sum(kwc_concus), 2), 'unite': 'kWc'},
        {'id': 'ventes_kwc_signes', 'label': 'kWc signés',
         'valeur': round(sum(kwc_signes), 2), 'unite': 'kWc'},
        {'id': 'ventes_taux_conversion_concus',
         'label': 'Taux de conversion des devis conçus',
         'valeur': taux_conversion, 'unite': '%'},
    ]
