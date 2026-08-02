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
