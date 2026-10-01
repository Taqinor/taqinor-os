"""QJR586 (contrat QJR506 ``lead_ville_effective.json``) — UNE « ville de
calcul » : ``crm.selectors.ville_effective(lead)`` = ville de rattachement
(VREF) sinon ville tapée, lue par le moteur (entrées lead ET devis, donc
l'empreinte), le transport, le distributeur déduit, le PDF et l'écran.

Cas : un douar hors gazetier (« Sidi Hashass ») rattaché à Casablanca, sans
GPS — le moteur lisait la ville TAPÉE pendant que le PDF chiffrait Casablanca.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.crm.selectors import (
    lead_bills_for_devis, site_location_for_devis, ville_effective)
from apps.parametres.transport_bareme import prix_transport_ht
from apps.ventes.domain.entrees import entrees_depuis_devis, entrees_depuis_lead
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = (Path(__file__).resolve().parents[2] / 'crm' / 'contract_samples'
           / 'lead_ville_effective.json')


class TestVilleEffectiveParite(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        cls.company = Company.objects.create(nom='QJR586 Co', slug='qjr586-co')
        cls.user = User.objects.create_user(
            username='qjr586_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client', prenom='QJR586',
            email='qjr586@example.com', telephone='+212600005860')
        cls.lead = Lead.objects.create(
            company=cls.company, nom='Douar', client=cls.client_obj,
            ville='Sidi Hashass', ville_reference='Casablanca',
            facture_hiver=Decimal('900'), ete_differente=False,
            type_installation='residentiel')
        cls.devis = Devis.objects.create(
            company=cls.company, reference=f'DEV-{MONTH}-5860',
            client=cls.client_obj, lead=cls.lead,
            statut=Devis.Statut.BROUILLON, taux_tva=Decimal('20'),
            mode_installation='residentiel')

    def test_regle(self):
        self.assertEqual(ville_effective(self.lead), 'Casablanca')
        self.assertEqual(ville_effective(None), '')
        vide = Lead(ville='', ville_reference='')
        self.assertEqual(ville_effective(vide), '')
        seule = Lead(ville='  Agadir ', ville_reference='')
        self.assertEqual(ville_effective(seule), 'Agadir')

    def test_moteur_devis_transport_distributeur_alignes(self):
        self.assertEqual(site_location_for_devis(self.devis)['site_ville'],
                         'Casablanca')
        e_lead = entrees_depuis_lead(self.lead, self.company)
        e_devis = entrees_depuis_devis(self.devis)
        self.assertEqual(e_lead.ville, 'Casablanca')
        self.assertEqual(e_devis.ville, 'Casablanca')
        self.assertEqual(prix_transport_ht(ville_effective(self.lead)),
                         prix_transport_ht('Casablanca'))
        factures = lead_bills_for_devis(self.devis)
        from apps.crm.srm_regions import srm_depuis_ville
        self.assertEqual(factures['distributeur'],
                         srm_depuis_ville('Casablanca'))

    def test_l_empreinte_suit_la_ville_de_rattachement(self):
        from apps.ventes.domain.entrees import empreinte_entrees_du_devis
        avant = empreinte_entrees_du_devis(self.devis)
        Lead.objects.filter(pk=self.lead.pk).update(ville_reference='Agadir')
        devis = Devis.objects.get(pk=self.devis.pk)
        self.assertNotEqual(empreinte_entrees_du_devis(devis), avant)

    def test_serializer_sert_ville_effective(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        r = api.get(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        for cle in self.contrat['exemple']:
            self.assertIn(cle, r.data)
        self.assertEqual(r.data['ville_effective'], 'Casablanca')
        self.assertIsInstance(r.data['ville_effective'], str)
