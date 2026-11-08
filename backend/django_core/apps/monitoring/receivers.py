"""ARC36 — récepteurs du satellite monitoring sur le bus ``core.events``.

``abonnement_monitoring_resilie`` (YSUBS4) est émis par
``apps.monitoring.services.resilier_abonnement_monitoring`` (ASAV100 — l'ancien
émetteur ``compta.services`` est parqué) quand un abonnement de supervision est
résilié depuis l'écran SAV/monitoring. Effet aval DÉCOUPLÉ ici : couper la supervision
automatique du système lié (``MonitoringConfig.enabled=False`` pour
``abonnement.installation_id``) — le client ne paie plus, on arrête la
synchro fournisseur. ``monitoring`` n'importe JAMAIS ``compta`` :
l'abonnement transite par les arguments du signal, et on s'abonne par NOM de
signal (l'émetteur bougera avec ODX16/17-20 sans nous casser). Idempotent :
une config déjà coupée (ou absente) → no-op strict. Additif : aucun statut
d'abonnement modifié ici (la transition est déjà actée côté compta).
"""
import logging

from django.dispatch import receiver

from core.events import (
    abonnement_monitoring_resilie, chantier_receptionne, equipement_remplace,
)

logger = logging.getLogger(__name__)


@receiver(abonnement_monitoring_resilie,
          dispatch_uid="monitoring_arret_supervision_resiliation")
def _arreter_supervision_a_la_resiliation(sender, abonnement, motif, company,
                                          **kwargs):
    from .models import MonitoringConfig

    installation_id = getattr(abonnement, 'installation_id', None)
    if not installation_id:
        return
    MonitoringConfig.objects.filter(
        company=company, installation_id=installation_id, enabled=True,
    ).update(enabled=False)
    # AMON10 — plus aucun abonnement actif : l'épisode ouvert est clos.
    from apps.installations import selectors as installations_selectors

    from .selectors import supervision_resiliee
    from .services import MOTIF_SUPERVISION_RESILIEE, _fermer_episode
    installation = installations_selectors.installation_scoped(
        company, installation_id)
    if installation is not None and supervision_resiliee(installation):
        _fermer_episode(installation, MOTIF_SUPERVISION_RESILIEE,
                        'Supervision résiliée : système plus évalué.')


@receiver(chantier_receptionne,
          dispatch_uid="monitoring_seed_expected_kwh_reception")
def _semer_attendu_a_reception(sender, installation, user, ancien_statut,
                               **kwargs):
    """YSERV8 — à la réception d'un chantier (événement YSERV4), sème la
    production attendue du monitoring depuis le PR de recette FG278 ou l'étude
    du devis. ``monitoring`` est satellite : on s'abonne par NOM de signal et on
    lit les données ventes via ``services`` (jamais un import ventes.models).
    Idempotent et non destructif : une valeur déjà saisie n'est jamais écrasée.
    """
    if installation is None or getattr(installation, 'pk', None) is None:
        return
    from .services import seed_expected_annual_kwh

    # Best-effort : un semis de production attendue ne doit JAMAIS casser la
    # réception d'un chantier (les abonnés de core.events sont synchrones —
    # une exception ici remonterait à l'émetteur). On avale/loggue.
    try:
        seed_expected_annual_kwh(installation)
    except Exception:  # effet aval best-effort, jamais bloquant
        logger.warning(
            'YSERV8 : semis production attendue ignoré pour installation %s',
            getattr(installation, 'pk', '?'), exc_info=True)


@receiver(equipement_remplace,
          dispatch_uid="monitoring_fin_episode_remplacement")
def _clore_episode_au_remplacement(sender, equipement, ticket, company, user,
                                   **kwargs):
    """AMON4 — un équipement du système est remplacé (``retirer_piece``) :
    l'épisode de sous-performance ouvert est clos (motif
    ``equipement_remplace``) ; l'évaluation repart du remplacement. Best-effort
    (patron ``_semer_attendu_a_reception``) : jamais bloquant pour le SAV."""
    installation_id = getattr(equipement, 'installation_id', None)
    if not installation_id:
        return
    from .services import MOTIF_EQUIPEMENT_REMPLACE, _fermer_episode
    try:
        _fermer_episode(
            installation_id, MOTIF_EQUIPEMENT_REMPLACE,
            'Équipement remplacé (ticket '
            f'{getattr(ticket, "reference", "")}) : évaluation repartie '
            'du remplacement.')
    except Exception:  # effet aval best-effort, jamais bloquant
        logger.warning(
            'AMON4 : clôture de l’épisode ignorée pour installation %s',
            installation_id, exc_info=True)
