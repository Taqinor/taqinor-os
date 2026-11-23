"""ACAL744 — l'irradiation incidente de la base PVGIS utilisée face à l'AUTRE.

PVsyst, « Compare meteo data »
(https://www.pvsyst.com/help/meteo-database/compare-meteo-data/index.html) :
deux bases de rayonnement ne disent pas la même chose d'un même lieu. On
compare ici l'IRRADIATION incidente sur le pan de référence (la chaîne n'est
pas rejouée), pour les MÊMES années ; aucun seuil, aucune substitution : la
base de la simulation reste celle qui a servi. Une comparaison impossible est
publiée avec son motif, jamais une simulation arrêtée.
"""
from __future__ import annotations

import logging

from .valeurs import nombre

logger = logging.getLogger(__name__)

__all__ = ['MOTIF_FICHIER', 'MOTIF_ANNEES', 'MOTIF_NASA_FENETRE',
           'MOTIF_NASA_FICHIER', 'MOTIF_NASA_HORS_RESEAU', 'comparer_bases',
           'comparer_nasa_power']

MOTIF_FICHIER = ("La météo vient d'un fichier déposé : aucune autre base "
                 "PVGIS ne lui est comparée.")
MOTIF_ANNEES = ("Les deux bases ne couvrent pas les mêmes années : "
                "l'écart n'est pas calculé.")
MOTIF_NASA_FICHIER = ("La météo vient d'un fichier déposé : NASA POWER ne lui "
                      "est pas comparé.")
MOTIF_NASA_FENETRE = ("Aucune fenêtre d'années PVGIS (année type) : NASA POWER "
                      "n'est pas comparé.")
MOTIF_NASA_HORS_RESEAU = ("NASA POWER n'a pas été interrogé (aucun accès "
                          "réseau pour ce calcul) : PVGIS reste la seule source.")
MOTIF_NASA_ECHEC = ("La comparaison à NASA POWER a échoué : elle est omise, "
                    "PVGIS reste la source.")


def _ecart_pct(principale, comparee):
    """``(comparée − principale) / principale × 100``, ou ``None``."""
    if principale is None or comparee is None or principale <= 0:
        return None
    return round((comparee - principale) / principale * 100.0, 2)


def _irradiations(points, pas_minutes=60):
    """``(annees, annuelle, mensuelle[12])`` en kWh/m² : moyennes PAR ANNÉE
    de la fenêtre de ``gi_w_m2`` (W/m² × pas ÷ 1000)."""
    par_annee_mois = {}
    for point in points or ():
        gi = nombre(point.get('gi_w_m2'))
        if gi is None or point.get('annee') is None or point.get('mois') is None:
            continue
        cle = (int(point['annee']), int(point['mois']))
        par_annee_mois[cle] = (par_annee_mois.get(cle, 0.0)
                               + gi * float(pas_minutes) / 60.0 / 1000.0)
    annees = sorted({annee for annee, _mois in par_annee_mois})
    if not annees:
        return [], None, [None] * 12
    mensuelle = [sum(par_annee_mois.get((annee, mois), 0.0) for annee in annees)
                 / len(annees) for mois in range(1, 13)]
    return annees, sum(mensuelle), mensuelle


def _irradiations_de(reponse):
    pas = ((reponse.get('serie_horaire') or {}).get('pas_minutes')) or 60
    return _irradiations(reponse.get('points'), pas)


def _bloc_comparaison(principale, comparee, *, base_principale, base_comparee,
                      motif=''):
    """Le bloc ``meteo.comparaison_base`` depuis deux réponses ``serie_irradiance``
    (``comparee`` ``None`` ⇒ ``motif`` publié, ``ecart_pct`` ``null``)."""
    bloc = {'base_principale': base_principale, 'base_comparee': base_comparee,
            'irradiation_kwh_m2': {'principale': None, 'comparee': None},
            'ecart_pct': None, 'mensuel': [], 'motif': motif}
    if comparee is None or principale is None:
        return bloc
    annees_p, annuelle_p, mois_p = _irradiations_de(principale)
    annees_c, annuelle_c, mois_c = _irradiations_de(comparee)
    if not annees_p or annees_p != annees_c:
        bloc['motif'] = MOTIF_ANNEES
        return bloc
    bloc['irradiation_kwh_m2'] = {'principale': round(annuelle_p, 1),
                                  'comparee': round(annuelle_c, 1)}
    bloc['ecart_pct'] = _ecart_pct(annuelle_p, annuelle_c)
    bloc['mensuel'] = [{'mois': mois, 'principale': round(p, 1),
                        'comparee': round(c, 1), 'ecart_pct': _ecart_pct(p, c)}
                       for mois, p, c in zip(range(1, 13), mois_p, mois_c)]
    return bloc


def comparer_bases(client, plan, decision, document, fichier, compteur):
    """Les deux séries du pan de référence (la principale relue en cache, la
    comparée : UN appel de plus, compté), puis :func:`_bloc_comparaison`."""
    from .horizon import profil_depuis_document
    from .pvgis_serie import (
        BASE_PAR_DEFAUT, BASES_RAYONNEMENT, EntreeInvalide, PvgisIndisponible,
    )

    autre = next(base for base in BASES_RAYONNEMENT if base != BASE_PAR_DEFAUT)
    if fichier is not None:
        return _bloc_comparaison(None, None, base_principale=BASE_PAR_DEFAUT,
                                 base_comparee=autre, motif=MOTIF_FICHIER)
    debut, fin = (decision.get('fenetre_annees') or (None, None))
    demande = dict(
        lat=plan.get('lat'), lon=plan.get('lon'),
        inclinaison_deg=plan.get('inclinaison_deg'),
        aspect_deg=plan.get('azimut_pvgis_deg'), annee_debut=debut,
        annee_fin=fin, composantes=True, horizon=profil_depuis_document(
            (document or {}).get('horizonProfile')
            if isinstance(document, dict) else None))
    try:
        principale = client.serie_irradiance(base=BASE_PAR_DEFAUT, **demande)
        comparee = client.serie_irradiance(base=autre, **demande)
    except (EntreeInvalide, PvgisIndisponible) as refus:
        return _bloc_comparaison(None, None, base_principale=BASE_PAR_DEFAUT,
                                 base_comparee=autre, motif=str(refus))
    for reponse in (principale, comparee):
        if not reponse.get('depuis_cache'):
            compteur['appels'] += 1
    return _bloc_comparaison(principale, comparee,
                             base_principale=BASE_PAR_DEFAUT,
                             base_comparee=autre)


def _bloc_nasa_omis(ghi_pvgis, motif):
    """La forme de ``ClientNasaPower.comparaison_horizontale``, valeurs à
    ``None`` et ``motif`` nommé : la clé est toujours servie."""
    return {'source_du_chiffre': 'pvgis', 'source_comparee': 'nasa_power',
            'irradiation_horizontale_kwh_m2': {'pvgis': nombre(ghi_pvgis),
                                               'nasa_power': None},
            'ecart_pct': None, 'annees': [], 'meteo': None, 'motif': motif}


def _client_nasa(client):
    """Le client NASA POWER de ce calcul : celui posé sur le client PVGIS
    (``client_nasa_power``, transport injecté par un test), sinon un client
    neuf SEULEMENT quand PVGIS part réellement sur le réseau — un transport de
    test ne reçoit jamais une URL de NASA POWER. ``None`` : pas d'appel."""
    injecte = getattr(client, 'client_nasa_power', None)
    if injecte is not None:
        return injecte
    from . import pvgis_serie
    from .nasa_power import ClientNasaPower

    transport = getattr(client, 'transport', None)
    if transport is not None and transport is pvgis_serie._transport_urllib:
        # Le MÊME transport que PVGIS : une sonde posée sur le transport réseau
        # par un test l'intercepte aussi.
        return ClientNasaPower(transport)
    return None


def comparer_nasa_power(client, plan, decision, fichier, gain_inclinaison):
    """ACAL746 (D-ACAL-81) — ``meteo.comparaison_nasa_power`` : l'irradiation
    HORIZONTALE annuelle de NASA POWER à côté de celle de PVGIS
    (``production.gain_inclinaison.ghi_annuel_kwh_m2``, même fenêtre
    d'années). PVGIS reste la source du chiffre (un seul chiffre par valeur).
    Ne lève JAMAIS : la simulation n'échoue pas à cause de NASA POWER."""
    ghi_pvgis = (gain_inclinaison.get('ghi_annuel_kwh_m2')
                 if isinstance(gain_inclinaison, dict) else None)
    if fichier is not None:
        return _bloc_nasa_omis(ghi_pvgis, MOTIF_NASA_FICHIER)
    debut, fin = ((decision or {}).get('fenetre_annees') or (None, None))
    if debut is None or fin is None:
        return _bloc_nasa_omis(ghi_pvgis, MOTIF_NASA_FENETRE)
    try:
        nasa = _client_nasa(client)
        if nasa is None:
            return _bloc_nasa_omis(ghi_pvgis, MOTIF_NASA_HORS_RESEAU)
        return nasa.comparaison_horizontale(
            lat=plan.get('lat'), lon=plan.get('lon'), annee_debut=debut,
            annee_fin=fin, ghi_pvgis_kwh_m2=ghi_pvgis)
    except Exception:  # noqa: BLE001 — une comparaison ne fait jamais échouer la simulation (D-ENF22-BLE001)
        logger.exception('ACAL746 : comparaison NASA POWER en échec')
        return _bloc_nasa_omis(ghi_pvgis, MOTIF_NASA_ECHEC)
