"""AGR534 — « envoyer le résumé à un associé » : geste MANUEL, avec l'accord
du client (contrat partagé ``lead_resume_associe.json``, AGR504).

Le serveur PRÉPARE le lien WhatsApp vers le contact secondaire avec le lien
de la proposition déjà envoyée ; il n'envoie rien, ne touche ni statut, ni
date d'envoi, ni cadence (CAD144, règle #4).

Run :
    python manage.py test apps.crm.tests_agr_resume_associe -v 2
"""
import json
import re
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead, LeadActivity
from apps.parametres.models import CompanyProfile
from apps.parametres.models_messages import (
    MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
)
from apps.roles.models import Role
from apps.ventes.domain.envoi import mark_devis_sent
from apps.ventes.models import Devis

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_resume_associe.json').read_text(encoding='utf-8'))


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ResumeAssocieTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AGR534', slug='agr534')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.user = User.objects.create_user(
            username='agr534-resp', password='x', role_legacy='responsable',
            company=self.company, first_name='Nadia')
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Driss', owner=self.user,
            telephone='+212661000534', type_installation='agricole',
            contact_secondaire_nom='Hassan (associé)',
            contact_secondaire_telephone='0661223344')
        client = Client.objects.create(
            company=self.company, nom='Alaoui', email='agr534@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-AGR534-1', client=client,
            lead=self.lead, statut='brouillon', taux_tva=Decimal('20.00'))
        self.api = _api(self.user)

    def _post(self, **corps):
        corps.setdefault('devis_id', self.devis.pk)
        corps.setdefault('accord_client', True)
        return self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/resume-associe/', corps,
            format='json')

    def _envoyer(self):
        mark_devis_sent(devis=self.devis, user=self.user)
        self.devis.refresh_from_db()

    def test_a_sans_accord_400_nommant_accord_client(self):
        self._envoyer()
        resp = self._post(accord_client=False)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, CONTRAT['exemple_400_accord'])

    def test_b_telephone_vide_400(self):
        self._envoyer()
        Lead.objects.filter(pk=self.lead.pk).update(contact_secondaire_telephone='')
        resp = self._post()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, CONTRAT['exemple_400_telephone'])

    def test_c_devis_brouillon_400(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, CONTRAT['exemple_400_devis'])

    def test_d_cas_valide_wa_url_historique_devis_inchange(self):
        self._envoyer()
        avant = (self.devis.statut, getattr(self.devis, 'date_envoi', None))
        etapes_avant = self.lead.relance_etapes.count()
        resp = self._post()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(CONTRAT['exemple']))
        self.assertTrue(resp.data['wa_url'].startswith('https://wa.me/212661223344'))
        self.assertEqual(resp.data['phone'], '0661223344')
        self.assertIn('/proposition/', resp.data['message'])
        self.assertIn('Nadia', resp.data['message'])
        self.assertNotIn('{', resp.data['message'])
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            body__startswith='Résumé transmis à Hassan (associé) — accord du client noté').exists())
        self.devis.refresh_from_db()
        self.assertEqual((self.devis.statut, getattr(self.devis, 'date_envoi', None)), avant)
        self.assertEqual(self.lead.relance_etapes.count(), etapes_avant)

    def test_403_sans_client_pii_voir(self):
        self._envoyer()
        role = Role.objects.create(company=self.company, nom='Lecteur AGR534',
                                   permissions=['crm_voir'])
        lecteur = User.objects.create_user(
            username='agr534-lecteur', password='x', role=role,
            company=self.company)
        resp = _api(lecteur).post(
            f'/api/django/crm/leads/{self.lead.pk}/resume-associe/',
            {'devis_id': self.devis.pk, 'accord_client': True}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_textes_sans_chiffre_ni_prenom_code_en_dur(self):
        for texte in (MESSAGE_TEMPLATE_DEFAULTS['resume_associe'],
                      MESSAGE_TEMPLATE_DEFAULTS_DARIJA['resume_associe']):
            self.assertIsNone(re.search(r'\d', texte))
            for nom in ('Meryem', 'Reda', 'TAQINOR', 'Taqinor'):
                self.assertNotIn(nom, texte)
            for ph in ('{conseiller}', '{marque}', '{lien}'):
                self.assertIn(ph, texte)
