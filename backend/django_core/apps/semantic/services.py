"""NTDATA8 — LE RÉSOLVEUR : une définition de métrique → une valeur réelle.

``resolve_metric(company, user, cle, ...)`` est la SEULE porte : elle traduit
une :class:`~apps.semantic.models.MetricDefinition` en une requête
``core.data_explorer.run_query`` et renvoie la valeur (ou la série, si un
regroupement est demandé).

DEUX CHEMINS, choisis par la définition elle-même :

* MESURE SIMPLE — ``{"field": …, "agg": …}`` devient UN agrégat aliasé
  ``valeur``.
* MESURE FORMULE — ``{"formula": "ca / nb", "aggregates": [...]}`` devient les
  agrégats bruts nommés + une ``formula_measure`` ``valeur`` évaluée par
  ``core.formula`` (AST, jamais ``eval``). C'est exactement le patron de
  ``core.pivot`` ``extra_measures`` : on ne réinvente pas une seconde chaîne
  de calcul.

RIEN N'EST INVENTÉ. La valeur vient du dataset de l'app propriétaire, déjà
scopé société. Une DIVISION PAR ZÉRO rend ``None`` — jamais zéro (qui serait
un chiffre faux) et jamais une exception qui casserait le tableau de bord
entier. Un champ sous permission que le lecteur ne peut pas voir est écarté
par le moteur (AUD801) : la métrique rend alors une valeur VIDE plutôt que de
divulguer.

LECTURE PURE : aucune écriture, aucun statut changé, aucun import de modèle
d'app métier (le dataset est désigné par son NOM).
"""
from __future__ import annotations

#: Alias sous lequel la valeur de la métrique est toujours rendue.
ALIAS_VALEUR = 'valeur'


class MetriqueInconnue(Exception):
    """Aucune métrique ACTIVE ne porte cette clé dans cette société."""


class MetriqueNonResolvable(Exception):
    """La définition existe mais ne peut pas être exécutée telle quelle.

    Deux causes seulement : son dataset n'est pas (ou plus) enregistré, ou la
    période demandée ne trouve aucun axe de temps. Le message est en FRANÇAIS
    et nomme ce qui manque.
    """


def get_metric(company, cle):
    """La définition ACTIVE de ``cle`` pour ``company`` (ou ``MetriqueInconnue``)."""
    from .models import MetricDefinition

    definition = MetricDefinition.objects.filter(
        company=company, cle=cle, actif=True).first()
    if definition is None:
        raise MetriqueInconnue(
            'Aucune métrique active « %s » pour cette société.' % cle)
    return definition


def _champ_de_temps(dataset_nom, champ_demande=None):
    """L'axe de TEMPS sur lequel appliquer une période.

    ``champ_demande`` gagne toujours. Sinon on prend le PREMIER champ déclaré
    de type ``temps`` (métadonnées NTDATA5) — déterministe, et c'est l'app
    propriétaire qui a déclaré cet ordre. Aucun axe de temps ⇒ erreur
    explicite : filtrer une période sur un champ deviné serait un chiffre
    inventé.
    """
    from core import data_explorer

    if champ_demande:
        return champ_demande
    try:
        schema = data_explorer.describe_dataset(dataset_nom)
    except data_explorer.DatasetInconnu as exc:
        raise MetriqueNonResolvable(str(exc))
    temps = schema.get('temps') or []
    if not temps:
        raise MetriqueNonResolvable(
            'Le dataset « %s » ne déclare aucun champ de type « temps » : '
            'préciser « champ » dans la période.' % dataset_nom)
    return temps[0]


def _filtres_de_periode(dataset_nom, period):
    """Traduit ``period`` en filtres ``{champ__gte, champ__lte}``.

    ``period`` — dict ``{'champ': …, 'debut': …, 'fin': …}`` (``champ``
    optionnel) ou couple ``(debut, fin)``. ``None`` ⇒ aucun filtre.
    """
    if not period:
        return {}
    if isinstance(period, (tuple, list)):
        debut, fin = (list(period) + [None, None])[:2]
        champ = None
    else:
        debut = period.get('debut')
        fin = period.get('fin')
        champ = period.get('champ')
    if debut is None and fin is None:
        return {}
    champ = _champ_de_temps(dataset_nom, champ)
    filtres = {}
    if debut is not None:
        filtres['%s__gte' % champ] = debut
    if fin is not None:
        filtres['%s__lte' % champ] = fin
    return filtres


def _spec_de_mesure(definition):
    """Les AGRÉGATS de la spec + l'expression à appliquer dessus.

    Renvoie ``(agregats, expression, alias_agregats)``. ``expression`` est
    ``None`` pour une mesure simple (l'agrégat EST déjà la valeur).
    """
    mesure = definition.mesure if isinstance(definition.mesure, dict) else {}
    if mesure.get('formula'):
        agregats = [
            {'alias': a.get('alias'), 'fn': a.get('fn'),
             'field': a.get('field') or 'id'}
            for a in (mesure.get('aggregates') or [])
        ]
        return agregats, mesure['formula'], [a['alias'] for a in agregats]
    fn = mesure.get('agg')
    champ = mesure.get('field') or 'id'
    return [{'alias': ALIAS_VALEUR, 'fn': fn, 'field': champ}], None, []


def _valeur_de_formule(expression, alias_agregats, ligne, cle):
    """La valeur d'une mesure FORMULE sur UNE ligne d'agrégats.

    TROIS issues, et trois seulement :

    * un agrégat manquant ou VIDE (``None`` — population vide : ``SUM`` d'un
      ensemble vide vaut ``NULL``, ou un champ écarté par la permission
      AUD801) ⇒ ``None``. On ne le remplace PAS par zéro : zéro serait un
      chiffre faux, et « je ne sais pas » n'est pas « rien » ;
    * une DIVISION PAR ZÉRO ⇒ ``None`` (jamais une exception : un seul mois à
      dénominateur nul ne doit pas faire tomber toute la série) ;
    * une expression ILLÉGALE (nœud interdit, variable inconnue) ⇒
      ``MetriqueNonResolvable`` — c'est une définition fautive, pas une
      donnée manquante, et elle doit être corrigée, pas masquée.
    """
    from core.formula import FormulaError, evaluer_formule

    contexte = {alias: ligne.get(alias) for alias in alias_agregats}
    if any(contexte.get(alias) is None for alias in alias_agregats):
        return None
    try:
        return evaluer_formule(expression, contexte)
    except FormulaError as exc:
        if 'Division par zéro' in str(exc):
            return None
        raise MetriqueNonResolvable(
            'Métrique « %s » : formule invalide — %s' % (cle, exc))


def resolve_metric(company, user, cle, *, filters=None, group_by=None,
                   period=None):
    """Résout la métrique ``cle`` et renvoie sa valeur (ou sa série).

    ``filters`` — filtres additionnels, au format de la spec du moteur
    (``{'statut': 'payee'}``), validés contre la liste blanche du dataset.
    ``group_by`` — champs de regroupement ; sans eux, une valeur GLOBALE.
    ``period`` — ``{'champ': …, 'debut': …, 'fin': …}`` ou ``(debut, fin)``.

    RENDU ::

        {
          'cle', 'libelle', 'unite', 'format', 'dataset',
          'group_by': [...],
          'valeur': <valeur globale, ou None si regroupée>,
          'lignes': [ {<dimension>: …, 'valeur': …}, … ],
        }

    ``valeur`` à ``None`` n'est JAMAIS un zéro déguisé : c'est soit une
    division par zéro, soit une population vide, soit un champ que ce lecteur
    n'a pas le droit de voir.
    """
    from core import data_explorer
    from core.formula import FormulaError

    definition = get_metric(company, cle)
    dataset_nom = definition.dataset
    # Un `group_by` explicitement VIDE reste vide (valeur globale) : seul un
    # appel SANS `group_by` (``None``) retombe sur les dimensions par défaut
    # de la définition. Confondre les deux ferait rendre une série là où
    # l'appelant — une alerte de seuil, par exemple — attend UN nombre.
    if group_by is None:
        group_by = list(definition.dimensions_par_defaut or [])
    else:
        group_by = list(group_by)

    agregats, expression, alias_agregats = _spec_de_mesure(definition)
    filtres = dict(filters or {})
    filtres.update(_filtres_de_periode(dataset_nom, period))

    spec = {
        'filters': filtres,
        'group_by': group_by,
        'aggregates': agregats,
        'order_by': list(group_by),
    }
    try:
        lignes = data_explorer.run_query(dataset_nom, company, user, spec)
    except data_explorer.DatasetInconnu as exc:
        raise MetriqueNonResolvable(
            'Métrique « %s » : %s' % (cle, exc))
    except (data_explorer.ChampNonAutorise, FormulaError) as exc:
        raise MetriqueNonResolvable(
            'Métrique « %s » : %s' % (cle, exc))

    # La formule est appliquée ICI, jamais par `formula_measures` du moteur :
    # celui-ci RE-LÈVE toute FormulaError qui n'est pas une division par zéro,
    # et un agrégat VIDE (population vide ⇒ `SUM` NULL) produit justement un
    # « NoneType / NoneType » qui ferait tomber la série entière. Voir
    # `_valeur_de_formule` : vide ⇒ None, division par zéro ⇒ None, définition
    # fautive ⇒ erreur explicite.
    if expression:
        for ligne in lignes:
            valeur = _valeur_de_formule(expression, alias_agregats, ligne, cle)
            for alias in alias_agregats:
                ligne.pop(alias, None)
            ligne[ALIAS_VALEUR] = valeur

    entete = {
        'cle': definition.cle,
        'libelle': definition.libelle,
        'unite': definition.unite,
        'format': definition.format,
        'dataset': dataset_nom,
        'group_by': group_by,
    }
    if group_by:
        return dict(entete, valeur=None, lignes=lignes)
    valeur = lignes[0].get(ALIAS_VALEUR) if lignes else None
    return dict(entete, valeur=valeur, lignes=lignes)


def resolve_metric_valeur(company, user, cle, **kwargs):
    """Raccourci : la seule VALEUR globale d'une métrique (ou ``None``).

    Utilisé par les consommateurs qui n'ont besoin que du nombre (alertes KPI
    NTDATA13, widgets). Force l'absence de regroupement — une alerte de seuil
    compare une valeur, pas une série.
    """
    kwargs.pop('group_by', None)
    resultat = resolve_metric(company, user, cle, group_by=[], **kwargs)
    return resultat['valeur']
