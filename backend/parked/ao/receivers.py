"""Péremption automatique EN CASCADE des variantes (``apps.ao``) — AOF29.

Le défaut réel évité : la note de synthèse d'un dossier annonçait encore 264
modules quand la donnée en disait 314 — **la pièce la plus lue était la plus
fausse**. Dès qu'une entrée bouge (obstacle, cote, enveloppe, preset), toute
variante dont l'empreinte d'entrée DIVERGE bascule ``PERIME``, et les pièces
qui s'y adossent suivent.

**La péremption est GRANULAIRE.** Une planche du bâtiment C ne périme pas parce
que le bâtiment A a changé : le balayage est borné à LA toiture touchée. Sans
cette borne, le bandeau rouge s'afficherait partout, tout le temps, et
l'utilisateur apprendrait à l'ignorer — ce qui est pire que pas de bandeau.

Câblé au démarrage par ``AoConfig.ready()``.
"""
import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ChaineCotes, ObstacleAO, ToitureAO, VarianteCalepinage

logger = logging.getLogger(__name__)


def perimer_variantes_divergentes(toiture):
    """Périme les variantes de CETTE toiture dont l'empreinte a divergé.

    Une variante sans empreinte enregistrée n'est PAS périmée : elle n'a
    jamais prétendu correspondre à une entrée donnée. Renvoie le nombre de
    variantes périmées.
    """
    from .hashing import empreinte_entree

    variantes = list(VarianteCalepinage.objects.filter(
        toiture=toiture,
    ).exclude(statut=VarianteCalepinage.Statut.PERIME).exclude(entree_hash=''))
    if not variantes:
        return 0

    perimees = 0
    cache = {}
    for variante in variantes:
        cle = (
            json_cle(variante.params),
            json_cle((variante.params or {}).get('kits_autorises')),
            variante.version_moteur,
        )
        if cle not in cache:
            cache[cle] = empreinte_entree(
                toiture, params=variante.params,
                kits=(variante.params or {}).get('kits_autorises'),
                version_moteur=variante.version_moteur)
        if variante.entree_hash != cache[cle]:
            variante.statut = VarianteCalepinage.Statut.PERIME
            variante.save(update_fields=['statut', 'updated_at'])
            perimees += 1
    return perimees


def json_cle(valeur):
    """Clé de cache stable pour un fragment JSON (dict/list/None)."""
    import json

    return json.dumps(valeur, sort_keys=True, ensure_ascii=False,
                      default=str)


def _perimer_best_effort(toiture):
    """Ne casse JAMAIS l'écriture qui l'a déclenchée."""
    if toiture is None:
        return
    try:
        perimer_variantes_divergentes(toiture)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'AOF29 : péremption en cascade échouée pour la toiture #%s',
            getattr(toiture, 'pk', '?'), exc_info=True)


@receiver(post_save, sender=ObstacleAO,
          dispatch_uid='ao_perimer_variantes_on_obstacle_save')
@receiver(post_delete, sender=ObstacleAO,
          dispatch_uid='ao_perimer_variantes_on_obstacle_delete')
def _sur_ecriture_obstacle(sender, instance, **kwargs):
    _perimer_best_effort(getattr(instance, 'toiture', None))


@receiver(post_save, sender=ChaineCotes,
          dispatch_uid='ao_perimer_variantes_on_chaine_save')
@receiver(post_delete, sender=ChaineCotes,
          dispatch_uid='ao_perimer_variantes_on_chaine_delete')
def _sur_ecriture_chaine(sender, instance, **kwargs):
    _perimer_best_effort(getattr(instance, 'toiture', None))


@receiver(post_save, sender=ToitureAO,
          dispatch_uid='ao_perimer_variantes_on_toiture_save')
def _sur_ecriture_toiture(sender, instance, created, **kwargs):
    """Enveloppe ou preset modifiés : mêmes conséquences qu'un obstacle."""
    if created:
        return
    _perimer_best_effort(instance)
