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
import logging
from typing import NamedTuple
from zoneinfo import ZoneInfo

from . import calendar_utils

logger = logging.getLogger(__name__)

# Fenêtre "jour" par défaut (heure locale serveur) : 08h00-20h00 inclus.
_HEURE_DEBUT_JOUR = 8
_HEURE_FIN_JOUR = 20

# ── N1 — fenêtre de NOTIFICATION d'une société (décision fondateur 25/09/2026)
#
# « Les notifications ne doivent pas être à minuit ni à 23 h. Garde toutes les
# notifications importantes mais place-les aux heures de travail. » La fenêtre
# n'est PAS une seconde table d'horaires : c'est la fenêtre des MESSAGES de la
# société, telle que `apps.crm.horaires` la calcule déjà (ouverture
# `message_heure_debut`, fermeture `appel_heure_fin`, jours ouvrés et fériés de
# `calendar_utils`, Ramadan saisi par la société). Une notification suit donc
# exactement le même rythme qu'un WhatsApp au client.

#: Le canal dont la fenêtre borne les notifications internes : un MESSAGE
#: (silencieux, pas de pause du vendredi), jamais la fenêtre d'appel.
CANAL_NOTIFICATIONS = 'whatsapp'

#: Repli best-effort quand `crm.horaires` est illisible : 08:30-19:00, jours
#: ouvrés. Ne sert qu'en cas de panne — jamais une règle concurrente.
REPLI_OUVERTURE = datetime.time(8, 30)
REPLI_FERMETURE = datetime.time(19, 0)
_CASABLANCA = ZoneInfo('Africa/Casablanca')
_REPLI_MAX_JOURS = 15


class FenetreNotifications(NamedTuple):
    """N1 — ``ouverte`` : une notification émise à cet instant part tout de
    suite ; sinon ``prochaine_ouverture`` est l'instant (aware) où elle doit
    être livrée. Quand la fenêtre est ouverte, ``prochaine_ouverture`` vaut
    l'instant demandé."""
    ouverte: bool
    prochaine_ouverture: datetime.datetime


def _jour_ouvre_repli(d, company):
    try:
        return calendar_utils.is_jour_ouvre(d, company)
    except Exception:  # noqa: BLE001 — repli du repli : lundi-vendredi
        return d.weekday() < 5


def _fenetre_repli(company, maintenant):
    """N1 — 08:30-19:00 jours ouvrés, Africa/Casablanca. Best-effort : si
    aucun jour ouvré n'est trouvé sur 15 jours, la fenêtre est déclarée
    OUVERTE (une notification n'est jamais bloquée par une panne)."""
    tz_entree = maintenant.tzinfo or datetime.timezone.utc
    if maintenant.tzinfo is None:
        maintenant = maintenant.replace(tzinfo=datetime.timezone.utc)
    local = maintenant.astimezone(_CASABLANCA)
    for decalage in range(_REPLI_MAX_JOURS):
        jour = local.date() + datetime.timedelta(days=decalage)
        if not _jour_ouvre_repli(jour, company):
            continue
        ouverture = datetime.datetime.combine(
            jour, REPLI_OUVERTURE, tzinfo=_CASABLANCA)
        fermeture = datetime.datetime.combine(
            jour, REPLI_FERMETURE, tzinfo=_CASABLANCA)
        if decalage == 0:
            if ouverture <= local < fermeture:
                return FenetreNotifications(True, maintenant)
            if local >= fermeture:
                continue
        return FenetreNotifications(False, ouverture.astimezone(tz_entree))
    return FenetreNotifications(True, maintenant)


def fenetre_notifications(company, maintenant=None):
    """N1 — la fenêtre de notification de ``company`` à ``maintenant``.

    Renvoie un ``FenetreNotifications(ouverte, prochaine_ouverture)``. La
    fenêtre est celle des MESSAGES de la société
    (``crm.horaires.prochain_creneau_appel(..., canal='whatsapp')``) : jours
    ouvrés, jours fériés et Ramadan compris, rien n'est réécrit ici. Si les
    horaires sont illisibles, repli 08:30-19:00 jours ouvrés. Jamais
    d'exception : au pire la fenêtre est déclarée ouverte.

    ``notifications`` est une app satellite : elle lit ``crm.horaires``
    (module PUR, sans modèle) par un import local, comme ``sweeps.py``."""
    from django.utils import timezone
    maintenant = maintenant or timezone.now()
    if timezone.is_naive(maintenant):
        maintenant = timezone.make_aware(maintenant, datetime.timezone.utc)
    try:
        from apps.crm import horaires
        prochaine = horaires.prochain_creneau_appel(
            maintenant, company, canal=CANAL_NOTIFICATIONS)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning(
            'notifications: fenêtre de la société %s illisible, repli '
            '08:30-19:00', getattr(company, 'pk', '?'), exc_info=True)
        try:
            return _fenetre_repli(company, maintenant)
        except Exception:  # noqa: BLE001 — ne jamais bloquer une notification
            return FenetreNotifications(True, maintenant)
    if prochaine is None or prochaine <= maintenant:
        return FenetreNotifications(True, maintenant)
    return FenetreNotifications(False, prochaine)


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
        # N1 — une mention émise la nuit n'existe pour son destinataire qu'à
        # sa livraison (`programmee_pour` remis à NULL par le balayage).
        programmee_pour__isnull=True,
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


def superior_contact_status(company, link):
    """VX215 — boucle de retour « pris en charge » (version lecture seule) :
    l'état `read` des `Notification` déjà émises pour un `link` donné (ex.
    ``/ventes/devis?devis=<id>`` après « Contacter mon supérieur »), SANS
    jamais exposer le contenu (titre/corps) des notifications d'autrui —
    seulement si elles ont été vues et par qui. Point d'entrée cross-app
    LECTURE SEULE (jamais un import de ``notifications.models`` ailleurs).

    Renvoie ``{'requested': False}`` si aucune notification ne porte ce
    ``link`` pour cette société, sinon ``{'requested': True, 'seen': bool,
    'seen_by': [username, ...], 'requested_at': datetime}`` (le plus
    ancien lecteur en tête n'est pas garanti — l'ordre suit la création des
    notifications, pas la lecture)."""
    if company is None or not link:
        return {'requested': False}
    from .models import EventType, Notification
    notifs = list(
        Notification.objects.filter(
            company=company,
            event_type=EventType.DEVIS_SUPERIOR_CONTACT_REQUESTED,
            link=link,
        ).select_related('recipient').order_by('-created_at'))
    if not notifs:
        return {'requested': False}
    seen_by = [n.recipient.username for n in notifs if n.read]
    return {
        'requested': True,
        'seen': bool(seen_by),
        'seen_by': seen_by,
        'requested_at': notifs[-1].created_at,
    }


def holidays_for_export(company):
    """NTI18N45 — toutes les lignes ``Holiday`` d'une société, triées par
    pays puis date, sous forme de dicts ``{pays, date, nom,
    recurrent_annuel}``. Point d'entrée cross-app en LECTURE SEULE pour
    l'export CSV (``apps.dataimport.holidays_import``) — jamais un import
    direct de ``notifications.models`` ailleurs."""
    if company is None:
        return []
    from .models import Holiday
    return list(
        Holiday.objects.filter(company=company)
        .order_by('pays', 'date')
        .values('pays', 'date', 'nom', 'recurrent_annuel'))


def upsert_holiday(company, *, pays, date, nom, recurrent_annuel=False):
    """NTI18N45 — upsert IDEMPOTENT d'un jour férié, clé ``(company, pays,
    date)`` — jamais ``(company, date, nom)`` : rejouer un import ne doit
    jamais créer de doublon même si le libellé a légèrement changé entre
    deux imports (critère d'acceptation du plan). Point d'entrée cross-app
    en ÉCRITURE pour l'import CSV (``apps.dataimport.holidays_import``) —
    jamais un import direct de ``notifications.models`` ailleurs.

    Peut lever ``django.db.IntegrityError`` si un AUTRE jour férié porte
    déjà EXACTEMENT ce libellé à cette date (contrainte ``(company, date,
    nom)`` antérieure à ce module, non couverte par la clé pays+date) —
    laissé à l'appelant, qui journalise la ligne en erreur sans jamais
    faire échouer l'import entier.

    Renvoie ``(holiday, cree)``."""
    from .models import Holiday
    return Holiday.objects.update_or_create(
        company=company, pays=pays, date=date,
        defaults={'nom': nom, 'recurrent_annuel': bool(recurrent_annuel)})


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
