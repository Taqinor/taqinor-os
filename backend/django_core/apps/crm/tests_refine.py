"""
Affinages de la feature Leads (2026-06) :

  1. normalisation du téléphone/WhatsApp côté serveur (forme canonique
     '212XXXXXXXXX') via le sérialiseur — saisie libre acceptée, jamais rejetée ;
  2. contrôle PRÉ-CRÉATION (et édition) des doublons par téléphone/email
     (GET /crm/leads/check-duplicates/) — borné à la société ;
  3. nouveaux champs suivis dans l'Historique (chatter) : régularisation 82-21,
     notes de visite, tranche ONEE, notes d'ombrage, structure, étages,
     inclinaison, GPS, société.

Run:
    python manage.py test apps.crm.tests_refine -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead, LeadActivity

User = get_user_model()


def make_company(slug='refine-co', nom='Refine Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestPhoneNormalisationOnSave(TestCase):
    """Le téléphone/WhatsApp sont normalisés côté serveur à l'enregistrement."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='refine_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)

    def test_create_normalizes_phone_and_whatsapp(self):
        resp = self.api.post(
            '/api/django/crm/leads/',
            {'nom': 'Bennani', 'telephone': '06 12-34 56 78',
             'whatsapp': '+212 612 345 679'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(id=resp.data['id'])
        self.assertEqual(lead.telephone, '212612345678')
        self.assertEqual(lead.whatsapp, '212612345679')
        # La forme normalisée est reflétée dans la réponse (le formulaire la
        # ré-affiche telle quelle).
        self.assertEqual(resp.data['telephone'], '212612345678')
        self.assertEqual(resp.data['whatsapp'], '212612345679')

    def test_variants_store_same_canonical_form(self):
        for raw in ('+212612345678', '0612345678', '00212612345678',
                    '06 12 34 56 78'):
            lead = Lead.objects.create(company=self.company, nom='X')
            r = self.api.patch(
                f'/api/django/crm/leads/{lead.id}/',
                {'telephone': raw}, format='json')
            self.assertEqual(r.status_code, 200, r.data)
            lead.refresh_from_db()
            self.assertEqual(lead.telephone, '212612345678')

    def test_blank_phone_stays_blank(self):
        lead = Lead.objects.create(company=self.company, nom='Vide')
        r = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'telephone': ''}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        lead.refresh_from_db()
        self.assertIn(lead.telephone, (None, ''))


class TestPreCreateDuplicateCheck(TestCase):
    """GET /crm/leads/check-duplicates/ — avertissement pré-création/édition."""

    def setUp(self):
        self.company = make_company('refine-dup-co', 'Refine Dup Co')
        self.user = User.objects.create_user(
            username='refine_dup', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)
        # Lead existant avec téléphone canonique + email.
        self.existing = Lead.objects.create(
            company=self.company, nom='Alaoui', telephone='212612345678',
            email='alaoui@example.com')

    def test_phone_variant_matches_existing(self):
        r = self.api.get(
            '/api/django/crm/leads/check-duplicates/',
            {'telephone': '06 12-34 56 78'})
        self.assertEqual(r.status_code, 200, r.data)
        ids = [d['id'] for d in r.data]
        self.assertIn(self.existing.id, ids)

    def test_email_matches_existing(self):
        r = self.api.get(
            '/api/django/crm/leads/check-duplicates/',
            {'email': 'ALAOUI@example.com'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([d['id'] for d in r.data], [self.existing.id])

    def test_no_match_returns_empty(self):
        r = self.api.get(
            '/api/django/crm/leads/check-duplicates/',
            {'telephone': '0700000000'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data, [])

    def test_empty_query_returns_empty(self):
        r = self.api.get('/api/django/crm/leads/check-duplicates/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data, [])

    def test_exclude_self_in_edit(self):
        # En édition, le lead courant ne doit pas figurer dans ses doublons.
        r = self.api.get(
            '/api/django/crm/leads/check-duplicates/',
            {'telephone': '212612345678', 'exclude': str(self.existing.id)})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data, [])

    def test_other_company_not_matched(self):
        other_co = make_company('refine-other-co', 'Refine Other Co')
        Lead.objects.create(
            company=other_co, nom='Autre', telephone='212612345678')
        r = self.api.get(
            '/api/django/crm/leads/check-duplicates/',
            {'telephone': '212612345678'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([d['id'] for d in r.data], [self.existing.id])


class TestHistoriqueTracking(TestCase):
    """Les nouveaux champs suivis écrivent une ligne d'Historique à l'édition."""

    def setUp(self):
        self.company = make_company('refine-hist-co', 'Refine Hist Co')
        self.user = User.objects.create_user(
            username='refine_hist', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)

    def _patch(self, lead, data):
        r = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/', data, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r

    def test_regularisation_8221_logs_non_to_oui(self):
        lead = Lead.objects.create(
            company=self.company, nom='Régul', regularisation_8221=False)
        self._patch(lead, {'regularisation_8221': True})
        act = LeadActivity.objects.filter(
            lead=lead, field='regularisation_8221').first()
        self.assertIsNotNone(act)
        self.assertEqual(act.field_label, 'Régularisation 82-21')
        self.assertEqual(act.old_value, 'Non')
        self.assertEqual(act.new_value, 'Oui')

    def test_visite_notes_logged(self):
        lead = Lead.objects.create(company=self.company, nom='Visite')
        self._patch(lead, {'visite_notes': 'Toit accessible côté sud'})
        act = LeadActivity.objects.filter(
            lead=lead, field='visite_notes').first()
        self.assertIsNotNone(act)
        self.assertEqual(act.new_value, 'Toit accessible côté sud')

    def test_gps_fields_logged(self):
        lead = Lead.objects.create(company=self.company, nom='Geo')
        self._patch(lead, {'gps_lat': '33.5731', 'gps_lng': '-7.5898'})
        self.assertTrue(
            LeadActivity.objects.filter(lead=lead, field='gps_lat').exists())
        self.assertTrue(
            LeadActivity.objects.filter(lead=lead, field='gps_lng').exists())

    def test_structure_pref_logged_with_label(self):
        lead = Lead.objects.create(company=self.company, nom='Struct')
        self._patch(lead, {'structure_pref': 'acier'})
        act = LeadActivity.objects.filter(
            lead=lead, field='structure_pref').first()
        self.assertIsNotNone(act)
        # _CHOICE_FIELDS → le libellé humain du choix.
        self.assertEqual(act.new_value, 'Acier')

    def test_societe_logged(self):
        lead = Lead.objects.create(company=self.company, nom='Soc')
        self._patch(lead, {'societe': 'Ferme Atlas'})
        act = LeadActivity.objects.filter(lead=lead, field='societe').first()
        self.assertIsNotNone(act)
        self.assertEqual(act.field_label, 'Société')
        self.assertEqual(act.new_value, 'Ferme Atlas')

    def test_extra_scalar_fields_logged(self):
        lead = Lead.objects.create(company=self.company, nom='Divers')
        self._patch(lead, {
            'tranche_onee': 'Tranche 3',
            'ombrage_notes': 'Arbre au sud',
            'nb_etages': '2',
            'inclinaison_deg': '15',
        })
        for field in ('tranche_onee', 'ombrage_notes', 'nb_etages',
                      'inclinaison_deg'):
            self.assertTrue(
                LeadActivity.objects.filter(lead=lead, field=field).exists(),
                f'Historique manquant pour {field}')
