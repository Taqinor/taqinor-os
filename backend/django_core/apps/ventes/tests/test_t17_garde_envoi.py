"""QJR539 — la garde de remise T17 s'applique à TOUS les vrais envois, AVANT
tout effet de bord, et à la correction d'un envoyé ; l'approbation n'est pas
auto-attribuable.

Seuil société 10 %, remise 30 %, commercial « responsable » (non admin).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_t17_garde_envoi"
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis
from apps.ventes.services import RemiseNonApprouvee, mark_devis_sent
from authentication.models import Company

User = get_user_model()


class TestT17GardeEnvoi(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='T17 Co', slug='qjr539-co')
        CompanyProfile.objects.update_or_create(
            company=self.company,
            defaults={'discount_approval_threshold': Decimal('10')})
        self.resp = User.objects.create_user(
            username='qjr539_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.admin = User.objects.create_user(
            username='qjr539_admin', password='x', role_legacy='admin',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', telephone='0612345678')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', telephone='0612345678',
            email='alaoui@example.com')

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _devis(self, remise='30', statut='brouillon', ref='DEV-QJR539-1'):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            lead=self.lead, statut=statut, taux_tva=Decimal('20'),
            remise_globale=Decimal(remise))

    def _url(self, d, suffixe=''):
        return f'/api/django/ventes/devis/{d.id}/{suffixe}'

    def test_share_link_envoi_refuse_reste_brouillon(self):
        d = self._devis()
        r = self._api(self.resp).post(
            self._url(d, 'share-link/'), {'envoi': True}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('detail', r.json())
        d.refresh_from_db()
        self.assertEqual(d.statut, 'brouillon')
        self.assertIsNone(d.date_envoi)

    def test_share_link_sans_envoi_reste_permis(self):
        d = self._devis()
        r = self._api(self.resp).post(
            self._url(d, 'share-link/'), {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_envoyer_email_refuse_sans_jamais_appeler_send(self):
        d = self._devis()
        with patch('apps.ventes.email_service._send') as send:
            r = self._api(self.resp).post(
                self._url(d, 'envoyer-email/'), {}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        send.assert_not_called()
        d.refresh_from_db()
        self.assertEqual(d.statut, 'brouillon')

    def test_whatsapp_preview_refuse(self):
        d = self._devis()
        r = self._api(self.resp).post(
            self._url(d, 'whatsapp-preview/'), {}, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_whatsapp_commit_refuse(self):
        d = self._devis()
        r = self._api(self.resp).post(
            self._url(d, 'whatsapp/'), {}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        d.refresh_from_db()
        self.assertEqual(d.statut, 'brouillon')

    def test_patch_remise_approuvee_ignore(self):
        d = self._devis()
        r = self._api(self.resp).patch(
            self._url(d), {'remise_approuvee': True}, format='json')
        self.assertIn(r.status_code, (200, 400), r.content)
        d.refresh_from_db()
        self.assertFalse(d.remise_approuvee)
        self.assertIsNone(d.remise_approuvee_par)

    def test_admin_envoie_et_approuve_implicitement(self):
        d = self._devis()
        r = self._api(self.admin).post(
            self._url(d, 'share-link/'), {'envoi': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        d.refresh_from_db()
        self.assertEqual(d.statut, 'envoye')
        self.assertTrue(d.remise_approuvee)
        self.assertEqual(d.remise_approuvee_par, self.admin)

    def test_admin_apercu_n_ecrit_pas_l_approbation(self):
        d = self._devis()
        self._api(self.admin).post(
            self._url(d, 'whatsapp-preview/'), {}, format='json')
        d.refresh_from_db()
        self.assertFalse(d.remise_approuvee)

    def test_envoye_corrige_a_40_refuse(self):
        d = self._devis(remise='5', statut='envoye')
        r = self._api(self.resp).patch(
            self._url(d), {'remise_globale': '40'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('statut', r.json())
        d.refresh_from_db()
        self.assertEqual(d.remise_globale, Decimal('5'))

    def test_envoye_approuve_corrige_plus_profond_perd_l_approbation(self):
        d = self._devis(remise='20', statut='envoye')
        d.remise_approuvee = True
        d.remise_approuvee_par = self.admin
        d.save(update_fields=['remise_approuvee', 'remise_approuvee_par'])
        r = self._api(self.resp).patch(
            self._url(d), {'remise_globale': '40'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        d.refresh_from_db()
        # Le geste refusé ne change rien, approbation d'avant comprise.
        self.assertEqual(d.remise_globale, Decimal('20'))
        self.assertTrue(d.remise_approuvee)

    def test_envoye_corrige_sous_le_seuil_permis(self):
        d = self._devis(remise='5', statut='envoye')
        r = self._api(self.resp).patch(
            self._url(d), {'remise_globale': '8'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_filet_mark_devis_sent(self):
        d = self._devis()
        with self.assertRaises(RemiseNonApprouvee):
            mark_devis_sent(devis=d, user=self.resp)
        d.refresh_from_db()
        self.assertEqual(d.statut, 'brouillon')
