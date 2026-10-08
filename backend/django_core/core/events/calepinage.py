"""Signaux du bus du calepinage (propriétaire calepinage).

SPL290 — extrait de ``core/events/__init__.py`` (move only). Ré-exporté
par ``from .calepinage import *`` dans ``core/events/__init__.py`` :
les émetteurs et abonnés continuent d'importer ``core.events``.
"""
import django.dispatch


# CALX368 — Émis par ``apps.calepinage.services.simulation.simuler_calepinage``
# (le SEUL chemin qui lance une simulation, D-CALX 4) quand une simulation a
# RÉELLEMENT abouti et que son résultat vient d'être fusionné dans
# ``Calepinage.resultat`` — jamais pour un « déjà calculé » (empreinte
# inchangée), jamais pour une simulation refusée, jamais pour un calcul à
# blanc (``enregistrer=False``). Ce n'est PAS un changement de statut (règle
# #4) : le calepinage reste où il est.
# Arguments : ``calepinage`` (l'instance, résultat déjà fusionné) et
# ``company_id`` (ENTIER — la société du calepinage, lue sans requête).
# Abonné dans ce repo : ``apps.publicapi`` (``calepinage_event_receivers``,
# webhook sortant ``calepinage.simule``) — ainsi ``apps.calepinage`` ne
# connaît pas l'API publique, et ``apps.publicapi`` n'importe jamais
# ``apps.calepinage``.
calepinage_simule = django.dispatch.Signal()

__all__ = [
    'calepinage_simule',
]
