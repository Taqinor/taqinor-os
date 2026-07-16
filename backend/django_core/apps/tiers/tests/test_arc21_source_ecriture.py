"""ARC21 — Bascule write-path (DÉCISION founder-gated, OFF par défaut).

On prouve les DEUX modes :
  - flag OFF (défaut) : ``identite_source_est_tiers()`` est False, les hooks
    d'écriture identité sont des NO-OP stricts (rien n'est écrit sur Tiers) —
    comportement byte-identique à aujourd'hui ;
  - flag ON : ``ecrire_identite`` pousse bien l'identité vers Tiers (source),
    company-scopé.
"""
from django.test import TestCase, override_settings

from testkit.factories import CompanyFactory, another_tenant

from apps.tiers import services as tiers_services
from apps.tiers.models import Tiers


class Arc21FlagOffTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_flag_off_by_default(self):
        # Aucun override → défaut du settings (OFF).
        self.assertFalse(tiers_services.identite_source_est_tiers())

    def test_ecrire_identite_is_noop_when_off(self):
        t = Tiers.objects.create(company=self.company, nom='Avant')
        wrote = tiers_services.ecrire_identite(
            company=self.company, tiers=t, champs={'nom': 'Après'})
        self.assertFalse(wrote)
        t.refresh_from_db()
        self.assertEqual(t.nom, 'Avant')  # byte-identique : rien changé.

    def test_client_hook_noop_when_off(self):
        from apps.crm.models import Client
        from apps.crm.services import ecrire_identite_client
        client = Client.objects.create(
            company=self.company, nom='ClientAvant', email='c@example.ma')
        client.refresh_from_db()  # le miroir ARC18 a posé client.tiers
        wrote = ecrire_identite_client(client)
        self.assertFalse(wrote)


@override_settings(TIERS_SOURCE_ECRITURE=True)
class Arc21FlagOnTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.other_company, _ = another_tenant()

    def test_flag_on_detected(self):
        self.assertTrue(tiers_services.identite_source_est_tiers())

    def test_ecrire_identite_writes_to_tiers(self):
        t = Tiers.objects.create(company=self.company, nom='Avant')
        wrote = tiers_services.ecrire_identite(
            company=self.company, tiers=t,
            champs={'nom': 'Après', 'email': 'x@example.ma'})
        self.assertTrue(wrote)
        t.refresh_from_db()
        self.assertEqual(t.nom, 'Après')
        self.assertEqual(t.email, 'x@example.ma')

    def test_ecrire_identite_company_scoped(self):
        # Un Tiers d'une AUTRE société ne peut pas être écrit via cette société.
        autre = Tiers.objects.create(company=self.other_company, nom='Autre')
        wrote = tiers_services.ecrire_identite(
            company=self.company, tiers=autre, champs={'nom': 'Pirate'})
        self.assertFalse(wrote)
        autre.refresh_from_db()
        self.assertEqual(autre.nom, 'Autre')
