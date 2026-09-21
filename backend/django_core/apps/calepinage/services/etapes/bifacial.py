# -*- coding: utf-8 -*-
"""CALX177 — ÉTAPE « bifacial » : le GAIN de face arrière, mois par mois.

LE CONSTAT
----------
``services/bifacial.py`` (CAL141) calcule déjà le gain de face arrière par
GÉOMÉTRIE RÉELLE — facteur de vue isotrope ``(1 + cos β) / 2`` vers le sol,
fraction de sol libre vue par arctangente — et refuse tant que les cinq
entrées de ``PARAMETRES_REQUIS`` ne sont pas là. Il n'avait AUCUN appelant, et
son albédo était un SCALAIRE unique : un sol de terrasse rincé par la pluie
d'hiver et le même sol poussiéreux de juillet ne renvoient pas la même
lumière.

CETTE ÉTAPE NE RECALCULE RIEN : elle APPELLE ``bifacial.gain_bifacial`` une
fois PAR PAN ET PAR MOIS, avec l'albédo du mois, puis applique le gain heure
par heure selon le mois de chaque heure. Le modèle reste là-bas, entier ; ici
vivent seulement la LECTURE des entrées et leur mise en série.

D'OÙ VIENNENT LES ENTRÉES (D-CALX 7 : saisi avec provenance, ou OMIS)
----------------------------------------------------------------------
* **Bifacialité** — ``fiche_module.bifacialite_pct`` (CAL112, publié par
  ``apps.stock.selectors.specs_for_produit``). Une fiche RENSEIGNÉE qui ne
  porte pas de bifacialité décrit un module MONOFACIAL : l'étape est alors
  omise SANS rien réclamer — ce n'est pas une anomalie, et l'écran n'a aucun
  champ à faire remplir.
* **Géométrie** — LUE du document d'abord : la hauteur libre de pose
  (``poseSurfaces[].clearHeightM``, recopiée sur le plan), le pas entre
  rangées (``engine.rowPitchM``, MESURÉ par le moteur sur les rangées
  posées ; à défaut mesuré sur les centres ``zones[].geometry.panels[].cy``)
  et le taux d'occupation (GCR), dérivé du côté de table dans la pente et du
  pas quand le document ne le publie pas. La saisie société n'est qu'un REPLI,
  et il est NOMMÉ : ``entree.geometrie_source`` vaut ``document`` tant
  qu'aucun repli n'a servi, ``societe`` dès qu'un champ vient des réglages.
* **Albédo** — réglage société ``simulation.albedo_mensuel`` (CALX145) : DOUZE
  valeurs mensuelles, ou une valeur unique assumée pour les douze. Chaque
  valeur peut porter SA source (``{valeur, source}`` mois par mois) ; à
  défaut, la source du réglage vaut pour les douze.
* **Mismatch de face arrière** — réglage société
  ``simulation.bifacial_mismatch_arriere_pct``, SAISI. Non saisi ⇒ le gain
  sort BRUT et ``gain_bifacial`` l'annonce dans ses hypothèses. Le 10 % que
  PVsyst retient par défaut est CITÉ en texte dans ``reference`` (et proposé
  en aide à la saisie par l'écran de réglages) : il n'est jamais appliqué.

CE QUE ``gr_i_w_m2`` FAIT ICI — ET CE QU'IL N'Y FAIT PAS
----------------------------------------------------------
PVsyst avertit de ne pas confondre l'albédo « du projet » — celui avec lequel
la composante RÉFLÉCHIE de la face AVANT est calculée — et celui « du
bifacial », qui décrit le sol sous les rangées. La composante réfléchie de
PVGIS (``gr_i_w_m2``, CALX152) est donc LUE et publiée dans ``entree`` comme
REPÈRE de la première : on voit, à côté du gain arrière, quelle part de
l'irradiance avant PVGIS attribue déjà à une réflexion calculée avec SON
albédo. Elle n'entre dans AUCUN facteur du gain : composantes absentes ⇒ ce
repère vaut ``None`` avec son motif, et l'étape s'applique quand même.

CE QUI OMET L'ÉTAPE
--------------------
Une fiche renseignée sans bifacialité (silencieusement) ; sinon, tout
paramètre que ``gain_bifacial`` déclare ``manquant`` — ses libellés partent
TELS QUELS dans ``motif_omission``, un par un, jamais un « gain non
calculable » générique. Une série sans mois alors que l'albédo est mensuel
omet aussi l'étape, en nommant ``serie_horaire.mois``.

Module PUR : aucune base, aucun réseau, aucun appel PVGIS.
"""
from __future__ import annotations

from apps.calepinage.services import etapes as _etapes
from apps.calepinage.services.bifacial import PARAMETRES_REQUIS, gain_bifacial

#: La clé de réglage qui porte l'albédo (registre CALX145).
CLE_ALBEDO = 'albedo_mensuel'

#: Les trois clés du REPLI société de géométrie, et celle du mismatch
#: arrière — toutes déclarées au registre CALX145.
CLE_HAUTEUR = 'bifacial_hauteur_pose_m'
CLE_OCCUPATION = 'bifacial_taux_occupation'
CLE_PAS = 'bifacial_pas_rangee_m'
CLE_MISMATCH = 'bifacial_mismatch_arriere_pct'

#: Le champ de fiche qui dit qu'un module a une face arrière active.
CHAMP_BIFACIALITE = 'bifacialite_pct'

#: La composante RÉFLÉCHIE de la face avant (PVGIS, CALX152) — repère, pas
#: facteur.
COLONNE_REFLECHIE = 'gr_i_w_m2'
COLONNE_GLOBALE = 'gi_w_m2'

#: Les deux valeurs que ``entree.geometrie_source`` peut prendre.
SOURCE_DOCUMENT = 'document'
SOURCE_SOCIETE = 'societe'

#: Les deux modes de saisie de l'albédo, et leur nom publié.
MODE_MENSUEL = 'mensuel'
MODE_UNIQUE = 'unique'

#: Les douze mois, pour que chaque refus NOMME celui qui manque.
MOIS_LIBELLES = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                 'juillet', 'août', 'septembre', 'octobre', 'novembre',
                 'décembre')

#: La géométrie lue sur un pan : du nom canonique du contexte à la forme
#: brute du document ``roof_layout`` v2 (``zones[].geometry``) et à ce que le
#: moteur a rendu pour la surface de pose (``poseSurfaces[].engine``, CAL89).
CHEMINS_PAS = (('pas_rangee_m',), ('engine', 'rowPitchM'),
               ('geometry', 'rowPitchM'))
CHEMINS_HAUTEUR = (('hauteur_pose_m',), ('engine', 'clearHeightM'),
                   ('geometry', 'clearHeightM'), ('clearHeightM',),
                   ('batiment', 'hauteurM'), ('geometry', 'hauteurM'))
CHEMINS_OCCUPATION = (('taux_occupation',), ('geometry', 'gcr'),
                      ('engine', 'gcr'))
CHEMINS_LONGUEUR = (('longueur_table_m',), ('geometry', 'panelSlopeLenM'),
                    ('longueur_pente_m',))
CHEMINS_INCLINAISON = (('inclinaison_deg',), ('geometry', 'tiltDeg'),
                       ('tiltDeg',))
CHEMINS_KWC = (('kwc',), ('geometry', 'kwc'))

#: Les noms de champ que l'écran doit montrer quand un repli manque aussi.
CHAMP_HAUTEUR = ('poseSurfaces[].clearHeightM (hauteur libre de pose), '
                 f'à défaut le réglage société « simulation.{CLE_HAUTEUR} »')
CHAMP_PAS = ('zones[].geometry.rowPitchM (pas entre rangées), à défaut les '
             'centres zones[].geometry.panels[].cy, à défaut le réglage '
             f'société « simulation.{CLE_PAS} »')
CHAMP_OCCUPATION = ("zones[].geometry.gcr (taux d'occupation du sol), à "
                    'défaut panelSlopeLenM ÷ rowPitchM, à défaut le réglage '
                    f'société « simulation.{CLE_OCCUPATION} »')

#: La provenance publiée : la fiche produit pour la face arrière, la
#: géométrie du document et la saisie société pour le sol.
SOURCE = 'fiche+layout+societe'

REFERENCE = (
    'PVsyst — Bifacial systems : l\'irradiance de face arrière est calculée '
    'par FACTEURS DE VUE (albédo, hauteur de pose, taux d\'occupation), et '
    "PVsyst avertit de ne pas confondre l'albédo « du projet » (face avant) "
    "et celui « du bifacial » (le sol sous les rangées) ; il retient par "
    'défaut une perte de mismatch de face arrière de 10 % — chiffre CITÉ '
    'ici, jamais appliqué : il ne compte que s\'il est SAISI '
    '(https://www.pvsyst.com/help/project-design/bifacial-systems/index.html)'
    '. HelioScope — Bifacial Modules : l\'albédo s\'y renseigne MOIS PAR '
    'MOIS ou en valeur uniforme (https://help-center.helioscope.com/hc/en-us/'
    'articles/41739863126163-Bifacial-Modules).')

LIBELLE = 'Gain bifacial en face arrière'

__all__ = ['CLE_ALBEDO', 'CLE_HAUTEUR', 'CLE_OCCUPATION', 'CLE_PAS',
           'CLE_MISMATCH', 'CHAMP_BIFACIALITE', 'COLONNE_REFLECHIE',
           'COLONNE_GLOBALE', 'SOURCE_DOCUMENT', 'SOURCE_SOCIETE',
           'MODE_MENSUEL', 'MODE_UNIQUE', 'MOIS_LIBELLES', 'SOURCE',
           'REFERENCE', 'LIBELLE', 'appliquer']


# ── les motifs, chacun nommant ce qui manque ───────────────────────────

MOTIF_MONOFACIAL = (
    'La fiche du module ne déclare aucune bifacialité '
    f'(« {CHAMP_BIFACIALITE} ») : ce module est MONOFACIAL, il n\'a pas de '
    "face arrière à compter. Rien ne manque — l'étape est simplement sans "
    'objet ici.')

MOTIF_MOIS_ABSENT = (
    "La série horaire ne porte pas le mois de chacune de ses heures : un "
    "albédo MENSUEL ne peut être attribué à aucune heure, et aucun mois n'est "
    "comblé par la moyenne des autres.")

MOTIF_AUCUN_PAN = (
    "Aucun pan exploitable n'est décrit : sans géométrie de rangée, la "
    "fraction de sol vue depuis la face arrière n'a aucun sens.")

MOTIF_REFLECHIE_ABSENTE = (
    "PVGIS n'a pas rendu la composante réfléchie « gr_i_w_m2 » : le repère "
    "de réflexion de face AVANT reste inconnu. Il n'entre dans aucun facteur "
    'du gain arrière — seul le repère manque, pas le calcul.')


def appliquer(serie, contexte):
    """``(serie, etape)`` — le gain de face arrière, ou son silence motivé."""
    contexte = contexte if isinstance(contexte, dict) else {}
    serie = serie if isinstance(serie, dict) else {}

    fiche = contexte.get('fiche_module')
    fiche = fiche if isinstance(fiche, dict) else {}
    bifacialite = _nombre(fiche.get(CHAMP_BIFACIALITE))
    if fiche and bifacialite is None:
        # Fiche RENSEIGNÉE sans bifacialité = module monofacial : omission
        # SANS champ manquant, donc sans rien à réclamer à personne.
        return serie, _etapes.etape_omise(LIBELLE, MOTIF_MONOFACIAL)

    albedos, mode, motif_albedo = _albedos_mensuels(contexte)
    mismatch, source_mismatch = _mismatch_arriere(contexte)
    geometries, repli_societe = _geometries_des_plans(contexte)
    if not geometries:
        return serie, _etapes.etape_omise(LIBELLE, MOTIF_AUCUN_PAN)

    # Le diagnostic de RÉFÉRENCE : il porte les « manquants » nommés par
    # ``services/bifacial.py`` — on les publie tels quels plutôt que d'en
    # réécrire une seconde liste qui divergerait.
    temoin = gain_bifacial(
        bifacialite_pct=bifacialite,
        albedo=albedos[0][0],
        hauteur_pose_m=geometries[0]['hauteur_pose_m'],
        taux_occupation=geometries[0]['taux_occupation'],
        pas_rangee_m=geometries[0]['pas_rangee_m'],
        inclinaison_deg=geometries[0]['inclinaison_deg'],
        mismatch_arriere_pct=mismatch,
        source_albedo=albedos[0][1])
    if not temoin['calculable']:
        return serie, _etapes.etape_omise(
            LIBELLE, _motif_manquants(temoin, motif_albedo),
            champ=_champ_manquant(temoin))

    if mode == MODE_MENSUEL:
        manquant = _mois_absent(serie)
        if manquant:
            return serie, _etapes.etape_omise(
                LIBELLE, MOTIF_MOIS_ABSENT, champ='serie_horaire.mois')

    gains, diagnostics, echecs = _gains_par_mois(
        bifacialite, albedos, geometries, mismatch)
    if echecs:
        return serie, _etapes.etape_omise(
            LIBELLE, _motif_mois_refuses(echecs),
            champ=f'simulation.{CLE_ALBEDO}')

    repere, motif_repere = _repere_reflechi(serie)
    entree = {
        'geometrie_source': SOURCE_SOCIETE if repli_societe
        else SOURCE_DOCUMENT,
        'bifacialite_pct': bifacialite,
        'albedo_mode': mode,
        'albedo_mensuel': [
            {'mois': MOIS_LIBELLES[rang], 'valeur': valeur,
             'source': source}
            for rang, (valeur, source) in enumerate(albedos)],
        'mismatch_arriere_pct': mismatch,
        'source_mismatch': source_mismatch,
        'gain_mensuel_pct': [
            {'mois': MOIS_LIBELLES[rang], 'gain_pct': gains[rang]}
            for rang in range(12)],
        'plans': [
            {'cle': geometrie['cle'],
             'poids': round(geometrie['poids'], 6),
             'pas_rangee_m': geometrie['pas_rangee_m'],
             'hauteur_pose_m': geometrie['hauteur_pose_m'],
             'taux_occupation': geometrie['taux_occupation'],
             'inclinaison_deg': geometrie['inclinaison_deg'],
             'origines': dict(geometrie['origines'])}
            for geometrie in geometries],
        'facteurs_temoin': diagnostics[0]['facteurs'] if diagnostics else {},
        'hypotheses': diagnostics[0]['hypotheses'] if diagnostics else [],
        'repere_reflechi_avant': repere,
        'motif_repere_reflechi': motif_repere,
    }

    rendue = _appliquer_par_mois(serie, gains, mode)
    return rendue, _etapes.etape_appliquee(
        LIBELLE, source=SOURCE, entree=entree, reference=REFERENCE, gain=True)


# ── l'albédo, mois par mois, chacun avec sa source ─────────────────────

def _albedos_mensuels(contexte):
    """``(douze (valeur, source), mode, motif)`` — jamais un albédo supposé.

    ``valeur`` peut être ``None`` : l'absence remonte alors telle quelle à
    ``gain_bifacial``, qui la NOMME dans ses ``manquants``.
    """
    saisie = _etapes.reglage(contexte, CLE_ALBEDO)
    if not saisie:
        return ([(None, None)] * 12, MODE_UNIQUE,
                f"Aucun albédo saisi (« simulation.{CLE_ALBEDO} »).")

    source_globale = saisie.get('source')
    brute = saisie.get('valeur')
    if isinstance(brute, dict):
        brute = _douze_depuis_dict(brute)
        if brute is None:
            return ([(None, None)] * 12, MODE_MENSUEL,
                    f"La saisie « simulation.{CLE_ALBEDO} » ne porte pas les "
                    'douze mois.')
    if isinstance(brute, (list, tuple)):
        if len(brute) != 12:
            return ([(None, None)] * 12, MODE_MENSUEL,
                    f"La saisie mensuelle « simulation.{CLE_ALBEDO} » attend "
                    f'12 valeurs, une par mois (reçu : {len(brute)}). Une '
                    'année incomplète se lirait comme une année complète.')
        valeurs = []
        for entree in brute:
            if isinstance(entree, dict):
                valeurs.append((_nombre(entree.get('valeur')),
                                entree.get('source') or source_globale))
            else:
                valeurs.append((_nombre(entree), source_globale))
        return valeurs, MODE_MENSUEL, ''

    unique = _nombre(brute)
    return [(unique, source_globale)] * 12, MODE_UNIQUE, ''


def _douze_depuis_dict(brute):
    """Les douze mois d'un dict keyé ``1``…``12``, ou ``None``."""
    valeurs = []
    for rang in range(1, 13):
        if rang in brute:
            valeurs.append(brute[rang])
        elif str(rang) in brute:
            valeurs.append(brute[str(rang)])
        else:
            return None
    return valeurs


def _mismatch_arriere(contexte):
    """``(pourcentage, source)`` du mismatch de face arrière, SAISI."""
    saisie = _etapes.reglage(contexte, CLE_MISMATCH)
    if not saisie:
        return None, None
    return _nombre(saisie.get('valeur')), saisie.get('source')


# ── la géométrie : le document d'abord, la société en repli NOMMÉ ──────

def _geometries_des_plans(contexte):
    """``(liste de géométries, un repli société a-t-il servi ?)``."""
    plans = [plan for plan in (contexte.get('plans') or ())
             if isinstance(plan, dict)]
    if not plans:
        return [], False

    repli = _repli_societe(contexte)
    geometries = []
    repli_utilise = False
    poids_manquant = False
    for rang, plan in enumerate(plans):
        origines = {}
        pas = _valeur(plan, CHEMINS_PAS)
        if pas is not None:
            origines['pas_rangee_m'] = SOURCE_DOCUMENT
        else:
            pas = _pas_mesure(plan)
            if pas is not None:
                origines['pas_rangee_m'] = SOURCE_DOCUMENT
            else:
                pas = repli[CLE_PAS]
                origines['pas_rangee_m'] = SOURCE_SOCIETE

        hauteur = _valeur(plan, CHEMINS_HAUTEUR)
        if hauteur is not None:
            origines['hauteur_pose_m'] = SOURCE_DOCUMENT
        else:
            hauteur = repli[CLE_HAUTEUR]
            origines['hauteur_pose_m'] = SOURCE_SOCIETE

        longueur = _valeur(plan, CHEMINS_LONGUEUR)
        occupation = _valeur(plan, CHEMINS_OCCUPATION)
        if occupation is not None:
            origines['taux_occupation'] = SOURCE_DOCUMENT
        elif longueur is not None and pas:
            # GCR = côté de table dans la pente ÷ pas entre rangées. C'est la
            # DÉFINITION du taux d'occupation, pas un coefficient.
            occupation = longueur / pas
            origines['taux_occupation'] = SOURCE_DOCUMENT
        else:
            occupation = repli[CLE_OCCUPATION]
            origines['taux_occupation'] = SOURCE_SOCIETE

        if SOURCE_SOCIETE in origines.values():
            repli_utilise = True

        poids = _valeur(plan, CHEMINS_KWC)
        if poids is None or poids <= 0.0:
            poids_manquant = True
        geometries.append({
            'cle': plan.get('cle') or plan.get('id') or f'pan-{rang + 1}',
            'pas_rangee_m': pas,
            'hauteur_pose_m': hauteur,
            'taux_occupation': occupation,
            'inclinaison_deg': _valeur(plan, CHEMINS_INCLINAISON),
            'longueur_table_m': longueur,
            'origines': origines,
            'poids': poids,
        })

    if len(geometries) == 1 or poids_manquant:
        # Sans puissance crête sur CHAQUE pan, aucune pondération n'est
        # inventée : les pans pèsent à parts égales et le disent.
        part = 1.0 / len(geometries)
        for geometrie in geometries:
            geometrie['poids'] = part
    else:
        total = sum(geometrie['poids'] for geometrie in geometries)
        for geometrie in geometries:
            geometrie['poids'] = geometrie['poids'] / total
    return geometries, repli_utilise


def _repli_societe(contexte):
    """Les trois valeurs de géométrie SAISIES par la société, ou ``None``."""
    valeurs = {}
    for cle in (CLE_PAS, CLE_HAUTEUR, CLE_OCCUPATION):
        saisie = _etapes.reglage(contexte, cle)
        valeurs[cle] = _nombre(saisie.get('valeur')) if saisie else None
    return valeurs


def _pas_mesure(plan):
    """Le pas MESURÉ sur les centres ``geometry.panels[].cy``, ou ``None``.

    Deux rangées posées ont deux ordonnées de centre distinctes : l'écart le
    plus petit entre deux ordonnées consécutives EST le pas. Un plan d'une
    seule rangée n'en a pas, et on ne lui en invente pas.
    """
    geometrie = plan.get('geometry')
    panneaux = geometrie.get('panels') if isinstance(geometrie, dict) else None
    ordonnees = set()
    for panneau in panneaux or ():
        if not isinstance(panneau, dict):
            continue
        valeur = _nombre(panneau.get('cy'))
        if valeur is not None:
            ordonnees.add(round(valeur, 3))
    if len(ordonnees) < 2:
        return None
    triees = sorted(ordonnees)
    ecarts = [suivant - courant
              for courant, suivant in zip(triees, triees[1:])
              if suivant - courant > 0.0]
    return min(ecarts) if ecarts else None


# ── le gain, pan par pan et mois par mois ──────────────────────────────

def _gains_par_mois(bifacialite, albedos, geometries, mismatch):
    """``(douze gains %, diagnostics, mois refusés)`` — rien d'extrapolé."""
    gains = []
    diagnostics = []
    echecs = []
    for rang in range(12):
        albedo, source_albedo = albedos[rang]
        gain_du_mois = 0.0
        for geometrie in geometries:
            diagnostic = gain_bifacial(
                bifacialite_pct=bifacialite,
                albedo=albedo,
                hauteur_pose_m=geometrie['hauteur_pose_m'],
                taux_occupation=geometrie['taux_occupation'],
                pas_rangee_m=geometrie['pas_rangee_m'],
                inclinaison_deg=geometrie['inclinaison_deg'],
                mismatch_arriere_pct=mismatch,
                source_albedo=source_albedo)
            if not diagnostic['calculable']:
                echecs.append((MOIS_LIBELLES[rang], diagnostic['motif']))
                gain_du_mois = None
                break
            if rang == 0:
                diagnostics.append(diagnostic)
            gain_du_mois += geometrie['poids'] * diagnostic['gain_pct']
        gains.append(None if gain_du_mois is None
                     else round(gain_du_mois, 6))
    return gains, diagnostics, echecs


def _appliquer_par_mois(serie, gains, mode):
    """Une COPIE de la série dont chaque heure porte le gain de SON mois."""
    colonne = _etapes.colonne_energie(serie)
    if colonne is None:
        # Aucune colonne d'énergie lisible : il n'y a rien à mettre à
        # l'échelle, et l'ordonnanceur publiera des null (jamais des 0).
        return serie
    points = []
    for point in serie.get('points') or []:
        if mode == MODE_UNIQUE:
            gain = gains[0]
        else:
            gain = _gain_du_point(point, gains)
        valeur = point.get(colonne) if isinstance(point, dict) else None
        if not gain or valeur is None:
            points.append(point)
            continue
        try:
            echelle = float(valeur) * (1.0 + gain / 100.0)
        except (TypeError, ValueError):
            points.append(point)
            continue
        copie = dict(point)
        copie[colonne] = echelle
        points.append(copie)
    rendue = dict(serie)
    rendue['points'] = points
    rendue['colonne_energie'] = colonne
    return rendue


def _gain_du_point(point, gains):
    """Le gain du MOIS de cette heure, ou ``0`` si le mois est illisible."""
    mois = _nombre((point or {}).get('mois')) if isinstance(point,
                                                            dict) else None
    if mois is None or not 1 <= int(mois) <= 12:
        return 0.0
    return gains[int(mois) - 1] or 0.0


# ── le repère de réflexion AVANT (PVGIS), jamais un facteur ────────────

def _repere_reflechi(serie):
    """``(repère, motif)`` — la part réfléchie de la face AVANT selon PVGIS.

    C'est l'albédo « du projet » que PVsyst distingue de celui « du
    bifacial ». Publié pour être LU, jamais multiplié à quoi que ce soit.
    """
    points = serie.get('points') or []
    if serie.get('composantes_disponibles') is False or not points:
        return None, MOTIF_REFLECHIE_ABSENTE
    reflechie = globale = 0.0
    lues = 0
    for point in points:
        if not isinstance(point, dict):
            continue
        part = _nombre(point.get(COLONNE_REFLECHIE))
        totale = _nombre(point.get(COLONNE_GLOBALE))
        if part is None or totale is None:
            continue
        reflechie += part
        globale += totale
        lues += 1
    if not lues or globale <= 0.0:
        return None, MOTIF_REFLECHIE_ABSENTE
    return {
        'part_reflechie_avant_pct': round(100.0 * reflechie / globale, 3),
        'heures_lues': lues,
        'lecture': (
            "Composante RÉFLÉCHIE de la face avant telle que PVGIS la rend, "
            "calculée avec l'albédo de PVGIS : c'est l'albédo « du projet », "
            "distinct de celui du sol sous les rangées employé ci-dessus. "
            "Aucun facteur du gain arrière n'en dépend."),
    }, ''


# ── les motifs qui NOMMENT, un par un ──────────────────────────────────

def _motif_manquants(temoin, motif_albedo):
    """Le motif d'omission, bâti sur les « manquants » de ``gain_bifacial``."""
    motif = temoin['motif']
    if motif_albedo and 'albédo' in motif:
        motif = f'{motif} {motif_albedo}'
    return motif


def _champ_manquant(temoin):
    """LE champ que l'écran doit pointer — le premier réellement absent.

    Aucun ``manquant`` (le refus vient de bornes dépassées, pas d'une
    absence) ⇒ aucun champ n'est pointé : le motif se suffit.
    """
    manquants = temoin.get('manquants') or []
    if not manquants:
        return ''
    libelles = dict(PARAMETRES_REQUIS)
    if libelles.get('albedo') in manquants:
        return f'simulation.{CLE_ALBEDO}'
    if libelles.get('hauteur_pose_m') in manquants:
        return CHAMP_HAUTEUR
    if libelles.get('pas_rangee_m') in manquants:
        return CHAMP_PAS
    if libelles.get('taux_occupation') in manquants:
        return CHAMP_OCCUPATION
    if libelles.get('bifacialite_pct') in manquants:
        return f'fiche_module.{CHAMP_BIFACIALITE}'
    return 'zones[].geometry.tiltDeg (inclinaison des tables)'


def _motif_mois_refuses(echecs):
    """Le motif quand un MOIS précis n'a pas de gain calculable."""
    noms = ', '.join(f'« {mois} »' for mois, _ in echecs)
    premier = echecs[0][1]
    return (f"L'albédo mensuel n'est pas exploitable pour {noms} : {premier} "
            "Aucun mois n'est comblé par la moyenne des autres.")


def _mois_absent(serie):
    """Un point au moins est-il sans mois lisible ?"""
    for point in serie.get('points') or []:
        if not isinstance(point, dict):
            return True
        mois = _nombre(point.get('mois'))
        if mois is None or not 1 <= int(mois) <= 12:
            return True
    return False


# ── lectures élémentaires ──────────────────────────────────────────────

def _valeur(plan, chemins):
    """La première valeur trouvée parmi ``chemins``, ou ``None``."""
    for chemin in chemins:
        courant = plan
        for cle in chemin:
            if not isinstance(courant, dict):
                courant = None
                break
            courant = courant.get(cle)
        nombre = _nombre(courant)
        if nombre is not None:
            return nombre
    return None


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
