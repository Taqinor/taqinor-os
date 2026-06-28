"""Tests LITIGE3 — suspension des relances automatiques pour les factures en litige.

Couvre :
- litiges.selectors.relances_suspendues_pour_facture : True/False selon l'état
  du litige (ouvert bloquant, résolu, autre société, bloque_relances=False).
- ventes.scheduled.relance_reminders : skip d'une facture litigieuse, envoi
  normal pour une facture sans litige, et pour une facture dont le litige est
  résolu.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.litiges.models import Reclamation
from apps.litiges.selectors import relances_suspendues_pour_facture
from apps.stock.models import Produit
from apps.ventes.models import Facture, FollowupLevel, LigneFacture


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


class TestRelancesSuspendusPourFacture(TestCase):
    """Tests unitaires du sélecteur litiges."""

    def setUp(self):
        self.co_a = make_company("litige3-sel-a", "A")
        self.co_b = make_company("litige3-sel-b", "B")
        self.facture_id = 9999  # PK virtuel — le sélecteur ne charge pas la facture.

    def _reclamation(self, company=None, statut=Reclamation.Statut.OUVERTE,
                     bloque=True, source_type="facture", source_id=None):
        company = company or self.co_a
        source_id = source_id if source_id is not None else self.facture_id
        return Reclamation.objects.create(
            company=company,
            objet="Test litige",
            source_type=source_type,
            source_id=source_id,
            statut=statut,
            bloque_relances=bloque,
        )

    # ── Cas positif : litige ouvert bloquant ─────────────────────────────────

    def test_returns_true_for_open_blocking_dispute(self):
        self._reclamation()
        self.assertTrue(
            relances_suspendues_pour_facture(self.facture_id, self.co_a))

    def test_returns_true_for_en_traitement_blocking_dispute(self):
        self._reclamation(statut=Reclamation.Statut.EN_TRAITEMENT)
        self.assertTrue(
            relances_suspendues_pour_facture(self.facture_id, self.co_a))

    # ── Cas négatifs ─────────────────────────────────────────────────────────

    def test_returns_false_when_no_dispute(self):
        self.assertFalse(
            relances_suspendues_pour_facture(self.facture_id, self.co_a))

    def test_returns_false_when_dispute_resolved(self):
        self._reclamation(statut=Reclamation.Statut.RESOLUE)
        self.assertFalse(
            relances_suspendues_pour_facture(self.facture_id, self.co_a))

    def test_returns_false_when_dispute_rejected(self):
        self._reclamation(statut=Reclamation.Statut.REJETEE)
        self.assertFalse(
            relances_suspendues_pour_facture(self.facture_id, self.co_a))

    def test_returns_false_when_bloque_relances_false(self):
        self._reclamation(bloque=False)
        self.assertFalse(
            relances_suspendues_pour_facture(self.facture_id, self.co_a))

    def test_isolation_company_scoped(self):
        """Un litige de la société B ne bloque pas les relances de A."""
        self._reclamation(company=self.co_b)
        self.assertFalse(
            relances_suspendues_pour_facture(self.facture_id, self.co_a))

    def test_returns_false_when_source_type_not_facture(self):
        self._reclamation(source_type="lead")
        self.assertFalse(
            relances_suspendues_pour_facture(self.facture_id, self.co_a))

    def test_returns_false_when_source_id_differs(self):
        self._reclamation(source_id=self.facture_id + 1)
        self.assertFalse(
            relances_suspendues_pour_facture(self.facture_id, self.co_a))


class TestRelanceReminderSkipsLitige(TestCase):
    """Tests d'intégration : relance_reminders saute les factures en litige."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.company = make_company("litige3-sch", "Sched Co")
        self.client_obj = Client.objects.create(
            company=self.company, nom="Débiteur",
            email="deb-litige@example.ma")
        self.produit = Produit.objects.create(
            company=self.company, nom="Panneau", sku="PAN-LIT3",
            prix_vente=Decimal("1000"), quantite_stock=10, tva=Decimal("20.00"))
        FollowupLevel.objects.create(
            company=self.company, ordre=1, nom="Rappel", delai_jours=7,
            message="Merci de régler.")

    def _facture(self, ref, echeance_delta=-20):
        f = Facture.objects.create(
            company=self.company, reference=ref,
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal("20.00"),
            date_echeance=date.today() - timedelta(days=abs(echeance_delta)))
        LigneFacture.objects.create(
            facture=f, produit=self.produit, designation="Panneau",
            quantite=Decimal("1"), prix_unitaire=Decimal("1000"),
            taux_tva=Decimal("20.00"))
        Facture.objects.filter(pk=f.pk).update(
            prochaine_relance=date.today() - timedelta(days=1))
        f.refresh_from_db()
        return f

    def _litige(self, facture, statut=Reclamation.Statut.OUVERTE, bloque=True):
        return Reclamation.objects.create(
            company=self.company, objet="Litige test",
            source_type="facture", source_id=facture.id,
            statut=statut, bloque_relances=bloque)

    @patch("apps.ventes.email_service.send_relance_email")
    def test_relance_skipped_for_facture_en_litige(self, mock_send):
        """La facture avec un litige bloquant actif n'est PAS relancée."""
        f = self._facture("FAC-LIT3-0001")
        self._litige(f)
        from apps.ventes.scheduled import relance_reminders
        n = relance_reminders()
        self.assertEqual(n, 0)
        mock_send.assert_not_called()

    @patch("apps.ventes.email_service.send_relance_email")
    def test_relance_sent_when_no_litige(self, mock_send):
        """Sans litige, la facture est bien relancée."""
        f = self._facture("FAC-LIT3-0002")
        from apps.ventes.scheduled import relance_reminders
        n = relance_reminders()
        self.assertEqual(n, 1)
        mock_send.assert_called_once()

    @patch("apps.ventes.email_service.send_relance_email")
    def test_relance_sent_when_litige_resolved(self, mock_send):
        """Un litige résolu ne bloque plus les relances."""
        f = self._facture("FAC-LIT3-0003")
        self._litige(f, statut=Reclamation.Statut.RESOLUE)
        from apps.ventes.scheduled import relance_reminders
        n = relance_reminders()
        self.assertEqual(n, 1)
        mock_send.assert_called_once()

    @patch("apps.ventes.email_service.send_relance_email")
    def test_relance_sent_when_bloque_relances_false(self, mock_send):
        """Un litige avec bloque_relances=False ne bloque pas les relances."""
        f = self._facture("FAC-LIT3-0004")
        self._litige(f, bloque=False)
        from apps.ventes.scheduled import relance_reminders
        n = relance_reminders()
        self.assertEqual(n, 1)
        mock_send.assert_called_once()
