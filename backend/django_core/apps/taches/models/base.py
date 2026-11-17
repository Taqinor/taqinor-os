"""Bases communes des modèles `taches` (reference/donnees.md §0, §2) — aucun modèle concret.

- `StrNeutreMixin` : `__str__` neutre (`"<verbose_name> #<pk>"`), jamais un titre ni un nom.
- `NomCleQuerySet` : `nom_cle` n'est calculé que par `save()` ; `bulk_create`, et `update` /
  `bulk_update` qui touchent `nom`, contourneraient ce calcul (clé vide, collisions) : ils lèvent.
- Gestionnaires : `GestionnaireNomCle` (tout) et `GestionnaireNomCleVivants` (filtre des vivants
  de `SoftDeleteModel`, pour `Projet`).
"""
from django.db import models

from apps.taches.saisie.normalisation import cle_nom
from core.models import SoftDeleteQuerySet

CHAMPS_NOM = frozenset({'nom', 'nom_cle'})


class StrNeutreMixin(models.Model):
    """`__str__` neutre : le titre d'une tâche ou le nom d'un projet n'entre jamais dans un
    journal, une corbeille ou un message d'erreur par `str(objet)`."""

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self._meta.verbose_name} #{self.pk}'


class NomCleQuerySet(SoftDeleteQuerySet):
    """Jeu de requêtes des modèles à `nom_cle` (Projet, Section, Etiquette)."""

    def bulk_create(self, *args, **kwargs):
        raise TypeError(
            f'{self.model.__name__} : bulk_create interdit (nom_cle est calculé par save()).')

    def update(self, **kwargs):
        if CHAMPS_NOM & set(kwargs):
            raise TypeError(
                f'{self.model.__name__} : update(nom=…) interdit (nom_cle est calculé par save()).')
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, *args, **kwargs):
        if CHAMPS_NOM & set(fields):
            raise TypeError(
                f'{self.model.__name__} : bulk_update de nom interdit (nom_cle est calculé par save()).')
        return super().bulk_update(objs, fields, *args, **kwargs)


class GestionnaireNomCle(models.Manager.from_queryset(NomCleQuerySet)):
    """Toutes les lignes (Section, Etiquette ; `all_objects` de Projet)."""


class GestionnaireNomCleVivants(GestionnaireNomCle):
    """Lignes vivantes seulement (`objects` de Projet), comme `SoftDeleteManager`."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


def poser_nom_cle(instance, kwargs):
    """À appeler dans `save()` : calcule `nom_cle` depuis `nom` et l'ajoute à `update_fields`
    quand `nom` y figure (sinon la clé ne serait jamais écrite)."""
    instance.nom_cle = cle_nom(instance.nom or '')
    update_fields = kwargs.get('update_fields')
    if update_fields is not None:
        update_fields = list(update_fields)
        if 'nom' in update_fields and 'nom_cle' not in update_fields:
            update_fields.append('nom_cle')
        kwargs['update_fields'] = update_fields
