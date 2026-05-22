from django.db import models


class TimestampedModel(models.Model):
    """
    Modèle abstrait de base — ajoute created_at 
    / updated_at à tout modèle qui en hérite.
    Usage : class MonModele(TimestampedModel): ...
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
