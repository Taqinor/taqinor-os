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

    def test_b_telephone_vide_409(self):
        self._envoyer()
        Lead.objects.filter(pk=self.lead.pk).update(contact_secondaire_telephone='')
        resp = self._post()
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data, CONTRAT['exemple_400_telephone'])

    def test_c_devis_brouillon_409(self):
        # ERR-ENF11-FUZZ-CRM — un devis jamais envoyé est un ÉTAT : 409.
        resp = self._post()
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data, CONTRAT['exemple_400_devis'])

    def test_c2_devis_d_un_autre_lead_404(self):
        autre = Lead.objects.create(company=self.company, nom='Autre lead')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-AGR534-2', lead=autre,
            client=self.devis.client, statut='brouillon',
            taux_tva=Decimal('20.00'))
        resp = self._post(devis_id=devis.pk)
        self.assertEqual(resp.status_code, 404)
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

    def test_texte_personnalise_jamais_d_accolade_brute(self):
        """AMSG12 — un texte société avec tout le contexte de relance part
        rempli ; un placeholder sans valeur (ville) fait omettre sa phrase."""
        from apps.parametres.models_messages import MessageTemplate

        self._envoyer()
        Lead.objects.filter(pk=self.lead.pk).update(civilite='M.', ville='')
        MessageTemplate.objects.create(
            company=self.company, cle='resume_associe',
            corps_fr=('Bonjour, à la demande de {civilite} {nom}, voici le '
                      'résumé de la proposition {reference} : {lien}. '
                      'Ville : {ville}. — {conseiller}'))
        avant = LeadActivity.objects.filter(lead=self.lead).count()
        resp = self._post()
        self.assertEqual(resp.status_code, 200, resp.data)
        message = resp.data['message']
        self.assertIn('à la demande de M. Alaoui', message)
        self.assertIn('proposition DEV-AGR534-1 : ', message)
        self.assertIn('/proposition/', message)
        self.assertNotIn('Ville :', message)
        self.assertNotIn('{', message)
        self.assertNotIn('}', message)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), avant + 1)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'envoye')

    def test_lead_oppose_409_sans_lien(self):
        """ACVI104 (D-ACVI-7) — la proposition d'un opposé ne sort plus, même
        vers l'associé : 409 nommé, aucun lien, aucune ligne d'historique."""
        self._envoyer()
        Lead.objects.filter(pk=self.lead.pk).update(ne_plus_contacter=True)
        avant = LeadActivity.objects.filter(lead=self.lead).count()
        resp = self._post()
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(str(resp.data['detail']), 'Message refusé : ne plus contacter.')
        self.assertNotIn('wa_url', resp.data)
        self.assertEqual(LeadActivity.objects.filter(lead=self.lead).count(), avant)

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

    def test_fuzz_1176_corps_tableau_ou_langue_non_texte_400(self):
        """api-fuzz PR #1176 — corps ``[null, null]`` (``.get`` levait : 500)
        puis ``langue`` non texte (``.strip()`` levait) : 400, rien journalisé."""
        self._envoyer()
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/resume-associe/',
            [None, None], format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self._post(langue=[None, None])
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('langue', resp.data)
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, body__startswith='Résumé transmis').exists())

    def test_textes_sans_chiffre_ni_prenom_code_en_dur(self):
        for texte in (MESSAGE_TEMPLATE_DEFAULTS['resume_associe'],
                      MESSAGE_TEMPLATE_DEFAULTS_DARIJA['resume_associe']):
            self.assertIsNone(re.search(r'\d', texte))
            for nom in ('Meryem', 'Reda', 'TAQINOR', 'Taqinor'):
                self.assertNotIn(nom, texte)
            for ph in ('{conseiller}', '{marque}', '{lien}'):
                self.assertIn(ph, texte)
