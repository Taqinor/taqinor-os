"""NTAI30 — job Beat de matérialisation du feature store léger.

Balaye les sociétés OPÉRATIONNELLES (``authentication.selectors.
active_companies`` — un tenant suspendu n'est jamais balayé) et matérialise
leur ``FeatureVector``. Chaque société est isolée : une erreur sur l'une
n'interrompt jamais les suivantes.

LE JOB N'A PAS D'UTILISATEUR (``user=None``) : aucun acteur ne peut prouver
une permission, donc tout champ sous permission (AUD801) reste masqué côté
sélecteur — c'est le bon défaut pour une tâche planifiée.
"""
import logging

logger = logging.getLogger(__name__)


def recompute_features_all_companies():
    """Recalcule le feature store de chaque société active. Renvoie un
    récapitulatif ``[{'company': id, 'nb_vecteurs': int}, ...]``."""
    from authentication.selectors import active_companies

    from .services import recompute_features

    recap = []
    for company in active_companies():
        try:
            nb = recompute_features(company, user=None)
        except Exception:  # noqa: BLE001 — une société ne bloque pas les autres
            logger.exception(
                'NTAI30 : recalcul des features échoué pour la société %s',
                company.pk)
            continue
        recap.append({'company': company.pk, 'nb_vecteurs': nb})
    return recap


try:
    from celery import shared_task

    @shared_task(name='mlops.recompute_features')
    def recompute_features_task():
        """Tâche Beat quotidienne (NTAI30)."""
        recompute_features_all_companies()
except ImportError:  # pragma: no cover - celery absent en environnement nu
    pass
