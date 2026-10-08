"""AFAC53 — KPI factures du tableau Quote-to-Cash sur les définitions du modèle
et de la période : Facturé = Σ total_ttc des factures émises de la période,
Encaissé = paiements non rejetés de la période, DSO sur l'encours réel."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from authentication.models import Company

User = get_user_model()
URL = '/api/django/ventes/dashboard/'
URL_KPIS = '/api/django/ventes/factures/kpis/'


class DashboardQ2cKpisTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='afac53-co', nom='AFAC53 Co')
        self.user = User.objects.create_user(
            username='afac53_resp', password='x', role_legacy='responsable',
            company=self.co)
        self.client_obj = Client.objects.create(
            company=self.co, nom='Test', prenom='Client',
            email='afac53@example.com', telephone='+212600000053')
        self.produit = Produit.objects.create(
            company=self.co, nom='Prestation', sku='AFAC53-P',
            prix_vente=Decimal('1000'), quantite_stock=5)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.aujourdhui = timezone.localdate()
        self.debut = self.aujourdhui - timedelta(days=29)

    def _facture(self, ref, emission=None, statut=Facture.Statut.EMISE):
        """Facture classique : une ligne 1 000 HT (1 200 TTC), montant_ttc NULL."""
        f = Facture.objects.create(
            company=self.co, reference=ref, client=self.client_obj,
            statut=statut, taux_tva=Decimal('20'))
        LigneFacture.objects.create(
            facture=f, produit=self.produit, designation='Prestation',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20'))
        if emission:
            Facture.objects.filter(pk=f.pk).update(date_emission=emission)
        return f

    def _paiement(self, facture, montant, jour=None,
                  statut=Paiement.Statut.ENCAISSE):
        return Paiement.objects.create(
            company=self.co, facture=facture, montant=Decimal(montant),
            date_paiement=jour or self.aujourdhui, mode='virement',
            statut=statut)

    def _get(self, debut=None, fin=None):
        r = self.api.get(URL, {'start': (debut or self.debut).isoformat(),
                               'end': (fin or self.aujourdhui).isoformat()})
        self.assertEqual(r.status_code, 200)
        return r.data

    def _scenario(self):
        f = self._facture('FAC-AFAC53-1')
        self._paiement(f, '500')
        self._paiement(f, '300', statut=Paiement.Statut.REJETE)
        return f

    def test_facture_classique_comptee(self):
        self._scenario()
        data = self._get()
        self.assertEqual(Decimal(data['factures']['montant_facture']),
                         Decimal('1200.00'))

    def test_encaisse_hors_rejetes(self):
        f = self._facture('FAC-AFAC53-2')
        avant = Decimal(self._get()['factures']['montant_encaisse'])
        self._paiement(f, '500')
        self._paiement(f, '300', statut=Paiement.Statut.REJETE)
        apres = Decimal(self._get()['factures']['montant_encaisse'])
        self.assertEqual(apres - avant, Decimal('500.00'))

    def test_dso_sur_encours_reel(self):
        self._scenario()
        data = self._get()
        self.assertIsNotNone(data['dso_jours'])
        # encours 700 / facturé 1 200 × 30 jours = 17,5
        self.assertAlmostEqual(data['dso_jours'], 17.5, places=1)

    def test_hors_periode_exclu(self):
        vieille = self._facture('FAC-AFAC53-3',
                                emission=self.aujourdhui - timedelta(days=200))
        self._paiement(vieille, '400', jour=self.aujourdhui - timedelta(days=200))
        data = self._get()
        self.assertEqual(Decimal(data['factures']['montant_facture']),
                         Decimal('0.00'))
        self.assertEqual(Decimal(data['factures']['montant_encaisse']),
                         Decimal('0.00'))
        self.assertIsNone(data['dso_jours'])

    def test_parite_ecran_factures(self):
        self._scenario()
        debut = self.aujourdhui.replace(day=1)
        r = self.api.get(URL, {'month': self.aujourdhui.strftime('%Y-%m')})
        kpis = self.api.get(URL_KPIS)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(kpis.status_code, 200)
        self.assertEqual(Decimal(r.data['factures']['montant_encaisse']),
                         Decimal(kpis.data['encaisse_mois']))
        self.assertIsInstance(debut, date)
