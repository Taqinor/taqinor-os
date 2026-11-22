"""ACAL793 — quatre FAITS tirés de la série horaire de la batterie.

``etapes/batterie.py::_publier`` écrit l'état de charge pas par pas mais ne
disait rien de ce qu'il montre : la batterie se remplit-elle, se vide-t-elle
avant l'aube, combien de surplus part encore au réseau, et quel serait
l'autoconsommation SANS elle (« avant d'ajouter une batterie, regarde si tu
consommes déjà ta production »). Ce module les COMPTE sur les flux du
dispatch, sans aucun mot de verdict (ACAL794) ni montant :

* un jour = 24 heures de pas consécutifs depuis le début de la série ;
* ``jours_pleine`` : jours où l'état de charge atteint la capacité utile ;
* une nuit = le plus long tronçon contigu de pas SANS production d'un jour,
  « au plancher » si l'état de charge à sa fin est au plus le plancher
  (réserve de secours en ``backup``, sinon 0) ;
* ``part_surplus_injecte`` = export ÷ (production − autoconsommation directe) ;
* ``taux_autoconsommation_sans_batterie`` = celui de
  ``services/autoconsommation.py::bilan_autoconsommation`` (même moteur) sur
  la production AVANT batterie.

Fractions de 0 à 1, ``None`` si le dénominateur est nul ; jours et nuits
ramenés à l'année moyenne de la fenêtre (``annees``).
"""
from __future__ import annotations

__all__ = ['faits_de_la_serie', 'plancher_du_dispatch',
           'verdict_de_la_batterie', 'CLE_SEUIL_NUITS', 'CLE_SEUIL_JOURS']

#: ACAL794 — les deux réglages société (section « simulation ») qui fondent le
#: mot de verdict ; aucun n'a de valeur par défaut (D-CALX 7).
CLE_SEUIL_NUITS = 'batterie_seuil_nuits_pct'
CLE_SEUIL_JOURS = 'batterie_seuil_jours_pleine_pct'

#: Tolérance d'arithmétique flottante (kWh) — jamais un seuil métier.
_EPSILON = 1e-9

#: La durée d'un jour, en heures (le calendrier, pas une hypothèse).
HEURES_PAR_JOUR = 24.0


def plancher_du_dispatch(dispatch, strategie):
    """Le plancher d'état de charge (kWh) : la réserve de secours RETENUE par
    le dispatch en ``backup``, sinon 0 (aucune réserve n'est supposée)."""
    from .valeurs import nombre

    if strategie != 'backup':
        return 0.0
    parametres = (dispatch or {}).get('parametres') or {}
    return nombre(parametres.get('reserve_backup_kwh')) or 0.0


def _plus_longue_nuit(jour):
    """L'indice du DERNIER pas du plus long tronçon sans production, ou None."""
    meilleur, fin, longueur = 0, None, 0
    for rang, pas in enumerate(jour):
        longueur = longueur + 1 if pas['prod'] <= _EPSILON else 0
        if longueur > meilleur:
            meilleur, fin = longueur, rang
    return fin


def _fraction(numerateur, denominateur):
    if denominateur <= _EPSILON:
        return None
    return round(numerateur / denominateur, 4)


def faits_de_la_serie(flux, *, capacite, plancher=0.0, pas_heures=1.0,
                      annees=1):
    """Les quatre faits (et le nombre de jours) d'une série de flux.

    Args:
        flux: les pas de ``etapes/batterie.py::_flux_horaires`` (``conso``,
            ``prod``, ``direct``, ``export``, ``etat`` en kWh).
        capacite: la capacité utile de la banque (kWh).
        plancher: l'état de charge le plus bas permis (kWh).
        pas_heures: la durée d'un pas.
        annees: le N de la fenêtre météo.
    """
    from .autoconsommation import bilan_autoconsommation

    annees = annees if annees and annees > 1 else 1
    par_jour = max(1, int(round(HEURES_PAR_JOUR / pas_heures)))
    jours = [flux[debut:debut + par_jour]
             for debut in range(0, len(flux), par_jour)]
    pleines = sum(1 for jour in jours
                  if max(pas['etat'] for pas in jour) >= capacite - _EPSILON)
    au_plancher = 0
    for jour in jours:
        fin = _plus_longue_nuit(jour)
        if fin is not None and jour[fin]['etat'] <= plancher + _EPSILON:
            au_plancher += 1
    production = sum(pas['prod'] for pas in flux)
    direct = sum(pas['direct'] for pas in flux)
    sans_batterie = bilan_autoconsommation(
        [pas['conso'] for pas in flux], [pas['prod'] for pas in flux],
        pas_heures=pas_heures)
    return {
        'jours_total': round(len(jours) / annees, 1),
        'jours_pleine': round(pleines / annees, 1),
        'nuits_au_plancher': round(au_plancher / annees, 1),
        'part_surplus_injecte': _fraction(
            sum(pas['export'] for pas in flux), production - direct),
        'taux_autoconsommation_sans_batterie': (
            sans_batterie['taux_autoconsommation']),
    }


def verdict_de_la_batterie(faits, seuil_nuits, seuil_jours):
    """``(verdict, motif)`` — « trop_petite », « trop_grande » ou « adaptee ».

    ``seuil_nuits`` / ``seuil_jours`` : les réglages société ``{valeur,
    source, reference}`` (pourcentages) ou ``None``. Sans l'un des deux, ou
    sans jours dans la série, ``verdict`` vaut ``None`` et ``motif`` nomme ce
    qui manque. Les parts sont celles des faits de la série (ACAL793) :
    nuits au plancher ÷ jours, jours pleine ÷ jours.
    """
    from .valeurs import nombre

    manquantes = [cle for cle, seuil in ((CLE_SEUIL_NUITS, seuil_nuits),
                                         (CLE_SEUIL_JOURS, seuil_jours))
                  if nombre((seuil or {}).get('valeur')) is None]
    if manquantes:
        return None, ('Verdict non rendu : réglage société non saisi (%s).'
                      % ', '.join(manquantes))
    jours = nombre((faits or {}).get('jours_total'))
    if not jours or jours <= 0.0:
        return None, 'Verdict non rendu : la série ne couvre aucun jour.'
    part_nuits = nombre(faits.get('nuits_au_plancher')) / jours * 100.0
    part_pleine = nombre(faits.get('jours_pleine')) / jours * 100.0
    if part_nuits >= nombre(seuil_nuits['valeur']):
        mot = 'trop_petite'
    elif part_pleine <= nombre(seuil_jours['valeur']):
        mot = 'trop_grande'
    else:
        mot = 'adaptee'
    return {'mot': mot, 'seuils_utilises': {
        CLE_SEUIL_NUITS: seuil_nuits, CLE_SEUIL_JOURS: seuil_jours}}, ''
