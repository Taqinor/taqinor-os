"""
Tests du module Chantiers / Installations (2026-06-13).

Couvre : création depuis un devis accepté (pré-remplissage + anti-doublon),
changement de statut → ligne de chatter + statuts hors liste refusés, mise en
service qui pose le statut, isolation par société (A ne voit/touche pas B), et
le type de client + identifiants.

Run :
    docker compose exec django_core python manage.py test apps.installations -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Installation, Intervention, InstallationActivity

User = get_user_model()


def make_company(slug='cht-co', nom='Cht Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids_of(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return [x['id'] for x in rows]


def make_accepted_devis(company, with_lead=True):
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'site-{company.id}@example.invalid')
    lead = None
    if with_lead:
        lead = Lead.objects.create(
            company=company, nom='Site', prenom='Client', stage='SIGNED',
            adresse='Douar Test, route de Tit Mellil', ville='Médiouna',
            gps_lat=Decimal('33.456789'), gps_lng=Decimal('-7.512345'),
            raccordement='triphase', type_installation='residentiel',
            taille_souhaitee_kwc=Decimal('6.5'))
    devis = Devis.objects.create(
        company=company, reference=f'DEV-CHT-{company.id}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel',
        etude_params={'puissance_kwc': 7.2})
    return devis, client, lead


class TestCreateFromDevis(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='cht_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.devis, self.client_obj, self.lead = make_accepted_devis(self.company)

    def test_create_prefills_from_devis_and_lead(self):
        r = self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                          {'devis': self.devis.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['created'])
        self.assertTrue(r.data['reference'].startswith('CHT-'))
        # Pré-remplissage
        self.assertEqual(r.data['client'], self.client_obj.id)
        self.assertEqual(r.data['devis'], self.devis.id)
        self.assertEqual(r.data['lead'], self.lead.id)
        self.assertEqual(r.data['site_adresse'], 'Douar Test, route de Tit Mellil')
        self.assertEqual(r.data['site_ville'], 'Médiouna')
        self.assertEqual(r.data['raccordement'], 'triphase')  # gelé depuis le lead
        self.assertEqual(r.data['type_installation'], 'residentiel')
        self.assertEqual(Decimal(r.data['puissance_installee_kwc']), Decimal('7.20'))
        # Entonnoir N1 : un chantier créé depuis un devis accepté démarre « Signé ».
        self.assertEqual(r.data['statut'], 'signe')
        self.assertEqual(str(r.data['gps_lat']), '33.456789')

    def test_create_is_idempotent_no_duplicate(self):
        first = self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                              {'devis': self.devis.id}, format='json')
        self.assertEqual(first.status_code, 201)
        again = self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                              {'devis': self.devis.id}, format='json')
        self.assertEqual(again.status_code, 200, again.data)
        self.assertFalse(again.data['created'])
        self.assertEqual(again.data['id'], first.data['id'])
        self.assertEqual(Installation.objects.filter(devis=self.devis).count(), 1)

    def test_refuses_non_accepted_devis(self):
        self.devis.statut = Devis.Statut.BROUILLON
        self.devis.save()
        r = self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                          {'devis': self.devis.id}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_creation_writes_a_chatter_line(self):
        r = self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                          {'devis': self.devis.id}, format='json')
        acts = InstallationActivity.objects.filter(installation_id=r.data['id'])
        self.assertTrue(any(a.kind == 'creation' for a in acts))


class TestStatusAndMES(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='cht_resp2', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        devis, _, _ = make_accepted_devis(self.company)
        self.inst = Installation.objects.get(pk=self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json').data['id'])

    def test_status_change_logs_chatter(self):
        r = self.api.patch(f'/api/django/installations/chantiers/{self.inst.id}/',
                           {'statut': 'planifie'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'planifie')
        logged = InstallationActivity.objects.filter(
            installation=self.inst, field='statut')
        self.assertTrue(logged.exists())
        entry = logged.first()
        self.assertEqual(entry.new_value, 'Planifié')

    def test_invalid_status_rejected(self):
        r = self.api.patch(f'/api/django/installations/chantiers/{self.inst.id}/',
                           {'statut': 'en_orbite'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_mise_en_service_sets_status(self):
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/mise-en-service/',
            {'date_mise_en_service': '2026-06-20',
             'mes_pv_notes': 'PV signé, production OK',
             'mes_production_test': '32.5', 'mes_tension': '230'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'mise_en_service')
        self.assertEqual(r.data['date_mise_en_service'], '2026-06-20')
        self.assertEqual(Decimal(r.data['mes_production_test']), Decimal('32.50'))

    def test_cancel_is_a_flag_with_reason(self):
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/annuler/',
            {'motif': 'Client a renoncé'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['annule'])
        self.assertEqual(r.data['motif_annulation'], 'Client a renoncé')
        # Toujours visible (drapeau, pas une suppression)
        self.assertTrue(Installation.objects.filter(pk=self.inst.id).exists())

    def test_add_intervention(self):
        r = self.api.post('/api/django/installations/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'pose',
            'date_prevue': '2026-06-18', 'compte_rendu': 'Pose prévue',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Intervention.objects.filter(installation=self.inst).count(), 1)
        # L'ajout est tracé dans le chatter du chantier
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst, body__icontains='Intervention ajoutée').exists())


class TestChantierFunnelParcChecklist(TestCase):
    """N1/N2/N4/N7/N9 — entonnoir N1, parc installé, checklist, séries."""

    def setUp(self):
        self.company = make_company(slug='cht-funnel', nom='Funnel')
        self.user = User.objects.create_user(
            username='funnel_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        devis, _, _ = make_accepted_devis(self.company)
        self.inst = Installation.objects.get(pk=self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json').data['id'])

    def test_starts_signed_and_installer_defaulted(self):
        self.assertEqual(self.inst.statut, 'signe')
        self.assertEqual(self.inst.technicien_responsable_id, self.user.id)
        self.assertIsInstance(self.inst.bom, list)

    def test_reception_stamps_date_and_enters_parc(self):
        r = self.api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'statut': 'receptionne'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['est_parc'])
        self.assertIsNotNone(r.data['date_reception'])
        # Présent dans la vue parc.
        parc = self.api.get('/api/django/installations/chantiers/?parc=1')
        self.assertIn(self.inst.id, ids_of(parc))

    def test_legacy_status_maps_to_canonical_column(self):
        self.inst.statut = 'mise_en_service'
        self.inst.save(update_fields=['statut'])
        r = self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/')
        self.assertEqual(r.data['statut_canonique'], 'receptionne')
        self.assertTrue(r.data['est_parc'])

    def test_labour_days_editable(self):
        r = self.api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'labour_jours_estimes': '2.5', 'labour_jours_reels': '3'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(r.data['labour_jours_estimes']), Decimal('2.5'))

    def test_checklist_seeds_and_tracks_completion(self):
        r = self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/checklist/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['items']), 7)
        self.assertEqual(r.data['completion'], 0)
        cle = r.data['items'][0]['cle']
        r2 = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/cocher-checklist/',
            {'cle': cle, 'fait': True}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertGreater(r2.data['completion'], 0)

    def test_serial_capture_on_checklist_creates_equipement(self):
        from apps.stock.models import Produit
        from apps.sav.models import Equipement
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur X', prix_vente=Decimal('100'))
        self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/checklist/')
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/cocher-checklist/',
            {'cle': 'onduleur_raccorde', 'fait': True,
             'equipements': [{'produit': produit.id, 'numero_serie': 'SN-001'}]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['equipements_crees'], 1)
        self.assertTrue(Equipement.objects.filter(
            installation=self.inst, numero_serie='SN-001').exists())

    def test_serial_capture_optional_never_blocks(self):
        self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/checklist/')
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/cocher-checklist/',
            {'cle': 'panneaux_poses', 'fait': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['equipements_crees'], 0)

    def test_checklist_etapes_seeded_for_parametres(self):
        r = self.api.get('/api/django/installations/checklist-etapes/')
        self.assertEqual(r.status_code, 200)
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual(len(rows), 7)

    def test_regulatory_dossier_and_filters(self):
        # N40/N42 — pose un régime + statut + drapeau Article 33.
        r = self.api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'regime_8221': 'declaration_bt', 'dossier_statut': 'a_deposer',
             'art33_regularisation': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['regime_8221'], 'declaration_bt')
        self.assertTrue(r.data['art33_regularisation'])
        # N41 — filtres serveur par régime / statut / art33.
        self.assertIn(self.inst.id, ids_of(self.api.get(
            '/api/django/installations/chantiers/?regime=declaration_bt')))
        self.assertIn(self.inst.id, ids_of(self.api.get(
            '/api/django/installations/chantiers/?art33=1')))
        self.assertNotIn(self.inst.id, ids_of(self.api.get(
            '/api/django/installations/chantiers/?regime=autorisation_anre')))


class TestTenantScoping(TestCase):
    def setUp(self):
        self.a = make_company(slug='cht-a', nom='A')
        self.b = make_company(slug='cht-b', nom='B')
        self.ua = User.objects.create_user(
            username='cht_a', password='x', role_legacy='responsable', company=self.a)
        self.ub = User.objects.create_user(
            username='cht_b', password='x', role_legacy='admin', company=self.b)
        devis_a, _, _ = make_accepted_devis(self.a)
        self.inst_a = Installation.objects.get(pk=auth(self.ua).post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis_a.id}, format='json').data['id'])

    def test_other_company_cannot_see(self):
        r = auth(self.ub).get('/api/django/installations/chantiers/')
        self.assertNotIn(self.inst_a.id, ids_of(r))

    def test_other_company_cannot_retrieve_or_touch(self):
        api = auth(self.ub)
        self.assertEqual(
            api.get(f'/api/django/installations/chantiers/{self.inst_a.id}/').status_code, 404)
        self.assertEqual(
            api.patch(f'/api/django/installations/chantiers/{self.inst_a.id}/',
                      {'statut': 'planifie'}, format='json').status_code, 404)


class TestClientType(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='cli_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_default_is_particulier(self):
        c = Client.objects.create(company=self.company, nom='Sans ICE')
        self.assertEqual(c.type_client, 'particulier')

    def test_entreprise_with_identifiers_persist(self):
        r = self.api.post('/api/django/crm/clients/', {
            'nom': 'STE Solaire', 'email': 'ste@example.invalid', 'type_client': 'entreprise',
            'ice': '001234567890123', 'if_fiscal': '12345678', 'rc': 'RC-9001',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['type_client'], 'entreprise')
        self.assertEqual(r.data['ice'], '001234567890123')
        self.assertEqual(r.data['rc'], 'RC-9001')

    def test_particulier_with_cin(self):
        r = self.api.post('/api/django/crm/clients/', {
            'nom': 'Particulier', 'email': 'part@example.invalid', 'type_client': 'particulier', 'cin': 'BK123456',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['cin'], 'BK123456')
