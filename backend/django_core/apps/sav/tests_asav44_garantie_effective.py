"""ASAV44 — la garantie EFFECTIVE (max légale / constructeur) est servie
partout : `equipement_fin_garantie_effective` sur le ticket, `garantie_etat`
et `garantie_jours_restants` du parc.

Run :
    python manage.py test apps.sav.tests_asav44_garantie_effective -v2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement, Ticket
from apps.stock.models import Produit

User = get_user_model()


class GarantieEffectiveServieTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav44-co', defaults={'nom': 'ASAV44 Co'})
        self.user = User.objects.create_user(
            username='asav44_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV44')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV44', client=client)
        self.client_obj = client
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASAV44',
            prix_achat=0, prix_vente=100)
        self.today = timezone.localdate()

    def _equipement(self, serie, jours_pose, fin_constructeur=None):
        eq = Equipement.objects.create(
            company=self.company, produit=self.produit,
            installation=self.inst, numero_serie=serie,
            date_pose=self.today - timedelta(days=jours_pose),
            date_fin_garantie=fin_constructeur)
        return eq

    def test_ticket_sert_effective(self):
        # Pas de garantie constructeur : seule la légale (12 mois) compte.
        eq = self._equipement('A44-A', 240)
        t = Ticket.objects.create(
            company=self.company, reference='SAV-A44-1',
            client=self.client_obj, equipement=eq,
            type=Ticket.Type.CORRECTIF, created_by=self.user,
            date_ouverture=self.today)
        r = self.api.get(f'/api/django/sav/tickets/{t.pk}/')
        self.assertIsNone(r.data['equipement_fin_garantie'])
        self.assertEqual(r.data['equipement_fin_garantie_effective'],
                         eq.date_fin_garantie_effective.isoformat())
        self.assertEqual(r.data['sous_garantie_effectif'], 'oui')

    def test_etat_parc_effectif(self):
        # Constructeur échue depuis 60 jours, légale encore active.
        eq = self._equipement(
            'A44-B', 300, fin_constructeur=self.today - timedelta(days=60))
        r = self.api.get(f'/api/django/sav/equipements/{eq.pk}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['garantie_etat'], 'expire_bientot')
        self.assertEqual(
            r.data['garantie_jours_restants'],
            (eq.date_fin_garantie_effective - self.today).days)
        self.assertNotEqual(r.data['garantie_etat'], 'hors_garantie')
