# -*- coding: utf-8 -*-
"""CALX156 — étape « horizon » : le direct coupé sous la ligne d'horizon.

LE CONSTAT
----------
``services/horizon.py`` sait LIRE un profil d'horizon
(``{azimut_pvgis_deg, azimut_face_deg, hauteur_deg}``) et
``services/pvgis_serie.py`` sait le TRANSMETTRE à PVGIS (CALX151) — mais
aucun module du dépôt n'applique un horizon à une série HEURE PAR HEURE, et
``services/production.py`` n'en connaît pas l'existence. Ce module est cette
étape, et rien d'autre.

LA DOCTRINE APPLIQUÉE, ET SA SOURCE
------------------------------------
PVsyst — *Far shadings : horizon*
(https://www.pvsyst.com/help/project-design/shadings/far-shadings-horizon/index.html) :

* le faisceau **DIRECT** est traité en TOUT ou RIEN — sous la ligne
  d'horizon, il est coupé ; au-dessus, il passe entier ;
* le **DIFFUS** n'est pas coupé : il est atténué par la fraction de ciel
  encore visible. La fraction employée ici est celle que la tâche déclare,
  ``1 − Σ hauteur_i / (90 × N)`` sur les N azimuts du profil ;
* le **RÉFLÉCHI** (albédo) décroît linéairement avec la hauteur d'horizon et
  s'annule au-delà de 20° (:data:`HAUTEUR_ALBEDO_NUL_DEG`).

Les deux conventions d'atténuation sont donc CITÉES, et ``entree`` publie
laquelle a servi. La société peut les désactiver par le réglage sourcé
``simulation.attenuation_horizon`` (CALX145) : le direct reste alors masqué —
c'est la géométrie du site —, et diffus comme réfléchi ressortent intacts.

LE DOUBLE MASQUAGE EST STRUCTURELLEMENT IMPOSSIBLE
---------------------------------------------------
``meteo.horizon.origine`` (CALX151) dit QUI a déjà retranché un masque :

* ``dem_pvgis`` — PVGIS a appliqué SON modèle de terrain ;
* ``profil_mesure`` / ``saisie`` — NOTRE profil est parti en ``userhorizon``,
  et la mesure du 21/09/2026 consignée dans ``pvgis_serie._horizon_demande``
  prouve que PVGIS l'applique bel et bien (793,86 W/m² sans profil contre
  105,23 W/m² avec un mur de 40°), quoi qu'en dise sa réponse.

Dans ces trois cas l'étape s'OMET en le disant : l'irradiance reçue porte
déjà le masque. Elle ne s'applique donc que sur une série à laquelle AUCUN
horizon n'a été retranché en amont (``aucun``), où le profil du document est
la seule lecture du masque lointain.

AUCUN CHIFFRE INVENTÉ (D-CALX 7)
---------------------------------
Profil absent, composantes absentes (CALX152), site sans coordonnées, base
de temps de la série non déclarée : l'étape s'OMET en NOMMANT le champ qui
manque. Aucun horizon plat de repli, aucun fuseau supposé.
"""
from __future__ import annotations

import bisect
import datetime

from apps.calepinage.services import etapes
from apps.calepinage.services.pvgis_serie import MOTIF_COMPOSANTES_ABSENTES
from core.calepinage.soleil import position_solaire

#: Le nom du poste — celui de ``chaine_pertes.ORDRE_ETAPES``, qui est aussi
#: le nom de ce fichier : c'est toute l'inscription au registre (CALX147).
POSTE = 'horizon'

#: Hauteur d'horizon au-delà de laquelle PVsyst annule la part réfléchie.
#: Convention CITÉE (page « Far shadings : horizon »), publiée dans
#: ``entree`` — jamais présentée comme une mesure du site.
HAUTEUR_ALBEDO_NUL_DEG = 20.0

#: Les origines de masque pour lesquelles l'irradiance REÇUE porte déjà le
#: retrait : ``{origine: motif publié}``.
ORIGINES_DEJA_RETRANCHEES = {
    'dem_pvgis': (
        "L'horizon vient du modèle de terrain de PVGIS, qui l'a DÉJÀ "
        "retranché de l'irradiance rendue : le retrancher ici le compterait "
        'deux fois.'),
    'profil_mesure': (
        "Notre profil d'horizon est parti dans « userhorizon » et PVGIS l'a "
        "appliqué à la série rendue (mesuré le 21/09/2026 : 793,86 W/m² sans "
        'profil contre 105,23 W/m² avec un mur de 40°) : le masquer une '
        'seconde fois ici le compterait deux fois.'),
    'saisie': (
        "Le profil d'horizon SAISI est parti dans « userhorizon » et PVGIS "
        "l'a appliqué à la série rendue (mesuré le 21/09/2026) : le masquer "
        'une seconde fois ici le compterait deux fois.'),
}

#: Le motif publié quand aucun profil n'est joint au document.
MOTIF_SANS_PROFIL = (
    "Aucun profil d'horizon n'accompagne ce document : le masque lointain "
    "n'est pas calculé. Un horizon plat de repli se lirait « site "
    'parfaitement dégagé, vérifié ».')

#: Le motif publié quand la série ne dit pas à quelle base de temps ses
#: heures se rapportent — sans elle, la position du soleil serait décalée.
MOTIF_SANS_BASE_DE_TEMPS = (
    "La base de temps de la série n'est pas déclarée : PVGIS rend ses heures "
    "en heure locale standard (« localtime=1 ») et le décalage du site n'est "
    'pas posé. Sans lui, la position du soleil serait décalée et le masque '
    'tomberait sur les mauvaises heures.')

#: Les valeurs de ``simulation.attenuation_horizon`` qui DÉSACTIVENT
#: l'atténuation du diffus et du réfléchi.
VALEURS_SANS_ATTENUATION = ('aucune', 'non', 'sans', 'desactivee',
                            'désactivée', 'false', '0')

#: La référence publiée dans ``cascade[].reference``.
REFERENCE = (
    'PVsyst — Far shadings : horizon (direct coupé en tout ou rien, diffus '
    'atténué par la fraction de ciel visible, albédo linéairement décroissant '
    "et nul au-delà de 20°) : https://www.pvsyst.com/help/project-design/"
    'shadings/far-shadings-horizon/index.html — position du soleil : NOAA / '
    'Meeus par core.calepinage.soleil (CALX146).')

__all__ = ['POSTE', 'HAUTEUR_ALBEDO_NUL_DEG', 'ORIGINES_DEJA_RETRANCHEES',
           'MOTIF_SANS_PROFIL', 'MOTIF_SANS_BASE_DE_TEMPS',
           'VALEURS_SANS_ATTENUATION', 'REFERENCE', 'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — le direct masqué sous la ligne d'horizon.

    Fonction PURE : ni ``serie`` ni ses points ne sont modifiés sur place.
    """
    contexte = contexte if isinstance(contexte, dict) else {}
    libelle = _libelle()

    origine = ((contexte.get('meteo') or {}).get('horizon') or {}).get(
        'origine')
    if origine in ORIGINES_DEJA_RETRANCHEES:
        return serie, etapes.etape_omise(
            libelle, ORIGINES_DEJA_RETRANCHEES[origine])

    profil = _profil(contexte)
    releves = _releves(profil) if profil else {}
    if len(releves) < 2:
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_PROFIL,
                                         champ='horizon.points')

    points = (serie or {}).get('points') or []
    if not points:
        return serie, etapes.etape_omise(
            libelle, 'La série horaire est vide : aucun masque ne peut être '
            'appliqué heure par heure.', champ='serie.points')
    if any(point.get('gb_i_w_m2') is None for point in points):
        return serie, etapes.etape_omise(libelle,
                                         MOTIF_COMPOSANTES_ABSENTES)

    site = contexte.get('site') or {}
    latitude = _nombre(site.get('lat'))
    longitude = _nombre(site.get('lon'))
    if latitude is None:
        return serie, etapes.etape_omise(
            libelle, "Le site ne porte pas de latitude : la position du "
            'soleil ne peut pas être calculée.', champ='site.lat')
    if longitude is None:
        return serie, etapes.etape_omise(
            libelle, "Le site ne porte pas de longitude : la position du "
            'soleil ne peut pas être calculée.', champ='site.lon')

    decalage = _decalage_minutes(contexte.get('meteo') or {})
    if decalage is None:
        return serie, etapes.etape_omise(libelle, MOTIF_SANS_BASE_DE_TEMPS,
                                         champ='meteo.heure.decalage_minutes')
    if _instant_utc(points[0], decalage) is None:
        return serie, etapes.etape_omise(
            libelle, "Les points de la série ne portent pas d'horodatage "
            'lisible : la position du soleil ne peut pas leur être associée.',
            champ='serie.points[].heure')

    attenuation = _attenuation(contexte)
    azimuts = sorted(releves)
    hauteurs = [releves[azimut] for azimut in azimuts]
    hauteur_moyenne = sum(hauteurs) / len(hauteurs)
    fraction_ciel = 1.0
    facteur_albedo = 1.0
    if attenuation['active']:
        fraction_ciel = max(0.0, 1.0 - hauteur_moyenne / 90.0)
        facteur_albedo = max(
            0.0, 1.0 - max(0.0, hauteur_moyenne) / HAUTEUR_ALBEDO_NUL_DEG)

    suite, masquees = _masquer(serie, points, azimuts, releves,
                               latitude=latitude, longitude=longitude,
                               decalage=decalage, fraction_ciel=fraction_ciel,
                               facteur_albedo=facteur_albedo)
    return suite, etapes.etape_appliquee(
        libelle,
        source=profil.get('source') or 'saisie',
        reference=REFERENCE,
        entree={
            'profil': {
                'source': profil.get('source'),
                'directions': len(azimuts),
                'hauteur_max_deg': round(max(hauteurs), 3),
                'hauteur_moyenne_deg': round(hauteur_moyenne, 3),
            },
            'convention_direct': (
                'PVsyst — sous la ligne d’horizon le faisceau direct est '
                'coupé en TOUT ou RIEN.'),
            'convention_diffus': (
                'fraction de ciel visible « 1 − Σ hauteur / (90 × N) » sur '
                f'les {len(azimuts)} azimuts du profil'
                if attenuation['active'] else
                "atténuation désactivée par le réglage société : le diffus "
                'ressort intact.'),
            'convention_reflechi': (
                'PVsyst — facteur linéaire décroissant, nul au-delà de '
                f'{HAUTEUR_ALBEDO_NUL_DEG:g}° de hauteur d’horizon'
                if attenuation['active'] else
                "atténuation désactivée par le réglage société : le réfléchi "
                'ressort intact.'),
            'attenuation': attenuation['etat'],
            'attenuation_source': attenuation['source'],
            'fraction_ciel_visible': round(fraction_ciel, 6),
            'facteur_reflechi': round(facteur_albedo, 6),
            'heures_masquees': masquees,
            'heures_lues': len(points),
            'decalage_minutes': decalage,
            'source_elevation': (
                'h_sun_deg de PVGIS quand la colonne est présente, '
                'core.calepinage.soleil à défaut ; azimut toujours calculé '
                '(seriescalc ne le publie pas).'),
        })


# ── les entrées, une par une ────────────────────────────────────────────

def _libelle():
    """Le libellé FRANÇAIS du poste, déclaré une seule fois (CALX148)."""
    from apps.calepinage.services.chaine_pertes import LIBELLES

    return LIBELLES[POSTE]


def _profil(contexte):
    """Le profil d'horizon du document, ou ``None``.

    Deux emplacements sont lus, dans cet ordre : ``contexte['horizon']`` (le
    profil que ``services/horizon.py`` publie) et, à défaut, le profil que le
    bloc météo porterait sous ``meteo.horizon.profil``.
    """
    profil = contexte.get('horizon')
    if not isinstance(profil, dict):
        profil = ((contexte.get('meteo') or {}).get('horizon')
                  or {}).get('profil')
    return profil if isinstance(profil, dict) else None


def _releves(profil):
    """``{azimut de 0 à 360 depuis le nord: hauteur}`` lus dans le profil.

    Les deux repères du profil sont acceptés : ``azimut_face_deg`` (0 = nord,
    celui du document) et ``azimut_pvgis_deg`` (0 = sud). Deux relevés pour
    la même direction : la plus HAUTE est gardée — un masque ne se
    sous-estime pas.
    """
    releves = {}
    for point in (profil.get('points') or ()):
        if not isinstance(point, dict):
            continue
        azimut = _nombre(point.get('azimut_face_deg'))
        if azimut is None:
            pvgis = _nombre(point.get('azimut_pvgis_deg'))
            azimut = None if pvgis is None else pvgis + 180.0
        hauteur = _nombre(point.get('hauteur_deg'))
        if azimut is None or hauteur is None:
            continue
        azimut %= 360.0
        if azimut in releves:
            hauteur = max(hauteur, releves[azimut])
        releves[azimut] = hauteur
    return releves


def _decalage_minutes(meteo):
    """Le décalage de la série sur l'UTC, en minutes, ou ``None``.

    Rien n'est supposé : soit la série se déclare en UTC, soit le décalage
    du site est posé (CALX59). Une liste de décalages n'est lue que si elle
    n'en porte qu'un seul — deux décalages différents veulent dire que la
    série change d'heure en cours de route, et cela se traite point par
    point, pas en bloc.
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


def _attenuation(contexte):
    """L'état de l'atténuation du diffus et du réfléchi, et sa provenance."""
    saisie = etapes.reglage(contexte, 'attenuation_horizon')
    if saisie is None:
        return {'active': True, 'etat': 'conventions_citees',
                'source': 'PVsyst — Far shadings : horizon'}
    valeur = saisie.get('valeur')
    texte = str(valeur).strip().lower()
    inactive = (valeur is False or valeur == 0
                or texte in VALEURS_SANS_ATTENUATION)
    return {
        'active': not inactive,
        'etat': 'desactivee' if inactive else 'conventions_citees',
        'source': saisie.get('source'),
    }


# ── le masquage, heure par heure ────────────────────────────────────────

def _masquer(serie, points, azimuts, releves, *, latitude, longitude,
             decalage, fraction_ciel, facteur_albedo):
    """Une COPIE de la série masquée, et le nombre d'heures coupées."""
    suite = []
    masquees = 0
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
        hauteur = _hauteur_interpolee(
            azimuts, releves, position.azimut_depuis_sud_deg % 360.0)
        sous_l_horizon = _elevation(point, position) < hauteur
        if sous_l_horizon and directe > 0.0:
            masquees += 1
        copie = dict(point)
        copie['gb_i_w_m2'] = 0.0 if sous_l_horizon else directe
        copie['gd_i_w_m2'] = (_nombre(point.get('gd_i_w_m2')) or 0.0) \
            * fraction_ciel
        copie['gr_i_w_m2'] = (_nombre(point.get('gr_i_w_m2')) or 0.0) \
            * facteur_albedo
        _reporter(point, copie)
        suite.append(copie)
    rendue = dict(serie)
    rendue['points'] = suite
    return rendue, masquees


def _elevation(point, position):
    """La hauteur du soleil : celle de PVGIS d'abord, la calculée à défaut.

    ``h_sun_deg`` est la colonne ``H_sun`` de la réponse PVGIS, publiée telle
    quelle (CALX152) : c'est la hauteur de la SOURCE, synchrone de son
    irradiance à la minute près. ``position_solaire`` reste indispensable
    pour l'AZIMUT, que ``seriescalc`` ne publie pas — et sert ici de repli
    quand la colonne manque.
    """
    lue = _nombre(point.get('h_sun_deg'))
    return position.elevation_deg if lue is None else lue


def _reporter(avant, apres):
    """Recompose ``gi_w_m2`` et met l'énergie à l'échelle du même rapport.

    ``G(i)`` est la SOMME des trois composantes (vérifié sur les réponses
    PVGIS réelles par ``tests/test_calx152_composantes.py``) : la laisser
    inchangée après un masquage la rendrait incohérente avec ses propres
    composantes. Quand la série porte déjà une colonne de puissance, elle
    suit le MÊME rapport, heure par heure — jamais un rapport annuel moyen.
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


def _hauteur_interpolee(azimuts, releves, azimut):
    """La hauteur d'horizon à ``azimut``, interpolée LINÉAIREMENT.

    En circulaire : le secteur qui enjambe le nord n'est pas un trou.
    """
    rang = bisect.bisect_left(azimuts, azimut)
    if rang == 0 or rang == len(azimuts):
        bas, haut = azimuts[-1], azimuts[0]
        portee = (haut - bas) % 360.0
        ecart = (azimut - bas) % 360.0
    else:
        bas, haut = azimuts[rang - 1], azimuts[rang]
        portee = haut - bas
        ecart = azimut - bas
    if portee <= 0.0:
        return releves[bas]
    return releves[bas] + (releves[haut] - releves[bas]) * (ecart / portee)


def _nombre(valeur):
    """Un flottant lisible, ou ``None`` — jamais une valeur de remplacement."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre
