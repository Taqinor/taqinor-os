"""NTEDU13 — notification parent sur absence.

Signal ``post_save`` sur ``Presence`` : quand une présence est enregistrée
avec le statut ``absent``, notifie la famille le jour même via l'app
``notifications`` (service, jamais un import de modèle). Anti-doublon : une
seule notification par élève et par jour, même si plusieurs séances du même
jour sont marquées absentes.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='education.Presence')
def notifier_absence(sender, instance, created, **kwargs):
    from .models import Presence

    if instance.statut != Presence.Statut.ABSENT:
        return

    # Anti-doublon : UNE notification par élève/jour, quel que soit le
    # nombre de séances absentes ce jour-là. Règle déterministe : on notifie
    # uniquement quand ``instance`` EST la présence absente la plus ancienne
    # (id le plus bas) du jour pour cet élève — la 2e/3e séance absente du
    # même jour ne renvoie jamais rien (aucun compteur/flag supplémentaire
    # à maintenir).
    premiere_absence_du_jour = Presence.objects.filter(
        eleve=instance.eleve, seance__date=instance.seance.date,
        statut=Presence.Statut.ABSENT,
    ).order_by('id').first()
    if premiere_absence_du_jour is None or premiere_absence_du_jour.pk != instance.pk:
        return

    _notifier_famille_absence(instance)


def _notifier_famille_absence(presence):
    """Best-effort, jamais bloquant (comme ``notifications.services.notify``)."""
    famille = presence.eleve.famille
    recipient = famille.parent1_whatsapp or famille.parent1_telephone
    if not recipient:
        return
    try:
        from apps.notifications.services import send_whatsapp_campaign_message
        send_whatsapp_campaign_message(
            presence.company,
            recipient=recipient,
            body=(
                f"Bonjour {famille.parent1_nom or famille.nom}, votre enfant "
                f"{presence.eleve} a été marqué(e) absent(e) aujourd'hui "
                f"({presence.seance.date}). Merci de contacter "
                "l'administration en cas de justificatif."),
        )
    except Exception:  # pragma: no cover - défensif
        pass


# =============================================================================
# NTEDU27/NTEDU30 — notification parent sur incident disciplinaire.
# =============================================================================
#
# NTEDU30 (« notifications parents automatiques via WhatsApp », COST-gated
# GATED-founder) est déjà satisfait PAR CONSTRUCTION ici : ce signal réutilise
# EXACTEMENT le même canal que ``notifier_absence`` ci-dessus —
# ``apps.notifications.services.send_whatsapp_campaign_message`` →
# ``notifications.whatsapp_bsp.get_whatsapp_provider()``. Sans
# ``WHATSAPP_BSP_ENABLED=1`` + credentials complets, le provider retombe
# TOUJOURS sur ``ManualWaMeProvider`` (lien wa.me, ZÉRO appel réseau) — le
# flag COST-gated demandé par le plan est donc déjà celui posé par QJ23/FG33,
# jamais un second flag dupliqué (« ne jamais hand-rolle un substitut local
# d'une primitive déjà posée »).

@receiver(post_save, sender='education.IncidentDiscipline')
def notifier_incident_discipline(sender, instance, created, **kwargs):
    """NTEDU27 — un incident ``majeur`` notifie TOUJOURS le parent à la
    création ; un incident ``mineur`` ne notifie que si l'école l'a activé
    (``ParametresEducation.notifier_incidents_mineurs``). ``moyen`` ne
    notifie jamais (hors périmètre du critère d'acceptation)."""
    from .models import IncidentDiscipline

    if not created:
        return
    if instance.gravite == IncidentDiscipline.Gravite.MAJEUR:
        _notifier_famille_incident(instance)
    elif instance.gravite == IncidentDiscipline.Gravite.MINEUR:
        from .models import ParametresEducation

        if ParametresEducation.get(instance.company).notifier_incidents_mineurs:
            _notifier_famille_incident(instance)


def _notifier_famille_incident(incident):
    """Best-effort, jamais bloquant (comme ``_notifier_famille_absence``)."""
    famille = incident.eleve.famille
    recipient = famille.parent1_whatsapp or famille.parent1_telephone
    if not recipient:
        return
    try:
        from apps.notifications.services import send_whatsapp_campaign_message
        send_whatsapp_campaign_message(
            incident.company,
            recipient=recipient,
            body=(
                f"Bonjour {famille.parent1_nom or famille.nom}, un incident "
                f"({incident.get_type_display()}) a été signalé pour "
                f"{incident.eleve} le {incident.date}. Merci de contacter "
                "l'administration."),
        )
    except Exception:  # pragma: no cover - défensif
        pass
