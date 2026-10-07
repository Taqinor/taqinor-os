"""AANA22 (C-AANA-038) — tableau commercial et export classement donnent LE
même taux de victoire sur la même période.

Scénario R8 : un commercial a 2 leads ; le 2e est créé le jour ``to`` à 15 h.
Avant le correctif : l'export bornait par ``date_creation__lte=<date>``
(minuit) et ratait ce lead — 100,0 contre 50,0 au tableau commercial.

La fenêtre est désormais construite DANS ``build_leaderboard`` (bornes
``__date__`` inclusives). Données RÉELLES en base (aucun mock).
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/reporting'


class TestMemeTauxDeuxEcrans(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana22-co', defaults={'nom': 'AANA22 Co'})[0]
        self.user = User.objects.create_user(
            username='aana22_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.owner = User.objects.create_user(
            username='aana22_comm', password='x', role_legacy='responsable',
            company=self.company)
        self.to = date.today() - timedelta(days=2)
        self.frm = self.to - timedelta(days=5)

        signe = Lead.objects.create(
            company=self.company, nom='Signé', stage=stages.SIGNED,
            owner=self.owner)
        tardif = Lead.objects.create(
            company=self.company, nom='Créé le jour to à 15 h',
            stage=stages.NEW, owner=self.owner)
        Lead.objects.filter(pk=signe.pk).update(date_creation=timezone.make_aware(
            datetime.combine(self.frm + timedelta(days=1), time(10, 0))))
        Lead.objects.filter(pk=tardif.pk).update(
            date_creation=timezone.make_aware(
                datetime.combine(self.to, time(15, 0))))

        client = Client.objects.create(company=self.company, nom='Cli R8')
        produit = Produit.objects.create(
            company=self.company, nom='Kit', sku='AANA22-P',
            prix_vente=Decimal('1000'), quantite_stock=0)
        devis = Devis.objects.create(
            company=self.company, reference='DEV-AANA22', client=client,
            lead=signe, statut=Devis.Statut.ACCEPTE,
            date_acceptation=self.to)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))

    def test_meme_taux_deux_ecrans(self):
        params = f'?from={self.frm.isoformat()}&to={self.to.isoformat()}'
        resp = self.api.get(f'{BASE}/commercial/dashboard/{params}')
        self.assertEqual(resp.status_code, 200)
        taux_tableau = resp.data['leaderboard'][0]['win_rate_pct']

        resp = self.api.get(f'{BASE}/insights/sales-leaderboard/{params}')
        self.assertEqual(resp.status_code, 200)
        taux_export = resp.data['rows'][0]['win_rate_pct']

        self.assertEqual(taux_tableau, 50.0)
        self.assertEqual(taux_export, taux_tableau)
