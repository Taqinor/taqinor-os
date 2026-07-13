"""Point d'intégration de l'auto-génération des écritures (FG109).

L'auto-génération est OFF par défaut (``services.auto_ecritures_actif`` →
réglage ``COMPTA_AUTO_ECRITURES``) : tant que le founder ne l'active pas, RIEN
n'est passé en écriture — aucun comportement existant n'est modifié.

YLEDG1 — ``ventes`` émet désormais ``facture_emise``/``paiement_enregistre``/
``avoir_cree`` sur ``core.events`` (M6) aux points de transition réels
(``FactureViewSet.emettre``/``enregistrer_paiement``/``creer_avoir``, l'import
de relevé bancaire, le webhook ``PaymentLink`` et le service partagé POS). Ce
module s'y abonne pour appeler le bloc ``services.ecriture_pour_facture`` /
``ecriture_pour_paiement`` / ``ecriture_pour_avoir`` — idempotentes et gardées
par le toggle ``COMPTA_AUTO_ECRITURES`` (OFF par défaut, comportement
inchangé). ``ventes`` n'importe jamais ``apps.compta`` : les instances
transitent par les arguments du signal.
"""

from django.dispatch import receiver

from core.events import (
    avoir_cree,
    chantier_receptionne,
    facture_annulee,
    facture_emise,
    facture_fournisseur_creee,
    facture_payee,
    paiement_enregistre,
    paiement_fournisseur_enregistre,
    paiement_rejete,
)

from .services import (  # noqa: F401  (ré-export du point d'intégration)
    _ecriture_existante,
    auto_ecritures_actif,
    auto_lettrer_facture_soldee,
    ecriture_pour_avoir,
    ecriture_pour_facture,
    ecriture_pour_facture_fournisseur,
    ecriture_pour_paiement,
    ecriture_pour_paiement_especes_via_caisse,
    ecriture_pour_paiement_fournisseur,
    # XPLT20 — miroir inter-sociétés (vente A → achat B), opt-in strict via
    # RegleInterSociete (désactivée par défaut) ; indépendant du toggle
    # COMPTA_AUTO_ECRITURES (n'écrit jamais l'écriture de vente elle-même).
    generer_facture_fournisseur_miroir_intersociete,
    # YLEDG10 — chèques clients reçus → portefeuille d'effets (3425), jamais
    # directement en banque (l'argent n'y est pas encore).
    enregistrer_effet_pour_paiement_cheque,
    # YSERV4 — envoi (gated Brevo) de l'enquête NPS créée à la réception.
    envoyer_enquete_nps,
    extourner_ecriture,
    # XACC1 — transfert TVA attente→définitif (régime encaissement). Même
    # point d'ancrage : appel de service explicite depuis ``ventes`` tant
    # qu'aucun événement dédié « paiement enregistré » n'existe sur le bus.
    transferer_tva_encaissement,
    # XACC6 — écriture de stock automatique (inventaire permanent, toggle OFF
    # par défaut). Même point d'ancrage : appel de service explicite depuis
    # ``stock`` tant qu'aucun événement dédié « mouvement de stock » n'existe
    # sur ``core.events`` (l'ajouter modifierait ``apps.stock``, hors
    # périmètre additif ici).
    poster_mouvement_stock,
)


# ── YLEDG1 — auto-génération des écritures de vente sur le bus d'événements ─

@receiver(facture_emise, dispatch_uid="compta_ecriture_pour_facture_emise")
def _ecriture_pour_facture_emise(sender, instance, company, **kwargs):
    ecriture_pour_facture(instance)


# ── XPLT20 — miroir inter-sociétés, indépendant de COMPTA_AUTO_ECRITURES ────

@receiver(facture_emise, dispatch_uid="compta_miroir_intersociete_facture_emise")
def _miroir_intersociete_pour_facture_emise(sender, instance, company, **kwargs):
    generer_facture_fournisseur_miroir_intersociete(instance, company)


@receiver(paiement_enregistre, dispatch_uid="compta_ecriture_pour_paiement")
def _ecriture_pour_paiement_enregistre(sender, instance, company, **kwargs):
    mode = getattr(instance, 'mode', '')
    # YLEDG10 — un règlement CHÈQUE ne va pas directement en banque (5141) :
    # l'argent n'y est pas encore. Router vers le portefeuille d'effets
    # (3425 « effets à recevoir ») ; l'encaissement réel se fera au bordereau
    # de remise existant (poster_bordereau, qui crédite 3425 → banque). Jamais
    # `ecriture_pour_paiement` sur ce mode (une seule matérialisation du
    # règlement — le portefeuille, pas l'écriture banque directe).
    if mode == 'cheque':
        enregistrer_effet_pour_paiement_cheque(instance)
    # YLEDG9 — un règlement ESPÈCES route par le module caisse (mouvement +
    # timbre fiscal) au lieu de l'écriture banque directe ; jamais les deux
    # (une seule écriture par paiement). Sans caisse configurée : fallback
    # inchangé sur ``ecriture_pour_paiement``.
    elif mode == 'especes':
        ecriture = ecriture_pour_paiement_especes_via_caisse(instance)
        if ecriture is None:
            ecriture_pour_paiement(instance)
    else:
        ecriture_pour_paiement(instance)
    # YLEDG6 — auto-lettrage à l'encaissement : uniquement quand la facture
    # est désormais intégralement réglée (résiduel→0, comme YDOCF4) ; un
    # règlement partiel laisse le lot ouvert (comportement inchangé). Un
    # règlement chèque encore en portefeuille (aucune écriture 3421 postée)
    # ne trouve rien à lettrer — no-op silencieux (attendu, YLEDG6).
    facture = getattr(instance, 'facture', None)
    if facture is not None and getattr(facture, 'montant_du', None) is not None \
            and facture.montant_du <= 0:
        auto_lettrer_facture_soldee(facture)


@receiver(avoir_cree, dispatch_uid="compta_ecriture_pour_avoir")
def _ecriture_pour_avoir_cree(sender, instance, company, **kwargs):
    ecriture_pour_avoir(instance)


# ── YLEDG2 — auto-génération des écritures d'achat sur le bus d'événements ──

@receiver(facture_fournisseur_creee,
          dispatch_uid="compta_ecriture_pour_facture_fournisseur")
def _ecriture_pour_facture_fournisseur_creee(sender, instance, company,
                                             **kwargs):
    ecriture_pour_facture_fournisseur(instance)


@receiver(paiement_fournisseur_enregistre,
          dispatch_uid="compta_ecriture_pour_paiement_fournisseur")
def _ecriture_pour_paiement_fournisseur_enregistre(sender, instance, company,
                                                   **kwargs):
    ecriture_pour_paiement_fournisseur(instance)


# ── YLEDG4 — extourne automatique quand un document comptabilisé est annulé ─
# Si une écriture source existe déjà pour ce document (source_type='facture'),
# on poste son extourne (jamais de suppression d'écriture validée, COMPTA11).
# Un document jamais comptabilisé (toggle OFF, ou facture jamais émise via
# facture_emise) n'a aucune écriture source → aucune extourne (no-op).

@receiver(facture_annulee, dispatch_uid="compta_extourne_facture_annulee")
def _extourne_facture_annulee(sender, instance, company, **kwargs):
    ecriture = _ecriture_existante(company, 'facture', instance.id)
    if ecriture is None:
        return
    extourner_ecriture(ecriture)


# ── YLEDG6 (suite) — un paiement rejeté délettre le lot lié automatiquement ─
# (le rejet lui-même — statut ventes.Paiement + extourne de l'écriture
# d'encaissement, YLEDG4/5 — est traité côté ventes ; ici on rouvre
# uniquement le lettrage posé par ``auto_lettrer_facture_soldee``.)

@receiver(paiement_rejete, dispatch_uid="compta_delettrer_paiement_rejete")
def _delettrer_paiement_rejete(sender, paiement, facture, montant, company,
                               **kwargs):
    from .models import LigneEcriture
    ecriture = _ecriture_existante(company, 'paiement', paiement.id)
    if ecriture is None:
        return
    ligne_lettree = (LigneEcriture.objects
                     .filter(ecriture=ecriture, company=company)
                     .exclude(lettrage='').first())
    if ligne_lettree is None:
        return
    from . import selectors
    selectors.delettrer(company, ligne_lettree.lettrage)


# ── ARC36 — facture intégralement réglée → lettrage du solde (compta) ────────
# S'abonne à ``facture_payee`` (YEVNT6 — TOUT chemin qui solde la facture,
# y compris « marquer payée » manuel sans nouveau Paiement). Complète le
# lettrage YLEDG6 déjà déclenché sur ``paiement_enregistre`` : ce chemin-ci
# couvre les soldes SANS événement de paiement. ``auto_lettrer_facture_
# soldee`` est idempotente (lignes déjà lettrées exclues, no-op silencieux)
# — une double invocation (paiement_enregistre PUIS facture_payee) ne pose
# jamais deux lettrages. Le signal frère ``facture_paid`` (YDOCF4) porte le
# même fait : DÉPRÉCIÉ pour l'abonnement (docstring du bus) — on n'écoute
# que ``facture_payee``. Additif : aucun statut document modifié (règle #4).

@receiver(facture_payee, dispatch_uid="compta_lettrage_facture_payee")
def _lettrer_facture_payee(sender, instance, company, **kwargs):
    auto_lettrer_facture_soldee(instance)


# ── YSERV4 — enquête NPS auto à la réception d'un chantier ──────────────────
# FG238 avait livré EnqueteNPS + envoyer_enquete_nps (gated Brevo) sans aucun
# déclencheur : ce récepteur ferme la boucle sur core.events.chantier_
# receptionne (émis par apps.installations aux deux sites de transition vers
# RECEPTIONNE). Idempotent par chantier (get_or_create sur chantier_id) : une
# ré-émission du signal (ex. ré-sauvegarde) ne crée jamais une deuxième
# enquête pour le même chantier. L'envoi réel reste gated Brevo (envoyer_
# enquete_nps est déjà un no-op sans clé) — comportement FG238 inchangé.

@receiver(chantier_receptionne, dispatch_uid="compta_enquete_nps_reception")
def _creer_enquete_nps_a_reception(sender, installation, user, ancien_statut,
                                   **kwargs):
    from .models import EnqueteNPS

    client_id = getattr(installation, 'client_id', None)
    if not client_id:
        return
    enquete, created = EnqueteNPS.objects.get_or_create(
        company=installation.company, chantier_id=installation.id,
        defaults={'client_id': client_id})
    if created:
        envoyer_enquete_nps(enquete)
