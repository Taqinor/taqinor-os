# -*- coding: utf-8 -*-
"""CALX179 — LE RATIO DE PERFORMANCE, au sens de la norme IEC 61724-1.

LE CONSTAT
----------
``services/production.py`` publie déjà un ``performance_ratio`` : rendement
spécifique divisé par irradiation de plan, un rapport JUSTE
dimensionnellement — mais publié NU. Ni la norme qui le définit, ni la
définition du dénominateur, ni la PÉRIODE ne voyagent avec lui, et le contrat
le montre à ``0.799`` sans la moindre provenance. Un PR sans sa période est un
chiffre qu'on ne peut pas contredire : 0,79 sur juillet et 0,79 sur l'année ne
disent pas la même chose.

CE QUE CE MODULE PUBLIE
------------------------
Le bloc ``resultat['performance']`` du contrat
``contract_samples/calepinage_simulation.json`` :

* ``pr`` — rendement FINAL ÷ rendement de RÉFÉRENCE ;
* ``pr_methode`` — ``iec_61724_1``, nommée plutôt que sous-entendue ;
* ``pr_reference`` — la référence CITÉE, publiée telle quelle ;
* ``irradiation_plan_kwh_m2`` — le dénominateur, LISIBLE, sur la période ;
* ``periode`` — explicite dès qu'elle n'est pas annuelle ;
* ``pr_corrige_temperature`` et ``t_cell_moyenne_ponderee_c`` — la variante
  corrigée en température, publiée SEULEMENT si l'étape thermique a tourné.

LA DÉFINITION, ET D'OÙ CHAQUE TERME VIENT
-------------------------------------------
``PR = Yf / Yr``, où ``Yf`` est l'énergie livrée rapportée à la puissance
crête (kWh/kWc) et ``Yr`` l'irradiation reçue DANS LE PLAN des modules
rapportée à l'irradiance de référence STC (1 000 W/m²). Les deux termes
viennent de la MÊME série, celle que la cascade a rendue : l'énergie est lue
sur la colonne que la série DÉCLARE (``services/etapes``, CALX147 — le nom de
cette colonne est publié, parce qu'un PR calculé côté continu n'est pas un PR
calculé côté alternatif), et l'irradiation est la somme de ``gi_w_m2`` sur les
mêmes heures. Rien n'est recopié d'une table.

La variante CORRIGÉE EN TEMPÉRATURE pondère chaque heure du rendement de
référence par ``1 + γ × (T_cellule − 25 °C)`` : elle répond à « ce champ
aurait-il fait mieux sur un site plus froid ? » plutôt qu'à « combien
a-t-il produit ? ». Elle exige DEUX choses, et se tait sans elles : le
coefficient de puissance en température de la FICHE
(``temp_coeff_pmax_pct_c``) et la température de cellule heure par heure
(``t_cell_c``), que seule l'étape thermique (CALX163) écrit sur la série.
Sa présence EST la preuve que l'étape a tourné ; son absence est publiée avec
sa raison, jamais comblée par une hypothèse.

Module PUR : aucune base, aucun réseau, aucun appel PVGIS, aucun chiffre
inventé.
"""
from __future__ import annotations

from apps.calepinage.services import etapes as _etapes
from apps.calepinage.services.thermique import TEMPERATURE_STC_C

#: L'irradiance de RÉFÉRENCE (W/m²) qui définit le rendement de référence
#: dans la norme : ce sont les conditions STC elles-mêmes, pas un réglage.
IRRADIANCE_REFERENCE_W_M2 = 1000.0

#: La colonne d'irradiance DANS LE PLAN des modules (contrat CALX142).
COLONNE_IRRADIANCE = 'gi_w_m2'

#: La colonne de température de cellule (contrat CALX142), écrite par
#: l'étape thermique et par elle seule.
COLONNE_TEMPERATURE = 't_cell_c'

#: Le champ de fiche qui porte le coefficient de puissance en température.
CHAMP_GAMMA = 'temp_coeff_pmax_pct_c'

#: Le nom de la méthode publiée — nommée, jamais sous-entendue.
METHODE = 'iec_61724_1'

#: Les trois formes de période, publiées telles quelles.
PERIODE_ANNUELLE = 'annuelle'

#: LA RÉFÉRENCE, publiée TELLE QUELLE dans ``pr_reference``.
REFERENCE_IEC = (
    'IEC 61724-1 — Performance des systèmes photovoltaïques, partie 1 : '
    'surveillance. Le ratio de performance y est le rapport du rendement '
    'FINAL (énergie livrée rapportée à la puissance crête, en kWh/kWc) au '
    'rendement de RÉFÉRENCE (irradiation reçue dans le plan des modules '
    "rapportée à l'irradiance de référence STC, 1 000 W/m²). PVsyst rappelle "
    'que le PR est défini par cette norme pour les systèmes raccordés au '
    'réseau SANS stockage, et publie depuis une variante corrigée en '
    'température (https://www.pvsyst.com/help/project-design/results/'
    'performance-ratio-pr.html).')

#: Les douze mois, pour qu'une période partielle NOMME les siens.
MOIS_LIBELLES = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                 'juillet', 'août', 'septembre', 'octobre', 'novembre',
                 'décembre')

__all__ = ['IRRADIANCE_REFERENCE_W_M2', 'COLONNE_IRRADIANCE',
           'COLONNE_TEMPERATURE', 'CHAMP_GAMMA', 'METHODE',
           'PERIODE_ANNUELLE', 'REFERENCE_IEC', 'MOIS_LIBELLES',
           'bloc_performance']


# ── les motifs, chacun nommant ce qui manque ───────────────────────────

MOTIF_SERIE_VIDE = (
    "La série ne porte aucune heure : il n'y a ni énergie livrée ni "
    'irradiation reçue à rapporter l\'une à l\'autre.')

MOTIF_ENERGIE = (
    "Aucune colonne d'énergie lisible sur la série : le rendement final "
    "n'est pas mesurable, donc le ratio de performance non plus. Il reste "
    'nul — jamais 0, qui se lirait « ce champ ne produit rien ».')

MOTIF_IRRADIATION = (
    "La série ne porte pas l'irradiance reçue dans le plan des modules "
    f'(« {COLONNE_IRRADIANCE} ») : le rendement de RÉFÉRENCE de la norme est '
    'inconnu, et aucun ratio ne se calcule sans son dénominateur.')

MOTIF_KWC = (
    "La puissance crête posée n'est pas connue : le rendement final se "
    'rapporte à elle, et un ratio de performance sans puissance crête ne '
    'veut rien dire.')

MOTIF_GAMMA = (
    'Le PR corrigé en température n\'est PAS publié : la fiche du module ne '
    f'porte pas son coefficient de puissance en température (« {CHAMP_GAMMA} '
    '»), sans lequel aucune correction thermique n\'est calculable. Champ '
    f'manquant : « fiche_module.{CHAMP_GAMMA} ».')

MOTIF_TEMPERATURE = (
    'Le PR corrigé en température n\'est PAS publié : {heures} heure(s) '
    'recevant de la lumière ne portent pas de température de cellule '
    f'(« {COLONNE_TEMPERATURE} ») — l\'étape thermique n\'a pas tourné sur '
    'toute la série. Aucune heure n\'est corrigée à 25 °C par défaut. Champ '
    f'manquant : « serie_horaire.{COLONNE_TEMPERATURE} ».')


def bloc_performance(serie, *, kwc, fiche_module=None):
    """Le bloc ``resultat['performance']`` — ou ses nulls, motivés.

    Args:
        serie: la série rendue par ``services/chaine_pertes.appliquer_chaine``
            (contrat CALX142). Elle n'est jamais modifiée.
        kwc: la puissance crête RÉELLEMENT posée (kWc). ``None`` ou ``≤ 0`` ⇒
            le PR reste nul avec son motif.
        fiche_module: les specs produit déjà résolues, ou ``{}``. Seul
            ``temp_coeff_pmax_pct_c`` y est lu, et seulement pour la variante
            corrigée en température.

    Returns:
        dict — ``pr``, ``pr_methode``, ``pr_reference``,
        ``irradiation_plan_kwh_m2``, ``periode``, ``colonne_energie``,
        ``motif``, ``motif_pr_corrige_temperature``, plus
        ``pr_corrige_temperature`` et ``t_cell_moyenne_ponderee_c`` UNIQUEMENT
        quand la correction thermique est calculable.

    Ne lève jamais : une entrée absente est une RÉPONSE motivée, pas une
    erreur.
    """
    serie = serie if isinstance(serie, dict) else {}
    fiche = fiche_module if isinstance(fiche_module, dict) else {}
    points = [point for point in (serie.get('points') or ())
              if isinstance(point, dict)]

    colonne = _etapes.colonne_energie(serie)
    heures = _heures(serie)
    irradiation = _irradiation_kwh_m2(points, heures)
    periode = _periode(points)
    puissance = _nombre(kwc)

    bloc = {
        'pr': None,
        'pr_methode': None,
        'pr_reference': None,
        'irradiation_plan_kwh_m2': irradiation,
        'periode': periode,
        'colonne_energie': colonne,
        'motif': '',
        'motif_pr_corrige_temperature': '',
    }

    motif = _motif_du_refus(points, colonne, irradiation, puissance)
    if motif:
        bloc['motif'] = motif
        bloc['motif_pr_corrige_temperature'] = motif
        return bloc

    energie_kwh = _etapes.energie_kwh(serie)
    if energie_kwh is None:
        bloc['motif'] = MOTIF_ENERGIE
        bloc['motif_pr_corrige_temperature'] = MOTIF_ENERGIE
        return bloc

    reference_kwh = puissance * irradiation / (
        IRRADIANCE_REFERENCE_W_M2 / 1000.0)
    bloc['pr'] = round(energie_kwh / reference_kwh, 4)
    bloc['pr_methode'] = METHODE
    bloc['pr_reference'] = REFERENCE_IEC

    corrige, temperature, motif_corrige = _corrige_temperature(
        points, heures, energie_kwh, puissance, fiche)
    bloc['motif_pr_corrige_temperature'] = motif_corrige
    if motif_corrige:
        # La clé est ABSENTE, pas nulle : un PR corrigé à ``null`` se lirait
        # « calculé, puis perdu » là où la vérité est « jamais calculable ».
        return bloc
    bloc['pr_corrige_temperature'] = corrige
    bloc['t_cell_moyenne_ponderee_c'] = temperature
    return bloc


# ── le rendement de référence, heure par heure ─────────────────────────

def _heures(serie):
    """La durée d'un point, en heures."""
    pas = _nombre(serie.get('pas_minutes')) or _etapes.PAS_MINUTES_PVGIS
    return float(pas) / 60.0


def _irradiation_kwh_m2(points, heures):
    """``Σ G(i) × Δt`` en kWh/m², ou ``None`` si la colonne est illisible."""
    total = 0.0
    lues = 0
    for point in points:
        valeur = _nombre(point.get(COLONNE_IRRADIANCE))
        if valeur is None:
            continue
        total += valeur
        lues += 1
    if not lues:
        return None
    return round(total * heures / 1000.0, 3)


def _motif_du_refus(points, colonne, irradiation, puissance):
    """Le premier motif qui empêche TOUT ratio, ou ``''``."""
    if not points:
        return MOTIF_SERIE_VIDE
    if colonne is None:
        return MOTIF_ENERGIE
    if irradiation is None or irradiation <= 0.0:
        return MOTIF_IRRADIATION
    if puissance is None or puissance <= 0.0:
        return MOTIF_KWC
    return ''


# ── la variante CORRIGÉE EN TEMPÉRATURE ────────────────────────────────

def _corrige_temperature(points, heures, energie_kwh, puissance, fiche):
    """``(pr corrigé, T_cellule moyenne, motif)`` — jamais les deux à la fois.

    La température moyenne est PONDÉRÉE PAR L'IRRADIANCE : une heure de nuit
    et une heure de plein soleil ne pèsent pas pareil sur le comportement
    thermique d'un champ.
    """
    gamma = _nombre(fiche.get(CHAMP_GAMMA))
    if gamma is None:
        return None, None, MOTIF_GAMMA

    reference = 0.0
    somme_t_g = 0.0
    somme_g = 0.0
    sans_temperature = 0
    for point in points:
        irradiance = _nombre(point.get(COLONNE_IRRADIANCE))
        if irradiance is None or irradiance <= 0.0:
            continue
        temperature = _nombre(point.get(COLONNE_TEMPERATURE))
        if temperature is None:
            sans_temperature += 1
            continue
        correction = 1.0 + (gamma / 100.0) * (temperature - TEMPERATURE_STC_C)
        reference += (irradiance / IRRADIANCE_REFERENCE_W_M2) * correction
        somme_t_g += temperature * irradiance
        somme_g += irradiance
    if sans_temperature:
        return None, None, MOTIF_TEMPERATURE.format(heures=sans_temperature)
    if somme_g <= 0.0:
        return None, None, MOTIF_TEMPERATURE.format(heures=0)

    reference_kwh = puissance * reference * heures
    if reference_kwh <= 0.0:
        return None, None, MOTIF_TEMPERATURE.format(heures=0)
    return (round(energie_kwh / reference_kwh, 4),
            round(somme_t_g / somme_g, 2), '')


# ── la PÉRIODE, explicite dès qu'elle n'est pas annuelle ───────────────

def _periode(points):
    """Le texte qui dit sur QUOI ce ratio porte, ou ``None``."""
    mois = set()
    annees = set()
    for point in points:
        valeur = _nombre(point.get('mois'))
        annee = _nombre(point.get('annee'))
        if valeur is not None and 1 <= int(valeur) <= 12:
            mois.add(int(valeur))
        if annee is not None:
            annees.add(int(annee))
    if not mois:
        return None
    if len(mois) == 12:
        if len(annees) <= 1:
            return PERIODE_ANNUELLE
        return (f'pluriannuelle ({len(annees)} années : '
                f'{min(annees)}-{max(annees)})')
    noms = ', '.join(MOIS_LIBELLES[rang - 1] for rang in sorted(mois))
    return f'partielle (mois : {noms})'


# ── lecture élémentaire ────────────────────────────────────────────────

def _nombre(valeur):
    """Un flottant fini, ou ``None`` — un booléen n'est jamais un nombre."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre or nombre in (float('inf'), float('-inf')):
        return None
    return nombre
