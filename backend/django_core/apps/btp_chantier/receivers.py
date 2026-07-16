"""Abonnements de ``btp_chantier`` aux signaux d'autres apps.

NTCON5 branchera ici la ré-ouverture automatique d'un ``VisaDocument`` quand
une nouvelle ``ged.DocumentVersion`` est déposée sur le document visé —
connexion PARESSEUSE via ``django.apps.apps.get_model`` dans ``connect_
signals()`` (appelé depuis ``apps.py::ready()``), jamais un import statique
de ``ged.models``.
"""


def connect_signals():
    """Point d'entrée appelé depuis ``BtpChantierConfig.ready()``.

    Vide tant qu'aucune tâche n'a encore câblé de signal (NTCON5 le remplira).
    """
    return None


connect_signals()
