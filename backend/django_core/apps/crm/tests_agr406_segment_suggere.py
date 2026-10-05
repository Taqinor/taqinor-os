"""AGR406 — segment SUGGÉRÉ depuis la page d'arrivée et les mots-clés, jamais
écrit.

Contrats partagés : ``apps/crm/contract_samples/lead_pompage.json`` (bloc
``segment_suggere``) et ``panneau_appel.json`` (clé ``segment_suggere``).

Run :
    python manage.py test apps.crm.tests_agr406_segment_suggere -v 2
"""
import json
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import panneau_appel
from apps.crm.models import Lead
from apps.crm.segment_suggere import segment_suggere

User = get_user_model()
SECRET = 'test-secret-agr406'

_DOSSIER = Path(__file__).resolve().parent / 'contract_samples'
CONTRAT = json.loads((_DOSSIER / 'lead_pompage.json').read_text(
    encoding='utf-8'))
CONTRAT_PANNEAU = json.loads((_DOSSIER / 'panneau_appel.json').read_text(
    encoding='utf-8'))


def _lead(**kwargs):
    kwargs.setdefault('nom', 'P')
    return Lead(**kwargs)


class ModulePur(SimpleTestCase):
    def test_page_pompage_sans_mode_suggestion_agricole(self):
        for page in ('/pompage-solaire', '/en/pompage-solaire/',
                     '/ar/pompage-solaire'):
            bloc = segment_suggere(_lead(page=page))
            self.assertEqual(bloc['valeur'], 'agricole', page)
            self.assertIn(page.strip(), bloc['raison'])

    def test_lead_residentiel_note_puits_suggestion(self):
        bloc = segment_suggere(_lead(type_installation='residentiel',
                                     note='Il a un puits derrière la maison'))
        self.assertEqual(bloc['valeur'], 'agricole')
        self.assertIn('« puits »', bloc['raison'])

    def test_notes_de_visite_et_source_lues(self):
        self.assertEqual(segment_suggere(_lead(
            visite_notes='forage de 80 m'))['valeur'], 'agricole')
        self.assertEqual(segment_suggere(_lead(
            source='salon irrigation'))['valeur'], 'agricole')

    def test_equivalents_anglais_et_arabe(self):
        self.assertIsNotNone(segment_suggere(_lead(note='borehole pump')))
        self.assertIsNotNone(segment_suggere(_lead(note='عندي البئر')))

    def test_lead_agricole_null(self):
        self.assertIsNone(segment_suggere(_lead(
            type_installation='agricole', page='/pompage-solaire',
            note='puits')))

    def test_mot_entier_seulement(self):
        self.assertIsNone(segment_suggere(_lead(note='un discours pompeux')))
        self.assertIsNone(segment_suggere(_lead(note='la fermeture du toit')))

    def test_sans_signal_null(self):
        self.assertIsNone(segment_suggere(_lead(page='/devis/mon-toit',
                                                note='villa à Rabat')))

    def test_forme_conforme_au_contrat(self):
        attendu = CONTRAT['exemple_incoherent']['segment_suggere']
        bloc = segment_suggere(_lead(note='forage et irrigation'))
        self.assertEqual(set(bloc), set(attendu))
        self.assertEqual(bloc, attendu)

    def test_le_module_n_ecrit_rien(self):
        lead = _lead(page='/pompage-solaire')
        segment_suggere(lead)
        self.assertIsNone(lead.type_installation)


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class ServiSansEcriture(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AGR406 Co',
                                              slug='agr406-co')
        self.user = User.objects.create_user(
            username='agr406_u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_webhook_pompage_type_toujours_vide_et_suggestion_servie(self):
        res = self.client.post(
            reverse('website-lead-webhook'),
            data=json.dumps({
                'fullName': 'Agriculteur Test',
                'phoneE164': '+212661000406',
                'whatsappOptIn': True,
                'city': 'Agadir',
                'consent': True,
                'page': '/pompage-solaire',
            }),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertFalse(lead.type_installation)

        detail = self.api.get(f'/api/django/crm/leads/{lead.id}/').data
        self.assertEqual(detail['segment_suggere']['valeur'], 'agricole')
        lead.refresh_from_db()
        self.assertFalse(lead.type_installation)

    def test_la_liste_ne_sert_pas_la_suggestion(self):
        Lead.objects.create(company=self.company, nom='X',
                            page='/pompage-solaire')
        resp = self.api.get('/api/django/crm/leads/')
        for ligne in resp.data.get('results', resp.data):
            self.assertNotIn('segment_suggere', ligne)


class ServiAuPanneau(SimpleTestCase):
    def test_panneau_sert_segment_suggere(self):
        lead = _lead(page='/pompage-solaire')
        with mock.patch.object(panneau_appel, '_touche_en_cours',
                               return_value=None), \
                mock.patch.object(panneau_appel, 'fenetre_du_jour_servie',
                                  return_value=None), \
                mock.patch.object(panneau_appel, 'drapeaux_equipements',
                                  return_value=[]), \
                mock.patch.object(panneau_appel, 'profil_suppose_servi',
                                  return_value=False):
            data = panneau_appel.panneau_appel(lead)
        self.assertEqual(data['segment_suggere']['valeur'], 'agricole')
        for nom, exemple in CONTRAT_PANNEAU.items():
            if nom.startswith('exemple'):
                self.assertIn('segment_suggere', exemple, nom)
