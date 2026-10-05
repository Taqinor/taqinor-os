"""CIQ412 — lien « questionnaire client » d'un lead PRO : sections réseau,
activité, site, société — et plus jamais une question résidentielle.

Contrats partagés : ``questionnaire_lead.json`` (``exemple_pro``,
``segment_pro``) et ``questionnaire_lien_mint.json`` (``exemple_pro``), CIQ400.

Écart assumé : le GPS reste une section du lead pro (« plus gps et contact
s'ils manquent », texte de la tâche) ; ``exemple_pro`` du contrat ne le
montre pas. Les clés servies sont un SUR-ensemble de celles du contrat.

Run :
    python manage.py test apps.crm.tests_ciq412_questionnaire_pro -v 2
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


class QuestionnairePro(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='CIQ412 Co', slug='ciq412-co')
        self.user = User.objects.create_user(
            username='ciq412_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _pro(self, **extra):
        extra.setdefault('type_installation', 'commercial')
        return Lead.objects.create(
            company=self.company, nom='Hôtel', prenom='Karim', **extra)

    def _mint(self, lead, corps=None):
        return self.api.post(
            f'/api/django/crm/leads/{lead.pk}/questionnaire-lien/',
            corps or {}, format='json')

    def test_contrat_sections_et_colonnes(self):
        self.assertEqual(CONTRAT['sections'], list(quest.SECTIONS))
        for section, colonnes in CONTRAT['exemple_pro']['champs'].items():
            if section == 'contact':
                continue  # écart documenté : contact garde ses colonnes
            self.assertEqual(list(quest.CHAMPS_PAR_SECTION[section]),
                             colonnes, section)
        self.assertEqual(
            set(CONTRAT['segment_pro']['sections_pro']) - {'contact'},
            set(quest.SECTIONS_PRO_SEULES))

    def test_envoi_pro_coche_les_sections_pro_manquantes(self):
        lead = self._pro(tension_raccordement='bt', tension_source='declare',
                         categorie_commerciale='hotel',
                         surface_toiture_m2=Decimal('650'),
                         societe='Hôtel Exemple SARL',
                         email='h@example.ma', ville='Marrakech',
                         adresse='Route X')
        res = self._mint(lead)
        self.assertEqual(res.status_code, 200, res.data)
        questions = res.data['questions']
        self.assertTrue(set(CONTRAT_MINT['exemple_pro']['questions'])
                        <= set(questions))
        for residentielle in ('occupation', 'equipements', 'energie',
                              'toiture', 'photo_facture'):
            self.assertNotIn(residentielle, questions)
        attendu = CONTRAT_MINT['exemple_pro']['manquantes']
        for section, valeur in attendu.items():
            self.assertEqual(res.data['manquantes'][section], valeur, section)
        self.assertTrue(questions['reseau'])
        self.assertFalse(questions['site'])

    def test_section_residentielle_refusee_en_400_qui_la_nomme(self):
        lead = self._pro()
        for section in CONTRAT['segment_pro']['refusees_400']:
            res = self._mint(lead, {'questions': {section: True}})
            self.assertEqual(res.status_code, 400, section)
            self.assertIn(section, res.data['detail'])

    def test_post_reseau_n_ecrit_que_ses_colonnes_jamais_de_vide(self):
        lead = self._pro(email='h@example.ma', compteur_puissance_kva=60,
                         facture_hiver=Decimal('5000'))
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=lead,
            questions={s: s == 'reseau' for s in quest.sections_du_lead(lead)})
        get = self.client.get(PUBLIC.format(lien.token))
        self.assertEqual(get.status_code, 200, get.content)
        self.assertEqual(get.json()['sections'], ['reseau'])
        res = self.client.post(
            PUBLIC.format(lien.token),
            data=json.dumps({'section': 'reseau', 'reponses': {
                'tension_raccordement': 'mt',
                'compteur_puissance_kva': None,
                'releve_conso': {'mois': [
                    {'mois': '2026-08', 'kwh': 40000, 'kwh_pointe': 6000}],
                    'source': 'ocr_confirme'},
                'facture_hiver': 1, 'email': 'pirate@example.ma',
                'decideur': 'seul'}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 200, res.content)
        lead.refresh_from_db()
        self.assertEqual(lead.tension_raccordement, 'mt')
        self.assertEqual(lead.tension_source, 'declare')
        self.assertEqual(lead.releve_conso['source'], 'declare')
        self.assertEqual(lead.releve_conso['mois'][0]['kwh_pointe'],
                         '6000.00')
        # Une valeur existante non répondue n'est jamais vidée.
        self.assertEqual(lead.compteur_puissance_kva, Decimal('60'))
        # Hors section : jamais écrit.
        self.assertEqual(lead.facture_hiver, Decimal('5000'))
        self.assertEqual(lead.email, 'h@example.ma')
        self.assertIsNone(lead.decideur)

    def test_post_occupation_pour_un_pro_refuse(self):
        lead = self._pro()
        lien = QuestionnaireLien.objects.create(
            company=self.company, lead=lead, questions={})
        res = self.client.post(
            PUBLIC.format(lien.token),
            data=json.dumps({'section': 'occupation',
                             'reponses': {'occupation_jour': 'present'}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 400, res.content)
        lead.refresh_from_db()
        self.assertIsNone(lead.occupation_jour)

    def test_activite_ne_montre_que_le_segment(self):
        commercial = self._pro()
        industriel = self._pro(type_installation='industriel')
        carte_c = quest.champs_a_poser(commercial, ['activite'])['activite']
        carte_i = quest.champs_a_poser(industriel, ['activite'])['activite']
        self.assertIn('categorie_commerciale', carte_c)
        self.assertNotIn('secteur_industriel', carte_c)
        self.assertIn('secteur_industriel', carte_i)
        self.assertNotIn('categorie_commerciale', carte_i)

    def test_lien_residentiel_identique(self):
        lead = Lead.objects.create(company=self.company, nom='Maison')
        res = self._mint(lead)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(list(res.data['questions']),
                         list(quest.SECTIONS_HORS_POMPAGE))
        self.assertEqual(sorted(res.data['questions']),
                         sorted(CONTRAT_MINT['exemple']['questions']))

    def test_agricole_inchange(self):
        lead = Lead.objects.create(company=self.company, nom='Ferme',
                                   type_installation='agricole')
        res = self._mint(lead)
        self.assertEqual(sorted(res.data['questions']),
                         sorted(CONTRAT_MINT['exemple_agricole']['questions']))
