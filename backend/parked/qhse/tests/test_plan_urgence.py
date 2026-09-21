"""Tests QHSE28 — Plan d'urgence / premiers secours par chantier/site.

Couvre :
* CRUD scopé société pour ``PlanUrgence`` (``company`` posée côté serveur —
  jamais lue du corps) ;
* la lecture imbriquée des contacts d'urgence + secouristes + leurs compteurs ;
* les enfants ``ContactUrgence`` (pompiers/SAMU/police/interne) et
  ``Secouriste`` (salarié interne via ``rh.DossierEmploye`` OU nom libre
  externe), avec garde-fou même-société sur les FK ``plan`` / ``secouriste`` ;
* filtres ``?chantier_id=`` / ``?statut=`` / ``?plan=`` / ``?type_contact=`` ;
* garde-fou de rôle (IsResponsableOrAdmin → 403 pour un rôle normal) ;
* isolation entre sociétés (liste filtrée, détail 404 hors société).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import ContactUrgence, PlanUrgence, Secouriste
from apps.rh.models import DossierEmploye

User = get_user_model()

URL = '/api/django/qhse/plans-urgence/'
URL_CONTACTS = '/api/django/qhse/contacts-urgence/'
URL_SECOURISTES = '/api/django/qhse/secouristes/'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return (data['results']
            if isinstance(data, dict) and 'results' in data else data)


def make_employe(company, matricule='M001', prenom='Karim', nom='Bennani'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, prenom=prenom, nom=nom)


def make_plan(company, titre='Plan chantier A', **kwargs):
    return PlanUrgence.objects.create(
        company=company, titre=titre, **kwargs)


# ── API : CRUD scopé société ─────────────────────────────────────────────────

class PlanUrgenceApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-planurg-api', 'CoPlanUrgApi')
        self.other_company = make_company('co-planurg-api-2', 'CoPlanUrgApi2')
        self.user = make_user(self.company, 'planurg-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'planurg-resp-2')
        self.other_client = auth_client(self.other_user)

    def test_creation_pose_company_cote_serveur(self):
        resp = self.client_api.post(
            URL,
            {'titre': 'Plan site Casablanca', 'chantier_id': 7,
             'point_rassemblement': 'Parking nord',
             'hopital_proche': 'CHU Ibn Rochd',
             'hopital_distance_km': '3.50',
             'hopital_telephone': '0522-22-22-22',
             'statut': 'actif', 'date_revision': '2026-06-15'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        plan = PlanUrgence.objects.get(id=resp.data['id'])
        self.assertEqual(plan.company, self.company)
        self.assertEqual(plan.titre, 'Plan site Casablanca')
        self.assertEqual(plan.chantier_id, 7)
        self.assertEqual(plan.point_rassemblement, 'Parking nord')
        self.assertEqual(plan.statut, 'actif')

    def test_company_jamais_lue_du_corps(self):
        resp = self.client_api.post(
            URL,
            {'titre': 'X', 'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        plan = PlanUrgence.objects.get(id=resp.data['id'])
        self.assertEqual(plan.company, self.company)

    def test_statut_par_defaut_brouillon(self):
        resp = self.client_api.post(URL, {'titre': 'Sans statut'},
                                    format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        plan = PlanUrgence.objects.get(id=resp.data['id'])
        self.assertEqual(plan.statut, 'brouillon')

    def test_lecture_imbriquee_contacts_secouristes(self):
        plan = make_plan(self.company)
        ContactUrgence.objects.create(
            company=self.company, plan=plan, type_contact='pompiers',
            nom='Protection civile', telephone='15')
        Secouriste.objects.create(
            company=self.company, plan=plan, nom='Ali Externe')
        resp = self.client_api.get(f'{URL}{plan.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_contacts'], 1)
        self.assertEqual(resp.data['nb_secouristes'], 1)
        self.assertEqual(len(resp.data['contacts']), 1)
        self.assertEqual(
            resp.data['contacts'][0]['type_contact'], 'pompiers')
        self.assertEqual(len(resp.data['secouristes']), 1)

    def test_update_et_delete(self):
        plan = make_plan(self.company)
        patch = self.client_api.patch(
            f'{URL}{plan.id}/', {'statut': 'archive'}, format='json')
        self.assertEqual(patch.status_code, 200, patch.data)
        plan.refresh_from_db()
        self.assertEqual(plan.statut, 'archive')
        delete = self.client_api.delete(f'{URL}{plan.id}/')
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(PlanUrgence.objects.filter(id=plan.id).exists())

    # ── Filtres ──────────────────────────────────────────────────────────────

    def test_filtre_chantier_id(self):
        make_plan(self.company, chantier_id=1)
        make_plan(self.company, chantier_id=2)
        resp = self.client_api.get(URL, {'chantier_id': 2})
        ids = [r['chantier_id'] for r in rows(resp)]
        self.assertEqual(ids, [2])

    def test_filtre_statut(self):
        make_plan(self.company, statut='actif')
        make_plan(self.company, statut='brouillon')
        resp = self.client_api.get(URL, {'statut': 'actif'})
        statuts = [r['statut'] for r in rows(resp)]
        self.assertEqual(statuts, ['actif'])

    # ── Rôle + isolation société ─────────────────────────────────────────────

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'planurg-normal', role='normal')
        resp = auth_client(normal).get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_liste(self):
        make_plan(self.company, titre='Mien')
        make_plan(self.other_company, titre='Autre')
        resp = self.other_client.get(URL)
        ids = {r['id'] for r in rows(resp)}
        self.assertEqual(
            ids,
            set(PlanUrgence.objects.filter(
                company=self.other_company).values_list('id', flat=True)))

    def test_isolation_societe_detail_404(self):
        plan = make_plan(self.company)
        resp = self.other_client.get(f'{URL}{plan.id}/')
        self.assertEqual(resp.status_code, 404)


# ── API : ContactUrgence ─────────────────────────────────────────────────────

class ContactUrgenceApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-conturg-api', 'CoContUrgApi')
        self.other_company = make_company('co-conturg-api-2', 'CoContUrgApi2')
        self.user = make_user(self.company, 'conturg-resp')
        self.client_api = auth_client(self.user)
        self.plan = make_plan(self.company)
        self.other_plan = make_plan(self.other_company)

    def test_creation_contact_pose_company(self):
        resp = self.client_api.post(
            URL_CONTACTS,
            {'plan': self.plan.id, 'type_contact': 'samu',
             'nom': 'SAMU', 'telephone': '141'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        contact = ContactUrgence.objects.get(id=resp.data['id'])
        self.assertEqual(contact.company, self.company)
        self.assertEqual(contact.plan_id, self.plan.id)
        self.assertEqual(contact.type_contact, 'samu')

    def test_plan_autre_societe_refuse(self):
        resp = self.client_api.post(
            URL_CONTACTS,
            {'plan': self.other_plan.id, 'nom': 'X', 'telephone': '1'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_filtre_plan_et_type(self):
        ContactUrgence.objects.create(
            company=self.company, plan=self.plan, type_contact='pompiers',
            nom='Pompiers', telephone='15')
        ContactUrgence.objects.create(
            company=self.company, plan=self.plan, type_contact='police',
            nom='Police', telephone='19')
        resp = self.client_api.get(
            URL_CONTACTS, {'plan': self.plan.id, 'type_contact': 'police'})
        noms = [r['nom'] for r in rows(resp)]
        self.assertEqual(noms, ['Police'])

    def test_isolation_societe_detail_404(self):
        contact = ContactUrgence.objects.create(
            company=self.company, plan=self.plan, nom='Mien', telephone='1')
        other_user = make_user(self.other_company, 'conturg-resp-2')
        resp = auth_client(other_user).get(f'{URL_CONTACTS}{contact.id}/')
        self.assertEqual(resp.status_code, 404)


# ── API : Secouriste ─────────────────────────────────────────────────────────

class SecouristeApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-secour-api', 'CoSecourApi')
        self.other_company = make_company('co-secour-api-2', 'CoSecourApi2')
        self.user = make_user(self.company, 'secour-resp')
        self.client_api = auth_client(self.user)
        self.plan = make_plan(self.company)
        self.other_plan = make_plan(self.other_company)

    def test_secouriste_interne_relie(self):
        emp = make_employe(self.company)
        resp = self.client_api.post(
            URL_SECOURISTES,
            {'plan': self.plan.id, 'secouriste': emp.id,
             'certification': 'SST 2026', 'validite': '2028-06-01'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        sec = Secouriste.objects.get(id=resp.data['id'])
        self.assertEqual(sec.company, self.company)
        self.assertEqual(sec.secouriste_id, emp.id)
        self.assertEqual(sec.certification, 'SST 2026')

    def test_secouriste_externe_nom_libre(self):
        resp = self.client_api.post(
            URL_SECOURISTES,
            {'plan': self.plan.id, 'nom': 'Hicham Externe',
             'telephone': '0600-00-00-00'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        sec = Secouriste.objects.get(id=resp.data['id'])
        self.assertIsNone(sec.secouriste_id)
        self.assertEqual(sec.nom, 'Hicham Externe')

    def test_secouriste_autre_societe_refuse(self):
        emp_autre = make_employe(self.other_company, matricule='M999')
        resp = self.client_api.post(
            URL_SECOURISTES,
            {'plan': self.plan.id, 'secouriste': emp_autre.id},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_plan_autre_societe_refuse(self):
        resp = self.client_api.post(
            URL_SECOURISTES,
            {'plan': self.other_plan.id, 'nom': 'X'},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_filtre_plan(self):
        Secouriste.objects.create(
            company=self.company, plan=self.plan, nom='A')
        autre_plan = make_plan(self.company, titre='Plan B')
        Secouriste.objects.create(
            company=self.company, plan=autre_plan, nom='B')
        resp = self.client_api.get(URL_SECOURISTES, {'plan': self.plan.id})
        noms = [r['nom'] for r in rows(resp)]
        self.assertEqual(noms, ['A'])

    def test_isolation_societe_detail_404(self):
        sec = Secouriste.objects.create(
            company=self.company, plan=self.plan, nom='Mien')
        other_user = make_user(self.other_company, 'secour-resp-2')
        resp = auth_client(other_user).get(f'{URL_SECOURISTES}{sec.id}/')
        self.assertEqual(resp.status_code, 404)
