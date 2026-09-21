"""CALX171 — ÉTAPE « fenêtre MPPT » : les HEURES où la tension sort de la plage.

CE QUI EXISTAIT, ET POURQUOI IL NE SUFFISAIT PAS
-------------------------------------------------
``core/electrique/chaines.py`` vérifie les bornes de tension aux températures
EXTRÊMES (froid et chaud) et déclare « non vérifiable » ce qu'une fiche
incomplète interdit de calculer. C'est une vérification de CONCEPTION : elle
dit si une longueur de chaîne est admissible, jamais COMBIEN d'heures de
l'année sortent réellement de la plage. Rien ne comptait ces heures, alors que
la température de cellule horaire est désormais écrite sur la série par
l'étape « thermique » (CALX163).

CE QUE CETTE ÉTAPE FAIT
-------------------------
Elle reprend la dérive linéaire déjà employée par le noyau
(``core/electrique/types.py`` : ``V(T) = V_STC · (1 + coeff/100 · (T −
25 °C))``, le coefficient γ(Pmax) servant de dérive du Vmp) et la applique
HEURE PAR HEURE à la tension de la chaîne. Les heures dont la tension sort de
``[mppt_v_min, mppt_v_max]`` voient leur énergie retirée, avec le décompte
publié. PV*SOL fait la même vérification à chaque pas de simulation : « le
programme vérifie à chaque pas de simulation si la tension MPP du champ peut
être atteinte par l'onduleur »
(https://help.valentin-software.com/pvsol/en/calculation/inverters/).

ELLE PRÉCÈDE LE RENDEMENT ONDULEUR (D-CALX 16)
------------------------------------------------
L'ordre de ``chaine_pertes.ORDRE_ETAPES`` place ``mppt`` avant ``onduleur``,
lui-même avant ``ecretage`` : une heure dont la tension n'atteint pas la
fenêtre n'a pas de rendement de conversion à subir, elle n'est simplement pas
convertie.

CE QU'ELLE LIT, ET CE QUI LA FAIT S'OMETTRE
---------------------------------------------
* ``serie['points'][i]['t_cell_c']`` — la température de cellule de l'heure
  (CALX163). Absente ⇒ étape OMISE en nommant la colonne : aucune
  température n'est reconstituée ici.
* ``fiche_module['temp_coeff_pmax_pct_c']`` — le coefficient de dérive.
  ABSENT ⇒ étape OMISE en nommant le champ. Le repli de la dataclass du
  noyau (``−0,27`` / ``−0,35``, littéraux sans citation) n'est JAMAIS employé
  ici : il ferait passer un défaut de code pour une donnée constructeur.
* ``fiche_module['vmp_v']`` et ``electrique['chainage']
  ['modules_par_chaine']`` — la tension de la chaîne au STC.
* ``fiche_onduleur['mppt_v_min']`` / ``['mppt_v_max']`` — la fenêtre. Aucune
  des deux publiée ⇒ rien à vérifier, étape OMISE en les nommant.
* ``fiche_onduleur['v_demarrage_v']`` — la tension de démarrage, comptée à
  part (``heures_sous_demarrage``) : elle informe sans commander le retrait,
  qui reste celui de la fenêtre MPPT.

Seules les heures qui PRODUISENT sont examinées : une heure sans production
n'a pas d'énergie à perdre, et sa tension ne veut rien dire.
"""
from __future__ import annotations

from apps.calepinage.services import etapes
from core.electrique.types import TEMPERATURE_STC_C

LIBELLE = 'Fenêtre MPPT'

#: La colonne de température de cellule écrite par l'étape « thermique ».
COLONNE_TEMPERATURE = 't_cell_c'

#: Le champ de fiche module dont l'absence OMET l'étape.
CHAMP_COEFFICIENT = 'temp_coeff_pmax_pct_c'

REFERENCE_PVSOL = (
    'PV*SOL — Inverters : « le programme vérifie à chaque pas de simulation '
    'si la tension MPP du champ peut être atteinte par l\'onduleur » '
    '(https://help.valentin-software.com/pvsol/en/calculation/inverters/)')

MOTIF_SANS_TEMPERATURE = (
    "La série ne porte pas de température de cellule heure par heure : sans "
    "elle, la tension de la chaîne ne se calcule pour aucune heure et "
    "l'étape est OMISE. Elle est écrite par l'étape « thermique » (CALX163) "
    "quand celle-ci s'applique.")

MOTIF_SANS_COEFFICIENT = (
    "La fiche du module ne publie pas son coefficient de température de "
    "puissance : la dérive du Vmp n'est pas calculable. L'étape est OMISE — "
    "le défaut du noyau n'est pas employé ici, il ferait passer un littéral "
    "de code pour une donnée constructeur.")

MOTIF_SANS_TENSION_STC = (
    "La tension de la chaîne au STC n'est pas connue : il y faut le Vmp de "
    "la fiche module et le nombre de modules par chaîne (bloc « "
    "electrique.chainage »). Étape OMISE.")

MOTIF_SANS_FENETRE = (
    "La fiche de l'onduleur ne publie aucune borne de fenêtre MPPT : il n'y "
    "a rien à vérifier, et l'étape est OMISE plutôt que de supposer une "
    "plage.")

MOTIF_SERIE_ILLISIBLE = (
    "Aucune colonne d'énergie lisible sur la série : les heures hors plage "
    "n'ont pas d'énergie à retirer. Étape OMISE.")

MOTIF_AUCUNE_HEURE = (
    "Aucune heure de production ne porte à la fois une énergie et une "
    "température de cellule : il n'y a aucune heure à examiner, et l'étape "
    "est OMISE plutôt que de publier 0 % sur un échantillon vide.")

__all__ = ['appliquer', 'LIBELLE', 'COLONNE_TEMPERATURE',
           'CHAMP_COEFFICIENT']


def appliquer(serie, contexte):
    """``(serie, etape)`` — l'énergie des heures dont la tension sort de la
    plage, retirée et comptée."""
    contexte = contexte if isinstance(contexte, dict) else {}

    colonne = etapes.colonne_energie(serie)
    if colonne is None:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_SERIE_ILLISIBLE)

    fiche_module = contexte.get('fiche_module') or {}
    coefficient = _nombre(fiche_module.get(CHAMP_COEFFICIENT))
    if coefficient is None:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_SANS_COEFFICIENT,
                                         champ='fiche_module.%s'
                                               % CHAMP_COEFFICIENT)

    vmp = _nombre(fiche_module.get('vmp_v'))
    modules_par_chaine = _nombre(_chainage(contexte).get(
        'modules_par_chaine'))
    if not vmp or not modules_par_chaine:
        return serie, etapes.etape_omise(
            LIBELLE, MOTIF_SANS_TENSION_STC, champ='fiche_module.vmp_v')

    fiche_onduleur = contexte.get('fiche_onduleur') or {}
    borne_basse = _nombre(fiche_onduleur.get('mppt_v_min')) or 0.0
    borne_haute = _nombre(fiche_onduleur.get('mppt_v_max')) or 0.0
    if borne_basse <= 0.0 and borne_haute <= 0.0:
        return serie, etapes.etape_omise(
            LIBELLE, MOTIF_SANS_FENETRE,
            champ='fiche_onduleur.mppt_v_min / mppt_v_max')
    demarrage = _nombre(fiche_onduleur.get('v_demarrage_v')) or 0.0

    tension_stc = vmp * modules_par_chaine
    if not _porte_une_temperature(serie):
        return serie, etapes.etape_omise(
            LIBELLE, MOTIF_SANS_TEMPERATURE,
            champ='serie.points[].%s' % COLONNE_TEMPERATURE)

    releve = _examiner(serie, colonne, tension_stc, coefficient,
                       borne_basse, borne_haute, demarrage)
    if not releve['heures_examinees']:
        return serie, etapes.etape_omise(LIBELLE, MOTIF_AUCUNE_HEURE)

    suite = dict(serie)
    suite['points'] = releve.pop('points')
    suite['colonne_energie'] = colonne
    releve.update({
        'champ': 'serie.points[].%s' % COLONNE_TEMPERATURE,
        'fenetre_mppt_v': {'min': borne_basse or None,
                           'max': borne_haute or None},
        'tension_chaine_stc_v': round(tension_stc, 2),
        'coefficient_pct_par_c': coefficient,
        'formule': 'Vmp(T) = Vmp_STC · (1 + coeff/100 · (T − %s °C))'
                   % TEMPERATURE_STC_C,
    })
    return suite, etapes.etape_appliquee(
        LIBELLE, source='fiche', entree=releve,
        reference=REFERENCE_PVSOL)


def _examiner(serie, colonne, tension_stc, coefficient, borne_basse,
              borne_haute, demarrage):
    """Heure par heure : la tension, le verdict, et l'énergie retirée."""
    points = []
    heures_examinees = 0
    heures_hors_plage = 0
    heures_sous_demarrage = 0
    par_mois = {}
    tension_min = None
    tension_max = None

    for point in serie.get('points') or []:
        valeur = point.get(colonne)
        temperature = _nombre(point.get(COLONNE_TEMPERATURE))
        energie = _nombre(valeur)
        if temperature is None or energie is None or energie <= 0.0:
            points.append(point)
            continue

        tension = _tension(tension_stc, coefficient, temperature)
        heures_examinees += 1
        tension_min = tension if tension_min is None else min(tension_min,
                                                              tension)
        tension_max = tension if tension_max is None else max(tension_max,
                                                              tension)
        if demarrage > 0.0 and tension < demarrage:
            heures_sous_demarrage += 1

        hors = ((borne_basse > 0.0 and tension < borne_basse)
                or (borne_haute > 0.0 and tension > borne_haute))
        if not hors:
            points.append(point)
            continue

        heures_hors_plage += 1
        mois = point.get('mois')
        if mois is not None:
            par_mois[mois] = par_mois.get(mois, 0) + 1
        copie = dict(point)
        copie[colonne] = 0.0
        points.append(copie)

    mois_concerne = (max(par_mois.items(), key=lambda couple: couple[1])[0]
                     if par_mois else None)
    return {
        'points': points,
        'heures_examinees': heures_examinees,
        'heures_hors_plage': heures_hors_plage,
        'heures_sous_demarrage': heures_sous_demarrage,
        'mois_le_plus_concerne': mois_concerne,
        'tension_min_v': (round(tension_min, 2)
                          if tension_min is not None else None),
        'tension_max_v': (round(tension_max, 2)
                          if tension_max is not None else None),
    }


def _tension(tension_stc, coefficient, temperature_c):
    """La dérive linéaire du noyau, appliquée à la tension de la chaîne."""
    ecart = float(temperature_c) - TEMPERATURE_STC_C
    return tension_stc * (1.0 + (coefficient / 100.0) * ecart)


def _porte_une_temperature(serie):
    """La série porte-t-elle au moins une température de cellule ?"""
    for point in serie.get('points') or []:
        if isinstance(point, dict) and point.get(COLONNE_TEMPERATURE) is not \
                None:
            return True
    return False


def _chainage(contexte):
    electrique = contexte.get('electrique')
    if not isinstance(electrique, dict):
        return {}
    chainage = electrique.get('chainage')
    return chainage if isinstance(chainage, dict) else {}


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None
