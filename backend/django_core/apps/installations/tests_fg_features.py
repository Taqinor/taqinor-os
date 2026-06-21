"""
FG68 / FG69 / FG72 / FG73 / FG74 / FG75 / FG76 / FG78 / FG79 / FG80 — tests.

Couvre :
  * FG68 — filtre date_from/date_to sur interventions + endpoint calendrier
  * FG69 — signature client (signer-client)
  * FG72 — champs multi-day (date_pose_fin_prevue, duree_pose_jours)
  * FG73 — tournée journalière (ma-tournee)
  * FG74 — Gantt multi-chantier (gantt)
  * FG75 — relevés de toiture / drone (releves, ajouter-releve, supprimer-releve)
  * FG76 — photo_obligatoire sur checklist étape modèle et item
  * FG78 — confirmation RDV + reschedule (confirmer-rdv)
  * FG79 — scaffold interventions standard (TypeInterventionPlan + creer-interventions-standard)
  * FG80 — calibration outillage (calibrer, a_calibrer badge, date_prochaine_calibration)

Run :
    python manage.py test apps.installations.tests_fg_features -v2
    python manage.py test apps.outillage -v2
"""
import datetime
import itertools
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import (
    Installation, Intervention, TypeInterventionPlan,
    ChecklistEtapeModele,
)
from apps.installations.services import create_installation_from_devis
from apps.outillage.models import Outillage

User = get_user_model()
_seq = itertools.count(1)


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    slug = slug or f'fg-co-{n}'
    nom = nom or f'FG Co {n}'
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_chantier(company, user, type_installation='residentiel'):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'fg-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation=type_installation,
        gps_lat=Decimal('33.5'), gps_lng=Decimal('-7.5'))
    devis = Devis.objects.create(
        company=company, reference=f'DEV-FG-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation=type_installation)
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


def make_intervention(inst, company, user, type_interv='pose', date_prevue=None):
    kw = {}
    if date_prevue:
        kw['date_prevue'] = date_prevue
    return Intervention.objects.create(
        company=company, installation=inst, type_intervention=type_interv,
        created_by=user, technicien=user, **kw)


# Image PNG 1×1 minimale
_PNG_1x1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08'
    b'\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00'
    b'\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')


def png_file(name='photo.png'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, _PNG_1x1, content_type='image/png')


# ── FG68 — filtre date_from/date_to ──────────────────────────────────────────

class TestFG68DateRangeFilter(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg68_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def test_date_from_filter(self):
        """FG68 — date_from exclut les interventions antérieures."""
        make_intervention(self.inst, self.company, self.user,
                          date_prevue='2026-01-10')
        make_intervention(self.inst, self.company, self.user,
                          type_interv='raccordement',
                          date_prevue='2026-02-15')
        r = self.api.get('/api/django/installations/interventions/',
                         {'date_from': '2026-02-01'})
        self.assertEqual(r.status_code, 200)
        dates = [iv['date_prevue'] for iv in r.data['results']]
        self.assertNotIn('2026-01-10', dates)
        self.assertIn('2026-02-15', dates)

    def test_date_to_filter(self):
        """FG68 — date_to exclut les interventions postérieures."""
        make_intervention(self.inst, self.company, self.user,
                          date_prevue='2026-01-10')
        make_intervention(self.inst, self.company, self.user,
                          type_interv='raccordement',
                          date_prevue='2026-03-20')
        r = self.api.get('/api/django/installations/interventions/',
                         {'date_to': '2026-02-01'})
        self.assertEqual(r.status_code, 200)
        dates = [iv['date_prevue'] for iv in r.data['results']]
        self.assertIn('2026-01-10', dates)
        self.assertNotIn('2026-03-20', dates)

    def test_calendrier_groups_by_technicien(self):
        """FG68 — /calendrier groupe les interventions par technicien."""
        make_intervention(self.inst, self.company, self.user,
                          date_prevue='2026-06-01')
        r = self.api.get('/api/django/installations/interventions/calendrier/',
                         {'date_from': '2026-06-01', 'date_to': '2026-06-30'})
        self.assertEqual(r.status_code, 200)
        # Résultat est une liste de {technicien, interventions}
        self.assertIsInstance(r.data, list)
        self.assertGreaterEqual(len(r.data), 1)
        # Chaque entrée a bien les clés attendues
        entry = r.data[0]
        self.assertIn('technicien', entry)
        self.assertIn('interventions', entry)

    def test_calendrier_company_scoping(self):
        """FG68 — /calendrier ne renvoie que les interventions de la société."""
        company2 = make_company()
        user2 = User.objects.create_user(
            username='fg68_other', password='x', role_legacy='responsable',
            company=company2)
        inst2 = make_chantier(company2, user2)
        make_intervention(inst2, company2, user2, date_prevue='2026-06-01')
        r = self.api.get('/api/django/installations/interventions/calendrier/',
                         {'date_from': '2026-06-01', 'date_to': '2026-06-30'})
        # Toutes les interventions dans la réponse appartiennent à self.company
        for entry in r.data:
            for iv in entry['interventions']:
                self.assertEqual(iv['company'], self.company.id)


# ── FG69 — signature client ───────────────────────────────────────────────────

class TestFG69SignatureClient(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg69_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.interv = make_intervention(self.inst, self.company, self.user)

    def test_signer_client_stores_data(self):
        """FG69 — signer-client enregistre la signature et le nom."""
        r = self.api.post(
            f'/api/django/installations/interventions/{self.interv.id}/signer-client/',
            {'signature_client': 'data:image/png;base64,abc==',
             'signataire_nom': 'Mohammed Alami'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.signature_client, 'data:image/png;base64,abc==')
        self.assertEqual(self.interv.signataire_nom, 'Mohammed Alami')
        self.assertIsNotNone(self.interv.signe_le)

    def test_signer_client_empty_signature_rejected(self):
        """FG69 — signature vide renvoie 400."""
        r = self.api.post(
            f'/api/django/installations/interventions/{self.interv.id}/signer-client/',
            {'signature_client': '   '},
            format='json')
        self.assertEqual(r.status_code, 400)

    def test_signer_client_company_isolation(self):
        """FG69 — un user d'une autre société ne peut pas signer."""
        company2 = make_company()
        user2 = User.objects.create_user(
            username='fg69_other', password='x', role_legacy='responsable',
            company=company2)
        api2 = auth(user2)
        r = api2.post(
            f'/api/django/installations/interventions/{self.interv.id}/signer-client/',
            {'signature_client': 'data:image/png;base64,abc=='},
            format='json')
        self.assertIn(r.status_code, [403, 404])


# ── FG72 — champs multi-day ───────────────────────────────────────────────────

class TestFG72MultiDay(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg72_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def test_patch_multi_day_fields(self):
        """FG72 — PATCH accepte date_pose_fin_prevue et duree_pose_jours."""
        r = self.api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'date_pose_fin_prevue': '2026-07-10', 'duree_pose_jours': 3},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(str(self.inst.date_pose_fin_prevue), '2026-07-10')
        self.assertEqual(self.inst.duree_pose_jours, 3)

    def test_gantt_includes_new_fields(self):
        """FG72+FG74 — /gantt inclut date_pose_fin_prevue et duree_pose_jours."""
        self.inst.date_pose_prevue = datetime.date(2026, 7, 7)
        self.inst.date_pose_fin_prevue = datetime.date(2026, 7, 9)
        self.inst.duree_pose_jours = 3
        self.inst.save()
        r = self.api.get('/api/django/installations/chantiers/gantt/')
        self.assertEqual(r.status_code, 200)
        row = next((x for x in r.data if x['id'] == self.inst.id), None)
        self.assertIsNotNone(row)
        self.assertEqual(row['jalons']['pose_fin_prevue'], '2026-07-09')
        self.assertEqual(row['duree_pose_jours'], 3)


# ── FG73 — tournée journalière ────────────────────────────────────────────────

class TestFG73Tournee(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg73_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def test_ma_tournee_returns_today_interventions(self):
        """FG73 — ma-tournee renvoie les interventions du technicien pour aujourd'hui."""
        today = str(datetime.date.today())
        make_intervention(self.inst, self.company, self.user, date_prevue=today)
        r = self.api.get('/api/django/installations/interventions/ma-tournee/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['date'], today)
        self.assertIsInstance(r.data['stops'], list)
        self.assertGreaterEqual(len(r.data['stops']), 1)

    def test_ma_tournee_has_itineraire_url(self):
        """FG73 — ma-tournee inclut un lien maps pour chaque arrêt avec GPS."""
        today = str(datetime.date.today())
        make_intervention(self.inst, self.company, self.user, date_prevue=today)
        r = self.api.get('/api/django/installations/interventions/ma-tournee/')
        self.assertEqual(r.status_code, 200)
        for stop in r.data['stops']:
            self.assertIn('itineraire_url', stop)
            if stop.get('gps_lat'):
                self.assertIn('google.com/maps', stop['itineraire_url'])

    def test_ma_tournee_empty_other_day(self):
        """FG73 — ma-tournee pour hier renvoie une liste vide."""
        r = self.api.get('/api/django/installations/interventions/ma-tournee/',
                         {'date': '2020-01-01'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['stops'], [])


# ── FG74 — Gantt multi-chantier ───────────────────────────────────────────────

class TestFG74Gantt(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg74_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_gantt_returns_jalons(self):
        """FG74 — /gantt renvoie les chantiers actifs avec leurs jalons."""
        inst = make_chantier(self.company, self.user)
        inst.date_signature = datetime.date(2026, 6, 1)
        inst.save()
        r = self.api.get('/api/django/installations/chantiers/gantt/')
        self.assertEqual(r.status_code, 200)
        row = next((x for x in r.data if x['id'] == inst.id), None)
        self.assertIsNotNone(row)
        self.assertIn('jalons', row)
        self.assertEqual(row['jalons']['signature'], '2026-06-01')

    def test_gantt_excludes_cloture(self):
        """FG74 — /gantt exclut les chantiers clôturés."""
        inst = make_chantier(self.company, self.user)
        inst.statut = Installation.Statut.CLOTURE
        inst.save()
        r = self.api.get('/api/django/installations/chantiers/gantt/')
        self.assertEqual(r.status_code, 200)
        ids = [x['id'] for x in r.data]
        self.assertNotIn(inst.id, ids)

    def test_gantt_company_isolation(self):
        """FG74 — /gantt renvoie uniquement les chantiers de la société."""
        company2 = make_company()
        user2 = User.objects.create_user(
            username='fg74_other', password='x', role_legacy='responsable',
            company=company2)
        inst2 = make_chantier(company2, user2)
        r = self.api.get('/api/django/installations/chantiers/gantt/')
        ids = [x['id'] for x in r.data]
        self.assertNotIn(inst2.id, ids)


# ── FG75 — relevés toiture / drone ───────────────────────────────────────────

class TestFG75Releves(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg75_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    @mock.patch('apps.records.storage.get_minio_client')
    @mock.patch('apps.records.storage.ensure_uploads_bucket')
    def test_ajouter_releve_stores_attachment(self, mock_ensure, mock_minio):
        """FG75 — ajouter-releve crée une pièce jointe avec phase=releve."""
        mock_client = mock.MagicMock()
        mock_minio.return_value = mock_client
        url = f'/api/django/installations/chantiers/{self.inst.id}/ajouter-releve/'
        r = self.api.post(url, {'file': png_file(), 'phase': 'releve'},
                          format='multipart')
        self.assertEqual(r.status_code, 201, r.data)
        # L'attachment est bien en base
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        ct = ContentType.objects.get_for_model(Installation)
        att = Attachment.objects.filter(
            content_type=ct, object_id=self.inst.id,
            phase='releve').first()
        self.assertIsNotNone(att)

    @mock.patch('apps.records.storage.get_minio_client')
    @mock.patch('apps.records.storage.ensure_uploads_bucket')
    def test_releves_list(self, mock_ensure, mock_minio):
        """FG75 — /releves liste uniquement les phases releve / drone."""
        mock_client = mock.MagicMock()
        mock_minio.return_value = mock_client
        # Ajoute un relevé toiture et un drone
        self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/ajouter-releve/',
            {'file': png_file('toiture.png'), 'phase': 'releve'},
            format='multipart')
        self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/ajouter-releve/',
            {'file': png_file('drone.png'), 'phase': 'drone'},
            format='multipart')
        r = self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/releves/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)
        phases = {att['phase'] for att in r.data}
        self.assertEqual(phases, {'releve', 'drone'})

    def test_invalid_phase_rejected(self):
        """FG75 — phase invalide renvoie 400."""
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/ajouter-releve/',
            {'file': png_file(), 'phase': 'photo_perso'},
            format='multipart')
        self.assertEqual(r.status_code, 400)

    def test_releves_company_isolation(self):
        """FG75 — /releves d'une autre société renvoie 404."""
        company2 = make_company()
        user2 = User.objects.create_user(
            username='fg75_other', password='x', role_legacy='responsable',
            company=company2)
        api2 = auth(user2)
        r = api2.get(
            f'/api/django/installations/chantiers/{self.inst.id}/releves/')
        self.assertIn(r.status_code, [403, 404])


# ── FG76 — photo_obligatoire ──────────────────────────────────────────────────

class TestFG76PhotoObligatoire(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg76_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def test_etape_modele_has_photo_obligatoire_field(self):
        """FG76 — ChecklistEtapeModele expose photo_obligatoire."""
        etape = ChecklistEtapeModele.objects.filter(company=self.company).first()
        if etape is None:
            return  # Pas d'étapes — test non applicable
        r = self.api.get(f'/api/django/installations/checklist-etapes/{etape.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('photo_obligatoire', r.data)

    def test_checklist_item_has_photo_obligatoire(self):
        """FG76 — ChantierChecklistItem expose photo_obligatoire."""
        r = self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/checklist/')
        self.assertEqual(r.status_code, 200)
        items = r.data.get('items', [])
        if items:
            self.assertIn('photo_obligatoire', items[0])

    def test_patch_photo_obligatoire(self):
        """FG76 — PATCH d'une étape modèle accepte photo_obligatoire=True."""
        etape = ChecklistEtapeModele.objects.filter(
            company=self.company, protege=False).first()
        if etape is None:
            return
        r = self.api.patch(
            f'/api/django/installations/checklist-etapes/{etape.id}/',
            {'photo_obligatoire': True},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        etape.refresh_from_db()
        self.assertTrue(etape.photo_obligatoire)


# ── FG78 — confirmation RDV ───────────────────────────────────────────────────

class TestFG78RdvConfirmation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg78_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.interv = make_intervention(
            self.inst, self.company, self.user,
            date_prevue='2026-07-01')

    def test_confirmer_rdv(self):
        """FG78 — confirmer-rdv marque rdv_confirme=True."""
        r = self.api.post(
            f'/api/django/installations/interventions/{self.interv.id}/confirmer-rdv/',
            {'confirme': True},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.interv.refresh_from_db()
        self.assertTrue(self.interv.rdv_confirme)
        self.assertIsNotNone(self.interv.rdv_confirme_le)

    def test_reschedule_increments_count(self):
        """FG78 — reschedule incrémente rdv_reschedule_count."""
        r = self.api.post(
            f'/api/django/installations/interventions/{self.interv.id}/confirmer-rdv/',
            {'confirme': True, 'date_prevue': '2026-07-15'},
            format='json')
        self.assertEqual(r.status_code, 200)
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.rdv_reschedule_count, 1)
        self.assertEqual(str(self.interv.date_prevue), '2026-07-15')

    def test_deconfirmer_rdv(self):
        """FG78 — confirme=false remet rdv_confirme à False."""
        self.interv.rdv_confirme = True
        self.interv.save()
        r = self.api.post(
            f'/api/django/installations/interventions/{self.interv.id}/confirmer-rdv/',
            {'confirme': False},
            format='json')
        self.assertEqual(r.status_code, 200)
        self.interv.refresh_from_db()
        self.assertFalse(self.interv.rdv_confirme)

    def test_confirmer_rdv_company_isolation(self):
        """FG78 — autre société → 404."""
        company2 = make_company()
        user2 = User.objects.create_user(
            username='fg78_other', password='x', role_legacy='responsable',
            company=company2)
        api2 = auth(user2)
        r = api2.post(
            f'/api/django/installations/interventions/{self.interv.id}/confirmer-rdv/',
            {'confirme': True},
            format='json')
        self.assertIn(r.status_code, [403, 404])


# ── FG79 — scaffold interventions standard ────────────────────────────────────

class TestFG79InterventionPlan(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg79_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user,
                                  type_installation='residentiel')
        # Crée un plan standard pour résidentiel
        TypeInterventionPlan.objects.create(
            company=self.company, type_installation='residentiel',
            type_intervention_cle='pose', libelle_contexte='Pose des panneaux',
            ordre=1)
        TypeInterventionPlan.objects.create(
            company=self.company, type_installation='residentiel',
            type_intervention_cle='raccordement', libelle_contexte='Raccordement',
            ordre=2)

    def test_creer_interventions_standard(self):
        """FG79 — creer-interventions-standard crée les interventions du plan."""
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/'
            f'creer-interventions-standard/',
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data['created']), 2)
        self.assertEqual(r.data['existants'], [])
        types = {iv['type_intervention'] for iv in r.data['created']}
        self.assertEqual(types, {'pose', 'raccordement'})

    def test_creer_interventions_standard_idempotent(self):
        """FG79 — appel répété ne recrée pas les types déjà présents."""
        self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/'
            f'creer-interventions-standard/',
            format='json')
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/'
            f'creer-interventions-standard/',
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['created'], [])
        self.assertEqual(set(r.data['existants']), {'pose', 'raccordement'})

    def test_no_plan_returns_empty(self):
        """FG79 — pas de plan → 200 avec listes vides."""
        inst2 = make_chantier(self.company, self.user,
                              type_installation='agricole')
        r = self.api.post(
            f'/api/django/installations/chantiers/{inst2.id}/'
            f'creer-interventions-standard/',
            format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['created'], [])

    def test_plan_company_isolation(self):
        """FG79 — plan d'une autre société n'est pas utilisé."""
        company2 = make_company()
        user2 = User.objects.create_user(
            username='fg79_other', password='x', role_legacy='responsable',
            company=company2)
        inst2 = make_chantier(company2, user2, type_installation='residentiel')
        # Le plan de company1 ne devrait pas s'appliquer à company2
        api2 = auth(user2)
        r = api2.post(
            f'/api/django/installations/chantiers/{inst2.id}/'
            f'creer-interventions-standard/',
            format='json')
        self.assertEqual(r.status_code, 200)
        # company2 n'a pas de plan → 0 créations
        self.assertEqual(r.data['created'], [])


# ── FG80 — calibration outillage ─────────────────────────────────────────────

class TestFG80Calibration(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg80_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.outil = Outillage.objects.create(
            company=self.company, nom='Multimètre Fluke 117',
            categorie='Mesure', intervalle_calibration_mois=12)

    def test_calibrer_stores_date(self):
        """FG80 — POST calibrer enregistre date_derniere_calibration."""
        r = self.api.post(
            f'/api/django/outillage/outils/{self.outil.id}/calibrer/',
            {'date_calibration': '2026-06-21'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.outil.refresh_from_db()
        self.assertEqual(str(self.outil.date_derniere_calibration), '2026-06-21')

    def test_calibrer_calculates_next_date(self):
        """FG80 — calibrer calcule date_prochaine_calibration (intervalle 12 mois)."""
        r = self.api.post(
            f'/api/django/outillage/outils/{self.outil.id}/calibrer/',
            {'date_calibration': '2026-01-01'},
            format='json')
        self.assertEqual(r.status_code, 200)
        self.outil.refresh_from_db()
        self.assertIsNotNone(self.outil.date_prochaine_calibration)
        # ~365 jours après = 2027-01 environ
        self.assertGreater(self.outil.date_prochaine_calibration,
                           datetime.date(2026, 12, 1))

    def test_a_calibrer_badge(self):
        """FG80 — a_calibrer=True quand date_prochaine est dépassée."""
        self.outil.date_derniere_calibration = datetime.date(2024, 1, 1)
        self.outil.date_prochaine_calibration = datetime.date(2025, 1, 1)
        self.outil.save()
        r = self.api.get(
            f'/api/django/outillage/outils/{self.outil.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['a_calibrer'])

    def test_a_calibrer_false_when_recent(self):
        """FG80 — a_calibrer=False quand la prochaine calibration est dans le futur."""
        future = datetime.date.today() + datetime.timedelta(days=180)
        self.outil.date_prochaine_calibration = future
        self.outil.save()
        r = self.api.get(
            f'/api/django/outillage/outils/{self.outil.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['a_calibrer'])

    def test_filter_a_calibrer(self):
        """FG80 — ?a_calibrer=1 ne renvoie que les outils à calibrer."""
        # Outil à calibrer : date dépassée
        outil_overdue = Outillage.objects.create(
            company=self.company, nom='Testeur terre',
            intervalle_calibration_mois=6,
            date_prochaine_calibration=datetime.date(2025, 1, 1))
        # Outil pas à calibrer : date future
        outil_ok = Outillage.objects.create(
            company=self.company, nom='Perceuse',
            intervalle_calibration_mois=0)
        r = self.api.get('/api/django/outillage/outils/', {'a_calibrer': '1'})
        self.assertEqual(r.status_code, 200)
        ids = [o['id'] for o in r.data['results']]
        self.assertIn(outil_overdue.id, ids)
        self.assertNotIn(outil_ok.id, ids)

    def test_calibrer_default_date_today(self):
        """FG80 — calibrer sans date utilise aujourd'hui."""
        r = self.api.post(
            f'/api/django/outillage/outils/{self.outil.id}/calibrer/',
            {},
            format='json')
        self.assertEqual(r.status_code, 200)
        self.outil.refresh_from_db()
        self.assertEqual(self.outil.date_derniere_calibration, datetime.date.today())

    def test_calibrer_company_isolation(self):
        """FG80 — autre société ne peut pas calibrer."""
        company2 = make_company()
        user2 = User.objects.create_user(
            username='fg80_other', password='x', role_legacy='responsable',
            company=company2)
        api2 = auth(user2)
        r = api2.post(
            f'/api/django/outillage/outils/{self.outil.id}/calibrer/',
            {'date_calibration': '2026-06-21'},
            format='json')
        self.assertIn(r.status_code, [403, 404])
