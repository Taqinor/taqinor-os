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
    devis_accepted,
    devis_refused,
    facture_annulee,
    facture_emise,
    facture_fournisseur_creee,
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
    ecriture_pour_paiement_fournisseur,
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
    sortir_inscriptions_pour_lead,
)


# ── YLEDG1 — auto-génération des écritures de vente sur le bus d'événements ─

@receiver(facture_emise, dispatch_uid="compta_ecriture_pour_facture_emise")
def _ecriture_pour_facture_emise(sender, instance, company, **kwargs):
    ecriture_pour_facture(instance)


@receiver(paiement_enregistre, dispatch_uid="compta_ecriture_pour_paiement")
def _ecriture_pour_paiement_enregistre(sender, instance, company, **kwargs):
    ecriture_pour_paiement(instance)
    # YLEDG6 — auto-lettrage à l'encaissement : uniquement quand la facture
    # est désormais intégralement réglée (résiduel→0, comme YDOCF4) ; un
    # règlement partiel laisse le lot ouvert (comportement inchangé).
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


# ── XMKT1 — sortie automatique des séquences de relance ────────────────────
# À l'acceptation OU au refus d'un devis lié à un lead, sort ce lead de toute
# séquence de relance active (les séquences sont pilotées sur l'intention
# commerciale de conversion, plus pertinente une fois le devis tranché).

@receiver(devis_accepted, dispatch_uid="compta_sortir_sequence_on_devis_accepted")
def _sortir_sequence_on_devis_accepted(sender, devis, user, ancien_statut,
                                       **kwargs):
    lead_id = getattr(devis, 'lead_id', None)
    if not lead_id:
        return
    sortir_inscriptions_pour_lead(
        devis.company, lead_id, motif='devis_accepte')


@receiver(devis_refused, dispatch_uid="compta_sortir_sequence_on_devis_refused")
def _sortir_sequence_on_devis_refused(sender, devis, user, motif_refus,
                                      **kwargs):
    lead_id = getattr(devis, 'lead_id', None)
    if not lead_id:
        return
    sortir_inscriptions_pour_lead(
        devis.company, lead_id, motif='devis_refuse')
