"""NTPLT31 — Registre de recherche par module (fondation, sans app métier).

Chaque app déclare dans son ``apps.py`` ``ready()`` les modèles qu'elle veut
voir apparaître dans la recherche globale :

    from core import search_registry

    search_registry.register_search(
        Lead,
        fields={'A': ['nom', 'entreprise'], 'B': ['email', 'telephone'],
                'C': ['ville']},
        route='/crm/leads/{id}',
        label='Lead',
    )

Le registre EN MÉMOIRE devient la SOURCE UNIQUE consommée par le global search
(``apps/reporting/search.py``) et tout backend de recherche futur
(``core.search_backend``). ``core`` reste FONDATION : il n'importe AUCUNE app
métier — ce sont les apps qui s'enregistrent elles-mêmes (même pattern que le
registre d'agents / de rétention).

Pondération A/B/C
-----------------
Convention Postgres ``ts_rank`` : ``A`` = champs les plus importants (nom,
référence), ``B`` = importants (email, désignation), ``C``/``D`` = contextuels
(ville, notes). Un backend FTS (NTPLT32-33) mappe ces poids sur
``setweight('A'..'D')`` ; le repli ``icontains`` les traite tous pareil.
"""
from __future__ import annotations

# Registre {label_modèle -> entrée}. Réinitialisé à chaque démarrage process ;
# chaque app le repeuple dans son ``ready()``.
_REGISTRY: dict = {}

# Poids valides (ordre d'importance décroissante), alignés sur ts_rank.
VALID_WEIGHTS = ('A', 'B', 'C', 'D')


class SearchEntry:
    """Entrée de recherche déclarée par une app pour un modèle donné."""

    __slots__ = ('model', 'fields', 'route', 'label', 'entity')

    def __init__(self, model, fields, route, label, entity):
        self.model = model
        self.fields = fields  # {'A': [...], 'B': [...], ...}
        self.route = route    # gabarit de route frontend, ex. '/crm/leads/{id}'
        self.label = label    # libellé humain du type (ex. 'Lead')
        self.entity = entity  # clé stable app_label.model_name

    def all_fields(self):
        """Liste à plat de tous les champs déclarés (tous poids confondus)."""
        out = []
        for weight in VALID_WEIGHTS:
            out.extend(self.fields.get(weight, []))
        return out


def register_search(model, fields, route, label=None, entity=None):
    """Enregistre ``model`` dans la recherche globale.

    * ``fields`` : dict pondéré ``{'A': [...], 'B': [...], 'C': [...]}`` — au
      moins un champ requis. Les clés hors ``VALID_WEIGHTS`` sont ignorées.
    * ``route`` : gabarit de route frontend (``{id}`` remplacé par le pk).
    * ``label`` : libellé humain (défaut = nom du modèle).
    * ``entity`` : clé stable (défaut = ``app_label.model_name``).

    Ré-enregistrer le même modèle REMPLACE l'entrée (idempotent au rechargement
    du registre d'apps — utile en test).
    """
    entity = entity or f'{model._meta.app_label}.{model._meta.model_name}'
    label = label or model._meta.verbose_name.title()
    clean = {w: list(fields.get(w, [])) for w in VALID_WEIGHTS if fields.get(w)}
    if not clean:
        raise ValueError(
            f'register_search({entity}): au moins un champ pondéré requis.')
    _REGISTRY[entity] = SearchEntry(
        model=model, fields=clean, route=route, label=label, entity=entity)


def unregister_search(entity_or_model):
    """Retire une entrée (utile en test pour isoler le registre)."""
    entity = entity_or_model
    if not isinstance(entity_or_model, str):
        entity = (f'{entity_or_model._meta.app_label}.'
                  f'{entity_or_model._meta.model_name}')
    _REGISTRY.pop(entity, None)


def registered_entries():
    """Toutes les entrées enregistrées, triées par clé d'entité (stable)."""
    return [_REGISTRY[k] for k in sorted(_REGISTRY.keys())]


def get_entry(entity):
    """Entrée pour une clé d'entité (``app_label.model_name``) ou ``None``."""
    return _REGISTRY.get(entity)


def clear_registry():
    """Vide le registre (test uniquement — jamais en usage normal)."""
    _REGISTRY.clear()
