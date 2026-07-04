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
    facture_emise,
    paiement_enregistre,
)

from .services import (  # noqa: F401  (ré-export du point d'intégration)
    auto_ecritures_actif,
    ecriture_pour_avoir,
    ecriture_pour_facture,
    ecriture_pour_facture_fournisseur,
    ecriture_pour_paiement,
    ecriture_pour_paiement_fournisseur,
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


@receiver(avoir_cree, dispatch_uid="compta_ecriture_pour_avoir")
def _ecriture_pour_avoir_cree(sender, instance, company, **kwargs):
    ecriture_pour_avoir(instance)


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
