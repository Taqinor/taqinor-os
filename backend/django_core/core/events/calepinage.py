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

# ACAL2010 (D-ACAL-97, « un seul moteur ») — Émis par le calepinage quand une
# POSE est enregistrée avec une empreinte NOUVELLE (la pose est une entrée du
# moteur unique) — jamais pour un enregistrement à empreinte inchangée.
# Émetteur prévu : ACAL2011 (calepinage). Arguments : ``company_id``,
# ``calepinage_id``, ``lead_id`` (entiers ; ``lead_id`` peut valoir ``None`` :
# un calepinage sans lead porte lui-même sa conception) et ``empreinte_pose``
# (texte, l'empreinte de la pose enregistrée). Abonné prévu : ventes, qui
# relance la conception (ADEV139) ; d'ici là, réservé dans
# ``core.event_coverage.ALLOWED_UNCONSUMED``. Aucun statut ne bouge.
pose_enregistree = django.dispatch.Signal()

__all__ = [
    'calepinage_simule',
    'pose_enregistree',
]
