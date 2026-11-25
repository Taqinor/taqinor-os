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

import re

#: La pente supposée quand le lead n'en déclare aucune (Q1 du 23/11).
PENTE_SUPPOSEE_DEG = 30.0
#: Plein sud, convention du document (0 = nord, 180 = sud).
AZIMUT_SUD_DEG = 180.0
MESSAGE_PENTE_SUPPOSEE = ('Pente du toit supposée à 30° : renseigner « Inclinaison » sur la fiche du lead '
                          'ou tracer le toit au calepinage.')
#: L'identifiant du seul pan du toit supposé.
PAN_SUPPOSE = 'toit-suppose'


#: Le modèle du document qui porte la puissance unitaire de la CONCEPTION quand la fiche
#: du module n'en publie aucune (``modules[].pmaxWc``, comme une pose réelle).
MODULE_DE_LA_CONCEPTION = 'module-conception'
MESSAGE_PUISSANCE_CONCEPTION = ('Puissance du module prise de la conception (%s Wc, %s panneaux) : la fiche '
                                'technique de « %s » ne porte pas sa puissance crête — renseigner « pmax_wc » sur '
                                'la fiche technique du produit dans Stock.')
MESSAGE_ETAPE_SANS_FICHE = ('Étape « %s » non appliquée : la fiche technique de « %s » ne porte pas « %s » — '
                            'renseigner la fiche technique du produit dans Stock.')
#: ACAL2045 — ce qu'il faut renseigner pour que la pose ne soit plus supposée.
A_RENSEIGNER_POSE = 'renseigner « Type de toiture » sur la fiche du lead ou tracer le toit au calepinage'


def _pose_supposee(type_installation=None, type_toiture=None):
    """ACAL2045 — LA règle de D-ACAL-107 (fondateur, 25/11/2026 : « By roof type »), la seule
    place où elle vit. ``(flush, supposition)`` : sur châssis quand le lead déclare un toit plat
    (« Terrasse béton ») ou est un site commercial ou industriel (agricole : champ de pompage,
    posé sur châssis) ; sinon affleurante (toit en pente d'une maison, marché non dit). Le
    document la dit par ``flush`` comme une pose réelle : l'étape « Échauffement des modules »
    la relie à la table société (D-ACAL-84), aucun coefficient n'est posé ici."""
    if type_toiture == 'terrasse_beton':
        flush, champ, raison, quoi = False, 'type_toiture', 'toit plat déclaré', 'tracer le toit au calepinage'
    elif type_installation in ('commercial', 'industriel', 'agricole'):
        flush, champ, raison, quoi = False, 'type_installation', 'lead %s' % type_installation, A_RENSEIGNER_POSE
    else:
        flush, champ, raison, quoi = True, 'type_toiture', 'panneaux à plat sur la couverture', A_RENSEIGNER_POSE
    valeur = 'affleurante' if flush else 'sur châssis'
    return flush, {'code': 'pose_supposee', 'champ': champ, 'valeur': valeur, 'source': 'defaut',
                   'message': 'Pose des panneaux supposée %s (%s) : %s.' % (valeur, raison, quoi)}


def _document_du_plan(lat, lon, nb_panneaux, *, pente_deg, azimut_deg, watt_document=None, flush=True):
    """Le document ``roof_layout`` v2 du toit supposé : l'épingle (sans point donné : aucune,
    le site est alors celui du lead, résolu comme pour sa pose) et UN pan posé ;
    ``watt_document`` : la puissance unitaire portée par le document (``modules[].pmaxWc``,
    lue par la pose comme celle d'un pan) quand la fiche n'en a pas ; ``flush`` : la pose
    supposée (ACAL2045)."""
    epingle = {'pin': {'lat': lat, 'lng': lon}} if lat is not None and lon is not None else {}
    geometrie = {'count': nb_panneaux, 'azimuthDeg': azimut_deg, 'tiltDeg': pente_deg, 'family': 'surimposition',
                 'flush': flush}
    modeles = {}
    if watt_document:
        geometrie['moduleId'] = MODULE_DE_LA_CONCEPTION
        modeles = {'modules': [{'id': MODULE_DE_LA_CONCEPTION, 'pmaxWc': watt_document}]}
    return {'version': 2, **epingle, **modeles,
            'zones': [{'id': PAN_SUPPOSE, 'label': 'Toit supposé', 'geometry': geometrie}]}


def _taille(kwc, watt_fiche, nb_conception):
    """``(nb, watt, watt_document)`` : la fiche publie sa puissance ⇒ le kWc au module près ;
    sinon le compte et la puissance unitaire de la CONCEPTION (kWc ÷ panneaux), portés par le
    document ; ni l'un ni l'autre ⇒ ``(0, 0, None)`` (la simulation refuse, nommée)."""
    if watt_fiche:
        return max(1, int(round(float(kwc) * 1000 / watt_fiche))), watt_fiche, None
    if nb_conception and kwc:
        nb = int(nb_conception)
        watt = float(kwc) * 1000 / nb
        return nb, watt, watt
    return 0, 0.0, None


def _suppositions_du_module(rendu, materiel, nb, watt_document):
    """Rien d'inventé : la puissance prise de la conception, puis chaque étape de la cascade
    que la fiche vide empêche (``Champ manquant : « fiche_module.… »``), le produit nommé."""
    if not watt_document:
        return []
    nom = ((materiel or {}).get('designations') or {}).get('module') or 'module du moteur'
    dites = [{'code': 'puissance_module_de_la_conception', 'champ': 'fiche_technique', 'valeur': watt_document,
              'source': 'conception', 'message': MESSAGE_PUISSANCE_CONCEPTION % (
                  '{:g}'.format(watt_document), nb, nom)}]
    for etape in (rendu['blocs'].get('cascade') or {}).get('etapes') or ():
        manque = re.search(r'fiche_module\.(\w+)', etape.get('motif_omission') or '')
        if manque is None:
            continue
        champ = manque.group(1)
        dites.append({'code': 'fiche_module_incomplete', 'champ': 'fiche_technique', 'valeur': None,
                      'source': 'defaut', 'message': MESSAGE_ETAPE_SANS_FICHE % (etape.get('libelle'), nom, champ)})
    return dites


def simuler_plan_par_defaut(company, lat, lon, kwc, *, pente=None, azimut=AZIMUT_SUD_DEG, pertes=None,
                            lead_id=None, produits=None, nb_panneaux=None, materiel=None, reglages=None,
                            client=None, type_installation=None, type_toiture=None):
    """La production du plan par défaut de ``kwc`` kWc au point ``(lat, lon)``, SANS ÉCRITURE.

    ``lat`` / ``lon`` à ``None`` : le point du lead ``lead_id`` (repère toit, sinon ville de
    référence), lu par la simulation comme pour une pose de ce lead ;
    ``pente`` : la pente déclarée du lead (``None`` ⇒ 30°, dite dans ``suppositions``) ;
    ``pertes`` : postes saisis (``None`` ⇒ aucun : les valeurs de départ de la cascade) ;
    ``produits`` : ``{module, onduleur}`` identifiants produit (le matériel du moteur ;
    un rôle absent garde la résolution du calepinage) ; ``nb_panneaux`` : le compte de la
    CONCEPTION, employé seulement quand la fiche du module ne porte aucune puissance (le plan
    se pose alors à la taille de la conception, puissance portée par le document comme une
    pose réelle, et le dit dans ``suppositions``). ``materiel`` / ``reglages`` /
    ``client`` : substitutions internes et de test de ``construire_contexte``.
    ``type_installation`` / ``type_toiture`` : les champs du lead qui font la pose supposée
    (:func:`_pose_supposee`, toujours dite dans ``suppositions``).

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
    nb, watt, watt_document = _taille(kwc, float(((materiel or {}).get('module') or {}).get('pmax_wc') or 0),
                                      nb_panneaux)
    pente_deg = float(pente) if pente is not None else PENTE_SUPPOSEE_DEG
    flush, pose_dite = _pose_supposee(type_installation, type_toiture)
    pivot.roof_layout = _document_du_plan(lat, lon, nb, pente_deg=pente_deg, azimut_deg=float(azimut),
                                          watt_document=watt_document, flush=flush)
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
        'suppositions': ([] if pente is not None else [{
            'code': 'pente_supposee', 'champ': 'inclinaison_deg', 'valeur': PENTE_SUPPOSEE_DEG,
            'source': 'defaut', 'message': MESSAGE_PENTE_SUPPOSEE}]) + [pose_dite]
        + _suppositions_du_module(rendu, materiel, nb, watt_document),
        'document': pivot.roof_layout,
    }
