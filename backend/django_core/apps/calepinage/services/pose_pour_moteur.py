"""ACAL2018 (D-ACAL-97) — la FAÇADE de la pose du calepinage pour le moteur unique.

Le moteur (``apps/ventes/conception/``) ne lit jamais ``simulation.py`` : il
passe par ces deux fonctions, porte ``services`` du calepinage.

* :func:`pose_servie` — ce que le toit tracé dit au moteur, LU sans rien
  écrire : ``{nb_panneaux, kwc, complete, a_la_main, empreinte_pose,
  manquants}``. ``complete`` = la simulation peut partir (mêmes manques, mot
  pour mot, que ``services/manquants_simulation.py``, plus le module ou
  l'onduleur non désigné) ; ``a_la_main`` = le compte POSÉ diffère du compte
  que le plan a demandé à chaque pan (``neededPanels``, posé par le
  remplissage automatique) : l'utilisateur a ajouté ou retiré des panneaux.
* :func:`simuler_pose` — la production de LA simulation de la pose
  (``simulation.simuler_calepinage``, non modifiée, une seule simulation) pour
  le matériel du moteur ; ``Calepinage.resultat`` en garde le DÉTAIL au même
  ``hash_entree`` (c'est ce que ``simuler_calepinage`` écrit déjà, rien
  d'autre). Une pose incomplète n'est jamais simulée.
"""
from __future__ import annotations


def _calepinage(company, calepinage_id):
    from ..models import Calepinage

    if company is None or not calepinage_id:
        return None
    return Calepinage.objects.filter(company=company, pk=calepinage_id).first()


def _compte_demande(layout):
    """La somme des ``neededPanels`` des pans qui en portent, ``None`` sans aucun."""
    zones = (layout or {}).get('zones') if isinstance(layout, dict) else None
    demandes = [z.get('neededPanels') for z in zones or [] if isinstance(z, dict)
                and isinstance(z.get('neededPanels'), (int, float)) and not isinstance(z.get('neededPanels'), bool)]
    return int(sum(demandes)) if demandes else None


def _manquants(calepinage, materiel=None):
    """``(contexte, meta, manquants)`` — manques de la simulation de cette pose."""
    from .manquants_simulation import manquants_de_simulation
    from .simulation import SimulationRefusee, construire_contexte, fichier_meteo_depose
    from .simulation_auto import _manquants_du_materiel

    try:
        contexte, meta = construire_contexte(calepinage, materiel=materiel)
    except SimulationRefusee as refus:
        return None, None, list(refus.manquants or [{'champ': refus.champ or 'simulation',
                                                     'motif': refus.motif, 'cible': None}])
    manquants = manquants_de_simulation(contexte, meta, fichier_depose=fichier_meteo_depose(calepinage))
    return contexte, meta, manquants + _manquants_du_materiel(contexte)


def pose_servie(company, calepinage_id):
    """La pose du calepinage ``calepinage_id`` de ``company`` (``None`` s'il est
    introuvable pour elle), lue sans aucune écriture."""
    from .mesures import mesures_du_document

    calepinage = _calepinage(company, calepinage_id)
    if calepinage is None:
        return None
    layout = calepinage.roof_layout if isinstance(calepinage.roof_layout, dict) else {}
    mesures = mesures_du_document(layout)
    _contexte, _meta, manquants = _manquants(calepinage)
    nb, demande = mesures['modules'], _compte_demande(layout)
    return {'nb_panneaux': nb, 'kwc': mesures['kwc'], 'complete': bool(nb) and not manquants,
            'a_la_main': bool(nb) and demande is not None and nb != demande,
            'empreinte_pose': calepinage.layout_hash or '', 'manquants': manquants}


def simuler_pose(calepinage, *, materiel=None, client=None):
    """La production de la simulation de la pose, pour ``materiel`` (``{module,
    onduleur}`` : identifiants produit du moteur ; un rôle absent garde la
    résolution du calepinage). Rend ``{complete: False, manquants}`` sans
    simuler quand la pose est incomplète, sinon ``{complete: True,
    production_annuelle, production_mensuelle, hash_entree}``."""
    from .electrique import entree_stockee, resoudre_materiel
    from .simulation import CLE_SIMULATION, simuler_calepinage

    imposes = {'%s_produit' % role: pk for role, pk in (materiel or {}).items() if pk}
    resolu = (resoudre_materiel(calepinage.company, {**(entree_stockee(calepinage) or {}), **imposes},
                                calepinage=calepinage) if imposes else None)
    _contexte, _meta, manquants = _manquants(calepinage, materiel=resolu)
    if manquants:
        return {'complete': False, 'manquants': manquants}
    rendu = simuler_calepinage(calepinage, materiel=resolu, client=client)
    calepinage.refresh_from_db(fields=['resultat'])
    production = (calepinage.resultat or {}).get('production') or {}
    return {'complete': True, 'hash_entree': rendu.get('hash_entree')
            or ((calepinage.resultat or {}).get(CLE_SIMULATION) or {}).get('hash_entree'),
            'production_annuelle': (production.get('total') or {}).get('p50_kwh'),
            'production_mensuelle': [m.get('p50_kwh') for m in production.get('mensuel') or []] or None}
