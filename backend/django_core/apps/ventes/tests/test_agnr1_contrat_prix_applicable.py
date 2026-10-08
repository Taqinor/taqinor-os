"""AGNR1 (PACT10, C-AGNR-003) — contrat d'abord : la réponse de
``GET /ventes/prix-applicable/`` égale ``contract_samples/prix_applicable.json``
(ENSEMBLE des clés, natures) et dit que le prix est HT (``unite: 'HT'``).

Rejoue la sonde V_VB p_tarif : produit 2 061,82 HT à TVA 10 %, liste « Z »
à 1 961,82 pour le client. Source réelle : ``domain/tarification`` (aucun
mock).

Test-du-test : retirer ``unite`` de la réponse ⇒ ``test_reponse_egale_contrat``
échoue.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import LignePrixListe, ListePrix
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'prix_applicable.json').read_text(encoding='utf-8'))


def _nature(valeur):
    for nature in (bool, dict, list, str):
        if isinstance(valeur, nature):
            return nature.__name__
    return 'autre'


class ContratPrixApplicableTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AGNR1', slug='agnr1-co')
        self.user = User.objects.create_user(
            username='agnr1_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 710W', sku='AGNR1-PAN',
            prix_vente=Decimal('2061.82'), tva=Decimal('10'),
            quantite_stock=10)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client Z', email='z@example.com')
        liste = ListePrix.objects.create(company=self.company, nom='Z')
        LignePrixListe.objects.create(
            liste=liste, produit=self.produit,
            prix_unitaire=Decimal('1961.82'))
        # Liste assignée au client (crm.Client.liste_prix, string-FK).
        self.client_obj.liste_prix = liste
        self.client_obj.save(update_fields=['liste_prix'])

    def _get(self, **params):
        params.setdefault('produit', self.produit.pk)
        resp = self.api.get('/api/django/ventes/prix-applicable/', params)
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()

    def test_reponse_egale_contrat(self):
        for exemple, corps in (
                (CONTRAT['exemple'], self._get(client=self.client_obj.pk)),
                (CONTRAT['exemple_standard'], self._get())):
            with self.subTest(source=exemple['source']):
                self.assertEqual(set(corps), set(exemple))
                for cle in exemple:
                    if exemple[cle] is None or corps[cle] is None:
                        continue
                    self.assertEqual(_nature(corps[cle]), _nature(exemple[cle]),
                                     cle)
                self.assertEqual(corps['unite'], 'HT')

    def test_prix_ht_liste_puis_standard(self):
        avec_client = self._get(client=self.client_obj.pk)
        self.assertEqual(avec_client['prix'], '1961.82')
        self.assertEqual(avec_client['source'], 'liste')
        self.assertEqual(avec_client['liste_nom'], 'Z')
        sans_client = self._get()
        self.assertEqual(sans_client['prix'], '2061.82')
        self.assertEqual(sans_client['source'], 'standard')
