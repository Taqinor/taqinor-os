"""Récepteurs d'événements métier (M6) — app Contrats.

Abonne ``contrats`` à l'événement ``devis_accepted`` exposé par
``core.events`` pour, à l'acceptation d'un devis DE RENOUVELLEMENT (lié à un
contrat via ``ContratLien`` type ``devis``), marquer le renouvellement proposé
ACCEPTÉ sur le contrat — sans que ``ventes`` importe ``contrats`` (même schéma
que ``apps/crm/receivers.py`` / ``apps/installations/receivers.py``).

Le récepteur est un NO-OP pour tout devis qui n'est PAS un devis de
renouvellement de contrat (aucun ``ContratLien`` correspondant) — la grande
majorité des acceptations de devis (ventes normales) ne déclenchent rien ici.
Ne modifie JAMAIS ``Contrat.statut`` (préservation des statuts — CONTRAT12) ni
n'avance de renouvellement effectif automatique (acte séparé et explicite,
``services.renouveler_contrat`` — CONTRAT23) : seule l'ACCEPTATION est tracée
au chatter (XCTR12).

ARC35 — consomme le seam ``contrat_signe``/``contrat_actif`` (YDOCF5, posé par
CONTRAT16/17, jusqu'ici SANS abonné, catalogué ``ALLOWED_UNCONSUMED``).
``contrats`` est ici à la fois émetteur (``services.signer_contrat`` /
``services.activer_si_eligible``) ET abonné : le signal transite tout de même
par le bus (même patron que ``qhse.receivers`` pour ``incident_declared``) afin
que d'éventuels FUTURS abonnés externes (facturation récurrente CONTRAT31/FG40,
entitlement SAV…) puissent se greffer sans toucher ``contrats``. Deux effets
câblés ici :

* chatter générique ARC8 (``records.services.log_note`` — DISTINCT du journal
  legacy ``ContratActivity``/``journaliser_transition`` déjà posé en ligne dans
  ``signer_contrat``/``activer_si_eligible`` : une seconde trace, dans le
  chatter UNIFIÉ, visible par tout consommateur du contrat GED) ;
* dépôt GED du contrat signé (``contrats.services.deposer_contrat_signe_en_ged``
  pour ``contrat_signe`` — idempotent, dépose la dernière ``VersionContrat``
  figée à la signature).

Best-effort : une erreur dans un récepteur ne doit JAMAIS remonter (la
signature/activation, côté ``contrats``, est déjà actée).
"""
import logging

from django.dispatch import receiver

from core.events import contrat_actif, contrat_signe, devis_accepted

from .services import marquer_renouvellement_accepte

logger = logging.getLogger(__name__)


@receiver(devis_accepted,
          dispatch_uid="contrats_marquer_renouvellement_accepte")
def _marquer_renouvellement_accepte_on_devis_accepted(
        sender, devis, user, ancien_statut, **kwargs):
    """À l'acceptation d'un devis lié à un contrat (ContratLien type devis),
    marque le renouvellement proposé ACCEPTÉ (chatter uniquement — XCTR12).

    Idempotent au sens applicatif : ré-émettre l'événement pour un devis déjà
    accepté ajoute simplement une nouvelle ligne de chatter (jamais une
    exception, jamais de double effet sur le statut du contrat qui n'est de
    toute façon jamais touché ici).
    """
    company = getattr(devis, 'company', None)
    if company is None:
        return
    # `devis_accepted` est un signal PARTAGÉ : un émetteur d'un autre domaine
    # (ex. la séquence d'inscription XMKT1) peut envoyer un objet devis minimal
    # non persisté (sans pk). Aucun ContratLien ne peut pointer un devis sans
    # pk — on sort proprement plutôt que de lever AttributeError sur `.pk`.
    devis_pk = getattr(devis, 'pk', None)
    if devis_pk is None:
        return

    from .models import ContratLien

    lien = ContratLien.objects.filter(
        company=company, type_cible=ContratLien.TypeCible.DEVIS,
        cible_id=devis_pk,
    ).select_related('contrat').first()
    if lien is None:
        return

    marquer_renouvellement_accepte(lien.contrat, devis, auteur=user)


@receiver(contrat_signe, dispatch_uid="contrats_chatter_ged_on_contrat_signe")
def _chatter_et_ged_on_contrat_signe(sender, contrat, user, company, **kwargs):
    """ARC35 — à la bascule ``signe`` : note chatter ARC8 + dépôt GED.

    Best-effort et indépendant par effet : un échec de l'un ne doit jamais
    empêcher l'autre, ni remonter (la signature est déjà actée par
    ``services.signer_contrat``)."""
    ref = (getattr(contrat, 'reference', '') or '').strip() or f'#{contrat.pk}'

    try:
        from apps.records.services import log_note

        log_note(
            contrat, user,
            f'Contrat {ref} signé — toutes les parties requises ont signé.',
            company=company)
    except Exception:  # noqa: BLE001 — best-effort, ne casse jamais
        logger.warning(
            'ARC35 : chatter ARC8 échoué sur contrat_signe pour contrat #%s',
            getattr(contrat, 'pk', '?'), exc_info=True)

    try:
        from .services import deposer_contrat_signe_en_ged

        from .models import SignatureContrat

        signature = (
            SignatureContrat.objects
            .filter(contrat=contrat, company=company)
            .order_by('-id')
            .first()
        )
        if signature is not None:
            deposer_contrat_signe_en_ged(signature)
    except Exception:  # noqa: BLE001 — best-effort, ne casse jamais
        logger.warning(
            'ARC35 : dépôt GED échoué sur contrat_signe pour contrat #%s',
            getattr(contrat, 'pk', '?'), exc_info=True)


@receiver(contrat_actif, dispatch_uid="contrats_chatter_on_contrat_actif")
def _chatter_on_contrat_actif(sender, contrat, user, company, **kwargs):
    """ARC35 — à la bascule ``actif`` : note chatter ARC8 (pas de second dépôt
    GED — le contrat SIGNÉ est déjà déposé par le récepteur ``contrat_signe``
    ci-dessus ; ``deposer_version_en_ged`` est de toute façon idempotent par
    version si un futur appelant redéposait).

    Best-effort : une erreur ne doit jamais remonter (l'activation, côté
    ``contrats``, est déjà actée)."""
    ref = (getattr(contrat, 'reference', '') or '').strip() or f'#{contrat.pk}'

    try:
        from apps.records.services import log_note

        log_note(
            contrat, user,
            f'Contrat {ref} activé.',
            company=company)
    except Exception:  # noqa: BLE001 — best-effort, ne casse jamais
        logger.warning(
            'ARC35 : chatter ARC8 échoué sur contrat_actif pour contrat #%s',
            getattr(contrat, 'pk', '?'), exc_info=True)
