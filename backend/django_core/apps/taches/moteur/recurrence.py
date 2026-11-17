"""Récurrence pure (reference/regles.md §2) — sans base, sans horloge, sans réseau.

Le jour de référence, la date du « fait » et la fonction `est_ouvre` sont des
PARAMÈTRES : rien ici ne lit l'heure ni l'ORM. `est_ouvre(d)` est injecté (en
production : jour ouvré de la société, bitmask + fériés) ; seule la fréquence
`jours_ouvres` le consulte.

Les fonctions lisent une règle par ATTRIBUTS (`frequence`, `intervalle`,
`jours_semaine`, `jour_du_mois`, `rang_dans_mois`, `mode`, `date_debut`,
`date_fin`, `actif`) : `RegleRecurrencePure` ci-dessous, ou le modèle
`RegleRecurrence`, donnent le même résultat.
"""
import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from apps.taches.choix import Frequence, ModeRecurrence
from apps.taches.saisie.dates_pures import (
    ajouter_mois_borne, fin_de_mois, prochain_jour_semaine)

_MAX_JOURS_OUVRES = 400  # garde-fou : aucun jour ouvré en 400 jours = série vide
_NOMS_JOURS = ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche')
_RANGS = {1: 'premier', 2: 'deuxième', 3: 'troisième', 4: 'quatrième', -1: 'dernier'}


@dataclass(frozen=True)
class RegleRecurrencePure:
    """Règle de récurrence construite à la main (tests) ou par l'analyseur."""
    frequence: str
    date_debut: date
    intervalle: int = 1
    jours_semaine: str = '0000000'
    jour_du_mois: 'int | None' = None
    rang_dans_mois: 'int | None' = None
    mode: str = ModeRecurrence.CALENDRIER
    date_fin: 'date | None' = None
    actif: bool = True


def _lundi_a_vendredi(d):
    """`est_ouvre` par défaut : lundi à vendredi, sans fériés."""
    return d.weekday() < 5


def _jours_du_masque(masque):
    """Indices (0 = lundi) des jours retenus dans un masque `'1001000'`."""
    return [i for i, c in enumerate(masque or '') if c == '1']


def n_ieme_jour_du_mois(annee, mois, jour_semaine, rang):
    """N-ième `jour_semaine` (0 = lundi) du mois ; `rang` 1-4, −1 = le dernier."""
    if rang == -1:
        dernier = fin_de_mois(date(annee, mois, 1))
        return dernier - timedelta(days=(dernier.weekday() - jour_semaine) % 7)
    premier = prochain_jour_semaine(date(annee, mois, 1), jour_semaine, inclure=True)
    return premier + timedelta(weeks=rang - 1)


def _date_du_mois(regle, annee, mois):
    """La date de la série dans ce mois (quantième borné, ou N-ième jour de semaine)."""
    dernier = calendar.monthrange(annee, mois)[1]
    jours = _jours_du_masque(regle.jours_semaine)
    if regle.rang_dans_mois and len(jours) == 1:
        return n_ieme_jour_du_mois(annee, mois, jours[0], regle.rang_dans_mois)
    jour = regle.jour_du_mois
    if jour is None:
        jour = regle.date_debut.day
    if jour == -1:
        jour = dernier
    return date(annee, mois, min(jour, dernier))


def _date_annuelle(debut, annee):
    """Jour et mois de `debut` dans `annee` ; 29/02 → 28/02 hors année bissextile."""
    jour = min(debut.day, calendar.monthrange(annee, debut.month)[1])
    return date(annee, debut.month, jour)


def _quotidien(regle, depuis, est_ouvre):
    n = max(1, regle.intervalle)
    ecart = (depuis - regle.date_debut).days
    return regle.date_debut + timedelta(days=-(-ecart // n) * n)


def _jours_ouvres(regle, depuis, est_ouvre):
    d = depuis
    for _ in range(_MAX_JOURS_OUVRES):
        if est_ouvre(d):
            return d
        d += timedelta(days=1)
    return None


def _hebdo(regle, depuis, est_ouvre):
    n = max(1, regle.intervalle)
    masque = regle.jours_semaine
    if '1' not in (masque or ''):
        masque = ''.join('1' if i == regle.date_debut.weekday() else '0' for i in range(7))
    lundi_debut = regle.date_debut - timedelta(days=regle.date_debut.weekday())
    d = depuis
    for _ in range(7 * n + 7):
        lundi = d - timedelta(days=d.weekday())
        semaine = (lundi - lundi_debut).days // 7
        if masque[d.weekday()] == '1' and semaine % n == 0:
            return d
        d += timedelta(days=1)
    return None


def _mensuel(regle, depuis, est_ouvre):
    debut, n = regle.date_debut, max(1, regle.intervalle)
    ecart = (depuis.year * 12 + depuis.month) - (debut.year * 12 + debut.month)
    k = max(0, -(-ecart // n))
    for _ in range(3):
        annee, mois0 = divmod(debut.year * 12 + debut.month - 1 + k * n, 12)
        d = _date_du_mois(regle, annee, mois0 + 1)
        if d >= depuis:
            return d
        k += 1
    return None


def _annuel(regle, depuis, est_ouvre):
    debut, n = regle.date_debut, max(1, regle.intervalle)
    annee = depuis.year
    for _ in range(n + 2):
        if (annee - debut.year) % n == 0 and annee >= debut.year:
            d = _date_annuelle(debut, annee)
            if d >= depuis:
                return d
        annee += 1
    return None


_SERIES = {
    Frequence.QUOTIDIEN.value: _quotidien,
    Frequence.JOURS_OUVRES.value: _jours_ouvres,
    Frequence.HEBDO.value: _hebdo,
    Frequence.MENSUEL.value: _mensuel,
    Frequence.ANNUEL.value: _annuel,
}


def _premier_membre(regle, depuis, est_ouvre):
    """Première date de la série ≥ `depuis` (et ≥ `date_debut`), ou None."""
    serie = _SERIES.get(str(getattr(regle.frequence, 'value', regle.frequence)))
    if serie is None:
        return None
    return serie(regle, max(depuis, regle.date_debut), est_ouvre)


def _jours_ouvres_apres(fait, n, est_ouvre):
    d, restant = fait, max(1, n)
    for _ in range(_MAX_JOURS_OUVRES * max(1, n)):
        d += timedelta(days=1)
        if est_ouvre(d):
            restant -= 1
            if restant == 0:
                return d
    return None


def _hebdo_apres_fait(regle, fait):
    """Premier jour du masque ≥ fait + 7n − 6 (IR8)."""
    n = max(1, regle.intervalle)
    masque = regle.jours_semaine
    if '1' not in (masque or ''):
        masque = ''.join('1' if i == fait.weekday() else '0' for i in range(7))
    d = fait + timedelta(days=7 * n - 6)
    for _ in range(7):
        if masque[d.weekday()] == '1':
            return d
        d += timedelta(days=1)
    return None


def _apres_fait(regle, fait, est_ouvre):
    """Occurrence suivante d'une règle « après avoir fait » (depuis la date locale du fait)."""
    n = max(1, regle.intervalle)
    f = regle.frequence
    if f == Frequence.QUOTIDIEN:
        return fait + timedelta(days=n)
    if f == Frequence.JOURS_OUVRES:
        return _jours_ouvres_apres(fait, n, est_ouvre)
    if f == Frequence.HEBDO:
        return _hebdo_apres_fait(regle, fait)
    if f == Frequence.MENSUEL:
        return ajouter_mois_borne(fait, n)
    if f == Frequence.ANNUEL:
        return ajouter_mois_borne(fait, 12 * n)
    return None


def _borner(regle, d):
    """None au-delà de `date_fin` (la série est close)."""
    if d is not None and regle.date_fin is not None and d > regle.date_fin:
        return None
    return d


def _en_date(valeur):
    if isinstance(valeur, datetime):
        return valeur.date()
    return valeur


def premiere_occurrence(regle, est_ouvre=None):
    """Première date de la série ≥ `date_debut` (`apres_fait` : `date_debut` elle-même)."""
    est_ouvre = est_ouvre or _lundi_a_vendredi
    if regle.mode == ModeRecurrence.APRES_FAIT:
        return _borner(regle, regle.date_debut)
    return _borner(regle, _premier_membre(regle, regle.date_debut, est_ouvre))


def prochaine_occurrence(regle, occurrence_du, aujourdhui, fait_le=None, est_ouvre=None):
    """Occurrence suivante, ou None (série arrêtée ou close).

    `calendrier` : première date de la série STRICTEMENT après
    max(`occurrence_du`, `aujourdhui`) — avance, retard, saut : jamais de pile.
    `apres_fait` : depuis la date locale de `fait_le` (datetime déjà en heure
    locale, ou date ; à défaut `aujourdhui`).
    """
    if not regle.actif:
        return None
    est_ouvre = est_ouvre or _lundi_a_vendredi
    if regle.mode == ModeRecurrence.APRES_FAIT:
        fait = _en_date(fait_le) or aujourdhui
        return _borner(regle, _apres_fait(regle, fait, est_ouvre))
    base = max(d for d in (_en_date(occurrence_du), aujourdhui) if d is not None)
    return _borner(regle, _premier_membre(regle, base + timedelta(days=1), est_ouvre))


def est_routine(regle):
    """Routine (compte du rythme 0, puce « routine ») : quotidien ou jours ouvrés, tous les 1."""
    return (regle.frequence in (Frequence.QUOTIDIEN, Frequence.JOURS_OUVRES)
            and regle.intervalle == 1)


def _liste_francaise(noms):
    if len(noms) <= 1:
        return ''.join(noms)
    return ', '.join(noms[:-1]) + ' et ' + noms[-1]


def _libelle_hebdo(regle):
    jours = [_NOMS_JOURS[i] for i in _jours_du_masque(regle.jours_semaine)]
    if not jours:
        jours = [_NOMS_JOURS[regle.date_debut.weekday()]]
    if regle.intervalle > 1:
        return f'toutes les {regle.intervalle} semaines le {_liste_francaise(jours)}'
    return f'chaque {_liste_francaise(jours)}'


def _libelle_mensuel(regle):
    if regle.intervalle > 1:
        return f'tous les {regle.intervalle} mois'
    jours = _jours_du_masque(regle.jours_semaine)
    if regle.rang_dans_mois and len(jours) == 1:
        return f'chaque {_RANGS[regle.rang_dans_mois]} {_NOMS_JOURS[jours[0]]} du mois'
    if regle.jour_du_mois == -1:
        return 'chaque fin de mois'
    if regle.jour_du_mois:
        return f'chaque mois le {regle.jour_du_mois}'
    return 'chaque mois'


def _libelle_annuel(regle):
    jour = f'{regle.date_debut.day:02d}/{regle.date_debut.month:02d}'
    if regle.intervalle > 1:
        return f'tous les {regle.intervalle} ans le {jour}'
    return f'chaque année le {jour}'


def _libelle_base(regle):
    n, f = regle.intervalle, regle.frequence
    if f == Frequence.QUOTIDIEN:
        return 'chaque jour' if n == 1 else f'tous les {n} jours'
    if f == Frequence.JOURS_OUVRES:
        return 'chaque jour travaillé' if n == 1 else f'tous les {n} jours travaillés'
    if f == Frequence.HEBDO:
        return _libelle_hebdo(regle)
    if f == Frequence.MENSUEL:
        return _libelle_mensuel(regle)
    return _libelle_annuel(regle)


def libelle_regle(regle):
    """Libellé français de la règle (reference/textes.md §2.10)."""
    texte = _libelle_base(regle)
    if regle.mode == ModeRecurrence.APRES_FAIT:
        texte += ' après fait'
    if regle.date_fin is not None:
        fin = regle.date_fin
        texte += f" jusqu'au {fin.day:02d}/{fin.month:02d}/{fin.year}"
    return texte
