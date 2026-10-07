"""Abonnements au bus d'événements (M6) du module « calepinage ».

``core.events`` expose des objets ``django.dispatch.Signal`` (bus synchrone qui
ne dépend de rien). Une app réagit au changement d'état d'une AUTRE app en s'y
abonnant ICI (décorateur ``@receiver`` avec un ``dispatch_uid`` stable) et en
branchant ce module dans ``apps.py`` ``ready()`` — jamais en important les vues
ou les modèles de l'autre app (frontière import-linter).

ACAL38 (D-ACAL-1) — PLUS DE MIROIR : ``layout_finalise`` RATTACHE, IL N'ÉCRIT PLUS
--------------------------------------------------------------------------------
Le calepinage est l'UNIQUE conception d'un devis : l'atelier ouvert sur un devis
écrit le CALEPINAGE lié puis resynchronise le devis (ACAL37). L'ancien miroir
CAL39 (le document du devis recopié dans le calepinage à chaque
``layout_finalise``) est RETIRÉ : il écrasait les clés propres au module (fond
calé, surfaces de pose, modules). L'événement ne fait plus qu'ADOPTER ou CRÉER
le calepinage d'un devis qui n'en a pas encore (D02-T10) ; un calepinage
existant n'est JAMAIS réécrit.

BEST-EFFORT, TOUJOURS : un rattachement en échec ne doit JAMAIS faire échouer
un enregistrement de devis déjà réussi. L'erreur est journalisée, pas propagée.
"""
from __future__ import annotations

import logging

from django.dispatch import receiver

from core.events import (
    devis_revise, layout_finalise, lead_created, lead_trace_toit_recu,
)

logger = logging.getLogger(__name__)

__all__ = [
    'rattacher_conception_au_devis', 'relier_calepinage_au_devis_revise',
    'reprise_du_trace_public', 'reprise_du_trace_au_renvoi',
]


@receiver(layout_finalise,
          dispatch_uid='calepinage_rattacher_conception_au_devis')
def rattacher_conception_au_devis(sender, devis, user=None, **kwargs):
    """ACAL38 (D-ACAL-1) — RATTACHE le devis à son calepinage, sans jamais
    réécrire un calepinage existant.

    Selon l'origine rendue par ``services.creation.adopter_ou_creer_pour_devis``
    (idempotent : le même devis rend toujours le même calepinage) :

    * ``'existant'`` (déjà lié) — RIEN n'est écrit : le calepinage est la
      conception, le devis n'est qu'un instantané ;
    * ``'adopte'`` (l'ouvert du lead) — RIEN n'est écrit non plus ;
    * ``'cree'`` — le calepinage naît avec le document du devis SANS ses clés
      privées, et sa première version est déposée sur SON propre document.

    La SOCIÉTÉ et l'AUTEUR viennent du serveur. Aucun statut n'est écrit
    (règle #4), ni côté devis ni côté calepinage.
    """
    layout = getattr(devis, 'roof_layout', None)
    company = getattr(devis, 'company', None)
    if (devis is None or company is None or not isinstance(layout, dict)
            or not layout):
        return
    try:
        from .services.creation import (
            ORIGINE_CREE, adopter_ou_creer_pour_devis,
        )
        from .services.layout import enregistrer_layout

        calepinage, origine = adopter_ou_creer_pour_devis(
            devis.pk, company, user=user)
        if origine == ORIGINE_CREE:
            enregistrer_layout(calepinage, calepinage.roof_layout, user=user)
    except Exception:  # noqa: BLE001 — un rattachement ne casse jamais la source
        logger.exception(
            'ACAL38 : rattachement de conception en échec pour le devis %s',
            getattr(devis, 'pk', None))


#: ACAL92 — le libellé de la version FIGÉE déposée à la révision.
LIBELLE_VERSION_ENVOYEE = 'Version envoyée — {reference}'


@receiver(devis_revise, dispatch_uid='calepinage_relier_au_devis_revise')
def relier_calepinage_au_devis_revise(sender, ancien=None, nouveau=None,
                                      user=None, **kwargs):
    """ACAL92 (D-ACAL-3) — à la révision, le calepinage est RE-LIÉ à la V2.

    Le calepinage C lié DIRECTEMENT à la V1 (``ancien``) :

    1. dépose une version FIGÉE « Version envoyée — <référence V1> »
       (``enregistrer_version``, même empreinte admise : c'est la preuve de ce
       qui a été envoyé, sans sac de simulation) ;
    2. est re-lié à la V2 (``liens.lier_devis`` — l'ancien devis est inactif,
       le re-pointage est donc permis) : variantes, pertes, entrée électrique
       et versions restent sur C, aucun second calepinage n'est créé à la
       première sauvegarde de la V2.

    La V1 retrouve son calepinage par la chaîne de révision
    (``selectors.calepinage_du_devis`` suit ``superseded_by``). Aucun statut
    n'est écrit (règle #4). BEST-EFFORT : la révision est déjà actée, un
    échec est journalisé, jamais propagé.
    """
    company = getattr(ancien, 'company', None)
    if ancien is None or nouveau is None or company is None:
        return
    try:
        from django.db import transaction

        from .selectors import calepinage_du_devis
        from .services.liens import lier_devis
        from .services.versions import enregistrer_version

        calepinage = calepinage_du_devis(ancien.pk, company)
        if calepinage is None or calepinage.devis_id != ancien.pk:
            return
        reference = (getattr(ancien, 'reference', '') or '').strip() or (
            f'#{ancien.pk}')
        with transaction.atomic():
            enregistrer_version(
                calepinage, user=user,
                libelle=LIBELLE_VERSION_ENVOYEE.format(reference=reference),
                resultat=None, meme_empreinte_admise=True)
            lier_devis(calepinage, nouveau.pk, user=user)
    except Exception:  # noqa: BLE001 — une re-liaison ne casse jamais la révision
        logger.exception(
            'ACAL92 : re-liaison du calepinage en échec (%s -> %s)',
            getattr(ancien, 'pk', None), getattr(nouveau, 'pk', None))


@receiver(lead_created, dispatch_uid='calepinage_reprise_trace_public')
def reprise_du_trace_public(sender, lead=None, company=None, **kwargs):
    """CAL110 — un lead issu de « mon toit » ouvre un calepinage PRÉ-TRACÉ.

    PATRON M6 : c'est l'app CONSOMMATRICE qui s'abonne. ``apps.crm`` n'a
    aucune connaissance du module Calepinage, et ce module ne touche jamais
    les modèles crm — il lit le lead par ``apps.crm.selectors`` (dans le
    service) et n'écrit rien chez crm : ``roof_outline`` et ``roof_point`` du
    lead restent exactement ce qu'ils sont.

    ZÉRO CRÉATION SILENCIEUSE : un lead sans tracé exploitable, ou déjà doté
    d'un calepinage, n'en reçoit AUCUN (le service tranche, pas ce récepteur).

    BEST-EFFORT, TOUJOURS : une reprise en échec ne doit JAMAIS faire échouer
    la création du lead — un lead perdu coûte infiniment plus cher qu'un
    calepinage à recréer à la main. L'erreur est journalisée, pas propagée.
    """
    societe = company if company is not None else getattr(lead, 'company',
                                                          None)
    lead_id = getattr(lead, 'pk', None)
    if societe is None or not lead_id:
        return
    try:
        from .services.reprise_public import reprendre_trace_public

        reprendre_trace_public(lead_id, societe)
    except Exception:  # noqa: BLE001 — une reprise ne casse jamais un lead
        logger.exception(
            'CAL110 : reprise du tracé public en échec pour le lead %s',
            lead_id)


@receiver(lead_trace_toit_recu, dispatch_uid='calepinage_reprise_trace_renvoi')
def reprise_du_trace_au_renvoi(sender, lead=None, company=None, **kwargs):
    """ACAL189 (C-ACAL-006) — le tracé arrive au RENVOI du webhook (< 60 s).

    Le lead a été créé SANS contour (``lead_created`` n'avait rien à
    reprendre) ; le second POST du site lui en apporte un. ``crm`` émet
    ``lead_trace_toit_recu`` et ce module reprend le tracé par la MÊME porte
    que la création (``reprise_du_trace_public`` → ``reprendre_trace_public``
    → ``ouvrir_ou_creer_pour_lead``, ACAL182) : idempotent — un lead qui a
    déjà un calepinage ouvert n'en reçoit jamais un second.

    BEST-EFFORT, TOUJOURS (délégué) : une reprise en échec ne fait jamais
    échouer le webhook.
    """
    reprise_du_trace_public(sender, lead=lead, company=company, **kwargs)
