"""Le corps PUBLIÉ de ``POST calepinages/<id>/entree-electrique/`` (ENF11).

Chaque champ de ``services.electrique.CHAMPS_ENTREE`` est publié avec la
forme que ``_valider_entree`` / ``_valider_produits_designes`` ACCEPTENT : un
corps conforme au schéma n'est jamais refusé en 400 (api-fuzz-full 24/10 :
``temperature_max_c: []`` « conforme » car le champ était publié libre).

Quand le serveur juge un champ par une règle que le schéma ne sait pas dire
(document du calepinage, droit d'approbation, check-list dépendant du
matériel), le schéma publie le SOUS-ENSEMBLE toujours accepté (objet ou liste
vide) : le contenu riche reste accepté par le serveur, il n'est simplement pas
annoncé au schéma. Les vocabulaires (stratégies, couplages, grandeurs du
transformateur) viennent des services, jamais recopiés.
"""
from __future__ import annotations

from core.champs_stricts import MOTIF_NON_BLANC_SANS_NUL, MOTIF_SANS_NUL

__all__ = ['corps_entree_resserre', 'refuser_caractere_interdit',
           'REGLE_TEMPERATURES']

#: Identifiant de produit : entier de clé primaire, ou ``null`` (efface la
#: désignation). Un identifiant inconnu de la société est un 404.
_ID_PRODUIT = {'type': 'integer', 'minimum': 1, 'maximum': 2147483647,
               'nullable': True}

#: Les deux températures se jugent PAR PAIRE (``_saisie``) : l'une sans
#: l'autre est refusée, et le minimum doit rester sous le maximum. Le schéma
#: dit « les deux ou aucune » et sépare les plages (minimum ≤ 0 < maximum).
_TEMP_MIN = {'type': 'number', 'minimum': -60, 'maximum': 0}
_TEMP_MAX = {'type': 'number', 'minimum': 1, 'maximum': 100}

REGLE_TEMPERATURES = {'anyOf': [
    {'required': ['temperature_min_c', 'temperature_max_c']},
    {'not': {'anyOf': [{'required': ['temperature_min_c']},
                       {'required': ['temperature_max_c']}]}},
]}

_VIDE_OBJET = {'type': 'object', 'maxProperties': 0}
_VIDE_LISTE = {'type': 'array', 'maxItems': 0}


def _positif(maximum, *, strict=False):
    regle = {'type': 'number', 'maximum': maximum}
    if strict:
        regle.update(minimum=0, exclusiveMinimum=True)
    else:
        regle['minimum'] = 0
    return regle


def _transformateur():
    from .services.etapes.transformateur import (
        CHAMP_A_VIDE, CHAMP_EN_CHARGE, CHAMP_NOMINAL,
    )

    grandeur = {
        'type': 'object', 'nullable': True,
        'required': ['valeur', 'source'], 'additionalProperties': False,
        'properties': {
            'valeur': _positif(1e6),
            'source': {'type': 'string', 'pattern': MOTIF_NON_BLANC_SANS_NUL},
            'reference': {'type': 'string', 'pattern': MOTIF_SANS_NUL}}}
    return {'type': 'object', 'required': ['declare'],
            'additionalProperties': False,
            'properties': {
                'declare': {'type': 'boolean'},
                CHAMP_A_VIDE: grandeur, CHAMP_EN_CHARGE: grandeur,
                CHAMP_NOMINAL: grandeur}}


def _batterie():
    from .services.batterie import (
        COUPLAGES, FENETRES_MAX, MOTIVATIONS, STRATEGIES)

    heures = {'type': 'array', 'items': {
        'type': 'integer', 'minimum': 0, 'maximum': 23}}
    fenetres = {'type': 'array', 'minItems': 1, 'maxItems': FENETRES_MAX,
                'items': {'type': 'object', 'additionalProperties': False,
                          'required': ['heures'], 'properties': {
                              'heures': dict(heures, minItems=1),
                              'soc_cible_pct': _positif(100)}}}
    return {'type': 'object', 'additionalProperties': False, 'properties': {
        'strategie': {'type': 'string', 'enum': list(STRATEGIES)},
        'couplage': {'type': 'string', 'enum': list(COUPLAGES)},
        'motivation': {'type': 'string', 'enum': list(MOTIVATIONS)},
        'packs': {'type': 'integer', 'minimum': 1, 'maximum': 1000},
        'seuil_effacement_kw': _positif(1e6),
        'reserve_backup_kwh': _positif(1e6),
        'etat_initial_kwh': _positif(1e6),
        'heures_charge': heures, 'heures_decharge': heures,
        # ACAL786 — secours (CALX270) et commande horaire (CALX268).
        'appareils': {'type': 'array', 'minItems': 1, 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['puissance_continue_kw', 'puissance_pointe_kw',
                         'quantite'],
            'properties': {
                'nom': {'type': 'string', 'pattern': MOTIF_SANS_NUL},
                'puissance_continue_kw': _positif(1e4, strict=True),
                'puissance_pointe_kw': _positif(1e4, strict=True),
                'quantite': _positif(1e4, strict=True)}}},
        'duree_secours_h': _positif(1e3, strict=True),
        'fenetres': {'type': 'object', 'additionalProperties': False,
                     'required': ['charge', 'decharge'], 'properties': {
                         sorte: fenetres for sorte in ('charge', 'decharge')}},
        'part_effacable_pct': _positif(100, strict=True),
        'plafond_effacable_kw': _positif(1e6, strict=True),
        # ACAL796 — coupures de réseau déclarées (null efface) ; plage jugée
        # par services/batterie_declaration.py::_valider_coupures.
        'coupures': {'type': 'object', 'nullable': True,
                     'additionalProperties': False,
                     'required': ['nombre_par_an', 'duree_h', 'heure_debut'],
                     'properties': {
                         'nombre_par_an': {'type': 'integer', 'minimum': 1},
                         'duree_h': {'type': 'integer', 'minimum': 1},
                         'heure_debut': {'type': 'integer', 'minimum': 0,
                                         'maximum': 23}}}},
           # ACAL786 — appareils ⇒ durée, jamais avec la réserve nue ; fenêtres
           # OU listes d'heures, jamais les deux (règles de services/batterie.py).
           'allOf': [
               {'anyOf': [{'not': {'required': ['appareils']}},
                          {'required': ['duree_secours_h'],
                           'not': {'required': ['reserve_backup_kwh']}}]},
               {'not': {'required': ['fenetres', 'heures_charge']}},
               {'not': {'required': ['fenetres', 'heures_decharge']}}]}


def _hors_reseau():
    return {'type': 'object', 'additionalProperties': False, 'properties': {
        'actif': {'type': 'boolean'},
        'jours_autonomie': _positif(365, strict=True),
        'etat_initial_kwh': _positif(1e6),
        # ACAL790 — seuils de protection (CALX272) ; l'ordre arrêt ≤
        # entretien ≤ veille est jugé par services/hors_reseau.py.
        'seuils': {'type': 'object', 'nullable': True,
                   'additionalProperties': False,
                   'required': ['veille_pct', 'entretien_pct', 'arret_pct'],
                   'properties': {nom: _positif(100) for nom in (
                       'veille_pct', 'entretien_pct', 'arret_pct')}},
        # ACAL800 — groupe d'appoint (null efface) ; démarrage < arrêt jugé
        # par services/groupe_appoint.py.
        'groupe': {'type': 'object', 'nullable': True,
                   'additionalProperties': False, 'required': ['actif'],
                   'properties': {
                       'actif': {'type': 'boolean'},
                       'puissance_kw': _positif(1e6, strict=True),
                       'soc_demarrage_pct': _positif(100),
                       'soc_arret_pct': _positif(100),
                       'heures_max_par_jour': _positif(24, strict=True)}}}}


def corps_entree_resserre():
    """La règle ``x-corps-resserre`` du corps : clés FERMÉES (celles de
    ``CHAMPS_ENTREE``), chacune typée comme le serveur la lit."""
    from .services.electrique import CHAMPS_ENTREE

    publiees = {
        'module_produit': _ID_PRODUIT,
        'onduleur_produit': _ID_PRODUIT,
        'optimiseur_produit': _ID_PRODUIT,
        'temperature_min_c': _TEMP_MIN,
        'temperature_max_c': _TEMP_MAX,
        'dc_m': _positif(1000),
        'ac_m': _positif(1000),
        # Le cheminement par pan se juge sur le document : le schéma n'annonce
        # que l'objet vide (aucun pan à vérifier).
        'cheminement': _VIDE_OBJET,
        'phases': {'type': 'integer', 'enum': [1, 3]},
        'zone_keraunique': {'type': 'boolean'},
        'inclure_prise_terre': {'type': 'boolean'},
        'plafond_kwc_par_onduleur': _positif(100000, strict=True),
        'nombre_onduleurs': {'type': 'integer', 'minimum': 1,
                             'maximum': 1000},  # ACAL633
        'longueur_chaine_forcee': {'type': 'integer', 'minimum': 1,
                                   'maximum': 1000},
        'protections': _VIDE_OBJET, 'terre': _VIDE_OBJET,
        'exigence_marche': _VIDE_OBJET, 'affectation_manuelle': _VIDE_OBJET,
        'polystring': _VIDE_LISTE,
        # Passer outre une alerte exige le droit d'approbation et un code
        # réellement prononcé : liste vide seule annoncée.
        'derogations': _VIDE_LISTE,
        'transformateur': _transformateur(),
        'regime': {'type': 'string', 'enum': ['TT', 'TN', 'IT']},
        'batterie': _batterie(),
        'hors_reseau': _hors_reseau(),
    }
    manquants = [cle for cle in CHAMPS_ENTREE if cle not in publiees]
    if manquants:  # un champ ajouté demain au service doit être typé ici
        raise RuntimeError(
            "champs_entree : champ(s) sans forme publiée : %s"
            % ', '.join(manquants))
    return {'properties': {cle: publiees[cle] for cle in CHAMPS_ENTREE},
            'additionalProperties': False,
            'allOf': [REGLE_TEMPERATURES]}


def refuser_caractere_interdit(corps):
    """409 si la saisie porte U+0000 ou un demi-substitut isolé (clé OU valeur,
    à toute profondeur) : ne se range pas en JSONB, et un sous-objet libre ne
    peut pas le dire au schéma (refus d'état, même doctrine que les réglages
    et le document de conception)."""
    from core.conflit_etat import ConflitEtat

    from .services.parametres import _chemin_caractere_interdit

    interdit = _chemin_caractere_interdit(corps, 'entree_electrique')
    if interdit:
        raise ConflitEtat(
            "« %s » contient un caractère interdit (caractère nul ou "
            "illisible) : corrigez la saisie." % interdit)
