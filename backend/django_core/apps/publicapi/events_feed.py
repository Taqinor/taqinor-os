"""NTAPI17 — flux d'évènements consommable (CDC léger) : écriture & lecture.

Le pendant PULL des webhooks : mêmes signaux, même vocabulaire d'évènements,
mais c'est le client qui vient lire. Indispensable pour tout intégrateur qui ne
peut pas exposer d'URL publique (derrière un pare-feu, un poste de travail, un
connecteur no-code) et comme filet de RATTRAPAGE quand un webhook a été manqué.

Attribution de la ``sequence``
------------------------------
Compteur DENSE et croissant PAR SOCIÉTÉ, calculé « plus-haut-utilisé + 1 » dans
un savepoint avec retry sur course — jamais ``count() + 1`` (règle du dépôt :
un ``count()`` rétrécit dès qu'une ligne est purgée par la rétention, et deux
évènements se retrouveraient avec la même séquence). Même patron que
``core.numbering.create_with_reference``, transposé à un entier.

Scopes : LE point délicat
-------------------------
Un flux transverse ne doit jamais devenir un contournement des scopes de
lecture. Règle appliquée, stricte et facile à vérifier : le endpoint exige
``read:events``, ET chaque évènement n'est renvoyé que si la clé porte AUSSI le
scope de LECTURE de sa famille (``lead.*`` → ``read:leads``, ``facture.*`` →
``read:factures``…). Un évènement dont la famille n'a aucun scope de lecture
correspondant (aujourd'hui ``ticket.*``) n'est JAMAIS renvoyé — plutôt un flux
incomplet et documenté qu'une escalade de privilège silencieuse.
"""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.db.models import Max

from .constants import (
    EVENT_CHANTIER_COMPLETED, EVENT_DEVIS_ACCEPTED, EVENT_DEVIS_SENT,
    EVENT_FACTURE_CREATED, EVENT_FACTURE_PAID, EVENT_INTERVENTION_COMPLETED,
    EVENT_LEAD_CREATED, EVENT_LEAD_LOST, EVENT_LEAD_STAGE_CHANGED,
    EVENT_LIVRAISON_LIVREE, EVENT_PAIEMENT_RECORDED, EVENT_PLAN_CHANGED,
    EVENT_SCM_CYCLE_SOP_CLOTURE, EVENT_SCM_RUPTURE_IMMINENTE,
    EVENT_SIEGES_QUOTA_ATTEINT, EVENT_STOCK_SEUIL_ATTEINT,
    SCOPE_READ_CHANTIERS, SCOPE_READ_DEVIS, SCOPE_READ_FACTURES,
    SCOPE_READ_LEADS, SCOPE_READ_LICENCE, SCOPE_READ_SCM, SCOPE_READ_STOCK,
)

logger = logging.getLogger(__name__)

MAX_TENTATIVES_SEQUENCE = 5

# Borne dure de pagination du curseur (un client ne choisit jamais « tout »).
LIMITE_PAR_DEFAUT = 100
LIMITE_MAX = 500

# Évènement → scope de LECTURE requis pour le voir dans le flux. Un évènement
# ABSENT de cette table n'est jamais renvoyé (cf. docstring : jamais d'escalade
# silencieuse). `ticket.created`/`ticket.resolved` sont dans ce cas — aucun
# scope de lecture SAV n'existe encore.
SCOPE_PAR_EVENEMENT = {
    EVENT_LEAD_CREATED: SCOPE_READ_LEADS,
    EVENT_LEAD_LOST: SCOPE_READ_LEADS,
    EVENT_LEAD_STAGE_CHANGED: SCOPE_READ_LEADS,
    EVENT_DEVIS_SENT: SCOPE_READ_DEVIS,
    EVENT_DEVIS_ACCEPTED: SCOPE_READ_DEVIS,
    EVENT_FACTURE_CREATED: SCOPE_READ_FACTURES,
    EVENT_FACTURE_PAID: SCOPE_READ_FACTURES,
    EVENT_PAIEMENT_RECORDED: SCOPE_READ_FACTURES,
    EVENT_CHANTIER_COMPLETED: SCOPE_READ_CHANTIERS,
    EVENT_INTERVENTION_COMPLETED: SCOPE_READ_CHANTIERS,
    EVENT_STOCK_SEUIL_ATTEINT: SCOPE_READ_STOCK,
    EVENT_LIVRAISON_LIVREE: SCOPE_READ_STOCK,
    EVENT_PLAN_CHANGED: SCOPE_READ_LICENCE,
    EVENT_SIEGES_QUOTA_ATTEINT: SCOPE_READ_LICENCE,
    EVENT_SCM_RUPTURE_IMMINENTE: SCOPE_READ_SCM,
    EVENT_SCM_CYCLE_SOP_CLOTURE: SCOPE_READ_SCM,
}


def prochaine_sequence(company_id):
    """Plus-haut-utilisé + 1 pour cette société (1 si le flux est vide).

    JAMAIS ``count() + 1`` : la rétention purge les vieux évènements, donc le
    compte rétrécit alors que la séquence, elle, ne doit jamais reculer."""
    from .models import ApiEvent

    plus_haut = ApiEvent.objects.filter(company_id=company_id).aggregate(
        m=Max('sequence'))['m']
    return (plus_haut or 0) + 1


def enregistrer(company_id, event, payload, *, event_id=''):
    """Ajoute un évènement au flux de la société. Renvoie l'instance ou ``None``.

    Best-effort de bout en bout : le flux est un CANAL D'OBSERVATION, il ne doit
    jamais faire échouer l'enregistrement métier qui l'a déclenché.
    """
    from .models import ApiEvent

    if not company_id or not event:
        return None
    derniere_erreur = None
    for _ in range(MAX_TENTATIVES_SEQUENCE):
        sequence = prochaine_sequence(company_id)
        try:
            with transaction.atomic():
                return ApiEvent.objects.create(
                    company_id=company_id,
                    sequence=sequence,
                    type=event,
                    payload=payload if isinstance(payload, dict) else {},
                    event_id=event_id or '',
                )
        except IntegrityError as exc:
            # Course sur (company, sequence) : un autre écrivain a pris CE
            # numéro. On relit le plus-haut et on recommence — jamais un
            # trou, jamais un doublon.
            if 'sequence' not in str(exc).lower():
                raise
            derniere_erreur = exc
    logger.warning('Séquence de flux non attribuée après %s tentatives : %s',
                   MAX_TENTATIVES_SEQUENCE, derniere_erreur)
    return None


def scopes_lisibles(api_key):
    """Codes d'évènements que CETTE clé a le droit de voir dans le flux."""
    return [
        event for event, scope in SCOPE_PAR_EVENEMENT.items()
        if api_key.has_scope(scope)
    ]


def lire(api_key, *, after=0, limit=LIMITE_PAR_DEFAUT):
    """Page d'évènements strictement APRÈS ``after``, par ordre de séquence.

    Toujours scopé à la société de la clé, et restreint aux familles
    d'évènements dont la clé porte le scope de lecture.
    """
    from .models import ApiEvent

    limit = max(1, min(int(limit or LIMITE_PAR_DEFAUT), LIMITE_MAX))
    autorises = scopes_lisibles(api_key)
    if not autorises:
        return [], limit
    qs = (ApiEvent.objects
          .filter(company_id=api_key.company_id,
                  sequence__gt=max(0, int(after or 0)),
                  type__in=autorises)
          .order_by('sequence'))
    return list(qs[:limit]), limit


def serialiser(evenement):
    return {
        'sequence': evenement.sequence,
        'type': evenement.type,
        'event_id': evenement.event_id,
        'payload': evenement.payload,
        'created_at': evenement.created_at.isoformat(),
    }


# ── Rétention (bornée par le plan NTAPI7) ───────────────────────────────────
#
# `ApiUsagePlan.retention_livraisons_jours` borne déjà la rétention des
# livraisons webhook ; le flux d'évènements est le MÊME matériau (une trace
# d'évènement sortant) et suit donc la MÊME borne, par société — jamais une
# seconde notion de rétention à régler ailleurs. Une société sans plan retombe
# sur `API_EVENT_RETENTION_DAYS` (défaut 0 = OFF, rien n'est jamais purgé).

DEFAULT_API_EVENT_RETENTION_DAYS = 0


def purger_evenements(now, apply_=True):
    """Purge, PAR SOCIÉTÉ, les évènements plus vieux que sa rétention.

    ``apply_=False`` (dry-run) compte sans supprimer. Renvoie le nombre
    d'évènements concernés."""
    from datetime import timedelta

    from core.models import ApiUsagePlan
    from core.retention import setting_days

    from .models import ApiEvent

    defaut = setting_days('API_EVENT_RETENTION_DAYS',
                          DEFAULT_API_EVENT_RETENTION_DAYS)
    jours_par_societe = dict(
        ApiUsagePlan.objects.filter(actif=True).values_list(
            'company_id', 'retention_livraisons_jours'))
    total = 0
    # `order_by()` VIDE avant `distinct()` : sans lui, l'ordering de `Meta`
    # (`company, sequence`) réinjecte `sequence` dans le SELECT et la distinction
    # porte sur la PAIRE — on itérerait une fois par ÉVÈNEMENT au lieu d'une
    # fois par société (piège Django documenté sur `values_list().distinct()`).
    societes = ApiEvent.objects.order_by().values_list(
        'company_id', flat=True).distinct()
    for company_id in societes:
        jours = jours_par_societe.get(company_id, defaut)
        if not jours or jours <= 0:
            continue  # rétention illimitée pour cette société
        limite = now - timedelta(days=jours)
        qs = ApiEvent.objects.filter(
            company_id=company_id, created_at__lt=limite)
        compte = qs.count()
        if compte and apply_:
            qs.delete()
        total += compte
    return total
