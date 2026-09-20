"""CAL138 — production PAR PAN, avec l'orientation et l'inclinaison RÉELLES.

LE CONSTAT
----------
La production du devis repose sur un productible de VILLE
(``frontend/src/features/ventes/solar.js``, table ``PRODUCTIBLE_PAR_VILLE``,
défaut Casablanca) : un seul chiffre pour toute la ville, quelle que soit
l'orientation du toit. Or le calepinage CONNAÎT la pente et l'azimut de chaque
pan (``zones[].geometry.tiltDeg`` / ``azimuthDeg`` du document ``roof_layout``
v2). PVsyst autorise d'ailleurs jusqu'à 8 orientations dans une variante.

LA RÈGLE POSÉE ICI
------------------
1. **Un appel PVGIS par PLAN réel** (angle + azimut du pan), jamais un azimut
   moyen : la moyenne de deux pans opposés est un toit qui n'existe pas.
2. **Le total est la SOMME des pans**, au prorata des modules réellement
   posés. Il ne peut donc pas diverger du détail affiché.
3. **Un pan sans module ne pèse rien** : aucun appel, aucune production — et
   ``p50_kwh`` vaut ``null``, jamais ``0`` (un 0 se lirait « ce pan ne produit
   rien », là où personne n'a rien posé dessus).
4. **Rien n'est inventé.** P75/P90 et la variabilité inter-annuelle ne sont
   PAS calculés ici (c'est CAL142) : ils valent ``null`` et la raison est
   publiée dans ``avertissements``. L'ombrage par pan n'est pas mesuré ici non
   plus.
5. **Les pertes sont celles de CAL238** : la somme explicite passée à PVGIS,
   republiée avec le résultat.

La forme rendue est celle du contrat committé
``contract_samples/calepinage_resultat.json`` (blocs ``production`` et
``pertes``) — aucune clé inventée.
"""
from __future__ import annotations

from .pvgis_serie import BASE_PAR_DEFAUT, EntreeInvalide, azimut_pvgis

__all__ = ['PanSansOrientation', 'pans_du_layout', 'production_du_layout']

#: Arrondi d'affichage des énergies (Wh près, en kWh) — un arrondi
#: d'AFFICHAGE, pas un calcul : les sommes se font sur les valeurs pleines.
DECIMALES_KWH = 1


class PanSansOrientation(EntreeInvalide):
    """Un pan porte des modules mais aucune orientation exploitable."""


def _nombre(valeur):
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre:
        return None
    return nombre


def _premier(*valeurs):
    for valeur in valeurs:
        nombre = _nombre(valeur)
        if nombre is not None:
            return nombre
    return None


def pans_du_layout(layout):
    """Les pans d'un document ``roof_layout`` v2, prêts à être interrogés.

    Lit ``zones[]`` : la géométrie POSÉE (``geometry``) prime sur le résultat
    d'écran (``result``), qui prime sur le dimensionnement souhaité
    (``neededPanels``) — même ordre de préséance que les lecteurs existants du
    document. Aucune valeur par défaut n'est inventée : un pan sans
    orientation est rendu tel quel, avec ses champs à ``None``.
    """
    zones = ((layout or {}).get('zones')
             if isinstance(layout, dict) else None) or []
    pans = []
    for rang, zone in enumerate(zones):
        if not isinstance(zone, dict):
            continue
        geometrie = zone.get('geometry') if isinstance(
            zone.get('geometry'), dict) else {}
        resultat = zone.get('result') if isinstance(
            zone.get('result'), dict) else {}
        modules = _premier(geometrie.get('count'), resultat.get('count'), 0)
        pans.append({
            'pan': str(zone.get('label') or zone.get('id')
                       or f'PAN-{rang + 1}'),
            'modules': int(modules or 0),
            'kwc': _premier(geometrie.get('kwc'), resultat.get('kwc')),
            'azimut_deg': _premier(geometrie.get('azimuthDeg'),
                                   zone.get('facingAzimuthDeg')),
            'inclinaison_deg': _premier(geometrie.get('tiltDeg'),
                                        zone.get('pitchDeg')),
        })
    return pans


def _agreger(points):
    """Énergie annuelle (kWh/an), mensuelle et irradiation, depuis la série.

    La série peut couvrir PLUSIEURS années (fenêtre multi-années) : on divise
    par le nombre d'années RÉELLEMENT présentes, jamais par une constante.
    """
    annees = {p['annee'] for p in points if p.get('annee') is not None}
    nombre_annees = len(annees) or 1
    total_wh = 0.0
    irradiation_wh_m2 = 0.0
    mensuel_wh = {mois: 0.0 for mois in range(1, 13)}
    for point in points:
        puissance = point.get('p_w')
        if puissance is not None:
            total_wh += puissance          # 1 point = 1 heure ⇒ W = Wh
            mois = point.get('mois')
            if mois in mensuel_wh:
                mensuel_wh[mois] += puissance
        irradiance = point.get('gi_w_m2')
        if irradiance is not None:
            irradiation_wh_m2 += irradiance
    return {
        'annees': nombre_annees,
        'kwh_par_kwc': total_wh / 1000.0 / nombre_annees,
        'mensuel_kwh_par_kwc': {
            mois: valeur / 1000.0 / nombre_annees
            for mois, valeur in mensuel_wh.items()},
        'irradiation_kwh_m2': irradiation_wh_m2 / 1000.0 / nombre_annees,
    }


def production_du_layout(layout, *, lat, lon, politique, client,
                         annee_debut, annee_fin, base=BASE_PAR_DEFAUT,
                         montage='building'):
    """La production d'un calepinage, pan par pan PUIS au total.

    Args:
        layout: le document ``roof_layout`` v2 (pans, géométrie posée).
        lat, lon: le point GPS du site.
        politique: la ``PolitiquePertes`` de CAL238 (obligatoire).
        client: un ``ClientPvgis`` (réseau injectable).
        annee_debut, annee_fin: la fenêtre d'années demandée à PVGIS.

    Returns:
        dict aux clés du contrat : ``production`` (``base`` / ``total`` /
        ``mensuel`` / ``par_pan``), ``pertes`` et ``avertissements``.

    Raises:
        PanSansOrientation: un pan porte des modules mais pas d'orientation —
            on refuse EN NOMMANT le pan plutôt que de supposer « plein sud ».
    """
    pans = pans_du_layout(layout)
    avertissements = []
    par_pan = []
    mensuel_total = {mois: 0.0 for mois in range(1, 13)}
    total_kwh = 0.0
    total_kwc = 0.0
    irradiation_ponderee = 0.0
    provenance = None

    for pan in pans:
        kwc = pan['kwc'] or 0.0
        ligne = {
            'pan': pan['pan'],
            'modules': pan['modules'],
            'kwc': round(kwc, 3) if kwc else 0.0,
            'azimut_deg': pan['azimut_deg'],
            'inclinaison_deg': pan['inclinaison_deg'],
            'p50_kwh': None,
            'p75_kwh': None,
            'p90_kwh': None,
            'performance_ratio': None,
            'specific_yield_kwh_kwc': None,
            'shading_annual_loss_pct': None,
        }
        if not pan['modules'] or kwc <= 0:
            # Un pan sans module ne PÈSE rien : ni appel, ni kWh, ni 0 kWh.
            avertissements.append(
                f'Le pan « {pan["pan"]} » ne porte aucun module : il ne '
                'produit rien et n\'entre dans aucun total.')
            par_pan.append(ligne)
            continue
        if pan['azimut_deg'] is None or pan['inclinaison_deg'] is None:
            raise PanSansOrientation(
                f'Le pan « {pan["pan"]} » porte {pan["modules"]} module(s) '
                'mais son orientation ou son inclinaison est inconnue : la '
                'production ne peut pas être calculée sans elles (aucune '
                'orientation « plein sud » n\'est supposée).',
                champ=f'zones[{pan["pan"]}].facingAzimuthDeg')

        # Un appel PAR KWc : deux pans de même plan partagent le cache, et
        # l'échelle se fait ici — jamais une seconde requête pour une
        # puissance différente.
        serie = client.serie_horaire(
            lat=lat, lon=lon,
            inclinaison_deg=pan['inclinaison_deg'],
            aspect_deg=azimut_pvgis(pan['azimut_deg']),
            politique=politique, puissance_kwc=1.0,
            annee_debut=annee_debut, annee_fin=annee_fin,
            base=base, montage=montage)
        if provenance is None:
            provenance = serie

        agrege = _agreger(serie['points'])
        kwh = agrege['kwh_par_kwc'] * kwc
        total_kwh += kwh
        total_kwc += kwc
        for mois, valeur in agrege['mensuel_kwh_par_kwc'].items():
            mensuel_total[mois] += valeur * kwc
        irradiation = agrege['irradiation_kwh_m2']
        irradiation_ponderee += irradiation * kwc

        ligne['p50_kwh'] = round(kwh, DECIMALES_KWH)
        ligne['specific_yield_kwh_kwc'] = round(agrege['kwh_par_kwc'],
                                                DECIMALES_KWH)
        if irradiation > 0:
            # PR = énergie livrée / (kWc × irradiation sur le PLAN du pan) —
            # calculé sur la série reçue, jamais recopié d'une table.
            ligne['performance_ratio'] = round(
                agrege['kwh_par_kwc'] / irradiation, 3)
        par_pan.append(ligne)

    if provenance is None:
        avertissements.append(
            'Aucun pan ne porte de module : aucune production n\'a été '
            'demandée à PVGIS.')

    publication = politique.publication()
    performance_totale = None
    if total_kwc > 0 and irradiation_ponderee > 0:
        performance_totale = round(
            total_kwh / (irradiation_ponderee), 3)
    avertissements.append(
        'P75, P90 et la variabilité inter-annuelle ne sont pas calculés par '
        'ce service (CAL142) : ils restent « non calculés », jamais 0.')

    return {
        'production': {
            'base': {
                'source': 'pvgis' if provenance else None,
                'base_rayonnement': (provenance or {}).get('base'),
                'fenetre_annees': (provenance or {}).get('fenetre_annees'),
                'loss_passee_pct': publication['loss_passee_pct'],
                'commentaire': publication['commentaire'],
            },
            'total': {
                'kwc': round(total_kwc, 3),
                'p50_kwh': (round(total_kwh, DECIMALES_KWH)
                            if provenance else None),
                'p75_kwh': None,
                'p90_kwh': None,
                'performance_ratio': performance_totale,
                'specific_yield_kwh_kwc': (
                    round(total_kwh / total_kwc, DECIMALES_KWH)
                    if total_kwc > 0 else None),
                'annual_variability': None,
                'total_loss_pct': publication['loss_passee_pct'],
            },
            'mensuel': [
                {'mois': mois,
                 'p50_kwh': (round(mensuel_total[mois], DECIMALES_KWH)
                             if provenance else None)}
                for mois in range(1, 13)
            ] if provenance else [],
            'par_pan': par_pan,
        },
        'pertes': publication['pertes'],
        'avertissements': avertissements,
    }
