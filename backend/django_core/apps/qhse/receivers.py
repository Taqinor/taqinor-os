"""Récepteurs d'événements métier QHSE (QHSE32) — escalade des incidents.

Mirroir EXACT du patron ``core.events`` utilisé par ``ventes`` (émet
``devis_accepted``) et ``crm`` (s'y abonne via ``receivers.py`` câblé dans son
``apps.py`` ``ready()``) : une partie du code émet un événement sur le bus de
signaux Django, une autre s'y abonne pour réagir — sans import direct des
``models`` / ``views`` de l'émetteur.

Ici l'émetteur ET l'abonné sont la MÊME app ``qhse`` : le signal
``incident_declared`` est donc défini localement dans cette app (couche QHSE)
plutôt que dans ``core.events`` (réservé aux événements INTER-app), ce qui
respecte la règle « ne pas éditer ``core`` ». Le bus reste le même
(``django.dispatch.Signal``) ; l'émission est SYNCHRONE, identique au bus
existant.

Événement
---------

``incident_declared``
    Émis quand un ``Incident`` (QHSE29) est déclaré/créé via le chemin canonique
    de création (``IncidentViewSet.perform_create``). Arguments du signal :

    * ``incident`` — l'instance ``Incident`` créée ;
    * ``company`` — la société (posée côté serveur, jamais lue du corps) ;
    * ``user`` — l'utilisateur qui déclare (peut être ``None``) ;
    * ``gravite`` — la gravité de l'incident (``mineure`` / ``majeure`` /
      ``critique``).

Réaction d'escalade
-------------------

Pour un incident de gravité ``critique``, une note d'escalade est ajoutée au
chatter QHSE de l'incident (``QhseChatterEntry`` — historique style Odoo), afin
que les responsables voient une trace explicite « à escalader ». La réaction est
best-effort et idempotente : une erreur ne casse JAMAIS la création de
l'incident, et le ``dispatch_uid`` empêche tout double-abonnement.
"""
import logging

import django.dispatch
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Émis à la déclaration/création d'un Incident HSE (QHSE29).
# Émetteur ET abonné = app qhse → défini ici (pas dans core.events, réservé aux
# événements inter-app). Arguments : incident, company, user, gravite.
incident_declared = django.dispatch.Signal()


@receiver(incident_declared, dispatch_uid="qhse_escalate_on_incident_declared")
def _escalader_incident_critique(sender, incident, company, user, gravite,
                                 **kwargs):
    """À la déclaration d'un incident CRITIQUE, ajoute une note d'escalade au
    chatter QHSE de l'incident.

    Mirroir du patron ``crm`` : un récepteur câblé dans ``apps.py`` ``ready()``
    réagit à un événement du bus. Gating par gravité : SEULS les incidents
    ``critique`` déclenchent l'escalade (mineurs/majeurs : aucune réaction).

    Best-effort : toute exception est avalée + journalisée — la réaction ne doit
    JAMAIS faire échouer la création de l'incident.
    """
    from apps.qhse.models import Incident

    if gravite != Incident.Gravite.CRITIQUE:
        return  # seuls les incidents critiques sont escaladés

    # Import function-local pour éviter tout cycle d'import au démarrage.
    from apps.qhse import chatter as qhse_chatter

    try:
        ref = getattr(incident, 'reference', '') or 'INC'
        qhse_chatter.log_note(
            incident, user,
            "⚠️ Incident CRITIQUE déclaré — escalade requise auprès des "
            "responsables QHSE. Référence : %s." % ref)
    except Exception as exc:  # noqa: BLE001 — best-effort, ne casse jamais
        logger.warning(
            'QHSE32 : escalade incident critique échouée pour %s : %s',
            getattr(incident, 'pk', '?'), exc)
