"""ACAL786 — les réglages de SECOURS et de COMMANDE de la batterie, admis.

La simulation (``etapes/batterie.py::_bloc_batterie_dispatch``, CALX268 et
CALX270) lit déjà ``appareils``, ``duree_secours_h``, ``fenetres``,
``part_effacable_pct`` et ``plafond_effacable_kw`` ; l'enregistrement de
l'entrée électrique les refusait (``CLES_BATTERIE``, ACAL166) : aucun écran
ne pouvait les poser. Ce module porte la liste des clés admises (relue par
``services/electrique.py`` et ``services/validation_batterie.py``) et juge
ces cinq-là avec les RÈGLES MÊMES du calcul (``services/batterie.py``),
jamais une copie : un refus du calcul devient un refus d'enregistrement
nommé ``batterie.<champ>``.
"""
from __future__ import annotations

__all__ = ['CLES_BATTERIE', 'CLES_SECOURS_ET_COMMANDE', 'valider_secours']

#: ACAL786 — les cinq clés de secours (CALX270) et de commande (CALX268).
CLES_SECOURS_ET_COMMANDE = ('appareils', 'duree_secours_h', 'fenetres',
                            'part_effacable_pct', 'plafond_effacable_kw',
                            'coupures')

#: ACAL166 — les clés d'une déclaration de batterie, et AUCUNE autre : ce sont
#: celles que lit l'étape ``services/etapes/batterie.py``.
CLES_BATTERIE = ('produit', 'packs', 'strategie', 'couplage', 'onduleur_ref',
                 'seuil_effacement_kw', 'heures_charge', 'heures_decharge',
                 'reserve_backup_kwh', 'motivation',
                 'etat_initial_kwh') + CLES_SECOURS_ET_COMMANDE

MOTIF_RESERVE_EN_DOUBLE = (
    'Une réserve de secours nue (« reserve_backup_kwh ») ET des appareils '
    'secourus sont déclarés : la réserve se saisit d’une seule façon, '
    'jamais les deux.')


#: ACAL796 — les trois champs d'une coupure de réseau déclarée et leur plage
#: (une heure du jour : 0 à 23 ; un nombre et une durée : entiers d'au moins
#: 1). Aucune valeur par défaut : un champ absent est refusé.
CHAMPS_COUPURES = (('nombre_par_an', 1, None), ('duree_h', 1, None),
                   ('heure_debut', 0, 23))


def _valider_coupures(coupures):
    """ACAL796 — ``batterie.coupures`` : ``{nombre_par_an, duree_h,
    heure_debut}`` (entiers), ``None`` efface. Chaque champ faux ou manquant
    est refusé sous ``batterie.coupures.<champ>`` (jamais de défaut)."""
    from .electrique import EntreeInvalide

    if coupures is None:
        return
    if not isinstance(coupures, dict):
        raise EntreeInvalide("« coupures » doit être un objet {nombre_par_an, "
                             "duree_h, heure_debut} ou null.",
                             champ='batterie.coupures')
    inconnu = sorted(set(coupures) - {nom for nom, _, _ in CHAMPS_COUPURES})
    if inconnu:
        raise EntreeInvalide("Champ de coupure inconnu : « %s »." % inconnu[0],
                             champ='batterie.coupures.%s' % inconnu[0])
    for nom, minimum, maximum in CHAMPS_COUPURES:
        valeur = coupures.get(nom)
        if (isinstance(valeur, bool) or not isinstance(valeur, int)
                or valeur < minimum
                or (maximum is not None and valeur > maximum)):
            plage = ('un entier de %d à %d' % (minimum, maximum)
                     if maximum is not None
                     else 'un entier supérieur ou égal à %d' % minimum)
            raise EntreeInvalide("« %s » : saisissez %s (reçu : « %s »)."
                                 % (nom, plage, valeur),
                                 champ='batterie.coupures.%s' % nom)


def valider_secours(saisie):
    """ACAL786 — la forme des cinq clés, refusée en NOMMANT le champ.

    Rejoue ``reserve_depuis_appareils`` (appareils + durée), ``_fenetres``
    (fenêtres de la commande horaire, avec les listes d'heures posées à côté)
    et ``_part_effacable`` ; leur ``champ`` devient ``batterie.<champ>``
    (``duree_h`` du calcul se saisit ``duree_secours_h``). La forme d'objet et
    les clés inconnues sont jugées avant, par ``valider_batterie``.
    """
    if not isinstance(saisie, dict):
        return
    from .batterie import (
        StrategieInvalide, _fenetres, _part_effacable, reserve_depuis_appareils,
    )
    from .electrique import EntreeInvalide

    _valider_coupures(saisie.get('coupures'))
    try:
        if saisie.get('appareils') is not None:
            if saisie.get('reserve_backup_kwh') not in (None, ''):
                raise StrategieInvalide(MOTIF_RESERVE_EN_DOUBLE,
                                        champ='reserve_backup_kwh')
            reserve_depuis_appareils(saisie.get('appareils'),
                                     duree_h=saisie.get('duree_secours_h'))
        if saisie.get('fenetres') is not None:
            _fenetres(saisie.get('fenetres'), saisie.get('heures_charge'),
                      saisie.get('heures_decharge'))
        _part_effacable(saisie.get('part_effacable_pct'),
                        saisie.get('plafond_effacable_kw'))
    except StrategieInvalide as refus:
        champ = 'duree_secours_h' if refus.champ == 'duree_h' else refus.champ
        raise EntreeInvalide(refus.motif,
                             champ='batterie.%s' % champ) from refus
