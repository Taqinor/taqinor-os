"""CIQ323 — acceptation saisie dans l'ERP (devis papier signé) : l'action
``accepter`` enregistre aussi la raison sociale, la qualité et l'ICE d'un
C&I, à titre FACULTATIF (D-CIQ-11 ne les exige qu'en ligne). Corps du
contrat partagé ``acceptation_entreprise.json`` › ``exemple_erp``.
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, DevisSignature, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'acceptation_entreprise.json').read_text(encoding='utf-8'))
CORPS_ERP = CONTRAT['exemple_erp']['corps']
ENTREPRISE = dict(CONTRAT['exemple']['entreprise'])


class AccepterInterneEntreprise(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CIQ323 Co')
        self.user = User.objects.create_user(
            username='ciq323_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Hôtel Exemple', prenom='',
            email='ciq323@example.test', telephone='+212600000323')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.n = 0

    def _devis(self, mode='commercial'):
        from apps.stock.models import Produit
        self.n += 10
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-C4{self.n:03d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.user,
            mode_installation=mode)
        for i, (nom, qte) in enumerate((
                ('Panneau Canadien Solar 710W', '10'),
                ('Onduleur réseau Huawei 10kW Triphasé', '1'),
                ('Installation', '1'))):
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku=f'C323-{self.n}-{i}',
                prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'))
        return devis

    def _accepter(self, devis, corps):
        with patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            return self.api.post(
                f'/api/django/ventes/devis/{devis.id}/accepter/', corps,
                format='json')

    def test_avec_le_bloc_signature_complete(self):
        devis = self._devis('industriel')
        corps = dict(CORPS_ERP, entreprise=ENTREPRISE, option='')
        resp = self._accepter(devis, corps)
        self.assertEqual(resp.status_code, 200, resp.data)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.raison_sociale, ENTREPRISE['raison_sociale'])
        self.assertEqual(sig.signataire_qualite,
                         ENTREPRISE['signataire_qualite'])
        self.assertEqual(sig.ice_declare, ENTREPRISE['ice'])

    def test_bloc_facultatif_champs_vides_acceptes(self):
        devis = self._devis()
        resp = self._accepter(devis, dict(CORPS_ERP, option=''))
        self.assertEqual(resp.status_code, 200, resp.data)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.raison_sociale, CORPS_ERP['entreprise'][
            'raison_sociale'])
        self.assertEqual(sig.ice_declare, '')

    def test_sans_le_bloc_comportement_d_aujourd_hui(self):
        devis = self._devis()
        resp = self._accepter(devis, {'nom': 'Karim Exemple'})
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        sig = DevisSignature.objects.filter(devis=devis).first()
        if sig is not None:
            self.assertEqual((sig.raison_sociale, sig.signataire_qualite,
                              sig.ice_declare), ('', '', ''))

    def test_ice_mal_forme_400_qui_nomme_le_champ(self):
        devis = self._devis()
        resp = self._accepter(devis, dict(
            CORPS_ERP, option='', entreprise=dict(ENTREPRISE, ice='12AB')))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['champ'], 'entreprise.ice')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
