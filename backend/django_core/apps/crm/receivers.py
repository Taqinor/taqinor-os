"""Récepteurs d'événements métier (M6).

Abonne le CRM aux événements du cœur métier exposés par ``core.events``, pour
réagir à des changements d'état déclenchés par d'autres apps (ex. ``ventes``)
sans que celles-ci importent le CRM. Câblé au démarrage par ``CrmConfig.ready``.

ARC37 — s'abonne aussi à ``ticket_resolu`` (``sav`` devient émetteur du bus) :
pose une note chatter ARC8 (``records.services.log_note``) sur le
``crm.Client`` lié au ticket, sans jamais importer ``apps.sav``.
"""
import logging
from urllib.parse import quote

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core.events import (
    ao_depose, ao_gagne, appointment_effectue, deal_commission_due,
    devis_accepted, devis_refused, devis_sent, layout_finalise,
    lead_stage_changed, ticket_resolu,
)

from . import stages
from .models import Appointment, LeadActivity
from .services import (
    _CONTACT_KINDS,
    arreter_cadence,
    arreter_cadence_du_lead_id,
    FILET_REFUS_LIBELLE,
    assurer_prochaine_etape_apres_succes,
    avancer_stage_lead_vers,
    avancer_stage_new_vers_contacted,
    avancer_stage_pour_devis,
    generer_playbook_progress,
    initialiser_plan_relance,
    marquer_premier_contact,
    signaler_mismatch_signe_sur_refus,
)

logger = logging.getLogger(__name__)


@receiver(devis_accepted, dispatch_uid="crm_advance_stage_on_devis_accepted")
def _avancer_stage_on_devis_accepted(sender, devis, user, ancien_statut,
                                     **kwargs):
    """À l'acceptation d'un devis, avance l'étape du lead (→ SIGNED).

    Remplace, à l'identique, l'appel direct ``ventes → crm.services`` qui était
    fait au site d'acceptation : même règle (ne recule jamais, ignore les leads
    perdus), désormais déclenchée par l'événement ``devis_accepted``.
    """
    avancer_stage_pour_devis(devis, ancien_statut, devis.statut, user)


@receiver(devis_accepted,
          dispatch_uid="crm_stop_relance_on_devis_accepted")
def _arreter_cadence_on_devis_accepted(sender, devis, user, ancien_statut,
                                       **kwargs):
    """MRY9 (a) — un devis accepté ARRÊTE toutes les cadences du lead.

    Sans cela, le client qui vient de signer continue de recevoir les
    messages « votre proposition est valable jusqu'au … » : la faute la plus
    visible qu'un CRM puisse commettre. Best-effort — jamais d'exception vers
    l'acceptation, qui est déjà actée."""
    arreter_cadence_du_lead_id(
        getattr(devis, 'lead_id', None), company=getattr(devis, 'company', None),
        user=user, motif='devis accepté')


@receiver(devis_accepted, dispatch_uid="crm_deal_commission_on_devis_accepted")
def _calculer_commission_deal_on_devis_accepted(sender, devis, user,
                                                ancien_statut, **kwargs):
    """NTCRM22 — À l'acceptation d'un devis lié à un ``DealEnregistre``
    APPROUVE, calcule la commission due (taux × montant HT accepté), la pose
    sur ``montant_commission_du`` et passe le deal à À_PAYER. Émet
    ``deal_commission_due`` (core.events) pour un futur consommateur compta —
    jamais d'écriture comptable automatique ici (frontière compta respectée).

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

    deal_commission_due.send(
        sender='crm.receivers', company=devis.company, deal_id=deal.pk,
        apporteur_id=deal.apporteur_id, montant=montant)


@receiver(devis_sent, dispatch_uid="crm_plan_apres_devis_on_devis_sent")
def _planifier_apres_devis_on_devis_sent(sender, devis, user, ancien_statut,
                                         **kwargs):
    """MRY7 — L'ENVOI d'un devis bascule le lead sur la cadence « après devis ».

    Deux gestes, dans cet ordre : la prise de contact s'ARRÊTE (son but est
    atteint — le prospect a son chiffrage), puis le suivi de proposition
    DÉMARRE, daté depuis la date d'envoi réelle et non depuis maintenant.

    UNE SEULE cadence après-devis par LEAD à la fois : quand plusieurs devis
    d'un même lead partent ensemble (``whatsapp_devis`` boucle sur la
    sélection), le deuxième ne crée rien — sinon le client recevrait deux
    séries de messages parallèles pour un seul dossier. Le fait est journalisé
    plutôt que silencieux.

    Best-effort : ne fait jamais retomber un envoi déjà acté."""
    lead_id = getattr(devis, 'lead_id', None)
    if not lead_id:
        return
    try:
        from .models import Lead
        lead = Lead.objects.filter(
            pk=lead_id, company=getattr(devis, 'company', None)).first()
        if lead is None:
            return
        # RELANCE-SUITE (08/09/2026) — l'envoi ferme aussi l'étape générique
        # « préparer et envoyer le devis » / « appeler le client » devenue
        # sans objet : le plan après-devis prend la suite.
        arreter_cadence(lead, user=user, motif='devis envoyé',
                        cadences=['contact', 'generique'])
        deja = lead.relance_etapes.filter(
            cadence='apres_devis', statut='a_faire').exclude(
                devis_id=devis.pk).first()
        if deja is not None:
            reference = getattr(deja.devis, 'reference', '') or '?'
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=user,
                kind=LeadActivity.Kind.NOTE,
                body=('Cadence après devis déjà en cours pour '
                      f'{reference} — aucune seconde série lancée.'))
            return
        etapes = initialiser_plan_relance(
            lead, user, cadence='apres_devis',
            depart=getattr(devis, 'date_envoi', None), devis=devis)
        # M2 (revue Fable 07/09/2026) — société sans gabarit après-devis (ou
        # barreaux tous écartés) : le plan est vide et la prise de contact
        # vient d'être arrêtée — sans filet, le lead sortait de toutes les
        # files. L'étape générique tient l'invariant Froid-ou-Signé.
        if not any(getattr(e, 'statut', '') == 'a_faire' for e in etapes):
            assurer_prochaine_etape_apres_succes(lead, user)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            "MRY7: cadence après devis non planifiée (devis #%s)",
            getattr(devis, 'pk', '?'), exc_info=True)


@receiver(devis_refused, dispatch_uid="crm_stop_apres_devis_on_devis_refused")
def _arreter_apres_devis_on_devis_refused(sender, devis, user, motif_refus,
                                          **kwargs):
    """MRY7 — Un devis REFUSÉ arrête sa cadence de suivi, même quand le lead
    n'est PAS marqué perdu.

    C'est le cas par défaut (`marquer_lead_perdu` non coché) : le lead reste
    vivant — on lui refera peut-être une offre — mais continuer à lui demander
    « alors, ce PDF ? » sur une proposition qu'il vient de refuser serait
    absurde. Distinct du receveur « perdu », qui ne se déclenche pas ici."""
    lead_id = getattr(devis, 'lead_id', None)
    if not lead_id:
        return
    try:
        from .models import Lead, RelanceEtape
        lead = Lead.objects.filter(
            pk=lead_id, company=getattr(devis, 'company', None)).first()
        if lead is None:
            return
        if RelanceEtape.objects.filter(
                devis_id=devis.pk,
                statut=RelanceEtape.Statut.A_FAIRE).exists():
            arreter_cadence(lead, user=user,
                            motif=(motif_refus or 'devis refusé'),
                            cadences=['apres_devis'])
        # QJ-INVARIANT — le lead reste VIVANT après ce refus (pas marqué
        # perdu) : une étape « décider la suite » le garde dans les files —
        # sa liste de relances ne se termine que par Froid ou Signé. Jamais
        # le plan après-devis (relancer la proposition refusée).
        assurer_prochaine_etape_apres_succes(
            lead, user, libelle=FILET_REFUS_LIBELLE, avec_plan_devis=False)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            "MRY7: arrêt de la cadence après devis échoué (devis #%s)",
            getattr(devis, 'pk', '?'), exc_info=True)


@receiver(devis_sent, dispatch_uid="crm_advance_stage_on_devis_sent")
def _avancer_stage_on_devis_sent(sender, devis, user, ancien_statut,
                                 **kwargs):
    """À l'ENVOI d'un devis (U4), avance l'étape du lead (→ QUOTE_SENT).

    Même câblage que ``devis_accepted`` : ``avancer_stage_pour_devis`` ne recule
    jamais le funnel et ignore les leads perdus, donc l'avance vers QUOTE_SENT
    est sûre et idempotente (un lead déjà ≥ QUOTE_SENT ne bouge pas).
    """
    avancer_stage_pour_devis(devis, ancien_statut, devis.statut, user)


@receiver(layout_finalise, dispatch_uid="crm_note_chatter_on_layout_finalise")
def _noter_conception_on_layout_finalise(sender, devis, user=None, **kwargs):
    """PV79 — pose une note au chatter du lead quand la toiture est finalisée.

    « Conception 3D finalisée — X kWc » : la commerciale voit dans
    l'historique du lead que la toiture a été dessinée (ou redessinée), sans
    avoir à ouvrir le devis. Même câblage que ``devis_sent`` — c'est le BUS qui
    porte l'information, ``ventes`` n'importe jamais ``crm``.

    No-op quand le devis n'a pas de lead (un devis client direct n'a pas de
    chatter de lead à alimenter). La puissance est lue par le SÉLECTEUR
    ``ventes`` (PV78) : jamais un import de ses modèles ; absente, la note se
    contente de dire que la conception est finalisée — jamais un « 0 kWc »
    fabriqué.
    """
    if not getattr(devis, 'lead_id', None):
        return
    from .models import Lead
    lead = Lead.objects.filter(
        pk=devis.lead_id, company_id=getattr(devis, 'company_id', None)).first()
    if lead is None:
        return

    kwc = None
    try:
        from .selectors import conception_3d_du_lead
        kwc = (conception_3d_du_lead(lead) or {}).get('kwc')
    except Exception:  # noqa: BLE001 — une puissance illisible ne bloque rien
        kwc = None
    if kwc:
        corps = ('Conception 3D finalisée — %s kWc'
                 % ('%.2f' % float(kwc)).rstrip('0').rstrip('.').replace(
                     '.', ','))
    else:
        corps = 'Conception 3D finalisée'

    LeadActivity.objects.create(
        company=lead.company, lead=lead, kind=LeadActivity.Kind.NOTE,
        body=corps, user=user)


@receiver(devis_refused, dispatch_uid="crm_mark_lead_perdu_on_devis_refused")
def _marquer_lead_perdu_on_devis_refused(sender, devis, user, motif_refus,
                                         **kwargs):
    """FG44 — au refus d'un devis (optionnel), marque le lead perdu (perdu=True).

    Ne s'active que si le devis a un lead associé et que ``marquer_lead_perdu``
    est True dans les kwargs (la vue envoie ce paramètre si l'utilisateur a coché
    la case). Le motif de refus du devis devient le motif_perte du lead.
    """
    if not getattr(devis, 'lead_id', None):
        return
    marquer = kwargs.get('marquer_lead_perdu', False)
    if not marquer:
        return
    # Import local pour éviter les cycles (CRM n'importe pas ventes.models).
    from .models import Lead
    try:
        lead = Lead.objects.get(pk=devis.lead_id, company=devis.company)
    except Lead.DoesNotExist:
        return
    if lead.perdu:
        return  # Déjà perdu, ne pas écraser.
    from . import activity as crm_activity
    old_perdu = lead.perdu
    old_motif = lead.motif_perte
    lead.perdu = True
    # MRY22 — le TROISIÈME chemin vers « perdu ». Le refus d'un devis peut
    # arriver sans motif saisi : on retombe alors sur « Devis refusé » plutôt
    # que d'écrire NULL, sinon ce chemin serait le seul à produire des pertes
    # sans raison — exactement ce que les deux autres refusent désormais.
    lead.motif_perte = (motif_refus or '')[:255] or 'Devis refusé'
    lead.save(update_fields=['perdu', 'motif_perte'])
    crm_activity.log_bulk_change(lead, user, 'perdu', old_perdu, True)
    if lead.motif_perte != old_motif:
        crm_activity.log_bulk_change(lead, user, 'motif_perte',
                                     old_motif, lead.motif_perte)
    # MRY9 (c) — troisième chemin vers « perdu » : il arrête les relances
    # comme les deux autres. Une seule fonction, jamais une variante locale.
    arreter_cadence(lead, user=user,
                    motif=(motif_refus or 'devis refusé'))


@receiver(devis_accepted, dispatch_uid="crm_flip_parrainage_converti_on_devis_accepted")
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


@receiver(devis_accepted, dispatch_uid="crm_lien_parrainage_on_devis_accepted")
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


@receiver(devis_refused, dispatch_uid="crm_signal_signe_sans_devis_actif")
def _signaler_signe_sans_devis_actif(sender, devis, user, motif_refus,
                                     **kwargs):
    """U11 — au refus d'un devis, signale (sans reculer l'étape) si le lead reste
    coincé à SIGNED sans aucun devis accepté actif (« signé fantôme »).

    Indépendant de la case « marquer le lead perdu » : la cohérence du funnel
    doit être signalée que l'utilisateur coche ou non cette case. Conforme à la
    règle #2 (le funnel est une couche permanente, séparée des statuts DOCUMENT —
    on NE recule JAMAIS l'étape à l'aveugle).
    """
    if not getattr(devis, 'lead_id', None):
        return
    signaler_mismatch_signe_sur_refus(devis, user)


# ── QJ7 — Avance automatique NEW → CONTACTED au premier contact ──────────────

@receiver(post_save, sender=LeadActivity,
          dispatch_uid="crm_advance_stage_new_vers_contacted_on_activity")
def _avancer_stage_on_contact_activity(sender, instance, created, **kwargs):
    """QJ7 — Quand la PREMIÈRE activité de contact (NOTE/APPEL/EMAIL) est créée
    sur un lead NEW (et non perdu), avance l'étape vers CONTACTED — une seule fois.

    Intra-CRM : utilise ``post_save`` sur ``LeadActivity`` (pas de bus cross-app).
    Le garde-fou « ne recule jamais » et « ignore les leads perdus » est délégué à
    ``avancer_stage_new_vers_contacted`` dans ``services.py``.
    """
    if not created:
        return  # mise à jour, pas une nouvelle activité
    if instance.kind not in _CONTACT_KINDS:
        return  # CREATION ou MODIFICATION ne déclenchent pas l'avancée
    if instance.user is None:
        return  # uniquement un contact MANUEL d'un utilisateur (pas auto/système)
    lead = instance.lead
    # RÈGLE FONDATEUR 07/09/2026 — le funnel ne bouge que sur une RÉPONSE
    # CONFIRMÉE de Meryem : « joint » / « intéressé ». Une simple note, un
    # appel sans réponse ou un WhatsApp ENVOYÉ ne déplacent plus l'étape
    # (l'ancien « auto — premier contact » sur toute activité est mort) ;
    # le KPI de premier contact, lui, reste horodaté (MRY19).
    marquer_premier_contact(lead)
    if (instance.outcome or '').strip() in ('joint', 'interesse'):
        avancer_stage_new_vers_contacted(lead, instance.user)


@receiver(post_save, sender=LeadActivity,
          dispatch_uid="crm_stop_contact_cadence_on_outcome")
def _arreter_cadence_on_outcome(sender, instance, created, **kwargs):
    """MRY9 (e) — l'ISSUE d'un appel arrête la bonne cadence, et elle seule.

    * `joint` / `interesse` → arrête `contact` : le but de la prise de contact
      est atteint. La cadence APRÈS DEVIS, elle, continue — un client joint
      reste à relancer sur sa proposition. RELANCE-SUITE (fondateur
      08/09/2026) : la suite posée par le filet suit le CANAL de la touche —
      message répondu → « appeler le client » ; appel fait → « préparer et
      envoyer le devis » ; le plan après-devis attend l'ENVOI du devis.
    * `refus` → arrête `contact` ET `apres_devis`, SANS marquer le lead perdu :
      « perdu » est une décision humaine qui exige un motif (MRY22), pas un
      effet de bord d'un appel.

    Seule une activité créée par un HUMAIN compte (``user`` non nul) — une
    ligne système ne décide pas d'un arrêt."""
    if not created or instance.user is None:
        return
    issue = (instance.outcome or '').strip()
    # M1 (revue Fable 07/09/2026) — la cadence ``reveil`` est arrêtée comme
    # les autres : un client JOINT au réveil J30 ne doit pas recevoir le J60,
    # et un refus au réveil termine les réveils (le dossier reste au Froid).
    if issue in ('joint', 'interesse'):
        motif, cadences = 'joint', ['contact', 'reveil']
    elif issue == 'refuse':
        motif, cadences = ('refus au téléphone',
                           ['contact', 'apres_devis', 'reveil'])
    else:
        return
    try:
        arreter_cadence(instance.lead, user=instance.user, motif=motif,
                        cadences=cadences)
        # QJ-INVARIANT — si l'arrêt (ou l'absence de toute cadence) laisse le
        # lead SANS prochaine étape, le filet en pose une : un client joint ne
        # disparaît jamais des files, et un REFUS téléphonique laisse une
        # étape « décider la suite » — la décision (perdu + motif, MRY22)
        # reste humaine, mais le dossier reste visible en attendant.
        if issue in ('joint', 'interesse'):
            # M1 — un client joint pendant un RÉVEIL sort du parking : COLD
            # est rangé SOUS toute étape active (rang -1), l'avance vers
            # CONTACTED est donc légitime et réactive le dossier — sans quoi
            # la garde COLD du filet le laisserait figé au Froid sans suite.
            instance.lead.refresh_from_db(fields=['stage'])
            if instance.lead.stage == stages.COLD:
                avancer_stage_lead_vers(
                    instance.lead, instance.user, stages.CONTACTED)
            # RELANCE-SUITE (08/09/2026) — la suite dépend du CANAL de la
            # touche : message répondu → l'appeler ; appel fait → préparer
            # et envoyer le devis. Le plan après-devis, lui, ne démarre qu'à
            # l'ENVOI du devis (jamais sur un brouillon).
            assurer_prochaine_etape_apres_succes(
                instance.lead, instance.user, canal_touche=instance.kind)
        elif issue == 'refuse':
            assurer_prochaine_etape_apres_succes(
                instance.lead, instance.user,
                libelle=FILET_REFUS_LIBELLE, avec_plan_devis=False)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            "MRY9: arrêt de cadence échoué sur l'issue « %s » (lead #%s)",
            issue, getattr(instance, 'lead_id', '?'), exc_info=True)


@receiver(lead_stage_changed,
          dispatch_uid="crm_stop_relance_on_stage_signed_or_cold")
def _arreter_cadence_on_stage_change(sender, lead, old_stage, new_stage, user,
                                     **kwargs):
    """MRY9 (b) — SIGNED arrête TOUT ; COLD arrête `contact` et `apres_devis`.

    COLD est un PARKING, pas une perte : les réveils J30/J60 y sont posés par
    MRY11 — on ne les arrête donc pas ici, sinon un lead mis au froid ne
    serait plus jamais réveillé. Best-effort : ne bloque jamais la transition
    d'étape déjà actée par l'émetteur."""
    try:
        if new_stage == stages.SIGNED:
            arreter_cadence(lead, user=user, motif='lead signé')
        elif new_stage == stages.COLD:
            arreter_cadence(lead, user=user, motif='lead passé en froid',
                            cadences=['contact', 'apres_devis'])
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            "MRY9: arrêt de cadence échoué au changement d'étape du lead #%s",
            getattr(lead, 'pk', '?'), exc_info=True)


@receiver(lead_stage_changed, dispatch_uid="crm_generate_playbook_progress_on_stage_change")
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


@receiver(ticket_resolu, dispatch_uid="crm_chatter_on_ticket_resolu")
def _chatter_on_ticket_resolu(sender, ticket, company, user, ancien_statut,
                              **kwargs):
    """ARC37 — à la résolution d'un ticket SAV, pose une note chatter ARC8 sur
    le ``crm.Client`` lié (``sav.Ticket.client`` — lien direct, jamais un
    import d'``apps.sav.models``, uniquement l'instance déjà portée par le
    signal). Best-effort : une erreur ici ne doit jamais remonter (la
    résolution, côté ``sav``, est déjà actée)."""
    client = getattr(ticket, 'client', None)
    if client is None:
        return
    try:
        from apps.records.services import log_note

        log_note(
            client, user,
            f'Ticket SAV {ticket.reference} résolu.',
            company=company)
    except Exception:  # noqa: BLE001 — best-effort, ne casse jamais
        logger.warning(
            'ARC37 : chatter ARC8 échoué sur ticket_resolu pour ticket #%s',
            getattr(ticket, 'pk', '?'), exc_info=True)


# ── AOF13 — Appels d'offres : le funnel CRM suit le dossier ─────────────────
#
# ``crm`` n'importe JAMAIS ``apps.ao`` : le signal porte l'instance, et le lead
# n'est connu de l'AO que par ``lead_id`` (entier OPAQUE, jamais une FK — c'est
# ce qui tient le contrat import-linter ``ao-models-decoupled``).

def _lead_de_l_appel_offre(appel_offre, company):
    """Résout le lead lié à un AO, ou ``None``. Jamais d'exception."""
    lead_id = getattr(appel_offre, 'lead_id', None)
    if not lead_id:
        return None
    from .models import Lead
    return Lead.objects.filter(pk=lead_id, company=company).first()


@receiver(ao_depose, dispatch_uid="crm_advance_stage_on_ao_depose")
def _avancer_stage_on_ao_depose(sender, appel_offre, company, user,
                                ancien_statut, **kwargs):
    """Au DÉPÔT d'un dossier d'appel d'offres, avance le lead → QUOTE_SENT.

    Une offre remise à un acheteur EST, au sens du funnel, un devis envoyé.
    ``avancer_stage_lead_vers`` ne recule jamais et est idempotent : un lead
    déjà ≥ QUOTE_SENT ne bouge pas. Best-effort — le dépôt, lui, est déjà acté.
    """
    lead = _lead_de_l_appel_offre(appel_offre, company)
    if lead is None or lead.perdu:
        return
    try:
        avancer_stage_lead_vers(lead, user, stages.QUOTE_SENT)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            "AOF13 : avance de funnel échouée sur ao_depose pour l'AO #%s",
            getattr(appel_offre, 'pk', '?'), exc_info=True)


@receiver(ao_gagne, dispatch_uid="crm_advance_stage_on_ao_gagne")
def _avancer_stage_on_ao_gagne(sender, appel_offre, company, user,
                               ancien_statut, **kwargs):
    """À l'ATTRIBUTION d'un appel d'offres, avance le lead → SIGNED.

    Même garde-fou que ci-dessus (jamais en arrière, jamais sur un lead perdu,
    best-effort). Règle #2 : les clés d'étape viennent de ``STAGES.py``, jamais
    d'un littéral.
    """
    lead = _lead_de_l_appel_offre(appel_offre, company)
    if lead is None or lead.perdu:
        return
    try:
        avancer_stage_lead_vers(lead, user, stages.SIGNED)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            "AOF13 : avance de funnel échouée sur ao_gagne pour l'AO #%s",
            getattr(appel_offre, 'pk', '?'), exc_info=True)


# ── PUB30 — appointment_effectue : transition GÉNUINE Appointment → EFFECTUE ──
# Intra-CRM (comme le récepteur QJ7 sur LeadActivity ci-dessus), pas un
# abonnement M6 — CE module ÉMET ici l'événement dont ``adsengine`` (jamais
# importé par crm) s'abonne dans SON PROPRE apps.py/receivers.py, pour pousser
# un événement CAPI dédié (même famille/gating que ADSENG32).

_APPOINTMENT_OLD_STATUT_ATTR = '_pub30_old_statut'


@receiver(pre_save, sender=Appointment,
          dispatch_uid="crm_capture_appointment_old_statut")
def _capture_appointment_old_statut(sender, instance, **kwargs):
    """Capture l'ANCIEN statut (la base porte encore l'ancienne valeur) avant
    le save — un Appointment neuf (pas de pk) → ancien statut None."""
    old = None
    if getattr(instance, 'pk', None):
        old = (Appointment.objects
               .filter(pk=instance.pk)
               .values_list('statut', flat=True)
               .first())
    setattr(instance, _APPOINTMENT_OLD_STATUT_ATTR, old)


@receiver(post_save, sender=Appointment,
          dispatch_uid="crm_emit_appointment_effectue")
def _emit_appointment_effectue_on_transition(sender, instance, created,
                                             **kwargs):
    """Sur une transition GÉNUINE vers EFFECTUE, émet ``appointment_effectue``.

    Un save qui laisse le statut inchangé (ex. édition des notes d'un RDV déjà
    EFFECTUE) ne réémet JAMAIS — même garde que ADSENG32
    (``capi_crm._emit_on_stage_change``). Best-effort : un abonné en échec ne
    casse jamais le save du rendez-vous."""
    new_statut = getattr(instance, 'statut', None)
    if new_statut != Appointment.Statut.EFFECTUE:
        return
    old_statut = getattr(instance, _APPOINTMENT_OLD_STATUT_ATTR, None)
    if not created and old_statut == new_statut:
        return  # save sans changement de statut → rien à émettre.
    try:
        appointment_effectue.send(
            sender='crm.Appointment', appointment=instance,
            company=instance.company, user=None, ancien_statut=old_statut)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'PUB30 : émission appointment_effectue échouée pour le '
            'rendez-vous #%s', getattr(instance, 'pk', '?'), exc_info=True)
