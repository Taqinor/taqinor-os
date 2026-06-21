"""Couche d'événements métier (M6) — petit bus d'événements interne basé sur
les signaux Django, pour découpler les apps du cœur métier.

Une app émettrice (ex. ``ventes``) envoie un événement ; les apps intéressées
(``crm``, ``installations``…) s'y abonnent via un récepteur câblé dans leur
``apps.py`` (``ready()``). Cela évite qu'une app importe directement les
``models`` / ``services`` d'une autre uniquement pour réagir à un changement
d'état : l'émetteur ne connaît pas ses abonnés.

``core`` est une app de fondation : elle ne dépend d'aucune app métier, donc
placer le bus ici n'introduit aucun cycle d'import.

Événements disponibles
----------------------

``devis_accepted``
    Émis quand un devis passe à « accepté » (action explicite ``accepter``).
    Arguments du signal :

    * ``devis`` — l'instance ``Devis`` acceptée ;
    * ``user`` — l'utilisateur qui accepte (peut être ``None``) ;
    * ``ancien_statut`` — le statut du devis avant l'acceptation.
"""
import django.dispatch

# Émis à l'acceptation d'un devis.
# Abonné dans ce repo : crm (avance l'étape du lead → SIGNED).
devis_accepted = django.dispatch.Signal()

# Émis au refus d'un devis (FG44).
# Arguments : devis, user, motif_refus.
# Abonné optionnellement par crm pour marquer le lead perdu (→ COLD + perdu).
devis_refused = django.dispatch.Signal()
