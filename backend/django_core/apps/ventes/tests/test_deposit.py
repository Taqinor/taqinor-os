"""QJ24 — Tests du scaffold acompte (deposit) + fournisseurs de paiement.

Couvre :
  * compute_deposit : calcul correct, arrondi ROUND_HALF_UP, taux par défaut,
    taux configuré via env, valeurs limites (0, 1, grand TTC), erreurs.
  * deposit_protection_message : message en français, présence du montant et
    de la référence.
  * get_payment_provider (flag-off) : retourne NoOnlineProvider, status
    'indisponible', is_available() False — aucun appel réseau.
  * get_payment_provider (CMI creds présentes) : retourne CmiProvider disponible,
    create_payment_intent retourne le bon payload (scaffold only, pas d'appel réseau).
  * get_payment_provider (PayZone creds présentes, pas CMI) : retourne PayzoneProvider.
  * get_payment_provider (creds incomplètes) : retourne NoOnlineProvider.
  * CmiProvider / PayzoneProvider appelés sans creds : fallback NoOnlineProvider.

Run :
    python manage.py test apps.ventes.tests.test_deposit -v 2
"""
import os
import unittest
from decimal import Decimal
from unittest.mock import patch


# ── helpers pour patcher l'env proprement ────────────────────────────────────

def _env(**kwargs):
    """Context manager : surcharge des variables d'env, nettoie après le test."""
    return patch.dict(os.environ, {k: str(v) for k, v in kwargs.items()})


def _clear_env(*keys):
    """Context manager : retire les variables d'env, nettoie après le test."""
    return patch.dict(os.environ, {k: "" for k in keys}, clear=False)


# ── Tests deposit.py ──────────────────────────────────────────────────────────

class TestComputeDeposit(unittest.TestCase):
    """compute_deposit : calcul et arrondis."""

    def setUp(self):
        from apps.ventes.deposit import compute_deposit
        self.compute = compute_deposit

    def test_default_rate_30_percent(self):
        """Taux par défaut 30 % sur un TTC rond."""
        result = self.compute(Decimal("10000.00"))
        self.assertEqual(result, Decimal("3000.00"))

    def test_explicit_rate_50_percent(self):
        """Taux explicite 50 %."""
        result = self.compute(Decimal("5000.00"), rate=Decimal("0.50"))
        self.assertEqual(result, Decimal("2500.00"))

    def test_rounding_half_up(self):
        """Arrondi ROUND_HALF_UP : 0.005 → 0.01."""
        # 3.33... → arrondi à 0.01 vers le haut si le 3e dec >= 5
        # 10.00 * 0.3 = 3.00 (exact), testons un cas non-exact
        result = self.compute(Decimal("3333.34"), rate=Decimal("0.30"))
        # 3333.34 * 0.30 = 1000.002 → arrondi HALF_UP → 1000.00
        self.assertEqual(result, Decimal("1000.00"))

    def test_rounding_rounds_up_at_half(self):
        """3333.35 * 0.30 = 1000.005 → ROUND_HALF_UP → 1000.01."""
        result = self.compute(Decimal("3333.35"), rate=Decimal("0.30"))
        self.assertEqual(result, Decimal("1000.01"))

    def test_zero_total(self):
        """Acompte sur TTC zéro → 0.00."""
        result = self.compute(Decimal("0.00"))
        self.assertEqual(result, Decimal("0.00"))

    def test_large_amount(self):
        """Grand montant (installation industrielle) → calcul correct."""
        result = self.compute(Decimal("500000.00"), rate=Decimal("0.30"))
        self.assertEqual(result, Decimal("150000.00"))

    def test_negative_total_raises(self):
        """TTC négatif → ValueError."""
        with self.assertRaises(ValueError):
            self.compute(Decimal("-100.00"))

    def test_invalid_rate_zero_raises(self):
        """Taux à 0 → ValueError."""
        with self.assertRaises(ValueError):
            self.compute(Decimal("1000.00"), rate=Decimal("0"))

    def test_invalid_rate_above_one_raises(self):
        """Taux > 1 → ValueError."""
        with self.assertRaises(ValueError):
            self.compute(Decimal("1000.00"), rate=Decimal("1.01"))

    def test_rate_one_allowed(self):
        """Taux = 1.0 (acompte 100 %) → TTC complet."""
        result = self.compute(Decimal("1000.00"), rate=Decimal("1.0"))
        self.assertEqual(result, Decimal("1000.00"))

    def test_env_rate_override(self):
        """DEPOSIT_RATE dans l'env surcharge le taux par défaut."""
        with _env(DEPOSIT_RATE="0.20"):
            result = self.compute(Decimal("10000.00"))
            self.assertEqual(result, Decimal("2000.00"))

    def test_env_rate_invalid_falls_back_to_default(self):
        """DEPOSIT_RATE invalide dans l'env → taux par défaut (0.30)."""
        with _env(DEPOSIT_RATE="not_a_number"):
            result = self.compute(Decimal("10000.00"))
            self.assertEqual(result, Decimal("3000.00"))

    def test_env_rate_zero_falls_back_to_default(self):
        """DEPOSIT_RATE=0 → hors intervalle → taux par défaut."""
        with _env(DEPOSIT_RATE="0"):
            result = self.compute(Decimal("10000.00"))
            self.assertEqual(result, Decimal("3000.00"))

    def test_result_is_decimal(self):
        """Le résultat est toujours un Decimal (pas un float)."""
        result = self.compute(Decimal("1234.56"))
        self.assertIsInstance(result, Decimal)

    def test_string_total_accepted(self):
        """total_ttc passé comme string → conversion interne OK."""
        result = self.compute("10000.00")  # type: ignore[arg-type]
        self.assertEqual(result, Decimal("3000.00"))


class TestDepositProtectionMessage(unittest.TestCase):
    """deposit_protection_message : texte en français."""

    def setUp(self):
        from apps.ventes.deposit import deposit_protection_message
        self.msg = deposit_protection_message

    def test_contains_amount(self):
        """Le message contient le montant en MAD (séparateur décimal indépendant)."""
        text = self.msg(Decimal("3000.00"))
        # Le montant et la devise doivent être présents ; le séparateur décimal
        # peut varier selon la locale Python (. ou ,), on teste séparément.
        self.assertIn("MAD", text)
        # 3000 → formaté avec séparateur de milliers : "3 000" ou "3,000"
        self.assertTrue(
            "3 000" in text or "3,000" in text or "3000" in text,
            f"Le montant 3000 n'est pas trouvé dans : {text!r}",
        )

    def test_contains_reference(self):
        """Si une référence est fournie, elle apparaît dans le message."""
        text = self.msg(Decimal("1500.00"), reference="DEV-202406-0042")
        self.assertIn("DEV-202406-0042", text)

    def test_no_reference(self):
        """Sans référence, le message reste valide (pas d'exception)."""
        text = self.msg(Decimal("1500.00"))
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 20)

    def test_message_is_french(self):
        """Le message contient des marqueurs français attendus."""
        text = self.msg(Decimal("2000.00"))
        self.assertIn("acompte", text.lower())
        self.assertIn("sécu", text.lower())

    def test_returns_string(self):
        """Retourne toujours une str."""
        result = self.msg(Decimal("500.00"), "REF-001")
        self.assertIsInstance(result, str)


# ── Tests payment_providers.py ────────────────────────────────────────────────

class TestGetPaymentProviderFlagOff(unittest.TestCase):
    """Quand DEPOSIT_PAYMENT_ENABLED est absent ou 0 → NoOnlineProvider."""

    def setUp(self):
        from apps.ventes.payment_providers import get_payment_provider, NoOnlineProvider
        self.get_provider = get_payment_provider
        self.NoOnlineProvider = NoOnlineProvider

    def test_flag_absent_returns_no_online(self):
        """Sans flag, get_payment_provider() → NoOnlineProvider."""
        env_clear = {
            "DEPOSIT_PAYMENT_ENABLED": "",
            "CMI_MERCHANT_ID": "",
            "PAYZONE_MERCHANT_ID": "",
        }
        with patch.dict(os.environ, env_clear):
            provider = self.get_provider()
            self.assertIsInstance(provider, self.NoOnlineProvider)

    def test_flag_zero_returns_no_online(self):
        """DEPOSIT_PAYMENT_ENABLED=0 → NoOnlineProvider même avec creds."""
        env = {
            "DEPOSIT_PAYMENT_ENABLED": "0",
            "CMI_MERCHANT_ID": "MERCHANT123",
            "CMI_SECRET_KEY": "secret",
            "CMI_STORE_KEY": "storekey",
        }
        with patch.dict(os.environ, env):
            provider = self.get_provider()
            self.assertIsInstance(provider, self.NoOnlineProvider)

    def test_no_online_provider_not_available(self):
        """NoOnlineProvider.is_available() → False."""
        with patch.dict(os.environ, {"DEPOSIT_PAYMENT_ENABLED": "0"}):
            provider = self.get_provider()
            self.assertFalse(provider.is_available())

    def test_no_online_provider_intent_status(self):
        """NoOnlineProvider.create_payment_intent → status 'indisponible'."""
        with patch.dict(os.environ, {"DEPOSIT_PAYMENT_ENABLED": "0"}):
            provider = self.get_provider()
            intent = provider.create_payment_intent(
                Decimal("3000.00"), "DEV-001", "https://erp.example.com/retour"
            )
            self.assertEqual(intent["status"], "indisponible")

    def test_no_online_provider_intent_no_network(self):
        """L'appel à create_payment_intent ne lève aucune exception réseau."""
        with patch.dict(os.environ, {"DEPOSIT_PAYMENT_ENABLED": "0"}):
            provider = self.get_provider()
            # Doit s'exécuter sans erreur ni appel réseau
            intent = provider.create_payment_intent(
                Decimal("1500.00"), "REF-TEST", "https://example.com"
            )
            self.assertIsInstance(intent, dict)


class TestGetPaymentProviderCmiSelected(unittest.TestCase):
    """Quand CMI_MERCHANT_ID + creds + flag=1 → CmiProvider sélectionné."""

    def _cmi_env(self):
        return {
            "DEPOSIT_PAYMENT_ENABLED": "1",
            "CMI_MERCHANT_ID": "TEST_MERCHANT",
            "CMI_SECRET_KEY": "test_secret_key",
            "CMI_STORE_KEY": "test_store_key",
            "CMI_BASE_URL": "https://payment.cmi.co.ma",
        }

    def setUp(self):
        from apps.ventes.payment_providers import get_payment_provider, CmiProvider
        self.get_provider = get_payment_provider
        self.CmiProvider = CmiProvider

    def test_cmi_selected_when_configured(self):
        """CMI sélectionné quand flag=1 et creds présentes."""
        with patch.dict(os.environ, self._cmi_env()):
            provider = self.get_provider()
            self.assertIsInstance(provider, self.CmiProvider)

    def test_cmi_is_available(self):
        """CmiProvider.is_available() → True quand creds configurées."""
        with patch.dict(os.environ, self._cmi_env()):
            from apps.ventes.payment_providers import CmiProvider
            provider = CmiProvider()
            self.assertTrue(provider.is_available())

    def test_cmi_intent_scaffold_only(self):
        """create_payment_intent retourne scaffold (pas d'appel réseau)."""
        with patch.dict(os.environ, self._cmi_env()):
            provider = self.get_provider()
            intent = provider.create_payment_intent(
                Decimal("3000.00"),
                "DEV-202406-0001",
                "https://erp.taqinor.ma/retour",
            )
            self.assertEqual(intent["provider"], "cmi")
            self.assertEqual(intent["status"], "scaffold_only")
            self.assertIn("payload", intent)
            self.assertIn("endpoint", intent)

    def test_cmi_intent_payload_fields(self):
        """Le payload CMI contient les champs obligatoires."""
        with patch.dict(os.environ, self._cmi_env()):
            provider = self.get_provider()
            intent = provider.create_payment_intent(
                Decimal("5000.00"), "REF-001", "https://example.com/ok"
            )
            payload = intent["payload"]
            self.assertEqual(payload["clientid"], "TEST_MERCHANT")
            self.assertEqual(payload["currency"], "504")  # MAD ISO 4217
            self.assertEqual(payload["amount"], "5000.00")
            self.assertEqual(payload["oid"], "REF-001")
            self.assertEqual(payload["okUrl"], "https://example.com/ok")

    def test_cmi_missing_secret_key_falls_back_to_noop(self):
        """CMI sans CMI_SECRET_KEY → is_available() False, factory → NoOnlineProvider."""
        env = {
            "DEPOSIT_PAYMENT_ENABLED": "1",
            "CMI_MERCHANT_ID": "TEST_MERCHANT",
            "CMI_SECRET_KEY": "",
            "CMI_STORE_KEY": "storekey",
            "PAYZONE_MERCHANT_ID": "",
        }
        with patch.dict(os.environ, env):
            from apps.ventes.payment_providers import NoOnlineProvider
            provider = self.get_provider()
            self.assertIsInstance(provider, NoOnlineProvider)

    def test_cmi_no_creds_create_intent_noop(self):
        """CmiProvider sans creds → create_payment_intent retourne NoOp."""
        env = {
            "DEPOSIT_PAYMENT_ENABLED": "1",
            "CMI_MERCHANT_ID": "",
            "CMI_SECRET_KEY": "",
            "CMI_STORE_KEY": "",
        }
        with patch.dict(os.environ, env):
            from apps.ventes.payment_providers import CmiProvider
            provider = CmiProvider()
            intent = provider.create_payment_intent(
                Decimal("1000.00"), "REF", "https://x.com"
            )
            self.assertEqual(intent["status"], "indisponible")


class TestGetPaymentProviderPayzoneSelected(unittest.TestCase):
    """PayZone sélectionné quand CMI absent et PayZone configuré."""

    def _payzone_env(self):
        return {
            "DEPOSIT_PAYMENT_ENABLED": "1",
            "CMI_MERCHANT_ID": "",
            "CMI_SECRET_KEY": "",
            "CMI_STORE_KEY": "",
            "PAYZONE_MERCHANT_ID": "PZ_MERCHANT",
            "PAYZONE_SECRET_KEY": "pz_secret",
            "PAYZONE_BASE_URL": "https://www.payzone.ma",
        }

    def setUp(self):
        from apps.ventes.payment_providers import get_payment_provider, PayzoneProvider
        self.get_provider = get_payment_provider
        self.PayzoneProvider = PayzoneProvider

    def test_payzone_selected_when_cmi_absent(self):
        """PayZone sélectionné si CMI non configuré et PayZone configuré."""
        with patch.dict(os.environ, self._payzone_env()):
            provider = self.get_provider()
            self.assertIsInstance(provider, self.PayzoneProvider)

    def test_payzone_is_available(self):
        """PayzoneProvider.is_available() → True quand creds configurées."""
        with patch.dict(os.environ, self._payzone_env()):
            from apps.ventes.payment_providers import PayzoneProvider
            provider = PayzoneProvider()
            self.assertTrue(provider.is_available())

    def test_payzone_intent_scaffold_only(self):
        """create_payment_intent PayZone → scaffold only, pas d'appel réseau."""
        with patch.dict(os.environ, self._payzone_env()):
            provider = self.get_provider()
            intent = provider.create_payment_intent(
                Decimal("4500.00"),
                "DEV-202406-0042",
                "https://erp.taqinor.ma/retour",
            )
            self.assertEqual(intent["provider"], "payzone")
            self.assertEqual(intent["status"], "scaffold_only")
            self.assertIn("payload", intent)

    def test_payzone_intent_payload_fields(self):
        """Le payload PayZone contient les champs attendus."""
        with patch.dict(os.environ, self._payzone_env()):
            provider = self.get_provider()
            intent = provider.create_payment_intent(
                Decimal("2000.00"), "REF-042", "https://example.com/ok"
            )
            payload = intent["payload"]
            self.assertEqual(payload["merchant_id"], "PZ_MERCHANT")
            self.assertEqual(payload["amount"], "2000.00")
            self.assertEqual(payload["currency"], "MAD")
            self.assertEqual(payload["order_id"], "REF-042")

    def test_payzone_missing_secret_falls_back_to_noop(self):
        """PayZone sans PAYZONE_SECRET_KEY → factory → NoOnlineProvider."""
        env = {
            "DEPOSIT_PAYMENT_ENABLED": "1",
            "CMI_MERCHANT_ID": "",
            "CMI_SECRET_KEY": "",
            "CMI_STORE_KEY": "",
            "PAYZONE_MERCHANT_ID": "PZ_MERCHANT",
            "PAYZONE_SECRET_KEY": "",
        }
        with patch.dict(os.environ, env):
            from apps.ventes.payment_providers import NoOnlineProvider
            provider = self.get_provider()
            self.assertIsInstance(provider, NoOnlineProvider)

    def test_payzone_no_creds_create_intent_noop(self):
        """PayzoneProvider sans creds → create_payment_intent retourne NoOp."""
        env = {
            "DEPOSIT_PAYMENT_ENABLED": "1",
            "PAYZONE_MERCHANT_ID": "",
            "PAYZONE_SECRET_KEY": "",
        }
        with patch.dict(os.environ, env):
            from apps.ventes.payment_providers import PayzoneProvider
            provider = PayzoneProvider()
            intent = provider.create_payment_intent(
                Decimal("1000.00"), "REF", "https://x.com"
            )
            self.assertEqual(intent["status"], "indisponible")


class TestProviderSelectionPriority(unittest.TestCase):
    """CMI prend priorité sur PayZone quand les deux sont configurés."""

    def test_cmi_beats_payzone(self):
        """Si CMI ET PayZone configurés, CMI est sélectionné."""
        env = {
            "DEPOSIT_PAYMENT_ENABLED": "1",
            "CMI_MERCHANT_ID": "CMI_MERCHANT",
            "CMI_SECRET_KEY": "cmi_secret",
            "CMI_STORE_KEY": "cmi_store",
            "PAYZONE_MERCHANT_ID": "PZ_MERCHANT",
            "PAYZONE_SECRET_KEY": "pz_secret",
        }
        with patch.dict(os.environ, env):
            from apps.ventes.payment_providers import get_payment_provider, CmiProvider
            provider = get_payment_provider()
            self.assertIsInstance(provider, CmiProvider)

    def test_fallback_to_noop_when_no_creds(self):
        """Flag=1 mais aucun cred → NoOnlineProvider."""
        env = {
            "DEPOSIT_PAYMENT_ENABLED": "1",
            "CMI_MERCHANT_ID": "",
            "CMI_SECRET_KEY": "",
            "CMI_STORE_KEY": "",
            "PAYZONE_MERCHANT_ID": "",
            "PAYZONE_SECRET_KEY": "",
        }
        with patch.dict(os.environ, env):
            from apps.ventes.payment_providers import get_payment_provider, NoOnlineProvider
            provider = get_payment_provider()
            self.assertIsInstance(provider, NoOnlineProvider)


class TestNoOnlineProviderDirectly(unittest.TestCase):
    """Tests directs sur NoOnlineProvider (importé directement)."""

    def setUp(self):
        from apps.ventes.payment_providers import NoOnlineProvider
        self.provider = NoOnlineProvider()

    def test_not_available(self):
        self.assertFalse(self.provider.is_available())

    def test_intent_has_none_provider_key(self):
        intent = self.provider.create_payment_intent(
            Decimal("100.00"), "REF", "https://x.com"
        )
        self.assertEqual(intent["provider"], "none")

    def test_intent_message_in_french(self):
        intent = self.provider.create_payment_intent(
            Decimal("100.00"), "REF", "https://x.com"
        )
        self.assertIn("message", intent)
        text = intent["message"]
        # Contient un mot français identifiable
        self.assertTrue(
            any(word in text.lower() for word in ["paiement", "conseiller", "disponible"]),
            f"Message ne semble pas être en français : {text!r}",
        )


if __name__ == "__main__":
    unittest.main()
