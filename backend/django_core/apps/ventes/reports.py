"""PV82 — KPI « conçu vs vendu » (Ventes) pour le hub fédéré (ARC40).

Trois tuiles, dérivées UNIQUEMENT de ce que le devis porte déjà — aucun
recalcul solaire, aucune nouvelle donnée :

  * **kWc conçus** — somme du kWc de tout devis qui porte un layout 3D
    finalisé (``Devis.roof_layout`` non nul, Q1/Q5). C'est la puissance
    RÉELLEMENT dessinée par un commercial, pas une estimation de simulateur.
  * **kWc signés** — même somme, restreinte aux devis ``statut='accepte'``.
  * **Taux de conversion des devis conçus** — signés / conçus (en %), CALCULÉ
    à chaque appel, jamais saisi.

PVUNI (fondateur, 18/08/2026) — le kWc d'un devis suit désormais EXACTEMENT
la même priorité que ``quote_engine/builder.py`` (``build_quote_data``,
réparé par l'incident DEV-202608-0007) : les LIGNES du devis d'abord
(``puissance_panneaux_lignes`` — LA MÊME fonction que le PDF/la page, jamais
une seconde dérivation), et le kWc du calepinage (``roof_layout.result.kwc``)
seulement en repli quand le devis ne porte AUCUNE ligne panneau. Cette tuile
lisait auparavant ``etude_params.puissance_kwc`` EN PREMIER — exactement la
valeur que la création depuis calepinage y recopie (base 720 W constante
roofPro, potentiellement différente du panneau réellement vendu) : le résidu
exact de l'incident, côté KPI. ``etude_params.puissance_kwc`` ne reste qu'un
DERNIER repli, pour les rares devis dont le layout stocké ne porte lui-même
aucun ``kwc`` exploitable. Un devis avec layout mais sans kWc résoluble d'
aucun des trois côtés est ignoré (il ne compterait ni pour conçu ni pour
signé — mieux qu'une fausse valeur zéro).

**Aucun prix, aucune marge, aucun ``prix_achat`` ne transite ici** (règle
générateur-only de ``Produit.prix_achat``) : ce module ne lit que les lignes
du devis, ``Devis.roof_layout``, ``Devis.etude_params`` et ``Devis.statut``.
"""
from __future__ import annotations

__all__ = ['kwc_concu_devis', 'kpi_ventes']


def kwc_concu_devis(devis):
    """kWc d'UN devis « conçu » (layout 3D finalisé), ou ``None`` si irrésoluble.

    PVUNI — même priorité que ``quote_engine/builder.py`` (``build_quote_data``) :
    les LIGNES d'abord (``puissance_panneaux_lignes``), le kWc du calepinage
    en repli quand le devis ne porte aucune ligne panneau, et
    ``etude_params.puissance_kwc`` en tout dernier repli.
    """
    from .quote_engine import puissance_panneaux_lignes

    lignes = [li for li in devis.lignes.all() if li.compte_dans_totaux]
    nb_panneaux, watt = puissance_panneaux_lignes(lignes)
    if nb_panneaux > 0:
        return round(nb_panneaux * watt / 1000, 2)

    roof_layout = devis.roof_layout
    if isinstance(roof_layout, dict):
        resultat = roof_layout.get('result') or {}
        kwc = resultat.get('kwc')
        if kwc:
            return float(kwc)

    etude = devis.etude_params or {}
    kwc = etude.get('puissance_kwc')
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
    # PVUNI — ``prefetch_related`` évite un aller-retour DB par devis pour
    # ``kwc_concu_devis`` (lignes-d'abord) : la fiche technique du produit est
    # jointe dès ici, comme ``build_quote_data`` (PV11).
    for devis in Devis.objects.filter(
            company=company, roof_layout__isnull=False).only(
                'etude_params', 'roof_layout', 'statut').prefetch_related(
                    'lignes__produit__fiche_technique'):
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
