"""APRF17 (C-APRF-006) — la liste des clients coûte un nombre de requêtes
CONSTANT.

Sonde P-1 V_VA : 52 → 152 requêtes pour 5 → 15 clients à 2 factures
(4 + 3·F par client) : ``ClientSerializer`` lisait par ligne le créateur, le
nombre de devis et les totaux facturé/payé (lignes, paiements, ventilations).
``ClientViewSet.get_queryset`` les charge désormais en lot.

``CaptureQueriesContext`` à deux tailles, F = 0 / 2 / 4 factures ; valeurs
servies inchangées. Aucun mock.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.ventes.models import Devis, Facture, LigneFacture, Paiement

User = get_user_model()
URL = '/api/django/crm/clients/?page_size=200'


class ClientsListeRequetesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='APRF17 Solaire', slug='aprf17-clients')
        self.user = User.objects.create_user(
            username='aprf17-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        self.n = 0

    def _clients(self, nombre, factures):
        for _ in range(nombre):
            self.n += 1
            client = Client.objects.create(
                company=self.company, nom=f'Client {self.n}',
                created_by=self.user)
            Devis.objects.create(
                company=self.company, reference=f'DEV-APRF17-{self.n:04d}',
                client=client, statut='envoye', taux_tva=Decimal('20.00'),
                remise_globale=Decimal('0'), created_by=self.user)
            for k in range(factures):
                facture = Facture.objects.create(
                    company=self.company, client=client,
                    reference=f'FA-APRF17-{self.n:04d}-{k}',
                    statut=Facture.Statut.EMISE)
                LigneFacture.objects.create(
                    facture=facture, designation='Panneau',
                    quantite=Decimal('2'), prix_unitaire=Decimal('1000'),
                    remise=Decimal('0'))
                Paiement.objects.create(
                    company=self.company, facture=facture,
                    montant=Decimal('500'),
                    date_paiement=timezone.localdate(),
                    mode=Paiement.Mode.VIREMENT)

    def _compter(self):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        return len(ctx.captured_queries), resp

    def _verifier(self, factures):
        self._clients(5, factures)
        petite, _ = self._compter()
        self._clients(10, factures)
        grande, resp = self._compter()
        self.assertEqual(petite, grande)
        lignes = (resp.data['results'] if isinstance(resp.data, dict)
                  else resp.data)
        self.assertEqual(len(lignes), 15)
        for ligne in lignes:
            # Valeurs égales au calcul unitaire (sans préchargement).
            unitaires = list(Facture.objects.filter(client_id=ligne['id']))
            self.assertEqual(ligne['devis_count'], 1)
            self.assertEqual(
                Decimal(ligne['total_facture_ttc']),
                sum((f.total_ttc for f in unitaires), Decimal('0')))
            self.assertEqual(
                Decimal(ligne['total_paye']),
                sum((f.montant_paye for f in unitaires), Decimal('0')))
            self.assertEqual(ligne['created_by_nom'], 'aprf17-admin')

    def test_sans_facture(self):
        self._verifier(0)

    def test_deux_factures(self):
        self._verifier(2)

    def test_quatre_factures(self):
        self._verifier(4)
