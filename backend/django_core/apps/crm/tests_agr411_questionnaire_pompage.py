"""AGR411 — lien « questionnaire client » : une section POMPAGE, et plus jamais
piscine/clim/toit pour un agriculteur.

Contrats partagés : ``contract_samples/questionnaire_lead.json``
(``exemple_agricole``, ``segment_agricole``, ``colonnes_ecrites.pompage``) et
``contract_samples/questionnaire_lien_mint.json`` (``exemple_agricole``).

Run :
    python manage.py test apps.crm.tests_agr411_questionnaire_pompage -v 2
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import questionnaire as quest
from apps.crm.models import Lead, QuestionnaireLien

User = get_user_model()

ICI = Path(__file__).resolve().parent / 'contract_samples'
CONTRAT = json.loads((ICI / 'questionnaire_lead.json').read_text(
    encoding='utf-8'))
CONTRAT_MINT = json.loads((ICI / 'questionnaire_lien_mint.json').read_text(
    encoding='utf-8'))
PUBLIC = '/api/django/crm/public/questionnaire/{}/'


class SectionPompageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AGR411 Co', slug='agr411-co')
        self.user = User.objects.create_user(
            username='agr411_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _mint(self, lead, corps=None):
        return self.api.post(
            f'/api/django/crm/leads/{lead.pk}/questionnaire-lien/',
            corps or {}, format='json')

    def _agricole(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Fellah', prenom='Brahim',
            type_installation='agricole', **extra)

    def test_contrat_colonnes_pompage_egale_la_fonction(self):
        self.assertEqual(CONTRAT['colonnes_ecrites']['pompage'],
                         list(quest.colonnes_ecrites('pompage')))
        self.assertEqual(CONTRAT['sections'], list(quest.SECTIONS))
        for orale in ('autorisation_prelevement', 'deja_beneficiaire_fda',
                      'decideur'):
            self.assertNotIn(orale, quest.CHAMPS_PAR_SECTION['pompage'])

    def test_envoi_agricole_sans_corps_coche_les_sections_attendues(self):
        lead = self._agricole()
        res = self._mint(lead)
        self.assertEqual(res.status_code, 200, res.data)
        coches = sorted(c for c, oui in res.data['questions'].items() if oui)
        self.assertEqual(coches, sorted(quest.SECTIONS_DEFAUT_AGRICOLE))
        attendu = CONTRAT_MINT['exemple_agricole']
        self.assertEqual(sorted(res.data['questions']),
                         sorted(attendu['questions']))
        self.assertEqual(sorted(res.data['manquantes']),
                         sorted(attendu['manquantes']))
        for refusee in quest.SECTIONS_REFUSEES_AGRICOLE:
            self.assertNotIn(refusee, res.data['questions'])

    def test_sections_maison_refusees_en_400_qui_nomme_la_section(self):
        lead = self._agricole()
        for section in quest.SECTIONS_REFUSEES_AGRICOLE:
            res = self._mint(lead, {'questions': {section: True}})
            self.assertEqual(res.status_code, 400, section)
            self.assertIn(section, res.data['detail'])

    def test_post_section_pompage_n_ecrit_que_ses_colonnes(self):
        lead = self._agricole(email='b@example.ma', facture_hiver=900,
                              culture='olivier')
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=lead, questions={'pompage': True})
        get = self.client.get(PUBLIC.format(lien.token))
        self.assertEqual(get.status_code, 200, get.content)
        self.assertEqual(sorted(get.json()),
                         sorted(CONTRAT['exemple_agricole']))
        self.assertEqual(get.json()['sections'], ['pompage'])
        res = self.client.post(
            PUBLIC.format(lien.token),
            data=json.dumps({'section': 'pompage', 'reponses': {
                'source_eau': 'puits', 'niveau_statique_m': 18,
                'mois_irrigation': [5, 6, 7], 'compteur_eau': False,
                'carburant_prix_unitaire_mad': 50,
                'facture_hiver': 4000, 'email': 'pirate@example.ma',
                'autorisation_prelevement': 'oui'}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 200, res.content)
        lead.refresh_from_db()
        self.assertEqual(lead.source_eau, 'puits')
        self.assertEqual(lead.niveau_statique_m, Decimal('18'))
        self.assertEqual(lead.niveau_statique_source, 'declare')
        self.assertEqual(lead.mois_irrigation, [5, 6, 7])
        self.assertIs(lead.compteur_eau, False)
        self.assertIsNotNone(lead.carburant_prix_declare_le)
        # Hors section : jamais écrit.
        self.assertEqual(lead.facture_hiver, Decimal('900'))
        self.assertEqual(lead.email, 'b@example.ma')
        self.assertIsNone(lead.autorisation_prelevement)
        # Une valeur existante non répondue n'est jamais vidée.
        self.assertEqual(lead.culture, 'olivier')

    def test_lien_residentiel_identique(self):
        lead = Lead.objects.create(company=self.company, nom='Maison')
        res = self._mint(lead)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(list(res.data['questions']),
                         list(quest.SECTIONS_HORS_POMPAGE))
        self.assertEqual(sorted(res.data['questions']),
                         sorted(CONTRAT_MINT['exemple']['questions']))
        for section in quest.SECTIONS_AGRICOLES_SEULES:
            self.assertNotIn(section, res.data['questions'])
            self.assertNotIn(section, res.data['manquantes'])
        res = self._mint(lead, {'questions': {'pompage': True}})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['detail'], 'Section inconnue : « pompage ».')
