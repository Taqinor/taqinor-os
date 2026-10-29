"""Couche VISITE de l'étude C&I — sortie de ``etude_ci.py`` (fichier-mur, C20) le
29/10/2026, pur déplacement : couverture constatée → type de pose (CIQ141), mesures
de la dernière visite ``ci`` validée (longueurs, zones de toiture, comptage) et,
depuis R3 (fondateur 28/10/2026), la mise à la terre constatée
(:func:`mise_a_la_terre_du_releve`). ``etude_ci`` ré-exporte ces noms (tests,
``revision_visite_ci``) ; les helpers communs (``_vide``, ``_num``, ``_provenance``,
``_alerte``) restent dans ``etude_ci`` et sont importés paresseusement (cycle).
"""
from __future__ import annotations


#: CIQ141 — couverture constatée à la visite → type de pose CIQ7 : seulement
#: les correspondances CERTAINES (une dalle béton lestée ou fixée reste à dire).
POSE_DE_LA_COUVERTURE_VISITE = {'bac_acier': 'bac_acier', 'tuile': 'toiture_inclinee'}


def _poser_mesure_visite(res, feuille, valeur, provenance, devis_modifiable=False):
    """Une mesure de visite passe devant le lead, jamais devant une saisie
    (corps). CORC4 (27/10/2026) : elle passe aussi devant la valeur STOCKÉE
    d'un devis encore modifiable (brouillon) — copie d'une déclaration faite
    AVANT la visite ; un devis envoyé garde ce que le client a reçu."""
    from .etude_ci import _vide  # paresseux : etude_ci importe ce module
    if _vide(valeur):
        return
    actuelle = res.provenance(feuille) or {}
    if actuelle.get('origine') == 'saisie' or (
            actuelle.get('origine') == 'devis' and not devis_modifiable):
        return
    res.poser(feuille, valeur, provenance)


#: R3.7 — constat de la visite (``releve['mise_a_la_terre']['constate']``,
#: contrat ``apps.visites.selectors.releve_ci_pour_lead``) → besoin d'une
#: mise à la terre : « à créer » ⇒ oui, « conforme » ⇒ non ; « à vérifier » ou
#: absent ⇒ rien (la composition lève alors l'alerte interne de visite).
MISE_A_LA_TERRE_DU_CONSTAT = {'a_creer': True, 'conforme': False}


def mise_a_la_terre_du_releve(releve):
    """R3.7 — ``True`` / ``False`` / ``None`` : la mise à la terre est-elle
    nécessaire d'après le relevé de visite C&I ? (Fonction pure.)"""
    terre = (releve or {}).get('mise_a_la_terre')
    if not isinstance(terre, dict):
        return None
    return MISE_A_LA_TERRE_DU_CONSTAT.get(terre.get('constate'))


def _couche_visite(res, lead, alertes, devis=None):
    """CIQ141 — le relevé de la dernière visite ``ci`` VALIDÉE du lead (façade
    ``apps.visites.selectors.releve_ci_pour_lead``, jamais ses modèles) :
    vérifié par la visite > déclaré > absent. Une mesure « non relevée » ne
    remplace rien et lève une alerte nommée."""
    from .etude_ci import _alerte, _num, _provenance, _vide  # paresseux (cycle)
    if lead is None:
        return
    from apps.visites.selectors import releve_ci_pour_lead
    releve = releve_ci_pour_lead(lead)
    if not releve:
        return
    prov = _provenance('mesure_visite', 'visite %s' % releve.get('visite_id'),
                       releve.get('validee_le'))
    modifiable = devis is None or (getattr(devis, 'statut', '') or '') == 'brouillon'

    def poser(feuille, valeur):
        _poser_mesure_visite(res, feuille, valeur, prov, modifiable)

    # Longueurs de cheminement : CORC4 (constat CMP, 27/10/2026) — le trajet
    # le PLUS LONG, jamais la somme : la composition lit le DC comme une
    # distance aller simple champ → onduleur (2 × chaînes × distance) et l'AC
    # comme une distance par onduleur.
    trajets = releve.get('trajets') or []
    for cle in ('longueur_dc_m', 'longueur_ac_m'):
        valeurs = [_num(t.get(cle)) for t in trajets if _num(t.get(cle)) is not None]
        if valeurs:
            poser(cle, round(max(valeurs), 2))
    # Zones de toiture : la plus grande surface utile devient le toit de l'étude.
    zones = []
    for zone in releve.get('zones_toiture') or []:
        surface = _num(zone.get('surface_utile_m2'))
        if surface is None and _num(zone.get('longueur_m')) and _num(zone.get('largeur_m')):
            surface = _num(zone['longueur_m']) * _num(zone['largeur_m'])
        zones.append((surface or 0.0, zone))
    if len(zones) > 1:
        alertes.append(_alerte('plusieurs_zones_toiture', 'toit',
                               'Plusieurs zones de toiture relevées : calepinage requis.'))
    if zones:
        surface, zone = max(zones, key=lambda z: z[0])
        if surface:
            poser('surface_utile_m2', round(surface, 2))
            poser('surface_type', 'mesuree')
        couverture = zone.get('couverture')
        poser('couverture', couverture)
        poser('type_pose', POSE_DE_LA_COUVERTURE_VISITE.get(couverture))
        poser('pente_deg', _num(zone.get('pente_deg')))
        charge = _num(zone.get('charge_admissible_declaree_kg_m2'))
        if charge is not None:
            piece = zone.get('charge_admissible_piece')
            source = 'pièce %s, zone « %s » (visite %s du %s)' % (
                piece if not _vide(piece) else 'non jointe', zone.get('libelle') or '?',
                releve.get('visite_id'), releve.get('validee_le'))
            poser('charge_admissible_kg_m2', charge)
            poser('charge_admissible_source', source)
    # Comptage : seulement si le lead ne le porte pas encore.
    tension = (releve.get('niveau_tension') or {}).get('constate')
    if tension and res.valeur('tension') in (None, 'inconnue'):
        res.poser('tension', tension, prov)
    puissance = (releve.get('puissance_souscrite_kva') or {}).get('constate')
    if puissance is not None and res.valeur('puissance_souscrite_kva') is None:
        res.poser('puissance_souscrite_kva', puissance, prov)
    # R3.7 — la mise à la terre constatée à la visite (jamais une saisie
    # écrasée : même règle que les autres mesures).
    poser('mise_a_la_terre_necessaire', mise_a_la_terre_du_releve(releve))
    for mesure, motif in sorted((releve.get('non_releves') or {}).items()):
        alertes.append(_alerte('mesure_non_verifiee', mesure,
                               '%s non vérifiée à la visite (%s).' % (mesure, motif)))
