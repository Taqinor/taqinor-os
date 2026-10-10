"""AFAC100 (C-AMET-005) — « Payer » au portail initie l'EXIGIBLE
(``Facture.montant_exigible`` : reste dû hors retenue de garantie non
libérée), plus jamais ``montant_du`` qui inclut la retenue.

Facture 32 023,50 TTC avec retenue 1 000 non libérée : le paiement initié
vaut 31 023,50 ; ``montant_du`` reste 32 023,50 en base. Une facture dont
seule la retenue reste n'est pas payable (400, aucune intention créée).
CMI : comportement inchangé (sans clé, méthode virement — D-ADEP-3).

Test-du-test : rétablir ``facture.montant_du`` dans ``payer`` ⇒
``test_payer_initie_le_montant_exigible_hors_retenue`` échoue (32023.50).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.portail.tests.test_paiement_portail"
"""
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.facturation.models import Facture, Paiement
from apps.portail.models import PaiementFacturePortail
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    PORTAIL_CLIENT_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
)
from authentication.models import Company, CustomUser

TTC = Decimal('32023.50')
RETENUE = Decimal('1000.00')


@override_settings(CMI_ENABLED=False, CMI_MERCHANT_KEY='')
class PortailPaiementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AFAC100 Co', slug='afac100-co')
        self.client_a = Client.objects.create(
            company=self.company, nom='Retenue', prenom='Client',
            email='afac100@example.invalid')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom=ROLE_PORTAIL_CLIENT,
            defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                      'est_systeme': True})
        user = CustomUser.objects.create_user(
            username='afac100-portail', password='motdepasse-test-1234',
            company=self.company, role=role)
        user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
        user.portail_client_id = self.client_a.id
        user.save()
        self.api = APIClient()
        self.api.force_authenticate(user=user)

    def _facture(self, reference):
        ht = (TTC / Decimal('1.2')).quantize(Decimal('0.01'))
        return Facture.objects.create(
            company=self.company, reference=reference, client=self.client_a,
            statut=Facture.Statut.EMISE, montant_ht=ht,
            montant_tva=TTC - ht, montant_ttc=TTC, taux_tva=Decimal('20'),
            retenue_garantie_mad=RETENUE)

    def _payer(self, facture):
        return self.api.post(
            f'/api/django/portail/mes-factures/{facture.id}/payer/',
            {}, format='json')

    def test_payer_initie_le_montant_exigible_hors_retenue(self):
        facture = self._facture('FAC-AFAC100-1')
        self.assertEqual(facture.montant_du, TTC)
        self.assertEqual(facture.montant_exigible, TTC - RETENUE)
        res = self._payer(facture)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['montant'], '31023.50')
        self.assertFalse(res.data['paiement_en_ligne_actif'])
        # Persistance : l'intention relue porte l'exigible ; la créance
        # (`montant_du`) est inchangée.
        paiement = PaiementFacturePortail.objects.get(pk=res.data['paiement_id'])
        self.assertEqual(paiement.montant, Decimal('31023.50'))
        self.assertEqual(paiement.methode,
                         PaiementFacturePortail.Methode.VIREMENT)
        self.assertEqual(Facture.objects.get(pk=facture.pk).montant_du, TTC)

    def test_facture_a_retenue_seule_non_payable(self):
        facture = self._facture('FAC-AFAC100-2')
        Paiement.objects.create(
            company=self.company, facture=facture, client=self.client_a,
            montant=TTC - RETENUE, date_paiement=timezone.localdate())
        facture = Facture.objects.get(pk=facture.pk)
        self.assertEqual(facture.montant_du, RETENUE)
        self.assertEqual(facture.montant_exigible, Decimal('0'))
        res = self._payer(facture)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(PaiementFacturePortail.objects.filter(
            facture=facture).exists())
