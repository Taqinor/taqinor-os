"""Tâches planifiées (Celery beat) du module PAIE.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``) ; les
entrées ``beat_schedule`` et le routage vers la file ``scheduled`` vivent dans
``erp_agentique/celery.py`` et ``erp_agentique/settings/base.py``.

Multi-tenant : chaque balayage boucle sur les sociétés ACTIVES
(``authentication.selectors.active_companies()`` — AUD415/SCA19 : un tenant
suspendu ou en fermeture n'est plus balayé), jamais une société lue d'un corps
de requête. Une exception sur une société n'empêche jamais les suivantes
(best-effort, journalisée).

DONNÉE SENSIBLE — aucune de ces tâches ne journalise ni ne notifie un MONTANT
de salaire : les messages nomment une échéance ou un profil, jamais une somme.
"""
import logging
from datetime import timedelta

from celery import shared_task

logger = logging.getLogger(__name__)

#: Fenêtres de rappel avant la date limite d'une déclaration (J-7, J-3, J-0).
#: Chaque seuil notifie AU PLUS UNE FOIS par échéance — l'idempotence est
#: portée par une entrée de chatter ``records`` (aucun modèle paie dédié,
#: aucune migration).
SEUILS_RAPPEL_ECHEANCE = (7, 3, 0)

#: Préfixe du marqueur d'idempotence posé sur le chatter de l'échéance.
CHAMP_RAPPEL_ECHEANCE = 'rappel_echeance_j'

EVENEMENT_RAPPEL_ECHEANCE = 'paie_echeance_rappel'


def _destinataires_paie(company, event_type):
    """Destinataires d'une notification paie : ``paie_gerer`` + repli manager.

    L'UNION de deux ensembles, dédupliquée :

    * les titulaires du rôle fin ``paie_gerer`` (ce que la tâche vise) ;
    * le routage standard ``notifications.resolve_recipients`` (règles de
      routage de la société, à défaut les managers actifs) — le repli
      historique déjà utilisé par les autres notifications de la paie.
    """
    from django.contrib.auth import get_user_model

    from apps.notifications import services as notif_services

    utilisateurs = {}
    for user in notif_services.resolve_recipients(company, event_type):
        utilisateurs[user.pk] = user
    User = get_user_model()
    for user in User.objects.filter(
            company=company, is_active=True,
            role__permissions__contains=['paie_gerer']).select_related('role'):
        utilisateurs[user.pk] = user
    return list(utilisateurs.values())


def _rappel_deja_pose(echeance, seuil):
    """Vrai si le rappel de ce SEUIL a déjà été posé pour cette échéance.

    Le marqueur est une entrée de chatter ``records`` (ARC8) sur l'échéance :
    pas de modèle paie dédié, pas de migration, et la trace reste lisible par
    un humain dans l'historique de l'objet.
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Activity

    ct = ContentType.objects.get_for_model(echeance.__class__)
    return Activity.objects.filter(
        content_type=ct, object_id=echeance.pk,
        field=f'{CHAMP_RAPPEL_ECHEANCE}{seuil}',
    ).exists()


def rappeler_echeances_declaratives_company(company, *, today=None):
    """Rappels J-7/J-3/J-0 des échéances déclaratives d'UNE société (NTPAY25).

    Sélectionne les ``EcheanceDeclarative`` dont la ``date_limite`` tombe
    EXACTEMENT dans l'une des fenêtres et qui ne sont pas encore déposées
    (``statut`` ≠ déposée/payée, cf. NTPAY5). Pour chacune, notifie les
    gestionnaires de paie UNE SEULE FOIS par jour-seuil : le marqueur de
    chatter rend le re-run du lendemain (ou d'un rattrapage manuel)
    strictement sans effet.

    ``today`` est injectable (tests déterministes). Renvoie la liste des
    ``(echeance, seuil)`` réellement notifiés.
    """
    from django.utils import timezone as dj_timezone

    from apps.notifications import services as notif_services
    from apps.records import services as records_services

    from .models import EcheanceDeclarative

    if today is None:
        today = dj_timezone.localdate()

    dates_cibles = {
        today + timedelta(days=seuil): seuil
        for seuil in SEUILS_RAPPEL_ECHEANCE
    }
    echeances = (
        EcheanceDeclarative.objects
        .filter(company=company, date_limite__in=list(dates_cibles))
        .exclude(statut__in=[EcheanceDeclarative.STATUT_DEPOSEE,
                             EcheanceDeclarative.STATUT_PAYEE])
        .select_related('periode')
    )

    notifies = []
    for echeance in echeances:
        seuil = dates_cibles[echeance.date_limite]
        if _rappel_deja_pose(echeance, seuil):
            continue
        libelle = echeance.get_type_echeance_display()
        periode = echeance.periode
        quand = ("aujourd'hui" if seuil == 0 else f'dans {seuil} jour(s)')
        titre = f'Échéance paie {libelle} — à déposer {quand}'
        corps = (
            f'Période {periode.mois:02d}/{periode.annee} — date limite '
            f'{echeance.date_limite}. Aucun dépôt enregistré à ce jour.')
        try:
            notif_services.notify_many(
                _destinataires_paie(company, EVENEMENT_RAPPEL_ECHEANCE),
                EVENEMENT_RAPPEL_ECHEANCE, title=titre, body=corps,
                company=company)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'paie.rappeler_echeances_declaratives : notification échouée '
                "pour l'échéance #%s", echeance.pk, exc_info=True)
        # Le marqueur est posé MÊME si la diffusion a échoué : sans quoi un
        # canal en panne re-notifierait tous les jours la même échéance.
        records_services.log_activity(
            echeance, 'note', company=company,
            field=f'{CHAMP_RAPPEL_ECHEANCE}{seuil}',
            field_label=f'Rappel J-{seuil}',
            body=f'{titre} — {corps}')
        notifies.append((echeance, seuil))
    return notifies


#: Champ de chatter portant la trace d'un ajustement de cumul annuel.
CHAMP_AJUSTEMENT_CUMUL = 'ajustement_cumul_annuel'


def _ecarts_cumul(profil, annee):
    """Écarts entre le ``CumulAnnuel`` stocké et la somme RÉELLE des bulletins.

    Calcul PUR : aucune écriture. Renvoie ``(cumul, {champ: (ancien, reel)})``
    — le dict est vide quand le cumul est cohérent. ``cumul`` vaut ``None``
    quand aucun cumul n'existe encore pour l'année (rien à corriger : c'est
    ``recalculer_cumul_annuel`` qui le créera, jamais une dérive).
    """
    from decimal import Decimal

    from .models import BulletinPaie, CumulAnnuel
    from .services import _CUMUL_CHAMPS, _q

    cumul = CumulAnnuel.objects.filter(
        company=profil.company, profil=profil, annee=annee).first()
    if cumul is None:
        return None, {}

    reels = {champ: Decimal('0') for champ in _CUMUL_CHAMPS}
    nombre = 0
    for bulletin in BulletinPaie.objects.filter(
            company=profil.company, profil=profil, periode__annee=annee,
            statut=BulletinPaie.STATUT_VALIDE):
        nombre += 1
        for champ in _CUMUL_CHAMPS:
            reels[champ] += Decimal(getattr(bulletin, champ) or 0)

    ecarts = {}
    for champ in _CUMUL_CHAMPS:
        ancien = Decimal(getattr(cumul, champ) or 0)
        reel = _q(reels[champ])
        if ancien != reel:
            ecarts[champ] = (ancien, reel)
    if cumul.nombre_bulletins != nombre:
        ecarts['nombre_bulletins'] = (cumul.nombre_bulletins, nombre)
    return cumul, ecarts


def recalculer_cumuls_annuels_company(company, *, annee=None, today=None):
    """Corrige les ``CumulAnnuel`` EN DÉRIVE d'une société (NTPAY26).

    Un cumul peut diverger SILENCIEUSEMENT de la réalité : un bulletin validé
    après coup, un rappel rétroactif (NTPAY1) non répercuté, un import.
    Ce balayage recompare chaque cumul de l'année à la somme réelle des
    bulletins VALIDÉS et, EN CAS D'ÉCART SEULEMENT, le recalcule — en
    déposant une LIGNE D'AJUSTEMENT horodatée et motivée sur le chatter
    ``records`` du cumul (jamais une mutation silencieuse).

    Un cumul déjà cohérent n'est PAS touché : ni écriture, ni ``date_calcul``
    rafraîchie, ni ligne de trace. ``annee``/``today`` sont injectables.
    Renvoie la liste des ``(cumul, ecarts)`` corrigés.
    """
    from django.utils import timezone as dj_timezone

    from apps.records import services as records_services

    from .models import ProfilPaie
    from .services import recalculer_cumul_annuel

    if today is None:
        today = dj_timezone.localdate()
    if annee is None:
        annee = today.year

    corriges = []
    for profil in ProfilPaie.objects.filter(company=company, actif=True):
        cumul, ecarts = _ecarts_cumul(profil, annee)
        if cumul is None or not ecarts:
            continue
        detail = ' ; '.join(
            f'{champ} {ancien} → {reel}'
            for champ, (ancien, reel) in sorted(ecarts.items()))
        recalculer_cumul_annuel(profil, annee)
        records_services.log_activity(
            cumul, 'modification', company=company,
            field=CHAMP_AJUSTEMENT_CUMUL,
            field_label=f'Ajustement du cumul {annee}',
            old_value=detail,
            new_value=f'Recalculé le {today.isoformat()}',
            body=(
                f'Cumul annuel {annee} désynchronisé de la somme des '
                f'bulletins validés — recalculé. Écarts : {detail}.'))
        corriges.append((cumul, ecarts))
    return corriges


@shared_task(name='paie.recalculer_cumuls_annuels')
def recalculer_cumuls_annuels():
    """NTPAY26 — recalcul mensuel des cumuls annuels en dérive.

    Planifié à J+1 de la clôture mensuelle (le 2 du mois, la nuit) : la
    clôture de la veille a figé ses bulletins, le cumul peut donc être
    confronté à la réalité.
    """
    from authentication.selectors import active_companies

    total = 0
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        try:
            total += len(recalculer_cumuls_annuels_company(company))
        except Exception:  # noqa: BLE001 — une société ne bloque pas les autres
            logger.warning(
                'paie.recalculer_cumuls_annuels : échec pour la société #%s',
                getattr(company, 'pk', '?'), exc_info=True)
    return total


@shared_task(name='paie.rappeler_echeances_declaratives')
def rappeler_echeances_declaratives():
    """NTPAY25 — balayage quotidien des échéances déclaratives à venir.

    ``EcheanceDeclarative`` (XPAI6) suivait le calendrier mais rien ne
    prévenait PROACTIVEMENT : on découvrait le retard une fois dépassé
    (``notifier_echeances_en_retard``). Ce balayage prévient AVANT.
    """
    from authentication.selectors import active_companies

    total = 0
    for company in active_companies():  # AUD415/SCA19 — pas les suspendus
        try:
            total += len(rappeler_echeances_declaratives_company(company))
        except Exception:  # noqa: BLE001 — une société ne bloque pas les autres
            logger.warning(
                'paie.rappeler_echeances_declaratives : échec pour la '
                'société #%s', getattr(company, 'pk', '?'), exc_info=True)
    return total
