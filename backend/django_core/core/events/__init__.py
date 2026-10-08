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

``reception_fournisseur_annulee``
    ASTK55 (C-ASTK-011) — jumeau d'ANNULATION de
    ``reception_fournisseur_confirmee`` : émis après commit à la fin de
    ``stock.services.annuler_reception_confirmee`` (ASTK56). Arguments :

    * ``reception`` — l'instance ``stock.ReceptionFournisseur`` annulée ;
    * ``company`` — la société (posée côté serveur) ;
    * ``user`` — l'utilisateur qui annule (peut être ``None``) ;
    * ``lignes`` — liste de dicts ``{ligne, produit, quantite_annulee}``.

    Abonné attendu : ``installations`` (ASTK57) — extourne la provision GR/IR,
    repasse les ``SerieEntrepot`` en « retourné » et re-plafonne la
    réservation YPROC10 du chantier. ``stock`` n'importe pas ``installations``.

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
    inchangé). ``installations`` n'importe jamais la comptabilité — même
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

``module_toggled``
    ODY25 — Émis à CHAQUE bascule RÉELLE d'un ``core.ModuleToggle`` (une app
    installée ou désinstallée pour une société), aux DEUX seuls sites qui
    écrivent cet état : ``core.feature_flags.activer_module`` et
    ``core.feature_flags.desactiver_module``. Émis UNIQUEMENT sur un
    FRANCHISSEMENT — ré-activer une app déjà active, ou désactiver une app déjà
    désactivée, n'émet RIEN (le journal de la boutique ne doit pas se remplir de
    lignes « rien n'a changé »). Une bascule en CASCADE émet un événement PAR
    module réellement basculé : le journal montre l'effet complet, pas seulement
    le module cliqué. Arguments du signal :

    * ``toggle`` — l'instance ``core.ModuleToggle`` après écriture ;
    * ``company`` — la société (posée côté serveur, jamais du corps) ;
    * ``module`` — la clé de module (chaîne LIBRE : ``core`` ne connaît aucun
      module métier, contrat import-linter) ;
    * ``actif`` — le NOUVEL état (``True`` = installée) ;
    * ``user`` — l'utilisateur qui bascule (peut être ``None`` : bascule
      système, commande de gestion, provisioning) ;
    * ``raison`` — le motif éventuel porté par le toggle.

    Abonné dans ce repo : ``records`` (``apps/records/receivers.py``, câblé
    dans son ``apps.py`` ``ready()``). Il historise la bascule dans le CHATTER
    GÉNÉRIQUE ``records.Activity`` (ARC8) plutôt que dans un 14ᵉ modèle de
    journal maison — c'est exactement la convergence qu'ARC8 existe pour
    obtenir. La cible du chatter est le ``ModuleToggle`` lui-même : la société
    du journal est donc CELLE du toggle, et l'isolation multi-tenant est
    STRUCTURELLE (pas un filtre qu'on peut oublier).

    L'abonné n'est PAS dans ``core`` (patron émetteur=abonné de
    ``contrat_signe``/``incident_declared``) pour une raison de contrat :
    ``records.services`` — seul point d'écriture autorisé du chatter — importe
    les ``selectors`` de crm/ventes/stock (VX210(c)), donc un
    ``core → records.services`` créerait la chaîne ``core → apps.crm``
    interdite par ``core-foundation-is-a-base-layer``. ``core`` ne lit du
    journal que ``records.models`` (module sans dépendance métier), via
    ``core.feature_flags.journal_modules``.
"""
import django.dispatch
from .parked import *  # noqa: F401,F403
from .facturation import *  # noqa: F401,F403
from .devis import *  # noqa: F401,F403

# ADSDEEP17 — Émis quand un lead Meta Lead Ads est capturé par le webhook CRM
# EXISTANT (``apps/crm/webhooks.meta_lead_ads_webhook``, après
# ``create_lead_from_meta_lead_ads``). Permet à ``adsengine`` de matérialiser un
# ``MetaLeadMirror`` (leads PAR AD) sans que ``crm`` importe ``apps.adsengine``.
# Arguments : lead (crm.Lead), company, leadgen_id, ad_id, adset_id,
# campaign_id, form_id, created_time (str|None), is_organic (bool). Abonné dans
# ce repo : adsengine (apps/adsengine/receivers.py).
meta_lead_captured = django.dispatch.Signal()

# PUB100 — Émis quand un lead CRM est EFFACÉ (droit à l'oubli CNDP). Permet aux
# miroirs qui portent une référence STRING au lead (adsengine :
# ``MetaLeadMirror``/``CtwaReferral`` via ``crm_lead_id`` + ``phone_key``) de
# propager l'effacement (anonymisation best-effort) sans que ``crm`` importe
# ``apps.adsengine``. Arguments : company, crm_lead_id (int), phone_key (str,
# optionnel). Abonné dans ce repo : adsengine (apps/adsengine/receivers.py).
lead_erased = django.dispatch.Signal()

# NTGRC9 — Émis à la CRÉATION d'un lead CRM, quelle que soit la porte d'entrée
# (saisie, webhook site, import). Arguments : lead (crm.Lead), company.
# Émetteur dans ce repo : crm (apps/crm/receivers.py, post_save created=True).
# Abonné vivant (ALEA3 — docstring corrigée) : calepinage
# (apps/calepinage/receivers.py, reprise du tracé public CAL110) — `crm`
# n'importe jamais `apps.calepinage`. L'abonné historique `grc` (alerte DPO,
# NTGRC9) vit dans un module PARQUÉ (backend/parked/grc) : il ne reçoit rien.
lead_created = django.dispatch.Signal()

# ACAL189 (C-ACAL-006, D06-T17) — Émis quand le tracé de toit d'un lead public
# ARRIVE APRÈS sa création : le webhook du site (``apps/crm/webhooks.py``,
# branche « renvoi < 60 s ») complète un lead qui n'avait AUCUN contour
# exploitable et en reçoit un (≥ 3 sommets). ``lead_created`` a déjà été émis
# sans tracé : sans ce second signal, le calepinage pré-tracé n'était jamais
# ouvert. Jamais émis pour un lead qui avait déjà un contour (aucun doublon).
# Arguments : lead (crm.Lead), company. Abonné dans ce repo : calepinage
# (apps/calepinage/receivers.py → reprendre_trace_public, idempotent par la
# porte unique ACAL182) — ``crm`` n'importe jamais ``apps.calepinage``.
lead_trace_toit_recu = django.dispatch.Signal()


# VTA5 — Émis quand une visite technique terrain reçoit le FEU VERT du bureau
# d'études (``apps.visites.services.valider_visite``). Arguments : visite
# (visites.VisiteTerrain), lead_id (ENTIER, jamais l'instance — référence
# cross-app string), user (l'utilisateur AGISSANT, jamais déduit), recap
# (phrase FR courte PRÉ-CALCULÉE par ``visites.selectors.recap_visite_terrain``
# — le récepteur n'a rien à recalculer, et la règle « zéro chiffre inventé »
# reste tenue d'un seul côté).
# Ce n'est PAS un changement d'étape du funnel : ``STAGES.py`` n'est pas touché
# (le statut de visite est un layer DOCUMENT interne). Abonné dans ce repo :
# ``crm`` (``apps/crm/receivers.py``) — il pose ``Lead.visite_effectuee`` +
# le récap dans ``Lead.visite_notes`` et une note au chatter. C'est ce qui
# supprime le DERNIER écrit direct de ``visites`` vers ``crm.Lead`` : l'app
# visites ne connaît plus le lead que par un entier.
visite_validee = django.dispatch.Signal()

# VISITE-CADENCE (fondateur 15/09/2026) — LA VISITE TECHNIQUE EST UNE ÉTAPE DU
# SUIVI COMMERCIAL, PAS UN ÉVÉNEMENT ISOLÉ.
#
# Doctrine : la visite se place APRÈS l'envoi du devis, comme outil de closing
# pendant que le client est chaud. Le SUIVI doit donc RÉAGIR à la visite —
# suspendre les touches génériques quand un rendez-vous est pris, pousser le
# responsable à rappeler dans les 24-48 h une fois le technicien reparti.
# ``apps.visites`` ne sait RIEN de tout cela : elle ÉMET, ``apps.crm`` décide
# (même montage que ``visite_validee`` ci-dessus, frontière M3/M6 intacte).
#
# AUCUN de ces deux événements ne touche ``STAGES.py`` : le statut d'une visite
# reste un layer DOCUMENT interne, jamais une étape de funnel.

# Émis quand la DATE PRÉVUE d'une visite technique est posée ou CHANGÉE
# (création avec date, mise à jour, ou ``visites.services.planifier_visite``).
# Arguments : visite (visites.VisiteTerrain), lead_id (ENTIER — référence
# cross-app string), user (l'utilisateur AGISSANT), date_prevue (``date``),
# commercial_nom (texte déjà composé côté émetteur — le CRM n'a aucun
# utilisateur à aller relire).
# Abonné dans ce repo : ``crm`` — il synchronise ``Lead.visite_prevue_le``,
# pose la note de chatter, suspend la cadence après-devis en cours et programme
# les deux gestes du rendez-vous (confirmation la veille, débrief le lendemain).
visite_planifiee = django.dispatch.Signal()

# Émis à la fin de l'action ``terminer`` d'une visite technique (le technicien
# a fini sur place). Arguments : visite, lead_id (ENTIER), user, retour —
# ``{'notes': str, 'commentaires_photos': [{'slot': str, 'commentaire': str}],
# 'nb_photos': int}``, PRÉ-COMPOSÉ par ``visites.selectors.retour_visite`` :
# c'est le TEXTE LIBRE du terrain, celui que ``visite_validee`` ne transporte
# justement pas (son récap ne porte que des mesures). Sans lui, les remarques
# du technicien mouraient dans l'app terrain.
# …et ``qualification`` : la LECTURE COMMERCIALE du terrain, à vocabulaire
# FERMÉ (``apps.visites.qualification``) — température, sort du devis,
# décideur, frein, déclencheur, moment du rappel, conseil de closing. ``None``
# tant que rien n'a été saisi (jamais un dict de défauts, qui ferait croire à
# une qualification faite). Elle voyage À CÔTÉ du retour parce qu'elle n'est
# pas du texte : le CRM la rend en une phrase et cale le débrief dessus.
# Abonné dans ce repo : ``crm`` — note de chatter portant la qualification puis
# les commentaires, ``Lead.visite_effectuee``, recalage du débrief et
# notification au RESPONSABLE du lead (« rappeler sous 24-48 h »).
visite_terminee = django.dispatch.Signal()


# Émis à la CONFIRMATION d'une réception fournisseur (XQHS3 / YPROC3).
# Arguments : reception (stock.ReceptionFournisseur), company, user.
# cf. docstring du module ci-dessus pour la carte des deux abonnés attendus.
reception_fournisseur_confirmee = django.dispatch.Signal()
# (Le signal ``facture_fournisseur_creee`` est défini plus bas, section
# YLEDG2 — contrat unifié ``instance, company, user`` pour ses DEUX abonnés :
# installations (lettrage GR/IR, YPROC3) et compta (écriture, YLEDG2).)

# ASTK55 — émis à l'ANNULATION d'une réception fournisseur confirmée (ASTK56).
# Arguments : reception, company, user, lignes ({ligne, produit,
# quantite_annulee}). Abonné attendu : installations (ASTK57).
reception_fournisseur_annulee = django.dispatch.Signal()


# Émis quand une Intervention (apps.installations) passe à TERMINEE ou VALIDEE
# (YSERV2). Arguments : intervention, company, user (peut être None). Abonné
# dans ce repo : sav (apps/sav/receivers.py) — si l'intervention porte un
# ticket lié, pose Ticket.date_resolution et avance le ticket vers RESOLU
# (idempotent, ne recule jamais un statut). installations n'importe jamais
# apps.sav — même patron que devis_accepted → crm.
intervention_completed = django.dispatch.Signal()


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

# WIR85 / XACC6 — un ``stock.MouvementStock`` vient d'être enregistré
# (``stock.services.record_stock_movement``, le seul point de création).
# Émis SYNCHRONEMENT et en best-effort après l'écriture du mouvement : il ne
# change jamais le mouvement lui-même ni un statut de document (règle #4).
#   Arguments : instance (stock.MouvementStock), company.
#   Abonné dans ce repo : compta (``poster_mouvement_stock``, écriture
#   d'inventaire permanent — doublement gardée par le toggle
#   ``COMPTA_AUTO_ECRITURES``/WIR24 ET par ``PlanComptable.inventaire_permanent``,
#   les deux OFF par défaut : sans opt-in explicite, RIEN n'est écrit).
# ``stock`` n'importe jamais la comptabilité — l'instance transite par le
# signal, exactement comme ``facture_fournisseur_creee``.
mouvement_stock_enregistre = django.dispatch.Signal()

# PVSYNC — une RÉFÉRENCE du catalogue vient de changer : ``stock`` a écrit un
# ``Produit`` sur un champ qui peut RENDRE FAUX un devis déjà rédigé (le NOM,
# qui est la désignation reprise ligne à ligne, et le PRIX DE VENTE, qui est le
# prix catalogue auquel une ligne non négociée a été posée).
#   Arguments : ``produit`` (l'instance APRÈS écriture), ``company`` (posée
#   côté serveur, jamais lue du corps), ``user`` (peut être None) et
#   ``champs`` — dict ``{champ: [ancienne_valeur, nouvelle_valeur]}`` en
#   CHAÎNES, l'ancienne valeur étant la seule façon de reconnaître plus tard
#   une ligne restée AU PRIX CATALOGUE d'une ligne NÉGOCIÉE (une fois le
#   produit réécrit, la comparaison au prix courant ne prouve plus rien).
# Émis SYNCHRONE et best-effort par le SEUL point de mise à jour REST d'un
# produit (``stock.views.produit.ProduitViewSet.perform_update``) — JAMAIS un
# ``post_save`` de modèle : un signal de modèle se déclencherait aussi sur les
# écritures internes (mouvements de stock, recatégorisation du seeder,
# migrations de données) et ferait re-synchroniser des devis pour rien.
# Émis UNIQUEMENT sur un changement RÉEL (dict vide ⇒ aucune émission).
# Abonné dans ce repo : ``ventes`` (``apps/ventes/apps.py`` ``ready()`` →
# ``ventes.services.on_produit_modifie``), qui délègue à une tâche Celery la
# resynchronisation des devis BROUILLON/ENVOYÉ portant ce produit. ``stock``
# n'importe jamais ``apps.ventes`` — même patron que ``devis_accepted`` → crm.
produit_modifie = django.dispatch.Signal()

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


# NTCRM22 — commission due d'un ``DealEnregistre``. ALEA3 (D-ALEA-3) : n'est
# PLUS émis (aucun abonné ; la commission due se lit par
# ``deals-enregistres/a-payer/``). Déclaration conservée (golden SPL283),
# réservée dans ``core.event_coverage`` pour le retour du module compta.
# Arguments historiques : company, deal_id, apporteur_id, montant (Decimal).
deal_commission_due = django.dispatch.Signal()


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

# NTUX7 — Émis par TOUTE app qui soft-supprime (archive/annule) un
# enregistrement, pour alimenter la corbeille transverse 30 jours SANS créer un
# modèle « éléments supprimés » par app. Abonné dans ce repo : ``trash``
# (``apps/trash/receivers.py`` → ``ElementSupprime``). L'émetteur ne connaît pas
# la corbeille, et ``apps.trash`` n'importe aucune app métier (la cible est
# pointée par ``contenttypes``). Arguments : ``instance`` (l'objet
# soft-supprimé), ``company``, ``user`` (peut être None), ``type_libelle``
# (libellé de type lisible, ex. « Devis » — à défaut le nom du ContentType),
# ``libelle`` (snapshot d'affichage — à défaut ``str(instance)``), ``donnees``
# (dict best-effort, AFFICHAGE SEUL, jamais réinjecté à la restauration).
record_soft_deleted = django.dispatch.Signal()

# ODY25 — une app est INSTALLÉE ou DÉSINSTALLÉE pour une société (bascule réelle
# d'un ``core.ModuleToggle``, franchissement uniquement). Arguments : toggle,
# company, module, actif, user (peut être None), raison. Abonné dans ce repo :
# ``records`` (``apps/records/receivers.py`` → chatter générique ARC8 sur le
# toggle) — voir la docstring du module ci-dessus.
module_toggled = django.dispatch.Signal()

# AUD816 — une ÉDITION EN MASSE a été appliquée (``core.bulk_edit``). Ce
# chemin écrit par ``queryset.update()`` : il court-circuite ``Model.save()``,
# ``full_clean()`` et TOUS les signaux — donc l'audit générique par
# ``post_save`` (``apps.audit.signals.TRACKED_MODELS``) ne voit RIEN passer.
# Cet événement est le SEUL canal par lequel une opération de masse laisse une
# trace, et il permet à ``core`` (fondation) de la produire sans importer
# ``apps.audit`` (contrat import-linter ``core-foundation-is-a-base-layer``).
# Émis UNE fois par lot réellement appliqué (jamais si 0 ligne modifiée).
# Arguments : ``target`` (nom logique de la cible), ``label``, ``fields``
# (liste des champs écrits), ``count`` (nb de lignes modifiées), ``company``,
# ``user`` (peut être None). Abonné : ``apps/audit/receivers.py``.
bulk_edit_applied = django.dispatch.Signal()


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

    from core.models import OutboxEvent

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


# ``salle_vente_signal_interet``
#     Une salle de vente (``crm.SalleVente``) a reçu ≥3 consultations
#     (``crm.SalleVenteVue``) en moins de 48h alors que le lead lié est en
#     stage QUOTE_SENT — signal d'intérêt fort, purement informationnel
#     (JAMAIS un changement de stage automatique). Émis par
#     ``apps.crm.services.detecter_signal_interet_salle_vente`` (appelé en
#     best-effort depuis ``apps.crm.public_views.public_salle_vente`` à chaque
#     nouvelle vue), au plus UNE fois par jour local et par salle. La note de
#     chatter (``LeadActivity``) est écrite EN LIGNE par ce même service.
#     Abonné dans ce repo (ALEA3) : ``crm`` (``apps/crm/receivers.py``)
#     notifie le responsable du lead (``apps.notifications``).
#     Arguments : ``lead``, ``salle``, ``company``.
salle_vente_signal_interet = django.dispatch.Signal()


# NTWFL5 — Émis par ``core.workflow.avancer`` (moteur BPM FG366) exactement
# quand une ``WorkflowStepInstance`` devient la nouvelle étape ACTIVE
# (manuelle/par rôle, en attente de décision) — comble YEVNT8 pour FG366 :
# aujourd'hui aucune notification ne part à la création d'une étape
# d'approbation BPM (les 4 autres sources de l'agrégateur XKB1 sont déjà
# câblées, voir ``apps/notifications/signals.py``). Émission best-effort,
# jamais bloquante pour le moteur BPM. Arguments : ``step``
# (``core.WorkflowStepInstance``, la nouvelle étape courante), ``company``.
# Abonné dans ce repo : notifications (``apps/notifications/signals.py``,
# notifie les managers de la société — ``core`` n'a aucune notion
# d'assignation par utilisateur, seulement ``step_def.role_requis``).
workflow_etape_activee = django.dispatch.Signal()


# ── NTUX32 — Événements des objets UX (apps.uxviews / apps.trash) ───────────
# Émis par les apps NTUX (le SEUL point d'écriture de leur état), abonnés par
# ``apps.publicapi`` (webhook sortant, voir
# ``apps/publicapi/uxviews_event_receivers.py``) — jamais un import direct
# ``uxviews``/``trash`` → ``publicapi`` : l'app émet sur le bus, sans savoir
# qui écoute (même patron que ``btp_reserve_levee`` ci-dessus).

# Émis EXACTEMENT quand une ``SavedView`` (NTUX1) est CRÉÉE ou SUPPRIMÉE avec
# ``visibilite=EQUIPE`` (jamais sur une simple modification de filtres — ça,
# c'est NTUX39/notifications). Arguments : ``view`` (l'instance ``SavedView``
# — peut être un objet déjà supprimé de la base, ne lire que ses attributs
# scalaires), ``company``, ``user`` (peut être ``None``),
# ``action`` (``'partagee'`` ou ``'suppression'``).
saved_view_shared = django.dispatch.Signal()

# Émis EXACTEMENT quand ``apps.trash.services.restaurer`` restaure avec succès
# la cible d'une entrée de corbeille (NTUX7) — jamais sur une restauration
# refusée/déjà faite. Arguments : ``element`` (l'``ElementSupprime`` fermé),
# ``obj`` (l'objet métier restauré, peut être ``None`` si la cible avait
# disparu), ``company``, ``user`` (peut être ``None``).
record_restored = django.dispatch.Signal()

# NTWFL18 — Émis par le balayage journalier ``core.dossiers
# .notifier_echeances_depassees`` pour CHAQUE dossier transverse (NTWFL17)
# dont l'échéance est dépassée alors qu'il est encore ouvert. Dédupliqué à la
# source par ``Dossier.dernier_rappel_echeance_le`` : un dossier en retard
# n'émet qu'UNE fois par jour, quel que soit le nombre de passages du job
# (même discipline anti-double-notification que NTWFL5 sur les étapes BPM).
# ``core`` ne connaît aucun canal : il émet, et ``apps.notifications``
# notifie le propriétaire. Émission best-effort, jamais bloquante pour le
# balayage des dossiers suivants. Arguments : ``dossier`` (l'instance
# ``core.Dossier``), ``company``, ``proprietaire`` (``CustomUser`` ou
# ``None`` si le dossier n'a pas de propriétaire désigné).
dossier_echeance_depassee = django.dispatch.Signal()

# ── NTP2P38 — Événements du domaine Procure-to-Pay ──────────────────────────
# Les deux gestes d'achat qu'un tiers attend d'être notifié. Émis par
# ``apps.installations.services`` (le SEUL point d'écriture d'état de la
# réquisition et de l'adjudication), consommables par ``apps.automation`` (une
# ``AutomationRule`` sur ces ``TriggerType``) pour envoyer une notification ou
# un webhook sortant configuré par le founder — AUCUN appel HTTP automatique
# par défaut : l'app émet sur le bus, sans savoir qui écoute (même patron que
# ``btp_reserve_levee`` plus haut).

# Émis EXACTEMENT quand une ``installations.DemandeAchat`` (FG310) atteint le
# statut ``approuvee``, que la décision vienne du guichet unique
# (``services.decider_demande_achat``, XKB1) ou de la DERNIÈRE étape d'un plan
# d'approbation à N paliers (``services.approuver_etape_achat``, NTP2P2) —
# jamais sur une étape intermédiaire, jamais sur un refus. Arguments :
# ``demande`` (l'instance déjà ``approuvee``), ``company``, ``user``
# (l'approbateur, peut être ``None``), ``montant_estime`` (``Decimal``).
demande_achat_approuvee = django.dispatch.Signal()

# Émis EXACTEMENT quand une ``installations.RFQ`` (FG311) est ADJUGÉE : une
# offre à fournisseur catalogue est retenue ET le bon de commande fournisseur
# du gagnant vient d'être créé (``services.marquer_rfq_attribuee``). Retenir
# une offre à fournisseur nom-libre ne fait que basculer la sélection : ce
# n'est pas une attribution, et rien n'est émis. Arguments : ``rfq``
# (l'instance clôturée), ``offre`` (la ``RFQOffre`` retenue), ``company``,
# ``user`` (peut être ``None``), ``bon_commande_id`` (le BCF créé).
rfq_attribuee = django.dispatch.Signal()

# NTP2P38 — ADAPTATION DE PÉRIMÈTRE, pour le 3ᵉ événement prévu au plan
# (``facture_fournisseur_exception_3voies``) : le rapprochement 3 voies est
# FG131 et vit intégralement dans les services de la comptabilité
# (``evaluer_rapprochement`` est le seul endroit où un écart reçu↔facturé est
# calculé et où le statut « en écart » est posé), app qui n'appartient pas à
# la lane de ce commit. Aucun signal n'est déclaré ici tant que son émetteur
# ne l'est pas : un signal jamais émis serait un seam creux, pas un contrat
# (même arbitrage que pour ``scm.score_fournisseur_degrade`` plus haut). La
# tâche qui touchera ``apps/compta`` l'ajoutera ici, sans rien casser.

# ── NTI18N43 — Bascule de langue (société ou client) ────────────────────────
# Une intégration tierce synchronisée (un CRM externe, un outil d'e-mailing)
# doit savoir qu'un client est passé au français ou à l'arabe : sinon elle
# continue d'écrire dans l'ancienne langue, et c'est le client qui le
# découvre. Émis quand la langue de DOCUMENT d'un client change, ou quand la
# langue par DÉFAUT de la société change ; consommé par ``apps.publicapi``
# (webhook sortant ``langue_changed``, voir
# ``apps/publicapi/i18n_event_receivers.py``) — jamais un import direct de
# ``publicapi`` depuis l'app qui écrit la langue (même patron que
# ``btp_reserve_levee`` plus haut).
#
# Arguments : ``company``, ``portee`` (``'client'`` ou ``'societe'``),
# ``client_id`` (``int`` ou ``None`` pour une bascule société),
# ``ancienne_langue``, ``nouvelle_langue`` (codes courts, ex. ``'fr'`` /
# ``'ar'``), ``user`` (peut être ``None``).
langue_changed = django.dispatch.Signal()

#: NTI18N43 — portées reconnues de la bascule de langue.
PORTEE_LANGUE_CLIENT = 'client'
PORTEE_LANGUE_SOCIETE = 'societe'


def emettre_langue_changed(company, *, ancienne_langue, nouvelle_langue,
                           portee=PORTEE_LANGUE_CLIENT, client_id=None,
                           user=None, sender=None):
    """Émet ``langue_changed`` — BEST-EFFORT, et seulement si ça a bougé.

    L'app qui ÉCRIT la langue appelle cette fonction en UNE ligne, plutôt que
    de re-coder la garde « la valeur a-t-elle réellement changé ? » et le
    try/except à chaque point d'écriture (le chemin le plus sûr pour qu'un des
    points l'oublie). Retourne ``True`` si un événement est parti.

    Une langue identique avant/après n'émet RIEN : un webhook ne doit pas
    partir parce qu'un formulaire a été ré-enregistré sans changement.
    """
    avant = (ancienne_langue or '').strip().lower()
    apres = (nouvelle_langue or '').strip().lower()
    if avant == apres:
        return False
    try:
        langue_changed.send(
            sender=sender or 'core.events',
            company=company,
            portee=portee,
            client_id=client_id,
            ancienne_langue=avant,
            nouvelle_langue=apres,
            user=user)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        import logging
        logging.getLogger(__name__).warning(
            'NTI18N43 : émission langue_changed échouée (%s %s → %s)',
            portee, avant, apres, exc_info=True)
    return True


# ── NTOBS26 — Incidents publics (page d'état) sur le bus ────────────────────
# Une intégration tierce (webhook sortant, page de statut miroir) doit savoir
# qu'un incident vient de s'ouvrir/se résoudre — système (``company=None``,
# visible de tous les tenants) ou spécifique à une société. Émis par
# le ``receivers.py`` de la page d'état (le SEUL point d'écriture du statut
# d'un incident public), consommé par ``apps.publicapi`` (webhook sortant),
# jamais un import direct ``statuspage`` -> ``publicapi``. Arguments :
# ``incident`` (l'instance ``IncidentPublic``), ``company`` (peut être
# ``None`` : incident système).
incident_opened = django.dispatch.Signal()
incident_resolved = django.dispatch.Signal()

# NTOBS26 — Émis par
# ``core.maintenance_windows.MaintenanceWindowListCreateView.perform_create``
# à la CRÉATION d'une fenêtre de maintenance : ANNONCE immédiate côté webhook
# sortant — distinct du rappel in-app 24h/1h avant l'échéance, qui reste porté
# par ``core.notify_registry`` (``_notifier_fenetre``, inchangé). Arguments :
# ``fenetre`` (l'instance ``MaintenanceWindow``), ``company`` (peut être
# ``None`` : annonce système large), ``user`` (peut être ``None``).
maintenance_window_announced = django.dispatch.Signal()

# ── NTOBS30-reste — Actions Fiabilité auditées (apps.audit) ────────────────
# Sur les 5 actions Fiabilité listées par le plan NTOBS30 (création
# MaintenanceWindow, lancement export de réversibilité, publication
# post-mortem, émission crédit SLA, édition SlaCreditPolicy), les 4 qui
# vivent dans ``core`` (``core`` NE PEUT JAMAIS importer ``apps.audit`` —
# contrat import-linter ``core-foundation-is-a-base-layer``) émettent ici ;
# ``apps.audit.receivers`` s'y abonne (M4, même patron que
# ``document_pdf_generated``/``bulk_edit_applied`` plus haut). La publication
# de post-mortem (5ᵉ action) vit dans la page d'état — pas ``core`` —
# et appelle déjà ``apps.audit.recorder`` directement (satellite → satellite,
# aucune contrainte import-linter).
#
# LIMITE ASSUMÉE (héritée de la lane NTOBS30 d'origine, voir la docstring de
# ``apps/statuspage/tests/test_ntobs30_postmortem_audit_log.py``) : la 5ᵉ
# action « édition SlaCreditPolicy » n'a AUCUNE vue d'écriture dans ce dépôt
# (``SlaCreditPolicy`` — ``core/sla.py`` — n'est exposée par aucun viewset ni
# admin ; seule écriture existante = ORM direct / seed). Aucun signal
# ``sla_credit_policy_edited`` n'est déclaré ici tant que son émetteur ne
# l'est pas : un signal jamais émis serait un seam creux, pas un contrat
# (même arbitrage que ``facture_fournisseur_exception_3voies`` plus haut).

# Émis par ``core.maintenance_windows.MaintenanceWindowListCreateView.
# perform_create`` à la CRÉATION d'une fenêtre de maintenance (même site que
# ``maintenance_window_announced`` ci-dessus — DEUX signaux distincts pour
# DEUX abonnés distincts : publicapi webhook vs audit trail interne).
# Arguments : ``fenetre`` (l'instance ``MaintenanceWindow``), ``company``
# (peut être ``None``), ``user``.
maintenance_window_created = django.dispatch.Signal()

# Émis par ``core.export_registry.declencher_export_reversibilite`` au
# DÉCLENCHEMENT d'un export de réversibilité (avant même que la tâche Celery
# ne le construise — l'action auditée est la DEMANDE, pas son aboutissement).
# Arguments : ``run`` (l'``ExportReversibiliteRun`` fraîchement créé,
# ``statut='en_cours'``), ``company``, ``user`` (le demandeur).
export_reversibilite_declenche = django.dispatch.Signal()

# Émis par ``core.sla.sla_credit_statut`` quand un humain trace la décision
# ``emis``/``refuse`` sur un crédit SLA (``SlaSnapshot.credit_statut``).
# N'ÉMET jamais l'avoir lui-même (cf. docstring de la vue) — seulement le
# FAIT qu'un humain a décidé. Arguments : ``snapshot`` (le ``SlaSnapshot``),
# ``company``, ``ancien_statut``, ``nouveau_statut``, ``user``.
sla_credit_statut_change = django.dispatch.Signal()

# CALX368 — Émis par ``apps.calepinage.services.simulation.simuler_calepinage``
# (le SEUL chemin qui lance une simulation, D-CALX 4) quand une simulation a
# RÉELLEMENT abouti et que son résultat vient d'être fusionné dans
# ``Calepinage.resultat`` — jamais pour un « déjà calculé » (empreinte
# inchangée), jamais pour une simulation refusée, jamais pour un calcul à
# blanc (``enregistrer=False``). Ce n'est PAS un changement de statut (règle
# #4) : le calepinage reste où il est.
# Arguments : ``calepinage`` (l'instance, résultat déjà fusionné) et
# ``company_id`` (ENTIER — la société du calepinage, lue sans requête).
# Abonné dans ce repo : ``apps.publicapi`` (``calepinage_event_receivers``,
# webhook sortant ``calepinage.simule``) — ainsi ``apps.calepinage`` ne
# connaît pas l'API publique, et ``apps.publicapi`` n'importe jamais
# ``apps.calepinage``.
calepinage_simule = django.dispatch.Signal()
