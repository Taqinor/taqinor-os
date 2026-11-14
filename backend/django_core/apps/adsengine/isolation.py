"""ACEL71 — isolation par société / par ad des tâches Celery : un
``except Exception`` d'isolation n'avale JAMAIS le délai souple de Celery
(``SoftTimeLimitExceeded`` hérite d'``Exception``)."""
from celery.exceptions import SoftTimeLimitExceeded


def relever_si_delai(exc):
    """À appeler en tête d'un ``except Exception as exc`` d'isolation : relève
    ``SoftTimeLimitExceeded`` (la tâche s'arrête), laisse passer le reste."""
    if isinstance(exc, SoftTimeLimitExceeded):
        raise exc


def degrader(exc):
    """ACEL81 — relève le délai souple, sinon rend ``exc`` pour ``exc_info=``
    du ``logger.warning`` d'isolation (mode dégradé journalisé)."""
    relever_si_delai(exc)
    return exc
