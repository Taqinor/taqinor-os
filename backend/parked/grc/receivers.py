"""NTGRC9 — alerte DPO : traitement d'une personne au consentement RETIRÉ.

``grc`` s'abonne au bus ``core.events`` (M6) : il ne connaît ni ``crm`` ni
``ventes``, et eux ne connaissent pas ``grc``. Deux déclencheurs :
``lead_created`` (une nouvelle demande arrive) et ``devis_accepted`` (un
engagement commercial se noue).

L'alerte NE BLOQUE JAMAIS l'opération : c'est un signalement au responsable,
pas un veto de la machine. Un retrait de consentement porte sur une FINALITÉ
(marketing, WhatsApp…) et n'interdit pas mécaniquement toute relation
contractuelle — c'est au DPO de trancher, avec le contexte.
"""
from __future__ import annotations

import logging

from django.dispatch import receiver

from core.events import devis_accepted, lead_created

logger = logging.getLogger(__name__)

TITRE = "Consentement retiré : personne de nouveau traitée"


def _identifiants(objet):
    """Email et téléphone portés par l'objet (best-effort, sans import)."""
    valeurs = []
    for champ in ('email', 'telephone', 'whatsapp'):
        valeur = (getattr(objet, champ, None) or '').strip()
        if valeur:
            valeurs.append(valeur)
    return valeurs


def retraits_de_consentement(company, identifiants):
    """Finalités dont le consentement est RETIRÉ pour ces identifiants.

    Un registre de consentement est APPEND-ONLY : la même personne peut avoir
    accordé puis retiré puis ré-accordé. Seule la ligne la PLUS RÉCENTE par
    finalité fait foi — compter les ``granted=False`` alerterait à vie sur
    quelqu'un qui a re-consenti depuis.
    """
    from core.models import ConsentRecord

    if company is None or not identifiants:
        return []
    lignes = (ConsentRecord.objects
              .filter(company=company, subject_identifier__in=identifiants)
              .order_by('id')
              .values_list('purpose', 'granted'))
    dernier_par_finalite = {}
    for purpose, granted in lignes:
        dernier_par_finalite[purpose] = granted
    return sorted(p for p, granted in dernier_par_finalite.items()
                  if not granted)


def _alerter_dpo(company, identifiants, contexte, lien=None):
    """Émet la notification de conformité (best-effort, jamais bloquante)."""
    from apps.notifications.models import EventType
    from apps.notifications.services import notify_many, resolve_recipients

    finalites = retraits_de_consentement(company, identifiants)
    if not finalites:
        return []
    event_type = EventType.CONSENTEMENT_RETIRE_TRAITE
    corps = (
        f'{contexte} — consentement retiré pour : {", ".join(finalites)}. '
        "Vérifiez la base légale du traitement avant toute sollicitation."
    )
    return notify_many(
        resolve_recipients(company, event_type), event_type, TITRE,
        body=corps, link=lien, company=company)


@receiver(lead_created, dispatch_uid='grc_alerte_dpo_sur_lead_created')
def _sur_lead_created(sender, lead=None, company=None, **kwargs):
    try:
        _alerter_dpo(
            company or getattr(lead, 'company', None),
            _identifiants(lead),
            'Nouveau lead créé',
            lien=f'/crm/leads/{getattr(lead, "pk", "")}')
    except Exception:  # noqa: BLE001 — jamais bloquant pour la création
        logger.warning('NTGRC9 : alerte DPO (lead) échouée', exc_info=True)


@receiver(devis_accepted, dispatch_uid='grc_alerte_dpo_sur_devis_accepted')
def _sur_devis_accepted(sender, devis=None, **kwargs):
    try:
        company = getattr(devis, 'company', None)
        cible = getattr(devis, 'client', None) or getattr(devis, 'lead', None)
        _alerter_dpo(
            company, _identifiants(cible), 'Devis accepté',
            lien=f'/ventes/devis/{getattr(devis, "pk", "")}')
    except Exception:  # noqa: BLE001 — jamais bloquant pour l'acceptation
        logger.warning('NTGRC9 : alerte DPO (devis) échouée', exc_info=True)
