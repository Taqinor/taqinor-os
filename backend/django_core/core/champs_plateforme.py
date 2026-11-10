"""Colonnes PLATEFORME portées par les modèles métier « chauds » (mixins abstraits).

Couche de FONDATION pure : aucune importation d'app domaine. Un modèle métier
hérite du mixin ; la colonne, sa règle d'entretien et sa migration vivent dans
son app (une migration par app propriétaire).

NTPLT17 — :class:`VerrouOptimisteMixin`, verrou optimiste OPT-IN.
``lock_version`` (et non ``version`` : ``Devis.version`` est déjà le numéro de
révision V1/V2 lu par le moteur de devis — le réutiliser casserait les
révisions) avance de 1 à chaque ``save()`` d'une ligne existante. La
vérification (409 quand le client renvoie une version périmée) vit dans
``core.verrou_optimiste.VerrouOptimisteSerializerMixin`` ; un client qui
n'envoie rien garde le comportement d'avant, à l'identique.

Limite assumée : un ``QuerySet.update()`` / ``bulk_update`` ne fait pas avancer
la version (aucun ``save()``), comme ``auto_now``.
"""
from django.db import models


class VerrouOptimisteMixin(models.Model):
    """``lock_version`` : 0 à la création, +1 à chaque ``save()`` d'une ligne
    existante — y compris borné par ``update_fields`` (la colonne y est
    ajoutée, sinon la version n'atteindrait jamais la base)."""

    lock_version = models.PositiveIntegerField(
        default=0, editable=False,
        help_text='Verrou optimiste (NTPLT17) : +1 à chaque enregistrement.')

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = list(update_fields)  # un générateur ne se lit qu'une fois
            kwargs['update_fields'] = update_fields
        # ``update_fields=[]`` : Django n'écrit rien, la version ne bouge pas.
        if not self._state.adding and (update_fields is None or update_fields):
            self.lock_version = (self.lock_version or 0) + 1
            if update_fields is not None and 'lock_version' not in update_fields:
                kwargs['update_fields'] = [*update_fields, 'lock_version']
        super().save(*args, **kwargs)
