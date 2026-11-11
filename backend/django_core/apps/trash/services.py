"""NTUX7 — écritures/orchestration de la corbeille transverse.

Point d'entrée cross-app pour les ÉCRITURES (frontière inter-apps, CLAUDE.md) :
journalisation d'une suppression, restauration, purge de rétention.
"""
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.conflit_etat import ConflitEtat
from core.events import record_restored

from .models import ElementSupprime
from .registry import restaurateur

logger = logging.getLogger(__name__)

# Le SEUL drapeau de suppression reconnu par le repli GÉNÉRIQUE de `restaurer`
# (`core.SoftDeleteModel.is_deleted`, résolu sur l'instance). ASUP10 —
# l'archivage (`is_archived`) et l'annulation (`annule`) ne passent jamais par
# la corbeille : un lead archivé puis supprimé revient archivé.
DRAPEAUX_SOFT_DELETE = ('is_deleted',)


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

    connus = [d for d in DRAPEAUX_SOFT_DELETE if hasattr(obj, d)]
    if not connus and not hasattr(obj, 'restore'):
        raise RestaurationImpossible(
            f"Aucun service de restauration pour « {element.cle_modele} » et "
            f"aucun drapeau de soft-delete reconnu sur la cible."
        )

    if getattr(obj, 'is_deleted', False) and hasattr(obj, 'restore'):
        obj.restore()
    return obj


def _vivant_en_conflit(element):
    """ASUP16 — l'enregistrement vivant qui porte déjà les valeurs uniques de la cible, sinon ``None``."""
    modele = element.content_type.model_class()
    obj = getattr(modele, 'all_objects', modele._default_manager).filter(pk=element.object_id).first()
    for c in (modele._meta.constraints if obj else ()):
        valeurs = {f: getattr(obj, f) for f in getattr(c, 'fields', ())}
        if valeurs and None not in valeurs.values() and (
                autre := modele._default_manager.filter(**valeurs).exclude(pk=obj.pk).first()):
            return autre
    return None


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
    fonction = restaurateur(element.cle_modele) or _restauration_generique
    try:
        with transaction.atomic():
            obj = fonction(element)
    except IntegrityError:  # ASUP16 — une contrainte d'unicité refuse : 409 nommé, jamais un 500
        autre = _vivant_en_conflit(element)
        raise ConflitEtat("Restauration impossible : un élément vivant porte déjà le même identifiant"
                          + (f" — « {autre} » (#{autre.pk})." if autre else "."))
    element.restaure_le = now or timezone.now()
    element.save(update_fields=['restaure_le', 'updated_at'])
    # NTUX32 — webhook sortant (jamais sur le no-op « déjà restauré » ci-dessus,
    # géré par apps/publicapi/uxviews_event_receivers.py). Best-effort : un
    # abonné qui casse ne doit jamais faire échouer la restauration.
    try:
        record_restored.send(
            sender=ElementSupprime, element=element, obj=obj,
            company=element.company, user=user)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.exception(
            'record_restored: envoi du signal échoué (%s)', element.pk)
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
    from core.trash import purger_deletion_records
    purger_deletion_records(now=now, company=company)  # ASUP15 — même rétention que la corbeille commune
    if par_company:
        # ASUP16 — une pièce jointe RETIRÉE (jamais restaurée) perd son binaire par l'API de stockage de la pièce
        # (une clé encore tenue ailleurs est conservée) ; la ligne métier reste.
        from apps.records.models import Attachment
        from apps.records.storage import delete_attachment
        for piece in Attachment.objects.filter(pk__in=qs.filter(
                restaure_le__isnull=True, content_type__app_label='records',
                content_type__model='attachment').values('object_id')):
            delete_attachment(piece.file_key, liberee_par=(piece,))
        qs.delete()
        logger.info('purger_corbeille: %d entrée(s) purgée(s) sur %d société(s).',
                    sum(par_company.values()), len(par_company))
    return par_company
