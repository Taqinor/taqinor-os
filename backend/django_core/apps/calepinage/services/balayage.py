"""ACAL468 — le BALAYAGE d'orientation d'un pan libre (inclinaison × azimut).

Contrat ``contract_samples/calepinage_balayage.json`` (ACAL388). Pour chaque
point de la grille, la simulation COMPLÈTE (chaîne de pertes comprise) est
rejouée sur une COPIE du document où le pan porte l'inclinaison et l'azimut
du point, avec le MÊME ``ClientPvgis`` — donc son cache : un couple distinct
= un appel PVGIS, un rejeu dans le TTL = zéro. RIEN n'est écrit au
calepinage (``enregistrer=False``).

Un pan dont l'orientation est un CHOIX : surface de pose (champ au sol,
ombrière) ou toit plat à châssis. Un pan à pente imposée par le toit
(``roofType`` « pitched »), une façade ou une pose est-ouest est refusé.
Axes pris en charge ici : ``inclinaison_deg`` et ``azimut_deg`` (boussole,
180 = Sud, comme ``pose.pans[].azimut_deg``) et, depuis ACAL477,
``ratio_dc_ac`` : la chaîne est rejouée sur la MÊME météo (mêmes appels,
zéro de plus) avec la puissance AC de l'onduleur remise à l'échelle
(kWc ÷ ratio ; la fiche réelle reste celle de la courbe de rendement et de
la fenêtre MPPT). ``ecretage_pct`` est celui de l'étape « écrêtage ».
"""
from __future__ import annotations

import copy
import types

from .pvgis_serie import CACHE_MAX

__all__ = ['AXES_PRIS_EN_CHARGE', 'BalayageInvalide', 'appliquer_point',
           'balayer', 'points_de_la_grille', 'valider_demande']

AXES_PRIS_EN_CHARGE = ('inclinaison_deg', 'azimut_deg', 'ratio_dc_ac')
_BORNES = {'inclinaison_deg': (0.0, 90.0), 'azimut_deg': (0.0, 360.0)}
MENTION_RATIO = "onduleur de même fiche remis à l'échelle — hypothèse"
_EPSILON = 1e-9


class BalayageInvalide(ValueError):
    """Une demande refusée : ``champ`` dit où (jamais un refus générique).

    ``forme`` = la FORME du corps viole le schéma publié (400) ; sinon le
    refus tient au document ou à une contrainte croisée que le schéma ne peut
    pas dire (409, comme ``refuser_caractere_interdit``) — api-fuzz #1512.
    """

    def __init__(self, message, *, champ='', forme=False):
        super().__init__(message)
        self.champ = champ
        self.forme = forme


def _nombre(valeur, champ):
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise BalayageInvalide('Un nombre est attendu.', champ=champ,
                               forme=True)
    return float(valeur)


def _forme_de_l_axe(axe, indice):
    """``(nom, min, max, pas)`` ou refus de FORME (400) : ce que le schéma
    publié dit d'un axe (``views/balayage._AXES_RESSERRES``)."""
    base = 'axes[%d]' % indice
    if not isinstance(axe, dict):
        raise BalayageInvalide("Un axe est un objet {nom, min, max, pas}.",
                               champ=base, forme=True)
    nom = axe.get('nom')
    if nom not in AXES_PRIS_EN_CHARGE:
        raise BalayageInvalide(
            'Axe inconnu : %r (attendu : %s).'
            % (nom, ', '.join(AXES_PRIS_EN_CHARGE)), champ=base + '.nom',
            forme=True)
    mini = _nombre(axe.get('min'), base + '.min')
    maxi = _nombre(axe.get('max'), base + '.max')
    pas = _nombre(axe.get('pas'), base + '.pas')
    if pas <= 0:
        raise BalayageInvalide('Le pas doit être strictement positif.',
                               champ=base + '.pas', forme=True)
    return nom, mini, maxi, pas


def _valeurs_de_l_axe(axe, indice):
    base = 'axes[%d]' % indice
    nom, mini, maxi, pas = _forme_de_l_axe(axe, indice)
    if mini > maxi:
        raise BalayageInvalide('min dépasse max.', champ=base + '.min')
    bas, haut = _BORNES.get(nom, (None, None))
    if nom == 'ratio_dc_ac':
        if mini <= 0:
            raise BalayageInvalide('Le ratio DC/AC doit être positif.',
                                   champ=base + '.min')
    elif mini < bas or maxi > haut:
        raise BalayageInvalide('%s doit rester dans [%g ; %g].'
                               % (nom, bas, haut), champ=base + '.min')
    nombre = int((maxi - mini) / pas + _EPSILON) + 1
    if nombre > CACHE_MAX:
        raise BalayageInvalide(
            "Trop de valeurs sur l'axe (%d > %d)." % (nombre, CACHE_MAX),
            champ=base + '.pas')
    return nom, [round(mini + i * pas, 6) for i in range(nombre)]


def _cible(layout, pan, *, par_cle=False):
    """``(rangée de pans_du_document, objet du document porteur)``."""
    from apps.ventes.services import pans_du_document

    pans = pans_du_document(layout)
    ligne = None
    if isinstance(pan, bool) or pan is None:
        pan = None
    elif (not par_cle and isinstance(pan, str)
          and pan.strip().isdigit()):
        pan = int(pan.strip())
    if isinstance(pan, int):
        if 1 <= pan <= len(pans):
            ligne = pans[pan - 1]
    elif isinstance(pan, str):
        ligne = next((p for p in pans
                      if pan in (p['cle'], p['libelle'])), None)
    if ligne is None:
        raise BalayageInvalide(
            'Pan introuvable dans le document : %r.' % (pan,), champ='pan')
    if ligne['kind'] == 'facade':
        raise BalayageInvalide(
            "Une façade n'a pas d'orientation à balayer.", champ='pan')
    if ligne['kind'] == 'toit':
        zones = (layout.get('zones') or layout.get('areas')
                 or layout.get('pans') or [])
        for index, zone in enumerate(zones):
            if (isinstance(zone, dict) and str(
                    zone.get('id') or 'zone-%d' % (index + 1))
                    == ligne['cle']):
                geo = zone.get('geometry')
                if isinstance(geo, dict) and geo.get('family') == 'eastwest':
                    raise BalayageInvalide(
                        'Un pan est-ouest porte deux faces : son orientation '
                        "n'est pas un choix unique.", champ='pan')
                if str(zone.get('roofType') or '').lower() == 'pitched':
                    raise BalayageInvalide(
                        "La pente de ce pan est imposée par le toit : rien "
                        "à balayer.", champ='pan')
                return ligne, zone
    else:
        for index, surface in enumerate(layout.get('poseSurfaces') or []):
            if (isinstance(surface, dict) and str(
                    surface.get('id') or 'surface-%d' % (index + 1))
                    == ligne['cle']):
                return ligne, surface
    raise BalayageInvalide('Pan introuvable dans le document : %r.' % (pan,),
                           champ='pan')


def valider_demande(layout, corps):
    """``(cle du pan, [(axe, valeurs)])`` ou ``BalayageInvalide`` nommé."""
    if not isinstance(corps, dict):
        raise BalayageInvalide('Le corps doit être un objet.', champ='',
                               forme=True)
    axes = corps.get('axes')
    if not isinstance(axes, list) or not axes:
        raise BalayageInvalide('Au moins un axe est attendu.', champ='axes',
                               forme=True)
    # La FORME d'abord (400), le document et les contraintes croisées ensuite
    # (409) : un corps mal formé est nommé comme tel, quel que soit le toit.
    for indice, axe in enumerate(axes):
        _forme_de_l_axe(axe, indice)
    if not isinstance(layout, dict):
        raise BalayageInvalide("Le calepinage n'a pas de conception.",
                               champ='pan')
    ligne, _objet = _cible(layout, corps.get('pan'))
    vus, balayes, total = set(), [], 1
    for indice, axe in enumerate(axes):
        nom, valeurs = _valeurs_de_l_axe(axe, indice)
        if nom in vus:
            raise BalayageInvalide('Axe répété : %s.' % nom,
                                   champ='axes[%d].nom' % indice)
        vus.add(nom)
        total *= len(valeurs)
        if total > CACHE_MAX:
            raise BalayageInvalide(
                'Trop de points (%d > %d) : le cache évincerait ses propres '
                'réponses.' % (total, CACHE_MAX), champ='axes')
        balayes.append((nom, valeurs))
    return ligne['cle'], balayes


def points_de_la_grille(axes):
    """Le produit cartésien, une ligne ``{axe: valeur}`` par point."""
    points = [{}]
    for nom, valeurs in axes:
        points = [dict(p, **{nom: v}) for p in points for v in valeurs]
    return points


def appliquer_point(layout, pan, point):
    """Une COPIE du document où le pan porte l'orientation du point."""
    copie = copy.deepcopy(layout)
    ligne, objet = _cible(copie, pan, par_cle=True)
    incl = point.get('inclinaison_deg')
    azim = point.get('azimut_deg')
    if ligne['kind'] == 'toit':
        geo = objet.get('geometry')
        if incl is not None:
            objet['pitchDeg'] = incl
            if isinstance(geo, dict):
                geo['tiltDeg'] = incl
        if azim is not None:
            objet['facingAzimuthDeg'] = azim
            if isinstance(geo, dict):
                geo['azimuthDeg'] = azim
    else:
        if incl is not None:
            objet['tiltDeg'] = incl
        if azim is not None:
            objet['rowAzimuthDeg'] = (azim - 90.0) % 360.0
    return copie


def _appels_irradiance(client):
    """Les appels RÉELS (hors cache) d'irradiance faits par ce client."""
    return sum(1 for url in client.urls_appelees
               if url and '/seriescalc?' in url)


def _onduleur_au_ratio(calepinage, layout, materiel):
    """``(materiel de base, kWc, nombre)`` ou refus nommé (ACAL477)."""
    from .chaines import evaluer_onduleurs
    from .electrique import conception_du_calepinage

    conception, resolu, _donnees, _doc = conception_du_calepinage(
        calepinage, layout=layout, materiel=materiel)
    evaluation = evaluer_onduleurs(conception)
    if (evaluation is None or not evaluation.nombre
            or not (evaluation.ac_kw_unitaire or 0) > 0):
        raise BalayageInvalide(
            "L'axe « ratio_dc_ac » exige un onduleur désigné avec sa "
            "puissance AC (« electrique.onduleurs »).",
            champ='electrique.onduleurs')
    return resolu, evaluation.puissance_dc_kwc, evaluation.nombre


def _ligne_ratio(ratio, kwc, nombre, cascade):
    """``ecretage_pct`` de l'étape « écrêtage » (jamais recalculé), le
    marquage hors bornes du noyau et la mention d'hypothèse."""
    from core.electrique.onduleurs import ratios

    valeur = ratios(kwc, kwc / ratio)[0]
    etape = next((e for e in (cascade or {}).get('etapes') or ()
                  if e.get('etape') == 'ecretage'), None)
    entree = (etape or {}).get('entree') or {}
    return {'ecretage_pct': entree.get('ecretage_pct'),
            'ratio_hors_bornes': (valeur.valeur is not None
                                  and not valeur.dans_bornes),
            'mention_ratio': MENTION_RATIO}


def balayer(calepinage, corps, *, client=None, simuler=None,
            progression=None, materiel=None):
    """Le résultat au contrat : ``{grille, optimum, appels_pvgis, complete,
    socle_manquant, etat}``. Aucune écriture.

    ``simuler(calepinage, variante=…, client=…)`` est injectable (tests) ;
    par défaut la simulation complète. ``complete`` n'est vrai que si TOUS
    les points sont complets ; ``socle_manquant`` en est l'union (D-ACAL-7).
    """
    from .pvgis_serie import ClientPvgis

    layout = getattr(calepinage, 'roof_layout', None)
    pan, axes = valider_demande(layout, corps)
    client = client if client is not None else ClientPvgis()
    if simuler is None:
        from .simulation import simuler_calepinage

        def simuler(cal, *, variante, client, **extra):
            return simuler_calepinage(cal, forcer=True, client=client,
                                      enregistrer=False, variante=variante,
                                      **extra)

    grille, complete, socle = [], True, []
    points = points_de_la_grille(axes)
    avec_ratio = any(nom == 'ratio_dc_ac' for nom, _v in axes)
    if avec_ratio:
        base, kwc, nombre = _onduleur_au_ratio(calepinage, layout, materiel)
    for index, point in enumerate(points):
        fantome = types.SimpleNamespace(
            roof_layout=appliquer_point(layout, pan, point), resultat=None,
            pk=None)
        extra = {}
        if avec_ratio:
            ratio = point['ratio_dc_ac']
            extra['materiel'] = dict(base, onduleur=dict(
                base.get('onduleur') or {}, ac_kw=kwc / ratio / nombre))
        sortie = simuler(calepinage, variante=fantome, client=client, **extra)
        total = sortie['blocs']['production']['total']
        ligne = dict(point, p50_kwh=total.get('p50_kwh'),
                     rendement_specifique_kwh_kwc=total.get(
                         'specific_yield_kwh_kwc'))
        if avec_ratio:
            ligne.update(_ligne_ratio(point['ratio_dc_ac'], kwc, nombre,
                                      sortie['blocs'].get('cascade')))
        grille.append(ligne)
        complete = complete and bool(total.get('complete'))
        for manque in total.get('socle_manquant') or ():
            if manque not in socle:
                socle.append(manque)
        if progression is not None:
            progression(5 + int(90 * (index + 1) / len(points)))
    classables = [ligne for ligne in grille
                  if isinstance(ligne['rendement_specifique_kwh_kwc'],
                                (int, float))]
    optimum = (max(classables,
                   key=lambda ligne: ligne['rendement_specifique_kwh_kwc'])
               if classables else None)
    return {'grille': grille, 'optimum': optimum,
            'appels_pvgis': _appels_irradiance(client),
            'complete': complete, 'socle_manquant': socle, 'etat': 'done'}
