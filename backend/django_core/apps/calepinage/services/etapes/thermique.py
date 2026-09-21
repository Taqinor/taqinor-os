"""CALX163 — ÉTAPE « thermique » : Faiman par TYPE DE POSE, heure par heure.

LE CONSTAT
----------
``services/thermique.py`` (CAL140) sait déjà tout faire — Faiman
``T_cell = T_air + G / (Uc + Uv·v)`` quand la fiche porte ``uc_w_m2k``, NOCT
en repli, refus explicite ``calculable: False`` quand elle ne porte ni l'un ni
l'autre — et personne ne l'appelait. Surtout, Uc et Uv décrivent la POSE
(surimposé ventilé, intégré, châssis, sol, ombrière), pas le module : lire
``uc_w_m2k`` sur la fiche du panneau, c'est demander au fabricant un chiffre
qui dépend du toit. Et la NOCT est mesurée en conditions « open rack » : pour
un module intégré non ventilé, elle SOUS-ESTIME la température de cellule.

CE QUE CETTE ÉTAPE FAIT
------------------------
1. Elle LIT le type de pose sur le document (``plans[].type_pose``, à défaut
   ``pose`` / ``kind`` / ``family``, à défaut le booléen ``flush`` du plan ou
   de sa géométrie).
2. Elle cherche ce type de pose dans le réglage société
   ``simulation.thermique_par_pose`` — ``{type_pose: {uc_w_m2k, uv_w_m3sk,
   source, reference}}``. Les valeurs publiées par les logiciels du marché
   sont proposées en AIDE À LA SAISIE par l'écran de réglages, jamais
   préremplies ici (D-CALX 7).
3. Table société muette ⇒ Faiman avec le ``uc_w_m2k`` de la fiche s'il
   existe, provenance ``fiche``, et la mention qui dit que le coefficient
   d'une fiche est appliqué à une pose non caractérisée.
4. Toujours rien ⇒ NOCT de la fiche, provenance ``noct``, avec la mention qui
   dit que la NOCT est mesurée en open-rack.
5. Rien du tout ⇒ étape OMISE, avec le motif de ``services/thermique.py``
   publié tel quel et le champ manquant nommé. Aucun ``forfait_pct`` n'est
   employé nulle part dans ce module.

HEURE PAR HEURE, ET LA TEMPÉRATURE RESTE SUR LA SÉRIE
------------------------------------------------------
La dérate ``γ × (T_cell − 25)`` est appliquée à CHAQUE point, et la
température de cellule de chaque heure est écrite sur le point sous
``t_cell_c`` — une colonne que le contrat de la série (CALX142) déclare
déjà, et dont les étapes aval (fenêtre MPPT, ratio de performance) ont
besoin. Une heure dont la température n'est pas lisible (pas d'irradiance,
pas de ``t2m_c``) est laissée INTACTE et COMPTÉE dans
``entree.heures_sans_temperature`` : un facteur 1 silencieux se lirait
« aucune perte », ce qui serait un forfait déguisé.

γ est NÉGATIF sur une fiche : au-dessus de 25 °C la dérate retire de
l'énergie, en dessous elle en ajoute. Sur un site froid le bilan de l'étape
peut donc être un GAIN — il est alors DÉCLARÉ (``gain=True``) plutôt
qu'effacé, comme ``services/thermique.py`` le fait déjà de son côté.

Module PUR : aucune base, aucun réseau, aucun appel PVGIS (la série du pan
arrive par la chaîne, CALX155).
"""
from __future__ import annotations

from apps.calepinage.services import etapes as _etapes
from apps.calepinage.services.thermique import (
    MODELE_FAIMAN, MODELE_NOCT, TEMPERATURE_STC_C, perte_thermique,
    temperature_cellule)

#: La clé de réglage société lue ici (registre CALX145).
CLE_REGLAGE = 'thermique_par_pose'

#: La colonne de température de cellule écrite sur chaque point — elle
#: FIGURE déjà au contrat de la série horaire (CALX142).
COLONNE_TEMPERATURE = 't_cell_c'

#: Les champs du document qui NOMMENT le type de pose d'un plan, dans
#: l'ordre de lecture. Le premier renseigné gagne ; aucun n'est inventé.
CHAMPS_POSE = ('type_pose', 'pose', 'kind', 'family')

#: Les deux types de pose que le booléen ``flush`` du document distingue à
#: lui seul : posé À PLAT sur la couverture, ou relevé sur un châssis.
POSE_INTEGRE = 'integre'
POSE_CHASSIS = 'chassis'

PROVENANCE_SOCIETE = 'societe'
PROVENANCE_FICHE = 'fiche'
PROVENANCE_NOCT = 'noct'

#: La mention qui accompagne chaque provenance — elle voyage dans
#: ``cascade[].entree`` pour que l'écran puisse la citer telle quelle.
MENTIONS = {
    PROVENANCE_SOCIETE: '',
    PROVENANCE_FICHE: (
        "coefficient de fiche appliqué à une pose non caractérisée : la "
        "société n'a pas saisi de Uc/Uv pour ce type de pose."),
    PROVENANCE_NOCT: (
        "NOCT : conditions open-rack, température sous-estimée pour une pose "
        'intégrée.'),
}

#: Les textes du marché, CITÉS et jamais recopiés en constantes.
REFERENCE = (
    'PVsyst — Array thermal losses : les valeurs U sont « fitted to '
    "measurements » et l'effet typique va de −0,2 à −0,4 %/°C "
    '(https://www.pvsyst.com/help/project-design/array-and-system-losses/'
    'array-thermal-losses/index.html) ; PV*SOL — Module temperature : ΔT de '
    '20 K en photovoltaïque flottant à 43 K en toiture intégrée non ventilée '
    '(https://help.valentin-software.com/pvsol/en/calculation/pv-modules/'
    'module-temperature/).')

LIBELLE = 'Échauffement des modules'

__all__ = ['CLE_REGLAGE', 'COLONNE_TEMPERATURE', 'CHAMPS_POSE',
           'POSE_INTEGRE', 'POSE_CHASSIS', 'PROVENANCE_SOCIETE',
           'PROVENANCE_FICHE', 'PROVENANCE_NOCT', 'MENTIONS', 'REFERENCE',
           'LIBELLE', 'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — la dérate thermique horaire, ou son silence."""
    contexte = contexte if isinstance(contexte, dict) else {}
    fiche = contexte.get('fiche_module')
    fiche = dict(fiche) if isinstance(fiche, dict) else {}

    types_lus, type_pose, champ_pose = _poses_du_document(contexte)
    coefficients, entree_societe, ecart_societe = _coefficients_societe(
        contexte, type_pose)

    specs = dict(fiche)
    specs.update(coefficients)
    points = list((serie or {}).get('points') or ())
    mesure = perte_thermique(specs, points)
    if not mesure['calculable']:
        return serie, _etapes.etape_omise(
            LIBELLE, mesure['motif'], champ=_champ_manquant(specs))

    provenance = _provenance(mesure['modele'], bool(coefficients))
    mention = MENTIONS[provenance]
    if ecart_societe:
        mention = (mention + ' ' if mention else '') + ecart_societe

    rendue, sans_temperature = _appliquer_heure_par_heure(
        serie, points, mesure)
    entree = {
        'modele': mesure['modele'],
        'provenance': provenance,
        'mention': mention,
        'type_pose': type_pose,
        'champ_type_pose': champ_pose,
        'types_pose_lus': types_lus,
        'reglage_societe': entree_societe,
        'parametres': dict(mesure['parametres']),
        'pct_pondere_irradiance': mesure['pct'],
        'heures_retenues': mesure['heures_retenues'],
        'heures_sans_temperature': sans_temperature,
        'temperature_cellule_moyenne_c':
            mesure['temperature_cellule_moyenne_c'],
        'temperature_cellule_max_c': mesure['temperature_cellule_max_c'],
        'colonne_publiee': COLONNE_TEMPERATURE,
    }
    return rendue, _etapes.etape_appliquee(
        LIBELLE,
        source=PROVENANCE_SOCIETE if provenance == PROVENANCE_SOCIETE
        else PROVENANCE_FICHE,
        entree=entree, reference=REFERENCE,
        gain=_est_un_gain(serie, rendue))


# ── le type de pose, LU du document ────────────────────────────────────

def _poses_du_document(contexte):
    """``(types_lus, type_pose, champ)`` — rien n'est supposé hors du document.

    Le premier plan qui NOMME sa pose fixe le type retenu ; tous les types
    lus sont publiés pour qu'un document mixte soit VU plutôt que réduit en
    silence à son premier pan.
    """
    types = []
    retenu, champ = None, ''
    for plan in contexte.get('plans') or ():
        if not isinstance(plan, dict):
            continue
        type_plan, champ_plan = _pose_du_plan(plan)
        if type_plan is None:
            continue
        if type_plan not in types:
            types.append(type_plan)
        if retenu is None:
            retenu, champ = type_plan, champ_plan
    return types, retenu, champ


def _pose_du_plan(plan):
    """La pose d'UN plan, et le champ qui l'a donnée."""
    for champ in CHAMPS_POSE:
        valeur = plan.get(champ)
        if isinstance(valeur, str) and valeur.strip():
            return _normaliser(valeur), f'plans[].{champ}'
    flush = plan.get('flush')
    if not isinstance(flush, bool):
        geometrie = plan.get('geometry') or plan.get('geometrie')
        if isinstance(geometrie, dict):
            flush = geometrie.get('flush')
    if isinstance(flush, bool):
        return (POSE_INTEGRE if flush else POSE_CHASSIS), 'plans[].flush'
    return None, ''


def _normaliser(texte):
    """Une clé de pose comparable : minuscules, sans accent ni tiret."""
    brut = str(texte).strip().lower()
    accents = {'à': 'a', 'â': 'a', 'ä': 'a', 'é': 'e', 'è': 'e', 'ê': 'e',
               'ë': 'e', 'î': 'i', 'ï': 'i', 'ô': 'o', 'ö': 'o', 'ù': 'u',
               'û': 'u', 'ü': 'u', 'ç': 'c'}
    plat = ''.join(accents.get(lettre, lettre) for lettre in brut)
    return '_'.join(plat.replace('-', ' ').replace('_', ' ').split())


# ── la table société, et ce qu'elle exige d'elle-même ──────────────────

def _coefficients_societe(contexte, type_pose):
    """``(coefficients, entree_publiee, ecart)`` lus dans le réglage société.

    Une entrée de la table qui ne porte pas sa propre ``source`` n'est PAS
    employée : elle est écartée, et l'écart est dit dans la mention (D-CALX 7
    — un chiffre qu'on ne peut pas sourcer ne se défend pas).
    """
    saisie = _etapes.reglage(contexte, CLE_REGLAGE)
    if not saisie or type_pose is None:
        return {}, None, ''
    table = saisie.get('valeur')
    if not isinstance(table, dict):
        return {}, None, ''
    entree = None
    for cle, valeur in table.items():
        if _normaliser(cle) == type_pose and isinstance(valeur, dict):
            entree = valeur
            break
    if entree is None:
        return {}, None, (
            f'aucune ligne « {type_pose} » dans la table société des '
            'coefficients par type de pose.')
    if not (entree.get('source') or '').strip():
        return {}, None, (
            f'la ligne « {type_pose} » de la table société est écartée : '
            'elle ne porte pas sa source.')
    uc = _nombre(entree.get('uc_w_m2k'))
    if uc is None or uc <= 0:
        return {}, None, (
            f'la ligne « {type_pose} » de la table société ne porte pas de '
            'Uc exploitable.')
    coefficients = {'uc_w_m2k': uc, 'uv_w_m3sk': _nombre(entree.get(
        'uv_w_m3sk'))}
    publiee = {
        'type_pose': type_pose,
        'uc_w_m2k': uc,
        'uv_w_m3sk': coefficients['uv_w_m3sk'],
        'source': entree.get('source'),
        'reference': entree.get('reference') or '',
        'source_du_reglage': saisie.get('source'),
    }
    return coefficients, publiee, ''


def _provenance(modele, table_societe_employee):
    if modele == MODELE_NOCT:
        return PROVENANCE_NOCT
    if modele == MODELE_FAIMAN and table_societe_employee:
        return PROVENANCE_SOCIETE
    return PROVENANCE_FICHE


def _champ_manquant(specs):
    """LE champ à saisir pour que l'étape devienne calculable.

    Trois refus possibles, trois champs différents : le coefficient de
    puissance de la fiche, le couple Uc/Uv (société) ou la NOCT, et enfin les
    colonnes de la série quand la fiche dit tout mais que la météo est muette.
    """
    if _nombre(specs.get('temp_coeff_pmax_pct_c')) is None:
        return 'fiche_module.temp_coeff_pmax_pct_c'
    uc = _nombre(specs.get('uc_w_m2k'))
    if (uc is None or uc <= 0) and _nombre(specs.get('noct_c')) is None:
        return (f'{CLE_REGLAGE} (réglages simulation) ou '
                'fiche_module.uc_w_m2k ou fiche_module.noct_c')
    return 'serie_horaire.gi_w_m2 et serie_horaire.t2m_c'


# ── la dérate, heure par heure ─────────────────────────────────────────

def _appliquer_heure_par_heure(serie, points, mesure):
    """``(serie_rendue, heures_sans_temperature)`` — copie PURE des points."""
    gamma = mesure['parametres']['temp_coeff_pmax_pct_c']
    modele = mesure['modele']
    parametres = {cle: valeur for cle, valeur in mesure['parametres'].items()
                  if cle in ('uc_w_m2k', 'uv_w_m3sk', 'noct_c')}
    colonne = _etapes.colonne_energie(serie)
    rendus = []
    sans_temperature = 0
    for point in points:
        if not isinstance(point, dict):
            rendus.append(point)
            continue
        copie = dict(point)
        temperature = _temperature(point, modele, parametres)
        if temperature is None:
            sans_temperature += 1
            rendus.append(copie)
            continue
        copie[COLONNE_TEMPERATURE] = round(temperature, 2)
        if colonne is not None:
            valeur = _nombre(point.get(colonne))
            if valeur is not None:
                facteur = 1.0 + gamma * (temperature - TEMPERATURE_STC_C) \
                    / 100.0
                copie[colonne] = valeur * facteur
        rendus.append(copie)
    rendue = dict(serie)
    rendue['points'] = rendus
    if colonne is not None:
        rendue['colonne_energie'] = colonne
    return rendue, sans_temperature


def _temperature(point, modele, parametres):
    irradiance = _nombre(point.get('gi_w_m2'))
    if irradiance is None:
        irradiance = _nombre(point.get('gh_w_m2'))
    if irradiance is None:
        return None
    return temperature_cellule(
        t_air_c=point.get('t2m_c'), irradiance_w_m2=irradiance,
        modele=modele, vent_m_s=point.get('ws10m'), **parametres)


def _est_un_gain(avant, apres):
    """Le bilan de l'étape ajoute-t-il de l'énergie ? (site froid)."""
    depart = _etapes.energie_kwh(avant)
    arrivee = _etapes.energie_kwh(apres)
    if depart is None or arrivee is None:
        return False
    return arrivee > depart


def _nombre(valeur):
    if isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre:
        return None
    return nombre
