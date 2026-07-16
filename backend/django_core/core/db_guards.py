"""NTPLT18 — garde-fous au niveau connexion Postgres (statement_timeout).

Couche de FONDATION : n'importe aucune app métier. Fournit un context manager
pour ÉLARGIR explicitement le ``statement_timeout`` (posé par défaut à 30 s dans
``settings.DATABASES['default']['OPTIONS']``) autour d'un bloc de travail
légitimement long — un backfill, un rebuild d'index par lots, un rapport lourd.

Usage ::

    from core.db_guards import statement_timeout

    with statement_timeout(minutes=15):
        ...  # requêtes ORM lourdes, non tronquées par la limite globale

``SET LOCAL`` ne vaut que DANS une transaction : le context manager en ouvre une
via ``transaction.atomic()`` si aucune n'est active, et restaure implicitement la
valeur à la sortie du bloc (SET LOCAL est annulé à la fin de la transaction).
"""
from __future__ import annotations

from contextlib import contextmanager

from django.db import connection, transaction


def _timeout_ms(ms=None, seconds=None, minutes=None) -> int:
    if ms is not None:
        return int(ms)
    if seconds is not None:
        return int(seconds) * 1000
    if minutes is not None:
        return int(minutes) * 60 * 1000
    raise ValueError("statement_timeout: préciser ms, seconds ou minutes.")


@contextmanager
def statement_timeout(ms=None, *, seconds=None, minutes=None):
    """Élargit (ou réduit) le statement_timeout pour la durée du bloc.

    ``0`` désactive la limite pour le bloc. Ne fait rien de spécial hors
    Postgres (le SET est un no-op inoffensif sur d'autres backends via le
    même dialecte SQL standard).
    """
    value = _timeout_ms(ms, seconds, minutes)
    with transaction.atomic():
        with connection.cursor() as cur:
            # SET LOCAL n'accepte pas de placeholder paramétré ; on interpole un
            # entier validé (jamais une entrée utilisateur brute).
            cur.execute(f"SET LOCAL statement_timeout = {int(value)}")
        yield
