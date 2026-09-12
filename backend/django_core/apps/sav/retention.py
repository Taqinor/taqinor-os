"""NTGRC4 — politique de rétention SAV pilotée par `grc.PolitiqueRetentionObjet`.

Le SAV expose le type d'objet ``sav_ticket`` en **signalement seul**. Un
ticket ne porte AUCUNE donnée personnelle en propre : l'identité vit sur le
client CRM, qui a sa PROPRE politique (``crm_client``) — c'est elle qui
anonymise la personne. Anonymiser ici en plus détruirait de l'historique
technique (symptôme, diagnostic, pièces posées) sans rien gagner côté vie
privée, et fausserait les statistiques de garantie.

Le balayage COMPTE donc les tickets hors fenêtre de conservation et le
rapporte au DPO ; il ne modifie jamais rien, même avec ``--commit``.
"""
from __future__ import annotations

TYPES = ('sav_ticket',)

MOTIF_NON_APPLICABLE = (
    "La donnée personnelle d'un ticket vit sur le client CRM, qui a sa propre "
    "politique de rétention : le SAV signale les tickets échus sans toucher à "
    "leur historique technique."
)


def _echus(politique, now):
    """Tickets échus pour CETTE politique (bornés à sa société)."""
    from django.utils import timezone

    from .models import Ticket

    cutoff = now - timezone.timedelta(days=politique['jours'])
    return Ticket.objects.filter(
        company=politique['company'], date_creation__lt=cutoff)


def sweep_objets(now, apply_):
    """Compte les tickets hors fenêtre de conservation. Ne modifie rien."""
    from apps.grc.selectors import politiques_retention_actives

    total = 0
    for politique in politiques_retention_actives(TYPES):
        total += _echus(politique, now).count()
    return total


def register():
    """Enregistre la politique SAV (idempotent, appelée en ready())."""
    from core.retention import register_retention_policy

    register_retention_policy('sav_tickets_echus', sweep_objets)
