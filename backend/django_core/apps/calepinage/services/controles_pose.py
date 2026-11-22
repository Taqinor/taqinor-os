"""ACAL568 — les ALERTES de pose d'une nomenclature de fixation.

Le document ne porte pas la position des crochets : le contrôle se fait sur
des valeurs DÉCLARÉES par le système (``SystemeFixation.controles_pose``,
saisies et sourcées, vides par défaut), comparées à la zone de serrage que la
fiche du module publie (ACAL567). Tout est en millimètres, sans conversion.

Rien n'est supposé : une zone ou une valeur non saisie ne donne JAMAIS une
alerte, mais une ligne ``info`` qui nomme ce qui manque.
"""
from __future__ import annotations

from .valeurs import nombre

__all__ = ['alertes_du_systeme', 'erreur_de_controles_pose']

#: Les trois valeurs numériques déclarées (mm) ; ``source`` est un texte.
CHAMPS_MM = ('distance_rail_bord_mm', 'porte_a_faux_rail_mm',
             'porte_a_faux_max_mm')
GRAVITE_ALERTE = 'alerte'
GRAVITE_INFO = 'info'


def _fr(valeur):
    return f'{valeur:g}'.replace('.', ',')


def erreur_de_controles_pose(valeur):
    """``''`` si ``valeur`` est valide, sinon le message (nomme le champ)."""
    if valeur is None or valeur == {}:
        return ''
    if not isinstance(valeur, dict):
        return 'Les contrôles de pose se saisissent en objet.'
    inconnues = sorted(set(valeur) - set(CHAMPS_MM) - {'source'})
    if inconnues:
        return f'Contrôle de pose inconnu : « {inconnues[0]} ».'
    saisis = False
    for cle in CHAMPS_MM:
        if valeur.get(cle) is None:
            continue
        saisis = True
        lu = None if isinstance(valeur[cle], str) else nombre(valeur[cle])
        if lu is None or lu < 0:
            return f'« {cle} » : un nombre de millimètres positif est attendu.'
    if saisis and not str(valeur.get('source') or '').strip():
        return ('La source des contrôles de pose est obligatoire dès qu\'une '
                'valeur est saisie (notice du fabricant).')
    return ''


def _info(message):
    return {'code': 'controle_non_fait', 'gravite': GRAVITE_INFO,
            'message': message}


def _alerte(code, message):
    return {'code': code, 'gravite': GRAVITE_ALERTE, 'message': message}


def _zone_serrage(distance, module):
    if distance is None:
        return None
    mini = nombre(module.get('serrage_min_mm'))
    maxi = nombre(module.get('serrage_max_mm'))
    if mini is None or maxi is None:
        return _info('Zone de serrage du module non saisie sur sa fiche : la '
                     'distance rail-bord n\'est pas contrôlée.')
    if distance < mini or distance > maxi:
        return _alerte(
            'zone_serrage',
            f'Rail à {_fr(distance)} mm du bord, hors de la zone de serrage '
            f'du module ({_fr(mini)} à {_fr(maxi)} mm).')
    return None


def _porte_a_faux(controles):
    reel = nombre(controles.get('porte_a_faux_rail_mm'))
    admis = nombre(controles.get('porte_a_faux_max_mm'))
    if reel is None and admis is None:
        return None
    if reel is None or admis is None:
        manque = ('porte-à-faux du rail' if reel is None
                  else 'porte-à-faux maximal admis')
        return _info(f'Contrôle du porte-à-faux non fait : {manque} non '
                     'saisi sur le système.')
    if reel > admis:
        return _alerte('porte_a_faux',
                       f'Porte-à-faux du rail {_fr(reel)} mm, '
                       f'{_fr(admis)} mm admis.')
    return None


def _alertes(controles, module):
    """``[{code, gravite, message}]`` — PUR (aucune lecture de base)."""
    if not controles:
        return [_info('Contrôles de pose non saisis sur le système : ni la '
                      'distance rail-bord ni le porte-à-faux ne sont '
                      'contrôlés.')]
    alertes = [_zone_serrage(nombre(controles.get('distance_rail_bord_mm')),
                             module or {}),
               _porte_a_faux(controles)]
    return [alerte for alerte in alertes if alerte]


def alertes_du_systeme(calepinage, systeme):
    """Les alertes du système retenu, le module étant celui du calepinage
    (``resoudre_materiel``, lu par ``specs_for_produit``)."""
    controles = getattr(systeme, 'controles_pose', None) or {}
    if not controles:
        return _alertes(controles, None)
    from .electrique import entree_stockee, resoudre_materiel

    materiel = resoudre_materiel(getattr(calepinage, 'company', None),
                                 entree_stockee(calepinage),
                                 calepinage=calepinage)
    return _alertes(controles, materiel.get('module'))
