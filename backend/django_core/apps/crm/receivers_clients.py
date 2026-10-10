"""SPL95 — corps des récepteurs CLIENTS / parrainage / commission (déplacés de
``receivers.py``).

Move only : corps et noms inchangés, SANS décorateur. Le câblage (``@receiver``,
``dispatch_uid``, ordre de connexion) reste dans ``receivers.py``, qui garde un
relais d'une ligne par récepteur parti.
"""

import logging

from urllib.parse import quote

from .fiche_funnel import generer_playbook_progress

logger = logging.getLogger(__name__)


def _calculer_commission_deal_on_devis_accepted(sender, devis, user,
                                                ancien_statut, **kwargs):
    """NTCRM22 — À l'acceptation d'un devis lié à un ``DealEnregistre``
    APPROUVE, calcule la commission due (taux × montant HT accepté), la pose
    sur ``montant_commission_du`` et passe le deal à À_PAYER. N'émet plus
    aucun événement (ALEA3, D-ALEA-3) — jamais d'écriture comptable
    automatique ici (frontière compta respectée).

    QJR22 — Décision fondateur D3 (29/08/2026) : la commission est un
    pourcentage du total NET de l'OPTION ACCEPTÉE, jamais du total BRUT ni,
    sur un devis à deux options, de la somme des deux (un montant qui ne
    correspond à aucune vente réelle). ``devis.option_acceptee`` est déjà
    posé quand ce signal se déclenche (``services.accept_devis`` l'écrit en
    base avant d'émettre ``devis_accepted``) : on route donc sur la chaîne
    canonique par option (``apps.ventes.utils.options.option_totaux``, la
    même que l'échéancier/bon de commande) plutôt que sur ``devis.total_ht``
    (brut, toutes lignes, aucune option). Cross-app : lecture via un
    utilitaire de ``ventes`` (pas d'import de ``models``), comme le reste de
    ce fichier.
    """
    from apps.ventes.utils.options import option_totaux

    from .models import DealEnregistre

    if devis.lead_id is None:
        return
    deal = (DealEnregistre.objects
            .filter(lead_id=devis.lead_id, statut=DealEnregistre.Statut.APPROUVE)
            .select_related('apporteur')
            .first())
    if deal is None:
        # QJR560 / D-QJR5-11 — V2 d'un devis signé acceptée : la commission
        # encore À_PAYER (calculée sur la V1) est RECALCULÉE sur l'option
        # acceptée de la V2 ; jamais une commission déjà payée.
        from apps.ventes.selectors import devis_predecesseurs_revision_ids
        if not devis_predecesseurs_revision_ids(devis):
            return
        deal = (DealEnregistre.objects
                .filter(lead_id=devis.lead_id,
                        statut=DealEnregistre.Statut.A_PAYER)
                .select_related('apporteur')
                .first())
        if deal is None:
            return
    taux = deal.apporteur.taux_commission_pct
    if not taux:
        return
    try:
        total_net_option = option_totaux(devis)['ht']
        montant = (total_net_option * taux) / 100
    except Exception:  # noqa: BLE001 — jamais bloquer l'acceptation du devis
        logger.exception('NTCRM22 — échec calcul commission deal %s', deal.pk)
        return
    deal.montant_commission_du = montant
    deal.statut = DealEnregistre.Statut.A_PAYER
    deal.save(update_fields=['montant_commission_du', 'statut'])


def _flip_parrainage_converti_on_devis_accepted(sender, devis, user, ancien_statut,
                                                **kwargs):
    """QX35 — Quand le devis d'un FILLEUL est accepté, le parrainage passe
    ``en_attente`` → ``converti`` (la récompense reste versée manuellement,
    hors périmètre ici). Même bus que l'avance de funnel ci-dessus — aucun
    import de ``ventes`` (le devis n'est manipulé qu'au travers des kwargs du
    signal). No-op si le devis ne désigne ni lead ni client, si aucun
    Parrainage ``en_attente`` ne le référence, ou s'il est déjà ``converti``/
    ``recompense_versee`` (jamais reculé).

    CRX34 — LE FILLEUL DÉJÀ CONVERTI EN CLIENT ÉTAIT LAISSÉ DE CÔTÉ. Le
    modèle ``Parrainage`` porte DEUX désignations du filleul (``filleul_lead``
    ET ``filleul_client``) parce qu'un filleul peut arriver comme prospect,
    comme client, ou devenir client entre-temps. Le récepteur, lui, ne
    consultait que ``filleul_lead_id`` : un parrainage enregistré sur le seul
    ``filleul_client`` restait ÉTERNELLEMENT « en attente » alors que la vente
    était signée — et le parrain n'était jamais récompensé. On apparie
    désormais sur l'une OU l'autre désignation."""
    from django.db.models import Q

    lead_id = getattr(devis, 'lead_id', None)
    client_id = getattr(devis, 'client_id', None)
    if not lead_id and not client_id:
        return
    from .models import Parrainage
    appariement = Q(pk__in=[])
    if lead_id:
        appariement |= Q(filleul_lead_id=lead_id)
    if client_id:
        appariement |= Q(filleul_client_id=client_id)
    parrainage = Parrainage.objects.filter(
        appariement, company=devis.company,
        statut=Parrainage.Statut.EN_ATTENTE,
    ).first()
    if parrainage is None:
        return
    parrainage.statut = Parrainage.Statut.CONVERTI
    parrainage.save(update_fields=['statut'])
    _suggerer_graine_pub_parrainage(parrainage, user)


def _proposer_lien_parrainage_on_devis_accepted(sender, devis, user,
                                                ancien_statut, **kwargs):
    """CRX38 — LE LIEN DE PARRAINAGE POST-SIGNATURE ATTEINT ENFIN QUELQU'UN.

    ``ventes.services.installation_share_link`` (PUB69) existe, est testé, et
    fabrique le lien « mon installation » d'un devis ACCEPTÉ — celui que le
    client peut faire suivre, porteur des UTM ``parrainage_whatsapp`` qui
    mesurent le bouche-à-oreille organique. Personne ne l'appelait : la
    capacité était complète et ORPHELINE, donc le canal de parrainage
    n'existait que sur le papier.

    Au moment exact de l'enchantement — la signature — le commercial reçoit
    donc le lien DÉJÀ PRÊT à envoyer en WhatsApp, plus le message tout fait.
    Aucun envoi automatique au client : c'est un humain qui décide (même
    doctrine que la suggestion de graine pub PUB65 ci-dessous).

    FRONTIÈRE CROSS-APP : le lien est demandé à la porte publique de
    ``ventes`` (``services.installation_share_link``), jamais à ses modèles.
    Best-effort de bout en bout — ce câblage ne fait JAMAIS échouer une
    acceptation : l'appel prend son propre point de sauvegarde (une erreur
    base ne peut pas empoisonner la transaction d'acceptation, cf. QJR421) et
    la notification part par ``transaction.on_commit`` (jamais un envoi
    synchrone sous les verrous de l'acceptation, cf. QJR422)."""
    from django.db import transaction

    try:
        from apps.ventes.services import installation_share_link
        with transaction.atomic():
            _, url = installation_share_link(devis)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CRX38 : lien de parrainage indisponible pour le devis %s',
            getattr(devis, 'reference', '?'), exc_info=True)
        return
    if not url:
        # Devis non accepté (garde PUB69) — rien à proposer.
        return

    destinataire = _commercial_du_devis(devis)
    if destinataire is None:
        return

    reference = getattr(devis, 'reference', '') or ''
    client_nom = (getattr(getattr(devis, 'client', None), 'nom', '')
                  or '').strip()
    message = (
        f"Merci pour votre confiance {client_nom} ! Voici le lien de votre "
        f"installation, à partager autour de vous : {url}").strip()
    wa_url = 'https://wa.me/?text=' + quote(message)
    corps = '\n'.join([
        (f'Le devis {reference} de {client_nom} est signé.'
         if client_nom else f'Le devis {reference} est signé.'),
        'Lien « mon installation » à faire suivre au client :',
        url,
        f'Envoyer en WhatsApp : {wa_url}',
    ])
    company = getattr(devis, 'company', None)
    lien_interne = f'/ventes/devis/{devis.pk}'

    def _envoyer():
        try:
            from apps.notifications.services import notify
            notify(
                user=destinataire,
                event_type='devis_accepted',
                title=f'Lien de parrainage prêt — {reference}',
                body=corps,
                link=lien_interne,
                company=company,
            )
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'CRX38 : notification de lien de parrainage échouée '
                'pour le devis %s', reference, exc_info=True)

    transaction.on_commit(_envoyer)


def _commercial_du_devis(devis):
    """CRX38 — LE commercial à qui le lien est utile : le propriétaire du lead
    d'origine, à défaut le créateur du devis. ``None`` si ni l'un ni l'autre —
    on ne notifie alors personne plutôt que de choisir au hasard."""
    lead = getattr(devis, 'lead', None)
    owner = getattr(lead, 'owner', None) if lead is not None else None
    if owner is not None:
        return owner
    return getattr(devis, 'created_by', None)


def _suggerer_graine_pub_parrainage(parrainage, user):
    """PUB65 — Poste, sur la fiche du PARRAIN, une note chatter suggérant une
    graine publicitaire géo/lookalike autour de lui (jamais une action
    automatique — un humain doit déclencher via
    ``apps.adsengine.audiences``). Best-effort : n'échoue JAMAIS la
    conversion du parrainage elle-même."""
    parrain = getattr(parrainage, 'parrain', None)
    if parrain is None:
        return
    try:
        from apps.adsengine.audiences import referral_seed_suggestion
        from apps.records.services import log_note

        nom_complet = f'{parrain.nom} {parrain.prenom or ""}'.strip() or 'parrain'
        suggestion = referral_seed_suggestion(
            parrain_nom=nom_complet,
            parrain_localisation=getattr(parrain, 'adresse', None))
        log_note(parrain, user, suggestion['reason_fr'],
                 company=parrainage.company)
    except Exception:  # noqa: BLE001 — best-effort, ne casse jamais la conversion
        logger.warning(
            'PUB65 : suggestion de graine pub échouée pour parrainage #%s',
            getattr(parrainage, 'pk', '?'), exc_info=True)


def _generer_playbook_progress_on_stage_change(sender, lead, old_stage,
                                               new_stage, user, **kwargs):
    """NTCRM12 — À CHAQUE changement d'étape d'un lead, génère la progression
    des tâches obligatoires/optionnelles du(des) playbook(s) actif(s) portant
    une étape sur ``new_stage``. Best-effort : ne bloque jamais la transition
    de stage déjà actée par l'émetteur."""
    try:
        generer_playbook_progress(lead, new_stage)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'NTCRM12: génération de la progression playbook échouée '
            'pour le lead #%s', getattr(lead, 'pk', '?'), exc_info=True)
