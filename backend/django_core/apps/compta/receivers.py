"""Point d'intégration de l'auto-génération des écritures (FG109).

L'auto-génération est OFF par défaut (``services.auto_ecritures_actif`` →
réglage ``COMPTA_AUTO_ECRITURES``) : tant que le founder ne l'active pas, RIEN
n'est passé en écriture — aucun comportement existant n'est modifié.

FG109 autorise explicitement le câblage « via le bus d'événements OU un appel de
service ». Le bus d'événements métier (``core.events``, M6) existe désormais,
mais il n'émet à ce jour que ``devis_accepted`` — AUCUN événement documentaire
« facture émise / paiement encaissé / avoir émis » n'est encore émis par
``ventes`` (et en ajouter modifierait ``ventes``, hors périmètre additif ici).
L'auto-génération reste donc déclenchée par APPEL DE SERVICE EXPLICITE — les
fonctions ``services.ecriture_pour_facture`` / ``ecriture_pour_paiement`` /
``ecriture_pour_avoir``, idempotentes et gardées par le toggle ``COMPTA_AUTO_
ECRITURES`` (OFF par défaut). Le jour où ``ventes`` émettra ces événements
documentaires sur ``core.events``, il suffira de les abonner ICI (à la manière
d'``apps/crm/receivers.py``, câblé dans ``ComptaConfig.ready``) ; ce module est
le point d'ancrage prévu, et reste importable sans dépendance manquante en
attendant.
"""

from django.dispatch import receiver

from core.events import devis_accepted, devis_refused

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
