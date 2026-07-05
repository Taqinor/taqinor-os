"""XMKT6 — Segments dynamiques enregistrés et réutilisables.

Couvre : un segment sauvegardé se réévalue à chaque usage (jamais mis en
cache), la préview renvoie le compte exact, ciblage lead par ville/type/
tags/canal/score, activité marketing (a_ouvert/a_clique/jamais_ouvert) via
EnvoiCampagne (XMKT2), validation stricte des règles inconnues, isolation
multi-tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Campagne, EnvoiCampagne, SegmentMarketing
from apps.crm.models import Lead

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_lead(co, nom, **kwargs):
    return Lead.objects.create(company=co, nom=nom, **kwargs)


class SegmentMarketingTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt6', 'XMKT6')
        self.user = make_user(self.co, 'xmkt6-user')

    def test_evaluer_segment_filtre_par_ville(self):
        make_lead(self.co, 'A', ville='Casablanca')
        make_lead(self.co, 'B', ville='Rabat')
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='Casa', regles={'ville': 'casablanca'})
        ids = services.evaluer_segment(segment)
        self.assertEqual(len(ids), 1)

    def test_evaluer_segment_filtre_par_tags(self):
        make_lead(self.co, 'A', tags='VIP, Regularisation 82-21')
        make_lead(self.co, 'B', tags='froid')
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='VIP', regles={'tags': 'VIP'})
        ids = services.evaluer_segment(segment)
        self.assertEqual(len(ids), 1)

    def test_evaluer_segment_filtre_par_score(self):
        make_lead(self.co, 'A', score=80)
        make_lead(self.co, 'B', score=10)
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='HotScore', regles={'score': {'gte': 50}})
        ids = services.evaluer_segment(segment)
        self.assertEqual(len(ids), 1)

    def test_segment_reevalue_a_chaque_usage(self):
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='Casa', regles={'ville': 'casablanca'})
        self.assertEqual(len(services.evaluer_segment(segment)), 0)
        make_lead(self.co, 'A', ville='Casablanca')
        # Un nouveau lead créé APRÈS le segment doit apparaître au réévaluation.
        self.assertEqual(len(services.evaluer_segment(segment)), 1)

    def test_activite_a_ouvert(self):
        lead = make_lead(self.co, 'A', ville='Casablanca')
        autre_lead = make_lead(self.co, 'B', ville='Casablanca')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='a@x.ma',
            contact_ref=f'lead:{lead.id}', statut=EnvoiCampagne.Statut.OUVERT,
            ouvert_le=services.timezone.now())
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='b@x.ma',
            contact_ref=f'lead:{autre_lead.id}',
            statut=EnvoiCampagne.Statut.ENVOYE)
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='Ouverts',
            regles={'ville': 'casablanca', 'activite': 'a_ouvert'})
        ids = services.evaluer_segment(segment)
        self.assertEqual(ids, [lead.id])

    def test_activite_jamais_ouvert(self):
        lead_ouvert = make_lead(self.co, 'A')
        lead_jamais = make_lead(self.co, 'B')
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='a@x.ma',
            contact_ref=f'lead:{lead_ouvert.id}',
            statut=EnvoiCampagne.Statut.OUVERT, ouvert_le=services.timezone.now())
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='JamaisOuvert', regles={'activite': 'jamais_ouvert'})
        ids = services.evaluer_segment(segment)
        self.assertIn(lead_jamais.id, ids)
        self.assertNotIn(lead_ouvert.id, ids)

    def test_regle_inconnue_leve_erreur(self):
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='Bad', regles={'champ_inconnu': 'x'})
        with self.assertRaises(ValueError):
            services.evaluer_segment(segment)

    def test_previsualiser_compte_exact(self):
        make_lead(self.co, 'A', ville='Casablanca')
        make_lead(self.co, 'B', ville='Casablanca')
        make_lead(self.co, 'C', ville='Rabat')
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='Casa', regles={'ville': 'casablanca'})
        preview = services.previsualiser_segment(segment)
        self.assertEqual(preview['count'], 2)
        self.assertEqual(len(preview['echantillon']), 2)

    def test_isolation_multi_tenant(self):
        other = make_company('xmkt6-b', 'XMKT6-B')
        make_lead(self.co, 'A', ville='Casablanca')
        make_lead(other, 'B', ville='Casablanca')
        segment = SegmentMarketing.objects.create(
            company=self.co, nom='Casa', regles={'ville': 'casablanca'})
        self.assertEqual(len(services.evaluer_segment(segment)), 1)


class SegmentMarketingApiTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt6-api', 'XMKT6 API')
        self.user = make_user(self.co, 'xmkt6-api-user')

    def test_creation_rejette_regle_inconnue(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/segments-marketing/', {
            'nom': 'Bad', 'regles': {'champ_inconnu': 'x'},
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_previsualiser_endpoint(self):
        make_lead(self.co, 'A', ville='Casablanca')
        api = auth(self.user)
        resp = api.post('/api/django/compta/segments-marketing/', {
            'nom': 'Casa', 'regles': {'ville': 'casablanca'},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        seg_id = resp.data['id']
        resp2 = api.get(
            f'/api/django/compta/segments-marketing/{seg_id}/previsualiser/')
        self.assertEqual(resp2.status_code, 200, resp2.content)
        self.assertEqual(resp2.data['count'], 1)
