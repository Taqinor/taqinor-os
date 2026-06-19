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


class TestStageGuardOnUpdate(TestCase):
    """Garde funnel côté serveur sur un PATCH d'étape simple (parité bulk)."""

    def setUp(self):
        self.company = make_company('refine-stage-co', 'Refine Stage Co')
        self.user = User.objects.create_user(
            username='refine_stage', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)

    def test_perdu_lead_stage_locked(self):
        lead = Lead.objects.create(
            company=self.company, nom='Perdu', stage='QUOTE_SENT', perdu=True)
        r = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'stage': 'SIGNED'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'QUOTE_SENT')

    def test_backward_stage_rejected(self):
        lead = Lead.objects.create(
            company=self.company, nom='Recul', stage='FOLLOW_UP')
        r = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'stage': 'NEW'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'FOLLOW_UP')

    def test_forward_stage_allowed(self):
        lead = Lead.objects.create(
            company=self.company, nom='Avance', stage='NEW')
        r = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'stage': 'CONTACTED'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'CONTACTED')


class TestCanalGuardOnUpdate(TestCase):
    """Le canal doit appartenir au référentiel géré de la société."""

    def setUp(self):
        self.company = make_company('refine-canal-co', 'Refine Canal Co')
        self.user = User.objects.create_user(
            username='refine_canal', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)
        from apps.crm.models import Canal
        Canal.objects.create(
            company=self.company, cle='telephone', libelle='Téléphone')

    def test_unknown_canal_rejected(self):
        lead = Lead.objects.create(company=self.company, nom='Canal')
        r = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'canal': 'canal_bidon'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('canal', r.data)

    def test_known_canal_accepted(self):
        lead = Lead.objects.create(company=self.company, nom='Canal2')
        r = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'canal': 'telephone'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        lead.refresh_from_db()
        self.assertEqual(lead.canal, 'telephone')


class TestResolveClientLogsActivity(TestCase):
    """La résolution/création du client au 1er devis écrit une note Historique."""

    def setUp(self):
        self.company = make_company('refine-resolve-co', 'Refine Resolve Co')

    def test_creation_logs_client_lie(self):
        from apps.crm.services import resolve_client_for_lead
        lead = Lead.objects.create(
            company=self.company, nom='Tazi', prenom='Sara',
            email='sara@example.com')
        client = resolve_client_for_lead(lead)
        act = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='Client lié').first()
        self.assertIsNotNone(act)
        self.assertIn('Tazi', act.body)
        self.assertIn(client.nom, act.body)


class TestLeadExportColumns(TestCase):
    """L'export leads contient « Modifié le » + le dernier devis (TTC/statut)."""

    def setUp(self):
        self.company = make_company('refine-exp-co', 'Refine Exp Co')

    def test_lead_row_has_new_columns(self):
        from apps.crm.exports import LEAD_EXPORT_HEADERS, lead_row
        self.assertIn('Modifié le', LEAD_EXPORT_HEADERS)
        self.assertIn('Dernier devis (TTC)', LEAD_EXPORT_HEADERS)
        self.assertIn('Statut devis', LEAD_EXPORT_HEADERS)
        lead = Lead.objects.create(company=self.company, nom='Exp')
        row = lead_row(lead)
        self.assertEqual(len(row), len(LEAD_EXPORT_HEADERS))


class TestClientExportColumns(TestCase):
    """L'export clients sort Type/ICE/IF/RC/CIN/RIB."""

    def test_client_headers(self):
        from apps.crm.exports import CLIENT_EXPORT_HEADERS
        for col in ('Type', 'ICE', 'IF', 'RC', 'CIN', 'RIB'):
            self.assertIn(col, CLIENT_EXPORT_HEADERS)

    def test_client_row_values(self):
        from apps.crm.exports import CLIENT_EXPORT_HEADERS
        from apps.crm.models import Client
        company = make_company('refine-cli-exp', 'Refine Cli Exp')
        c = Client.objects.create(
            company=company, nom='SARL Atlas', type_client='entreprise',
            ice='001234567890123', if_fiscal='12345678', rc='RC-99')
        # Reconstruit la ligne via la même logique que l'export.
        from apps.crm.exports import export_clients_xlsx
        resp = export_clients_xlsx([c])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(CLIENT_EXPORT_HEADERS), 12)


class TestClientTracabilite(TestCase):
    """L16 — Client.created_by est forcé côté serveur (jamais lu du corps) et
    date_modification est exposée + se met à jour à la modification."""

    def setUp(self):
        self.company = make_company('refine-cli-trace', 'Refine Cli Trace')
        self.admin = User.objects.create_user(
            username='trace-admin', password='x', company=self.company,
            role='admin')
        self.autre = User.objects.create_user(
            username='trace-autre', password='x', company=self.company,
            role='admin')
        self.api = make_api(self.admin)

    def test_created_by_forced_to_request_user(self):
        # Le corps tente d'usurper created_by → ignoré, c'est l'utilisateur
        # courant qui est enregistré.
        resp = self.api.post('/api/django/crm/clients/', {
            'nom': 'Traçable', 'email': 'trace@ex.ma',
            'created_by': self.autre.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        from apps.crm.models import Client
        c = Client.objects.get(email='trace@ex.ma')
        self.assertEqual(c.created_by_id, self.admin.id)

    def test_serializer_exposes_created_by_and_date_modification(self):
        resp = self.api.post('/api/django/crm/clients/', {
            'nom': 'Lecture', 'email': 'lecture@ex.ma',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data['created_by'], self.admin.id)
        self.assertEqual(data['created_by_nom'], 'trace-admin')
        self.assertIn('date_modification', data)
        self.assertTrue(data['date_modification'])


class TestClientDocumentsPanel(TestCase):
    """L4 — GET /crm/clients/<id>/documents/ liste devis/factures/chantiers du
    client, borné à la société (lecture seule)."""

    def setUp(self):
        self.company = make_company('refine-cli-docs', 'Refine Cli Docs')
        self.admin = User.objects.create_user(
            username='docs-admin', password='x', company=self.company,
            role='admin')
        self.api = make_api(self.admin)
        from apps.crm.models import Client
        self.client_obj = Client.objects.create(
            company=self.company, nom='Docs Client', email='docs@ex.ma')

    def test_empty_client_returns_three_empty_lists(self):
        url = f'/api/django/crm/clients/{self.client_obj.id}/documents/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['devis'], [])
        self.assertEqual(data['factures'], [])
        self.assertEqual(data['chantiers'], [])

    def test_lists_client_devis(self):
        from apps.ventes.models import Devis
        Devis.objects.create(
            company=self.company, client=self.client_obj, reference='DV-001')
        url = f'/api/django/crm/clients/{self.client_obj.id}/documents/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(len(data['devis']), 1)
        row = data['devis'][0]
        self.assertEqual(row['reference'], 'DV-001')
        self.assertIn('statut', row)
        self.assertIn('total_ttc', row)

    def test_other_company_client_not_visible(self):
        # Un client d'une autre société renvoie 404 (portée TenantMixin).
        from apps.crm.models import Client
        autre = make_company('refine-cli-docs-2', 'Autre Docs')
        autre_client = Client.objects.create(
            company=autre, nom='Autre', email='autre@ex.ma')
        url = f'/api/django/crm/clients/{autre_client.id}/documents/'
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 404)
