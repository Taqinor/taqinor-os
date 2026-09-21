"""Tests QHSE37 — RecyclageModule (fin de vie des modules PV).

Couvre :
* CRUD scopé société (``company`` / ``reference`` posées côté serveur) ;
* FK ``bordereau`` (BSD QHSE36) validé même-société ;
* transitions ``transporter`` / ``recycler`` + garde-fous ;
* filtres, rôle, isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    BordereauSuiviDechet, Dechet, RecyclageModule,
)

User = get_user_model()

REC_URL = '/api/django/qhse/recyclage-modules/'


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


def make_recyclage(company, reference='REC-202606-0001', statut='collecte',
                   motif='fin_de_vie', nombre_modules=10, chantier_id=None):
    return RecyclageModule.objects.create(
        company=company, reference=reference, statut=statut, motif=motif,
        nombre_modules=nombre_modules, chantier_id=chantier_id)


class RecyclageModuleApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-rec', 'CoRec')
        self.other_company = make_company('co-rec-2', 'CoRec2')
        self.user = make_user(self.company, 'rec-resp')
        self.client_api = auth_client(self.user)
        self.other_user = make_user(self.other_company, 'rec-resp-2')
        self.other_client = auth_client(self.other_user)

    def test_creation_company_et_reference(self):
        resp = self.client_api.post(
            REC_URL,
            {'marque': 'JinkoSolar', 'nombre_modules': 24,
             'motif': 'declassement', 'company': self.other_company.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        rec = RecyclageModule.objects.get(id=resp.data['id'])
        self.assertEqual(rec.company, self.company)
        self.assertEqual(rec.statut, 'collecte')
        self.assertTrue(rec.reference.startswith('REC-'))

    def test_bordereau_meme_societe(self):
        dechet = Dechet.objects.create(
            company=self.other_company, libelle='Batterie',
            categorie='dangereux')
        bsd = BordereauSuiviDechet.objects.create(
            company=self.other_company, dechet=dechet,
            reference='BSD-202606-0001')
        resp = self.client_api.post(
            REC_URL, {'marque': 'X', 'bordereau': bsd.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_transporter_puis_recycler(self):
        rec = make_recyclage(self.company)
        r1 = self.client_api.post(
            f'{REC_URL}{rec.id}/transporter/', {}, format='json')
        self.assertEqual(r1.status_code, 200, r1.data)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, 'transporte')
        r2 = self.client_api.post(
            f'{REC_URL}{rec.id}/recycler/', {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, 'recycle')
        self.assertIsNotNone(rec.date_recyclage)

    def test_recycler_refuse_si_deja_recycle(self):
        rec = make_recyclage(self.company, statut='recycle')
        resp = self.client_api.post(
            f'{REC_URL}{rec.id}/recycler/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_filtre_statut(self):
        make_recyclage(self.company, reference='REC-202606-0001',
                       statut='collecte')
        make_recyclage(self.company, reference='REC-202606-0002',
                       statut='recycle')
        resp = self.client_api.get(REC_URL, {'statut': 'recycle'})
        statuts = [r['statut'] for r in rows(resp)]
        self.assertEqual(statuts, ['recycle'])

    def test_filtre_motif(self):
        make_recyclage(self.company, reference='REC-202606-0001',
                       motif='casse')
        make_recyclage(self.company, reference='REC-202606-0002',
                       motif='fin_de_vie')
        resp = self.client_api.get(REC_URL, {'motif': 'casse'})
        motifs = [r['motif'] for r in rows(resp)]
        self.assertEqual(motifs, ['casse'])

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'rec-normal', role='normal')
        resp = auth_client(normal).get(REC_URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_societe_detail_404(self):
        rec = make_recyclage(self.company)
        resp = self.other_client.get(f'{REC_URL}{rec.id}/')
        self.assertEqual(resp.status_code, 404)
