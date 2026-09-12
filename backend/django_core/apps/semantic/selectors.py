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


# ── NTDATA43 — LIGNAGE : « d'où vient ce chiffre » ─────────────────────────
#
# Une métrique gouvernée ne vaut que si un utilisateur métier peut vérifier
# d'où sort son nombre SANS lire de code. Le lignage rend l'arbre complet :
# la métrique → son ou ses datasets source → l'APP qui les possède → les
# filtres réellement appliqués → le nombre de lignes agrégées → la version de
# définition en vigueur (NTDATA9).
#
# TOUT Y EST DÉRIVÉ, RIEN N'Y EST DÉCLARÉ À LA MAIN. L'app propriétaire d'un
# dataset se lit du MODULE qui a enregistré son fournisseur — aucune table de
# correspondance à tenir à jour, donc aucune dérive possible entre le lignage
# affiché et la réalité.
#
# CE QUI N'EST PAS EXPRIMABLE EST OMIS. Une métrique d'ADAPTATEUR (NTDATA11 :
# le DSO du grand livre, le pipeline pondéré lead par lead) n'est pas une
# requête : elle n'a ni dataset ni « nombre de lignes agrégées ». On rend alors
# `None` et on NOMME l'adaptateur, plutôt que d'inventer un compte de lignes
# qui ne correspondrait à rien.


def _app_proprietaire(nom_dataset):
    """L'app qui a ENREGISTRÉ ce dataset, déduite de son fournisseur.

    ``apps.ventes.bi_datasets`` → ``ventes``. ``''`` si le dataset n'est pas
    (ou plus) enregistré : un module désactivé ne doit pas faire échouer la
    lecture du lignage.
    """
    from core import data_explorer

    try:
        dataset = data_explorer.get_dataset(nom_dataset)
    except data_explorer.DatasetInconnu:
        return ''
    module = getattr(dataset.get('provider'), '__module__', '') or ''
    morceaux = module.split('.')
    if len(morceaux) >= 2 and morceaux[0] == 'apps':
        return morceaux[1]
    return morceaux[0] if morceaux else ''


def _champs_du_calcul(definition):
    """Les champs du dataset que la mesure LIT réellement (ordre stable)."""
    mesure = definition.mesure if isinstance(definition.mesure, dict) else {}
    champs = []
    if mesure.get('formula'):
        for agregat in (mesure.get('aggregates') or []):
            champ = (agregat or {}).get('field')
            if champ and champ not in champs:
                champs.append(champ)
    elif mesure.get('field'):
        champs.append(mesure['field'])
    for cle_filtre in sorted((definition.filtres or {}) or {}):
        # Un filtre peut porter un suffixe de lookup (`mois__gte`) : la
        # COLONNE lue est sa racine.
        racine = str(cle_filtre).split('__')[0]
        if racine and racine not in champs:
            champs.append(racine)
    return champs


def _description_du_calcul(definition):
    """Ce que la métrique CALCULE, en une structure lisible."""
    mesure = definition.mesure if isinstance(definition.mesure, dict) else {}
    if definition.est_adaptateur:
        return {'type': 'adaptateur', 'adaptateur': mesure.get('adapter')}
    if definition.est_formule:
        return {
            'type': 'formule',
            'expression': mesure.get('formula'),
            'agregats': [
                {'alias': (a or {}).get('alias'),
                 'fonction': (a or {}).get('fn'),
                 'champ': (a or {}).get('field')}
                for a in (mesure.get('aggregates') or [])
            ],
        }
    return {'type': 'agregat_simple', 'fonction': mesure.get('agg'),
            'champ': mesure.get('field')}


def _nb_lignes_agregees(company, user, definition):
    """Combien de lignes la métrique agrège, ou ``None`` si inexprimable.

    ``None`` — et jamais 0 — quand la métrique passe par un adaptateur (ce
    n'est pas une requête), quand son dataset n'est plus enregistré, ou quand
    un champ de sa population n'est pas lisible par ce lecteur : « je ne sais
    pas » n'est pas « aucune ligne ».
    """
    from core import data_explorer

    if definition.est_adaptateur or not definition.dataset:
        return None
    try:
        lignes = data_explorer.run_query(
            definition.dataset, company, user,
            {'filters': dict(definition.filtres or {}),
             'aggregates': [{'alias': 'nb', 'fn': 'count', 'field': 'id'}]})
    except Exception:  # noqa: BLE001 — le lignage ne doit jamais lever
        return None
    if not lignes:
        return None
    return lignes[0].get('nb')


def lineage(company, cle, *, user=None):
    """NTDATA43 — l'arbre complet « d'où vient ce chiffre » pour une métrique.

    Lève ``services.MetriqueInconnue`` si aucune métrique ACTIVE ne porte cette
    clé dans cette société — c'est un 404 côté HTTP, pas un arbre vide.
    """
    definition = services.get_metric(company, cle)
    sources = []
    if definition.dataset:
        from core import data_explorer
        try:
            schema = data_explorer.describe_dataset(definition.dataset, user)
            label = schema.get('label') or definition.dataset
        except data_explorer.DatasetInconnu:
            label = definition.dataset
        sources.append({
            'dataset': definition.dataset,
            'label': label,
            'app': _app_proprietaire(definition.dataset),
            'champs_utilises': _champs_du_calcul(definition),
        })

    derniere = services.versions_metrique(definition).first()
    return {
        'metrique': definition.cle,
        'libelle': definition.libelle,
        'description': definition.description,
        'unite': definition.unite,
        'format': definition.format,
        'calcul': _description_du_calcul(definition),
        'sources': sources,
        'filtres': dict(definition.filtres or {}),
        'nb_lignes_agregees': _nb_lignes_agregees(company, user, definition),
        'version': ({
            'version': derniere.version,
            'figee_le': derniere.date_creation.isoformat(),
            'auteur': (getattr(derniere.auteur, 'username', '')
                       if derniere.auteur_id else ''),
        } if derniere is not None else None),
    }


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
