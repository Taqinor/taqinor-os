"""Signaux du bus émis par les apps PARQUÉES (``core/parked.py``).

SPL285 — extrait de ``core/events/__init__.py`` (move only). Ré-exporté
par ``from .parked import *`` dans ``core/events/__init__.py`` :
les émetteurs et abonnés continuent d'importer ``core.events``.

Événements
----------

``employe_sorti``
    Émis à la fin de ``rh.services.sortir_employe`` (YHIRE2) — orchestration
    de sortie : checklist ``ElementSortie`` générée, compte utilisateur
    désactivé, PUIS cet événement. Arguments du signal :

    * ``dossier`` — l'instance ``rh.DossierEmploye`` sortie ;
    * ``user`` — le compte utilisateur lié (peut être ``None``) ;
    * ``motif`` — le motif de sortie (``DossierEmploye.MotifSortie``).

    Abonné historique : le module PAIE (son ``receivers.py``) — passe le
    profil de paie lié à ``actif=False``, SANS que le module RH importe
    jamais la paie directement (même pattern que ``devis_accepted`` →
    ``crm``). Les deux modules sont en Phase 2 (docs/parked-modules.md) : le
    signal reste le point d'accroche du jour où ils reviennent.

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
    hypothétique recevrait bien l'événement sans importer le module QHSE.

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
# ``installation_id``), sans jamais importer l'app émettrice (abonnement par
# NOM de signal : l'émetteur bougera avec ODX16/17-20 sans casser l'abonné).
abonnement_monitoring_resilie = django.dispatch.Signal()

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

# NTFPA29 — Émis EXACTEMENT une fois quand un ``fpa.CycleBudgetaire`` passe à
# ``clos`` (action ``clore`` gardée côté service FP&A). Pose le crochet pour
# qu'un futur module (paie, reporting…) réagisse à la clôture d'un cycle
# budgétaire sans couplage direct. Aucun abonné requis dans le lot NTFPA.
# Arguments : company, cycle_id, totaux (dict, ex. {'total_depenses': ...}).
budget_cycle_clos = django.dispatch.Signal()

# NTSAN23 — Émis quand un ``sante.CycleSterilisation`` est enregistré (ou
# basculé) NON CONFORME. Événement INTER-app véritable : l'émetteur est
# ``sante``, l'abonné est ``qhse`` (``apps/qhse/receivers.py``, câblé dans son
# ``apps.py ready()``), qui ouvre une ``NonConformite`` liée au cycle. C'est
# précisément ce qui permet à ``sante`` de ne JAMAIS importer ``qhse.models``
# (et réciproquement — le lien est une FK à chaîne côté QHSE). Émis sur une
# VRAIE transition seulement : un ``save()`` qui laisse le cycle non conforme
# ne réémet pas. Arguments : ``cycle`` (instance ``CycleSterilisation``),
# ``company``, ``user`` (peut être None).
cycle_sterilisation_non_conforme = django.dispatch.Signal()

# AOF13 — DEUX événements du domaine « appel d'offres », et deux
# seulement : on ne déclare pas ``ao_perdu``/``ao_dossier_pret`` « pour plus
# tard » (un signal sans abonné réel fait rougir ``core.event_coverage``).
# Émis EXCLUSIVEMENT par le service de changement de statut du module appel
# d'offres — jamais depuis un modèle, jamais depuis une vue. Ce module est en
# Phase 2 (docs/parked-modules.md). ALEA3 (D-ALEA-3) : l'abonné ``crm``
# (avance d'étape du lead lié) a été RETIRÉ — il ne pouvait plus rien recevoir
# du module parqué. Les deux signaux restent déclarés (golden SPL283) et sont
# réservés dans ``core.event_coverage`` jusqu'au retour du module.
#
# ``ao_depose``
#     Le dossier est DÉPOSÉ (transition ``pret_a_deposer`` → ``depose``).
#     Aucun abonné vivant. Arguments : ``appel_offre``, ``company``, ``user``
#     (peut être None), ``ancien_statut``.
ao_depose = django.dispatch.Signal()

# ``ao_gagne``
#     L'AO est ATTRIBUÉ (transition ``depose`` → ``gagne``). Aucun abonné
#     vivant. Mêmes arguments que ``ao_depose``.
ao_gagne = django.dispatch.Signal()

# ``lead_maturite_changee``
#     Le score de MATURITÉ marketing (``marketing.ScoreMaturite``, NTMKT18)
#     d'un lead change lors du recalcul quotidien de la pénalité d'inactivité
#     30j (NTMKT34, tâche beat ``marketing.recalculer_scores_maturite_inactivite``).
#     Émis par le recalcul quotidien du module marketing (Phase 2)
#     UNIQUEMENT quand la valeur change réellement (jamais à chaque tick
#     no-op). Distinct du score de QUALITÉ ``crm.Lead.score`` (QJ6, jamais
#     modifié par ce signal). AUCUN abonné dans ce repo aujourd'hui — seam
#     posé pour un futur récepteur ``apps.crm.receivers`` (aucun import direct
#     crm↔marketing, réservé dans ``core.event_coverage``).
#     Arguments : ``lead_id`` (opaque), ``company``, ``ancienne_valeur``,
#     ``nouvelle_valeur``.
lead_maturite_changee = django.dispatch.Signal()

# NTLOG44 — Émis EXACTEMENT une fois quand un dossier d'export douane bascule
# vers CLÔTURÉ (service de clôture du module douane, garde
# idempotente — reclôturer un dossier déjà clôturé ne réémet rien). Des 3
# événements originellement prévus pour ce lot, seul celui-ci est émissible
# depuis la douane : ``ordre_transport_livre``/
# ``litige_transport_ouvert`` appartiennent au domaine du transport
# (lane concurrente) ; ``dossier_import_cloture`` dépendrait de
# ``douane.DossierImport``, qui reste BLOCKED (NTLOG10 — GARDE WIR80, voir
# ``apps/douane/apps.py``). ``dossier_export_cloture`` couvre le volet EXPORT
# réellement construit dans cette app — symétrique par la forme, indépendant
# par le fond, même motif que ``DossierExport`` lui-même. Aucun abonné câblé
# dans ce lot (réservé dans ``core.event_coverage.ALLOWED_UNCONSUMED``, même
# motif « seam » que ``budget_cycle_clos``/``entite_created`` ci-dessus) —
# pose le crochet pour un futur abonné ``publicapi`` (webhook sortant) sans
# que ``douane`` importe cette app. Arguments : ``dossier`` (instance
# ``douane.DossierExport``), ``company``, ``user`` (peut être None),
# ``ancien_statut`` (str, le statut BRUT avant la clôture).
dossier_export_cloture = django.dispatch.Signal()

# NTSCM39 — Émis pour CHAQUE produit que le tableau de bord réappro du module
# SCM (NTSCM7) classe ``rupture_imminente`` (rupture
# projetée AVANT qu'une commande lancée aujourd'hui ne puisse livrer),
# déclenché par sa détection hebdomadaire des ruptures imminentes
# (tâche beat NTSCM35 — pas à chaque lecture du
# tableau de bord, qui serait rejouée à chaque page vue). Abonné par
# ``apps.publicapi`` (webhook sortant ``scm.rupture_imminente_detectee``,
# ``apps/publicapi/scm_event_receivers.py``) sans que le module SCM importe
# cette app (même patron que ``dossier_export_cloture`` ci-dessus).
# Arguments : ``company``, ``produit_id``, ``produit_nom``, ``rupture_date``
# (``str`` ISO-8601 ou ``None`` — déjà sérialisée par ``selectors.
# tableau_bord_reappro``), ``quantite_suggeree``.
scm_rupture_imminente_detectee = django.dispatch.Signal()

# NTSCM39 — Émis EXACTEMENT à la clôture d'un ``scm.CyclePlanificationSOP``
# (service d'avancement de cycle du module SCM, transition vers ``clos`` —
# même point d'ancrage que le hook NTSCM27 de génération du compte-rendu
# .xlsx, juste après). Abonné par ``apps.publicapi`` (webhook sortant
# ``scm.cycle_sop_cloture``). Arguments : ``cycle`` (instance
# ``scm.CyclePlanificationSOP``, déjà ``clos``), ``user`` (peut être None).
scm_cycle_sop_cloture = django.dispatch.Signal()

# NTSCM39 — ADAPTATION DE PÉRIMÈTRE : le plan prévoit un 3ᵉ événement
# ``scm.score_fournisseur_degrade`` (« émis par NTSCM23 ») — NTSCM23 (score
# fournisseur) n'existe pas dans ``docs/plans/PLAN_SUPPLY.md`` (aucune tâche
# de ce nom, contrairement à NTSCM8/9/11/17/26 qui EXISTENT mais sont encore
# ``[ ]``). Sans fonctionnalité source, aucun signal n'est déclaré ici : un
# signal jamais émis serait un seam creux, pas un contrat. Un futur task
# scorant les fournisseurs pourra l'ajouter ici sans rien casser.

# NTJUR26 — Émis EXACTEMENT à la clôture d'un ``juridique.DossierJuridique``
# (service de clôture du module juridique, transition vers l'un des quatre
# statuts ``clos_*``). L'abonné historique est le ``receivers.py`` de ce même
# module : il lève la bannière « reprendre la provision » (NTJUR15) —
# une PROPOSITION, jamais une écriture. La comptabilité peut s'y abonner de la
# même façon pour proposer la reprise depuis son propre écran, sans que le
# juridique l'importe. Les deux modules sont en Phase 2
# (docs/parked-modules.md).
# GARANTIE : cet événement ne poste JAMAIS d'écriture comptable — la reprise
# reste gardée par une confirmation explicite (patron « propose → confirme »).
# Arguments : ``dossier`` (l'instance close), ``company``, ``resultat`` (le
# statut ``clos_*`` atteint), ``montant_final`` (Decimal — le montant en jeu
# arrêté), ``user`` (peut être ``None``).
dossier_juridique_clos = django.dispatch.Signal()

# ── NTCON31 — Événements du vertical BTP/EPC ────────────────────────────────
# Les quatre gestes que la MOE/le client externe attend d'être notifiés. Émis
# par les services du module chantier BTP (le SEUL point d'écriture d'état du
# module, en Phase 2), abonnés par ``apps.publicapi`` (webhook sortant, voir
# ``apps/publicapi/btp_event_receivers.py``) — jamais un import direct
# ``btp_chantier`` → ``publicapi`` : l'app émet sur le bus, sans savoir qui
# écoute (même patron que ``scm_rupture_imminente_detectee`` ci-dessus).

# Émis EXACTEMENT quand une ``ReserveChantier`` passe à ``levee``
# (``services.lever_reserve``, APRÈS la capture de la signature et la
# transition). Arguments : ``reserve``, ``company``, ``user`` (le leveur,
# peut être ``None``).
btp_reserve_levee = django.dispatch.Signal()

# Émis EXACTEMENT quand un ``RFI`` reçoit sa réponse et passe à ``repondu``
# (``services.repondre_rfi``). Arguments : ``rfi``, ``company``, ``reponse``
# (la ``RFIReponse`` créée), ``user`` (l'auteur, peut être ``None``).
btp_rfi_repondu = django.dispatch.Signal()

# Émis EXACTEMENT quand un ``VisaDocument`` est APPROUVÉ (sans réserve ou
# avec observations — jamais sur un refus : l'événement s'appelle
# ``visa.approuve``). Arguments : ``visa``, ``company``, ``user`` (le
# revuseur, peut être ``None``).
btp_visa_approuve = django.dispatch.Signal()

# Émis EXACTEMENT quand un ``DecompteGeneral`` devient ``definitif``
# (``services.finaliser_dgd``) — le verrouillage du décompte, le moment que
# la MOE et la comptabilité du client attendent. Arguments : ``dgd``,
# ``company``, ``user`` (peut être ``None``).
btp_dgd_finalise = django.dispatch.Signal()

__all__ = [
    'employe_sorti',
    'conge_approuve',
    'contrat_signe',
    'contrat_actif',
    'contrat_resilie',
    'effet_rejete',
    'abonnement_monitoring_resilie',
    'projet_status_change',
    'incident_declared',
    'budget_cycle_clos',
    'cycle_sterilisation_non_conforme',
    'ao_depose',
    'ao_gagne',
    'lead_maturite_changee',
    'dossier_export_cloture',
    'scm_rupture_imminente_detectee',
    'scm_cycle_sop_cloture',
    'dossier_juridique_clos',
    'btp_reserve_levee',
    'btp_rfi_repondu',
    'btp_visa_approuve',
    'btp_dgd_finalise',
]
