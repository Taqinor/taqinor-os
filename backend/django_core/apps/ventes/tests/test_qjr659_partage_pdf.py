"""QJR659 (décision fondateur 01/10) — partager le PDF depuis la liste
(feuille de partage native résolue) vaut ENVOI, comme copier le lien
(D-QJR5-3). Le chemin passe par la garde de remise T17 (QJR539) AVANT tout
effet, puis par ``mark_devis_sent`` (seul chemin brouillon → envoyé) : aucun
lien client n'est minté, aucun statut n'est régressé.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr659_partage_pdf"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis, ShareLink
from authentication.models import Company

User = get_user_model()


class PartagePdfVautEnvoi(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QJR659', slug='qjr659-co')
        CompanyProfile.objects.update_or_create(
            company=self.company,
            defaults={'discount_approval_threshold': Decimal('10')})
        self.resp = User.objects.create_user(
            username='qjr659_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', telephone='0612345678',
            email='qjr659@example.com')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.resp)}')

    def _devis(self, statut='brouillon', remise='0', ref='DEV-QJR659-1'):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=statut, taux_tva=Decimal('20'),
            remise_globale=Decimal(remise))

    def _post(self, d):
        return self.api.post(
            f'/api/django/ventes/devis/{d.id}/pdf-partage/', {}, format='json')

    def test_brouillon_partage_marque_envoye_sans_lien_minte(self):
        d = self._devis()
        r = self._post(d)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['devis_statut'], 'envoye')
        d.refresh_from_db()
        self.assertEqual(d.statut, 'envoye')
        self.assertIsNotNone(d.date_envoi)
        self.assertFalse(ShareLink.objects.filter(devis=d).exists())

    def test_remise_non_approuvee_400_reste_brouillon(self):
        d = self._devis(remise='30')
        r = self._post(d)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('detail', r.json())
        d.refresh_from_db()
        self.assertEqual(d.statut, 'brouillon')
        self.assertIsNone(d.date_envoi)

    def test_envoye_idempotent_date_inchangee(self):
        d = self._devis()
        self._post(d)
        d.refresh_from_db()
        premiere = d.date_envoi
        r = self._post(d)
        self.assertEqual(r.status_code, 200, r.content)
        d.refresh_from_db()
        self.assertEqual(d.date_envoi, premiere)

    def test_accepte_jamais_regresse(self):
        d = self._devis(statut='accepte', ref='DEV-QJR659-ACC')
        r = self._post(d)
        self.assertEqual(r.status_code, 200, r.content)
        d.refresh_from_db()
        self.assertEqual(d.statut, 'accepte')
