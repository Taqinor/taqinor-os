"""Couche d'événements métier (M6) — petit bus d'événements interne basé sur
les signaux Django, pour découpler les apps du cœur métier.

Une app émettrice (ex. ``ventes``) envoie un événement ; les apps intéressées
(``crm``, ``installations``, ``audit``…) s'y abonnent via un récepteur câblé
dans leur ``apps.py`` (``ready()``). Cela évite qu'une app importe directement
les ``models`` / ``services`` d'une autre uniquement pour réagir à un changement
d'état : l'émetteur ne connaît pas ses abonnés.

``core`` est une app de fondation : elle ne dépend d'aucune app métier, donc
placer le bus ici n'introduit aucun cycle d'import.

Carte des trois couches (M4)
----------------------------

Le repo est organisé en trois couches, chacune ne dépendant QUE de couches en
dessous d'elle ; les réactions inter-app montantes passent par ce bus, jamais
par un import direct des ``models`` / ``views`` d'une autre app :

* **Fondation** — ``authentication``, ``roles``, ``records``, ``customfields``,
  ``core`` (dont ce bus). Ne dépend d'aucune app métier.
* **Cœur métier** — ``crm``, ``stock``, ``ventes``, ``installations``, ``sav``.
  Se parlent via ``services.py`` / ``selectors.py`` (jamais les ``models`` /
  ``views`` d'une autre), et réagissent aux autres via ce bus.
* **Satellites** — ``reporting``, ``automation``, ``monitoring``,
  ``notifications``, ``publicapi``, ``audit``, ``documents``, ``dataimport``,
  ``contact``. Observent le cœur métier ; le cœur métier ne les importe pas.

M4 a supprimé la dernière arête montante ``ventes → audit`` : ``ventes`` émet
désormais ``document_pdf_generated`` et le satellite ``audit`` s'y abonne
(``apps/audit/receivers.py``) pour journaliser le PDF, sans que ``ventes``
importe ``apps.audit``.

Événements disponibles
----------------------

``devis_accepted``
    Émis quand un devis passe à « accepté » (action explicite ``accepter``).
    Arguments du signal :

    * ``devis`` — l'instance ``Devis`` acceptée ;
    * ``user`` — l'utilisateur qui accepte (peut être ``None``) ;
    * ``ancien_statut`` — le statut du devis avant l'acceptation.

``devis_sent``
    Émis quand un devis passe à « envoyé » suite à un partage client (U4), p.
    ex. la génération d'un lien WhatsApp. Abonné par ``crm`` pour avancer
    l'étape du lead vers QUOTE_SENT. Arguments du signal :

    * ``devis`` — l'instance ``Devis`` envoyée ;
    * ``user`` — l'utilisateur qui partage (peut être ``None``) ;
    * ``ancien_statut`` — le statut du devis avant l'envoi.

``devis_expired``
    Émis quand un devis ``envoyé`` bascule automatiquement en ``expiré``
    (QJ5, ``expire_stale_devis``) — YEVNT2. Jamais réémis pour un devis déjà
    ``expiré`` (no-op). Abonné dans ce repo : ``notifications`` (notifie le
    propriétaire du devis, ``EventType.DEVIS_EXPIRED``) ; ``crm`` continue
    d'avancer le funnel séparément (avancement direct dans le même appel,
    clés ``STAGES.py`` uniquement). Arguments du signal :

    * ``devis`` — l'instance ``Devis`` désormais ``expire`` ;
    * ``ancien_statut`` — toujours ``'envoye'``.

``document_pdf_generated``
    Émis quand un PDF de document de vente est généré (devis ou facture).
    Abonné par le satellite ``audit`` (journalise une entrée ``AuditLog.PDF``).
    Arguments du signal :

    * ``instance`` — l'objet ``Devis`` ou ``Facture`` concerné ;
    * ``kind`` — ``'devis'`` ou ``'facture'`` (sert au libellé d'audit).

``reception_fournisseur_confirmee``
    Émis à la CONFIRMATION d'une réception fournisseur (fin de
    ``stock.services.confirm_reception_fournisseur``). Arguments du signal :

    * ``reception`` — l'instance ``stock.ReceptionFournisseur`` confirmée ;
    * ``company`` — la société (posée côté serveur) ;
    * ``user`` — l'utilisateur qui confirme (peut être ``None``).

    DEUX abonnés indépendants sont attendus sur ce même événement (documentés
    ici pour éviter toute re-création accidentelle d'un événement jumeau) :

    * ``qhse`` (XQHS3) — ouvre un ``ControleReception`` si un
      ``PlanControleReception`` couvre le produit/catégorie reçu (contrôle
      qualité à réception + quarantaine) ;
    * ``installations`` (YPROC3, à construire séparément) — crée la provision
      GR/IR (``ReceptionNonFacturee``).

    ``stock`` n'importe ni ``qhse`` ni ``installations`` : chaque abonné se
    câble dans son propre ``apps.py`` ``ready()``.

``employe_sorti``
    Émis à la fin de ``rh.services.sortir_employe`` (YHIRE2) — orchestration
    de sortie : checklist ``ElementSortie`` générée, compte utilisateur
    désactivé, PUIS cet événement. Arguments du signal :

    * ``dossier`` — l'instance ``rh.DossierEmploye`` sortie ;
    * ``user`` — le compte utilisateur lié (peut être ``None``) ;
    * ``motif`` — le motif de sortie (``DossierEmploye.MotifSortie``).

    Abonné dans ce repo : ``paie`` (``apps/paie/receivers.py``) — passe
    ``ProfilPaie.actif=False`` pour le dossier lié, SANS que ``rh`` importe
    jamais ``apps.paie`` directement (même pattern que ``devis_accepted`` →
    ``crm``).

``conge_approuve``
    Émis quand une ``rh.DemandeConge`` passe à VALIDÉE (FG163,
    ``rh.services.valider_demande``) OU est annulée après validation
    (``rh.services.annuler_demande``) — XPRJ9. Abonné par ``gestion_projet``
    (crée/ferme automatiquement l'``Indisponibilite`` de type congé de la
    ``RessourceProfil`` liée au même utilisateur, sans que ``rh`` importe
    ``gestion_projet``). Arguments du signal :

    * ``demande`` — l'instance ``rh.DemandeConge`` concernée ;
    * ``user`` — l'utilisateur qui décide (peut être ``None``) ;
    * ``annule`` — ``True`` si l'événement correspond à une ANNULATION d'une
      demande précédemment validée (ferme l'indisponibilité), ``False`` pour
      une validation (crée/étend l'indisponibilité).

``contrat_signe``
    Émis EXACTEMENT une fois quand un ``contrats.Contrat`` bascule vers
    ``signe`` (dernier signataire requis, CONTRAT16) — YDOCF5. Émis par
    ``contrats.services.signer_contrat``, jamais un import direct par les
    abonnés. Arguments du signal :

    * ``contrat`` — l'instance ``contrats.Contrat`` concernée ;
    * ``user`` — l'utilisateur agissant (peut être ``None`` pour une partie
      externe) ;
    * ``company`` — la société (posée côté serveur).

    Abonnés dans ce repo (ARC35) : ``contrats`` lui-même
    (``apps/contrats/receivers.py`` — note chatter ARC8 via
    ``records.services.log_note`` + dépôt GED du contrat signé via
    ``deposer_contrat_signe_en_ged``, sur le patron émetteur=abonné de
    ``qhse.receivers``) et ``notifications``
    (``apps/notifications/signals.py`` — notifie l'utilisateur signataire,
    repli managers, ``EventType.CONTRAT_SIGNE``). Reste ouvert à un futur
    abonné pour la facturation récurrente (CONTRAT31/FG40) ou une
    vérification d'entitlement SAV.

``contrat_actif``
    Émis EXACTEMENT une fois quand un ``contrats.Contrat`` bascule vers
    ``actif`` (activation automatique à la signature si la prise d'effet est
    atteinte, CONTRAT17, ou toute future activation manuelle qui passe par
    ``contrats.services.activer_si_eligible``) — YDOCF5. Mêmes arguments que
    ``contrat_signe`` (``contrat``, ``user``, ``company``). ``Contrat.statut``
    n'est jamais modifié par ce module lui-même (préservation des statuts,
    CONTRAT12) : le bus ne fait qu'observer la bascule déjà actée par la
    machine d'états gardée.

    Abonné dans ce repo (ARC35) : ``contrats`` lui-même
    (``apps/contrats/receivers.py`` — note chatter ARC8 ; pas de second dépôt
    GED, déjà couvert par ``contrat_signe`` juste avant dans le même appel).

``contrat_resilie``
    Émis à la FIN de ``contrats.services.resilier_contrat`` (CONTRAT25) —
    YSUBS5. Permet une propagation aval DÉCOUPLÉE (de-provisioning) sans que
    ``contrats`` importe les apps abonnées. Arguments du signal :

    * ``contrat_id`` — id du ``contrats.Contrat`` résilié (pas l'instance —
      un abonné qui a besoin de plus lit via son propre sélecteur/la string-FK
      ``sav_contrat_maintenance_id``) ;
    * ``company`` — la société (posée côté serveur) ;
    * ``date_effet`` — date d'effet de la résiliation (peut être ``None``).

    Abonné dans ce repo : ``sav`` (``apps/sav/receivers.py``) — désactive la
    facturation récurrente et arrête les visites préventives futures du
    ``ContratMaintenance`` lié (résolu via ``Contrat.sav_contrat_maintenance_id``).
    ``contrats.services.resilier_contrat`` passe lui-même les
    ``LigneEcheance`` futures non facturées à ``annulee`` (pas besoin d'un
    abonné pour ça — même module, pas de cross-app).

``facture_paid``
    Émis EXACTEMENT une fois quand une ``ventes.Facture`` passe résiduel→0
    (intégralement réglée) — YDOCF4. DISTINCT de ``payment_captured`` (FG370,
    core/payment.py) : celui-ci ne se déclenche qu'à la capture d'une
    transaction carte EN LIGNE (``core.PaymentTransaction``) ; ``facture_paid``
    couvre TOUT encaissement qui solde la facture, y compris un encaissement
    MANUEL (``enregistrer-paiement``), un webhook de lien de paiement
    (``record_payment_from_link``) ou un passage manuel « marquer payée ».
    Émis par ``apps/ventes/views/facture.py`` et ``apps/ventes/services.py``
    UNIQUEMENT au moment où le résiduel atteint zéro (un paiement partiel
    n'émet rien) ; jamais posé deux fois pour le même règlement. Arguments du
    signal :

    * ``facture`` — l'instance ``ventes.Facture`` désormais soldée ;
    * ``montant`` — montant du DERNIER paiement qui a soldé la facture ;
    * ``company`` — la société (posée côté serveur).

    **DÉPRÉCIÉ POUR L'ABONNEMENT (ARC36).** ``facture_payee`` (YEVNT6,
    ci-dessous) porte le MÊME fait métier, émis aux MÊMES sites au même
    résiduel→0 — deux signaux pour un seul fait = dérive garantie. Les
    abonnés consomment ``facture_payee`` (contrat ``instance, company``) ;
    ne JAMAIS s'abonner aussi à ``facture_paid`` (réaction double au même
    règlement). ``facture_paid`` reste ÉMIS tel quel (compat émetteur — il
    porte ``montant``, absent du frère) et catalogué en seam
    ``ALLOWED_UNCONSUMED`` ; à retirer quand plus aucun site ne l'émettra.

``paiement_rejete``
    Émis quand un ``ventes.Paiement`` encaissé est REJETÉ (chèque revenu
    impayé / virement rejeté) — YLEDG5. La facture concernée est rouverte
    (``montant_du`` remonte, statut recalculé) et les relances existantes sont
    ré-armées AVANT l'émission. Destiné à un abonné compta (extourne
    l'écriture d'encaissement d'origine, YLEDG4) et un délettrage (YLEDG6) ;
    aucun abonné obligatoire dans ce lot (pose du seam). Arguments du signal :

    * ``paiement`` — l'instance ``ventes.Paiement`` désormais ``rejete`` ;
    * ``facture`` — la ``ventes.Facture`` concernée (peut être ``None`` pour
      une avance non affectée) ;
    * ``montant`` — montant du paiement rejeté ;
    * ``company`` — la société (posée côté serveur).

``facture_emise`` / ``facture_payee`` / ``facture_annulee`` / ``bon_commande_cree``
    Événements documentaires ventes EN AVAL du devis — YEVNT6.
    ``ventes.services``/``views.facture`` n'émettaient jusque-là que pour les
    DEVIS (``devis_accepted``/``devis_sent``/``devis_refused``) ; rien pour la
    chaîne BonCommande → Facture. Émission SYNCHRONE, best-effort, aux sites
    de transition réels (``emettre``, ``creer_facture_contrat``,
    ``creer_facture_tranche`` pour ``facture_emise`` ; ``annuler`` pour
    ``facture_annulee`` ; ``convertir_en_bc`` pour ``bon_commande_cree`` ;
    ``facture_payee`` accompagne ``facture_paid`` — YDOCF4 — au même
    résiduel→0). Préserve STRICTEMENT les statuts document (règle #4) :
    l'émission n'en change AUCUN. Arguments communs :

    * ``instance`` — l'objet ``Facture`` ou ``BonCommande`` concerné ;
    * ``company`` — la société (posée côté serveur).

    Abonnés dans ce repo (ARC36) : ``facture_payee`` → ``compta``
    (``apps/compta/receivers.py``, lettrage du solde — idempotent avec le
    chemin YLEDG6 sur ``paiement_enregistre``) + ``notifications``
    (``apps/notifications/signals.py``, notifie le vendeur) ;
    ``bon_commande_cree`` → ``notifications`` (magasinier/managers via
    ``resolve_recipients``, routable par ``NotificationRoutingRule``).
    ``facture_emise``/``facture_annulee`` avaient déjà leur abonné compta
    (YLEDG1/YLEDG4). C'est ``facture_payee`` — PAS ``facture_paid`` — qui
    est le signal à consommer pour « facture soldée » (cf. dépréciation
    ci-dessus).

``paiement_enregistre`` / ``avoir_cree``
    Complètent ``facture_emise`` côté YLEDG1 : événements documentaires pour
    les deux autres flux du bloc `ecriture_pour_*` (``compta.services``)
    encore appelés uniquement par service explicite. Émis SYNCHRONE,
    best-effort, aux points de création réels : ``paiement_enregistre`` à
    ``ventes.views.facture.FactureViewSet.enregistrer_paiement`` et à
    l'import de relevé (``ventes.paiement_import``) — chaque création d'un
    ``ventes.Paiement`` encaissé (jamais au rejet, cf. ``paiement_rejete`` qui
    reste distinct) ; ``avoir_cree`` à ``creer_avoir``. Ne change AUCUN statut
    document (règle #4). Abonné dans ce repo : ``compta`` (YLEDG1, génère
    l'écriture GL correspondante quand ``COMPTA_AUTO_ECRITURES`` est actif).
    Arguments :

    * ``instance`` — l'objet ``Paiement`` ou ``Avoir`` concerné ;
    * ``company`` — la société (posée côté serveur).

``facture_fournisseur_creee`` / ``paiement_fournisseur_enregistre``
    Symétrique achat de ``facture_emise``/``paiement_enregistre`` — YLEDG2.
    Émis SYNCHRONE, best-effort, au point de création canonique :
    ``stock.views.facture_fournisseur.FactureFournisseurViewSet.
    perform_create`` et ``stock.views.paiement_fournisseur.
    PaiementFournisseurViewSet.perform_create`` (couvre la saisie manuelle ;
    les créations programmatiques OCR/UBL/réception/sous-traitant restent
    hors de ce lot). Abonné dans ce repo : ``compta`` (YLEDG2, appelle
    ``ecriture_pour_facture_fournisseur``/``ecriture_pour_paiement_
    fournisseur`` quand ``COMPTA_AUTO_ECRITURES`` est actif). Arguments :

    * ``instance`` — l'objet ``FactureFournisseur`` ou ``PaiementFournisseur``
      concerné ;
    * ``company`` — la société (posée côté serveur).

``document_produit``
    Émis par une app métier/satellite quand elle produit un fichier destiné à
    être centralisé dans la GED (ZGED6 — pattern Odoo « File centralization »).
    L'émetteur n'importe jamais ``apps.ged`` ; ``ged`` s'abonne dans
    ``apps/ged/apps.py`` ``ready()`` (``apps/ged/receivers.py``) et route le
    fichier via ``ged.services.router_document_module`` si un
    ``RoutageDocumentaire`` existe pour la ``source`` — sinon no-op silencieux
    (comportement actuel inchangé). Arguments du signal :

    * ``source`` — code de module (ex. ``paie_bulletin``, ``rh_document``,
      ``sav_piece_jointe``, ``ventes_facture``) — doit correspondre à la
      ``source`` d'un ``RoutageDocumentaire.company`` ;
    * ``company`` — la société (posée côté serveur) ;
    * ``file`` — le fichier (objet file-like, passé à
      ``records.storage.store_attachment``) ;
    * ``filename`` — nom de fichier lisible ;
    * ``reference`` — référence métier stable de l'objet source (ex. numéro de
      bulletin) — sert de clé d'IDEMPOTENCE (ré-émettre le même
      ``source``+``reference`` ne dépose pas deux fois le même document) ;
    * ``contexte`` — dict de valeurs pour résoudre les jetons ``{{ champ }}``
      du ``dossier_cible`` (ex. ``{"annee": 2026}``) ;
    * ``uploaded_by`` — utilisateur à l'origine du fichier (peut être
      ``None``).

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
    inchangé). ``installations`` n'importe jamais ``apps.compta`` — même
    patron que ``devis_accepted`` → ``crm``. Arguments du signal :

    * ``installation`` — l'instance ``installations.Installation`` désormais
      RECEPTIONNE ;
    * ``user`` — l'utilisateur qui a déclenché la transition (peut être
      ``None``) ;
    * ``ancien_statut`` — le statut BRUT (non canonicalisé) avant la
      transition.

``ticket_resolu``
    Émis quand un ``sav.Ticket`` bascule vers RESOLU (ARC37) — aux DEUX sites
    où cette bascule peut être atteinte : l'action gardée ``resoudre``
    (``apps/sav/views.py``, via ``sav.services.emettre_ticket_resolu``) et
    l'avancement automatique sur intervention terminée
    (``apps/sav/receivers.py``, YSERV2). Émis SYNCHRONE, best-effort,
    uniquement sur le FRANCHISSEMENT (un ticket déjà RESOLU/CLOTURE ne réémet
    rien — même garde que les autres transitions SAV). Ne change AUCUN statut
    lui-même (l'émission suit la bascule déjà actée). Arguments du signal :

    * ``ticket`` — l'instance ``sav.Ticket`` désormais RESOLU ;
    * ``company`` — la société (posée côté serveur) ;
    * ``user`` — l'utilisateur qui a déclenché la transition (peut être
      ``None`` pour une résolution automatique) ;
    * ``ancien_statut`` — le statut avant la transition.

    Abonnés dans ce repo (ARC37) : ``notifications``
    (``apps/notifications/signals.py`` — notifie le technicien assigné, repli
    managers, ``EventType.SAV_TICKET_RESOLU``) et ``crm``
    (``apps/crm/receivers.py`` — note chatter ARC8 sur le ``crm.Client`` du
    ticket, sans jamais importer ``apps.sav``).

``equipement_remplace``
    Émis quand un ``sav.Equipement`` est marqué REMPLACE suite au retrait
    d'une pièce (ARC37, ``sav.services.retirer_piece``). Émis SYNCHRONE,
    best-effort, à l'unique site de la bascule. Ne change AUCUN statut
    lui-même. Arguments du signal :

    * ``equipement`` — l'instance ``sav.Equipement`` désormais REMPLACE ;
    * ``ticket`` — le ``sav.Ticket`` dont le retrait de pièce a déclenché le
      remplacement ;
    * ``company`` — la société (posée côté serveur) ;
    * ``user`` — l'utilisateur qui a retiré la pièce (peut être ``None``).

    Abonné dans ce repo (ARC37) : ``notifications``
    (``apps/notifications/signals.py`` — notifie les managers,
    ``EventType.SAV_EQUIPEMENT_REMPLACE``).

``projet_status_change``
    Émis quand un ``gestion_projet.Projet`` change de statut (ARC37) — posé
    dans ``gestion_projet.services.notifier_transition_projet`` (même site
    que l'émission EXISTANTE vers le moteur ``automation`` N72/N73, qui reste
    inchangée : les DEUX chemins cohabitent, ``automation`` en direct ET ce
    signal sur le bus, pour ouvrir un abonné DÉCOUPLÉ sans importer
    ``apps.automation``). Émis SYNCHRONE, best-effort. Arguments du signal :

    * ``projet`` — l'instance ``gestion_projet.Projet`` concernée ;
    * ``company`` — la société (posée côté serveur) ;
    * ``user`` — l'utilisateur qui a déclenché la transition (peut être
      ``None``) ;
    * ``ancien_statut`` / ``nouveau_statut`` — l'instantané avant/après.

    Abonné dans ce repo (ARC37) : ``notifications``
    (``apps/notifications/signals.py`` — notifie le responsable du projet,
    ``EventType.PROJET_STATUT_CHANGE``).

``incident_declared``
    Émis quand un ``qhse.Incident`` (QHSE29) est déclaré/créé via le chemin
    canonique de création (``IncidentViewSet.perform_create``) — ARC38,
    RAPATRIEMENT sur le bus d'un signal jusque-là LOCAL à l'app ``qhse``
    (``apps/qhse/receivers.py``, posé par QHSE32 car à l'époque émetteur ET
    abonné étaient la même app, donc invisible à tout abonné cross-app).
    PÉRIODE DE DOUBLE ÉMISSION assumée et documentée : le site d'émission
    (``IncidentViewSet.perform_create``) envoie D'ABORD le signal LOCAL
    ``qhse.receivers.incident_declared`` (comportement QHSE32 inchangé —
    l'escalade chatter/notification/audit interne à ``qhse`` continue de
    fonctionner à l'identique) PUIS ce signal BUS (``core.events.
    incident_declared``) pour toute réaction cross-app future. Le retrait du
    signal local est un pas ULTÉRIEUR distinct (non fait ici — double émission
    délibérément conservée le temps que d'éventuels abonnés externes migrent).
    Arguments du signal (identiques au signal local) :

    * ``incident`` — l'instance ``qhse.Incident`` créée ;
    * ``company`` — la société (posée côté serveur) ;
    * ``user`` — l'utilisateur qui déclare (peut être ``None``) ;
    * ``gravite`` — la gravité de l'incident (``mineure`` / ``majeure`` /
      ``critique``).

    Abonné dans ce repo (ARC38) : ``qhse`` lui-même se réabonne à SON PROPRE
    signal bus (``apps/qhse/receivers.py``, même patron émetteur=abonné que
    ``contrats``/``contrat_signe``) pour prouver la visibilité cross-app avec
    un abonné réel plutôt qu'un simple seam — journalise une entrée d'audit
    dédiée (``apps.audit.recorder``) distincte de celle déjà posée par le
    récepteur du signal local (YEVNT12), preuve qu'un abonné EXTERNE
    hypothétique recevrait bien l'événement sans importer ``apps.qhse``.

    ``publicapi`` — DÉCISION (ARC38) : ``apps/publicapi/signals.py`` reste
    volontairement LOCAL et NE SOUSCRIT PAS à ``incident_declared``. Ce module
    diffuse des WEBHOOKS SORTANTS vers des intégrations CLIENT externes
    (``lead.*``/``devis.*``/``facture.*``/``ticket.*`` — catalogue fermé,
    ``apps/publicapi/constants.py``) : un incident QHSE est une donnée
    INTERNE de sécurité de site, jamais un événement métier CLIENT-FACING.
    Aucun abonné cross-app légitime n'existe aujourd'hui pour ce cas —
    documenté ici plutôt que migré, conformément à la consigne ARC38
    (« vérifier puis migrer si valeur cross-app, sinon documenter le choix
    local »).
"""
import django.dispatch

# ADSDEEP17 — Émis quand un lead Meta Lead Ads est capturé par le webhook CRM
# EXISTANT (``apps/crm/webhooks.meta_lead_ads_webhook``, après
# ``create_lead_from_meta_lead_ads``). Permet à ``adsengine`` de matérialiser un
# ``MetaLeadMirror`` (leads PAR AD) sans que ``crm`` importe ``apps.adsengine``.
# Arguments : lead (crm.Lead), company, leadgen_id, ad_id, adset_id,
# campaign_id, form_id, created_time (str|None), is_organic (bool). Abonné dans
# ce repo : adsengine (apps/adsengine/receivers.py).
meta_lead_captured = django.dispatch.Signal()

# Émis à l'acceptation d'un devis.
# Abonné dans ce repo : crm (avance l'étape du lead → SIGNED).
devis_accepted = django.dispatch.Signal()

# Émis à l'ENVOI d'un devis (U4) — passage brouillon → envoyé déclenché par un
# partage client (ex. lien WhatsApp). Arguments : devis, user, ancien_statut.
# Abonné dans ce repo : crm (avance l'étape du lead → QUOTE_SENT), exactement
# comme devis_accepted, pour que ventes n'importe jamais crm directement.
devis_sent = django.dispatch.Signal()

# Émis au refus d'un devis (FG44).
# Arguments : devis, user, motif_refus.
# Abonné optionnellement par crm pour marquer le lead perdu (→ COLD + perdu).
devis_refused = django.dispatch.Signal()

# Émis quand un devis envoyé bascule automatiquement en « expiré » (QJ5,
# ``expire_stale_devis``) — YEVNT2. Arguments : devis, ancien_statut='envoye'.
# Abonné dans ce repo : notifications (notifie le propriétaire).
devis_expired = django.dispatch.Signal()

# Émis à la génération d'un PDF de document de vente (devis/facture) — M4.
# Arguments : instance (Devis|Facture), kind ('devis'|'facture').
# Abonné par le satellite audit (journalise AuditLog.Action.PDF), ce qui évite
# que ventes importe apps.audit (suppression de l'arête montante ventes→audit).
document_pdf_generated = django.dispatch.Signal()

# Émis quand une transaction de paiement carte en ligne est capturée (FG370).
# Arguments : transaction (core.PaymentTransaction), company.
# Destiné à être abonné par l'app comptable pour matérialiser un ``Paiement``
# et rapprocher la facture — core n'importe jamais l'app comptable lui-même.
payment_captured = django.dispatch.Signal()

# Émis à la CONFIRMATION d'une réception fournisseur (XQHS3 / YPROC3).
# Arguments : reception (stock.ReceptionFournisseur), company, user.
# cf. docstring du module ci-dessus pour la carte des deux abonnés attendus.
reception_fournisseur_confirmee = django.dispatch.Signal()

# (Le signal ``facture_fournisseur_creee`` est défini plus bas, section
# YLEDG2 — contrat unifié ``instance, company, user`` pour ses DEUX abonnés :
# installations (lettrage GR/IR, YPROC3) et compta (écriture, YLEDG2).)

# Émis à la fin de l'orchestration de sortie d'un employé (YHIRE2).
# Arguments : dossier (rh.DossierEmploye), user, motif.
# Abonné dans ce repo : paie (coupe ProfilPaie.actif) — voir docstring du
# module ci-dessus.
employe_sorti = django.dispatch.Signal()

# Émis à la validation (ou l'annulation d'une validation) d'une demande de
# congé RH (FG163) — XPRJ9. Arguments : demande, user, annule.
# Abonné dans ce repo : gestion_projet (crée/ferme l'Indisponibilite de la
# RessourceProfil liée au même utilisateur), pour que rh n'importe jamais
# gestion_projet directement.
conge_approuve = django.dispatch.Signal()

# Émis à la bascule d'un contrat vers « signe » (CONTRAT16) — YDOCF5.
# Arguments : contrat, user, company. Abonnés (ARC35) : contrats lui-même
# (chatter ARC8 + dépôt GED) et notifications — voir docstring du module.
contrat_signe = django.dispatch.Signal()

# Émis à la bascule d'un contrat vers « actif » (CONTRAT17) — YDOCF5.
# Arguments : contrat, user, company. Abonné (ARC35) : contrats lui-même
# (chatter ARC8) — voir docstring du module ci-dessus.
contrat_actif = django.dispatch.Signal()

# Émis à la résiliation d'un contrat (CONTRAT25) — YSUBS5.
# Arguments : contrat_id, company, date_effet. Abonné dans ce repo : sav
# (désactive la facturation récurrente + arrête les visites préventives
# futures du ContratMaintenance lié) — voir docstring du module ci-dessus.
contrat_resilie = django.dispatch.Signal()

# Émis par une app émettrice quand elle produit un fichier à centraliser dans
# la GED (ZGED6). Arguments : source, company, file, filename, reference,
# contexte, uploaded_by. Abonné dans ce repo : ged (apps/ged/receivers.py),
# no-op silencieux si aucun RoutageDocumentaire pour la source — voir
# docstring du module ci-dessus.
document_produit = django.dispatch.Signal()

# Émis quand une Intervention (apps.installations) passe à TERMINEE ou VALIDEE
# (YSERV2). Arguments : intervention, company, user (peut être None). Abonné
# dans ce repo : sav (apps/sav/receivers.py) — si l'intervention porte un
# ticket lié, pose Ticket.date_resolution et avance le ticket vers RESOLU
# (idempotent, ne recule jamais un statut). installations n'importe jamais
# apps.sav — même patron que devis_accepted → crm.
intervention_completed = django.dispatch.Signal()

# Émis EXACTEMENT une fois quand une Facture passe résiduel→0 (YDOCF4).
# Arguments : facture, montant, company. DISTINCT de payment_captured (capture
# carte en ligne uniquement) — voir docstring du module ci-dessus.
facture_paid = django.dispatch.Signal()

# Émis quand un ``ventes.Paiement`` encaissé est REJETÉ (chèque impayé /
# virement rejeté) — YLEDG5. Arguments : paiement, facture, montant, company.
# Destiné à un abonné compta (extourne l'écriture d'encaissement, YLEDG4) et
# délettrage (YLEDG6) — aucun abonné obligatoire dans ce lot (pose du seam).
paiement_rejete = django.dispatch.Signal()

# YEVNT6 — événements documentaires ventes en aval du devis (émission
# SYNCHRONE, best-effort ; ne change JAMAIS un statut/PDF — règle #4).
# Arguments communs : instance (Facture|BonCommande), company. Aucun abonné
# obligatoire dans ce lot (pose du seam pour compta/notifications/audit/KPI).
facture_emise = django.dispatch.Signal()
facture_payee = django.dispatch.Signal()
facture_annulee = django.dispatch.Signal()
bon_commande_cree = django.dispatch.Signal()

# YLEDG1 — complètent facture_emise pour le bloc ecriture_pour_* (compta) :
# chaque création d'un ventes.Paiement encaissé / ventes.Avoir. Arguments
# communs : instance, company. Abonné dans ce repo : compta (génère
# l'écriture GL correspondante, cf. docstring du module ci-dessus).
paiement_enregistre = django.dispatch.Signal()
avoir_cree = django.dispatch.Signal()

# YLEDG2 / YPROC3 — CRÉATION d'une stock.FactureFournisseur (saisie manuelle
# via la vue, OU construite par ``stock.services.facturer_reception`` depuis
# une réception). Contrat UNIFIÉ (un seul signal, deux abonnés) :
#   Arguments : instance (stock.FactureFournisseur), company, user (peut être
#   None pour une création système/hors-requête).
#   Abonnés : compta (``ecriture_pour_facture_fournisseur``, YLEDG2) et
#   installations (lettre les provisions GR/IR ouvertes du BCF, YPROC3).
# ``stock`` n'importe jamais compta/installations — même patron que
# ``devis_accepted``. `paiement_fournisseur_enregistre` : instance, company.
facture_fournisseur_creee = django.dispatch.Signal()
paiement_fournisseur_enregistre = django.dispatch.Signal()

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

# YLEDG10 — un effet À RECEVOIR créé depuis un règlement chèque client
# (``compta.services.enregistrer_effet_pour_paiement_cheque``) est rejeté par
# la banque (``compta.services.rejeter_effet``). Arguments : effet
# (compta.Effet), paiement_id (id du ventes.Paiement d'origine, jamais
# l'instance — cross-app string-ref), frais (Decimal, peut être 0), company.
# Abonné dans ce repo : ventes (``apps/ventes/receivers.py``), qui route vers
# le rejet de paiement existant (YLEDG5) pour rouvrir la facture ET tracer
# les frais. ``compta`` n'importe jamais ``apps.ventes``.
effet_rejete = django.dispatch.Signal()

# YSUBS4 — un ``compta.AbonnementMonitoring`` est résilié
# (``services.resilier_abonnement_monitoring``). Arguments : abonnement
# (compta.AbonnementMonitoring), motif (str), company. Abonné dans ce repo
# (ARC36) : ``monitoring`` (``apps/monitoring/receivers.py``) — coupe la
# supervision automatique liée (``MonitoringConfig.enabled=False`` pour
# ``installation_id``), sans jamais importer ``apps.compta`` (abonnement par
# NOM de signal : l'émetteur bougera avec ODX16/17-20 sans casser l'abonné).
abonnement_monitoring_resilie = django.dispatch.Signal()

# Émis quand une Installation atteint le statut canonique RECEPTIONNE
# (YSERV4). Arguments : installation, user (peut être None), ancien_statut.
# Abonné dans ce repo : compta (crée l'EnqueteNPS + envoyer_enquete_nps,
# idempotent) — voir docstring du module ci-dessus.
chantier_receptionne = django.dispatch.Signal()

# Émis quand un Ticket SAV bascule vers RESOLU (ARC37). Arguments : ticket,
# company, user (peut être None), ancien_statut. Abonnés dans ce repo :
# notifications (EventType.SAV_TICKET_RESOLU) et crm (chatter ARC8 sur le
# Client lié) — voir docstring du module ci-dessus.
ticket_resolu = django.dispatch.Signal()

# NTCRM12 — Émis quand ``crm.Lead.stage`` change (à N'IMPORTE quel point
# d'entrée : avance auto premier contact, avance auto devis envoyé/accepté,
# réactivation YLEAD11, avance manuelle depuis l'écran lead). Arguments :
# lead, old_stage, new_stage, user (peut être None — transitions système).
# Abonné dans ce repo : crm lui-même (``apps/crm/receivers.py``) — génère la
# progression des tâches du playbook actif de la nouvelle étape
# (``LeadPlaybookProgress``), même patron émetteur=abonné que
# ``incident_declared``/``contrat_signe`` (preuve de visibilité cross-app
# sans import direct).
lead_stage_changed = django.dispatch.Signal()

# Émis quand un Equipement SAV est marqué REMPLACE suite au retrait d'une
# pièce (ARC37). Arguments : equipement, ticket, company, user (peut être
# None). Abonné dans ce repo : notifications (EventType.
# SAV_EQUIPEMENT_REMPLACE) — voir docstring du module ci-dessus.
equipement_remplace = django.dispatch.Signal()

# Émis quand un Projet (gestion_projet) change de statut (ARC37). Arguments :
# projet, company, user (peut être None), ancien_statut, nouveau_statut. Le
# chemin EXISTANT vers le moteur automation (N72/N73) reste inchangé et
# cohabite avec ce signal (double émission assumée, transition documentée).
# Abonné dans ce repo : notifications (EventType.PROJET_STATUT_CHANGE) — voir
# docstring du module ci-dessus.
projet_status_change = django.dispatch.Signal()

# Émis quand un Incident QHSE (QHSE29) est déclaré (ARC38 — rapatrié du signal
# LOCAL qhse.receivers.incident_declared, conservé en DOUBLE ÉMISSION pendant
# la transition). Arguments : incident, company, user (peut être None),
# gravite. Abonné dans ce repo : qhse lui-même (audit dédié) — voir docstring
# du module ci-dessus. Décision publicapi (pas d'abonné) documentée aussi
# ci-dessus.
incident_declared = django.dispatch.Signal()

# Émis par le kit DocumentMetier (SCA30, ``core.documents``) quand un document
# métier change de statut via ``changer_statut()`` gardé côté service. GÉNÉRIQUE
# (un seul signal pour tout document composant le kit) — le cycle de vie PROPRE
# du document, DISTINCT du cycle d'APPROBATION qui reste ARC10/WorkflowDefinition.
# EXCLUSION PERMANENTE (règle #4) : Devis/Facture/BonCommande/Avoir ne sont
# JAMAIS rétrofittés sur le kit ; ce signal ne les concerne donc jamais.
# Arguments : instance (le document), ancien_statut, nouveau_statut,
# user (peut être None), company. Aucun abonné obligatoire (pose du seam pour
# audit/notifications/KPI d'un futur type de document construit sur le kit).
document_statut_change = django.dispatch.Signal()

# NTFPA29 — Émis EXACTEMENT une fois quand un ``fpa.CycleBudgetaire`` passe à
# ``clos`` (action ``clore`` gardée côté service FP&A). Pose le crochet pour
# qu'un futur module (paie, reporting…) réagisse à la clôture d'un cycle
# budgétaire sans couplage direct. Aucun abonné requis dans le lot NTFPA.
# Arguments : company, cycle_id, totaux (dict, ex. {'total_depenses': ...}).
budget_cycle_clos = django.dispatch.Signal()


# NTADM40 — ``apps.entites`` émet ces 2 événements à la création/désactivation
# d'une ``Entite`` (jamais de suppression dure). Permet à d'autres apps de
# réagir (ex. invalider un cache d'agrégats par entité) sans import direct de
# ``apps.entites.models``. Arguments des deux signaux : ``entite`` (instance
# ``Entite``), ``user`` (peut être None).
entite_created = django.dispatch.Signal()
entite_deactivated = django.dispatch.Signal()

# PUB30 — Émis quand un ``crm.Appointment`` (RDV terrain) bascule vers EFFECTUE
# (transition GÉNUINE — un save sans changement de statut ne réémet jamais).
# Câblé par ``crm`` lui-même (``apps/crm/receivers.py``, un pre_save/post_save
# intra-app comme le récepteur QJ7 sur ``LeadActivity`` juste au-dessus), même
# patron émetteur=abonné-ailleurs que ``ticket_resolu``. Permet à ``adsengine``
# de pousser un événement CAPI CRM-stage dédié (« visite technique effectuée »,
# même famille/gating que ADSENG32 — ``apps/adsengine/capi_crm.py``) sans que
# ``crm`` importe jamais ``apps.adsengine``. Arguments : ``appointment``
# (instance ``crm.Appointment``), ``company``, ``user`` (toujours None
# aujourd'hui — transition détectée par signal modèle, pas par une action
# utilisateur explicite), ``ancien_statut`` (str|None).
appointment_effectue = django.dispatch.Signal()


# ===========================================================================
# NTPLT9/10 — Outbox transactionnel FIABLE (façade au-dessus des signaux M6).
#
# ``emit_reliable(event, **kwargs)`` écrit une ligne ``core.OutboxEvent`` DANS la
# transaction appelante puis, via ``transaction.on_commit``, émet l'événement
# synchrone M6 EXISTANT inchangé (les abonnés actuels ne voient aucune
# différence). Un worker (``core.dispatch_outbox``) livre ensuite la ligne aux
# handlers DURABLES enregistrés par ``subscribe_durable`` — « aucun événement
# perdu, même sur crash ». ``core`` reste fondation : aucun import d'app métier.
# ===========================================================================

# Registre {event_name: [(handler_name, handler, rejouable)]}. Peuplé par les
# apps dans leur ``ready()`` via ``subscribe_durable``.
_DURABLE_HANDLERS: dict = {}


def subscribe_durable(name, handler, *, rejouable=False, handler_name=None):
    """Abonne un handler DURABLE à l'événement ``name`` (livré par l'outbox).

    ``handler(outbox_event)`` reçoit l'instance ``OutboxEvent`` livrée. Doit
    être IDEMPOTENT (la livraison est at-least-once ; la dédup par
    ``(event_id, handler_name)`` garantit l'effet exactement-une-fois).
    ``rejouable=True`` autorise le rejeu ciblé support (NTPLT13). Ré-abonner le
    même ``handler_name`` remplace (idempotent au rechargement d'app)."""
    hname = handler_name or getattr(handler, '__name__', repr(handler))
    entries = _DURABLE_HANDLERS.setdefault(name, [])
    entries[:] = [e for e in entries if e[0] != hname]
    entries.append((hname, handler, bool(rejouable)))


def durable_handlers(name):
    """Handlers durables (liste de tuples) enregistrés pour ``name``."""
    return list(_DURABLE_HANDLERS.get(name, []))


def clear_durable_handlers():
    """Vide le registre des handlers durables (test uniquement)."""
    _DURABLE_HANDLERS.clear()


def _jsonify(value):
    """Rend une valeur JSON-sérialisable pour le payload d'outbox.

    Une instance de modèle → ``{'_model': 'app.Model', 'pk': ...}`` ; un
    datetime → ISO ; les primitives telles quelles ; sinon ``str(value)``.
    """
    from datetime import date, datetime
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    meta = getattr(value, '_meta', None)
    pk = getattr(value, 'pk', None)
    if meta is not None and pk is not None:
        return {'_model': f'{meta.app_label}.{meta.model_name}', 'pk': pk}
    return str(value)


def _resolve_company(company, kwargs):
    """Déduit la société : arg explicite, sinon kwargs, sinon objet portant
    ``company``. Renvoie l'instance/None (jamais une exception)."""
    if company is not None:
        return company
    if 'company' in kwargs and kwargs['company'] is not None:
        return kwargs['company']
    for value in kwargs.values():
        c = getattr(value, 'company', None)
        if c is not None:
            return c
    return None


def emit_reliable(event, *, sender=None, company=None, emitted_by=None,
                  **kwargs):
    """Émet un événement de façon FIABLE : outbox + signal M6 synchrone.

    Écrit une ligne ``OutboxEvent`` dans la transaction courante (payload
    JSON-sérialisé, enveloppe versionnée NTPLT12) puis, sur commit, envoie le
    signal M6 existant ``events.<event>`` avec les kwargs d'origine — les
    abonnés synchrones actuels sont préservés à l'identique. Renvoie
    l'``OutboxEvent`` créé (ou ``None`` si l'événement est inconnu du bus).
    """
    from django.db import transaction

    from .models import OutboxEvent

    signal = globals().get(event)
    if not isinstance(signal, django.dispatch.Signal):
        # Événement inconnu du bus : on n'écrit rien (contrat catalogue NTPLT12
        # le fera échouer en test) et on ne casse pas l'appelant.
        return None

    resolved_company = _resolve_company(company, kwargs)
    payload = {k: _jsonify(v) for k, v in kwargs.items()}
    row = OutboxEvent.objects.create(
        company=resolved_company,
        event_name=event,
        payload=payload,
    )

    send_kwargs = dict(kwargs)

    def _send_sync():
        signal.send(sender=sender or 'core.emit_reliable', **send_kwargs)

    transaction.on_commit(_send_sync)
    return row
