# -*- coding: utf-8 -*-
"""CALX160 — étape « IAM » : Fresnel par défaut, physique et sourcé.

LE CONSTAT
----------
``services/pertes.py::CATALOGUE`` ouvre sur ``iam`` (référence « PVsyst —
array and system losses »), mais ce poste n'a jamais eu ni valeur ni calcul.
Or c'est le SEUL poste de la chaîne qui n'exige AUCUN coefficient société :
les lois de Fresnel suffisent, et elles sont de la physique, pas un réglage.

LE MODÈLE PAR DÉFAUT, ET SA SOURCE
------------------------------------
PVsyst — *Array incidence loss (IAM)* : « Fresnel's laws » est le modèle par
DÉFAUT depuis la v6.67 ; l'ASHRAE ``FIAM = 1 − b0·(1/cos i − 1)`` y est
documenté comme déprécié et sous-estimant l'IAM entre 30° et 60°
(https://www.pvsyst.com/help/project-design/array-and-system-losses/array-incidence-loss-iam.html).

Le calcul retenu ici est la transmission d'un dioptre air/verre, sans aucun
coefficient ajusté :

    θ_r = arcsin(sin θ / n)
    τ(θ) = 1 − ½ [ sin²(θ_r − θ)/sin²(θ_r + θ) + tan²(θ_r − θ)/tan²(θ_r + θ) ]
    IAM(θ) = τ(θ) / τ(0)

(Fresnel, écrit sous cette forme par Duffie & Beckman, *Solar Engineering of
Thermal Processes*, § 5.1 « Reflection of radiation ».) L'indice du verre
solaire vaut ``n = 1,526`` — valeur CITÉE, employée telle quelle par PVsyst
sur la page ci-dessus et par De Soto, Klein & Beckman, *Improvement and
validation of a model for photovoltaic array performance*, Solar Energy 80
(2006). Un verre à revêtement antireflet déclaré sur la FICHE PRODUIT prend
``n = 1,3``, l'autre valeur citée par la même page.

La seule absorption modélisée est la RÉFLEXION : aucun coefficient
d'extinction ni épaisseur de verre n'est inventé ici — ces deux nombres ne
figurent sur aucune fiche produit que le dépôt sache lire.

LE DIFFUS ET LE RÉFLÉCHI NE SONT PAS DU DIRECT
------------------------------------------------
Ils n'arrivent pas sous un angle : ils arrivent de tout le ciel et de tout
le sol. Ils reçoivent donc l'IAM du MÊME modèle, pris à l'angle d'incidence
EFFECTIF de Brandemuehl & Beckman, repris par Duffie & Beckman (éq. 5.4.2) :

    θ_eff,ciel = 59,7 − 0,1388·β + 0,001497·β²
    θ_eff,sol  = 90  − 0,5788·β + 0,002693·β²

avec β l'inclinaison du plan. Traiter le diffus comme du direct est
précisément l'erreur que ce découpage (CALX152) existe pour éviter.

LES AUTRES MODÈLES
-------------------
``parametres.simulation.modele_iam`` (CALX145) choisit ``ashrae``, qui exige
``b0_iam`` SAISI avec sa provenance. Sans ce coefficient, l'étape retombe
sur ``fresnel`` et le DIT dans ``entree.modele`` — jamais un ``b0`` par
défaut. ``martin_ruiz`` demanderait un ``a_r`` qui ne figure PAS au registre
de CALX145 : il retombe de la même façon, en nommant la clé absente.

AUCUN CHIFFRE INVENTÉ (D-CALX 7)
---------------------------------
Composantes absentes (CALX152), pan sans inclinaison ou sans azimut, site
sans coordonnées, base de temps non déclarée : l'étape s'OMET en NOMMANT le
champ manquant.
"""
from __future__ import annotations

import datetime
import math

from apps.calepinage.services import etapes
from apps.calepinage.services.pvgis_serie import MOTIF_COMPOSANTES_ABSENTES
from core.calepinage.soleil import position_solaire

#: Le nom du poste — celui de ``chaine_pertes.ORDRE_ETAPES``.
POSTE = 'iam'

#: Indice de réfraction du verre solaire — valeur CITÉE (PVsyst, page IAM ;
#: De Soto, Klein & Beckman 2006). Jamais ajustée, jamais « calibrée ».
INDICE_VERRE = 1.526

#: Indice retenu pour un verre à revêtement antireflet — l'autre valeur
#: citée par la même page de PVsyst. Employée SEULEMENT si la fiche produit
#: déclare le revêtement.
INDICE_VERRE_ANTIREFLET = 1.3

#: Les clés de fiche produit qui déclarent un revêtement antireflet.
CLES_ANTIREFLET = ('revetement_ar', 'traitement_antireflet',
                   'verre_antireflet')

#: Les modèles que la société peut demander par ``simulation.modele_iam``.
MODELES = ('fresnel', 'ashrae', 'martin_ruiz')

#: Au-delà de cet angle, le soleil est DERRIÈRE le plan : il n'y a plus de
#: faisceau direct sur la face avant. Ce n'est pas un seuil, c'est la
#: géométrie.
ANGLE_DERRIERE_LE_PLAN_DEG = 90.0

#: La référence publiée dans ``cascade[].reference``.
REFERENCE = (
    "PVsyst — Array incidence loss (IAM) : « Fresnel's laws » est le modèle "
    'par défaut depuis la v6.67, l’ASHRAE b0 y étant déprécié — '
    'https://www.pvsyst.com/help/project-design/array-and-system-losses/'
    'array-incidence-loss-iam.html. Indice du verre n = 1,526 : même page, '
    'et De Soto, Klein & Beckman, Solar Energy 80 (2006). Angles '
    'd’incidence effectifs du diffus et du réfléchi : Brandemuehl & Beckman, '
    'repris par Duffie & Beckman, Solar Engineering of Thermal Processes, '
    'éq. 5.4.2. Angle d’incidence du direct : core.calepinage.soleil '
    '(CALX146).')

#: Le motif publié quand la série ne dit pas à quelle base de temps ses
#: heures se rapportent.
MOTIF_SANS_BASE_DE_TEMPS = (
    "La base de temps de la série n'est pas déclarée : PVGIS rend ses heures "
    "en heure locale standard (« localtime=1 ») et le décalage du site n'est "
    "pas posé. Sans lui, l'angle d'incidence serait calculé à la mauvaise "
    'heure.')

__all__ = ['POSTE', 'INDICE_VERRE', 'INDICE_VERRE_ANTIREFLET',
           'CLES_ANTIREFLET', 'MODELES', 'ANGLE_DERRIERE_LE_PLAN_DEG',
           'REFERENCE', 'MOTIF_SANS_BASE_DE_TEMPS', 'appliquer']


# ── le modèle, privé mais vérifié pièce par pièce ───────────────────────

def _iam_fresnel(angle_deg, indice=INDICE_VERRE):
    """L'IAM d'un dioptre air/verre à l'incidence ``angle_deg``.

    ``IAM(0°) = 1`` par construction (la transmission est normalisée à
    l'incidence normale), décroissance monotone jusqu'au rasant, et ``0``
    dès que le soleil passe derrière le plan.
    """
    angle = abs(float(angle_deg))
    if angle >= ANGLE_DERRIERE_LE_PLAN_DEG:
        return 0.0
    normale = _transmission_fresnel(0.0, indice)
    if not normale:
        return 0.0
    return max(0.0, _transmission_fresnel(angle, indice) / normale)


def _iam_ashrae(angle_deg, b0):
    """L'IAM ASHRAE ``1 − b0·(1/cos i − 1)``, borné à zéro.

    Déprécié par PVsyst (il sous-estime l'IAM entre 30° et 60°) : il n'est
    employé que si la société le DEMANDE et SAISIT son ``b0``.
    """
    angle = abs(float(angle_deg))
    if angle >= ANGLE_DERRIERE_LE_PLAN_DEG:
        return 0.0
    cosinus = math.cos(math.radians(angle))
    if cosinus <= 0.0:
        return 0.0
    return max(0.0, 1.0 - float(b0) * (1.0 / cosinus - 1.0))


def _angles_effectifs(inclinaison_deg):
    """``(θ_ciel, θ_sol)`` — Brandemuehl & Beckman (Duffie & Beckman 5.4.2).

    Le diffus du ciel et le réfléchi du sol n'arrivent pas sous un angle :
    ces deux angles EFFECTIFS sont la façon citée d'appliquer un IAM à un
    rayonnement qui vient de partout.
    """
    beta = float(inclinaison_deg)
    ciel = 59.7 - 0.1388 * beta + 0.001497 * beta * beta
    sol = 90.0 - 0.5788 * beta + 0.002693 * beta * beta
    return ciel, sol


def _transmission_fresnel(angle_deg, indice):
    """La transmission non polarisée d'un dioptre air/verre."""
    angle = math.radians(float(angle_deg))
    if angle < 1e-9:
        # Incidence normale : les deux termes de Fresnel dégénèrent en 0/0.
        return 1.0 - ((indice - 1.0) / (indice + 1.0)) ** 2
    sinus_refracte = min(1.0, math.sin(angle) / float(indice))
    refracte = math.asin(sinus_refracte)
    ecart = refracte - angle
    somme = refracte + angle
    sinus = math.sin(somme)
    if abs(sinus) < 1e-12:
        return 0.0
    perpendiculaire = (math.sin(ecart) / sinus) ** 2
    cosinus = math.cos(somme)
    if abs(cosinus) < 1e-12:
        parallele = 0.0
    else:
        tangente = sinus / cosinus
        parallele = (math.tan(ecart) / tangente) ** 2
    return max(0.0, 1.0 - 0.5 * (perpendiculaire + parallele))


# ── l'étape ─────────────────────────────────────────────────────────────

def appliquer(serie, contexte):
    """``(serie, etape)`` — l'IAM sur le direct, le diffus et le réfléchi.

    Fonction PURE : ni ``serie`` ni ses points ne sont modifiés sur place.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    libelle = _libelle()

    points = (serie or {}).get('points') or []
    if not points:
        return serie, etapes.etape_omise(
            libelle, "La série horaire est vide : aucun angle d'incidence "
            'ne peut y être calculé.', champ='serie.points')
    if any(point.get('gb_i_w_m2') is None for point in points):
        return serie, etapes.etape_omise(libelle, MOTIF_COMPOSANTES_ABSENTES)

    plan, refus = _plan(contexte)
    if refus:
        return serie, etapes.etape_omise(libelle, refus[0], champ=refus[1])
    inclinaison = _nombre(plan.get('inclinaison_deg'))
    azimut = _nombre(plan.get('azimut_pvgis_deg'))
    if inclinaison is None:
        return serie, etapes.etape_omise(
            libelle, "Le pan ne porte pas d'inclinaison : l'angle "
            "d'incidence du faisceau direct ne peut pas être calculé.",
            champ='plan.inclinaison_deg')
    if azimut is None:
        return serie, etapes.etape_omise(
            libelle, "Le pan ne porte pas d'azimut : l'angle d'incidence du "
            'faisceau direct ne peut pas être calculé.',
            champ='plan.azimut_pvgis_deg')

    site = contexte.get('site') or {}
    latitude = _nombre(site.get('lat'))
    longitude = _nombre(site.get('lon'))
    if latitude is None or longitude is None:
        return serie, etapes.etape_omise(
            libelle, "Le site ne porte pas de coordonnées : la position du "
            'soleil ne peut pas être calculée.',
            champ='site.lat' if latitude is None else 'site.lon')

    decalage = _decalage_minutes(contexte.get('meteo') or {})
    if decalage is None:
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_BASE_DE_TEMPS,
                                         champ='meteo.heure.decalage_minutes')
    if _instant_utc(points[0], decalage) is None:
        return serie, etapes.etape_omise(
            libelle, "Les points de la série ne portent pas d'horodatage "
            "lisible : l'angle d'incidence ne peut pas leur être associé.",
            champ='serie.points[].heure')

    choix = _modele(contexte)
    indice = _indice(contexte)
    theta_ciel, theta_sol = _angles_effectifs(inclinaison)
    iam_diffus = _iam(choix, indice, theta_ciel)
    iam_reflechi = _iam(choix, indice, theta_sol)

    suite, angle_moyen = _appliquer_iam(
        serie, points, choix, indice, iam_diffus, iam_reflechi,
        latitude=latitude, longitude=longitude, decalage=decalage,
        inclinaison=inclinaison, azimut=azimut)

    entree = {
        'modele': choix['modele'],
        'indice_verre': indice['valeur'],
        'revetement_ar': indice['antireflet'],
        'iam_direct': 'calculé heure par heure à l’angle d’incidence du '
                      'soleil (core.calepinage.soleil)',
        'angle_incidence_moyen_deg': angle_moyen,
        'iam_diffus': round(iam_diffus, 6),
        'iam_reflechi': round(iam_reflechi, 6),
        'angle_effectif_ciel_deg': round(theta_ciel, 3),
        'angle_effectif_sol_deg': round(theta_sol, 3),
        'inclinaison_deg': inclinaison,
        'azimut_pvgis_deg': azimut,
        'decalage_minutes': decalage,
    }
    if choix.get('modele_demande'):
        entree['modele_demande'] = choix['modele_demande']
        entree['repli'] = choix['repli']
    if choix['modele'] == 'ashrae':
        entree['b0'] = choix['b0']
    return suite, etapes.etape_appliquee(
        libelle, source=choix['source'], reference=REFERENCE, entree=entree)


# ── les entrées, une par une ────────────────────────────────────────────

def _libelle():
    """Le libellé FRANÇAIS du poste, déclaré une seule fois (CALX148)."""
    from apps.calepinage.services.chaine_pertes import LIBELLES

    return LIBELLES[POSTE]


def _plan(contexte):
    """``(plan, None)`` ou ``(None, (motif, champ))`` — le pan de la série.

    La chaîne s'applique à la série d'UN pan. Le contexte le nomme
    (``plan``), ou n'en porte qu'un seul (``plans``) ; plusieurs pans sans
    désignation laisseraient CHOISIR, et une étape ne choisit pas.
    """
    plan = contexte.get('plan')
    if isinstance(plan, dict):
        return plan, None
    plans = [p for p in (contexte.get('plans') or ()) if isinstance(p, dict)]
    if isinstance(plan, str) and plan:
        for candidat in plans:
            if str(candidat.get('cle')) == plan:
                return candidat, None
        return None, (
            f'Le contexte désigne le pan « {plan} », que « plans » ne porte '
            "pas : l'angle d'incidence ne peut pas être calculé.", 'plan')
    if len(plans) == 1:
        return plans[0], None
    if not plans:
        return None, ("Le contexte ne porte aucun pan : sans inclinaison ni "
                      "azimut, l'angle d'incidence n'existe pas.", 'plans')
    return None, (
        f'Le contexte porte {len(plans)} pans sans dire lequel cette série '
        "décrit : l'étape ne choisit pas à la place du document.", 'plan')


def _modele(contexte):
    """Le modèle retenu, sa source, et le repli s'il a fallu replier."""
    fresnel = {'modele': 'fresnel', 'source': 'texte', 'b0': None}
    saisie = etapes.reglage(contexte, 'modele_iam')
    demande = str((saisie or {}).get('valeur') or '').strip().lower()
    if not demande or demande == 'fresnel':
        return fresnel

    if demande == 'ashrae':
        coefficient = etapes.reglage(contexte, 'b0_iam')
        valeur = _nombre((coefficient or {}).get('valeur'))
        if valeur is None:
            return dict(fresnel, modele_demande='ashrae', repli=(
                "Le modèle ASHRAE est demandé mais son coefficient « b0 » "
                "n'est pas saisi avec sa provenance (réglage "
                '« b0_iam ») : le modèle physique de Fresnel s’applique, '
                'aucun b0 par défaut n’est inventé.'))
        return {'modele': 'ashrae', 'b0': valeur,
                'source': coefficient.get('source')}

    if demande == 'martin_ruiz':
        return dict(fresnel, modele_demande='martin_ruiz', repli=(
            'Le modèle Martin-Ruiz est demandé, mais son coefficient '
            '« a_r » ne figure pas au registre des réglages de simulation '
            '(CALX145) : il ne peut donc pas être saisi avec sa provenance, '
            'et le modèle physique de Fresnel s’applique.'))

    return dict(fresnel, modele_demande=demande, repli=(
        f'Le modèle d’incidence « {demande} » n’est pas connu de cette '
        f'étape (attendus : {", ".join(MODELES)}) : le modèle physique de '
        'Fresnel s’applique.'))


def _indice(contexte):
    """L'indice de réfraction employé, et d'où vient le choix."""
    fiche = contexte.get('fiche_module') or {}
    antireflet = any(fiche.get(cle) is True for cle in CLES_ANTIREFLET)
    return {
        'valeur': INDICE_VERRE_ANTIREFLET if antireflet else INDICE_VERRE,
        'antireflet': antireflet,
    }


def _iam(choix, indice, angle_deg):
    """L'IAM du modèle retenu à ``angle_deg``."""
    if choix['modele'] == 'ashrae':
        return _iam_ashrae(angle_deg, choix['b0'])
    return _iam_fresnel(angle_deg, indice['valeur'])


def _decalage_minutes(meteo):
    """Le décalage de la série sur l'UTC, en minutes, ou ``None``.

    Rien n'est supposé : soit la série se déclare en UTC, soit le décalage
    du site est posé (CALX59). Une liste de décalages n'est lue que si elle
    n'en porte qu'un seul.
    """
    heure = (meteo or {}).get('heure') or {}
    if str(heure.get('base') or '').strip().lower() == 'utc':
        return 0.0
    brut = heure.get('decalage_minutes')
    nombre = _nombre(brut)
    if nombre is not None:
        return nombre
    if isinstance(brut, (list, tuple)):
        valeurs = {_nombre(valeur) for valeur in brut}
        valeurs.discard(None)
        if len(valeurs) == 1:
            return valeurs.pop()
    return None


# ── l'application, heure par heure ──────────────────────────────────────

def _appliquer_iam(serie, points, choix, indice, iam_diffus, iam_reflechi, *,
                   latitude, longitude, decalage, inclinaison, azimut):
    """Une COPIE de la série sous IAM, et l'angle d'incidence moyen pondéré.

    La moyenne est pondérée par le DIRECT : un angle rasant à l'aube ne pèse
    pas autant qu'un angle de midi, et une moyenne arithmétique le laisserait
    croire.
    """
    suite = []
    somme_angles = 0.0
    somme_poids = 0.0
    for point in points:
        instant = _instant_utc(point, decalage)
        directe = _nombre(point.get('gb_i_w_m2')) or 0.0
        if instant is None:
            suite.append(point)
            continue
        position = position_solaire(
            latitude, longitude, annee=instant.year, mois=instant.month,
            jour=instant.day,
            heure_utc=instant.hour + instant.minute / 60.0)
        angle = position.angle_incidence_deg(inclinaison, azimut)
        somme_angles += angle * directe
        somme_poids += directe
        copie = dict(point)
        copie['gb_i_w_m2'] = directe * _iam(choix, indice, angle)
        copie['gd_i_w_m2'] = (_nombre(point.get('gd_i_w_m2'))
                              or 0.0) * iam_diffus
        copie['gr_i_w_m2'] = (_nombre(point.get('gr_i_w_m2'))
                              or 0.0) * iam_reflechi
        _reporter(point, copie)
        suite.append(copie)
    rendue = dict(serie)
    rendue['points'] = suite
    moyen = round(somme_angles / somme_poids, 3) if somme_poids else None
    return rendue, moyen


def _reporter(avant, apres):
    """Recompose ``gi_w_m2`` et met l'énergie à l'échelle du même rapport.

    ``G(i)`` est la SOMME des trois composantes sous ``components=1``
    (vérifié sur les réponses PVGIS réelles par
    ``tests/test_calx152_composantes.py``). Une colonne de puissance déjà
    présente suit le MÊME rapport, heure par heure.
    """
    globale_avant = _nombre(avant.get('gi_w_m2'))
    globale_apres = (apres['gb_i_w_m2'] + apres['gd_i_w_m2']
                     + apres['gr_i_w_m2'])
    apres['gi_w_m2'] = globale_apres
    if not globale_avant:
        return
    rapport = globale_apres / globale_avant
    for colonne in etapes.ORDRE_COLONNES_ENERGIE:
        valeur = _nombre(avant.get(colonne))
        if valeur is not None:
            apres[colonne] = valeur * rapport


def _instant_utc(point, decalage_minutes):
    """L'instant UTC d'un point de série, ou ``None`` s'il est illisible."""
    try:
        moment = datetime.datetime(int(point['annee']), int(point['mois']),
                                   int(point['jour']))
        moment += datetime.timedelta(hours=float(point['heure']))
    except (KeyError, TypeError, ValueError):
        return None
    return moment - datetime.timedelta(minutes=decalage_minutes)


def _nombre(valeur):
    """Un flottant lisible, ou ``None`` — jamais une valeur de remplacement."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre
