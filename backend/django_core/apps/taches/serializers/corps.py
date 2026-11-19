"""Base des CORPS reçus de l'app : les règles CROISÉES (entre deux champs) publiées au schéma.

Une règle qui lie deux champs (« `avant_id` ou `apres_id` », « une heure demande un jour », « `deplacer`
demande un projet ») ne se dit pas champ par champ : sans elle, le schéma déclare valide un corps que le
serveur refuse (api-fuzz, `positive_data_acceptance`). Un corps la déclare dans `regles_croisees` — une
liste de groupes, chaque groupe = les branches dont AU MOINS UNE doit tenir (`anyOf`) — et l'extension
ci-dessous la publie en `allOf` de ces `anyOf`, côté requête seulement. La validation du serveur reste celle
du sérialiseur ou du service (même message, même champ) : le schéma dit enfin ce qu'elle exige.
"""
from drf_spectacular.extensions import OpenApiSerializerExtension
from rest_framework import serializers


class CorpsTaches(serializers.Serializer):
    """Un corps reçu ; `regles_croisees` : `((branche, …), …)`, chaque branche un fragment de schéma."""

    regles_croisees = ()


class _ReglesCroiseesPubliees(OpenApiSerializerExtension):
    target_class = 'apps.taches.serializers.corps.CorpsTaches'
    match_subclasses = True

    def map_serializer(self, auto_schema, direction):
        schema = auto_schema._map_serializer(self.target, direction, bypass_extensions=True)
        regles = getattr(self.target, 'regles_croisees', ())
        if direction != 'request' or not regles:
            return schema
        return {**schema, 'allOf': [{'anyOf': [dict(branche) for branche in groupe]} for groupe in regles]}


def parmi(*valeurs):
    """« Une de `valeurs` », en `anyOf` : le crochet de nommage des énums (`postprocess_schema_enums`) ne lit que
    les `enum` posés directement sous `properties` (il en faisait des composants, et `[None]` un énum vide)."""
    return {'anyOf': [{'enum': list(valeurs)}]}


def present(champ, schema):
    """Branche « `champ` présent et conforme à `schema` »."""
    return {'required': [champ], 'properties': {champ: schema}}


def valeur(champ, *valeurs):
    """Branche « `champ`, s'il est présent, vaut une de `valeurs` »."""
    return {'properties': {champ: parmi(*valeurs)}}


def absent(champ):
    """Branche « `champ` absent »."""
    return {'not': {'required': [champ]}}


ENTIER = {'type': 'integer'}
DATE = {'type': 'string', 'format': 'date'}
