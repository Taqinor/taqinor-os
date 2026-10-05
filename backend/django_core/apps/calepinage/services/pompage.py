"""CAL155-158 — dimensionnement du pompage solaire, côté module.

CE QUE CE FICHIER NE RECODE PAS
--------------------------------
Le calcul du volume pompé heure par heure existe déjà et reste la SEULE
source : ``apps.ventes.solar_design.pumping_cycle_yield`` (débit × profil
horaire pondéré par l'irradiation, ou mode PLAT débit × heures). Ce module
ne fait qu'ALIMENTER ses paramètres avec des données RÉELLES — besoin en eau
saisi, HMT calculée depuis un puits, facteurs mensuels PVGIS, pompe/variateur
assortis — jamais un second calcul de volume.

ZÉRO CHIFFRE INVENTÉ (CLAUDE.md)
----------------------------------
Chaque fonction de ce fichier documente sa source : ``saisie`` (l'utilisateur
a tapé la valeur), ``fiche`` (la fiche technique/catalogue du produit),
``pvgis`` (l'irradiation réelle du site) — jamais une valeur par défaut
inventée. Une donnée manquante fait tomber le résultat vers ``None`` (la
carte correspondante disparaît côté écran), jamais vers 0 ni vers une
hypothèse tacite.

Fonctions PURES (pas de requête, pas d'écriture) : les appelants (vues,
sélecteurs) construisent les entrées depuis ``apps.stock.selectors`` et
``apps.parametres.pvgis_profils``, jamais l'inverse.

AGR109 — LE MOTEUR A DÉMÉNAGÉ dans le noyau pur ``core.pompage``
(``hydraulique``, ``selection``, ``volumes``), partagé par ventes ET calepinage.
Ce module garde des RÉ-EXPORTS (appelants inchangés, comportement
octet-identique) et ne porte plus en propre que :func:`volumes_mensuels` et
:func:`hmt_du_puits`, qui ALIMENTENT le noyau avec la saisie de l'écran.

AGR125 — MÊME CALCUL QUE LE DEVIS : les volumes viennent de
``core.pompage.volumes.production_mensuelle`` (heure par heure sur le profil
PVGIS du site, lois de similitude de la courbe) et la HMT de
``core.pompage.hydraulique.hmt_composantes`` — les MÊMES fonctions, nourries
du MÊME profil (``apps.ventes.domain.pompage.profils_horaires_site``), que
``POST /ventes/etude-pompage/preview/`` (AGR121). L'ancien « volume plat ×
part mensuelle PVGIS » (``pompage_mensuel_pvgis``) est supprimé : il aurait
publié un second volume, différent de celui du devis.
"""
from __future__ import annotations

from core.pompage.hydraulique import (  # noqa: F401 — ré-exports AGR109
    _CHAMPS_PUITS_REQUIS,
    _debit_a_hmt,
    _flottant,
    debit_a_hmt,
    hmt_composantes,
    hmt_puits_iteree,
)
from core.pompage.selection import (  # noqa: F401 — ré-exports AGR109
    TENSION_MONO_V,
    TENSION_TRI_V,
    _RE_TENSION_MONO,
    _RE_TENSION_TRI,
    _a_prix,
    _tension_alim,
    selection_pompe,
    selection_variateur,
    tension_produit,
)
from core.pompage.volumes import (  # noqa: F401 — ré-exports AGR109
    JOURS_PAR_MOIS,
    couverture_besoin_eau,
    production_mensuelle,
    pumping_cycle_yield,
)


# ═══════════════════════════════════════════════════════════════════════════
# AGR125 — la HMT de l'écran par le MÊME calcul que le devis (AGR111).
# ═══════════════════════════════════════════════════════════════════════════

#: Libellé de chaque composante, pour NOMMER ce qui manque à l'écran.
LIBELLES_COMPOSANTES_HMT = {
    'niveau_dynamique_m': 'niveau dynamique (ou niveau statique + rabattement spécifique)',
    'denivele_m': 'dénivelé / hauteur de refoulement',
    'pertes_lineaires_m': ('pertes de charge (longueur de conduite + coefficient de '
                           'frottement, ou diamètre et matériau)'),
    'pertes_singulieres_m': 'pertes singulières',
    'pression_service_m': 'pression de service',
}


def hmt_du_puits(*, hmt_saisie=None, debit_m3h=None, niveau_statique_m=None,
                 niveau_dynamique_m=None, coefficient_rabattement_m_par_m3h=None,
                 longueur_tuyauterie_m=None, coefficient_frottement=None,
                 hauteur_refoulement_m=None, denivele_m=None,
                 diametre_interieur_mm=None, materiau_conduite=None,
                 c_hazen_williams=None, pertes_singulieres_m=None,
                 pression_service_bar=None):
    """AGR125 — la saisie de l'écran passée à ``hmt_composantes`` (AGR111).

    Correspondance des champs CAL156 de l'écran : ``coefficient_rabattement``
    = rabattement spécifique, ``longueur_tuyauterie`` = longueur de conduite,
    ``hauteur_refoulement`` = dénivelé (si ``denivele_m`` n'est pas saisi).
    Les pertes singulières et la pression de service n'ont AUCUN défaut :
    absentes, la HMT retombe sur la saisie (``source: 'saisie'``) et
    ``manquantes`` nomme ce qui manque — exactement comme le devis.

    Rend la forme ``hmt`` du contrat ``calepinage_pompage.json`` :
    ``{hmt_m, source, composantes, debit_convergence_m3h, iterations}`` plus
    ``manquantes`` et ``alertes`` (lues par la vue, retirées de la réponse).
    """
    resultat = hmt_composantes(
        hmt_saisie=hmt_saisie, debit_m3h=debit_m3h,
        niveau_dynamique_m=niveau_dynamique_m,
        niveau_statique_m=niveau_statique_m,
        rabattement_specifique_m_par_m3h=coefficient_rabattement_m_par_m3h,
        denivele_m=denivele_m if denivele_m is not None else hauteur_refoulement_m,
        longueur_conduite_m=longueur_tuyauterie_m,
        diametre_interieur_mm=diametre_interieur_mm,
        materiau_conduite=materiau_conduite, c_hazen_williams=c_hazen_williams,
        coefficient_frottement=coefficient_frottement,
        pertes_singulieres_m=pertes_singulieres_m,
        pression_service_bar=pression_service_bar)
    calculee = resultat['source'] == 'calculee'
    return {
        'hmt_m': resultat['valeur_m'],
        'source': resultat['source'],
        'composantes': resultat['composantes'] if calculee else None,
        'debit_convergence_m3h': resultat['debit_convergence_m3h'],
        'iterations': resultat['iterations'],
        'manquantes': resultat['manquantes'],
        'alertes': resultat['alertes'],
    }


# ═══════════════════════════════════════════════════════════════════════════
# AGR125 — les 12 volumes par le MÊME calcul que le devis (AGR114).
# ═══════════════════════════════════════════════════════════════════════════

def volumes_mensuels(*, debit_hmt_m3h, pumping_hours=None, courbe_pompe=None,
                     hmt_m=None, kwc=None, p_plaque_kw=None, rendement_mppt=None,
                     salissure_pct=None, profils_horaires=None,
                     source_irradiation=None, jours_par_mois=None):
    """AGR125 — 12 volumes mensuels : production PHYSIQUE + calcul plat.

    ``m3_mois_pvgis`` porte désormais la production PHYSIQUE de
    ``production_mensuelle`` (heure par heure sur ``profils_horaires``, le
    profil PVGIS du site fourni par l'appelant — le MÊME que celui du devis,
    ``apps.ventes.domain.pompage.profils_horaires_site``) : m³/jour du mois ×
    jours du mois. Le calcul PLAT historique (débit × heures) reste publié
    (``m3_jour_plat``, ``m3_mois_plat``), jamais remplacé en silence, avec
    l'écart mois par mois.

    ``m3_mois_pvgis`` vaut ``None`` (avertissement nommé) quand le profil
    PVGIS du site est indisponible, ou que le kWc du champ / la puissance de
    plaque de la pompe manquent : jamais un volume pondéré inventé.
    """
    jours = list(jours_par_mois or JOURS_PAR_MOIS)
    plat = pumping_cycle_yield(debit_hmt_m3h=debit_hmt_m3h,
                               pumping_hours=pumping_hours,
                               days_in_month=jours_par_mois)
    warnings = list(plat['warnings'])
    m3_mois = None
    source = None
    if profils_horaires is None:
        warnings.append(
            "irradiation PVGIS indisponible pour ce site (ni coordonnées ni "
            "ville reconnue) — m³/jour reste le calcul plat (débit × heures), "
            "aucune production heure par heure publiée")
    else:
        production = production_mensuelle(
            kwc=kwc, profils_horaires=profils_horaires,
            courbe_pompe=courbe_pompe, hmt_m=hmt_m, p_plaque_kw=p_plaque_kw,
            rendement_mppt=rendement_mppt, salissure_pct=salissure_pct)
        journaliers = production['m3_jour_mois']
        if journaliers is None or production['source_irradiation'] != 'pvgis':
            warnings.append(production['motif']
                            or 'production heure par heure non calculée')
        else:
            m3_mois = [round(journaliers[i] * jours[i], 1) for i in range(12)]
            source = source_irradiation
            warnings.extend(production['etiquettes'])

    ecarts = None
    if plat['monthly_m3'] is not None and m3_mois is not None:
        ecarts = [round(m3_mois[i] - plat['monthly_m3'][i], 1)
                  for i in range(12)]
    return {
        'm3_jour_plat': plat['daily_m3'],
        'm3_mois_plat': plat['monthly_m3'],
        'm3_mois_pvgis': m3_mois,
        'source_irradiation': source,
        'ecart_m3_mois': ecarts,
        'warnings': warnings,
    }
