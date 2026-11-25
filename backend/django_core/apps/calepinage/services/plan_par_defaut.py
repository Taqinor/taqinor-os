"""ACAL2026 (D-ACAL-97 ; Q1 du 23/11/2026, le fondateur : « Same simulation, default
roof ») — le PLAN PAR DÉFAUT d'un lead sans toit tracé.

Un toit SUPPOSÉ — un seul pan, la pente déclarée du lead sinon 30° (DITE), plein sud
sauf azimut donné, le kWc demandé au module près — simulé par LA simulation de la pose
(``simulation.simuler_calepinage``, non modifiée : même cascade de pertes, mêmes quatre
pertes de départ D-ACAL-82 quand aucune n'est saisie, même ``version_moteur``), sans
ombre proche (aucun obstacle dessiné). Le pivot est un ``Calepinage`` NON ENREGISTRÉ et
la simulation tourne en ``enregistrer=False`` : rien n'est écrit en base.

Appelants : ``remplir_conceptions --ecarts-sans-toit`` (ADEV154, la liste montrée au
fondateur), puis le moteur sans toit (ADEV155, gardé jusqu'à cette lecture).
"""
from __future__ import annotations

#: La pente supposée quand le lead n'en déclare aucune (Q1 du 23/11).
PENTE_SUPPOSEE_DEG = 30.0
#: Plein sud, convention du document (0 = nord, 180 = sud).
AZIMUT_SUD_DEG = 180.0
MESSAGE_PENTE_SUPPOSEE = ('Pente du toit supposée à 30° : renseigner « Inclinaison » sur la fiche du lead '
                          'ou tracer le toit au calepinage.')
#: L'identifiant du seul pan du toit supposé.
PAN_SUPPOSE = 'toit-suppose'


def _document_du_plan(lat, lon, nb_panneaux, *, pente_deg, azimut_deg):
    """Le document ``roof_layout`` v2 du toit supposé : l'épingle (sans point donné : aucune,
    le site est alors celui du lead, résolu comme pour sa pose) et UN pan posé."""
    epingle = {'pin': {'lat': lat, 'lng': lon}} if lat is not None and lon is not None else {}
    return {'version': 2, **epingle,
            'zones': [{'id': PAN_SUPPOSE, 'label': 'Toit supposé',
                       'geometry': {'count': nb_panneaux, 'azimuthDeg': azimut_deg, 'tiltDeg': pente_deg,
                                    'family': 'surimposition'}}]}


def simuler_plan_par_defaut(company, lat, lon, kwc, *, pente=None, azimut=AZIMUT_SUD_DEG, pertes=None,
                            lead_id=None, produits=None, materiel=None, reglages=None, client=None):
    """La production du plan par défaut de ``kwc`` kWc au point ``(lat, lon)``, SANS ÉCRITURE.

    ``lat`` / ``lon`` à ``None`` : le point du lead ``lead_id`` (repère toit, sinon ville de
    référence), lu par la simulation comme pour une pose de ce lead ;
    ``pente`` : la pente déclarée du lead (``None`` ⇒ 30°, dite dans ``suppositions``) ;
    ``pertes`` : postes saisis (``None`` ⇒ aucun : les valeurs de départ de la cascade) ;
    ``produits`` : ``{module, onduleur}`` identifiants produit (le matériel du moteur ;
    un rôle absent garde la résolution du calepinage). ``materiel`` / ``reglages`` /
    ``client`` : substitutions internes et de test de ``construire_contexte``.

    Rend ``{production_annuelle, production_mensuelle, nb_panneaux, kwc, pente_deg,
    azimut_deg, version_moteur, hash_entree, suppositions, document}``. Lève
    ``SimulationRefusee`` (champ nommé) comme la simulation de la pose."""
    from ..models import Calepinage
    from .electrique import resoudre_materiel
    from .simulation import CLE_SIMULATION, simuler_calepinage

    pivot = Calepinage(company=company, lead_id=lead_id, roof_layout={}, pertes=list(pertes or []))
    if materiel is None:
        imposes = {'%s_produit' % role: pk for role, pk in (produits or {}).items() if pk}
        materiel = resoudre_materiel(company, imposes, calepinage=pivot)
    watt = float(((materiel or {}).get('module') or {}).get('pmax_wc') or 0)
    nb = max(1, int(round(float(kwc) * 1000 / watt))) if watt else 0
    pente_deg = float(pente) if pente is not None else PENTE_SUPPOSEE_DEG
    pivot.roof_layout = _document_du_plan(lat, lon, nb, pente_deg=pente_deg, azimut_deg=float(azimut))
    rendu = simuler_calepinage(pivot, forcer=True, enregistrer=False, materiel=materiel, reglages=reglages,
                               client=client)
    production = rendu['blocs'].get('production') or {}
    return {
        'production_annuelle': (production.get('total') or {}).get('p50_kwh'),
        'production_mensuelle': [m.get('p50_kwh') for m in production.get('mensuel') or []] or None,
        'nb_panneaux': nb, 'kwc': round(nb * watt / 1000, 3),
        'pente_deg': pente_deg, 'azimut_deg': float(azimut),
        'version_moteur': rendu['blocs'][CLE_SIMULATION]['version_moteur'],
        'hash_entree': rendu['hash_entree'],
        'suppositions': [] if pente is not None else [{
            'code': 'pente_supposee', 'champ': 'inclinaison_deg', 'valeur': PENTE_SUPPOSEE_DEG,
            'source': 'defaut', 'message': MESSAGE_PENTE_SUPPOSEE}],
        'document': pivot.roof_layout,
    }
