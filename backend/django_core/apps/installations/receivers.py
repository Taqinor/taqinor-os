"""Récepteurs d'événements métier (M6) — app Installations.

Abonne ``installations`` à l'événement ``devis_accepted`` exposé par
``core.events`` pour, à l'acceptation d'un devis, créer AUTOMATIQUEMENT le
chantier correspondant — sans que ``ventes`` importe ``installations``. Câblé
au démarrage par ``InstallationsConfig.ready`` (même schéma que ``crm`` dans
``apps/crm/receivers.py``).

Le récepteur passe par la couche service (``services.create_installation_from_devis``)
qui est IDEMPOTENTE : si un chantier existe déjà pour ce devis, elle le renvoie
sans en créer un second. Ré-accepter un devis (ou ré-émettre l'événement) ne
duplique donc jamais le chantier. La création est company-scopée
(``devis.company``). Le signal est synchrone, comme les autres récepteurs.
"""
from django.dispatch import receiver

from core.events import devis_accepted

from .services import create_installation_from_devis


@receiver(devis_accepted,
          dispatch_uid="installations_create_chantier_on_devis_accepted")
def _creer_chantier_on_devis_accepted(sender, devis, user, ancien_statut,
                                      **kwargs):
    """À l'acceptation d'un devis, crée son chantier UNE seule fois.

    Délègue à ``create_installation_from_devis`` qui garde l'anti-doublon
    (retourne le chantier existant le cas échéant) — donc ré-accepter ou
    ré-émettre l'événement ne crée jamais de second chantier. La société du
    chantier est celle du devis (jamais issue d'une entrée client).
    """
    company = getattr(devis, 'company', None)
    if company is None:
        return
    create_installation_from_devis(devis, user, company)
