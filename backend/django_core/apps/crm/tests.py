"""Tests for the CRM Lead/Opportunity model and API."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.crm import stages

User = get_user_model()


def make_company(slug='lead-co', nom='Lead Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestLeadModel(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_default_stage_is_nouveau(self):
        lead = Lead.objects.create(company=self.company, nom='Alaoui')
        # Canonical default = NEW, French label = Nouveau.
        self.assertEqual(lead.stage, stages.NEW)
        self.assertEqual(lead.stage, 'NEW')
        self.assertEqual(lead.get_stage_display(), 'Nouveau')

    def test_default_source_is_native(self):
        lead = Lead.objects.create(company=self.company, nom='Bennani')
        self.assertEqual(lead.source, Lead.Source.OS_NATIVE)

    def test_stage_choices_match_canonical_stages(self):
        choice_keys = [c[0] for c in Lead._meta.get_field('stage').choices]
        self.assertEqual(choice_keys, stages.STAGES)
        # And exactly the canonical 6.
        self.assertEqual(len(choice_keys), 6)

    def test_external_ref_uniqueness(self):
        Lead.objects.create(
            company=self.company, nom='X',
            source=Lead.Source.ODOO_IMPORT_TEST,
            external_system='odoo', external_id='42',
        )
        # Same (company, system, external_id) must not duplicate.
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Lead.objects.create(
                    company=self.company, nom='X dup',
                    source=Lead.Source.ODOO_IMPORT_TEST,
                    external_system='odoo', external_id='42',
                )


class TestLeadAPI(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company(slug='other-co', nom='Other Co')
        self.user = User.objects.create_user(
            username='lead_api_user', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_list_scoped_to_company(self):
        Lead.objects.create(company=self.company, nom='Mine')
        Lead.objects.create(company=self.other, nom='Theirs')
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results'] if 'results' in resp.data else resp.data
        names = [row['nom'] for row in data]
        self.assertIn('Mine', names)
        self.assertNotIn('Theirs', names)

    def test_create_forces_company_and_defaults(self):
        resp = self.api.post('/api/django/crm/leads/', {'nom': 'Nouveau Lead'})
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(nom='Nouveau Lead')
        self.assertEqual(lead.company_id, self.company.id)
        self.assertEqual(lead.stage, stages.NEW)

    def test_filter_by_source_and_stage(self):
        Lead.objects.create(company=self.company, nom='Imported',
                            source=Lead.Source.ODOO_IMPORT_TEST,
                            external_system='odoo', external_id='1')
        Lead.objects.create(company=self.company, nom='Native')
        resp = self.api.get('/api/django/crm/leads/?source=odoo_import_test')
        data = resp.data['results'] if 'results' in resp.data else resp.data
        names = [row['nom'] for row in data]
        self.assertEqual(names, ['Imported'])


class TestClientAPI(TestCase):
    """Création de client par l'API : la société vient du serveur (jamais du
    corps de la requête) — le validateur d'unicité (company, email) n'exige
    plus `company` du client HTTP. Champ ICE optionnel accepté."""

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='test-clientapi', defaults={'nom': 'Test ClientAPI'})
        self.user = User.objects.create_user(
            username='test_clientapi', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_create_client_without_company_in_body(self):
        r = self.api.post('/api/django/crm/clients/', {
            'nom': 'Bennani', 'email': 'bennani@example.com',
            'ice': '001122334455667',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['ice'], '001122334455667')
        c = Client.objects.get(email='bennani@example.com')
        self.assertEqual(c.company_id, self.company.id)  # forcée serveur

    def test_company_from_body_is_ignored(self):
        from authentication.models import Company
        other, _ = Company.objects.get_or_create(
            slug='test-clientapi-other', defaults={'nom': 'Autre'})
        r = self.api.post('/api/django/crm/clients/', {
            'nom': 'Intrus', 'email': 'intrus@example.com',
            'company': other.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        c = Client.objects.get(email='intrus@example.com')
        self.assertEqual(c.company_id, self.company.id)  # pas `other`


class TestLeadBills(TestCase):
    """A lead stores its electricity bill, with the summer-differs toggle."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='lead_bill_user', password='x',
            role_legacy='responsable', company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_lead_stores_bills_and_toggle(self):
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'Bennis', 'telephone': '+212600000003',
            'facture_hiver': '650', 'facture_ete': '420',
            'ete_differente': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(pk=resp.data['id'])
        self.assertEqual(str(lead.facture_hiver), '650.00')
        self.assertEqual(str(lead.facture_ete), '420.00')
        self.assertTrue(lead.ete_differente)

    def test_toggle_off_single_bill(self):
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'Sefrioui', 'facture_hiver': '533.50',
            'ete_differente': False,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(pk=resp.data['id'])
        # Arbitrary typed value kept exactly (no snapping).
        self.assertEqual(str(lead.facture_hiver), '533.50')
        self.assertFalse(lead.ete_differente)
        self.assertIsNone(lead.facture_ete)

    def test_client_link_not_writable_from_browser(self):
        from apps.crm.models import Client
        sneaky = Client.objects.create(
            company=self.company, nom='Sneaky', email='sneaky@example.com')
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'Hack', 'client': sneaky.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(Lead.objects.get(pk=resp.data['id']).client_id)


class TestResolveClientForLead(TestCase):
    """Lead → client resolution: reuse, match by email, else create. Never duplicates."""

    def setUp(self):
        from apps.crm.models import Client
        self.company = make_company()
        self.Client = Client

    def test_reuses_already_linked_client(self):
        from apps.crm.services import resolve_client_for_lead
        client = self.Client.objects.create(
            company=self.company, nom='Linked', email='linked@example.com')
        lead = Lead.objects.create(
            company=self.company, nom='Linked', client=client)
        self.assertEqual(resolve_client_for_lead(lead).id, client.id)
        self.assertEqual(self.Client.objects.count(), 1)

    def test_matches_existing_client_by_email(self):
        from apps.crm.services import resolve_client_for_lead
        existing = self.Client.objects.create(
            company=self.company, nom='Match', email='Match@Example.com')
        lead = Lead.objects.create(
            company=self.company, nom='Match', email='match@example.com')
        resolved = resolve_client_for_lead(lead)
        self.assertEqual(resolved.id, existing.id)
        lead.refresh_from_db()
        self.assertEqual(lead.client_id, existing.id)
        self.assertEqual(self.Client.objects.count(), 1)  # no duplicate

    def test_creates_client_from_lead_without_email(self):
        from apps.crm.services import resolve_client_for_lead
        lead = Lead.objects.create(
            company=self.company, nom='Nouveau', prenom='Prospect',
            telephone='+212600000004', ville='Rabat',
        )
        resolved = resolve_client_for_lead(lead)
        self.assertEqual(resolved.nom, 'Nouveau')
        self.assertEqual(resolved.company_id, self.company.id)
        self.assertIsNone(resolved.email)
        # Second resolution reuses the same client (persisted link).
        self.assertEqual(resolve_client_for_lead(lead).id, resolved.id)
        self.assertEqual(self.Client.objects.count(), 1)

    def test_email_match_is_company_scoped(self):
        from apps.crm.services import resolve_client_for_lead
        other = make_company(slug='other-bills-co', nom='Other')
        self.Client.objects.create(
            company=other, nom='Foreign', email='shared@example.com')
        lead = Lead.objects.create(
            company=self.company, nom='Local', email='shared@example.com')
        resolved = resolve_client_for_lead(lead)
        # Must NOT link the other company's client.
        self.assertEqual(resolved.company_id, self.company.id)
        self.assertEqual(self.Client.objects.count(), 2)


class TestLeadActivity(TestCase):
    """Historique chatter : journal automatique + notes manuelles."""

    def setUp(self):
        from apps.crm.models import LeadActivity
        self.LeadActivity = LeadActivity
        self.company = make_company()
        self.user = User.objects.create_user(
            username='chatter_user', password='x',
            role_legacy='responsable', company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _create(self, **extra):
        payload = {'nom': 'Chatter', **extra}
        resp = self.api.post('/api/django/crm/leads/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['id']

    def test_creation_is_logged_with_user(self):
        lead_id = self._create()
        acts = self.LeadActivity.objects.filter(lead_id=lead_id)
        self.assertEqual(acts.count(), 1)
        act = acts.first()
        self.assertEqual(act.kind, 'creation')
        self.assertEqual(act.user_id, self.user.id)
        self.assertIn('chatter_user', act.body)
        self.assertEqual(act.company_id, self.company.id)

    def test_field_changes_logged_old_to_new(self):
        lead_id = self._create(facture_hiver='600')
        resp = self.api.patch(f'/api/django/crm/leads/{lead_id}/', {
            'stage': 'CONTACTED',
            'facture_hiver': '750.50',
            'type_toiture': 'tole_metal',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        acts = self.LeadActivity.objects.filter(
            lead_id=lead_id, kind='modification')
        by_field = {a.field: a for a in acts}
        self.assertEqual(by_field['stage'].old_value, 'Nouveau')
        self.assertEqual(by_field['stage'].new_value, 'Contacté')
        self.assertEqual(by_field['facture_hiver'].old_value, '600.00')
        self.assertEqual(by_field['facture_hiver'].new_value, '750.50')
        self.assertEqual(by_field['type_toiture'].old_value, '—')
        self.assertEqual(by_field['type_toiture'].new_value, 'Tôle/Métal')
        for a in acts:
            self.assertEqual(a.user_id, self.user.id)

    def test_unchanged_fields_not_logged(self):
        lead_id = self._create(ville='Rabat')
        self.api.patch(f'/api/django/crm/leads/{lead_id}/',
                       {'ville': 'Rabat'}, format='json')
        self.assertEqual(
            self.LeadActivity.objects.filter(
                lead_id=lead_id, kind='modification').count(), 0)

    def test_manual_note_posted_and_listed(self):
        lead_id = self._create()
        resp = self.api.post(f'/api/django/crm/leads/{lead_id}/noter/',
                             {'body': 'Rappelé, pas de réponse'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['user_nom'], 'chatter_user')
        hist = self.api.get(f'/api/django/crm/leads/{lead_id}/historique/')
        self.assertEqual(hist.status_code, 200)
        kinds = [a['kind'] for a in hist.data]
        self.assertIn('note', kinds)
        self.assertIn('creation', kinds)
        # plus récent en premier
        self.assertEqual(hist.data[0]['kind'], 'note')

    def test_empty_note_rejected(self):
        lead_id = self._create()
        resp = self.api.post(f'/api/django/crm/leads/{lead_id}/noter/',
                             {'body': '   '}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_new_solar_fields_save_and_reload(self):
        lead_id = self._create(
            whatsapp='+212611223344', canal='meta_ads', priorite='haute',
            tags='Régularisation 82-21, VIP', type_installation='industriel',
            conso_mensuelle_kwh='1234.56', raccordement='triphase',
            regularisation_8221=True, type_toiture='bac_acier',
            surface_toiture_m2='850.25', orientation='sud',
            inclinaison_deg='0', ombrage='partiel',
            ombrage_notes='cheminée au sud-ouest', nb_etages='2',
            structure_pref='aluminium', taille_souhaitee_kwc='99.99',
            batterie_souhaitee='les_deux', visite_prevue_le='2026-06-20',
            relance_date='2026-06-15', gps_lat='33.589886', gps_lng='-7.603869',
        )
        data = self.api.get(f'/api/django/crm/leads/{lead_id}/').data
        self.assertEqual(data['canal'], 'meta_ads')
        self.assertEqual(data['priorite'], 'haute')
        self.assertEqual(data['tags'], 'Régularisation 82-21, VIP')
        self.assertEqual(data['conso_mensuelle_kwh'], '1234.56')
        self.assertEqual(data['surface_toiture_m2'], '850.25')
        self.assertEqual(data['taille_souhaitee_kwc'], '99.99')
        self.assertEqual(data['gps_lat'], '33.589886')
        self.assertTrue(data['regularisation_8221'])
        self.assertEqual(data['batterie_souhaitee'], 'les_deux')

    def test_owner_must_be_same_company(self):
        other = make_company(slug='chatter-other', nom='Other')
        foreign_user = User.objects.create_user(
            username='foreign_owner', password='x', company=other)
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': 'X', 'owner': foreign_user.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class TestStageChangeViaAPI(TestCase):
    """Kanban CRM : le glisser-déposer d'une carte persiste via
    PATCH /leads/<id>/ {'stage': ...} — même endpoint, mêmes garanties :
    journal Historique automatique (libellés français), scoping société,
    rejet des étapes inconnues. Les clés d'étape viennent de `stages`
    (STAGES.py canonique) — jamais de liste codée en dur ici.
    """

    def setUp(self):
        from apps.crm.models import LeadActivity
        self.LeadActivity = LeadActivity
        self.company = make_company()
        self.user = User.objects.create_user(
            username='kanban_user', password='x',
            role_legacy='responsable', company=self.company,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        # Lead créé directement en base (pas via l'API) pour que le
        # journal ne contienne QUE les entrées produites par le PATCH.
        self.lead = Lead.objects.create(company=self.company, nom='Kanban')
        self.assertEqual(self.lead.stage, stages.NEW)

    def _patch_stage(self, stage_key, lead_id=None, api=None):
        api = api or self.api
        lead_id = lead_id or self.lead.id
        return api.patch(f'/api/django/crm/leads/{lead_id}/',
                         {'stage': stage_key}, format='json')

    def test_patch_stage_changes_stage_and_logs_historique(self):
        resp = self._patch_stage('CONTACTED')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'CONTACTED')
        acts = self.LeadActivity.objects.filter(
            lead=self.lead, kind='modification', field='stage')
        self.assertEqual(acts.count(), 1)
        act = acts.first()
        self.assertEqual(act.field_label, 'Étape')
        # Libellés français lus depuis STAGES.py — pas codés en dur.
        self.assertEqual(act.old_value, stages.STAGE_LABELS[stages.NEW])
        self.assertEqual(act.old_value, 'Nouveau')
        self.assertEqual(act.new_value, stages.STAGE_LABELS['CONTACTED'])
        self.assertEqual(act.new_value, 'Contacté')
        self.assertEqual(act.user_id, self.user.id)
        self.assertEqual(act.company_id, self.company.id)

    def test_historique_endpoint_returns_stage_entry(self):
        self._patch_stage('CONTACTED')
        hist = self.api.get(
            f'/api/django/crm/leads/{self.lead.id}/historique/')
        self.assertEqual(hist.status_code, 200)
        stage_entries = [a for a in hist.data if a['field'] == 'stage']
        self.assertEqual(len(stage_entries), 1)
        entry = stage_entries[0]
        self.assertEqual(entry['field_label'], 'Étape')
        self.assertEqual(entry['old_value'], stages.STAGE_LABELS[stages.NEW])
        self.assertEqual(entry['new_value'],
                         stages.STAGE_LABELS['CONTACTED'])
        self.assertEqual(entry['user_nom'], 'kanban_user')

    def test_patch_invalid_stage_rejected(self):
        resp = self._patch_stage('PAS_UNE_ETAPE')
        self.assertEqual(resp.status_code, 400)
        self.lead.refresh_from_db()
        # Étape inchangée, rien de journalisé.
        self.assertEqual(self.lead.stage, stages.NEW)
        self.assertEqual(
            self.LeadActivity.objects.filter(lead=self.lead).count(), 0)

    def test_patch_stage_scoped_to_company(self):
        other = make_company(slug='kanban-other', nom='Kanban Other')
        intruder = User.objects.create_user(
            username='kanban_intruder', password='x',
            role_legacy='responsable', company=other,
        )
        foreign_api = APIClient()
        token = str(AccessToken.for_user(intruder))
        foreign_api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = self._patch_stage('CONTACTED', api=foreign_api)
        # Scoping multi-tenant : le lead d'une autre société est invisible.
        self.assertEqual(resp.status_code, 404)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)
        self.assertEqual(
            self.LeadActivity.objects.filter(lead=self.lead).count(), 0)

    def test_granular_role_user_can_change_stage(self):
        # Rôle fin façon « Commerciale » : permissions CRM seulement.
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Commerciale Kanban',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'],
        )
        commerciale = User.objects.create_user(
            username='kanban_commerciale', password='x',
            role=role, company=self.company,
        )
        api = APIClient()
        token = str(AccessToken.for_user(commerciale))
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        resp = self._patch_stage('CONTACTED', api=api)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'CONTACTED')
        acts = self.LeadActivity.objects.filter(
            lead=self.lead, kind='modification', field='stage')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().user_id, commerciale.id)

    def test_drag_to_signed_logs_label(self):
        # Glissé directement en conversion : seul le journal est attendu,
        # aucun autre effet de bord aujourd'hui.
        resp = self._patch_stage('SIGNED')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'SIGNED')
        act = self.LeadActivity.objects.get(
            lead=self.lead, kind='modification', field='stage')
        self.assertEqual(act.new_value, stages.STAGE_LABELS['SIGNED'])
        self.assertEqual(act.new_value, 'Signé')


class TestDefaultResponsable(TestCase):
    """Responsable par défaut des nouveaux leads (Paramètres → profil).

    Couvre l'assignation automatique à la création manuelle et le respect
    d'un responsable explicitement choisi.
    """

    def setUp(self):
        from apps.parametres.models import CompanyProfile
        self.company = make_company(slug='resp-co', nom='Resp Co')
        self.meryem = User.objects.create_user(
            username='meryem', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.autre = User.objects.create_user(
            username='autre_resp', password='x', role_legacy='responsable',
            company=self.company,
        )
        self.profile = CompanyProfile.get(company=self.company)
        self.profile.responsable_defaut_leads = self.meryem
        self.profile.save(update_fields=['responsable_defaut_leads'])

        self.api = APIClient()
        token = str(AccessToken.for_user(self.autre))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_new_lead_gets_default_responsable(self):
        resp = self.api.post('/api/django/crm/leads/', {'nom': 'Sans resp'})
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(nom='Sans resp')
        self.assertEqual(lead.owner_id, self.meryem.id)

    def test_explicit_responsable_is_respected(self):
        resp = self.api.post(
            '/api/django/crm/leads/',
            {'nom': 'Avec resp', 'owner': self.autre.id},
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(nom='Avec resp')
        self.assertEqual(lead.owner_id, self.autre.id)

    def test_webhook_lead_gets_default_responsable(self):
        from django.test import override_settings
        from apps.crm.models import Lead as LeadModel
        with override_settings(
            WEBSITE_LEAD_WEBHOOK_SECRET='sekret',
            WEBSITE_LEADS_COMPANY_ID=self.company.id,
        ):
            client = APIClient()
            resp = client.post(
                '/api/django/crm/webhooks/website-leads/',
                data={'fullName': 'Web Lead', 'phoneE164': '+212600000000'},
                format='json',
                HTTP_X_WEBHOOK_SECRET='sekret',
            )
        self.assertIn(resp.status_code, (200, 201), resp.content)
        lead = LeadModel.objects.filter(nom='Web Lead').first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.owner_id, self.meryem.id)


class TestAssignableUsers(TestCase):
    """Endpoint /assignable-users/ — ouvert à la Commerciale, scopé société."""

    def setUp(self):
        self.company = make_company(slug='assign-co', nom='Assign Co')
        self.other = make_company(slug='assign-other', nom='Assign Other')
        self.commerciale = User.objects.create_user(
            username='assign_commerciale', password='x',
            role_legacy='responsable', company=self.company,
        )
        self.collegue = User.objects.create_user(
            username='assign_collegue', password='x',
            role_legacy='responsable', company=self.company, poste='Technicien',
        )
        User.objects.create_user(
            username='assign_etranger', password='x',
            role_legacy='responsable', company=self.other,
        )
        self.api = APIClient()
        token = str(AccessToken.for_user(self.commerciale))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_commerciale_can_list_assignable_users(self):
        resp = self.api.get('/api/django/crm/assignable-users/')
        self.assertEqual(resp.status_code, 200, resp.data)
        usernames = [u['username'] for u in resp.data]
        self.assertIn('assign_commerciale', usernames)
        self.assertIn('assign_collegue', usernames)
        self.assertNotIn('assign_etranger', usernames)
        collegue = next(
            u for u in resp.data if u['username'] == 'assign_collegue')
        self.assertEqual(collegue['poste'], 'Technicien')

    def test_reassign_owner_is_logged(self):
        from apps.crm.models import LeadActivity
        lead = Lead.objects.create(
            company=self.company, nom='À réassigner', owner=self.commerciale)
        resp = self.api.patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'owner': self.collegue.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.owner_id, self.collegue.id)
        act = LeadActivity.objects.get(
            lead=lead, kind='modification', field='owner')
        self.assertEqual(act.old_value, 'assign_commerciale')
        self.assertEqual(act.new_value, 'assign_collegue')
        self.assertEqual(act.user_id, self.commerciale.id)
