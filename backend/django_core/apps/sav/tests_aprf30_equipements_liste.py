"""APRF30 — `GET /sav/equipements/` coûte le même nombre de requêtes à 5 et à
30 lignes, avec des compteurs de tickets identiques à l'ancien `.count()`.

Run :
    python manage.py test apps.sav.tests_aprf30_equipements_liste -v2
"""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import CategorieEquipement, Equipement, Ticket
from apps.sav.serializers import EquipementSerializer
from apps.stock.models import Produit

User = get_user_model()
URL = '/api/django/sav/equipements/?rebut=tous&page_size=100'


class EquipementsListeTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='aprf30-co', defaults={'nom': 'APRF30 Co'})
        self.user = User.objects.create_user(
            username='aprf30_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='APRF30')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-APRF30',
            client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-APRF30',
            prix_achat=0, prix_vente=100)
        self.categorie = CategorieEquipement.objects.create(
            company=self.company, nom='Onduleurs')
        self.n = 0

    def _equipements(self, nb):
        crees = []
        for _ in range(nb):
            self.n += 1
            eq = Equipement.objects.create(
                company=self.company, produit=self.produit,
                installation=self.inst, numero_serie=f'APRF30-{self.n}',
                categorie=self.categorie, created_by=self.user)
            for statut, annule in (('nouveau', False), ('en_cours', False),
                                   ('nouveau', True), ('cloture', False)):
                Ticket.objects.create(
                    company=self.company, reference=f'SAV-A30-{self.n}-{statut}-{annule}',
                    client=self.client_obj, equipement=eq,
                    type=Ticket.Type.CORRECTIF, statut=statut, annule=annule)
            crees.append(eq)
        return crees

    def _requetes(self):
        with CaptureQueriesContext(connection) as ctx:
            r = self.api.get(URL)
            self.assertEqual(r.status_code, 200, r.content)
        data = r.data['results'] if isinstance(r.data, dict) else r.data
        return len(ctx), data

    def test_requetes_plates_et_compteurs_identiques(self):
        self._equipements(5)
        self._requetes()  # échauffement
        petit, _ = self._requetes()
        self._equipements(25)
        grand, data = self._requetes()
        self.assertEqual(petit, grand)
        self.assertEqual(len(data), 30)
        # Compteurs égaux à l'ancien calcul unitaire (repli ``.count()``).
        for ligne in data:
            eq = Equipement.objects.get(pk=ligne['id'])
            attendu = EquipementSerializer(eq).data
            self.assertEqual(ligne['nb_tickets_ouverts'],
                             attendu['nb_tickets_ouverts'])
            self.assertEqual(ligne['nb_tickets_12m'], attendu['nb_tickets_12m'])
        self.assertEqual(data[0]['nb_tickets_ouverts'], 2)
