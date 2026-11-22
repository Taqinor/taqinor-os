"""ACAL797 — rejouer des coupures de réseau déclarées sur la série de la batterie.

Le réseau n'est JAMAIS absent dans ``services/batterie.py::simuler_batterie`` :
aucun kWh « non fourni » n'y existe. Ce module rejoue, sur la série déjà
dispatchée, une coupure déclarée (``batterie.coupures`` : nombre par an, durée
en heures, heure de début) :

* la date réelle des coupures est INCONNUE (jamais devinée) : la coupure est
  rejouée sur CHAQUE jour de la série dont la fenêtre tient ;
* on part de l'état de charge du dispatch à l'heure de début ;
* pendant la fenêtre le réseau est coupé : le solaire sert d'abord, la
  batterie décharge jusqu'à 0 (au rendement et à la puissance de la fiche —
  la réserve de secours est précisément faite pour cet usage), le surplus la
  recharge ; l'énergie que ni l'un ni l'autre ne sert est « non fournie » ;
* ``energie_non_fournie_kwh`` = nombre de coupures par an × moyenne des jours
  testés (un ATTENDU par an, dit dans la mention).

Fonction pure : le dispatch normal n'est jamais modifié. Aucun litre, aucun
montant.
"""
from __future__ import annotations

import math

from .valeurs import nombre

__all__ = ['rejouer_coupures', 'heures_tenues']

#: Tolérance d'arithmétique flottante (kWh) — jamais un seuil métier.
_EPSILON = 1e-9

#: Le calendrier : un jour = 24 heures.
HEURES_PAR_JOUR = 24

MOTIF_SANS_COUPURES = ('Aucune coupure déclarée : saisissez « batterie.'
                       'coupures » (nombre par an, durée, heure de début).')
MOTIF_HORS_BACKUP = ("Les coupures se rejouent avec la stratégie « backup » : "
                     "« %s » n'a pas de réserve réservée aux coupures.")
MOTIF_NON_HORAIRE = ('Série non horaire : les coupures se rejouent heure par '
                     'heure, la série en a un autre pas. Rejeu OMIS.')
MOTIF_DUREE_TROP_LONGUE = ('La durée de coupure déclarée (%s h) ne tient dans '
                           'aucun jour de la série. Champ à corriger : '
                           '« batterie.coupures.duree_h ».')
MOTIF_SANS_APPAREILS = ('Aucun appareil secouru déclaré (stratégie « backup » '
                        'avec « batterie.appareils ») : aucune durée tenue.')
MENTION = ('Attendu par an : %s coupures × la moyenne de %s jours testés. La '
           'date des coupures est inconnue : chacune est rejouée sur tous les '
           "jours de la série, depuis l'état de charge du dispatch à l'heure "
           'de début.')


def _fenetre(flux, debut, duree, etat, parametres, eta):
    """L'énergie non servie d'UNE fenêtre, du pas ``debut`` sur ``duree`` pas."""
    capacite = parametres['capacite_utile_kwh']
    p_charge = parametres['puissance_charge_kw']
    p_decharge = parametres['puissance_decharge_kw']
    non_servie = 0.0
    for pas in flux[debut:debut + duree]:
        surplus = max(0.0, pas['prod'] - pas['conso'])
        deficit = max(0.0, pas['conso'] - pas['prod'])
        entree = min(surplus, p_charge, max(0.0, capacite - etat) / eta)
        etat += entree * eta
        sortie = min(deficit, p_decharge, max(0.0, etat) * eta)
        etat -= sortie / eta
        non_servie += deficit - sortie
    return max(0.0, non_servie)


def rejouer_coupures(flux, *, coupures, strategie, parametres, etat_initial,
                     heure_de_depart, pas_heures):
    """``(bloc, motif)`` — ``bloc`` = ``{nombre_par_an, duree_h, heure_debut,
    jours_testes, energie_non_fournie_par_coupure_moyenne_kwh,
    energie_non_fournie_par_coupure_pire_kwh, energie_non_fournie_kwh,
    mention}`` ou ``None`` avec son ``motif``.

    Args:
        flux: les pas de ``etapes/batterie.py::_flux_horaires`` (``conso``,
            ``prod``, ``etat`` en kWh).
        coupures: la déclaration ``{nombre_par_an, duree_h, heure_debut}``.
        strategie: la stratégie du dispatch (``backup`` seulement).
        parametres: la banque (``etapes/batterie.py::_banque`` : capacité
            utile, puissances de charge et de décharge en kW, rendement
            aller-retour en %).
        etat_initial: l'état de charge avant le premier pas (kWh).
        heure_de_depart: l'heure du jour du premier pas (0 à 23).
        pas_heures: la durée d'un pas (1,0 seulement).
    """
    if not isinstance(coupures, dict):
        return None, MOTIF_SANS_COUPURES
    if strategie != 'backup':
        return None, MOTIF_HORS_BACKUP % strategie
    if abs(pas_heures - 1.0) > _EPSILON:
        return None, MOTIF_NON_HORAIRE
    lus = [nombre(coupures.get(cle)) for cle in
           ('nombre_par_an', 'duree_h', 'heure_debut')]
    if None in lus:
        return None, MOTIF_SANS_COUPURES
    nombre_par_an, duree, debut_h = (int(valeur) for valeur in lus)
    premier = (debut_h - int(heure_de_depart)) % HEURES_PAR_JOUR
    departs = [rang for rang in range(premier, len(flux), HEURES_PAR_JOUR)
               if rang + duree <= len(flux)]
    if not departs:
        return None, MOTIF_DUREE_TROP_LONGUE % duree
    eta = math.sqrt(nombre(parametres.get('rendement_ar_pct')) / 100.0)
    energies = [_fenetre(flux, rang, duree,
                         flux[rang - 1]['etat'] if rang else etat_initial,
                         parametres, eta)
                for rang in departs]
    moyenne = sum(energies) / len(energies)
    return {
        'nombre_par_an': nombre_par_an,
        'duree_h': duree,
        'heure_debut': debut_h,
        'jours_testes': len(energies),
        'energie_non_fournie_par_coupure_moyenne_kwh': round(moyenne, 3),
        'energie_non_fournie_par_coupure_pire_kwh': round(max(energies), 3),
        'energie_non_fournie_kwh': round(nombre_par_an * moyenne, 3),
        'mention': MENTION % (nombre_par_an, len(energies)),
    }, ''


def heures_tenues(reserve, capacite_utile_kwh):
    """ACAL798 — ``{appareils, energie_disponible_kwh, heures_tenues_ensemble,
    motif_appareils}`` : les heures que tient chaque appareil secouru.

    ``reserve`` : la sortie de ``batterie.reserve_depuis_appareils`` (ou
    ``None`` : sans appareils, ``appareils`` vaut ``None`` avec son motif).
    L'énergie disponible = ``min(réserve, capacité utile)`` ; chaque durée est
    un quotient traçable, jamais un défaut : énergie disponible ÷ (puissance
    continue × quantité), et ``heures_tenues_ensemble`` = énergie disponible ÷
    puissance continue totale.
    """
    vide = {'appareils': None, 'energie_disponible_kwh': None,
            'heures_tenues_ensemble': None,
            'motif_appareils': MOTIF_SANS_APPAREILS}
    if not isinstance(reserve, dict) or not reserve.get('detail'):
        return vide
    disponible = min(nombre(reserve.get('energie_kwh')),
                     nombre(capacite_utile_kwh))
    lignes = [{
        'nom': ligne['nom'], 'quantite': ligne['quantite'],
        'puissance_continue_kw': ligne['puissance_continue_kw'],
        'heures_tenues': round(
            disponible / (ligne['puissance_continue_kw'] * ligne['quantite']),
            2),
    } for ligne in reserve['detail']]
    continue_totale = nombre(reserve.get('puissance_continue_kw'))
    return {'appareils': lignes,
            'energie_disponible_kwh': round(disponible, 3),
            'heures_tenues_ensemble': round(disponible / continue_totale, 2),
            'motif_appareils': ''}
