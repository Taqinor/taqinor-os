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
    bon_commande_cree, devis_accepted, reception_fournisseur_confirmee,
    facture_fournisseur_creee,
)

from .models import Installation
from .services import (
    create_installation_from_devis, provisionner_gr_ir_reception,
    lettrer_gr_ir_facture, peupler_series_entrepot_reception,
    reserver_stock_recu_pour_chantier,
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
    create_installation_from_devis(devis, user, company)


@receiver(reception_fournisseur_confirmee,
          dispatch_uid="installations_provisionner_gr_ir_on_reception")
def _provisionner_gr_ir_on_reception(sender, reception, company, user,
                                     **kwargs):
    """YPROC3 — à la confirmation d'une réception fournisseur, provisionne la
    dette latente GR/IR (idempotent, no-op sans BCF lié)."""
    try:
        provisionner_gr_ir_reception(
            reception=reception, company=company, user=user)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass


@receiver(reception_fournisseur_confirmee,
          dispatch_uid="installations_peupler_series_entrepot_on_reception")
def _peupler_series_entrepot_on_reception(sender, reception, company, user,
                                          **kwargs):
    """YSTCK7 — à la confirmation d'une réception fournisseur, peuple le
    registre entrepôt (SerieEntrepot) depuis les séries capturées à la ligne
    (idempotent, best-effort)."""
    try:
        peupler_series_entrepot_reception(
            reception=reception, company=company, user=user)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass


@receiver(reception_fournisseur_confirmee,
          dispatch_uid="installations_reserver_stock_chantier_on_reception")
def _reserver_stock_chantier_on_reception(sender, reception, company, user,
                                          **kwargs):
    """YPROC10 — à la confirmation d'une réception fournisseur dont le BCF
    porte un `chantier_origine`, réserve les quantités reçues pour ce
    chantier (idempotent, plafonné au manque recalculé, no-op sans lien)."""
    try:
        reserver_stock_recu_pour_chantier(reception=reception)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass


@receiver(bon_commande_cree,
          dispatch_uid="installations_rattacher_chantier_on_bon_commande_cree")
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
    try:
        Installation.objects.filter(
            devis_id=devis_id, company=company, bon_commande__isnull=True,
        ).update(bon_commande=instance)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass


@receiver(facture_fournisseur_creee,
          dispatch_uid="installations_lettrer_gr_ir_on_facture")
def _lettrer_gr_ir_on_facture(sender, instance, company, user=None, **kwargs):
    """YPROC3 — à la création d'une facture fournisseur, lettre les
    provisions GR/IR ouvertes du même bon de commande (idempotent).

    Contrat unifié du signal (core/events.py) : ``instance`` = la
    stock.FactureFournisseur, ``user`` optionnel (None pour une création
    système/hors-requête, ex. saisie manuelle via la vue)."""
    try:
        lettrer_gr_ir_facture(facture=instance, company=company, user=user)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass
