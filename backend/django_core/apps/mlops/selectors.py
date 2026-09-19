"""Sélecteurs (LECTURE) du module « mlops » (Groupe NTAI, P3).

Point d'entrée UNIQUE pour qu'un scorer (``core/*.py``) lise les paramètres
ACTIFS de sa société — jamais un import direct de ``apps.mlops.models``
ailleurs. Toute lecture est SCOPÉE SOCIÉTÉ.
"""
from __future__ import annotations


def params_actifs(company, nom, *, defauts=None):
    """Paramètres ACTIFS d'un scorer pour une société, ou ``defauts``.

    ``nom`` — une des clés de ``ModeleML.Nom`` (``'churn'``, ``'win_proba'``,
    ``'retard_paiement'``, ``'reappro'``, ``'anomalie'``). Sans société, sans
    version active, ou si le JSON stocké n'est pas un dict, renvoie
    ``defauts`` (``{}`` par défaut) INCHANGÉ — un scorer existant qui
    n'appelle jamais ce module garde EXACTEMENT son comportement actuel.

    Ne lève jamais : un scorer ne doit jamais planter parce que le registre de
    paramètres est indisponible.
    """
    defauts = dict(defauts or {})
    if company is None or not nom:
        return defauts
    from .models import ModeleML

    actif = (
        ModeleML.objects.filter(company=company, nom=nom, actif=True)
        .order_by('-version').first())
    if actif is None or not isinstance(actif.params_json, dict):
        return defauts
    return actif.params_json


def version_active(company, nom):
    """L'instance ``ModeleML`` active d'un scorer pour une société, ou
    ``None``. Utile à l'écran d'administration (affiche QUELLE version tourne
    réellement) sans dupliquer la requête ci-dessus."""
    if company is None or not nom:
        return None
    from .models import ModeleML

    return (ModeleML.objects.filter(company=company, nom=nom, actif=True)
            .order_by('-version').first())


def feature_vector(company, content_type, object_id):
    """NTAI30 — ``features_json`` matérialisé d'une entité (``content_type``
    ex. ``'crm.lead'``, ``object_id``), ou ``{}`` sans vecteur matérialisé —
    l'appelant garde alors son calcul direct habituel (repli inchangé,
    jamais une exception)."""
    if company is None or not content_type or not object_id:
        return {}
    from .models import FeatureVector

    vecteur = FeatureVector.objects.filter(
        company=company, content_type=content_type,
        object_id=object_id).first()
    if vecteur is None or not isinstance(vecteur.features_json, dict):
        return {}
    return vecteur.features_json


def versions_pour_company(company, nom=None):
    """Toutes les versions (actives ou non) d'un scorer — ou de tous les
    scorers — pour une société, les plus récentes d'abord."""
    if company is None:
        return []
    from .models import ModeleML

    qs = ModeleML.objects.filter(company=company)
    if nom:
        qs = qs.filter(nom=nom)
    return list(qs)
