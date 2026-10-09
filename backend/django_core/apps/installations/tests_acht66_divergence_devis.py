"""ACHT66 (C-ACHT-064) — `divergence_devis` sur le DÉTAIL d'un chantier,
calculée par le serveur avec la même fonction que `_freeze_bom` (option
retenue × N villas) comparée à `Installation.bom` ; la liste ne la calcule pas.

Contrat partagé : `contract_samples/installation_divergence_devis.json`
(ACHT40) — la forme servie en est comparée clé à clé.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht66_divergence_devis"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.events import devis_accepted

from apps.crm.models import Lead
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.ventes.models import Client, Devis, LigneDevis

User = get_user_model()
BASE = '/api/django/installations/chantiers/'
CONTRAT = (Path(__file__).parent / 'contract_samples'
           / 'installation_divergence_devis.json')


class DivergenceDevisTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht66', defaults={'nom': 'Co ACHT66'})
        self.user = User.objects.create_user(
            username='resp-acht66', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ACHT66', sku='PAN-ACHT66',
            prix_vente=Decimal('100'), quantite_stock=100)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='acht66@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ACHT66', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))
        devis_accepted.send(sender=None, devis=self.devis, user=self.user,
                            ancien_statut='envoye')
        self.chantier = Installation.objects.get(devis=self.devis)

    def _detail(self, inst):
        r = self.api.get(f'{BASE}{inst.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data['divergence_devis']

    def test_concordant_puis_diverge_puis_sans_devis(self):
        self.assertEqual(self._detail(self.chantier),
                         {'diverge': False, 'lignes': []})
        LigneDevis.objects.filter(pk=self.ligne.pk).update(
            quantite=Decimal('12'))
        div = self._detail(self.chantier)
        self.assertTrue(div['diverge'])
        self.assertEqual(len(div['lignes']), 1)
        ligne = div['lignes'][0]
        self.assertEqual(ligne['produit_id'], self.panneau.id)
        self.assertEqual(ligne['quantite_bom'], 10.0)
        self.assertEqual(ligne['quantite_devis'], 12.0)
        sans_devis = Installation.objects.create(
            company=self.company, reference='CH-ACHT66-SD')
        self.assertEqual(self._detail(sans_devis),
                         {'diverge': False, 'lignes': []})

    def test_forme_conforme_au_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        LigneDevis.objects.filter(pk=self.ligne.pk).update(
            quantite=Decimal('12'))
        div = self._detail(self.chantier)
        attendu = contrat['exemple']['divergence_devis']
        self.assertEqual(set(div), set(attendu))
        self.assertEqual(set(div['lignes'][0]), set(attendu['lignes'][0]))

    def test_liste_sans_la_cle(self):
        r = self.api.get(BASE)
        self.assertEqual(r.status_code, 200)
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertTrue(rows)
        self.assertNotIn('divergence_devis', rows[0])
