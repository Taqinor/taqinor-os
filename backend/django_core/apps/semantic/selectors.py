"""NTDATA41/42 — LECTURES DÉRIVÉES d'une métrique nommée : séries et variation.

Une métrique (NTDATA7/8) rend UN nombre. Deux usages en demandent la
TRAJECTOIRE :

  * l'alerte de VARIATION (NTDATA41) — « le MRR a-t-il chuté de plus de 20 %
    par rapport au mois précédent ? » ;
  * la détection d'ANOMALIE (NTDATA42) — « ce mois-ci est-il aberrant face aux
    douze précédents ? ».

Les deux ont besoin de la même chose : la série de la métrique, période par
période. Elle est calculée ICI, une fois, par le résolveur existant
(``services.resolve_metric`` avec un ``group_by`` sur l'axe de TEMPS déclaré
par le dataset) — jamais par une seconde requête qui dériverait.

DEUX RÈGLES QUI NE SE NÉGOCIENT PAS
-----------------------------------

1. **UNE PÉRIODE SANS VALEUR EST OMISE, jamais lue comme zéro.** ``SUM`` d'un
   ensemble vide vaut ``NULL`` : un mois sans facture n'est pas « 0 MAD de
   chiffre d'affaires mesuré », c'est « rien à mesurer ». Le compter 0 ferait
   voir une chute de 100 % là où il n'y a eu aucune activité enregistrée.

2. **LA PÉRIODE COURANTE EST EXCLUE des comparaisons.** Le 3 du mois, le mois
   en cours contient trois jours : le comparer au mois précédent COMPLET
   affiche mécaniquement une chute de ~90 % et déclencherait une alerte tous
   les débuts de mois. La variation se lit donc entre les DEUX DERNIÈRES
   PÉRIODES COMPLÈTES.
"""
from __future__ import annotations

import datetime

from . import services


def champ_temps(cle_dataset):
    """Le premier champ de type ``temps`` du dataset, ou ``None``.

    ``None`` (dataset absent du registre, ou sans axe de temps déclaré)
    signifie « cette métrique n'a pas de trajectoire lisible » — l'appelant
    renonce, il ne devine pas un champ de date.
    """
    from core import data_explorer

    try:
        schema = data_explorer.describe_dataset(cle_dataset)
    except data_explorer.DatasetInconnu:
        return None
    temps = schema.get('temps') or []
    return temps[0] if temps else None


def _cle_periode(valeur):
    """``(annee, mois)`` d'une borne de période, ou ``None`` si illisible.

    Les datasets rendent leur axe de temps via ``TruncMonth`` (une ``date``) ;
    certains rendent une chaîne ``AAAA-MM``. On accepte les deux et on refuse
    tout le reste plutôt que de deviner.
    """
    if isinstance(valeur, datetime.datetime):
        return (valeur.year, valeur.month)
    if isinstance(valeur, datetime.date):
        return (valeur.year, valeur.month)
    texte = str(valeur or '')
    if len(texte) >= 7 and texte[4] == '-':
        try:
            return (int(texte[:4]), int(texte[5:7]))
        except ValueError:
            return None
    return None


def serie_temporelle(company, user, cle, *, champ=None, filters=None):
    """La série de la métrique ``cle``, période par période, triée.

    Renvoie ``[{'periode': …, 'valeur': …}, …]``. Les périodes SANS valeur
    sont OMISES (voir l'en-tête du module). Une métrique inconnue, inactive,
    d'adaptateur (un scalaire n'a pas de dimensions) ou sur un dataset sans axe
    de temps renvoie une liste VIDE — jamais une série fabriquée.
    """
    try:
        definition = services.get_metric(company, cle)
    except services.MetriqueInconnue:
        return []
    if definition.est_adaptateur:
        return []
    axe = champ or champ_temps(definition.dataset)
    if not axe:
        return []
    try:
        resultat = services.resolve_metric(
            company, user, cle, group_by=[axe], filters=filters)
    except services.MetriqueNonResolvable:
        return []

    points = []
    for ligne in resultat.get('lignes') or []:
        valeur = ligne.get(services.ALIAS_VALEUR)
        periode = ligne.get(axe)
        if valeur is None or _cle_periode(periode) is None:
            continue
        points.append({'periode': periode, 'valeur': valeur})
    points.sort(key=lambda point: _cle_periode(point['periode']))
    return points


def _est_periode_courante(periode, aujourdhui):
    cle = _cle_periode(periode)
    return cle == (aujourdhui.year, aujourdhui.month)


def periodes_completes(points, aujourdhui=None):
    """La série PRIVÉE de sa période courante (incomplète par construction)."""
    if aujourdhui is None:
        from django.utils import timezone
        aujourdhui = timezone.localdate()
    return [point for point in points
            if not _est_periode_courante(point['periode'], aujourdhui)]


def variation_pct(company, user, cle, *, aujourdhui=None, filters=None):
    """Δ % entre les DEUX DERNIÈRES périodes COMPLÈTES de la métrique.

    Renvoie ``(pourcentage, courante, precedente)``, ou ``(None, …)`` quand la
    variation n'est pas CALCULABLE — et ce n'est jamais 0 :

    * moins de deux périodes complètes : il n'y a rien à comparer ;
    * période précédente à ZÉRO : la variation relative n'existe pas
      (« +∞ % » n'est pas un nombre à comparer à un seuil).

    Une valeur non calculable ne déclenche donc AUCUNE alerte, au lieu de faire
    passer une absence de mesure pour une stabilité.
    """
    points = periodes_completes(
        serie_temporelle(company, user, cle, filters=filters), aujourdhui)
    if len(points) < 2:
        return None, None, None
    precedente = float(points[-2]['valeur'])
    courante = float(points[-1]['valeur'])
    if precedente == 0:
        return None, courante, precedente
    return ((courante - precedente) / abs(precedente) * 100.0,
            courante, precedente)
