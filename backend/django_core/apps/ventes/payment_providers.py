"""QJ24 — Abstraction fournisseurs de paiement en ligne (acompte, flag-gated).

ARCHITECTURE
------------
Ce module expose une interface unique ``PaymentProvider`` et une factory
``get_payment_provider()`` qui sélectionne le fournisseur actif selon les
variables d'environnement :

  1. CMI (Centre Monétique Interbancaire, Maroc) — si CMI_MERCHANT_ID est défini.
  2. PayZone (passerelle alternative) — si PAYZONE_MERCHANT_ID est défini.
  3. ``NoOnlineProvider`` — défaut : aucun fournisseur en ligne, aucun appel réseau.

ACTIVATION
----------
Le module entier est conditionné par la variable ``DEPOSIT_PAYMENT_ENABLED=1``.
Quand ce flag est absent ou à ``0``, ``get_payment_provider()`` retourne
toujours ``NoOnlineProvider``, quelle que soit la config des creds.

AUCUNE DÉPENDANCE EXTERNE
--------------------------
Les méthodes ``create_payment_intent`` décrivent le payload qui SERAIT envoyé
(sous forme de dict) SANS déclencher aucun appel réseau. L'intégration live est
un drop-in : remplacer le ``return`` du dict par un vrai appel HTTP (httpx,
déjà présent en dépendance) une fois le compte marchand ouvert.

WIRING FOLLOW-UP (gated) :
    L'intégration dans le flux d'acceptation de devis (endpoint e-signature /
    public_views.py) est une étape future, conditionnée à l'ouverture d'un
    compte marchand CMI ou PayZone par le fondateur. Ce module est le scaffold ;
    il ne modifie aucun statut de devis/facture et n'expose aucun prix d'achat.
"""
from __future__ import annotations

import logging
import os
from decimal import Decimal

__all__ = [
    "PaymentProvider",
    "NoOnlineProvider",
    "CmiProvider",
    "PayzoneProvider",
    "get_payment_provider",
]

logger = logging.getLogger(__name__)

# ── Variables d'environnement utilisées (documentées ici pour le fondateur) ──
#
#   DEPOSIT_PAYMENT_ENABLED   '1' pour activer la sélection CMI/PayZone.
#                              Toute autre valeur (ou absent) → NoOnlineProvider.
#   CMI_MERCHANT_ID           Identifiant marchand CMI (active CmiProvider).
#   CMI_SECRET_KEY            Clé secrète CMI pour la signature des requêtes.
#   CMI_STORE_KEY             Clé de boutique CMI (storeKey).
#   CMI_BASE_URL              URL de base de l'API CMI (ex. https://payment.cmi.co.ma).
#   PAYZONE_MERCHANT_ID       Identifiant marchand PayZone (active PayzoneProvider).
#   PAYZONE_SECRET_KEY        Clé secrète PayZone.
#   PAYZONE_BASE_URL          URL de base de l'API PayZone.


class PaymentProvider:
    """Interface de base pour tous les fournisseurs de paiement en ligne.

    Chaque fournisseur expose :
      - ``is_available()`` : True si les creds sont configurées et le flag actif.
      - ``create_payment_intent(amount, reference, return_url)`` : retourne un
        dict décrivant le payload qui SERAIT envoyé. Aucun appel réseau ici.
      - ``label`` : nom lisible du fournisseur.
    """

    label: str = "Fournisseur"

    def is_available(self) -> bool:
        """Retourne True si ce fournisseur est configuré et peut être utilisé."""
        return False

    def create_payment_intent(
        self,
        amount: Decimal,
        reference: str,
        return_url: str,
    ) -> dict:
        """Décrit le payload de redirection de paiement.

        Args:
            amount:     Montant de l'acompte en MAD (Decimal, arrondi 2 dec).
            reference:  Référence du devis (identifiant unique côté ERP).
            return_url: URL de retour après paiement (page de confirmation).

        Returns:
            Dict décrivant l'intent (provider, status, payload). Pour les
            providers configurés, contient ``redirect_url`` ; pour
            ``NoOnlineProvider``, ``status`` est ``'indisponible'``.

        Note:
            Cette méthode NE déclenche AUCUN appel réseau. Elle construit
            uniquement la structure de la requête pour validation/test.
        """
        raise NotImplementedError


class NoOnlineProvider(PaymentProvider):
    """Fournisseur par défaut — aucun paiement en ligne disponible.

    Retourné quand ``DEPOSIT_PAYMENT_ENABLED`` est absent/0 ou qu'aucun
    fournisseur avec creds n'est configuré. N'initie aucun appel réseau,
    ne modifie aucun état, ne coûte rien.
    """

    label = "Aucun paiement en ligne (non configuré)"

    def is_available(self) -> bool:
        return False

    def create_payment_intent(
        self,
        amount: Decimal,
        reference: str,
        return_url: str,
    ) -> dict:
        return {
            "provider": "none",
            "status": "indisponible",
            "message": (
                "Le paiement en ligne n'est pas encore disponible. "
                "Votre conseiller Taqinor vous contactera pour les modalités de paiement."
            ),
        }


class CmiProvider(PaymentProvider):
    """Fournisseur CMI (Centre Monétique Interbancaire, Maroc).

    ACTIF uniquement quand ``DEPOSIT_PAYMENT_ENABLED=1`` ET que
    ``CMI_MERCHANT_ID``, ``CMI_SECRET_KEY`` et ``CMI_STORE_KEY`` sont tous
    définis dans l'env.

    AUCUN appel réseau ici : ``create_payment_intent`` construit le dict du
    payload CMI (form POST 3D-Secure) sans l'envoyer. L'intégration live est
    un drop-in une fois le compte marchand ouvert (ajouter l'appel httpx et
    la vérification HMAC SHA-512 dans une sous-classe ou en remplaçant la
    méthode).
    """

    label = "CMI — Centre Monétique Interbancaire"

    def _creds(self) -> dict:
        """Lit les creds CMI depuis l'env. Dict vide si incomplet."""
        merchant_id = os.getenv("CMI_MERCHANT_ID", "").strip()
        secret_key = os.getenv("CMI_SECRET_KEY", "").strip()
        store_key = os.getenv("CMI_STORE_KEY", "").strip()
        base_url = os.getenv("CMI_BASE_URL", "https://payment.cmi.co.ma").strip()
        if merchant_id and secret_key and store_key:
            return {
                "merchant_id": merchant_id,
                "secret_key": secret_key,
                "store_key": store_key,
                "base_url": base_url,
            }
        return {}

    def is_available(self) -> bool:
        flag = os.getenv("DEPOSIT_PAYMENT_ENABLED", "0").strip()
        return flag == "1" and bool(self._creds())

    def create_payment_intent(
        self,
        amount: Decimal,
        reference: str,
        return_url: str,
    ) -> dict:
        """Construit le payload CMI (form POST 3D-Secure) SANS appel réseau.

        Le payload suit la spécification CMI Maroc (champs obligatoires du
        formulaire de paiement hébergé). La signature HMAC SHA-512 doit être
        calculée et ajoutée à ce dict avant soumission réelle.

        NOTE : Cette méthode ne doit être appelée que si ``is_available()``
        est True. Si appelée sans creds, retourne un intent indisponible.
        """
        creds = self._creds()
        if not creds:
            logger.warning("CmiProvider.create_payment_intent appelé sans creds — no-op.")
            return NoOnlineProvider().create_payment_intent(amount, reference, return_url)

        return {
            "provider": "cmi",
            "status": "scaffold_only",
            "note": (
                "SCAFFOLD — aucun appel réseau. Ajouter la signature HMAC SHA-512 "
                "et l'appel HTTP au guichet CMI une fois le compte marchand ouvert."
            ),
            "payload": {
                "clientid": creds["merchant_id"],
                "storetype": "3D_PAY_HOSTING",
                "amount": str(amount),
                "currency": "504",  # MAD ISO 4217
                "oid": reference,
                "okUrl": return_url,
                "failUrl": return_url,
                "lang": "fr",
                "rnd": None,       # à générer côté appelant (timestamp/uuid)
                "hashAlgorithm": "ver3",
                # "hash": "<HMAC-SHA512 à calculer>",
            },
            "endpoint": f"{creds['base_url']}/fim/est3Dgate",
        }


class PayzoneProvider(PaymentProvider):
    """Fournisseur PayZone (passerelle alternative Maroc).

    ACTIF uniquement quand ``DEPOSIT_PAYMENT_ENABLED=1`` ET que
    ``PAYZONE_MERCHANT_ID`` et ``PAYZONE_SECRET_KEY`` sont définis.

    Même principe que ``CmiProvider`` : scaffold only, aucun appel réseau.
    """

    label = "PayZone Maroc"

    def _creds(self) -> dict:
        merchant_id = os.getenv("PAYZONE_MERCHANT_ID", "").strip()
        secret_key = os.getenv("PAYZONE_SECRET_KEY", "").strip()
        base_url = os.getenv("PAYZONE_BASE_URL", "https://www.payzone.ma").strip()
        if merchant_id and secret_key:
            return {
                "merchant_id": merchant_id,
                "secret_key": secret_key,
                "base_url": base_url,
            }
        return {}

    def is_available(self) -> bool:
        flag = os.getenv("DEPOSIT_PAYMENT_ENABLED", "0").strip()
        return flag == "1" and bool(self._creds())

    def create_payment_intent(
        self,
        amount: Decimal,
        reference: str,
        return_url: str,
    ) -> dict:
        """Construit le payload PayZone SANS appel réseau.

        NOTE : Cette méthode ne doit être appelée que si ``is_available()``
        est True. Si appelée sans creds, retourne un intent indisponible.
        """
        creds = self._creds()
        if not creds:
            logger.warning("PayzoneProvider.create_payment_intent appelé sans creds — no-op.")
            return NoOnlineProvider().create_payment_intent(amount, reference, return_url)

        return {
            "provider": "payzone",
            "status": "scaffold_only",
            "note": (
                "SCAFFOLD — aucun appel réseau. Ajouter la signature et "
                "l'appel HTTP PayZone une fois le compte marchand ouvert."
            ),
            "payload": {
                "merchant_id": creds["merchant_id"],
                "amount": str(amount),
                "currency": "MAD",
                "order_id": reference,
                "return_url": return_url,
                "language": "fr",
            },
            "endpoint": f"{creds['base_url']}/payment/initiate",
        }


def get_payment_provider() -> PaymentProvider:
    """Factory : retourne le fournisseur de paiement actif.

    Ordre de sélection :
      1. ``CmiProvider`` — si ``DEPOSIT_PAYMENT_ENABLED=1`` et creds CMI présentes.
      2. ``PayzoneProvider`` — si ``DEPOSIT_PAYMENT_ENABLED=1`` et creds PayZone présentes.
      3. ``NoOnlineProvider`` — par défaut (flag absent/0 ou aucun cred configuré).

    Jamais d'exception — toujours un provider utilisable retourné.
    """
    flag = os.getenv("DEPOSIT_PAYMENT_ENABLED", "0").strip()
    if flag != "1":
        return NoOnlineProvider()

    cmi = CmiProvider()
    if cmi.is_available():
        return cmi

    payzone = PayzoneProvider()
    if payzone.is_available():
        return payzone

    return NoOnlineProvider()
