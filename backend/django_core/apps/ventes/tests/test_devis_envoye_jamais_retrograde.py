"""QJR515 (Groupe QJR5, D-QJR5-1) — un devis ENVOYÉ ne repasse jamais en
brouillon par un PATCH : il se corrige SUR PLACE.

QJR541 — ``statut`` est en LECTURE SEULE dans ``DevisWriteSerializer`` : un
PATCH ``statut: brouillon`` sur un envoyé est IGNORÉ (200, reste envoyé) ; un
PATCH ``statut: envoye`` sur un brouillon aussi (reste brouillon — l'envoi a ses
portes dédiées). Un PATCH sans ``statut`` sur un envoyé passe.

PACT10 — le test AFFIRME l'exemple committé
``apps/ventes/contract_samples/devis_modifiabilite.json`` : un envoyé actif y
est déclaré modifiable, un brouillon aussi.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'devis_modifiabilite.json')


class TestDevisEnvoyeJamaisRetrograde(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        cls.company = Company.objects.create(
            nom='QJR515 Co', slug='qjr515-co')
        cls.user = User.objects.create_user(
            username='qjr515_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client', prenom='QJR515',
            email='qjr515@example.com', telephone='+212600005150')

    def setUp(self):
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, num, statut):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{5150 + num}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))

    def _patch(self, devis, corps):
        return self.api.patch(
            f'/api/django/ventes/devis/{devis.id}/', corps, format='json')

    def test_contrat_declare_envoye_et_brouillon_modifiables(self):
        env = self.contrat['exemple_envoye']
        self.assertEqual(env['statut'], Devis.Statut.ENVOYE)
        self.assertTrue(env['modifiable'])
        brouillon = self.contrat['exemple_brouillon']
        self.assertEqual(brouillon['statut'], Devis.Statut.BROUILLON)
        self.assertTrue(brouillon['modifiable'])

    def test_envoye_vers_brouillon_ignore(self):
        devis = self._devis(1, Devis.Statut.ENVOYE)
        r = self._patch(devis, {'statut': 'brouillon'})
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_brouillon_vers_envoye_ignore(self):
        devis = self._devis(2, Devis.Statut.BROUILLON)
        r = self._patch(devis, {'statut': 'envoye'})
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_patch_note_sur_envoye_garde_le_statut(self):
        devis = self._devis(3, Devis.Statut.ENVOYE)
        r = self._patch(devis, {'note': 'corrigé'})
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.note, 'corrigé')
