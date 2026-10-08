"""Signaux du bus des chantiers (propriétaire chantiers).

SPL290 — extrait de ``core/events/__init__.py`` (move only). Ré-exporté
par ``from .chantiers import *`` dans ``core/events/__init__.py`` :
les émetteurs et abonnés continuent d'importer ``core.events``.

Événements
----------

``chantier_receptionne``
    Émis quand une ``installations.Installation`` atteint le statut canonique
    RECEPTIONNE (YSERV4) — aux DEUX sites où ce jalon peut être atteint :
    ``InstallationViewSet.perform_update`` et l'action ``mise-en-service``
    (celle-ci se rabat sur RECEPTIONNE, même patron que ``_apply_reception_
    handover``). Émis SYNCHRONE, best-effort, uniquement sur le FRANCHISSEMENT
    (``ancien_statut`` canonique différent de RECEPTIONNE) — un re-passage ne
    réémet rien. Ne change AUCUN statut (l'émission suit la bascule déjà
    actée). Abonné dans ce repo : ``compta`` (``apps/compta/receivers.py``) —
    crée idempotemment une ``EnqueteNPS`` pour le client du chantier (une
    enquête par chantier, jamais de doublon même en cas de ré-émission) et
    appelle ``envoyer_enquete_nps`` (no-op sans clé Brevo, comportement FG238
    inchangé). ``installations`` n'importe jamais la comptabilité — même
    patron que ``devis_accepted`` → ``crm``. Arguments du signal :

    * ``installation`` — l'instance ``installations.Installation`` désormais
      RECEPTIONNE ;
    * ``user`` — l'utilisateur qui a déclenché la transition (peut être
      ``None``) ;
    * ``ancien_statut`` — le statut BRUT (non canonicalisé) avant la
      transition.
"""
import django.dispatch


# Émis quand une Intervention (apps.installations) passe à TERMINEE ou VALIDEE
# (YSERV2). Arguments : intervention, company, user (peut être None). Abonné
# dans ce repo : sav (apps/sav/receivers.py) — si l'intervention porte un
# ticket lié, pose Ticket.date_resolution et avance le ticket vers RESOLU
# (idempotent, ne recule jamais un statut). installations n'importe jamais
# apps.sav — même patron que devis_accepted → crm.
intervention_completed = django.dispatch.Signal()

# Émis à l'annulation d'un chantier (``apps.installations``) — YSERV9.
# Arguments : installation (installations.Installation), user (peut être
# None), company. NE change JAMAIS un statut devis/facture (règle #4,
# STATUT PRESERVATION) : simple signal d'exception pour que ``ventes`` pose
# une activité/alerte au responsable (décider avoir vs retenue sur un
# acompte déjà encaissé). Abonné dans ce repo : ventes
# (``apps/ventes/receivers.py``), qui pose une ``DevisActivity`` de type NOTE
# sur le devis lié au chantier quand il existe. ``installations`` n'importe
# jamais ``apps.ventes`` — même patron que ``devis_accepted`` → installations.
chantier_annule = django.dispatch.Signal()

# Émis quand une Installation atteint le statut canonique RECEPTIONNE
# (YSERV4). Arguments : installation, user (peut être None), ancien_statut.
# Abonné dans ce repo : compta (crée l'EnqueteNPS + envoyer_enquete_nps,
# idempotent) — voir docstring du module ci-dessus.
chantier_receptionne = django.dispatch.Signal()

__all__ = [
    'intervention_completed',
    'chantier_annule',
    'chantier_receptionne',
]
