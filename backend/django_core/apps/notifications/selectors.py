"""Selectors de lecture cross-app pour ``apps.notifications`` (XMKT7).

Point d'entrée unique pour les autres apps qui ont besoin de savoir si un
moment donné tombe dans une « fenêtre de silence » d'envoi marketing — jamais
d'import direct de ``notifications.models`` (WorkingHoursConfig/Holiday)
ailleurs. Réutilise ``calendar_utils.is_jour_ouvre`` (jours fériés + jours
ouvrés de la société) et ajoute une fenêtre horaire nocturne fixe (08h–20h)
puisque ``WorkingHoursConfig`` ne porte pas d'heures de coupure configurables
aujourd'hui — ADDITIF, sans configuration le comportement par défaut n'exclut
QUE la nuit stricte + les jours fériés/non-ouvrés.
"""
from __future__ import annotations

import datetime

from . import calendar_utils

# Fenêtre "jour" par défaut (heure locale serveur) : 08h00-20h00 inclus.
_HEURE_DEBUT_JOUR = 8
_HEURE_FIN_JOUR = 20


def mentions_non_lues(user, company):
    """VX83 — Notifications de MENTION non lues d'un utilisateur (``chat_mention``),
    plus récentes d'abord. Point d'entrée cross-app LECTURE SEULE pour que
    « Ma file » (``apps.records``) liste les mentions non lues avec leur
    ``link`` sans importer ``notifications.models``. Scopé société : jamais une
    mention d'une autre société. Renvoie un queryset (éventuellement vide).
    """
    from .models import EventType, Notification
    qs = Notification.objects.filter(
        recipient=user, read=False,
        event_type=EventType.CHAT_MENTION,
    )
    if company is not None:
        qs = qs.filter(company=company)
    return qs.order_by('-created_at', '-id')


def escalade_state_pour(instance):
    """VX218 — état de relance/escalade YEVNT9 (``ApprovalReminderState``)
    d'UNE approbation en attente, générique via content-type — jamais un
    import de ``notifications.models`` ailleurs.

    Renvoie ``(niveau_label, derniere_relance_le)`` où ``niveau_label`` est
    ``None`` (jamais relancé), ``'relance'`` (palier 1) ou ``'escalade'``
    (palier 2). Ne FABRIQUE rien : une instance sans ligne d'état connue
    (jamais balayée, ou décidée puis état non nettoyé) renvoie ``(None,
    None)``. Best-effort : toute erreur (content-type absent, etc.) renvoie
    aussi ``(None, None)`` plutôt qu'une exception qui casserait l'agrégateur
    appelant."""
    try:
        from django.contrib.contenttypes.models import ContentType

        from .models import ApprovalReminderState
        ct = ContentType.objects.get_for_model(instance.__class__)
        state = ApprovalReminderState.objects.filter(
            content_type=ct, object_id=instance.pk).first()
    except Exception:  # pragma: no cover - défensif
        return (None, None)
    if state is None or not state.palier:
        return (None, None)
    label = 'escalade' if state.palier >= 2 else 'relance'
    return (label, state.derniere_action_le)


def approbations_snoozees_actives(user, company):
    """VX210(b) — ensemble de ``(source, str(object_id))`` actuellement
    snoozés par ``user`` (``SnoozedItem.snoozed_until`` strictement dans le
    futur — le jour même, l'item redevient visible, même sémantique que
    ``records.Activity.snoozed_until`` VX85). Point d'entrée cross-app
    LECTURE SEULE pour que « Ma file » (``apps.records.views.ma_file``)
    masque ces items SANS jamais importer ``notifications.models`` — jamais
    un import de son ``models`` ailleurs."""
    if company is None:
        return set()
    from .models import SnoozedItem
    today = datetime.date.today()
    qs = SnoozedItem.objects.filter(
        user=user, company=company, snoozed_until__gt=today,
    ).values_list('source', 'object_id')
    return {(src, str(oid)) for src, oid in qs}


def est_hors_fenetre_silence(moment, company) -> bool:
    """Renvoie True si ``moment`` (datetime) tombe DANS la fenêtre de silence
    (nuit ou jour férié/non-ouvré) — c-à-d qu'un SMS/WhatsApp ne DOIT PAS
    partir à ce moment pour ``company``.

    ``moment`` naïf ou aware, seule l'heure locale (``moment.hour``) et la
    date (``moment.date()``) comptent.
    """
    if moment is None:
        return False
    d = moment.date() if isinstance(moment, datetime.datetime) else moment
    if not calendar_utils.is_jour_ouvre(d, company):
        return True
    if isinstance(moment, datetime.datetime):
        heure = moment.hour
        if heure < _HEURE_DEBUT_JOUR or heure >= _HEURE_FIN_JOUR:
            return True
    return False
