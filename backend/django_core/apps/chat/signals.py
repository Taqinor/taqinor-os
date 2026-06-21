"""S9 — point d'accroche des notifications de la messagerie.

Les notifications de nouveau message sont émises explicitement par
`services.create_message` (via `transaction.on_commit`) plutôt que par un signal
`post_save`, afin de connaître les @mentions résolues et la sourdine par membre.

Ce module existe pour rester cohérent avec la convention des autres apps
(`apps.py.ready()` importe `signals`) et offrir un point d'extension futur. Il
n'enregistre aucun récepteur aujourd'hui — toute la logique vit dans
`services._notify_new_message`.
"""
