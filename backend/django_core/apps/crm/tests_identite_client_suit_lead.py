"""
QJR590 (Groupe QJR5) — corriger le nom, le téléphone, l'e-mail ou l'adresse
d'un lead met à jour la fiche Client imprimée, tant que personne ne l'a
modifiée à la main.

Contrat partagé : ``apps/crm/contract_samples/lead_client_ecart.json``
(QJR506) — GET lead {client, client_nom, client_ecart} ; POST
…/synchroniser-client/ -> 200 {client_ecart, champs_mis_a_jour} | 400 {detail}.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_identite_client_suit_lead"
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead, LeadActivity
from apps.crm.services import resolve_client_for_lead
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_client_ecart.json').read_text(encoding='utf-8'))


class TestIdentiteClientSuitLead(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR590 Co', slug='qjr590-co')
        self.user = User.objects.create_user(
            username='qjr590_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Amina',
            email='amina@example.com', telephone='0612345590',
            adresse='12 rue X', ville='Settat')
        self.client_obj = resolve_client_for_lead(self.lead)
        self.lead.refresh_from_db()

    def _url(self, suffixe=''):
        return f'/api/django/crm/leads/{self.lead.id}/{suffixe}'

    def _patch(self, **corps):
        return self.api.patch(self._url(), corps, format='json')

    def test_get_lead_porte_les_cles_du_contrat(self):
        r = self.api.get(self._url())
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(set(CONTRAT['exemple_get_lead']) <= set(r.json()))
        self.assertEqual(r.json()['client_ecart'], [])

    def test_patch_nom_suit_sur_le_client_et_le_pdf(self):
        r = self._patch(nom='Benhali')
        self.assertEqual(r.status_code, 200, r.content)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.nom, 'Benhali')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR590-1',
            client=self.client_obj, lead=self.lead, statut='brouillon')
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertIn('Benhali', data['client_name'])

    def test_adresse_et_ville_recomposees(self):
        self._patch(ville='Berrechid')
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.adresse, '12 rue X, Berrechid')

    def test_client_modifie_a_la_main_reste_intact(self):
        Client.objects.filter(pk=self.client_obj.pk).update(nom='Ben Ali SARL')
        r = self._patch(nom='Benhali')
        self.assertEqual(r.status_code, 200, r.content)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.nom, 'Ben Ali SARL')
        self.assertEqual(r.json()['client_ecart'], ['nom'])

    def test_email_deja_pris_200_sans_propagation_avec_message(self):
        Client.objects.create(
            company=self.company, nom='Autre', email='pris@example.com')
        r = self._patch(email='pris@example.com', nom='Benhali')
        self.assertEqual(r.status_code, 200, r.content)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.email, 'amina@example.com')
        self.assertEqual(self.client_obj.nom, 'Benhali')
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, body__icontains='déjà utilisé').exists())

    def test_client_anonymise_jamais_touche(self):
        Client.objects.filter(pk=self.client_obj.pk).update(is_anonymized=True)
        self._patch(nom='Benhali')
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.nom, 'Benali')

    def test_devis_envoye_recoit_la_trace_de_correction(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR590-2',
            client=self.client_obj, lead=self.lead, statut='envoye')
        self._patch(telephone='0699999999')
        devis.refresh_from_db()
        self.assertIn('resync_apres_envoi', devis.etude_params or {})

    def test_action_synchroniser_client(self):
        Client.objects.filter(pk=self.client_obj.pk).update(
            telephone='0600000000')
        r = self.api.post(self._url('synchroniser-client/'), {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(set(r.json()), set(CONTRAT['exemple']))
        self.assertEqual(r.json()['client_ecart'], [])
        self.assertEqual(r.json()['champs_mis_a_jour'], ['telephone'])

    def test_action_sans_client_400(self):
        seul = Lead.objects.create(company=self.company, nom='Seul')
        r = self.api.post(
            f'/api/django/crm/leads/{seul.id}/synchroniser-client/', {},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()), set(CONTRAT['exemple_400']))
