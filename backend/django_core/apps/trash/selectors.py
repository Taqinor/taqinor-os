"""NTUX7 — lectures de la corbeille transverse (point d'entrée cross-app).

Toute LECTURE de la corbeille par une autre app passe par ici (jamais par un
import de `apps.trash.models`) — frontière inter-apps, CLAUDE.md.
"""
from .models import ElementSupprime


def corbeille(company, *, type_libelle=None, depuis=None, jusqua=None,
              inclure_restaures=False):
    """Entrées de corbeille d'une société, les plus récentes d'abord.

    Multi-tenant : TOUJOURS filtré par société. Par défaut, seules les entrées
    ENCORE dans la corbeille (non restaurées) sont renvoyées ; le journal
    complet (audit de rétention) s'obtient avec ``inclure_restaures=True``.

    ``type_libelle`` filtre sur le type lisible (ex. « Devis ») ;
    ``depuis``/``jusqua`` bornent ``supprime_le``.
    """
    qs = ElementSupprime.objects.filter(company=company)
    if not inclure_restaures:
        qs = qs.filter(restaure_le__isnull=True)
    if type_libelle:
        qs = qs.filter(type_libelle__iexact=type_libelle)
    if depuis:
        qs = qs.filter(supprime_le__gte=depuis)
    if jusqua:
        qs = qs.filter(supprime_le__lte=jusqua)
    return qs.select_related('content_type', 'supprime_par')


def expirees(company=None, *, now=None):
    """Entrées dont la rétention est dépassée (candidates à la purge dure)."""
    from django.utils import timezone

    now = now or timezone.now()
    qs = ElementSupprime.objects.filter(expire_le__lt=now)
    if company is not None:
        qs = qs.filter(company=company)
    return qs


def entree_active(instance):
    """CAL208 — l'entrée de corbeille ACTIVE (non restaurée) d'``instance``,
    ou ``None``.

    Générique par ``contenttypes``, comme ``ElementSupprime`` lui-même :
    utile à une app qui doit savoir si SA PROPRE cible est actuellement
    archivée, sans requêter ``ElementSupprime`` directement (frontière
    inter-apps, CLAUDE.md) — ex. exclure ses éléments archivés d'une liste
    PAR DÉFAUT.
    """
    from django.contrib.contenttypes.models import ContentType

    if instance is None or not getattr(instance, 'pk', None):
        return None
    content_type = ContentType.objects.get_for_model(type(instance))
    return (ElementSupprime.objects
            .filter(content_type=content_type, object_id=instance.pk,
                    restaure_le__isnull=True)
            .first())


def ids_dans_corbeille(cle_modele, *, company=None):
    """CAL208 — les ``object_id`` ACTIFS (non restaurés) de ``cle_modele``
    (ex. ``'calepinage.calepinage'``).

    Utile à un module qui doit exclure ses éléments archivés d'une liste PAR
    DÉFAUT sans importer ``ElementSupprime`` directement. ``company`` est
    OPTIONNELLE et resserre le résultat quand elle est fournie — l'omettre
    reste SÛR : les identifiants Django sont uniques PAR TABLE, jamais par
    société, donc exclure cet ensemble d'un queryset déjà scopé société ne
    peut jamais en retirer la ligne d'une AUTRE société par erreur.
    """
    from django.contrib.contenttypes.models import ContentType

    try:
        app_label, modele = str(cle_modele).strip().lower().split('.', 1)
        content_type = ContentType.objects.get_by_natural_key(
            app_label, modele)
    except (ValueError, ContentType.DoesNotExist):
        return ElementSupprime.objects.none().values_list(
            'object_id', flat=True)
    qs = ElementSupprime.objects.filter(content_type=content_type,
                                        restaure_le__isnull=True)
    if company is not None:
        qs = qs.filter(company=company)
    return qs.values_list('object_id', flat=True)
