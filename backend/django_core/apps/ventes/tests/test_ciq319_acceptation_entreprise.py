"""CIQ319 — acceptation entreprise côté serveur : raison sociale, qualité du
signataire et ICE enregistrés AVEC la signature ; ICE exigé en ligne pour un
devis commercial ou industriel (D-CIQ-11, contrat ``acceptation_entreprise.json``).

Chemin RÉEL : POST public ``/api/django/public/proposal/<token>/accept/`` ;
le PDF signé (WeasyPrint + MinIO) est neutralisé comme dans
``test_nplus1_acceptation_publique``. Aucun statut nouveau (règle #4).
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, DevisSignature, LigneDevis, ShareLink

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'acceptation_entreprise.json').read_text(encoding='utf-8'))
ENTREPRISE = dict(CONTRAT['exemple']['entreprise'])


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class AcceptationEntreprise(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CIQ319 Co')
        self.seller = User.objects.create_user(
            username='ciq319_seller', password='x', role_legacy='commercial',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Hôtel Exemple', prenom='',
            email='ciq319@example.test', telephone='+212600000319')
        self.api = APIClient()
        self.n = 0

    def _devis(self, mode='commercial'):
        from apps.stock.models import Produit
        self.n += 10
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-C3{self.n:03d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.seller,
            mode_installation=mode)
        for i, (nom, qte) in enumerate((
                ('Panneau Canadien Solar 710W', '10'),
                ('Onduleur réseau Huawei 10kW Triphasé', '1'),
                ('Installation', '1'))):
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku=f'C319-{self.n}-{i}',
                prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'))
        return devis

    def _post(self, devis, entreprise=None):
        link = ShareLink.for_devis(devis)
        corps = {'nom': 'Karim Exemple', 'consent_esign': True}
        if entreprise is not None:
            corps['entreprise'] = entreprise
        with patch('apps.ventes.domain.cycle_vie._store_signed_pdf'):
            return self.api.post(
                f'/api/django/public/proposal/{link.token}/accept/',
                corps, format='json')

    def test_ci_sans_ice_400_et_devis_non_accepte(self):
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                devis = self._devis(mode)
                resp = self._post(devis, dict(ENTREPRISE, ice=''))
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertEqual(resp.data['champ'], 'entreprise.ice')
                devis.refresh_from_db()
                self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
                self.assertFalse(
                    DevisSignature.objects.filter(devis=devis).exists())

    def test_ci_bloc_absent_nomme_le_premier_champ(self):
        resp = self._post(self._devis())
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['champ'], 'entreprise.raison_sociale')

    def test_ice_mal_forme_400(self):
        resp = self._post(self._devis(), dict(ENTREPRISE, ice='12AB'))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['champ'], 'entreprise.ice')

    def test_ci_trois_champs_signature_et_rendu(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis('industriel')
        resp = self._post(devis, ENTREPRISE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], Devis.Statut.ACCEPTE)
        self.assertEqual(resp.data['entreprise'], ENTREPRISE)
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual(sig.raison_sociale, ENTREPRISE['raison_sociale'])
        self.assertEqual(sig.signataire_qualite,
                         ENTREPRISE['signataire_qualite'])
        self.assertEqual(sig.ice_declare, ENTREPRISE['ice'])
        devis.refresh_from_db()
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        attendu = CONTRAT['signature_entreprise']['exemple']
        self.assertEqual(set(data['signature_entreprise']), set(attendu))
        self.assertEqual(data['signature_entreprise']['ice'],
                         ENTREPRISE['ice'])
        self.assertEqual(data['signature_entreprise']['signataire_nom'],
                         'Karim Exemple')

    def test_texte_echappe_une_seule_fois(self):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, echapper_textes_client,
        )
        devis = self._devis()
        self._post(devis, dict(ENTREPRISE, raison_sociale='A & <B> SARL'))
        devis.refresh_from_db()
        rendu = echapper_textes_client(
            build_quote_data(devis, {'pdf_mode': 'full'}))
        self.assertEqual(rendu['signature_entreprise']['raison_sociale'],
                         'A &amp; &lt;B&gt; SARL')

    def test_ice_different_deja_present_divergence(self):
        from apps.ventes.domain.cycle_vie import divergence_ice
        self.client_obj.ice = '111111111111111'
        self.client_obj.save(update_fields=['ice'])
        devis = self._devis()
        self.assertEqual(self._post(devis, ENTREPRISE).status_code, 200)
        self.client_obj.refresh_from_db()
        # Jamais écrasé.
        self.assertEqual(self.client_obj.ice, '111111111111111')
        self.assertTrue(divergence_ice(devis, ENTREPRISE['ice']))
        self.assertFalse(divergence_ice(devis, '111111111111111'))

    def test_residentiel_inchange(self):
        devis = self._devis('residentiel')
        resp = self._post(devis)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['entreprise'])
        sig = DevisSignature.objects.get(devis=devis)
        self.assertEqual((sig.raison_sociale, sig.ice_declare), ('', ''))
        # Un bloc envoyé hors C&I est IGNORÉ (ni erreur, ni écriture).
        devis2 = self._devis('residentiel')
        resp2 = self._post(devis2, dict(ENTREPRISE, ice='bad'))
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(
            DevisSignature.objects.get(devis=devis2).ice_declare, '')

    def test_double_envoi_idempotent(self):
        devis = self._devis()
        self.assertEqual(self._post(devis, ENTREPRISE).status_code, 200)
        autre = dict(ENTREPRISE, raison_sociale='Autre SARL')
        resp = self._post(devis, autre)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(DevisSignature.objects.filter(devis=devis).count(), 1)
        self.assertEqual(
            DevisSignature.objects.get(devis=devis).raison_sociale,
            ENTREPRISE['raison_sociale'])
        self.assertEqual(resp.data['entreprise'], ENTREPRISE)
