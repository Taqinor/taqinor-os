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
2 bis. ACAL1671 (D-ACAL-84) — sans ligne à son nom, la pose se relie à une
   ligne de la table par :data:`CORRESPONDANCE_POSE` : châssis ⇒ « pose
   libre », affleurant ⇒ « dos isolé » (le document réel dit sa pose par
   ``flush``), dite « par défaut — à confirmer ».
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
from ..valeurs import nombre as _nombre

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

#: ACAL1671 (D-ACAL-84) — la table FERMÉE qui relie la pose lue sur le document
#: à une ligne de la table société quand elle n'en porte pas une à son nom :
#: châssis ⇒ « pose libre » (air tout autour), affleurant ⇒ « dos isolé ». Les
#: coefficients restent dans les DONNÉES (``data/profil_depart.json``) ; ici
#: seulement des NOMS de lignes. Une ligne à son propre nom prime toujours.
CORRESPONDANCE_POSE = {POSE_CHASSIS: 'pose_libre', POSE_INTEGRE: 'dos_isole'}

#: La mention d'une ligne prise par correspondance (dite à l'écran et au rapport).
MENTION_CORRESPONDANCE = (
    'par défaut — à confirmer : pose « {pose} » lue sur le document, ligne '
    '« {ligne} » de la table société (D-ACAL-84).')

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
    # ACAL1607 — la fiche du module POSÉ (``construire_contexte``), à défaut
    # celle du module par défaut de l'entrée.
    fiche = contexte.get('fiche_module_pose') or contexte.get('fiche_module')
    fiche = dict(fiche) if isinstance(fiche, dict) else {}

    types_lus, type_pose, champ_pose = _poses_du_document(contexte)
    coefficients, entree_societe, ecart_societe = _coefficients_societe(
        contexte, type_pose, _genre_de_pose(contexte, type_pose))

    specs = dict(fiche)
    specs.update(coefficients)
    points = list((serie or {}).get('points') or ())
    mesure = perte_thermique(specs, points)
    if not mesure['calculable']:
        motif = mesure['motif']
        if not _forfait_saisi(contexte):
            # ACAL1607 — aucun poste « thermique » saisi : aucun forfait
            # n'est conservé, la phrase de ``services/thermique.py`` mentirait.
            motif = motif.replace(PHRASE_FORFAIT, '')
        if ecart_societe:
            # ACAL1934 — la table société est REMPLIE mais ne sert pas cette
            # pose : la vraie cause part avec l'omission (``a_renseigner``).
            motif = f'{motif} Table société : {ecart_societe}'
        return serie, _etapes.etape_omise(
            LIBELLE, motif, champ=_champ_manquant(specs))

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
        # CALX164 — ce que le vent a coûté ou n'a pas pu donner : les heures
        # qui portaient vraiment un ``ws10m``, et les hypothèses NOMMÉES qui
        # en découlent (fiche muette sur Uv, ou série muette sur le vent).
        'heures_avec_vent': mesure['heures_avec_vent'],
        'hypotheses': list(mesure['hypotheses']),
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

def _genre_de_pose(contexte, type_pose):
    """ACAL1671 — « chassis » ou « integre » : le type lu quand il l'est, sinon
    le booléen ``flush`` du premier pan qui le porte. Le document réel nomme
    sa famille (« south », « eastwest »), pas sa pose : c'est ``flush`` qui
    distingue le panneau à plat sur la couverture du panneau relevé. ``None``
    quand rien ne le dit — la correspondance n'est jamais devinée."""
    if type_pose in CORRESPONDANCE_POSE:
        return type_pose
    for plan in contexte.get('plans') or ():
        if not isinstance(plan, dict):
            continue
        flush = plan.get('flush')
        if not isinstance(flush, bool):
            geometrie = plan.get('geometry') or plan.get('geometrie')
            flush = (geometrie.get('flush')
                     if isinstance(geometrie, dict) else None)
        if isinstance(flush, bool):
            return POSE_INTEGRE if flush else POSE_CHASSIS
    return None


def _coefficients_societe(contexte, type_pose, genre=None):
    """``(coefficients, entree_publiee, ecart)`` lus dans le réglage société.

    Une entrée de la table qui ne porte pas sa propre ``source`` n'est PAS
    employée : elle est écartée, et l'écart est dit dans la mention (D-CALX 7
    — un chiffre qu'on ne peut pas sourcer ne se défend pas).

    ACAL1671 (D-ACAL-84) — sans ligne à son nom, la pose se relie à une ligne de
    la table par :data:`CORRESPONDANCE_POSE` (``genre`` : châssis ou
    affleurant), et la mention dit « par défaut — à confirmer ».
    """
    saisie = _etapes.reglage(contexte, CLE_REGLAGE)
    if not saisie or (type_pose is None and genre is None):
        return {}, None, ''
    table = saisie.get('valeur')
    if not isinstance(table, dict):
        return {}, None, ''
    entree, defaut = None, ''
    for cle, valeur in table.items():
        if _normaliser(cle) == type_pose and isinstance(valeur, dict):
            entree = valeur
            break
    ligne_par_defaut = CORRESPONDANCE_POSE.get(genre)
    if entree is None and ligne_par_defaut is not None:
        for cle, valeur in table.items():
            if (_normaliser(cle) == ligne_par_defaut
                    and isinstance(valeur, dict)):
                entree = valeur
                defaut = MENTION_CORRESPONDANCE.format(
                    pose=genre, ligne=ligne_par_defaut)
                break
    if entree is None:
        return {}, None, (
            f'aucune ligne « {type_pose or genre} » dans la table société des '
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
    return coefficients, publiee, defaut


def _provenance(modele, table_societe_employee):
    if modele == MODELE_NOCT:
        return PROVENANCE_NOCT
    if modele == MODELE_FAIMAN and table_societe_employee:
        return PROVENANCE_SOCIETE
    return PROVENANCE_FICHE


#: ACAL1607 — la phrase des motifs de ``services/thermique.py`` qui n'est
#: vraie que si un poste « thermique » forfaitaire est SAISI.
PHRASE_FORFAIT = ' Le poste forfaitaire est conservé et annoncé comme hypothèse.'


def _forfait_saisi(contexte):
    """Un poste « thermique » saisi avec un pourcentage lisible ?"""
    return any(isinstance(poste, dict) and poste.get('poste') == 'thermique'
               and _nombre(poste.get('pct')) is not None
               for poste in contexte.get('postes_saisis') or ())


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
