"""Écritures/orchestration de `apps.entites`."""
from django.core.exceptions import ValidationError

from .models import Entite


class CycleEntiteError(ValidationError):
    """NTADM30 — un parent ne peut jamais être un descendant de lui-même."""


def valider_non_cycle(entite, parent):
    """Lève `CycleEntiteError` si `parent` créerait un cycle pour `entite`
    (parent == entite, ou parent est un descendant de entite)."""
    if parent is None:
        return
    if entite.pk is not None and parent.pk == entite.pk:
        raise CycleEntiteError(
            "Une entité ne peut pas être son propre parent.")
    if entite.pk is not None and parent.pk in entite.descendants_ids():
        raise CycleEntiteError(
            "Ce rattachement créerait une boucle : le parent choisi est "
            "un descendant de cette entité.")


def creer_entite(company, *, nom, code, parent=None, user=None):
    """NTADM1 — crée une entité, valide l'anti-cycle, émet `entite_created`
    (NTADM40)."""
    entite = Entite(company=company, nom=nom, code=code, parent=parent)
    if parent is not None:
        valider_non_cycle(entite, parent)
    entite.full_clean(exclude=['id'])
    entite.save()

    from core.events import entite_created
    entite_created.send(sender=Entite, entite=entite, user=user)
    return entite


def desactiver_entite(entite, *, user=None):
    """NTADM1/40 — désactive une entité (soft — jamais de suppression dure) et
    émet `entite_deactivated`."""
    if entite.actif:
        entite.actif = False
        entite.save(update_fields=['actif'])

        from core.events import entite_deactivated
        entite_deactivated.send(sender=Entite, entite=entite, user=user)
    return entite


def changer_parent(entite, nouveau_parent, *, user=None):
    """NTADM30/47 — change le parent d'une entité après validation anti-cycle.
    Retourne (entite, ancienne_valeur) pour permettre au chatter (NTADM47)
    de journaliser le changement."""
    valider_non_cycle(entite, nouveau_parent)
    ancien = entite.parent
    entite.parent = nouveau_parent
    entite.full_clean(exclude=['id'])
    entite.save(update_fields=['parent', 'updated_at'])
    return entite, ancien
