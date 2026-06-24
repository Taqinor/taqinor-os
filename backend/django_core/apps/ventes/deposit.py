"""QJ24 — Calcul d'acompte (dépôt) et messagerie de protection client.

Module purement fonctionnel : aucun accès DB, aucune dépendance externe.
Fournit deux fonctions publiques :

  * ``compute_deposit(total_ttc, rate=Decimal('0.30'))``
      Calcule le montant de l'acompte en MAD, arrondi à 2 décimales vers le haut
      (moitié supérieure), à partir du total TTC passé en argument.
      Le taux est surchargeable via ``os.getenv('DEPOSIT_RATE')`` (valeur par
      défaut : 0.30, soit 30 %).

  * ``deposit_protection_message(montant, reference=None)``
      Retourne le texte de réassurance en français affiché au client au moment
      de la signature / du paiement de l'acompte.

WIRING FOLLOW-UP (gated):
    L'intégration de l'acompte dans le flux d'acceptation (endpoint e-signature)
    est une étape future, conditionnée à l'ouverture d'un compte marchand CMI ou
    PayZone par le fondateur. Ce module et ``payment_providers.py`` constituent
    le scaffold ; aucun branchement live n'est réalisé ici.
"""
from __future__ import annotations

import os
from decimal import ROUND_HALF_UP, Decimal

__all__ = ["compute_deposit", "deposit_protection_message", "DEFAULT_RATE"]

# ── Taux par défaut : 30 % — surchargeable via DEPOSIT_RATE dans l'env ────────

DEFAULT_RATE = Decimal("0.30")


def _read_rate() -> Decimal:
    """Lit le taux d'acompte depuis l'env, avec fallback à DEFAULT_RATE."""
    raw = os.getenv("DEPOSIT_RATE", "").strip()
    if raw:
        try:
            rate = Decimal(raw)
            if Decimal("0") < rate <= Decimal("1"):
                return rate
        except Exception:  # noqa: BLE001
            pass
    return DEFAULT_RATE


def compute_deposit(
    total_ttc: Decimal,
    rate: Decimal | None = None,
) -> Decimal:
    """Calcule le montant de l'acompte en MAD.

    Args:
        total_ttc: Montant total TTC du devis (passé en valeur, jamais chargé
                   depuis la DB ici — multi-tenant safe car la responsabilité
                   de la récupération est au niveau de l'appelant).
        rate:      Taux d'acompte (ex. ``Decimal('0.30')`` pour 30 %).
                   Si ``None``, lu depuis ``os.getenv('DEPOSIT_RATE')``
                   ou ``DEFAULT_RATE``.

    Returns:
        Montant arrondi à 2 décimales (ROUND_HALF_UP), en MAD.

    Raises:
        ValueError: si ``total_ttc`` est négatif ou si ``rate`` est hors [0, 1].
    """
    if rate is None:
        rate = _read_rate()

    total_ttc = Decimal(str(total_ttc))
    rate = Decimal(str(rate))

    if total_ttc < Decimal("0"):
        raise ValueError("total_ttc ne peut pas être négatif.")
    if not (Decimal("0") < rate <= Decimal("1")):
        raise ValueError(f"Le taux d'acompte doit être compris entre 0 et 1 (reçu : {rate}).")

    raw = total_ttc * rate
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def deposit_protection_message(
    montant: Decimal,
    reference: str | None = None,
) -> str:
    """Retourne le message de réassurance à afficher au client.

    Le texte est en français, conforme à la politique de l'entreprise.
    Il rassure le client sur la sécurité de son acompte et rappelle
    les conditions de la commande.

    Args:
        montant:   Montant de l'acompte (Decimal, MAD).
        reference: Référence du devis (optionnelle — enrichit le message).

    Returns:
        Chaîne de caractères prête à afficher / intégrer dans un email / PDF.
    """
    montant_str = f"{montant:,.2f}".replace(",", " ") + " MAD"
    ref_part = f" (devis {reference})" if reference else ""
    return (
        f"Votre acompte de {montant_str}{ref_part} est sécurisé. "
        "Il sera intégralement déduit du solde à payer à la livraison et "
        "à la mise en service de votre installation. "
        "En cas d'annulation de notre fait, vous êtes remboursé(e) intégralement "
        "dans un délai de 7 jours ouvrés. "
        "Pour toute question, contactez votre conseiller Taqinor."
    )
