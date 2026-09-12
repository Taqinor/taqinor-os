"""NTDATA15 — job Beat quotidien d'évaluation de la qualité des données.

Balaye les sociétés OPÉRATIONNELLES (``authentication.selectors.
active_companies`` — un tenant suspendu ou en fermeture n'est jamais balayé)
et évalue leurs règles actives. Chaque société est isolée : une erreur sur
l'une n'interrompt jamais les suivantes.

LE JOB N'A PAS D'UTILISATEUR. ``user=None`` est transmis délibérément au
moteur : aucun acteur ne peut prouver une permission, donc TOUS les champs
sous permission (AUD801) restent masqués. Une règle posée sur un champ gated
ne mesure alors rien — c'est le bon défaut pour une tâche planifiée.
"""
import logging

logger = logging.getLogger(__name__)


def evaluer_qualite_donnees():
    """Évalue les règles actives de chaque société. Renvoie un récapitulatif."""
    from authentication.selectors import active_companies

    from .services import evaluer_regles

    recap = []
    for company in active_companies():
        try:
            resultats = evaluer_regles(company, user=None)
        except Exception:  # noqa: BLE001 — une société ne bloque pas les autres
            logger.exception(
                'NTDATA15 : évaluation qualité échouée pour la société %s',
                company.pk)
            continue
        recap.append({'company': company.pk, 'nb_regles': len(resultats)})
    return recap


try:
    from celery import shared_task

    @shared_task(name='dataquality.evaluer_qualite_donnees')
    def evaluer_qualite_donnees_task():
        """Tâche Beat quotidienne (NTDATA15)."""
        evaluer_qualite_donnees()
except ImportError:  # pragma: no cover - celery absent en environnement nu
    pass
