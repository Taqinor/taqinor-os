"""QHSE14 — Chatter QHSE (historique style Odoo) pour NCR / CAPA / Incident / Audit.

Helpers côté serveur pour écrire et lire l'historique ``QhseChatterEntry`` d'une
entité QHSE. La cible est identifiée par un couple ``(cible_type, cible_id)``
(référence lâche stable) plutôt que par ContentType : la NCR et la CAPA sont
couvertes aujourd'hui, Incident et Audit le seront sans changement de schéma.

L'utilisateur acteur et la société sont toujours déduits/posés ici (jamais lus
du corps de requête). ``log_note`` est manuel ; ``log_creation`` /
``log_field_change`` tracent automatiquement les champs suivis.
"""
from .models import (
    ActionCorrectivePreventive, Audit, NonConformite, QhseChatterEntry,
)

# Mappe une classe de modèle QHSE → sa valeur ``Cible`` du chatter.
_CIBLE_PAR_MODELE = {
    NonConformite: QhseChatterEntry.Cible.NCR,
    ActionCorrectivePreventive: QhseChatterEntry.Cible.CAPA,
    Audit: QhseChatterEntry.Cible.AUDIT,
}


def cible_type_for(instance):
    """Valeur ``Cible`` correspondant à l'instance QHSE, ou ``ValueError``."""
    cible = _CIBLE_PAR_MODELE.get(instance.__class__)
    if cible is None:
        raise ValueError(
            'Type QHSE non chattérisable : %s' % instance.__class__.__name__)
    return cible


def _stringify(value):
    return '' if value is None else str(value)


def log_creation(instance, user):
    """Trace la création d'une entité QHSE dans son chatter."""
    return QhseChatterEntry.objects.create(
        company=instance.company,
        cible_type=cible_type_for(instance),
        cible_id=instance.id,
        kind=QhseChatterEntry.Kind.CREATION,
        user=user,
    )


def log_field_change(instance, user, field, old_value, new_value, label=''):
    """Trace le changement d'un champ suivi (rien si la valeur n'a pas bougé)."""
    old_s, new_s = _stringify(old_value), _stringify(new_value)
    if old_s == new_s:
        return None
    return QhseChatterEntry.objects.create(
        company=instance.company,
        cible_type=cible_type_for(instance),
        cible_id=instance.id,
        kind=QhseChatterEntry.Kind.MODIFICATION,
        field=field or '',
        field_label=label or field or '',
        old_value=old_s,
        new_value=new_s,
        user=user,
    )


def log_note(instance, user, body):
    """Ajoute une note manuelle au chatter d'une entité QHSE."""
    return QhseChatterEntry.objects.create(
        company=instance.company,
        cible_type=cible_type_for(instance),
        cible_id=instance.id,
        kind=QhseChatterEntry.Kind.NOTE,
        body=body or '',
        user=user,
    )


def chatter_for(company, cible_type, cible_id):
    """Historique d'une entité QHSE, scopé société (le plus récent d'abord)."""
    return QhseChatterEntry.objects.filter(
        company=company, cible_type=cible_type, cible_id=cible_id)
