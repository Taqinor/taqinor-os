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

    Aucun abonné obligatoire dans ce lot (pose du seam) — destiné à
    découpler la facturation récurrente (CONTRAT31/FG40), une notification
    client, un dépôt GED (CONTRAT-*), ou une vérification d'entitlement SAV.

``contrat_actif``
    Émis EXACTEMENT une fois quand un ``contrats.Contrat`` bascule vers
    ``actif`` (activation automatique à la signature si la prise d'effet est
    atteinte, CONTRAT17, ou toute future activation manuelle qui passe par
    ``contrats.services.activer_si_eligible``) — YDOCF5. Mêmes arguments que
    ``contrat_signe`` (``contrat``, ``user``, ``company``). ``Contrat.statut``
    n'est jamais modifié par ce module lui-même (préservation des statuts,
    CONTRAT12) : le bus ne fait qu'observer la bascule déjà actée par la
    machine d'états gardée.

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
    n'émet rien) ; jamais posé deux fois pour le même règlement. Contrat :
    émetteur ``ventes``, abonnés futurs ``compta`` (XACC1 transfert TVA à
    l'encaissement) / ``notifications``. Arguments du signal :

    * ``facture`` — l'instance ``ventes.Facture`` désormais soldée ;
    * ``montant`` — montant du DERNIER paiement qui a soldé la facture ;
    * ``company`` — la société (posée côté serveur).

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
    l'émission n'en change AUCUN. Aucun abonné obligatoire dans ce lot (pose
    du seam pour ``compta``/``notifications``/audit/KPI). Arguments communs :

    * ``instance`` — l'objet ``Facture`` ou ``BonCommande`` concerné ;
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
"""
import django.dispatch

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
# Arguments : contrat, user, company. Aucun abonné obligatoire dans ce lot
# (pose du seam) — voir docstring du module ci-dessus.
contrat_signe = django.dispatch.Signal()

# Émis à la bascule d'un contrat vers « actif » (CONTRAT17) — YDOCF5.
# Arguments : contrat, user, company. Aucun abonné obligatoire dans ce lot
# (pose du seam) — voir docstring du module ci-dessus.
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
