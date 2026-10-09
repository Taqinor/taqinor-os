"""Énumération EventType (types d'événement de notification) — sortie de notifications/models.py par SPL303."""
from django.db import models


class EventType(models.TextChoices):
    """Événements métier déclencheurs de notification (clé EN, libellé FR)."""
    LEAD_ASSIGNED = 'lead_assigned', 'Nouveau lead assigné'
    # CRX27 — DEUX ÉVÉNEMENTS DÉDIÉS, qui empruntaient jusqu'ici la clé
    # ``lead_assigned``. Le défaut du partage : couper « Nouveau lead assigné »
    # dans ses préférences coupait AUSSI, sans le savoir, la détection des
    # comptes dormants et l'escalade des leads non contactés — deux alertes
    # d'un tout autre propos. Chacune a désormais sa clé, son libellé FR et sa
    # préférence propre (défauts génériques : in-app ON, push ON).
    COMPTE_A_REACTIVER = 'compte_a_reactiver', 'Compte à réactiver'
    LEAD_NON_CONTACTE = 'lead_non_contacte', 'Lead non contacté (SLA)'
    # QJ2 — speed-to-lead : nouveau lead entrant (webhook site web).
    LEAD_NEW = 'lead_new', 'Nouveau lead site web'
    DEVIS_ACCEPTED = 'devis_accepted', 'Devis accepté'
    # QJ2 — première ouverture du lien de proposition par le client.
    DEVIS_OPENED = 'devis_opened', 'Proposition ouverte par le client'
    # QX36 — le client RÉPOND par email à une proposition/facture (réponse
    # rattachée au devis via sa référence) : le vendeur est notifié.
    DEVIS_REPLY = 'devis_reply', 'Réponse email du client sur un devis'
    # QX13 — une relance de devis (cadence j+2/j+5/j+10) est DUE : notification
    # in-app au vendeur avec brouillon wa.me + lien proposition prêts.
    DEVIS_NUDGE_DUE = 'devis_nudge_due', 'Relance de devis à faire'
    # QX31be — un lead CHAUD (score élevé) dont la notif d'arrivée reste NON LUE
    # après N minutes : escalade speed-to-lead (21× de qualification si contact
    # < 5 min). Notifie les managers en plus du destinataire initial.
    HOT_LEAD_UNREAD = 'hot_lead_unread', 'Lead chaud non contacté (escalade)'
    # QJ27 — le client demande à être contacté (depuis la proposition publique).
    CLIENT_CONTACT_REQUEST = (
        'client_contact_request', 'Client souhaite être contacté')
    # QJ28 — un vendeur demande l'avis de son supérieur sur un devis.
    DEVIS_SUPERIOR_CONTACT_REQUESTED = (
        'devis_superior_contact_requested',
        'Avis du supérieur demandé sur un devis')
    # QW4 — un lead demande explicitement un RAPPEL téléphonique (distinct
    # d'une simple réponse WhatsApp) : notification à urgence plus élevée.
    LEAD_CALLBACK_REQUESTED = (
        'lead_callback_requested', 'Rappel téléphonique demandé')
    # QW4 — le rappel demandé n'a pas été actionné dans le SLA serré (moitié
    # du SLA générique premier contact) : escalade dédiée.
    LEAD_CALLBACK_SLA_BREACH = (
        'lead_callback_sla_breach', 'Rappel demandé non actionné (SLA)')
    # MRY0 — le filet de rattrapage 15 min a créé un lead Meta que le webhook
    # temps réel n'avait pas livré : le câblage du webhook est à vérifier.
    # Zéro alerte quand le webhook fonctionne (le pull ne crée alors rien).
    LEAD_RATTRAPE = (
        'lead_rattrape', 'Lead Meta rattrapé par le pull (webhook muet)')
    # MRY17 — le digest de 08:30 des touches de cadence dues, et l'alerte
    # quand l'objectif de PREMIER CONTACT est dépassé sur un lead neuf.
    # Deux clés distinctes : couper le digest quotidien ne doit jamais
    # couper au passage l'alerte de speed-to-lead, qui est critique.
    RELANCE_DUE = 'relance_due', 'Relances du jour à faire'
    PREMIER_CONTACT_DEPASSE = (
        'premier_contact_depasse',
        'Nouveau lead non touché (objectif dépassé)')
    # MRY21 — bilan HEBDOMADAIRE du moteur de relances, envoyé à la
    # direction le lundi matin. Clé distincte de `digest` : couper le
    # récapitulatif générique ne doit pas couper le pilotage commercial.
    CRM_BILAN_HEBDO = (
        'crm_bilan_hebdo', 'Bilan hebdomadaire des relances')
    CHANTIER_DUE = 'chantier_due', 'Chantier à installer'
    FACTURE_OVERDUE = 'facture_overdue', 'Facture en retard'
    WARRANTY_EXPIRING = 'warranty_expiring', 'Garantie bientôt expirée'
    MAINTENANCE_DUE = 'maintenance_due', 'Visite de maintenance due'
    STOCK_LOW = 'stock_low', 'Stock bas'
    # ZSTK2 — un lot/réception approche de sa date de péremption (fenêtre
    # configurable par société, cron quotidien).
    STOCK_EXPIRATION_SOON = (
        'stock_expiration_soon', 'Lot bientôt périmé')
    SAV_TICKET_OPENED = 'sav_ticket_opened', 'Ticket SAV ouvert'
    SAV_TICKET_BREACHING = 'sav_ticket_breaching', 'Ticket SAV proche de son délai'
    # ZSAV3 — activité planifiée à échéance sur un ticket SAV (échue, pas faite).
    SAV_ACTIVITE_DUE = 'sav_activite_due', 'Activité SAV à échéance'
    # ZSAV9 — notification d'un suiveur de ticket (note ou transition).
    SAV_TICKET_FOLLOWED_UPDATE = (
        'sav_ticket_followed_update', 'Mise à jour sur un ticket suivi')
    # YSERV5 — génération automatique nocturne de visites préventives dues.
    SAV_VISITES_AUTO_GENEREES = (
        'sav_visites_auto_generees', 'Visites préventives générées automatiquement')
    # Group S — messagerie interne (« Discuss », app ``chat`` — SOLMVP19 ne
    # retire QUE les références notifications→chat ; ``chat`` référence
    # encore CE type directement (attribut Python) tant qu'elle n'est pas
    # elle-même coquillée, SOLMVP33 — jamais retiré avant).
    CHAT_MESSAGE = 'chat_message', 'Nouveau message'
    # VX209(b) — @mention dans une note/activité (`apps.records`), jamais
    # liée à un module de messagerie : reste même après SOLMVP19.
    CHAT_MENTION = 'chat_mention', 'Vous avez été mentionné'
    DIGEST = 'digest', 'Récapitulatif'
    # XKB5 — annonce interne publiée (programmée ou immédiate).
    ANNONCE_PUBLISHED = 'annonce_published', 'Nouvelle annonce interne'
    # XKB6 — relance de lecture obligatoire non confirmée.
    ANNONCE_READ_REMINDER = (
        'annonce_read_reminder', 'Relance lecture obligatoire')
    # YEVNT8 — demandes d'approbation (automation N73).
    APPROVAL_REQUESTED = 'approval_requested', "Approbation demandée"
    APPROVAL_DECIDED = 'approval_decided', "Approbation décidée"
    # YEVNT9 — relance/escalade d'une approbation restée en attente.
    APPROVAL_REMINDER = 'approval_reminder', "Relance d'approbation"
    APPROVAL_ESCALATED = 'approval_escalated', "Approbation escaladée"
    # XPUR1 — document de conformité fournisseur (ARF/CNSS/RC/assurance)
    # expiré ou bientôt expiré.
    SUPPLIER_DOC_EXPIRING = (
        'supplier_doc_expiring', 'Document fournisseur bientôt expiré')
    # XPUR7 — BCF envoyé en retard (prévue/confirmée dépassée, non reçu).
    BCF_LATE = 'bcf_late', 'Bon de commande fournisseur en retard'
    # YPROC7 — un BCF est annulé (cascade sur ses réceptions brouillon).
    BCF_CANCELLED = 'bcf_cancelled', 'Bon de commande fournisseur annulé'
    # ZPUR7 — brouillon de relance PROPOSÉ (jamais envoyé) pour un BCF en
    # retard, distinct de BCF_LATE (l'alerte buyer XPUR7) : jamais de
    # doublon de notification.
    BCF_RELANCE_PROPOSEE = (
        'bcf_relance_proposee', 'Brouillon de relance BCF proposé')
    # XPRJ22 — retard/risque de planning sur un projet (app ``gestion_projet``
    # — SOLMVP19 ne retire QUE les références notifications→gestion_projet ;
    # ``gestion_projet`` référence encore CE type directement tant qu'elle
    # n'est pas elle-même coquillée, SOLMVP33 — jamais retiré avant).
    PROJET_RETARD = 'projet_retard', 'Retard planning projet'
    # XFLT18 — dépassement de budget flotte annuel (par catégorie de coût).
    FLOTTE_BUDGET_DEPASSEMENT = (
        'flotte_budget_depassement', 'Dépassement budget flotte')
    # XFLT24 — géofencing : entrée en zone interdite / mouvement hors plage
    # horaire autorisée, détecté sur les relevés télématiques déjà ingérés.
    FLOTTE_ZONE_ALERTE = (
        'flotte_zone_alerte', 'Alerte géofencing véhicule')
    # XFLT25 — code défaut moteur (DTC) critique détecté sur un relevé
    # télématique (manuel ou fournisseur).
    FLOTTE_DTC_CRITIQUE = (
        'flotte_dtc_critique', 'Code défaut moteur critique (DTC)')
    # ZGED14 — une demande de signature en attente approche de son expiration
    # (versant ÉMETTEUR, complète les relances SIGNATAIRE de XGED2).
    GED_SIGNATURE_EXPIRATION_PROCHE = (
        'ged_signature_expiration_proche',
        'Demande de signature bientôt expirée')
    # YEVNT2 — un devis envoyé a expiré automatiquement (QJ5, date de
    # validité dépassée) sans action du propriétaire.
    DEVIS_EXPIRED = 'devis_expired', 'Devis expiré'
    # YEVNT12 — un incident QHSE CRITIQUE est déclaré (au-delà de la note
    # chatter existante QHSE32) : notifie les responsables QHSE.
    INCIDENT_CRITICAL = 'incident_critical', 'Incident QHSE critique'
    # XMKT35 — un post réseau social planifié arrive à échéance SANS jeton
    # Meta Graph configuré : rappel manuel (texte prêt à coller) à l'auteur.
    POST_SOCIAL_RAPPEL = 'post_social_rappel', 'Post social à publier (rappel)'
    # YSERV11 — réponse NPS promoteur (9-10) : proposer le parrainage au
    # moment de l'enchantement (notification au commercial du client).
    NPS_PROMOTEUR = 'nps_promoteur', 'Client promoteur — proposer le parrainage'
    # ARC36 — une facture est intégralement réglée (résiduel→0, bus
    # ``facture_payee``) : notifie le vendeur (créateur de la facture).
    FACTURE_PAYEE = 'facture_payee', 'Facture intégralement réglée'
    # ARC36 — un bon de commande est créé depuis un devis accepté (bus
    # ``bon_commande_cree``) : notifie le magasinier/managers (routable par
    # ``NotificationRoutingRule`` vers l'utilisateur entrepôt).
    BON_COMMANDE_CREE = 'bon_commande_cree', 'Bon de commande créé'
    # ARC35 — consomme le seam ``contrat_signe`` (bus ``core.events``) :
    # notifie le créateur du contrat (repli managers) qu'un contrat vient
    # d'être intégralement signé.
    CONTRAT_SIGNE = 'contrat_signe', 'Contrat signé'
    # ARC37 — sav devient émetteur du bus (``core.events.ticket_resolu``) :
    # notifie le technicien assigné (repli managers) qu'un ticket est résolu.
    SAV_TICKET_RESOLU = 'sav_ticket_resolu', 'Ticket SAV résolu'
    # ARC37 — sav devient émetteur du bus
    # (``core.events.equipement_remplace``) : notifie les managers qu'un
    # équipement du parc a été remplacé suite à un retrait de pièce.
    SAV_EQUIPEMENT_REMPLACE = (
        'sav_equipement_remplace', 'Équipement SAV remplacé')
    # ARC37 — gestion_projet devient émetteur du bus
    # (``core.events.projet_status_change``) : notifie le responsable du
    # projet d'un changement de statut. Signal DÉCOUPLÉ (aucun import de
    # l'app émettrice ici) — reste câblé après SOLMVP19, voir
    # apps.sav.tests_arc37_bus_emetteur (couverture des signaux non-orphelins).
    PROJET_STATUT_CHANGE = 'projet_statut_change', 'Statut de projet modifié'
    # ARC39 — couverture notifications : le rapport O&M périodique
    # (``monitoring/report.py``) est un envoi CLIENT (PDF joint, reste un
    # ``EmailMessage`` direct — exception documentée comme
    # ``ventes/email_service.py``/``installations/rfq_service.py``) ; cet
    # événement notifie EN INTERNE les responsables qu'un rapport vient
    # d'être envoyé, pour que l'équipe O&M ait enfin une trace côté
    # notifications (jusqu'ici totalement invisible en interne).
    MONITORING_RAPPORT = 'monitoring_rapport', 'Rapport O&M envoyé au client'
    # ARC39 — ARC25 émettait déjà ``notify_many(..., 'paie_rib_divergence',
    # ...)`` sans que ce type soit enregistré (avertissement + notification
    # in-app jamais persistée). Enregistrement de l'événement existant, aucun
    # changement de comportement de l'appelant.
    PAIE_RIB_DIVERGENCE = (
        'paie_rib_divergence', 'Divergence RIB paie ↔ RH')
    # ARC39 — un run de paie (``PeriodePaie``) devient PRÊT (statut
    # ``validee`` : tous ses bulletins sont validés) : notifie les
    # gestionnaires paie que le run peut passer à la génération de l'ordre de
    # virement / la clôture.
    PAIE_RUN_PRET = 'paie_run_pret', 'Run de paie prêt (validé)'
    # NTPAY25 — même cas que PAIE_RIB_DIVERGENCE (ARC39) : la tâche de rappel
    # des échéances déclaratives appelait déjà ``notify_many(...,
    # 'paie_echeance_rappel', ...)`` sans que le type soit enregistré, donc
    # ``notify()`` journalisait « type d'événement inconnu » et ne persistait
    # AUCUNE notification in-app. Enregistrement de l'événement existant ;
    # aucun changement de comportement de l'appelant.
    PAIE_ECHEANCE_RAPPEL = (
        'paie_echeance_rappel', 'Échéance déclarative paie à déposer')
    # VX213 — handoffs AVAL (exécution) longtemps muets. (a) un chantier est
    # créé depuis un devis accepté et assigné à un technicien ; (b) un chantier
    # est réassigné à un NOUVEAU technicien : dans les deux cas l'installateur
    # est notifié (le plus gros transfert de l'entreprise n'est plus silencieux).
    CHANTIER_ASSIGNE = 'chantier_assigne', 'Nouveau chantier assigné'
    # VX213 — le bord RETOUR d'une demande d'achat : à l'approbation OU au refus,
    # le DEMANDEUR (created_by) est notifié de la décision (motif si refus).
    DA_DECIDEE = 'da_decidee', "Demande d'achat décidée"
    # VX213 — SLA : une demande d'achat reste SOUMISE au-delà du seuil sans
    # décision → relance des approbateurs (miroir de sav_ticket_breaching).
    DA_SOUMISE_STALE = 'da_soumise_stale', "Demande d'achat en attente (SLA)"
    # CHT9 — désenchevêtrement : ``CHANTIER_DUE`` (« Chantier à installer »,
    # l'alerte de date de pose/météo de ``tasks.py``) servait aussi, par
    # facilité, à TROIS faits métier sans rapport (réassignation
    # d'intervention, annulation d'intervention, tranche d'échéancier à
    # facturer) : couper ``CHANTIER_DUE`` dans les préférences coupait ces
    # trois-là par ricochet, invisible dans l'écran de préférences. Doctrine :
    # UN ÉVÉNEMENT = UN FAIT MÉTIER — chacun sa clé, son libellé FR, sa
    # préférence propre.
    INTERVENTION_ASSIGNEE = (
        'intervention_assignee', 'Intervention assignée')
    INTERVENTION_REPLANIFIEE = (
        'intervention_replanifiee', 'Intervention replanifiée')
    INTERVENTION_ANNULEE = (
        'intervention_annulee', 'Intervention annulée')
    TRANCHE_A_FACTURER = (
        'tranche_a_facturer', "Tranche d'échéancier à facturer")
    # CHT15 — le bon de commande rattaché à un chantier est CONFIRMÉ (matériel
    # commandé) : notifie le responsable du chantier
    # (``apps.ventes.views.bon_commande.confirmer``).
    CHANTIER_MATERIEL_CONFIRME = (
        'chantier_materiel_confirme', 'Matériel du chantier confirmé')
    # VX210(a) — un item snoozé (``records.Activity`` VX85, ou une approbation
    # VX210(b) via ``SnoozedItem``) revient dans la file : notification
    # LÉGÈRE au propriétaire, jamais une nouvelle demande d'action.
    SNOOZE_REVEIL = 'snooze_reveil', '⏰ De retour'
    # NTSEC12/13/30 — sécurité. ``SECURITY_ALERT`` : anomalie de connexion
    # (voyage impossible, appareil inconnu) notifiée au Directeur.
    # ``SECURITY_CHANGE`` : changement d'un facteur de sécurité (mot de passe,
    # MFA, passkey…) notifié à l'utilisateur concerné — non désactivable.
    SECURITY_ALERT = 'security_alert', 'Alerte de sécurité'
    SECURITY_CHANGE = 'security_change', 'Changement de sécurité'
    # NTIDE16 — une idée (apps.innovation.Idee) ATTEINT le seuil de votes
    # configuré (InnovationSettings.seuil_votes_notification, défaut 3) :
    # notifie l'auteur (in-app + email, préférences respectées par notify()).
    IDEA_VOTE = 'idea_vote', 'Vote reçu sur une idée'
    # NTIDE31 — une campagne d'innovation (apps.innovation.CampagneInnovation)
    # passe brouillon → active : notifie chaque utilisateur du segment ciblé
    # (in-app systématique + email opt-in, préférences respectées par
    # notify()).
    INNOVATION_CAMPAIGN = 'innovation_campagne', "Campagne d'innovation lancée"
    # NTIDE40 — digest (quotidien/hebdo, gated via InnovationSettings.
    # feedback_digest_actif) du feedback produit (apps.innovation.
    # FeedbackProduit) non-lu, par thème — notifie les gérants/staff de
    # chaque société (même patron de destinataires que N76 daily_digest).
    FEEDBACK_DIGEST = 'feedback_digest', 'Récapitulatif feedback produit'
    # NTIDE45 — un feedback produit (apps.innovation.FeedbackProduit) est
    # marqué « étoilé » (important) : notifie les admins/gérants de la
    # société (« founder », si déployé — même patron de destinataires que
    # ``FEEDBACK_DIGEST``), UNE SEULE fois, à la transition False → True.
    FEEDBACK_STARRED = 'feedback_starred', 'Feedback marqué important'
    # NTEDU40 — un élève actif n'a aucune ``education.Inscription`` créée pour
    # l'année scolaire suivante après la date limite paramétrable
    # (``ParametresEducation.date_limite_reinscription``) : notifie
    # l'ADMINISTRATION (jamais les familles directement — contrôle humain).
    EDUCATION_REINSCRIPTION_RELANCE = (
        'education_reinscription_relance', 'Relance réinscription à traiter')
    # NTIDE52 — gabarits e-mail personnalisables des 3 étapes clés du cycle de
    # vie d'une idée (apps.innovation.Idee) : réception (bienvenue, à la
    # création NON brouillon), retenue et réalisée (à la transition de
    # statut) — notifie l'AUTEUR (in-app + email, sujet/corps personnalisables
    # via InnovationSettings, préférences respectées par notify()).
    IDEA_RECEIVED = 'idea_received', 'Idée reçue (bienvenue)'
    IDEA_RETAINED = 'idea_retenue', 'Idée retenue'
    IDEA_REALIZED = 'idea_realisee', 'Idée réalisée'
    # NTADM22 — le support de l'éditeur DEMANDE à ouvrir une session
    # d'assistance sur ce tenant. Notifie les Administrateurs du tenant CIBLE,
    # qui seuls peuvent autoriser : sans leur clic explicite, aucune session
    # n'est ouverte (cf. apps.adminops.impersonation_service).
    IMPERSONATION_REQUESTED = (
        'impersonation_requested', 'Demande de session support')
    # NTADM18 — annonce PRODUIT publiée par l'éditeur (nouveautés de l'ERP,
    # « Quoi de neuf »). Distincte de ANNONCE_PUBLISHED, qui porte les annonces
    # INTERNES d'un tenant à ses propres équipes : ici l'émetteur est l'éditeur
    # et l'audience traverse les sociétés.
    PRODUCT_ANNOUNCEMENT = (
        'product_announcement', 'Nouveauté produit')
    # VAO25 — la collecte du matin a ramené du NOUVEAU. Émise seulement s'il
    # y a quelque chose à dire : une notification quotidienne vide apprend à
    # ignorer les notifications.
    VEILLE_AO_NOUVEAUX_AVIS = (
        'veille_ao_nouveaux_avis', "Nouveaux avis d'appel d'offres")
    # VAO24 — la veille NE RAMÈNE PLUS RIEN (deux jours muets ou deux échecs
    # consécutifs). C'est le seul garde-fou contre le scénario réel : le
    # portail change, la collecte renvoie vide, l'écran reste calme et on se
    # croit couvert pendant des semaines.
    VEILLE_AO_ALARME_SILENCE = (
        'veille_ao_alarme_silence', "Veille appels d'offres muette")
    # NTUX30 — digest hebdomadaire : des favoris épinglés (`uxviews.FavoriUtilisateur`)
    # pointent vers un enregistrement définitivement supprimé (ex. purgé de la
    # corbeille transverse, NTUX29). Jamais de suppression automatique du favori.
    UXVIEWS_FAVORIS_OBSOLETES = (
        'uxviews_favoris_obsoletes', 'Favoris pointant vers des éléments supprimés')
    # NTUX39 — une vue sauvegardée PARTAGÉE À L'ÉQUIPE (`uxviews.SavedView`,
    # NTUX1) est modifiée par son propriétaire (filtres/colonnes) : notifie
    # les utilisateurs qui l'ont consultée récemment (`uxviews.EcranRecent`,
    # substitut serveur de NTUX11 — le widget « Récents » vit en localStorage,
    # jamais transmis au serveur), jamais toute la société.
    UXVIEWS_VUE_EQUIPE_MODIFIEE = (
        'uxviews_vue_equipe_modifiee', "Vue d'équipe modifiée")
    # NTLOG38 — rappel J-3 (beat quotidien) sur une `transport.EtapeTransport`
    # dont `date_prevue` est dépassée et `statut_etape` != fait : notifie le
    # responsable transport (motif `apps.sav.tasks._responsables`), une
    # seule fois par étape et par jour.
    TRANSPORT_ETAPE_RETARD = (
        'transport_etape_retard', 'Étape de transport en retard')
    # NTSCM21 — résumé de la génération mensuelle automatique des prévisions
    # de demande (tâche planifiée `apps.scm.tasks.generer_previsions_
    # mensuelles_task`).
    SCM_PREVISIONS_GENEREES = (
        'scm_previsions_generees', 'Prévisions de demande générées (mensuel)')
    # NTSCM22 — ouverture automatique du cycle S&OP du mois suivant (opt-in
    # par société, `apps.scm.models.ParametresSCM.sop_actif`).
    SCM_CYCLE_SOP_OUVERT = (
        'scm_cycle_sop_ouvert', 'Cycle S&OP ouvert automatiquement')
    # NTRET32 — clôture de SessionCaisse (apps.pos) dont l'écart (espèces ou
    # TPE) dépasse le seuil configuré (Paramètres POS) : notifie les
    # managers/gérants (resolve_recipients). Seuil vide/0 = désactivé,
    # jamais émis.
    CAISSE_ECART_ANORMAL = (
        'caisse_ecart_anormal', 'Écart de caisse anormal')
    # NTSCM45 — MAPE mensuel d'un produit au-delà du seuil configuré
    # (`apps.scm.models.ParametresSCM.seuil_alerte_mape_pct`, défaut 40%,
    # tâche planifiée `apps.scm.tasks.notifier_ecarts_prevision_importants`) :
    # notifie les `records.Follower` explicites du produit, sinon les
    # destinataires résolus (`resolve_recipients` — managers par défaut,
    # ou un rôle dédié via une `NotificationRoutingRule`).
    SCM_ECART_PREVISION_IMPORTANT = (
        'scm_ecart_prevision_important', 'Écart de prévision important (MAPE)')
    # T-TRACE (ordres fondateur 25/08/2026) — les DEUX alertes ROUGES du
    # traçage anti-fraude (`apps.crm.visites`). Classées CRITIQUE dans
    # `severity.py` : elles arrivent en TÊTE de la cloche, devant tout le
    # reste, et vont TOUJOURS au commercial ET à la direction.
    #
    # (a) une NOUVELLE demande de devis arrive depuis un appareil déjà
    #     rattaché à un AUTRE lead de la société — « if he asked for a NEW
    #     quote this should be clearly notified to commercial with red and
    #     director as well ».
    VISITEUR_APPAREIL_PARTAGE = (
        'visiteur_appareil_partage',
        'Nouvelle demande depuis un appareil déjà connu')
    # (b) un MÊME appareil consulte les documents de PLUSIEURS prospects
    #     différents — « notify when two clients have any similar data that
    #     can show it is a competitor ».
    VISITEUR_CONCURRENT_SUSPECTE = (
        'visiteur_concurrent_suspecte',
        'Appareil suivant plusieurs prospects (concurrent suspecté)')
    # VT3 — les deux bords du FEU VERT de la visite technique terrain. Deux
    # clés distinctes à dessein : « ta visite est validée » (bonne nouvelle,
    # informationnelle) et « ta visite revient à refaire » (une ACTION t'est
    # demandée, avec son motif) n'ont ni la même urgence ni la même suite —
    # les fondre aurait obligé le commercial à ouvrir la fiche pour savoir
    # laquelle des deux vient d'arriver.
    VISITE_TERRAIN_VALIDEE = (
        'visite_terrain_validee', 'Visite technique validée (feu vert)')
    VISITE_TERRAIN_A_REFAIRE = (
        'visite_terrain_a_refaire', 'Visite technique à refaire')
    # NTGRC9 — une personne qui a RETIRÉ son consentement est de nouveau
    # traitée (nouveau lead, devis accepté). Alerte de conformité destinée au
    # DPO : elle ne bloque JAMAIS l'opération commerciale, elle la signale —
    # c'est au responsable de trancher, pas à la machine.
    CONSENTEMENT_RETIRE_TRAITE = (
        'consentement_retire_traite',
        'Traitement d\'une personne ayant retiré son consentement')
    # NTAPI11 — un endpoint webhook SORTANT (apps.publicapi.Webhook) accumule
    # assez d'échecs consécutifs pour être considéré MORT : il est
    # automatiquement désactivé, et l'admin du tenant en est averti. La
    # réactivation reste un geste MANUEL explicite — jamais une remise en
    # service automatique vers une cible qui a cessé de répondre.
    API_WEBHOOK_DESACTIVE = (
        'api_webhook_desactive', 'Webhook désactivé automatiquement')
    # NTAPI41 — le taux d'erreur 5xx d'une intégration sortante (webhook) sur
    # une fenêtre glissante dépasse un seuil configurable : notifie l'admin
    # AVANT que le webhook n'atteigne le seuil d'échecs consécutifs qui le
    # désactiverait (NTAPI11, `API_WEBHOOK_DESACTIVE` ci-dessus) — signal
    # précoce, distinct, jamais un doublon de l'alerte de désactivation.
    API_TAUX_ERREUR_ELEVE = (
        'api_taux_erreur_eleve', "Taux d'erreur élevé sur une intégration")
    # NTOBS6 — l'export de réversibilité complet d'un tenant (ZIP CSV+fichiers,
    # core.export_registry) devient téléchargeable : notifie le demandeur avec
    # le lien tokenisé (7 jours, core.signed_download).
    EXPORT_REVERSIBILITE_PRET = (
        'export_reversibilite_pret', 'Export de vos données prêt')
    # NTOBS9 — une fenêtre de maintenance planifiée (core.MaintenanceWindow)
    # approche (24h/1h avant) ou est annulée : notifie les admins concernés.
    MAINTENANCE_WINDOW_ANNOUNCED = (
        'maintenance_window_announced', 'Fenêtre de maintenance annoncée')
    # NTOBS13 — une ressource mesurée (core.usage_limits) franchit 80% ou
    # 100% de son quota : notifie les admins du tenant concerné.
    USAGE_QUOTA_SEUIL_FRANCHI = (
        'usage_quota_seuil_franchi', 'Seuil de quota atteint')
    # VTA7 — « une visite t'est assignée ». Clé DISTINCTE des deux bords du feu
    # vert : c'est le seul message qui arrive AVANT la visite, au commercial
    # terrain, et qui doit atterrir dans sa journée. La fondre avec
    # `visite_terrain_validee` rendrait impossible de couper l'une sans l'autre
    # dans les préférences de notification.
    VISITE_TERRAIN_ASSIGNEE = (
        'visite_terrain_assignee', 'Visite technique assignée')
    # VISITE-CADENCE (fondateur 15/09/2026) — les deux messages qui manquaient
    # APRÈS la visite. Doctrine : la visite technique est un outil de closing
    # posé après l'envoi du devis ; le silence qui suivait le départ du
    # technicien était donc le pire moment possible pour ne prévenir personne.
    #
    # (a) au RESPONSABLE DU LEAD (jamais au commercial terrain, qui vient de
    #     la faire) : « le technicien est reparti, rappelez sous 24-48 h ».
    #     C'est le geste commercial que la visite existe pour provoquer.
    VISITE_RETOUR_TERRAIN = (
        'visite_retour_terrain', 'Retour de visite technique')
    # (b) à ceux qui peuvent VALIDER (bureau d'études) : « une visite terminée
    #     attend ton feu vert ». Clé DISTINCTE de (a) : les deux publics et les
    #     deux suites n'ont rien à voir, et les fondre rendrait impossible de
    #     couper l'une sans l'autre dans les préférences.
    VISITE_TERRAIN_A_VALIDER = (
        'visite_terrain_a_valider', 'Visite technique à valider')
    # NTI18N37 — rappel Beat de fin d'année : les 4 fêtes hégiriennes de
    # l'année N+1 (Aïd el-Fitr, Aïd el-Adha, 1er Moharram, Aïd el-Mawlid,
    # NTI18N33/`apps.parametres.fetes_mobiles`) ne sont pas toutes saisies
    # (`Holiday.recurrent_annuel=False`, NTI18N14) — notifie l'admin RH
    # quotidiennement jusqu'à saisie complète.
    FETES_MOBILES_A_SAISIR = (
        'fetes_mobiles_a_saisir', 'Fêtes mobiles à saisir')
    # NTPRT18 — notifications PORTAIL (compte `CustomUser`
    # `portee=portail_client/portail_fournisseur/portail_partenaire`,
    # NTPRT1/2). Réutilisent le canal `notify()` existant tel quel (in-app +
    # email SendGrid/Brevo-gated) — jamais un second moteur : avant NTPRT18,
    # les rares notifications client-facing (ex. livraisons,
    # `apps.installations.livraison_client_notify`) envoyaient un email
    # directement, hors de ce système de préférences/canal.
    PORTAIL_DEVIS_PRET = (
        'portail_devis_pret', 'Votre devis est prêt')
    PORTAIL_FACTURE_ECHUE = (
        'portail_facture_echue', 'Facture échue')
    PORTAIL_JALON_CHANTIER_ATTEINT = (
        'portail_jalon_chantier_atteint', 'Jalon de chantier atteint')
    PORTAIL_TICKET_MAJ = (
        'portail_ticket_maj', 'Mise à jour de votre ticket')
    # NTWFL18 — le dossier transverse (core.Dossier, NTWFL17) a une échéance
    # dépassée alors qu'il est encore ouvert (balayage quotidien
    # core.dossiers.notifier_echeances_depassees). Notifie le propriétaire.
    DOSSIER_ECHEANCE_DEPASSEE = (
        'dossier_echeance_depassee', 'Dossier en retard (échéance dépassée)')
    # ACHT75 — l'échéance de calibration d'un outil (FG80) est à 30 jours ou
    # moins : `calibrer` et la tâche quotidienne `outillage.calibrations_a_
    # echeance` notifient. Avant, le type n'existait pas (notify() renvoyait
    # None, exception avalée) et aucune notification n'était jamais créée.
    OUTILLAGE_CALIBRATION_PROCHE = (
        'outillage_calibration_proche', "Calibration d'outil proche")
    # ACRM41/ACRM42 — rappel d'une visite planifiée (QJ20) et visite réservée
    # par le prospect via le lien public. `crm.services` émettait déjà
    # 'appointment_reminder' mais le type n'existait pas : notify() renvoyait
    # None et AUCUNE notification n'était jamais créée (même défaut qu'ACHT75).
    APPOINTMENT_REMINDER = (
        'appointment_reminder', 'Rappel de rendez-vous / visite réservée')
    # APAR58 — alertes du moteur de publicité (adsengine) : émises via
    # ``notify_many`` (fenêtre de notification, préférences, module) au lieu
    # d'une écriture directe de ``Notification``.
    ADSENGINE_ALERT = ('adsengine_alert', 'Alerte du moteur de publicité')
