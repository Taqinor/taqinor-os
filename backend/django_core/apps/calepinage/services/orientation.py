# -*- coding: utf-8 -*-
"""CALX58 — TOF et TSRF par pan : ce que l'ORIENTATION coûte, mesuré.

LE CONSTAT
----------
``services/production.py`` publie un PR, ``services/ombrage_chaines.py`` un
accès solaire par module — mais aucun service ne comparait l'irradiation du
plan RÉEL à celle du plan OPTIMAL du site. Les deux écrans de la note de
calcul (CALX302, CALX317) impriment « TOF / TSRF si le contrat les publie » :
personne ne les publiait.

LES DEUX FACTEURS, ET LEUR DÉFINITION CITÉE
---------------------------------------------
* **TOF** (Tilt & Orientation Factor) — OpenSolar : « percentage of unshaded
  solar insolation at the actual tilt and azimuth … compared to the optimal
  tilt and azimuth »
  (https://support.opensolar.com/hc/en-us/articles/11007607272207-Generating-a-Shade-Report).
  Ici : ``TOF = H_annuelle(plan réel) / H_annuelle(plan optimal)``.
* **TSRF** (Total Solar Resource Fraction) — HelioScope : ``TSRF = accès
  solaire × TOF``
  (https://help-center.helioscope.com/hc/en-us/articles/8198877052435-Total-Solar-Resource-Factor-TSRF).

D'OÙ VIENT CHAQUE MOITIÉ — ET AUCUN CHIFFRE N'EST SUPPOSÉ (D-CALX 7)
----------------------------------------------------------------------
* Le plan RÉEL ne coûte AUCUN appel : son irradiation est la somme des
  ``gi_w_m2`` de la série DÉJÀ obtenue pour ce pan (CALX181), ramenée à
  l'ANNÉE (la fenêtre peut être pluriannuelle — additionner deux années
  doublerait le numérateur).
* Le plan OPTIMAL demande UN appel ``PVcalc`` avec ``optimalangles=1`` PAR
  SITE — ``optimalangles`` n'existe pas sur ``seriescalc`` (page API PVGIS).
  L'appel passe par ``ClientPvgis._appeler`` : il hérite donc du cache de
  processus, de l'auto-limitation de débit et du journal ``urls_appelees``
  du client, comme tous les autres appels du module. Deux pans du même site
  ne font qu'UNE requête ; ``meteo.appels_pvgis`` garde son sens de CALX155
  (les requêtes de SÉRIE météo) et n'est pas touché ici.
* ``PVcalc`` EXIGE ``peakpower`` et ``loss`` : ce sont des exigences d'API,
  pas des hypothèses de calcul, et RIEN de ce que PVGIS en déduit (``E_d``,
  ``E_m``, ``E_y``) n'est lu ni publié — seules ``H(i)_y`` et les deux angles
  optimaux le sont.
* PVGIS injoignable, série absente, accès solaire absent : ``tof`` et
  ``tsrf`` valent ``null`` AVEC leur motif, jamais 1,0 « par défaut » — un
  TOF supposé à 1 affirmerait que le toit est orienté au mieux.

Module de SERVICE (réseau INJECTÉ par le client) : aucune base, aucun prix.
"""
from __future__ import annotations

from apps.calepinage.services.ombrage_chaines import acces_par_module
from apps.calepinage.services.pvgis_serie import (
    BASE_PAR_DEFAUT, EntreeInvalide, PvgisIndisponible)

#: Le service PVGIS qui sait optimiser les angles (``seriescalc`` ne le sait
#: pas : ``optimalangles`` n'est pas un de ses paramètres).
SERVICE_PVCALC = 'PVcalc'

#: La méthode publiée dans ``resultat['ombrage']['methode']`` — le contrat
#: CALX4 la nomme déjà.
METHODE = 'tof_pvcalc_optimalangles_x_acces_solaire'

#: La provenance publiée sur une ligne ``production.par_pan[]`` servie.
SOURCE_PVGIS = 'pvgis'

#: Les deux paramètres que l'API ``PVcalc`` EXIGE et dont rien n'est lu.
PUISSANCE_EXIGEE_KWC = 1
PERTE_EXIGEE_PCT = 0

#: Les références CITÉES (jamais des constantes recopiées).
REFERENCE = (
    'OpenSolar — Generating a Shade Report : TOF = part de l\'ensoleillement '
    'non ombré à l\'inclinaison et à l\'azimut RÉELS, rapportée à '
    "l'inclinaison et à l'azimut OPTIMAUX (https://support.opensolar.com/hc/"
    'en-us/articles/11007607272207-Generating-a-Shade-Report) ; HelioScope — '
    'TSRF = accès solaire × TOF (https://help-center.helioscope.com/hc/en-us/'
    'articles/8198877052435-Total-Solar-Resource-Factor-TSRF) ; PVGIS — '
    "« optimalangles » n'existe que sur PVcalc "
    '(https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-'
    'information-system-pvgis/getting-started-pvgis/api-non-interactive-'
    'service_en).')

MOTIF_SANS_CLIENT = (
    "Aucun client PVGIS n'est disponible pour demander le plan OPTIMAL du "
    'site : le TOF n\'est pas publié. Un TOF supposé à 1,0 affirmerait que '
    'ce toit est orienté au mieux.')

MOTIF_SANS_SITE = (
    'Les coordonnées du site ne sont pas lisibles : le plan optimal ne peut '
    'pas être demandé à PVGIS, et le TOF n\'est pas publié.')

MOTIF_SANS_SERIE = (
    "Aucune série horaire pour ce pan : l'irradiation du plan RÉEL n'est pas "
    'mesurée, le TOF n\'est pas publié.')

MOTIF_SERIE_SANS_IRRADIANCE = (
    'La série de ce pan ne porte aucune irradiance de plan « gi_w_m2 » : '
    "l'irradiation du plan RÉEL n'est pas mesurée, le TOF n'est pas publié.")

MOTIF_OPTIMAL_SANS_IRRADIATION = (
    'La réponse PVcalc de PVGIS ne porte pas l\'irradiation annuelle du plan '
    'optimal (« H(i)_y ») : le TOF n\'est pas publié.')

MOTIF_SANS_ACCES_SOLAIRE = (
    "Le document ne porte aucun accès solaire pour ce pan "
    '(« zones[].geometry.solarAccess ») : le TSRF, qui est le produit de '
    "l'accès solaire par le TOF, n'est pas publié — un accès supposé à 100 % "
    'se lirait « pan sans aucune ombre, mesuré ».')

__all__ = ['SERVICE_PVCALC', 'METHODE', 'SOURCE_PVGIS', 'REFERENCE',
           'PUISSANCE_EXIGEE_KWC', 'PERTE_EXIGEE_PCT', 'MOTIF_SANS_CLIENT',
           'MOTIF_SANS_SITE', 'MOTIF_SANS_SERIE',
           'MOTIF_SERIE_SANS_IRRADIANCE', 'MOTIF_OPTIMAL_SANS_IRRADIATION',
           'MOTIF_SANS_ACCES_SOLAIRE', 'CLES_ORIENTATION',
           'plan_optimal', 'tof_du_pan', 'acces_solaire_moyen_pct']

#: Les clés du bloc rendu par :func:`tof_du_pan`. Les cinq premières
#: alimentent ``production.par_pan[]`` et les deux suivantes, avec ``tof`` et
#: ``tsrf``, ``resultat['ombrage']['par_pan'][]`` (contrat CALX4) ; les
#: dernières sont ce qui a SERVI au calcul, publié pour qu'il se vérifie.
CLES_ORIENTATION = (
    'tof', 'tsrf', 'inclinaison_optimale_deg', 'azimut_optimal_deg', 'source',
    'acces_solaire_moyen_pct', 'motif_omission',
    'irradiation_reelle_kwh_m2', 'irradiation_optimale_kwh_m2',
    'annees_serie', 'inclinaison_deg', 'azimut_pvgis_deg',
)


# ── le plan OPTIMAL du site : UN appel PVcalc ───────────────────────────

def plan_optimal(lat, lon, *, client, base=BASE_PAR_DEFAUT):
    """L'irradiation annuelle du plan OPTIMAL du site, et ses deux angles.

    Args:
        client: un ``ClientPvgis`` (ou tout objet exposant ``_appeler``) —
            c'est LUI qui porte le cache, la cadence et le transport. Un
            client absent n'est pas une erreur : le bloc revient omis.

    Returns:
        dict — ``irradiation_kwh_m2``, ``inclinaison_deg``,
        ``azimut_pvgis_deg``, ``azimut_deg`` (azimut de FACE, convention du
        document de toiture), ``source``, ``depuis_cache``, ``motif_omission``.

    Ne lève jamais : un refus de PVGIS est une RÉPONSE omise avec son motif.
    """
    appeler = getattr(client, '_appeler', None)
    if not callable(appeler):
        return _optimal_omis(MOTIF_SANS_CLIENT)

    coordonnees = _coordonnees(lat, lon)
    if coordonnees is None:
        return _optimal_omis(MOTIF_SANS_SITE)

    params = {
        'lat': coordonnees[0], 'lon': coordonnees[1],
        'raddatabase': base,
        # Exigences de l'API PVcalc : RIEN de ce que PVGIS en déduit n'est lu.
        'peakpower': PUISSANCE_EXIGEE_KWC,
        'loss': PERTE_EXIGEE_PCT,
        'optimalangles': 1,
        'pvtechchoice': 'crystSi',
        'mountingplace': 'building',
        'outputformat': 'json',
    }
    try:
        charge, depuis_cache = appeler(SERVICE_PVCALC, params)
    except (PvgisIndisponible, EntreeInvalide, TypeError, ValueError) as refus:
        return _optimal_omis(str(refus) or MOTIF_OPTIMAL_SANS_IRRADIATION)

    totaux = _sous_bloc(_sous_bloc(_sous_bloc(charge, 'outputs'), 'totals'),
                        'fixed')
    irradiation = _nombre(totaux.get('H(i)_y'))
    if irradiation is None or irradiation <= 0:
        return _optimal_omis(MOTIF_OPTIMAL_SANS_IRRADIATION)

    fixe = _sous_bloc(_sous_bloc(_sous_bloc(charge, 'inputs'),
                                 'mounting_system'), 'fixed')
    inclinaison = _nombre(_sous_bloc(fixe, 'slope').get('value'))
    azimut_pvgis = _nombre(_sous_bloc(fixe, 'azimuth').get('value'))
    return {
        'irradiation_kwh_m2': round(irradiation, 2),
        'inclinaison_deg': inclinaison,
        'azimut_pvgis_deg': azimut_pvgis,
        'azimut_deg': _azimut_de_face(azimut_pvgis),
        'source': SOURCE_PVGIS,
        'depuis_cache': bool(depuis_cache),
        'motif_omission': '',
    }


# ── le TOF et le TSRF d'UN pan ──────────────────────────────────────────

def tof_du_pan(lat, lon, inclinaison_deg, azimut_pvgis_deg, *, client,
               serie=None, acces_solaire_pct=None, optimal=None,
               base=BASE_PAR_DEFAUT):
    """``{tof, tsrf, …}`` pour UN pan — mesuré, ou omis en le disant.

    Args:
        inclinaison_deg / azimut_pvgis_deg: les angles RÉELS du pan. Ils sont
            republiés à côté des angles optimaux pour que l'écart se lise ;
            l'irradiation du plan réel, elle, ne se redemande PAS à PVGIS —
            elle est déjà dans ``serie``.
        serie: la série du pan (CALX142/CALX181), dont les ``gi_w_m2`` sont
            sommés.
        acces_solaire_pct: l'accès solaire MOYEN du pan en % (CALX158).
            ``None`` ⇒ ``tsrf`` omis avec son motif, jamais 100 % supposé.
        optimal: le retour de :func:`plan_optimal` DÉJÀ obtenu pour ce site —
            c'est ainsi qu'un toit à cinq pans ne fait qu'UN appel PVcalc.
    """
    bloc = _bloc_vide()
    reelle, annees = _irradiation_annuelle_kwh_m2(serie)
    bloc['irradiation_reelle_kwh_m2'] = reelle
    bloc['annees_serie'] = annees
    bloc['inclinaison_deg'] = _nombre(inclinaison_deg)
    bloc['azimut_pvgis_deg'] = _nombre(azimut_pvgis_deg)
    bloc['acces_solaire_moyen_pct'] = _nombre(acces_solaire_pct)

    if optimal is None:
        optimal = plan_optimal(lat, lon, client=client, base=base)
    bloc['inclinaison_optimale_deg'] = optimal.get('inclinaison_deg')
    bloc['azimut_optimal_deg'] = optimal.get('azimut_deg')
    bloc['irradiation_optimale_kwh_m2'] = optimal.get('irradiation_kwh_m2')

    if optimal.get('motif_omission'):
        return _omettre(bloc, optimal['motif_omission'])
    if serie is None:
        return _omettre(bloc, MOTIF_SANS_SERIE)
    if reelle is None:
        return _omettre(bloc, MOTIF_SERIE_SANS_IRRADIANCE)

    optimale = _nombre(optimal.get('irradiation_kwh_m2'))
    if optimale is None or optimale <= 0:
        return _omettre(bloc, MOTIF_OPTIMAL_SANS_IRRADIATION)

    bloc['tof'] = round(reelle / optimale, 4)
    bloc['source'] = SOURCE_PVGIS
    acces = bloc['acces_solaire_moyen_pct']
    if acces is None:
        bloc['motif_omission'] = MOTIF_SANS_ACCES_SOLAIRE
        return bloc
    bloc['tsrf'] = round(bloc['tof'] * acces / 100.0, 4)
    return bloc


def _irradiation_annuelle_kwh_m2(serie):
    """``(kWh/m² par AN, nombre d'années)`` sommés sur ``gi_w_m2``.

    Le pas de la série est celui qu'elle DÉCLARE (``pas_minutes``, 60 par
    défaut côté PVGIS) ; la somme est ensuite divisée par le nombre d'ANNÉES
    distinctes présentes, parce qu'une fenêtre pluriannuelle additionnerait
    autrement deux ciels dans un seul numérateur. ``(None, 0)`` quand aucune
    irradiance n'est lisible — jamais un zéro, qui se lirait « site sans
    soleil, mesuré ».
    """
    points = (serie or {}).get('points') if isinstance(serie, dict) else None
    if not points:
        return None, 0
    pas = _nombre((serie or {}).get('pas_minutes')) or 60.0
    heures = pas / 60.0
    par_annee = {}
    for point in points:
        if not isinstance(point, dict):
            continue
        globale = _nombre(point.get('gi_w_m2'))
        if globale is None:
            continue
        annee = point.get('annee')
        cumul = par_annee.get(annee) or 0.0
        par_annee[annee] = cumul + globale / 1000.0 * heures
    if not par_annee:
        return None, 0
    total = sum(par_annee.values())
    return round(total / len(par_annee), 2), len(par_annee)


# ── l'accès solaire MOYEN d'un pan, lu sur le document ──────────────────

def acces_solaire_moyen_pct(ombrage, plan=None, layout=None):
    """``(pourcentage | None, motif)`` — la moyenne des modules CALCULÉS.

    Même règle que l'étape CALX158 : un module ``null`` est un module NON
    calculé, il est EXCLU de la moyenne et jamais complété à 100 % — sans
    quoi l'accès du champ remonterait tout seul.
    """
    ombrage = ombrage if isinstance(ombrage, dict) else {}
    acces = ombrage.get('solar_access') or ombrage.get('solarAccess')
    acces = acces if isinstance(acces, dict) else {}

    valeurs = _facteurs(acces.get('values'))
    if valeurs is None:
        valeurs = _facteurs_du_pan(acces, ombrage, plan, layout)
    mesures = [valeur for valeur in (valeurs or ()) if valeur is not None]
    if not mesures:
        return None, MOTIF_SANS_ACCES_SOLAIRE
    return round(100.0 * sum(mesures) / len(mesures), 2), ''


def _facteurs_du_pan(acces, ombrage, plan, layout):
    """Les facteurs du pan NOMMÉ, lus dans ``par_pan`` ou dans le document."""
    par_pan = acces.get('par_pan')
    if not isinstance(par_pan, dict):
        document = layout or ombrage.get('layout')
        par_pan = acces_par_module(document) if document else {}
    if not isinstance(par_pan, dict) or not par_pan:
        return None
    for repere in _reperes_du_plan(plan):
        if repere in par_pan:
            return _facteurs(par_pan[repere])
    return None


def _reperes_du_plan(plan):
    """Les noms sous lesquels un pan peut être écrit dans le document."""
    if isinstance(plan, dict):
        return [str(plan[cle]) for cle in ('cle', 'pan', 'label', 'id')
                if plan.get(cle)]
    return [str(plan)] if plan else []


def _facteurs(valeurs):
    """``[facteur ou None]`` — hors de [0, 1] ⇒ NON calculé (contrat v2)."""
    if not isinstance(valeurs, (list, tuple)):
        return None
    lus = []
    for valeur in valeurs:
        nombre = _nombre(valeur)
        lus.append(nombre if nombre is not None and 0.0 <= nombre <= 1.0
                   else None)
    return lus


# ── petites aides ───────────────────────────────────────────────────────

def _bloc_vide():
    return {cle: ('' if cle == 'motif_omission' else None)
            for cle in CLES_ORIENTATION}


def _omettre(bloc, motif):
    bloc['tof'] = None
    bloc['tsrf'] = None
    bloc['source'] = None
    bloc['motif_omission'] = motif
    return bloc


def _optimal_omis(motif):
    return {
        'irradiation_kwh_m2': None, 'inclinaison_deg': None,
        'azimut_pvgis_deg': None, 'azimut_deg': None, 'source': None,
        'depuis_cache': False, 'motif_omission': motif,
    }


def _azimut_de_face(azimut_pvgis_deg):
    """PVGIS (0 = Sud, −90 = Est) → azimut de FACE (180 = Sud, 90 = Est).

    L'inverse exact de ``pvgis_serie.azimut_pvgis`` : le document de toiture
    et les écrans ne lisent que l'azimut de face, publier l'autre convention
    à côté de ``azimut_deg`` ferait lire un écart qui n'existe pas.
    """
    aspect = _nombre(azimut_pvgis_deg)
    if aspect is None:
        return None
    return round((aspect + 180.0) % 360.0, 1)


def _sous_bloc(charge, cle):
    valeur = charge.get(cle) if isinstance(charge, dict) else None
    return valeur if isinstance(valeur, dict) else {}


def _coordonnees(lat, lon):
    latitude = _nombre(lat)
    longitude = _nombre(lon)
    if latitude is None or longitude is None:
        return None
    if abs(latitude) > 90.0 or abs(longitude) > 180.0:
        return None
    return round(latitude, 4), round(longitude, 4)


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
