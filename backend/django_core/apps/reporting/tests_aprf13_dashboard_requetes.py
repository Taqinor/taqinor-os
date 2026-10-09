"""APRF13 (C-APRF-025) — le tableau de bord Reporting et le contrôle
d'intégrité ``factures_payees_avec_solde`` lisent les factures à travers
``facturation.selectors.factures_avec_montant_du`` (APRF11), ``montant_du``
évalué UNE fois par facture : même nombre de requêtes avec 1 et 11 factures
payées, mêmes chiffres qu'une lecture facture par facture sans préchargement.

Sonde V_VB rejouée : ``GET reporting/dashboard/`` 49 → 198 requêtes pour +10
factures payées ; intégrité 13 → 73. HTTP réel + ``CaptureQueriesContext``,
données réelles en base, aucun mock.

Test-du-test : retirer ``factures_avec_montant_du`` dans
``factures_payees_avec_solde`` ⇒ +N requêtes par facture, ``test_integrite_
constante`` échoue ; repasser ``_avec_du`` à ``prefetch_related('lignes')``
seul ⇒ ``test_dashboard_constant`` échoue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.reporting.tests_aprf13_dashboard_requetes"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.reporting.integrity import factures_payees_avec_solde
from apps.reporting.views import _ht_encaisse
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, Paiement
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/dashboard/'


class Aprf13DashboardRequetesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aprf13-co', defaults={'nom': 'APRF13 Co'})[0]
        self.user = User.objects.create_user(
            username='aprf13_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli APRF13')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku='APRF13-P',
            prix_vente=Decimal('1000'), quantite_stock=0)
        self._n = 0

    def _facture(self, statut, paye=Decimal('0'), part=None):
        """Facture 1×1000 HT ; ``paye`` TTC réglé (ou ``part`` du TTC) ;
        statut FORCÉ ensuite (une « payée » à reliquat = la saisie que
        l'intégrité signale)."""
        self._n += 1
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-APRF13-{self._n}',
            client=self.client_obj, statut=statut)
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        if part is not None:
            paye = (Decimal(facture.total_ttc) * part).quantize(
                Decimal('0.01'))
        if paye:
            Paiement.objects.create(
                company=self.company, facture=facture, client=self.client_obj,
                montant=paye, date_paiement=date.today(),
                mode=Paiement.Mode.VIREMENT)
        Facture.objects.filter(pk=facture.pk).update(statut=statut)
        return facture

    def _lot(self, nb_payees):
        """``nb_payees`` factures payées (moitié soldées, moitié à reliquat)
        + une facture émise partiellement réglée (créance)."""
        for i in range(nb_payees):
            self._facture(Facture.Statut.PAYEE,
                          part=Decimal('1') if i % 2 == 0 else Decimal('0.5'))
        self._facture(Facture.Statut.EMISE, paye=Decimal('100'))

    def _attendu(self):
        """Chiffres recalculés facture par facture, SANS préchargement."""
        payees = list(Facture.objects.filter(
            company=self.company, statut=Facture.Statut.PAYEE))
        ca_paye = sum((_ht_encaisse(f) for f in payees), Decimal('0'))
        ouvertes = Facture.objects.filter(
            company=self.company,
            statut__in=[Facture.Statut.EMISE, Facture.Statut.EN_RETARD])
        ca_attente = sum((Decimal(f.total_ht or 0) for f in ouvertes),
                         Decimal('0'))
        ca_attente += sum(
            (Decimal(f.total_ht or 0) - _ht_encaisse(f) for f in payees),
            Decimal('0'))
        creance = sum((f.montant_du for f in ouvertes), Decimal('0'))
        anomalies = sorted(f.id for f in payees if f.montant_du != 0)
        return ca_paye, ca_attente, creance, anomalies

    def _mesure_dashboard(self):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        return len(ctx.captured_queries), resp.data

    def _verifie_chiffres(self, data):
        ca_paye, ca_attente, creance, _ = self._attendu()
        self.assertAlmostEqual(data['kpis']['ca_paye'], float(ca_paye),
                               places=2)
        self.assertAlmostEqual(data['kpis']['ca_attente'], float(ca_attente),
                               places=2)
        # Toutes les payées sont émises ce mois-ci : le dernier mois du CA
        # mensuel = CA encaissé.
        self.assertAlmostEqual(data['ca_mensuel'][-1]['ca'], float(ca_paye),
                               places=2)
        self.assertEqual(len(data['creances']), 1)
        self.assertAlmostEqual(data['creances'][0]['montant_total'],
                               float(creance), places=2)

    def test_dashboard_constant(self):
        self._lot(1)
        self._mesure_dashboard()  # chauffe (caches de session/permissions)
        n1, data1 = self._mesure_dashboard()
        self._verifie_chiffres(data1)

        self._lot(10)
        self.assertEqual(Facture.objects.filter(
            company=self.company, statut=Facture.Statut.PAYEE).count(), 11)
        n11, data11 = self._mesure_dashboard()
        self._verifie_chiffres(data11)
        self.assertEqual(
            n1, n11,
            f'dashboard : {n1} requêtes avec 1 payée, {n11} avec 11')

    def test_integrite_constante(self):
        self._lot(1)
        with CaptureQueriesContext(connection) as ctx1:
            ids1 = factures_payees_avec_solde(self.company)
        self.assertEqual(sorted(ids1), self._attendu()[3])

        self._lot(10)
        with CaptureQueriesContext(connection) as ctx11:
            ids11 = factures_payees_avec_solde(self.company)
        self.assertEqual(sorted(ids11), self._attendu()[3])
        self.assertEqual(len(ids11), 5)  # 5 payées à reliquat sur 11
        self.assertEqual(
            len(ctx1.captured_queries), len(ctx11.captured_queries),
            f'intégrité : {len(ctx1.captured_queries)} requêtes avec 1 payée, '
            f'{len(ctx11.captured_queries)} avec 11')
