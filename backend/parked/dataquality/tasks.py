"""NTDATA15/24 — jobs Beat de la qualité des données.

  * ``evaluer_qualite_donnees`` (quotidien 05:45) — évalue les règles ;
  * ``consolider_golden_records`` (hebdomadaire) — recalcule les fiches
    consolidées (NTDATA22/23). Passe LOURDE et identité stable : hebdo suffit.

NTDATA15 — job Beat quotidien d'évaluation de la qualité des données.

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


def consolider_golden_records():
    """NTDATA24 — recalcule les golden records de chaque société (hebdo).

    HEBDOMADAIRE et pas quotidien : la consolidation relit toutes les fiches
    des trois entités et rejoue la détection de doublons — c'est une passe
    lourde, et l'identité consolidée d'un client ne change pas d'un jour à
    l'autre. Le recalcul À LA DEMANDE (``POST golden-records/consolider/``)
    reste disponible pour qui veut voir l'effet d'une correction tout de suite.

    AUCUNE SOURCE N'EST MUTÉE : le job ne fait que recalculer une VUE. Chaque
    société est isolée — une erreur sur l'une n'interrompt jamais les
    suivantes. ``user=None`` comme pour l'évaluation des règles : un job n'a
    pas d'acteur, donc aucun champ sous permission ne lui est lisible.
    """
    from authentication.selectors import active_companies

    from .services import CONSOLIDATION, consolider_golden

    recap = []
    for company in active_companies():
        total = 0
        for entite in sorted(CONSOLIDATION):
            try:
                total += len(consolider_golden(company, entite, user=None))
            except Exception:  # noqa: BLE001 — une entité ne bloque pas le reste
                logger.exception(
                    'NTDATA24 : consolidation %s échouée pour la société %s',
                    entite, company.pk)
                continue
        recap.append({'company': company.pk, 'nb_golden': total})
    return recap


try:
    from celery import shared_task

    @shared_task(name='dataquality.evaluer_qualite_donnees')
    def evaluer_qualite_donnees_task():
        """Tâche Beat quotidienne (NTDATA15)."""
        evaluer_qualite_donnees()

    @shared_task(name='dataquality.consolider_golden_records')
    def consolider_golden_records_task():
        """Tâche Beat hebdomadaire (NTDATA24)."""
        consolider_golden_records()
except ImportError:  # pragma: no cover - celery absent en environnement nu
    pass
