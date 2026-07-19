"""PUB60 — clients_sans_contrat_actif (version bulk de client_a_contrat_actif,
YSERV10) : dénominateur SAV du cross-sell « base installée sans entretien »."""
from datetime import date

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance
from apps.sav.selectors import clients_sans_contrat_actif


class ClientsSansContratActifTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB60 SAV Co')
        self.avec = Client.objects.create(
            company=self.company, nom='Avec', prenom='Contrat')
        self.sans = Client.objects.create(
            company=self.company, nom='Sans', prenom='Contrat')
        self.inactif = Client.objects.create(
            company=self.company, nom='Contrat', prenom='Inactif')
        ContratMaintenance.objects.create(
            company=self.company, client=self.avec, periodicite='annuel',
            date_debut=date.today(), actif=True)
        ContratMaintenance.objects.create(
            company=self.company, client=self.inactif, periodicite='annuel',
            date_debut=date.today(), actif=False)

    def test_empty_ids_returns_empty_set(self):
        self.assertEqual(clients_sans_contrat_actif(self.company, []), set())

    def test_client_with_active_contract_excluded(self):
        result = clients_sans_contrat_actif(
            self.company, [self.avec.id, self.sans.id])
        self.assertEqual(result, {self.sans.id})

    def test_inactive_contract_does_not_count_as_covered(self):
        result = clients_sans_contrat_actif(self.company, [self.inactif.id])
        self.assertEqual(result, {self.inactif.id})
