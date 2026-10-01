"""
QJR566 (Groupe QJR5) — la ligne devis de la fiche lead porte `corrige_le` :
la date de la dernière correction après envoi (marqueur
``etude_params.resync_apres_envoi``), null sinon. Le cockpit dit « lu le X —
avant la correction du Y » au lieu d'un « lu le » trompeur.

Contrat partagé : ``apps/crm/contract_samples/lead_devis_ligne.json`` (QJR500).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_lead_devis_corrige_le"
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_devis_ligne.json').read_text(encoding='utf-8'))


class TestLeadDevisCorrigeLe(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR566 Co', slug='qjr566-co')
        self.user = User.objects.create_user(
            username='qjr566_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR566',
            email='qjr566@example.com')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='QJR566',
            email='qjr566-lead@example.com', telephone='0612345566')

    def _devis(self, reference, statut, etude_params=None):
        return Devis.objects.create(
            company=self.company, reference=reference, lead=self.lead,
            client=self.client_obj, statut=statut, taux_tva=20,
            remise_globale=0, created_by=self.user,
            etude_params=etude_params or {})

    def _lignes(self):
        r = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        return {row['id']: row for row in r.json()['devis']}

    def test_envoye_corrige_expose_corrige_le(self):
        date = CONTRAT['exemple']['devis'][0]['corrige_le']
        d = self._devis('DEV-QJR566-1', 'envoye',
                        {'resync_apres_envoi': {'date': date}})
        self.assertEqual(self._lignes()[d.id]['corrige_le'], date)

    def test_brouillon_corrige_le_null(self):
        d = self._devis('DEV-QJR566-2', 'brouillon')
        self.assertIsNone(self._lignes()[d.id]['corrige_le'])

    def test_ligne_porte_toutes_les_cles_du_contrat(self):
        d = self._devis('DEV-QJR566-3', 'envoye')
        attendu = set(CONTRAT['exemple']['devis'][0])
        self.assertTrue(attendu <= set(self._lignes()[d.id]))
