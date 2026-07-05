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
    devis_accepted, reception_fournisseur_confirmee,
    facture_fournisseur_creee,
)

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


@receiver(facture_fournisseur_creee,
          dispatch_uid="installations_lettrer_gr_ir_on_facture")
def _lettrer_gr_ir_on_facture(sender, facture, company, user, **kwargs):
    """YPROC3 — à la création d'une facture fournisseur, lettre les
    provisions GR/IR ouvertes du même bon de commande (idempotent)."""
    try:
        lettrer_gr_ir_facture(facture=facture, company=company, user=user)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass
