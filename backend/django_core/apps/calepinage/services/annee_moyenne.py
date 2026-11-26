"""R3-01 / R3-17 — les énergies PUBLIÉES sur l'ANNÉE MOYENNE de la fenêtre.

ACAL54 a ramené le P50, le mensuel et le par pan à l'année moyenne d'une
fenêtre météo de N années (``production.total.annees_fenetre``). Les autres
énergies CUMULÉES restaient la SOMME des N années : la cascade de pertes
(``kwh_avant``, ``kwh_apres``, ``perte_kwh``, ses postes lisibles, les
énergies des entrées d'étape, l'irradiation incidente), les cascades par pan
du bloc ``ombrage`` et l'irradiation du plan du bloc ``performance`` — dix
fois trop grandes sur une fenêtre 2014-2023, et imprimées par le rapport
d'étude et le diagramme de pertes. (La production module par module, et donc
par chaîne, MPPT et onduleur, est ramenée À LA SOURCE :
``simulation_modules.production_module_par_module``.)

La division a lieu à la PUBLICATION, jamais dans le calcul : la chaîne, la
validation PVcalc, le PR et les pourcentages tournent sur les sommes, comme
avant ; seuls les nombres publiés changent. Une année type (N = 1) n'est pas
touchée (identique au bit). Aucune grandeur qui n'est pas une énergie
cumulée n'est divisée : pourcentages, ratios, puissances, comptes (sauf les
heures de :data:`CLES_COMPTE_PAR_AN`, ACAL1960) et températures restent tels quels.
"""
from __future__ import annotations

#: Les clés d'ÉNERGIE CUMULÉE sur la série (kWh, ou kWh/m² pour
#: l'irradiation) que publie une cascade — étapes, entrées d'étape
#: (``etapes/onduleur.py`` distribution, ``auxiliaires.py``,
#: ``indisponibilite.py``, ``mppt.py``, ``transformateur.py``) et postes
#: lisibles (``regroupement_pertes.py``). Liste FERMÉE : une clé neuve ne se
#: divise qu'une fois ajoutée ici. ACAL1605 — ``energie_ecretee_kwh`` de
#: l'histogramme de l'onduleur (``distribution.histogramme_puissance``) ; le
#: plafond d'injection (bloc ``autoconsommation``, déjà ``_par_an``) ne passe
#: pas par la cascade publiée : il n'est pas redivisé.
CLES_ENERGIE_CASCADE = frozenset((
    'kwh_avant', 'kwh_apres', 'perte_kwh', 'irradiation_incidente_kwh_m2',
    'depart_kwh', 'arrivee_kwh', 'energie_kwh', 'energie_totale_kwh',
    'energie_ecretee_kwh',
    'energie_jour_kwh', 'energie_nuit_kwh', 'energie_perdue_kwh',
    'energie_sous_demarrage_kwh', 'energie_sous_demarrage_deja_retiree_kwh',
    'energie_a_vide_kwh', 'energie_en_charge_kwh',
))

#: ACAL1960 — les COMPTES d'heures de la cascade dits « par an » : l'écrêtage
#: compte ses heures sur toute la fenêtre (87 600 h pour 2014-2023) ; publiées,
#: elles sont ramenées à l'année moyenne comme les énergies (liste FERMÉE).
CLES_COMPTE_PAR_AN = frozenset(('heures_ecretees',))

#: Les décimales publiées — celles de la cascade (``chaine_pertes._arrondi``).
DECIMALES = 3


def moyenne(valeur, annees):
    """``valeur`` ramenée à l'année moyenne de ``annees`` ans (``None`` et
    N ≤ 1 : rendue telle quelle, sans arrondi)."""
    if valeur is None or not annees or annees <= 1:
        return valeur
    return round(float(valeur) / annees, DECIMALES)


def _est_nombre(valeur):
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


def _annees_publiees(blocs):
    total = ((blocs or {}).get('production') or {}).get('total') or {}
    annees = total.get('annees_fenetre')
    return int(annees) if _est_nombre(annees) and annees >= 1 else 1


def _ramener(noeud, annees, vus):
    """Divise EN PLACE les énergies de :data:`CLES_ENERGIE_CASCADE` de
    ``noeud`` (récursif). ``vus`` : un objet partagé par deux blocs (copie
    superficielle d'une étape) n'est divisé qu'UNE fois."""
    if not isinstance(noeud, (dict, list)) or id(noeud) in vus:
        return
    vus.add(id(noeud))
    enfants = noeud.values() if isinstance(noeud, dict) else noeud
    if isinstance(noeud, dict):
        for cle, valeur in list(noeud.items()):
            if (cle in CLES_ENERGIE_CASCADE or cle in CLES_COMPTE_PAR_AN) and _est_nombre(valeur):
                noeud[cle] = moyenne(valeur, annees)
    for enfant in list(enfants):
        _ramener(enfant, annees, vus)


def publier_a_l_annee_moyenne(blocs):
    """Les blocs de ``simuler_calepinage`` ramenés à l'année moyenne, EN
    PLACE, juste avant leur écriture. Rend ``blocs``."""
    annees = _annees_publiees(blocs)
    if annees <= 1:
        return blocs
    vus = set()
    _ramener(blocs.get('cascade'), annees, vus)
    for ligne in ((blocs.get('ombrage') or {}).get('par_pan') or ()):
        if isinstance(ligne, dict):
            _ramener(ligne.get('cascade'), annees, vus)
    performance = blocs.get('performance')
    if isinstance(performance, dict) and _est_nombre(
            performance.get('irradiation_plan_kwh_m2')):
        performance['irradiation_plan_kwh_m2'] = moyenne(
            performance['irradiation_plan_kwh_m2'], annees)
    return blocs


def _arrivee_de_la_cascade(cascade):
    etapes = [etape for etape in ((cascade or {}).get('etapes') or ())
              if isinstance(etape, dict)]
    for etape in reversed(etapes):
        if not etape.get('motif_omission') and _est_nombre(
                etape.get('kwh_apres')):
            return float(etape['kwh_apres'])
    premiere = etapes[0].get('kwh_avant') if etapes else None
    return float(premiere) if _est_nombre(premiere) else None


def etat_des_energies(resultat):
    """Q2 (lecture seule) — ce que dit un ``resultat`` RANGÉ : ``None`` sans
    simulation ou en année type (N = 1) ; sinon ``{annees, mode, calcule_le,
    p50_kwh, arrivee_kwh, fenetre_entiere}``. ``fenetre_entiere`` est vrai
    quand l'arrivée de la cascade vaut ≈ N fois le P50 (énergies publiées
    avant cette correction : somme des N années), faux quand elle vaut ≈ le
    P50, ``None`` quand rien ne permet de le dire."""
    resultat = resultat if isinstance(resultat, dict) else {}
    annees = _annees_publiees(resultat)
    if annees <= 1:
        return None
    total = (resultat.get('production') or {}).get('total') or {}
    p50 = total.get('p50_kwh')
    arrivee = _arrivee_de_la_cascade(resultat.get('cascade'))
    fenetre_entiere = None
    if _est_nombre(p50) and p50 > 0 and arrivee is not None:
        # Le rapport vaut ≈ 1 (année moyenne) ou ≈ N (somme) : le seuil est
        # leur milieu.
        fenetre_entiere = arrivee / float(p50) >= (annees + 1) / 2.0
    return {
        'annees': annees,
        'mode': (resultat.get('meteo') or {}).get('mode'),
        'calcule_le': (resultat.get('simulation') or {}).get('calcule_le'),
        'p50_kwh': p50,
        'arrivee_kwh': arrivee,
        'fenetre_entiere': fenetre_entiere,
    }
