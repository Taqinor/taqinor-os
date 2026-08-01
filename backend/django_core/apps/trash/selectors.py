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
