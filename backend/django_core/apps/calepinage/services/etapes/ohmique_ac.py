"""CALX173 — ÉTAPE « ohmique AC » : la liaison onduleur → comptage.

CE QUI EXISTAIT, ET POURQUOI IL NE SUFFISAIT PAS
-------------------------------------------------
``services/cables.py::longueur_ac`` exige une longueur SAISIE et refuse toute
section AC sans elle : aucun plan de toiture ne porte le chemin jusqu'au
tableau général, et sa docstring dit qu'aucun forfait n'est substitué. Le
poste ``ohmique_ac`` du catalogue restait pourtant une saisie de pourcentage
indépendante de ce métré. Cette étape les réconcilie : la perte est calculée
en ``R·I²`` sur la section et la longueur AC retenues, heure par heure sur la
puissance ALTERNATIVE que l'étape « onduleur » (CALX170) a écrite. Le poste
saisi du même nom est écarté par l'arbitrage de CALX149 dès que le calcul
aboutit.

MONOPHASÉ ET TRIPHASÉ NE PERDENT PAS PAREIL
---------------------------------------------
Pour le même transit, le triphasé répartit le courant sur trois phases : la
perte y est strictement inférieure. Les deux grandeurs qui en dépendent — la
tension de service du réseau BT et le facteur de la formule de courant — sont
LUES sur ``core/electrique/types.py`` (``EntreeElectrique.tension_reseau_v``
et ``EntreeElectrique.facteur_phases``), jamais réécrites ici. PV*SOL traite
de même les câbles AC séparément de la ligne principale DC et des chaînes
(https://help.valentin-software.com/pvsol/en/pages/cables/).

CE QU'ELLE LIT, ET CE QUI LA FAIT S'OMETTRE
---------------------------------------------
* la série doit DÉCLARER le porteur alternatif (``colonne_energie ==
  'p_ac_kw'``) : sans conversion amont, il n'y a pas de transit alternatif à
  faire chuter, et l'étape s'omet en le disant ;
* ``norme`` non applicable (règle D5) ⇒ aucune section publiable, motif de
  ``services/norme.py`` repris tel quel ;
* ``cables`` sans câble de repère ``W2`` ⇒ l'étape reprend le motif de
  ``longueur_ac`` lui-même, mot pour mot ;
* ``fiche_onduleur['phases']`` absent ⇒ étape OMISE en nommant le champ :
  monophasé et triphasé ne donnent pas la même perte, et le régime ne se
  suppose pas.
"""
from __future__ import annotations

from types import SimpleNamespace

from apps.calepinage.services import etapes
from apps.calepinage.services.cables import longueur_ac
from core.electrique.cables import RHO_CUIVRE_20C
from core.electrique.types import EntreeElectrique

LIBELLE = 'Pertes ohmiques AC'

#: Le repère du câble AC dans le bloc ``cables`` (CAL131).
REPERE_AC = 'W2'

#: La colonne d'énergie qu'exige cette étape : l'alternatif de CALX170.
COLONNE_ALTERNATIVE = 'p_ac_kw'

#: Le nombre de conducteurs ACTIFS qui s'échauffent : deux en monophasé
#: (aller et retour), trois en triphasé (les trois phases).
CONDUCTEURS_ACTIFS = {1: 2.0, 3: 3.0}

REFERENCE_PVSOL = (
    'PV*SOL — Cables : les pertes de câble se traitent séparément pour l\'AC, '
    'la ligne principale DC et les chaînes, en forfait ou en détaillé '
    '(longueur / section / matériau) '
    '(https://help.valentin-software.com/pvsol/en/pages/cables/)')

MOTIF_SANS_ALTERNATIF = (
    "La série ne déclare pas de puissance alternative : la conversion "
    "continu → alternatif (étape « onduleur », CALX170) ne s'est pas "
    "appliquée, et il n'y a aucun transit alternatif à faire chuter. Étape "
    "OMISE.")

MOTIF_SANS_PHASES = (
    "La fiche de l'onduleur ne publie pas son nombre de phases : "
    "monophasé et triphasé ne perdent pas la même chose pour le même "
    "transit, et le régime ne se suppose pas. Étape OMISE.")

MOTIF_SANS_SECTION = (
    "Le métré ne publie pas de section pour le câble AC de repère "
    "« {repere} » : la résistance de la liaison n'est pas calculable. Étape "
    "OMISE.")

__all__ = ['appliquer', 'LIBELLE', 'REPERE_AC', 'COLONNE_ALTERNATIVE',
           'CONDUCTEURS_ACTIFS']


def appliquer(serie, contexte):
    """``(serie, etape)`` — la perte ``R·I²`` de la liaison alternative."""
    contexte = contexte if isinstance(contexte, dict) else {}

    if serie.get('colonne_energie') != COLONNE_ALTERNATIVE:
        return serie, etapes.etape_omise(
            LIBELLE, MOTIF_SANS_ALTERNATIF,
            champ='serie.colonne_energie')

    motif_norme = _motif_norme(contexte)
    if motif_norme:
        return serie, etapes.etape_omise(LIBELLE, motif_norme)

    phases = _phases(contexte)
    if phases is None:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_SANS_PHASES,
                                         champ='fiche_onduleur.phases')

    cable = _cable(contexte, REPERE_AC)
    if cable is None:
        return serie, etapes.etape_omise(
            LIBELLE, _motif_longueur_ac(contexte),
            champ='cheminement.onduleur_vers_tgbt_m')

    section = _nombre(cable.get('section_mm2'))
    longueur = _nombre(cable.get('longueur_m'))
    if not section:
        return serie, etapes.etape_omise(
            LIBELLE, MOTIF_SANS_SECTION.format(repere=REPERE_AC),
            champ='cables[%s].section_mm2' % REPERE_AC)
    if longueur is None:
        return serie, etapes.etape_omise(
            LIBELLE, _motif_longueur_ac(contexte),
            champ='cheminement.onduleur_vers_tgbt_m')

    return _appliquer_liaison(
        serie, phases, section, longueur,
        cable.get('longueur_origine') or 'saisie')


def _appliquer_liaison(serie, phases, section, longueur, origine):
    """La perte heure par heure sur la puissance alternative."""
    reperes = SimpleNamespace(phases=phases)
    tension_v = EntreeElectrique.tension_reseau_v.fget(reperes)
    facteur_phases = EntreeElectrique.facteur_phases.fget(reperes)
    conducteurs = CONDUCTEURS_ACTIFS[phases]
    resistance_lineique = RHO_CUIVRE_20C * longueur / section

    points = []
    energie_avant = 0.0
    energie_perdue = 0.0
    for point in serie.get('points') or []:
        valeur = point.get(COLONNE_ALTERNATIVE)
        puissance_w = _puissance_w(valeur)
        if puissance_w is None:
            points.append(point)
            continue
        courant_a = puissance_w / (tension_v * facteur_phases)
        perte_w = conducteurs * resistance_lineique * courant_a ** 2
        fraction = (min(1.0, perte_w / puissance_w)
                    if puissance_w > 0.0 else 0.0)
        copie = dict(point)
        copie[COLONNE_ALTERNATIVE] = float(valeur) * (1.0 - fraction)
        points.append(copie)
        energie_avant += puissance_w
        energie_perdue += puissance_w * fraction

    suite = dict(serie)
    suite['points'] = points
    suite['colonne_energie'] = COLONNE_ALTERNATIVE

    perte_ponderee = (energie_perdue / energie_avant
                      if energie_avant > 0.0 else 0.0)
    return suite, etapes.etape_appliquee(
        LIBELLE,
        source=origine,
        entree={
            'champ': 'cables[%s]' % REPERE_AC,
            'liaison': 'onduleur → tableau général',
            'section_mm2': section,
            'longueur_m': longueur,
            'phases': phases,
            'conducteurs_actifs': conducteurs,
            'tension_reseau_v': tension_v,
            'facteur_phases': round(facteur_phases, 6),
            'resistance_lineique_ohm': round(resistance_lineique, 6),
            'perte_ponderee_pct': round(100.0 * perte_ponderee, 4),
            'formule': 'Ploss(h) = n · (ρ·L/S) · I(h)², '
                       'I(h) = P(h) / (U · k)',
            'rho_ohm_mm2_par_m': RHO_CUIVRE_20C,
        },
        reference=REFERENCE_PVSOL)


# ── lectures de contexte ─────────────────────────────────────────────────

def _phases(contexte):
    """1 ou 3, ou ``None`` si la fiche ne le publie pas."""
    fiche_onduleur = contexte.get('fiche_onduleur') or {}
    nombre = _nombre(fiche_onduleur.get('phases'))
    if nombre is None:
        return None
    entier = int(nombre)
    return entier if entier in CONDUCTEURS_ACTIFS else None


def _motif_norme(contexte):
    """Le motif de la norme NON applicable, repris tel quel, ou ``''``."""
    norme = contexte.get('norme')
    if not isinstance(norme, dict) or norme.get('applicable', False):
        return ''
    return (norme.get('motif') or '').strip()


def _motif_longueur_ac(contexte):
    """Le refus de ``services/cables.py::longueur_ac``, mot pour mot."""
    _, manques = longueur_ac(contexte.get('cheminement'))
    if manques:
        return 'Liaison AC non dimensionnée : %s.' % manques[0]
    return ("Aucun câble AC de repère « %s » n'est publié par le métré : la "
            "perte ohmique alternative n'est pas calculable. Étape OMISE."
            % REPERE_AC)


def _cable(contexte, repere):
    bloc = contexte.get('cables')
    if not isinstance(bloc, dict):
        return None
    for cable in bloc.get('cables') or ():
        if isinstance(cable, dict) and cable.get('repere') == repere:
            return cable
    return None


def _puissance_w(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur) * 1000.0
    except (TypeError, ValueError):
        return None


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None
