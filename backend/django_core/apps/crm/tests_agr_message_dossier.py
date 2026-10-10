"""AGR526 — la tâche du playbook propose son texte, et ``message-visite`` rend
``dossier_fda`` / ``dossier_8221`` au SEUL lead dont le playbook de segment
confirme la clé (``cle_message_segment``).

Contrats partagés : ``lead_playbook.json`` (AGR507, ``cle_message``) et
``lead_message_visite.json`` (forme inchangée).

Run :
    python manage.py test apps.crm.tests_agr_message_dossier -v 2
"""
import json
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead, LeadActivity
from apps.crm.services import generer_playbook_progress
from apps.crm.cadence_messages import seed_playbooks_segment
from apps.parametres.models import CompanyProfile

User = get_user_model()

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'
PLAYBOOK = json.loads((CONTRATS / 'lead_playbook.json').read_text(encoding='utf-8'))
MESSAGE = json.loads((CONTRATS / 'lead_message_visite.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'agr526'

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x', role_legacy='responsable',
            company=self.company, first_name='Nadia')
        seed_playbooks_segment(self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _lead(self, segment, **extra):
        lead = Lead.objects.create(
            company=self.company, nom='Fellah', prenom='Aziz', owner=self.acteur,
            stage=stages.CONTACTED, type_installation=segment,
            telephone='+212661000526', **extra)
        generer_playbook_progress(lead, stages.CONTACTED)
        return lead

    def _playbook(self, lead):
        resp = self.api.get(f'/api/django/crm/leads/{lead.id}/playbook/')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    def _message(self, lead, cle):
        return self.api.get(f'/api/django/crm/leads/{lead.id}/message-visite/',
                            {'cle': cle})


class PlaybookCleMessage(_Base):
    slug = 'agr526-pb'

    def test_a_agricole_butane_cle_dossier_fda(self):
        lignes = self._playbook(self._lead('agricole', pompe_alim_actuelle='butane'))
        self.assertEqual([ligne['cle_message'] for ligne in lignes], ['dossier_fda'])
        self.assertEqual(set(lignes[0]), set(PLAYBOOK['exemple']))

    def test_c_residentiel_cle_null(self):
        lead = self._lead('residentiel')
        for ligne in self._playbook(lead):
            self.assertIsNone(ligne['cle_message'])

    def test_industriel_cle_dossier_8221(self):
        # CIQ517 — le 82-21 vise un site MT (ou régularisation / revente).
        lignes = self._playbook(
            self._lead('industriel', tension_raccordement='mt'))
        self.assertEqual([ligne['cle_message'] for ligne in lignes], ['dossier_8221'])


class MessageVisiteDossier(_Base):
    slug = 'agr526-msg'

    def test_a_dossier_fda_rendu_fr_et_darija_sans_chiffre(self):
        lead = self._lead('agricole', pompe_alim_actuelle='butane')
        resp = self._message(lead, 'dossier_fda')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data), set(MESSAGE['exemple']))
        for champ in ('corps_fr', 'corps_darija'):
            self.assertTrue(resp.data[champ].strip(), champ)
            self.assertNotIn('{', resp.data[champ])
            self.assertIsNone(re.search(r'\d', resp.data[champ]), champ)
        self.assertTrue(resp.data['wa_url_fr'].startswith('https://wa.me/212'))

    def test_b_diesel_400_nommant_cle(self):
        lead = self._lead('agricole', pompe_alim_actuelle='diesel')
        resp = self._message(lead, 'dossier_fda')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cle', resp.data)
        self.assertIn('dossier_fda', resp.data['cle'][0])

    def test_residentiel_ne_recoit_aucun_dossier(self):
        lead = self._lead('residentiel')
        for cle in ('dossier_fda', 'dossier_8221'):
            self.assertEqual(self._message(lead, cle).status_code, 400, cle)

    def test_cle_croisee_refusee(self):
        lead = self._lead('agricole', pompe_alim_actuelle='butane')
        self.assertEqual(self._message(lead, 'dossier_8221').status_code, 400)

    def test_ouvert_journalise_et_refuse_hors_segment(self):
        lead = self._lead('agricole', pompe_alim_actuelle='butane')
        resp = self.api.post(
            f'/api/django/crm/leads/{lead.id}/message-visite/ouvert/',
            {'cle': 'dossier_fda', 'langue': 'darija'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.WHATSAPP).latest('pk')
        self.assertIn('dossier de subvention FDA', ligne.body)
        diesel = self._lead('agricole', pompe_alim_actuelle='diesel')
        resp = self.api.post(
            f'/api/django/crm/leads/{diesel.id}/message-visite/ouvert/',
            {'cle': 'dossier_fda', 'langue': 'fr'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cle', resp.data['erreurs'])

    def test_les_cles_de_visite_restent_inchangees(self):
        lead = self._lead('residentiel')
        resp = self._message(lead, 'apres_visite')
        self.assertEqual(resp.data['cle'], MESSAGE['exemple_erreur_cle']['cle'])
