"""Attente de CONDITION pour les tests de course à deux connexions réelles.

Une transaction A qui tient un verrou attend que B soit RÉELLEMENT bloqué en
base sur ce verrou avant de commiter — jamais un délai arbitraire
(``time.sleep`` / ``Event().wait(n)``, refusés par
``scripts/check_test_determinism.py``). Patron de
``apps/ventes/tests/test_qjr223_overrides_concurrence.py`` (``pg_locks``),
restreint aux attentes que la connexion COURANTE provoque
(``pg_blocking_pids``) : un test parallèle d'une autre base ne compte pas.
"""
import threading
import time

from django.db import connection

_BLOQUE_PAR_MOI = (
    'SELECT count(*) FROM pg_locks WHERE NOT granted '
    'AND pg_backend_pid() = ANY(pg_blocking_pids(pid))')


def attendre_un_ecrivain_bloque(ou_bien=None, limite_s=10):
    """True dès qu'une autre connexion attend un verrou tenu par la
    transaction courante (ou dès que l'``Event`` ``ou_bien`` est signalé) ;
    False à l'échéance — les assertions du test disent alors pourquoi."""
    pacage = threading.Event()  # jamais signalé : régulateur de boucle
    echeance = time.monotonic() + limite_s
    while time.monotonic() < echeance:
        if ou_bien is not None and ou_bien.is_set():
            return True
        with connection.cursor() as curseur:
            curseur.execute(_BLOQUE_PAR_MOI)
            if curseur.fetchone()[0]:
                return True
        pacage.wait(0.02)
    return False
