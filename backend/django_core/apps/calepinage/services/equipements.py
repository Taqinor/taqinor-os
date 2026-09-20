"""CAL243 — sert l'agrégat ``équipements`` du contrat CAL120.

CE QUE CE MODULE PRODUIT
-------------------------
Le panneau, l'onduleur, la batterie et l'optimiseur RETENUS par le devis lié
au calepinage — un par famille, avec la complétude champ par champ et la
SOURCE de chaque valeur (contrat
``contract_samples/calepinage_equipements.json``, posé seul sur ``main`` par
CAL120 avant cette tâche, PACT10/PACT11).

D'OÙ VIENT L'ÉQUIPEMENT « RETENU »
-----------------------------------
Le document ``roof_layout`` (schéma v2) ne porte AUCUNE référence produit —
seule la géométrie. L'équipement chiffré vit sur le DEVIS lié
(``Calepinage.devis``) : ce module lit ses lignes PRODUIT via le sélecteur
cross-app ``apps.ventes.selectors.lignes_produits_calepinage`` (jamais un
import de ``apps.ventes.models``), classe chaque ligne par la famille de sa
fiche technique (``apps.stock.selectors.type_fiche_produit`` :
``module``/``onduleur``/``batterie``/``optimiseur``) et retient la PREMIÈRE
ligne de chaque famille — un devis ne porte normalement qu'une seule
référence par famille sur son option par défaut ; une famille sans ligne
correspondante reste ``None`` (jamais un objet à moitié rempli).

Sans devis lié (calepinage autonome, ou devis d'une autre société) les
quatre familles valent ``None`` et ``devis`` vaut ``None`` — jamais une
famille inventée.

LA GARDE PRIX D'ACHAT (CAL122)
--------------------------------
``apps.stock.selectors.specs_for_produit`` ne lit JAMAIS ``Produit.prix_achat``
— le bloc ``specs`` de ce module ne peut donc structurellement pas le
reprendre. Le test de surface CAL122 vérifie ce module en plus de tous les
autres.
"""
from __future__ import annotations

from apps.stock.selectors import specs_for_produit, type_fiche_produit
from apps.ventes.selectors import get_devis_by_pk, lignes_produits_calepinage

#: Famille de fiche technique -> clé de l'agrégat. Les familles hors de ce
#: dictionnaire (``''``, ``'autre'``) ne sont RETENUES pour aucune famille —
#: on préfère l'omission à un équipement mal rangé.
BUCKET_PAR_TYPE_FICHE = {
    'module': 'panneau',
    'onduleur': 'onduleur',
    'batterie': 'batterie',
    'optimiseur': 'optimiseur',
}

#: Les familles de l'agrégat, dans l'ordre du contrat CAL120.
FAMILLES = ('panneau', 'onduleur', 'batterie', 'optimiseur')

#: Le contrat de champs COMPLET de chaque famille — même liste, au caractère
#: près, que la docstring de ``specs_for_produit`` (CAL111-118) : c'est ce qui
#: permet de dire « ce champ est manquant » plutôt que « ce champ n'existe
#: pas ». Une clé qui n'y figure jamais n'apparaît dans AUCUNE des deux
#: listes de complétude — c'est voulu, ``specs_for_produit`` ne peut pas la
#: rendre.
CHAMPS_PAR_FAMILLE = {
    'panneau': (
        'vmp_v', 'voc_v', 'isc_a', 'imp_a', 'pmax_wc',
        'temp_coeff_voc_pct_c', 'temp_coeff_pmax_pct_c',
        'longueur_mm', 'largeur_mm', 'epaisseur_mm', 'poids_kg',
        'rendement_pct', 'techno_cellule', 'bifacial', 'noct_c',
        'uc_w_m2k', 'uv_w_m3sk', 'bifacialite_pct',
        'degradation_annuelle_pct', 'degradation_annee1_pct',
        'garantie_pct_a_10_ans', 'garantie_pct_a_25_ans',
    ),
    'onduleur': (
        'n_mppt', 'mppt_v_min', 'mppt_v_max', 'v_max_abs', 'i_max_mppt_a',
        'ac_kw', 'phases', 'rendement_euro_pct', 'v_demarrage_v',
        'isc_max_mppt_a', 'bat_max_charge_kw', 'bat_max_decharge_kw',
        'entrees_par_mppt', 'chaines_max_par_mppt', 's_max_kva',
        'dc_max_kwc',
    ),
    'batterie': (
        'kwh_nominal', 'kwh_usable', 'dod_pct', 'v_nominal',
        'max_charge_kw', 'max_decharge_kw', 'max_modules_par_banc',
        'rendement_ar_pct', 'cycles_publies', 'retention_fin_de_vie_pct',
        'garantie_annees',
    ),
    'optimiseur': (
        'pmax_in_w', 'v_in_min', 'v_in_max', 'i_in_max_a', 'rendement_pct',
        'modules_par_optimiseur',
    ),
}


def _devis_lie(calepinage):
    """Le devis lié au calepinage, borné à SA société — ou ``None``."""
    devis_id = getattr(calepinage, 'devis_id', None)
    if not devis_id:
        return None
    devis = get_devis_by_pk(devis_id)
    if devis is None:
        return None
    company = getattr(calepinage, 'company', None)
    if company is not None and devis.company_id != company.pk:
        return None
    return devis


def _bloc_equipement(ligne):
    """Le bloc ``{produit, designation, quantite, specs, ...}`` d'UNE ligne."""
    produit = ligne['produit']
    famille = BUCKET_PAR_TYPE_FICHE.get(type_fiche_produit(produit))
    if famille is None:
        return None, None

    specs = specs_for_produit(produit)
    contrat = CHAMPS_PAR_FAMILLE[famille]
    champs_renseignes = [champ for champ in contrat if champ in specs]
    champs_manquants = [champ for champ in contrat if champ not in specs]

    sources = {'quantite': 'saisie'}
    sources.update({champ: 'fiche' for champ in champs_renseignes})

    quantite = ligne['quantite']
    bloc = {
        'produit': produit.pk,
        'designation': ligne['designation'] or getattr(produit, 'nom', ''),
        'quantite': float(quantite) if quantite is not None else None,
        'specs': specs,
        'champs_renseignes': champs_renseignes,
        'champs_manquants': champs_manquants,
        'sources': sources,
    }
    return famille, bloc


def equipements_du_calepinage(calepinage):
    """CAL243 — l'agrégat COMPLET du contrat ``calepinage_equipements.json``.

    Lecture PURE : aucune écriture, aucun statut touché. Toujours les six
    clés (``calepinage``, ``devis`` + les quatre familles), jamais une clé
    omise — une famille non retenue vaut ``None``, jamais absente.
    """
    resultat = {famille: None for famille in FAMILLES}
    devis = _devis_lie(calepinage)
    if devis is None:
        return {'calepinage': calepinage.pk, 'devis': None, **resultat}

    for ligne in lignes_produits_calepinage(devis):
        famille, bloc = _bloc_equipement(ligne)
        if famille is None or resultat[famille] is not None:
            # famille inconnue, ou déjà servie par une ligne antérieure — la
            # PREMIÈRE ligne d'une famille est celle qui compte (repli sûr :
            # aucune règle métier ne dit laquelle choisir entre deux lignes
            # de la même famille sur un devis correctement composé).
            continue
        resultat[famille] = bloc

    return {'calepinage': calepinage.pk, 'devis': devis.pk, **resultat}
