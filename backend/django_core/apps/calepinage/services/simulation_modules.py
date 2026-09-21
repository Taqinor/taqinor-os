# -*- coding: utf-8 -*-
"""CALX182 — simuler MODULE PAR MODULE, puis AGRÉGER.

LE CONSTAT
----------
``services/production.py`` simule PAR PAN : une requête PVGIS par pan, une
mise à l'échelle par le kWc du pan, aucune notion de module. Le document
``roof_layout`` v2 porte pourtant le centre de CHAQUE module posé
(``zoneGeometry.panels``) et son accès solaire (``solarAccess``, une valeur
par module, dans le MÊME ordre) : la matière d'une simulation module par
module est là, et personne ne s'en sert.

Parité : HelioScope « modélise la performance de chaque module, pour chaque
heure du jour », par opposition aux outils qui « simulent un module et
mettent le résultat à l'échelle »
(https://help-center.helioscope.com/hc/en-us/articles/8537729072019-Maximum-Allowable-Design-Size).

CE QUE CE SERVICE FAIT
-----------------------
Il PILOTE la chaîne de pertes (``services/chaine_pertes.appliquer_chaine``,
CALX147) une fois PAR MODULE, et agrège. Il ne calcule aucune perte lui-même :
chaque poste reste dans son module d'étape, et l'accès solaire du module
arrive par l'étape « accès module » (CALX158), à qui ce pilote donne la
valeur du SEUL module simulé.

``services/chaine_pertes.py`` appartient à l'ordonnanceur : ce pilote vit
donc dans son propre module, et un seul appel le branche (CALX5) —
``production_module_par_module(contexte)``.

UNE REQUÊTE MÉTÉO PAR PLAN, JAMAIS PAR MODULE (CALX155)
----------------------------------------------------------
Les modules d'un même pan partagent la MÊME série horaire : elle est obtenue
une fois et mémorisée. Quand l'ordonnanceur a déjà installé son accès partagé
(``contexte['serie_du_pan']``), c'est LUI qui sert — deux pans de même
inclinaison et même azimut restent alors un seul appel. Sinon ce pilote pose
sa propre mémoire, keyée par le repère du plan, et l'installe dans le
contexte des modules pour que les étapes la partagent aussi.

CHAQUE PASSAGE TOURNE SUR SA PROPRE COPIE DU CONTEXTE
--------------------------------------------------------
``appliquer_chaine`` ÉCRIT dans le contexte qu'on lui donne, et c'est voulu :
elle y installe l'accès météo partagé, y sème le compteur
``meteo.appels_pvgis``, y réécrit ``meteo.heure`` après le recalage sur
l'heure du site et y pose le verdict ``croisement_horaire`` (CALX59/153/155).
Un pilote qui lui passerait le contexte de son appelant le laisserait donc
modifié — et l'appelant, lui, n'a rien demandé. Chaque passage reçoit donc sa
COPIE DE TRAVAIL : les clés de premier niveau sont reprises telles quelles
(les objets injectés — client météo, fiches — ne sont jamais clonés, sans
quoi leur cache serait perdu), et le bloc ``meteo``, le seul conteneur
imbriqué où la chaîne écrit, est recopié en profondeur. Ce que la chaîne y
pose n'est pas perdu pour autant : le verdict horaire et le bloc
``meteo.heure`` du premier passage sont REPUBLIÉS dans ``entree``.

LA PART D'UN MODULE DANS SON PAN
----------------------------------
La série d'un pan décrit le pan ENTIER. Un module en porte donc la part
``1/N``, N étant le nombre de modules posés sur ce pan : un pan ne porte
qu'un seul produit module (le document ne porte qu'une fiche), et cette part
est une division, pas une puissance inventée. C'est aussi ce qui rend
l'agrégat EXACTEMENT égal à la simulation par pan quand tous les modules ont
le même accès solaire.

LE PLAFOND, ET LA TRONCATURE QUI SE DIT
------------------------------------------
Au-delà d'un plafond de modules, la liste ``par_module`` n'est PAS publiée :
son volume la rendrait inexploitable, et la tronquer en silence ferait croire
à un toit plus petit. Le plafond se saisit (réglage société
``plafond_modules_simules``) ; à défaut c'est celui que la décision fondateur
du 21/09/2026 a arrêté — « plafond de simulation module par module à 5 000
modules, mesuré par CALX389 » — publié avec sa provenance. L'AGRÉGAT, lui,
reste juste : les modules identiques d'un pan sont simulés une seule fois et
comptés autant de fois qu'ils sont.

CE QUE CE SERVICE NE FAIT PAS
-------------------------------
Aucune base, aucun réseau, aucune horloge, aucun argent (D-CALX 5). Il ne
publie que ce qu'il a : une énergie illisible reste ``None``, jamais un zéro
(D-CALX 7), et un pan sans module est NOMMÉ plutôt qu'ignoré.
"""
from __future__ import annotations

import copy

from apps.calepinage.services import chaine_pertes, etapes
from apps.calepinage.services.ombrage_chaines import acces_par_module

#: La clé de réglage société qui porte le plafond (registre CALX145).
CLE_PLAFOND = 'plafond_modules_simules'

#: Le plafond ARRÊTÉ par la décision fondateur du 21/09/2026, en tête du
#: groupe CALX de ``docs/PLAN2.md`` : « plafond de simulation module par
#: module à 5 000 modules, mesuré par CALX389 ». Ce n'est pas un défaut
#: inventé, c'est une décision citée — et un réglage société saisi la
#: remplace (D-CALX 7).
PLAFOND_DECIDE = 5000

#: La provenance publiée avec le plafond retenu.
SOURCE_PLAFOND_DECIDE = 'decision'
SOURCE_PLAFOND_SAISI = 'reglage_societe'
REFERENCE_PLAFOND = (
    'Décision fondateur du 21/09/2026 (en-tête du groupe CALX, '
    'docs/PLAN2.md) : plafond de simulation module par module à 5 000 '
    'modules, mesuré par CALX389.')

#: La référence de méthode publiée avec le bloc.
REFERENCE = (
    'HelioScope — Maximum Allowable Design Size : la performance de CHAQUE '
    'module est modélisée, pour chaque heure, plutôt qu’un module simulé '
    'puis mis à l’échelle — https://help-center.helioscope.com/hc/en-us/'
    'articles/8537729072019-Maximum-Allowable-Design-Size.')

#: Ce que la méthode dit d'elle-même, publié dans ``entree.methode``.
METHODE = (
    'Un passage complet de la chaîne de pertes PAR MODULE, sur la part 1/N '
    'de la série de son pan ; les modules d’un pan qui partagent le même '
    'accès solaire sont calculés une seule fois et comptés autant de fois '
    "qu'ils sont — l'agrégat est donc exact, jamais échantillonné.")

MOTIF_SANS_PLAN = (
    'Le contexte ne porte aucun pan : il n’y a aucun module à simuler, et '
    'aucun total n’est publié (un 0 kWh se lirait « ce toit ne produit '
    'rien »).')

MOTIF_SANS_METEO = (
    'Aucune série horaire n’est accessible : ni l’accès partagé de '
    '« serie_du_pan » (CALX155), ni le fournisseur « obtenir_serie » que '
    'services/simulation.py pose (CALX5). Aucune production module par '
    'module n’est calculable.')

MOTIF_TRONCATURE = (
    'Le document porte {modules} modules, au-delà du plafond de {plafond} : '
    'la liste module par module n’est PAS publiée — seuls l’agrégat par '
    'chaîne et le total le sont, et ils restent justes. Le plafond se règle '
    'par « {cle} ».')

MOTIF_SERIE_AGREGEE_HETEROGENE = (
    'Les séries des modules ne partagent pas le même index horaire (nombre '
    'de points ou colonne d’énergie différents d’un pan à l’autre) : aucune '
    'série agrégée n’est publiée plutôt qu’une somme qui alignerait des '
    'heures différentes.')

MOTIF_ENERGIE_ILLISIBLE = (
    '{modules} module(s) n’ont pas d’énergie lisible dans leur série de '
    'sortie : le total reste nul (au sens « inconnu »), jamais un zéro qui '
    'se lirait « ces modules ne produisent rien ».')

__all__ = ['CLE_PLAFOND', 'PLAFOND_DECIDE', 'SOURCE_PLAFOND_DECIDE',
           'SOURCE_PLAFOND_SAISI', 'REFERENCE_PLAFOND', 'REFERENCE',
           'METHODE', 'MOTIF_SANS_PLAN', 'MOTIF_SANS_METEO',
           'MOTIF_TRONCATURE', 'MOTIF_SERIE_AGREGEE_HETEROGENE',
           'MOTIF_ENERGIE_ILLISIBLE', 'production_module_par_module']


def production_module_par_module(contexte, *, chaine=None):
    """``{par_module, par_chaine, total, serie_agregee, entree, motif}``.

    Args:
        contexte: le dict décrit en tête de ``services/etapes/__init__.py``,
            enrichi de ``plans``, ``ombrage`` (document de toiture et accès
            solaire), ``affectation`` (module → chaîne) et de l'accès météo
            (``serie_du_pan`` ou ``obtenir_serie``).
        chaine: l'ordonnanceur à employer — ``appliquer_chaine`` par défaut.
            Le paramètre existe pour qu'un test puisse ISOLER l'agrégation de
            la chaîne réelle, jamais pour brancher une autre chaîne en
            production.

    Returns:
        dict — ``par_module`` / ``par_chaine`` / ``total`` aux clés du contrat
        ``contract_samples/calepinage_simulation.json``, la ``serie_agregee``
        des modules (ou ``None`` avec son motif), le bloc ``entree`` qui dit
        ce qui a été lu, et ``motif`` (vide quand tout s'est calculé).

    Fonction PURE : le contexte reçu n'est jamais modifié.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    appliquer = chaine or chaine_pertes.appliquer_chaine
    plans = [plan for plan in (contexte.get('plans') or ())
             if isinstance(plan, dict)]
    if not plans:
        return _vide(MOTIF_SANS_PLAN)

    meteo, demandes = _acces_meteo(contexte)
    if meteo is None:
        return _vide(MOTIF_SANS_METEO)

    acces_par_pan = _acces_par_pan(contexte)
    par_module = []
    plans_sans_module = []
    groupes = []
    premiere_copie = None
    for plan in plans:
        repere = _repere(plan)
        acces = _acces_du_plan(plan, repere, acces_par_pan)
        if not acces:
            plans_sans_module.append(repere)
            continue
        serie_pan = meteo(plan)
        part = etapes.mettre_a_l_echelle(serie_pan, 1.0 / len(acces))
        memoire = {}
        for rang, valeur in enumerate(acces, start=1):
            groupe = memoire.get(valeur)
            if groupe is None:
                # Deux modules d'un même pan qui partagent leur accès
                # solaire partagent aussi leur résultat : la chaîne est
                # DÉTERMINISTE, la recalculer donnerait le même nombre.
                travail = _contexte_du_module(contexte, plan, valeur, meteo)
                if premiere_copie is None:
                    premiere_copie = travail
                sortie, _cascade = appliquer(part, travail)
                groupe = {'serie': sortie, 'modules': 0,
                          'kwh': etapes.energie_kwh(sortie)}
                memoire[valeur] = groupe
                groupes.append(groupe)
            groupe['modules'] += 1
            par_module.append({
                'module': '%s#%d' % (repere, rang),
                'pan': repere,
                'chaine': None,
                'acces_solaire_pct': (None if valeur is None
                                      else round(valeur * 100.0, 3)),
                'p50_kwh': _arrondi(groupe['kwh']),
                'source': _source(contexte),
            })

    _rattacher_les_chaines(par_module, contexte)
    sans_energie = sum(1 for ligne in par_module
                       if ligne['p50_kwh'] is None)
    total_kwh = (None if sans_energie or not par_module
                 else _arrondi(sum(ligne['p50_kwh']
                                   for ligne in par_module)))
    plafond = _plafond(contexte)
    tronque = len(par_module) > plafond['valeur']
    agregee, motif_agregee = _serie_agregee(groupes)

    entree = {
        'methode': METHODE,
        'reference': REFERENCE,
        'modules_simules': len(par_module),
        'chaines_executees': len(groupes),
        'series_demandees': len(demandes),
        'pans': [_repere(plan) for plan in plans],
        'pans_sans_module': plans_sans_module,
        'modules_sans_acces': [ligne['module'] for ligne in par_module
                               if ligne['acces_solaire_pct'] is None],
        'modules_sans_energie': sans_energie,
        'plafond': plafond,
        'par_module_tronque': tronque,
        'motif_troncature': (MOTIF_TRONCATURE.format(
            modules=len(par_module), plafond=plafond['valeur'],
            cle=CLE_PLAFOND) if tronque else ''),
        'motif_serie_agregee': motif_agregee,
        'motif_energie': (MOTIF_ENERGIE_ILLISIBLE.format(modules=sans_energie)
                          if sans_energie else ''),
    }
    entree.update(_ce_que_la_chaine_a_pose(premiere_copie))
    return {
        'par_module': [] if tronque else par_module,
        'par_chaine': _par_chaine(par_module, contexte),
        'total': {
            'modules': len(par_module),
            'kwc': _kwc(len(par_module), contexte),
            'p50_kwh': total_kwh,
        },
        'serie_agregee': agregee,
        'entree': entree,
        'motif': '',
    }


# ── la météo, UNE fois par plan ─────────────────────────────────────────

def _acces_meteo(contexte):
    """``(accès, demandes)`` — la série d'un plan, mémorisée par plan.

    L'accès partagé de l'ordonnanceur (CALX155) prime : lui seul sait que
    deux pans de même inclinaison et même azimut sont une seule requête.
    ``demandes`` compte les plans pour lesquels CE pilote a demandé une
    série — la garantie qu'il n'en demande jamais une par module.
    """
    demandes = {}
    partage = contexte.get(chaine_pertes.CLE_METEO_PARTAGEE)
    fournisseur = (partage if callable(partage)
                   else contexte.get(chaine_pertes.CLE_FOURNISSEUR_METEO))
    if not callable(fournisseur):
        return None, demandes

    def obtenir(plan):
        cle = _repere(plan) if isinstance(plan, dict) else str(plan)
        if cle not in demandes:
            demandes[cle] = fournisseur(plan)
        return demandes[cle]

    return obtenir, demandes


def _repere(plan):
    """Le repère d'un pan — celui du document, jamais un identifiant d'objet."""
    for cle in ('cle', 'label', 'id', 'pan'):
        valeur = plan.get(cle)
        if valeur:
            return str(valeur)
    return ''


# ── les modules d'un pan, et leur accès ─────────────────────────────────

def _acces_par_pan(contexte):
    """``{repère du pan: [accès ou None, …]}`` lu dans le document."""
    ombrage = contexte.get('ombrage')
    ombrage = ombrage if isinstance(ombrage, dict) else {}
    acces = ombrage.get('solar_access') or ombrage.get('solarAccess') or {}
    if isinstance(acces, dict) and isinstance(acces.get('par_pan'), dict):
        return acces['par_pan']
    layout = ombrage.get('layout') or contexte.get('layout')
    return acces_par_module(layout) if isinstance(layout, dict) else {}


def _acces_du_plan(plan, repere, acces_par_pan):
    """La liste des accès du pan — une entrée par module posé.

    Le document prime. À défaut, le nombre de modules déclaré par le plan
    donne autant d'entrées SANS accès (``None``) : un module sans accès
    calculé n'est pas un module à 100 %, il est simplement simulé sans
    lecture d'ombrage, et ``modules_sans_acces`` le dit.
    """
    lues = acces_par_pan.get(repere)
    if isinstance(lues, (list, tuple)) and lues:
        return [_nombre_borne(valeur) for valeur in lues]
    nombre = _entier(plan.get('modules'))
    return [None] * nombre if nombre else []


def _contexte_du_module(contexte, plan, acces, meteo):
    """La COPIE DE TRAVAIL d'UN module : son pan, son accès, sa météo.

    Le document de toiture et la table d'affectation restent INTACTS : les
    étapes qui raisonnent par CHAÎNE (la dispersion d'ombrage, CALX168) ont
    besoin de voir toute la chaîne, pas le seul module simulé. Seule la
    lecture d'accès solaire est réduite au module — c'est elle qui fait la
    différence avec une simulation par pan.

    ``meteo`` est recopié EN PROFONDEUR parce que ``appliquer_chaine`` y
    écrit (``appels_pvgis``, ``heure`` après le recalage horaire) : sans
    cette copie, le contexte de l'appelant ressortirait modifié. Les autres
    valeurs sont reprises telles quelles — cloner un client météo ou une
    fiche perdrait leur cache, et la chaîne n'y écrit pas.
    """
    copie = dict(contexte)
    bloc_meteo = contexte.get('meteo')
    copie['meteo'] = (copy.deepcopy(bloc_meteo)
                      if isinstance(bloc_meteo, dict) else {})
    copie['plan'] = plan
    copie['plans'] = [plan]
    copie[chaine_pertes.CLE_METEO_PARTAGEE] = meteo
    ombrage = contexte.get('ombrage')
    ombrage = dict(ombrage) if isinstance(ombrage, dict) else {}
    lecture = ombrage.get('solar_access') or ombrage.get('solarAccess')
    if isinstance(lecture, dict):
        reduite = dict(lecture)
        reduite['values'] = [acces]
        reduite.pop('par_pan', None)
        ombrage.pop('solarAccess', None)
        ombrage['solar_access'] = reduite
        copie['ombrage'] = ombrage
    return copie


# ── l'agrégation ────────────────────────────────────────────────────────

def _rattacher_les_chaines(par_module, contexte):
    """Pose la chaîne de chaque module depuis la table d'affectation."""
    par_repere = {}
    for ligne in _affectation(contexte):
        repere = ligne.get('module')
        if repere:
            par_repere[str(repere)] = ligne
    for ligne in par_module:
        affectee = par_repere.get(ligne['module'])
        if affectee is not None:
            ligne['chaine'] = affectee.get('chaine')


def _par_chaine(par_module, contexte):
    """L'agrégat par chaîne — la partition RÉELLE, jamais une recalculée."""
    par_repere = {str(ligne.get('module')): ligne
                  for ligne in _affectation(contexte) if ligne.get('module')}
    groupes = {}
    ordre = []
    for ligne in par_module:
        if ligne['chaine'] is None:
            continue
        cle = (ligne['pan'], ligne['chaine'])
        if cle not in groupes:
            groupes[cle] = []
            ordre.append(cle)
        groupes[cle].append(ligne)

    publiees = []
    for cle in ordre:
        lignes = groupes[cle]
        affectee = par_repere.get(lignes[0]['module']) or {}
        energies = [ligne['p50_kwh'] for ligne in lignes]
        acces = [ligne['acces_solaire_pct'] for ligne in lignes
                 if ligne['acces_solaire_pct'] is not None]
        publiees.append({
            'chaine': cle[1],
            'pan': cle[0],
            'onduleur': affectee.get('onduleur'),
            'mppt': affectee.get('mppt'),
            'modules': len(lignes),
            'kwc': _kwc(len(lignes), contexte),
            'p50_kwh': (None if any(valeur is None for valeur in energies)
                        else _arrondi(sum(energies))),
            'acces_solaire_min_pct': min(acces) if acces else None,
            'ecart_intra_chaine_pct': (round(max(acces) - min(acces), 3)
                                       if acces else None),
            'source': _source(contexte),
        })
    return publiees


def _serie_agregee(groupes):
    """``(serie, motif)`` — la somme HORAIRE des séries des modules.

    Elle n'est publiée que si toutes les séries partagent le même index
    horaire et la même colonne d'énergie : additionner des heures
    différentes donnerait une courbe qui ne décrit aucun toit. Chaque groupe
    pèse le NOMBRE de modules qu'il représente — c'est ce qui rend la courbe
    cohérente avec le total sans simuler deux fois le même module.
    """
    if not groupes:
        return None, ''
    premiere = groupes[0]['serie']
    colonne = etapes.colonne_energie(premiere)
    if colonne is None:
        return None, MOTIF_SERIE_AGREGEE_HETEROGENE
    points = premiere.get('points') or []
    index = [_horodatage(point) for point in points]
    cumul = [0.0] * len(points)
    for groupe in groupes:
        sortie = groupe['serie']
        if etapes.colonne_energie(sortie) != colonne:
            return None, MOTIF_SERIE_AGREGEE_HETEROGENE
        siens = sortie.get('points') or []
        if len(siens) != len(points):
            return None, MOTIF_SERIE_AGREGEE_HETEROGENE
        poids = groupe['modules']
        for rang, point in enumerate(siens):
            if _horodatage(point) != index[rang]:
                return None, MOTIF_SERIE_AGREGEE_HETEROGENE
            valeur = _nombre(point.get(colonne))
            if valeur is not None:
                cumul[rang] += valeur * poids
    rendus = []
    for rang, point in enumerate(points):
        copie = dict(point)
        copie[colonne] = cumul[rang]
        rendus.append(copie)
    serie = dict(premiere)
    serie['points'] = rendus
    serie['colonne_energie'] = colonne
    return serie, ''


def _horodatage(point):
    return tuple(point.get(cle) for cle in ('annee', 'mois', 'jour', 'heure'))


def _ce_que_la_chaine_a_pose(travail):
    """Ce que la chaîne a écrit sur la copie de travail, REPUBLIÉ ici.

    ``appliquer_chaine`` pose son verdict de croisement horaire et le bloc
    ``meteo.heure`` dans le contexte qu'elle reçoit (CALX59/153). Comme ce
    pilote ne lui donne que des copies, ces deux blocs seraient perdus : ils
    sont republiés tels quels. Ils ne dépendent que du site et de la série
    du pan, donc le premier passage les porte tous.
    """
    if not isinstance(travail, dict):
        return {'croisement_horaire': None, 'meteo_heure': None}
    bloc_meteo = travail.get('meteo')
    return {
        'croisement_horaire': travail.get(
            chaine_pertes.CLE_CROISEMENT_HORAIRE),
        'meteo_heure': (bloc_meteo.get('heure')
                        if isinstance(bloc_meteo, dict) else None),
    }


# ── les entrées, une par une ────────────────────────────────────────────

def _affectation(contexte):
    """La table module → chaîne, lue là où CALX5 la pose."""
    lue = contexte.get('affectation')
    if not lue:
        electrique = contexte.get('electrique')
        lue = (electrique.get('affectation')
               if isinstance(electrique, dict) else None)
    if not isinstance(lue, (list, tuple)):
        return ()
    return tuple(ligne for ligne in lue if isinstance(ligne, dict))


def _plafond(contexte):
    """Le plafond retenu, AVEC sa provenance — saisi, ou décidé et cité."""
    saisi = etapes.reglage(contexte, CLE_PLAFOND)
    valeur = _entier(saisi.get('valeur')) if saisi else None
    if valeur:
        return {'valeur': valeur, 'source': SOURCE_PLAFOND_SAISI,
                'reference': saisi.get('reference') or '', 'cle': CLE_PLAFOND}
    return {'valeur': PLAFOND_DECIDE, 'source': SOURCE_PLAFOND_DECIDE,
            'reference': REFERENCE_PLAFOND, 'cle': CLE_PLAFOND}


def _kwc(modules, contexte):
    """Les kWc de ``modules`` exemplaires, si la fiche publie sa puissance."""
    fiche = contexte.get('fiche_module')
    if not isinstance(fiche, dict):
        return None
    for champ in ('pmax_w', 'puissance_w', 'p_max_w'):
        watts = _nombre(fiche.get(champ))
        if watts:
            return round(modules * watts / 1000.0, 3)
    return None


def _source(contexte):
    """La provenance de la série employée, telle que le bloc météo la dit."""
    meteo = contexte.get('meteo')
    if not isinstance(meteo, dict):
        return None
    return meteo.get('base_rayonnement') or meteo.get('service') or None


def _vide(motif):
    """Le bloc PUBLIÉ quand rien n'a pu être simulé — nommé, jamais nul."""
    return {
        'par_module': [], 'par_chaine': [],
        'total': {'modules': 0, 'kwc': None, 'p50_kwh': None},
        'serie_agregee': None,
        'entree': {'methode': METHODE, 'reference': REFERENCE,
                   'modules_simules': 0, 'chaines_executees': 0,
                   'series_demandees': 0, 'croisement_horaire': None,
                   'meteo_heure': None},
        'motif': motif,
    }


def _arrondi(valeur):
    return None if valeur is None else round(float(valeur), 3)


def _entier(valeur):
    nombre = _nombre(valeur)
    return None if nombre is None else int(nombre)


def _nombre_borne(valeur):
    """Un accès solaire de [0, 1], ou ``None`` — le contrat v2 les borne."""
    nombre = _nombre(valeur)
    if nombre is None or not 0.0 <= nombre <= 1.0:
        return None
    return nombre


def _nombre(valeur):
    """Un flottant lisible, ou ``None`` — jamais une valeur de remplacement."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre
