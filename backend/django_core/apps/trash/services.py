"""NTUX7 — écritures/orchestration de la corbeille transverse.

Point d'entrée cross-app pour les ÉCRITURES (frontière inter-apps, CLAUDE.md) :
journalisation d'une suppression, restauration, purge de rétention.
"""
import logging

from django.utils import timezone

from .models import ElementSupprime
from .registry import restaurateur

logger = logging.getLogger(__name__)

# Drapeaux de soft-delete reconnus par le repli GÉNÉRIQUE de `restaurer` (les
# conventions déjà en place dans le repo : `core.SoftDeleteModel.is_deleted`,
# `is_archived`, `annule`). Résolus DYNAMIQUEMENT sur l'instance — jamais par un
# import du modèle d'une autre app.
DRAPEAUX_SOFT_DELETE = ('is_deleted', 'is_archived', 'annule')


class RestaurationImpossible(Exception):
    """La cible ne sait pas se restaurer (aucun restaurateur enregistré et
    aucun drapeau de soft-delete reconnu)."""


def journaliser_suppression(*, instance, company, user=None, type_libelle='',
                            libelle='', donnees=None, now=None):
    """Crée l'entrée de corbeille d'un enregistrement soft-supprimé.

    Appelée par le récepteur de `core.events.record_soft_deleted` — une app ne
    l'appelle donc jamais directement, elle ÉMET l'événement.

    Idempotent par cible : une cible déjà présente dans la corbeille ACTIVE
    (non restaurée) ne crée pas de doublon, son entrée est rafraîchie.
    """
    from django.contrib.contenttypes.models import ContentType

    now = now or timezone.now()
    content_type = ContentType.objects.get_for_model(type(instance))
    valeurs = {
        'type_libelle': (type_libelle or content_type.name or '')[:80],
        'libelle_snapshot': (libelle or str(instance) or '')[:255],
        'donnees_snapshot': donnees or {},
        'supprime_par': user,
        'supprime_le': now,
    }
    element = (ElementSupprime.objects
               .filter(company=company, content_type=content_type,
                       object_id=instance.pk, restaure_le__isnull=True)
               .first())
    if element is not None:
        for champ, valeur in valeurs.items():
            setattr(element, champ, valeur)
        # La rétention repart de la NOUVELLE date de suppression.
        element.expire_le = None
        element.save()
        return element
    return ElementSupprime.objects.create(
        company=company, content_type=content_type, object_id=instance.pk,
        **valeurs)


def _restauration_generique(element):
    """Repli : bascule le drapeau de soft-delete de la cible, résolue par
    `content_type` (aucun import de modèle étranger).

    Utilisé tant que l'app cible n'a pas enregistré son propre restaurateur
    (`registry.enregistrer_restaurateur`). Renvoie l'objet restauré, ou ``None``
    si la cible a disparu.
    """
    modele = element.content_type.model_class() if element.content_type_id else None
    if modele is None:
        return None
    manager = getattr(modele, 'all_objects', modele._default_manager)
    obj = manager.filter(pk=element.object_id).first()
    if obj is None:
        return None

    # Un modèle peut porter PLUSIEURS mécanismes de soft-delete indépendants :
    # `crm.Lead` hérite `core.SoftDeleteModel` (donc `is_deleted` + `restore()`)
    # ET possède son propre `is_archived`. Préférer `restore()` sur le seul
    # critère `hasattr` était donc faux : archiver un lead pose `is_archived`,
    # mais `restore()` ne regarde que `is_deleted`, sort immédiatement quand il
    # est déjà `False`, et rendait la restauration SILENCIEUSEMENT INEFFICACE —
    # l'API répondait `restaure: true`, l'entrée se fermait, et la cible restait
    # archivée (donnée irrécupérable depuis la corbeille).
    #
    # On lève donc TOUS les drapeaux réellement posés, `restore()` gardant la
    # main sur `is_deleted` (il gère aussi la fermeture de son propre journal).
    connus = [d for d in DRAPEAUX_SOFT_DELETE if hasattr(obj, d)]
    if not connus and not hasattr(obj, 'restore'):
        raise RestaurationImpossible(
            f"Aucun service de restauration pour « {element.cle_modele} » et "
            f"aucun drapeau de soft-delete reconnu sur la cible."
        )

    if getattr(obj, 'is_deleted', False) and hasattr(obj, 'restore'):
        obj.restore()

    champs = [d for d in connus if d != 'is_deleted' and getattr(obj, d, False)]
    if champs:
        for drapeau in champs:
            setattr(obj, drapeau, False)
        obj.save(update_fields=champs)
    return obj


def restaurer(element, *, user=None, now=None):
    """Restaure la cible d'une entrée de corbeille et ferme l'entrée.

    Appelle EN PRIORITÉ le restaurateur que l'app cible a enregistré (son
    `services.py`) ; à défaut, le repli générique ci-dessus. Jamais un accès
    direct au modèle d'une autre app.

    Renvoie l'objet restauré, ou ``None`` si la cible n'existe plus (l'entrée
    est alors quand même fermée — elle n'est plus restaurable).
    """
    if element.restaure_le is not None:
        return None
    fonction = restaurateur(element.cle_modele)
    if fonction is not None:
        obj = fonction(element)
    else:
        obj = _restauration_generique(element)
    element.restaure_le = now or timezone.now()
    element.save(update_fields=['restaure_le', 'updated_at'])
    return obj


def purger_expires(*, now=None, company=None):
    """Supprime DÉFINITIVEMENT les entrées dont la rétention est dépassée.

    Renvoie ``{company_id: nombre_purgé}`` (journalisé par la commande
    `purger_corbeille`). Ne touche JAMAIS l'enregistrement métier cible : la
    corbeille est un journal, la donnée d'origine suit sa propre rétention.
    """
    from .selectors import expirees

    now = now or timezone.now()
    qs = expirees(company, now=now)
    par_company = {}
    for company_id, object_id in qs.values_list('company_id', 'id'):
        par_company[company_id] = par_company.get(company_id, 0) + 1
    if par_company:
        qs.delete()
        logger.info('purger_corbeille: %d entrée(s) purgée(s) sur %d société(s).',
                    sum(par_company.values()), len(par_company))
    return par_company
