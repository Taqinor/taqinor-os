"""Signaux du bus stock / achats (propriétaire stock).

SPL288 — extrait de ``core/events/__init__.py`` (move only). Ré-exporté
par ``from .stock import *`` dans ``core/events/__init__.py`` :
les émetteurs et abonnés continuent d'importer ``core.events``.

Événements
----------

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
"""
import django.dispatch


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

__all__ = [
    'reception_fournisseur_confirmee',
    'reception_fournisseur_annulee',
    'facture_fournisseur_creee',
    'paiement_fournisseur_enregistre',
    'mouvement_stock_enregistre',
    'produit_modifie',
    'demande_achat_approuvee',
    'rfq_attribuee',
]
