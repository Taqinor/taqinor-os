"""ENF15 — relecture SOUS VERROU d'un document avant une garde de statut.

Une garde ``if doc.statut != …: raise`` lue sur une instance chargée AVANT la
transaction laisse deux requêtes concurrentes la franchir toutes les deux (double
entrée de stock, double décision, double application). ``sous_verrou`` exécute la
fonction dans ``transaction.atomic()``, verrouille la ligne portée par un argument
(``select_for_update``, bornée à sa société quand elle en a une) et RELIT
l'instance en place : la garde du corps voit l'état committé, pas un état périmé.
"""
import functools
import inspect

from django.db import transaction


def sous_verrou(argument):
    """Décorateur : atomique + ligne ``argument`` verrouillée puis relue."""

    def decorateur(fonction):
        signature = inspect.signature(fonction)

        @functools.wraps(fonction)
        def enveloppe(*args, **kwargs):
            liees = signature.bind(*args, **kwargs)
            with transaction.atomic():
                instance = liees.arguments[argument]
                filtre = {'pk': instance.pk}
                if getattr(instance, 'company_id', None) is not None:
                    filtre['company_id'] = instance.company_id
                type(instance)._default_manager.select_for_update().filter(**filtre).first()
                instance.refresh_from_db()
                return fonction(*args, **kwargs)

        return enveloppe

    return decorateur
