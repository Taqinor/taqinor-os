"""Récepteurs d'événements métier (M6) — app Installations.

Abonne ``installations`` à l'événement ``devis_accepted`` exposé par
``core.events`` pour, à l'acceptation d'un devis, créer AUTOMATIQUEMENT le
chantier correspondant — sans que ``ventes`` importe ``installations``. Câblé
au démarrage par ``InstallationsConfig.ready`` (même schéma que ``crm`` dans
``apps/crm/receivers.py``).

Le récepteur passe par la couche service (``services.create_installation_from_devis``)
qui est IDEMPOTENTE : si un chantier existe déjà pour ce devis, elle le renvoie
sans en créer un second. Ré-accepter un devis (ou ré-émettre l'événement) ne
duplique donc jamais le chantier. La création est company-scopée
(``devis.company``). Le signal est synchrone, comme les autres récepteurs.
"""
from django.dispatch import receiver

from core.events import (
    abonne_best_effort, bon_commande_cree, devis_acceptation_annulee,
    devis_accepted,
    reception_fournisseur_annulee,
    reception_fournisseur_confirmee, facture_fournisseur_creee,
)

from .models import Installation
from .services import (
    annuler_chantiers_desaccepte, create_installation_from_devis,
    extourner_gr_ir_reception,
    provisionner_gr_ir_reception, lettrer_gr_ir_facture,
    peupler_series_entrepot_reception,
    replafonner_reservation_recue_pour_chantier,
    reserver_stock_recu_pour_chantier, retourner_series_entrepot_reception,
)


@receiver(devis_accepted,
          dispatch_uid="installations_create_chantier_on_devis_accepted")
def _creer_chantier_on_devis_accepted(sender, devis, user, ancien_statut,
                                      **kwargs):
    """À l'acceptation d'un devis, crée son chantier UNE seule fois.

    Délègue à ``create_installation_from_devis`` qui garde l'anti-doublon
    (retourne le chantier existant le cas échéant) — donc ré-accepter ou
    ré-émettre l'événement ne crée jamais de second chantier. La société du
    chantier est celle du devis (jamais issue d'une entrée client).
    """
    company = getattr(devis, 'company', None)
    if company is None:
        return
    inst, _created = create_installation_from_devis(devis, user, company)
    _ouvrir_dossier_8221_ci(devis, inst, user)


@receiver(devis_acceptation_annulee,
          dispatch_uid="installations_annuler_chantier_on_acceptation_annulee")
def _annuler_chantier_on_acceptation_annulee(sender, devis, user, **kwargs):
    """Décision fondateur (08/10/2026) — l'acceptation du devis est annulée
    (lead sorti de « Signé ») : le chantier qu'elle avait créé est annulé
    (drapeau + motif-marqueur, jamais supprimé), ses réservations libérées.
    Synchrone et SANS filet : on est dans la transaction de dés-acceptation,
    une erreur l'annule en bloc. Le dossier 82-21 encore « en constitution »
    reste en place : la ré-acceptation le réutilise (idempotent)."""
    company = getattr(devis, 'company', None)
    if company is None:
        return
    annuler_chantiers_desaccepte(devis, user, company)


def _ouvrir_dossier_8221_ci(devis, inst, user):
    """CIQ618 — un chantier C&I (``industriel``) ouvre SEUL son dossier 82-21
    (D-CIQ-18) par la façade ``ventes.services.ouvrir_dossier_8221``
    (idempotente : un seul dossier par affaire, révisions comprises), puis le
    chantier reçoit le miroir de son état (CIQ617). Résidentiel et agricole :
    rien. Aucun délai promis au client."""
    if (inst is None or inst.type_installation
            != Installation.TypeInstallation.INDUSTRIEL):
        return
    from apps.ventes.selectors import dossier_8221_resume
    from apps.ventes.services import ouvrir_dossier_8221

    from .services import refleter_dossier_8221

    dossier, _ = ouvrir_dossier_8221(devis, inst.pk, inst.regime_8221,
                                     user=user)
    if dossier is not None:
        refleter_dossier_8221(
            inst.pk, dossier_8221_resume(inst.company, dossier.devis_id),
            company=inst.company)


@receiver(reception_fournisseur_confirmee,
          dispatch_uid="installations_provisionner_gr_ir_on_reception")
@abonne_best_effort
def _provisionner_gr_ir_on_reception(sender, reception, company, user,
                                     **kwargs):
    """YPROC3 — à la confirmation d'une réception fournisseur, provisionne la
    dette latente GR/IR (idempotent, no-op sans BCF lié)."""
    provisionner_gr_ir_reception(
        reception=reception, company=company, user=user)


@receiver(reception_fournisseur_confirmee,
          dispatch_uid="installations_peupler_series_entrepot_on_reception")
@abonne_best_effort
def _peupler_series_entrepot_on_reception(sender, reception, company, user,
                                          **kwargs):
    """YSTCK7 — à la confirmation d'une réception fournisseur, peuple le
    registre entrepôt (SerieEntrepot) depuis les séries capturées à la ligne
    (idempotent, best-effort)."""
    peupler_series_entrepot_reception(
        reception=reception, company=company, user=user)


@receiver(reception_fournisseur_confirmee,
          dispatch_uid="installations_reserver_stock_chantier_on_reception")
@abonne_best_effort
def _reserver_stock_chantier_on_reception(sender, reception, company, user,
                                          **kwargs):
    """YPROC10 — à la confirmation d'une réception fournisseur dont le BCF
    porte un `chantier_origine`, réserve les quantités reçues pour ce
    chantier (idempotent, plafonné au manque recalculé, no-op sans lien)."""
    reserver_stock_recu_pour_chantier(reception=reception)


@receiver(reception_fournisseur_annulee,
          dispatch_uid="installations_extourner_gr_ir_on_reception_annulee")
@abonne_best_effort
def _extourner_gr_ir_on_reception_annulee(sender, reception, company,
                                          user=None, **kwargs):
    """ASTK57 — jumeau d'annulation de YPROC3 : extourne la provision GR/IR
    ouverte de la réception annulée (idempotent)."""
    extourner_gr_ir_reception(reception=reception, company=company)


@receiver(reception_fournisseur_annulee,
          dispatch_uid="installations_retourner_series_on_reception_annulee")
@abonne_best_effort
def _retourner_series_on_reception_annulee(sender, reception, company,
                                           user=None, **kwargs):
    """ASTK57 — jumeau d'annulation de YSTCK7 : les séries « en stock » de
    la réception annulée passent « retourné » (idempotent)."""
    retourner_series_entrepot_reception(
        reception=reception, company=company)


@receiver(reception_fournisseur_annulee,
          dispatch_uid="installations_replafonner_resa_on_reception_annulee")
@abonne_best_effort
def _replafonner_reservation_on_reception_annulee(sender, reception, company,
                                                  user=None, **kwargs):
    """ASTK57 — jumeau d'annulation de YPROC10 : la réservation du chantier
    d'origine ne dépasse plus le reçu net (idempotent)."""
    replafonner_reservation_recue_pour_chantier(
        reception=reception, company=company)


@receiver(bon_commande_cree,
          dispatch_uid="installations_rattacher_chantier_on_bon_commande_cree")
@abonne_best_effort
def _rattacher_chantier_on_bon_commande_cree(sender, instance, company,
                                             **kwargs):
    """CHT15 — à la création d'un bon de commande, rattache AUTOMATIQUEMENT
    le chantier né du même devis (``Installation.bon_commande`` existe déjà
    mais n'était jamais posé par ce chemin — la jointure devis↔BC↔chantier
    restait IMPLICITE, jamais matérialisée sur la ligne chantier).

    Idempotent (``bon_commande__isnull=True`` — un second envoi, ou un
    chantier déjà rattaché à la main, n'est jamais écrasé) et tenant-safe
    (``company`` posée côté serveur par l'émetteur, jamais du corps de
    requête). No-op si le BC n'a pas de devis (BC manuel hors échéancier).
    Best-effort : ne bloque jamais la création du BC."""
    devis_id = getattr(instance, 'devis_id', None)
    if devis_id is None:
        return
    Installation.objects.filter(
        devis_id=devis_id, company=company, bon_commande__isnull=True,
    ).update(bon_commande=instance)


@receiver(facture_fournisseur_creee,
          dispatch_uid="installations_lettrer_gr_ir_on_facture")
@abonne_best_effort
def _lettrer_gr_ir_on_facture(sender, instance, company, user=None, **kwargs):
    """YPROC3 — à la création d'une facture fournisseur, lettre les
    provisions GR/IR ouvertes du même bon de commande (idempotent).

    Contrat unifié du signal (core/events.py) : ``instance`` = la
    stock.FactureFournisseur, ``user`` optionnel (None pour une création
    système/hors-requête, ex. saisie manuelle via la vue)."""
    lettrer_gr_ir_facture(facture=instance, company=company, user=user)
