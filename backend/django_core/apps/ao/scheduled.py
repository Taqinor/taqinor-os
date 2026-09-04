"""Beat quotidien du module Appels d'offres (``apps.ao``) — AOF15.

Un dossier d'appel d'offres se perd sur une DATE, jamais sur la technique : la
remise des plis, l'ouverture et la fin de validité sont des couperets. Ce beat
balaie, par société, les ``EcheanceAO`` dont le rappel est ÉCHU et non traitée,
et pose une note au chatter générique ``records`` sur l'AO concerné.

Aucune I/O réseau ici non plus : la sélection est un calcul pur
(``services.echeances_ao_dues``) et la trace est une écriture locale. Le canal
de diffusion (courriel, notification) reste le rôle des apps dédiées, jamais
celui de ``ao``.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``) ; son
entrée ``beat_schedule`` vit dans ``erp_agentique/celery.py``.

Multi-tenant : boucle par société (``authentication.Company``, jamais une
société lue d'un corps de requête) ; une exception sur une société n'empêche
jamais les suivantes (best-effort, journalisée).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='ao.rappeler_echeances')
def rappeler_echeances():
    """AOF15 — pose un rappel au chatter pour chaque échéance d'AO due.

    Une échéance est due quand ``date_echeance - rappel_jours <= aujourd'hui``
    et qu'elle n'est pas traitée (``services.echeances_ao_dues``). Le rappel
    est IDEMPOTENT par jour : l'échéance est marquée ``traitee`` une fois le
    rappel posé, et une PROROGATION la rouvre (le service d'échéancier remet
    ``traitee=False`` quand la date change) — jamais une seconde ligne.
    """
    from authentication.models import Company

    from .services import echeances_ao_dues

    total = 0
    for company in Company.objects.all():
        try:
            dues = echeances_ao_dues(company)
        except Exception:  # noqa: BLE001 — une société ne bloque pas les autres
            logger.warning(
                'ao.rappeler_echeances : sélection échouée pour la société #%s',
                getattr(company, 'pk', '?'), exc_info=True)
            continue
        for echeance in dues:
            try:
                _poser_rappel(echeance)
                total += 1
            except Exception:  # noqa: BLE001 — best-effort par échéance
                logger.warning(
                    'ao.rappeler_echeances : rappel échoué pour '
                    "l'échéance #%s", getattr(echeance, 'pk', '?'),
                    exc_info=True)
    logger.info('ao.rappeler_echeances : %s rappel(s) posé(s)', total)
    return {'rappels': total}


#: AUD614 — cadence de la relance PROACTIVE des pièces administratives.
INTERVALLE_RELANCE_JOURS = 7


def _statuts_vivants_pour_echeancier():
    """Statuts d'AO pour lesquels un échéancier a encore un sens.

    DÉRIVÉ de ``AppelOffre.Statut`` par EXCLUSION des états terminaux : un
    dossier gagné, perdu ou abandonné n'a plus d'échéance à tenir, et lui en
    générer produirait du bruit dans les rappels du matin. Dériver plutôt que
    lister en dur garantit qu'une étape ajoutée demain sera traitée — une
    liste figée l'aurait silencieusement ignorée.
    """
    from .models import AppelOffre

    terminaux = {AppelOffre.Statut.GAGNE, AppelOffre.Statut.PERDU,
                 AppelOffre.Statut.ABANDONNE}
    return [statut for statut, _libelle in AppelOffre.Statut.choices
            if statut not in terminaux]


@shared_task(name='ao.generer_echeanciers')
def generer_echeanciers():
    """AUD614 — (re)génère l'échéancier de chaque AO VIVANT, tous les matins.

    ``services.generer_echeancier_ao`` était écrit, testé, et enveloppé dans
    ``tasks.generer_echeancier`` (par clé primaire)… mais cette enveloppe
    n'était DISPATCHÉE nulle part. Seul ``ao.rappeler_echeances`` tournait :
    il rappelait donc un échéancier qui n'existait pas — un no-op silencieux,
    la pire forme de panne (l'écran « Tâches planifiées » affichait vert).

    Cette tâche est le CHAÎNON manquant, et elle passe AVANT le rappel dans le
    beat : générer après aurait fait attendre un jour à chaque nouvelle
    échéance.

    IDEMPOTENT par construction (clé
    ``(company, appel_offre, type_echeance, libelle)``) : rejouer chaque matin
    ne crée rien sur un dossier inchangé, et DÉCALE l'échéance existante après
    une prorogation.
    """
    from authentication.models import Company

    from .models import AppelOffre
    from .services import generer_echeancier_ao

    resume = {'creees': 0, 'mises_a_jour': 0, 'inchangees': 0, 'dossiers': 0}
    vivants = _statuts_vivants_pour_echeancier()
    for company in Company.objects.all():
        affaires = AppelOffre.objects.filter(
            company=company, statut__in=vivants)
        for affaire in affaires:
            try:
                rapport = generer_echeancier_ao(affaire)
            except Exception:  # noqa: BLE001 — un AO ne bloque pas les autres
                logger.warning(
                    'ao.generer_echeanciers : AO #%s en échec',
                    getattr(affaire, 'pk', '?'), exc_info=True)
                continue
            resume['dossiers'] += 1
            for cle in ('creees', 'mises_a_jour', 'inchangees'):
                resume[cle] += rapport.get(cle, 0)
    logger.info(
        'ao.generer_echeanciers : %s dossier(s), %s échéance(s) créée(s)',
        resume['dossiers'], resume['creees'])
    return resume


@shared_task(name='ao.relancer_pieces_administratives')
def relancer_pieces_administratives():
    """AUD614 — relance PROACTIVE des pièces administratives qui vont expirer.

    ``services.pieces_administratives_a_renouveler`` n'était appelée que par
    une action GET : il fallait ALLER VOIR pour apprendre qu'une attestation
    expire — alors que les échéances d'AO, elles, sont poussées chaque matin.
    Or une attestation périmée le jour de l'ouverture fait écarter le pli :
    c'est exactement le genre d'information qui doit venir à vous.

    La trace est une note au chatter générique ``records`` sur les dossiers où
    la pièce est rattachée — même canal que ``rappeler_echeances``, jamais un
    envoi réseau depuis ``ao``.

    CADENCE : au plus une relance tous les ``INTERVALLE_RELANCE_JOURS`` jours
    par pièce (marqueur ``PieceAdministrative.derniere_relance_le``). Une pièce
    reste dans sa fenêtre de rappel 30 jours par défaut : sans cette cadence,
    elle produirait trente notes pour une seule information — c'est-à-dire un
    canal qu'on apprend à ne plus lire.
    """
    from django.utils import timezone

    from authentication.models import Company

    from .services import pieces_administratives_a_renouveler

    aujourdhui = timezone.localdate()
    total = 0
    for company in Company.objects.all():
        try:
            pieces = pieces_administratives_a_renouveler(company)
        except Exception:  # noqa: BLE001 — une société ne bloque pas les autres
            logger.warning(
                'ao.relancer_pieces_administratives : sélection échouée pour '
                'la société #%s', getattr(company, 'pk', '?'), exc_info=True)
            continue
        for piece in pieces:
            try:
                total += _relancer_piece(piece, aujourdhui)
            except Exception:  # noqa: BLE001 — best-effort par pièce
                logger.warning(
                    'ao.relancer_pieces_administratives : relance échouée '
                    'pour la pièce #%s', getattr(piece, 'pk', '?'),
                    exc_info=True)
    logger.info(
        'ao.relancer_pieces_administratives : %s relance(s) posée(s)', total)
    return {'relances': total}


def _relancer_piece(piece, aujourdhui):
    """Note chatter sur CHAQUE dossier portant la pièce. Renvoie le compte.

    Ne fait RIEN si la pièce a déjà été relancée depuis moins de
    ``INTERVALLE_RELANCE_JOURS`` jours (renvoie 0).
    """
    from datetime import timedelta

    from apps.records.services import log_note

    if piece.derniere_relance_le is not None and (
            aujourdhui - piece.derniere_relance_le
            < timedelta(days=INTERVALLE_RELANCE_JOURS)):
        return 0

    expiration = piece.date_expiration
    message = (
        f'Pièce administrative à renouveler — {piece.get_type_piece_display()} '
        f'« {piece.libelle} » expire le '
        f'{expiration.strftime("%d/%m/%Y") if expiration else "date inconnue"}.'
    )
    poses = 0
    for dossier in piece.dossiers.all():
        log_note(dossier, None, message, company=piece.company)
        poses += 1
    piece.derniere_relance_le = aujourdhui
    piece.save(update_fields=['derniere_relance_le', 'updated_at'])
    return poses


def _poser_rappel(echeance):
    """Note chatter ``records`` sur l'AO + marquage de l'échéance traitée."""
    from apps.records.services import log_note

    appel_offre = echeance.appel_offre
    libelle = echeance.libelle or echeance.get_type_echeance_display()
    log_note(
        appel_offre, None,
        f'Rappel — {libelle} le '
        f'{echeance.date_echeance.strftime("%d/%m/%Y")} '
        f'(J-{echeance.rappel_jours}).',
        company=echeance.company)
    echeance.traitee = True
    echeance.save(update_fields=['traitee', 'updated_at'])
