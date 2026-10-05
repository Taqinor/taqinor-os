"""ACAL88 (C-ACAL-104, C-ACAL-106) — from-layout ne garde plus ses copies
inline : la dédup est ``selectors.devis_brouillon_pour_layout`` (brouillons
ACTIFS seulement), l'empreinte est posée par ``geometrie.poser_layout_hash``
et la réponse 201 porte ``avertissements`` / ``marques_manquantes``
(contrat ``contract_samples/devis_from_layout.json``).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_from_layout_dedup"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.models import Devis
from apps.ventes.selectors import devis_brouillon_pour_layout
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
           / 'devis_from_layout.json')

LAYOUT = {
    'scenario': 'reseau',
    'panelWatt': 550,
    'result': {'panels': 10, 'kwc': 5.5, 'annualKwh': 9000,
               'savings': 8000},
}


class FromLayoutDedup(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ACAL88 Co',
                                              slug='acal88-co')
        self.user = User.objects.create_user(
            username='acal88', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='ACAL88', prenom='Lead',
            email='acal88@example.test')
        for nom, sku, prix in (
                ('Panneau Jinko 550W', 'A88-PAN', '1100'),
                ('Onduleur réseau Huawei 5kW Monophasé', 'A88-OND', '14000'),
                ('Onduleur hybride Deye 5kW Monophasé', 'A88-HYB', '17000'),
                ('Batterie Dyness 5 kWh', 'A88-BAT', '16000')):
            Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)

    def _post(self):
        return self.api.post('/api/django/ventes/devis/from-layout/',
                             {'layout': dict(LAYOUT), 'lead': self.lead.pk},
                             format='json')

    def test_from_layout_brouillon_archive_non_reutilise(self):
        r1 = self._post()
        self.assertEqual(r1.status_code, 201, r1.data)
        d1 = r1.data['id']
        # L'empreinte posée = celle du layout (même formule qu'avant).
        self.assertEqual(Devis.objects.get(pk=d1).layout_hash,
                         layout_hash(LAYOUT))
        # Un second POST identique rend le brouillon ACTIF.
        r_bis = self._post()
        self.assertEqual(r_bis.status_code, 200, r_bis.data)
        self.assertTrue(r_bis.data['deduplicated'])
        self.assertEqual(r_bis.data['id'], d1)
        # Archivage (QJR661) : le brouillon n'est plus jamais rendu.
        Devis.objects.filter(pk=d1).update(is_active=False)
        r2 = self._post()
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertNotEqual(r2.data['id'], d1)
        self.assertNotIn('deduplicated', r2.data)

    def test_selecteur_dedup_exclut_archive(self):
        empreinte = layout_hash(LAYOUT)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-8801',
            lead=self.lead, statut='brouillon', taux_tva=Decimal('20'),
            layout_hash=empreinte, created_by=self.user)
        self.assertEqual(
            devis_brouillon_pour_layout(self.company, self.lead.pk,
                                        empreinte), devis)
        Devis.objects.filter(pk=devis.pk).update(is_active=False)
        self.assertIsNone(
            devis_brouillon_pour_layout(self.company, self.lead.pk,
                                        empreinte))

    def test_from_layout_renvoie_avertissements(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        r = self._post()
        self.assertEqual(r.status_code, 201, r.data)
        for cle in contrat['exemple']:
            self.assertIn(cle, r.data, cle)
        self.assertIsInstance(r.data['avertissements'], list)
        self.assertIsInstance(r.data['marques_manquantes'], list)
        r_bis = self._post()
        for cle in contrat['exemple_deduplique']:
            self.assertIn(cle, r_bis.data, cle)
