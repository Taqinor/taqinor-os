"""NTDATA9 — une édition de métrique FIGE automatiquement sa version.

POURQUOI UN SIGNAL ET PAS UN APPEL DANS LA VUE. Une ``MetricDefinition``
s'édite par plus d'un chemin : l'API, l'admin Django, le seeder
``seed_metriques``, un script de reprise. Poser l'instantané dans UN de ces
chemins laisserait les autres écrire en silence — et un historique troué ment
plus qu'il n'informe. Le signal couvre les quatre.

CE QUE LE SIGNAL NE SAIT PAS : QUI édite. Un ``post_save`` n'a pas d'acteur.
La version est donc figée SANS auteur par ce chemin, et c'est écrit tel quel
(``auteur`` NULL = « chemin sans acteur identifié ») plutôt que d'attribuer la
modification à quelqu'un au hasard. Un appelant qui CONNAÎT l'acteur — une vue
authentifiée — appelle ``services.snapshot_metrique(definition,
auteur=request.user)`` AVANT d'enregistrer : le signal voit alors un instantané
déjà à jour et n'écrit rien (idempotence par contenu).

Ce module est importé depuis ``SemanticConfig.ready()`` — les modèles y sont
chargés, le récepteur est donc branché sur son sender EXACT (jamais un
récepteur global qui tournerait à chaque écriture du dépôt).
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MetricDefinition


@receiver(post_save, sender=MetricDefinition,
          dispatch_uid='semantic_snapshot_metric_definition')
def _figer_version_metrique(sender, instance, **kwargs):
    """Fige une version quand la DÉFINITION d'une métrique a changé."""
    if kwargs.get('raw'):
        return  # chargement de fixture : on ne réécrit pas l'historique.
    from .services import snapshot_metrique

    snapshot_metrique(instance)
