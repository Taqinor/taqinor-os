"""Signaux du bus de la chaîne facture → compta/chantier (propriétaire facturation).

SPL286 — extrait de ``core/events/__init__.py`` (move only). Ré-exporté
par ``from .facturation import *`` dans ``core/events/__init__.py`` :
les émetteurs et abonnés continuent d'importer ``core.events``.

Événements
----------

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
    de transition réels.

    AUD101 (03/09/2026) — CE PARAGRAPHE DISAIT FAUX. Il affirmait que
    ``creer_facture_tranche`` émettait ``facture_emise`` : le grep rendait
    ZÉRO sur ``utils/echeancier.py`` comme sur ``views/devis.py``, et quatre
    autres chemins (bulk ``action=emettre``, facturation de pénalités,
    ``creer_facture_classique`` consommée par POS/e-commerce/immobilier,
    consolidation multi-devis) posaient eux aussi ``EMISE`` en silence — donc
    sans jamais atteindre le grand livre, qui ne comptabilise que sur
    événement. Depuis AUD101 il n'existe QU'UN SEUL émetteur dans le domaine
    ventes : ``apps.ventes.domain.facturation_ops.emettre_facture`` (verrou de
    période, blocage crédit XFAC28, workflow de revue XFAC18, dérivation
    d'échéance XFAC23, pose du statut, puis ``facture_emise`` exactement une
    fois) ; tous les chemins ci-dessus l'appellent, et un test de parité
    échoue si un site de ``apps/ventes`` repose ``Facture.Statut.EMISE`` hors
    de lui. Restent émetteurs directs hors ventes : ``contrats.services`` et
    ``compta.services``.

    Les autres transitions sont inchangées : ``annuler`` pour
    ``facture_annulee`` ; ``convertir_en_bc`` pour ``bon_commande_cree`` ;
    ``facture_payee`` accompagne ``facture_paid`` — YDOCF4 — au même
    résiduel→0 (AUD102 : émis par le service unique
    ``apps.ventes.domain.encaissements.marquer_facture_soldee``). Préserve
    STRICTEMENT les statuts document (règle #4) : l'émission n'en change
    AUCUN. Arguments communs :

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

    AUD127 — ``avoir_annule`` est le symétrique manquant d'``avoir_cree`` :
    même contrat d'arguments, émis à l'annulation d'un avoir, et abonné par
    compta pour EXTOURNER l'écriture d'avoir (YLEDG4). Sans lui, l'ERP
    rendait la créance (``avoirs_total`` exclut les avoirs annulés) pendant
    que le grand livre gardait l'avoir.

``document_produit``
    Émis par une app métier/satellite quand elle produit un fichier destiné à
    être centralisé dans la GED (ZGED6 — pattern Odoo « File centralization »).
    L'émetteur n'importe jamais la GED ; la GED s'abonne dans son
    ``apps.py`` ``ready()`` (son ``receivers.py``) et route le
    fichier via ``ged.services.router_document_module`` si un
    ``RoutageDocumentaire`` existe pour la ``source`` — sinon no-op silencieux
    (comportement actuel inchangé). WIR165 — premier ÉMETTEUR RÉEL :
    ``apps/ventes/utils/pdf.py`` ``generate_facture_pdf`` (``source=
    'ventes_facture'``), best-effort, juste après le stockage du PDF de
    facture. Arguments du signal :

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


# Émis quand une transaction de paiement carte en ligne est capturée (FG370).
# Arguments : transaction (core.PaymentTransaction), company.
# Destiné à être abonné par l'app comptable pour matérialiser un ``Paiement``
# et rapprocher la facture — core n'importe jamais l'app comptable lui-même.
payment_captured = django.dispatch.Signal()

# Émis par une app émettrice quand elle produit un fichier à centraliser dans
# la GED (ZGED6). Arguments : source, company, file, filename, reference,
# contexte, uploaded_by. Abonné dans ce repo : ged (apps/ged/receivers.py),
# no-op silencieux si aucun RoutageDocumentaire pour la source — voir
# docstring du module ci-dessus.
document_produit = django.dispatch.Signal()

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

# AUD127 — SYMÉTRIQUE d'``avoir_cree`` : l'annulation d'un avoir n'émettait
# RIEN, alors que sa création émet ``avoir_cree`` auquel compta abonne
# l'écriture d'avoir (YLEDG1). L'effet ERP était pourtant immédiat :
# ``Facture.avoirs_total`` exclut les avoirs annulés, donc ``montant_du``
# remonte — pendant que le grand livre, lui, garde l'avoir. Une créance de
# 20 000 réapparaissait côté ERP alors que la comptabilité la considérait
# toujours comme créditée. Émis SYNCHRONE, best-effort, au seul point
# d'annulation (``ventes.views.avoir.AvoirViewSet.annuler``), exactement une
# fois (l'action est idempotente). Arguments : instance (ventes.Avoir),
# company. Abonné : compta (YLEDG4, extourne l'écriture d'avoir — jamais de
# suppression d'écriture validée, COMPTA11).
avoir_annule = django.dispatch.Signal()

__all__ = [
    'payment_captured',
    'document_produit',
    'facture_paid',
    'paiement_rejete',
    'facture_emise',
    'facture_payee',
    'facture_annulee',
    'bon_commande_cree',
    'paiement_enregistre',
    'avoir_cree',
    'avoir_annule',
]
