"""CALX176 — ÉTAPE « indisponibilité » : des fenêtres d'arrêt DATÉES.

LE CONSTAT
----------
``indisponibilite`` était au catalogue en pourcentage plat
(``services/pertes.py``) : un chiffre annuel que RIEN ne reliait à des
périodes réelles. Une semaine d'arrêt en juin et une semaine en décembre y
coûtaient exactement la même chose.

CE QUE CETTE ÉTAPE FAIT
------------------------
La société saisit des FENÊTRES — ``{debut, fin, motif}`` — dans le réglage
``simulation.indisponibilite_fenetres``. Les heures couvertes sont mises à
ZÉRO, et DEUX pourcentages sont publiés CÔTE À CÔTE :

* ``pct_temps``   — la part du TEMPS pendant laquelle l'installation est à
  l'arrêt ;
* ``pct_energie`` — la part de l'ÉNERGIE réellement perdue, qui est la seule
  à entrer dans la cascade.

Les deux diffèrent presque toujours, et c'est exactement ce que PVsyst
avertit : l'énergie perdue calculée ne correspondra pas au temps
d'indisponibilité spécifié
(https://www.pvsyst.com/help/project-design/array-and-system-losses/
unavailability-loss.html). L'avertissement est publié EN FRANÇAIS avec les
deux chiffres, pour que personne ne lise l'un pour l'autre.

CONVENTION DE BORNES
---------------------
``debut`` est INCLUS, ``fin`` est EXCLUE : une fenêtre du 1er au 8 juin
couvre exactement sept jours. Les dates se saisissent en ISO
(``2026-06-01`` ou ``2026-06-01T06``).

CE QUI LA FAIT SE TAIRE
------------------------
* Aucune fenêtre saisie ⇒ étape OMISE. Jamais 1 %, jamais un forfait : une
  installation dont personne n'a daté les arrêts n'a pas « 1 % » d'arrêt,
  elle a des arrêts qu'on n'a pas décrits.
* Une fenêtre illisible, ou dont la fin précède le début ⇒ REFUSÉE en
  citant ses dates.
* Une fenêtre HORS de la plage d'années simulée ⇒ REFUSÉE en citant ses
  dates : la retenir retrancherait une énergie d'une autre année.
* Les points ne portent pas leur date ⇒ omise en nommant les colonnes.

Module PUR : aucune base, aucun réseau.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apps.calepinage.services import etapes as _etapes

#: La clé de réglage société lue ici (registre CALX145).
CLE_REGLAGE = 'indisponibilite_fenetres'

#: Les colonnes de date que chaque point doit porter pour être situé.
COLONNES_DATE = ('annee', 'mois', 'jour', 'heure')

AVERTISSEMENT = (
    "Le pourcentage de TEMPS d'arrêt et le pourcentage d'ÉNERGIE perdue ne "
    "sont pas le même chiffre et ne se remplacent pas : un arrêt d'été coûte "
    "plus qu'un arrêt d'hiver de même durée. Seul le pourcentage d'énergie "
    'entre dans la cascade.')

REFERENCE = (
    "PVsyst — Unavailability loss : l'indisponibilité se définit par une "
    "fraction de temps ou des périodes d'arrêt explicites, le système étant "
    "forcé à l'arrêt sur ces fenêtres, et l'outil avertit que « l'énergie "
    'perdue calculée ne correspondra pas au temps d\'indisponibilité '
    'spécifié » (https://www.pvsyst.com/help/project-design/'
    'array-and-system-losses/unavailability-loss.html).')

LIBELLE = 'Indisponibilité'

__all__ = ['CLE_REGLAGE', 'COLONNES_DATE', 'AVERTISSEMENT', 'REFERENCE',
           'LIBELLE', 'appliquer']


def appliquer(serie, contexte):
    """``(serie, etape)`` — les heures des fenêtres à zéro, ou le silence."""
    contexte = contexte if isinstance(contexte, dict) else {}
    saisie = _etapes.reglage(contexte, CLE_REGLAGE)
    brutes = saisie.get('valeur') if saisie else None
    if not isinstance(brutes, (list, tuple)) or not brutes:
        return serie, _etapes.etape_omise(
            LIBELLE,
            "Aucune fenêtre d'arrêt saisie pour cette installation : "
            "l'indisponibilité se décrit par des périodes datées, jamais par "
            'un pourcentage annuel supposé.',
            champ=f'simulation.{CLE_REGLAGE}')

    repere = _repere(contexte)
    horodatages, colonne_absente = _horodatages(serie, repere)
    if colonne_absente:
        return serie, _etapes.etape_omise(
            LIBELLE,
            'La série horaire ne porte pas la date complète de chacune de ses '
            f'heures ({", ".join(COLONNES_DATE)}) : une fenêtre d\'arrêt ne '
            'peut être rapportée à aucune heure.',
            champ=f'serie_horaire.{colonne_absente}')

    fenetres, motif = _fenetres(brutes, horodatages, repere)
    if fenetres is None:
        return serie, _etapes.etape_omise(
            LIBELLE, motif, champ=f'simulation.{CLE_REGLAGE}')

    rendue, arretees, energie_retiree = _arreter(serie, horodatages, fenetres)
    heures = len(horodatages)
    avant = _etapes.energie_kwh(serie)
    entree = {
        'fenetres': [_publiee(fenetre) for fenetre in fenetres],
        'heures_totales': heures,
        'heures_arretees': arretees,
        'pct_temps': _pct(arretees, heures),
        'pct_energie': _pct(energie_retiree, avant),
        'energie_perdue_kwh': round(energie_retiree, 3),
        'avertissement': AVERTISSEMENT,
        'convention_bornes': 'début INCLUS, fin EXCLUE',
        'source_du_reglage': saisie.get('source'),
    }
    return rendue, _etapes.etape_appliquee(
        LIBELLE, source=saisie.get('source'), entree=entree,
        reference=REFERENCE)


# ── situer chaque heure ────────────────────────────────────────────────

def _repere(contexte):
    """Le fuseau partagé par les heures de la série ET les fenêtres saisies.

    La série entre ré-indexée sur l'heure légale du site (CALX143) et les
    fenêtres d'arrêt se saisissent dans ce même repère : les deux côtés
    portent donc le fuseau saisi du site. Fuseau absent ou inconnu ⇒ repère
    UTC nominal, partagé par les deux côtés — seule la comparaison importe,
    aucune conversion n'est faite.
    """
    fuseau = ((contexte.get('site') or {}) if isinstance(contexte, dict)
              else {}).get('fuseau')
    if isinstance(fuseau, str) and fuseau.strip():
        try:
            return ZoneInfo(fuseau.strip())
        except (KeyError, ValueError, OSError):
            pass
    return timezone.utc


def _horodatages(serie, repere):
    """``([datetime | None, ...], colonne_absente)`` pour chaque point."""
    horodatages = []
    for point in (serie or {}).get('points') or ():
        if not isinstance(point, dict):
            horodatages.append(None)
            continue
        valeurs = {}
        for colonne in COLONNES_DATE:
            nombre = _entier(point.get(colonne))
            if nombre is None:
                return horodatages, colonne
            valeurs[colonne] = nombre
        try:
            horodatages.append(datetime(valeurs['annee'], valeurs['mois'],
                                        valeurs['jour'], valeurs['heure'],
                                        tzinfo=repere))
        except ValueError:
            return horodatages, 'jour'
    return horodatages, ''


def _entier(valeur):
    if isinstance(valeur, bool):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


# ── lire les fenêtres, et refuser celles qui ne tiennent pas ───────────

def _fenetres(brutes, horodatages, repere):
    """``(fenetres, '')`` ou ``(None, motif)`` — chaque refus CITE ses dates."""
    connus = [instant for instant in horodatages if instant is not None]
    if not connus:
        return None, ('La série horaire ne porte aucune heure datée : aucune '
                      "fenêtre d'arrêt ne peut y être rapportée.")
    premiere, derniere = min(connus).year, max(connus).year

    fenetres = []
    for rang, brute in enumerate(brutes, start=1):
        if not isinstance(brute, dict):
            return None, (f'La fenêtre d\'arrêt n° {rang} n\'est pas un objet '
                          '{debut, fin, motif}.')
        debut = _instant(brute.get('debut'), repere)
        fin = _instant(brute.get('fin'), repere)
        if debut is None or fin is None:
            return None, (
                f'La fenêtre d\'arrêt n° {rang} porte des dates illisibles '
                f'(début : {brute.get("debut")!r}, fin : {brute.get("fin")!r})'
                ' : une date se saisit en ISO, par exemple « 2026-06-01 ».')
        if fin <= debut:
            return None, (
                f'La fenêtre d\'arrêt « {_texte(debut)} → {_texte(fin)} » est '
                'refusée : sa fin ne suit pas son début.')
        if fin.year < premiere or debut.year > derniere:
            return None, (
                f'La fenêtre d\'arrêt « {_texte(debut)} → {_texte(fin)} » est '
                f'refusée : elle tombe hors de la plage simulée '
                f'({premiere}-{derniere}). La retenir retrancherait une '
                "énergie d'une autre année.")
        fenetres.append({'debut': debut, 'fin': fin,
                         'motif': (brute.get('motif') or '').strip()})
    return fenetres, ''


def _instant(valeur, repere):
    """Un horodatage ISO — date seule ou date et heure — ou ``None``."""
    if not isinstance(valeur, str) or not valeur.strip():
        return None
    texte = valeur.strip().replace('/', '-')
    for forme in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%dT%H',
                  '%Y-%m-%d %H:%M', '%Y-%m-%d %H', '%Y-%m-%d'):
        try:
            return datetime.strptime(texte, forme).replace(tzinfo=repere)
        except ValueError:
            continue
    return None


def _texte(instant):
    return instant.strftime('%Y-%m-%d %H:%M')


def _publiee(fenetre):
    return {'debut': _texte(fenetre['debut']), 'fin': _texte(fenetre['fin']),
            'motif': fenetre['motif']}


# ── forcer l'arrêt ─────────────────────────────────────────────────────

def _arreter(serie, horodatages, fenetres):
    """Copie PURE : les heures couvertes à zéro, et l'énergie retirée."""
    colonne = _etapes.colonne_energie(serie)
    pas_minutes = serie.get('pas_minutes') or _etapes.PAS_MINUTES_PVGIS
    heures_du_pas = float(pas_minutes) / 60.0
    facteur = _etapes.FACTEURS_KW[colonne] if colonne else 0.0
    rendus = []
    arretees = 0
    energie = 0.0
    for rang, point in enumerate((serie or {}).get('points') or ()):
        if not isinstance(point, dict):
            rendus.append(point)
            continue
        instant = horodatages[rang] if rang < len(horodatages) else None
        if instant is None or not _couverte(instant, fenetres):
            rendus.append(point)
            continue
        arretees += 1
        copie = dict(point)
        if colonne is not None:
            brut = copie.get(colonne)
            if brut is not None and not isinstance(brut, bool):
                try:
                    energie += float(brut) * facteur * heures_du_pas
                except (TypeError, ValueError):
                    pass
            copie[colonne] = 0.0
        rendus.append(copie)
    rendue = dict(serie)
    rendue['points'] = rendus
    if colonne is not None:
        rendue['colonne_energie'] = colonne
    return rendue, arretees, energie


def _couverte(instant, fenetres):
    for fenetre in fenetres:
        if fenetre['debut'] <= instant < fenetre['fin']:
            return True
    return False


def _pct(part, total):
    if not total:
        return None
    return round(100.0 * part / total, 3)
