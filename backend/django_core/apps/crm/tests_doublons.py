"""
FEATURE 1 — atelier doublons + fusion N-aire.

Le moteur de fusion (services.merge_leads) accepte déjà une LISTE d'absorbés et
archive sans perte. Ces tests couvrent :
  - le rapprochement global (find_duplicate_clusters) par téléphone / email /
    nom normalisé, borné au tenant ;
  - l'endpoint GET /crm/leads/doublons/ (clusters + survivant suggéré) ;
  - la fusion de 3 leads d'un coup via POST /crm/leads/<survivant>/merge/.

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_doublons -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.crm.services import (
    find_duplicate_clusters, normalize_name, normalize_phone)
from apps.ventes.models import Devis

User = get_user_model()


def make_company(slug='doublons-co', nom='Doublons Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestNormalisation(TestCase):
    def test_phone_variants_collapse(self):
        for v in ('+212 6 12-34-56-78', '0612345678', '00212612345678'):
            self.assertEqual(normalize_phone(v), '612345678')

    def test_name_accents_and_order(self):
        self.assertEqual(
            normalize_name('Bélkacem', 'Ali'),
            normalize_name('belkacem', 'ALI'))
        self.assertEqual(normalize_name('Ali', 'Belkacem'),
                         normalize_name('Belkacem', 'Ali'))

    def test_name_too_short_is_empty(self):
        self.assertEqual(normalize_name('Ali'), '')  # 3 lettres → pas de clé


class TestClusters(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_phone_clusters(self):
        a = Lead.objects.create(company=self.company, nom='Aziz',
                                telephone='0612345678')
        b = Lead.objects.create(company=self.company, nom='Aziz B',
                                telephone='+212 612 34 56 78')
        Lead.objects.create(company=self.company, nom='Autre',
                            telephone='0699999999')
        clusters, _ = find_duplicate_clusters(self.company)
        self.assertEqual(len(clusters), 1)
        ids = {le.id for le in clusters[0]}
        self.assertEqual(ids, {a.id, b.id})

    def test_email_clusters(self):
        a = Lead.objects.create(company=self.company, nom='X',
                                email='Foo@Example.com')
        b = Lead.objects.create(company=self.company, nom='Y',
                                email='foo@example.com ')
        clusters, _ = find_duplicate_clusters(self.company)
        self.assertEqual({le.id for le in clusters[0]}, {a.id, b.id})

    def test_name_clusters(self):
        a = Lead.objects.create(company=self.company, nom='Belkacem',
                                prenom='Ali')
        b = Lead.objects.create(company=self.company, nom='belkacem ali')
        clusters, _ = find_duplicate_clusters(self.company)
        self.assertEqual({le.id for le in clusters[0]}, {a.id, b.id})

    def test_transitive_union(self):
        # A~B par téléphone, B~C par email → un seul cluster {A,B,C}.
        a = Lead.objects.create(company=self.company, nom='A',
                                telephone='0612345678')
        b = Lead.objects.create(company=self.company, nom='B',
                                telephone='0612345678', email='b@x.com')
        c = Lead.objects.create(company=self.company, nom='C', email='b@x.com')
        clusters, _ = find_duplicate_clusters(self.company)
        self.assertEqual(len(clusters), 1)
        self.assertEqual({le.id for le in clusters[0]}, {a.id, b.id, c.id})

    def test_archived_excluded_by_default(self):
        a = Lead.objects.create(company=self.company, nom='A',
                                telephone='0612345678')
        Lead.objects.create(company=self.company, nom='B',
                            telephone='0612345678', is_archived=True)
        clusters, _ = find_duplicate_clusters(self.company)
        self.assertEqual(clusters, [])  # un seul membre actif → pas de cluster
        clusters2, _ = find_duplicate_clusters(self.company,
                                               include_archived=True)
        self.assertEqual(len(clusters2), 1)
        self.assertIn(a.id, {le.id for le in clusters2[0]})

    def test_tenant_scoped(self):
        other = make_company(slug='doublons-other', nom='Other')
        Lead.objects.create(company=self.company, nom='A',
                            telephone='0612345678')
        Lead.objects.create(company=other, nom='A',
                            telephone='0612345678')
        clusters, _ = find_duplicate_clusters(self.company)
        self.assertEqual(clusters, [])  # le doublon est dans l'autre société


class TestDoublonsEndpoint(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='doublons_u', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)

    def test_endpoint_returns_cluster_with_suggested_survivor(self):
        # Le plus complet doit être suggéré comme survivant.
        poor = Lead.objects.create(company=self.company, nom='Riche',
                                   telephone='0612345678')
        rich = Lead.objects.create(
            company=self.company, nom='Riche', telephone='0612345678',
            email='riche@x.com', ville='Casa', societe='ACME',
            type_installation='residentiel', facture_hiver=700)
        resp = self.api.get('/api/django/crm/leads/doublons/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        cluster = resp.data[0]
        self.assertEqual(cluster['suggested_survivor_id'], rich.id)
        ids = {m['id'] for m in cluster['members']}
        self.assertEqual(ids, {poor.id, rich.id})


class TestNwayMerge(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='doublons_merge', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)

    def test_merge_three_leads_archives_others_and_fills_blanks(self):
        survivor = Lead.objects.create(company=self.company, nom='Survivant',
                                       telephone='0612345678')
        b = Lead.objects.create(company=self.company, nom='B',
                                email='b@x.com')          # comble l'email
        c = Lead.objects.create(company=self.company, nom='C', ville='Rabat')
        # Un devis sur chaque absorbé → doit suivre le survivant.
        client = Client.objects.create(company=self.company, nom='Cl',
                                       email='cl@x.com')
        Devis.objects.create(company=self.company, reference='D-B',
                             lead=b, client=client)
        Devis.objects.create(company=self.company, reference='D-C',
                             lead=c, client=client)

        resp = self.api.post(
            f'/api/django/crm/leads/{survivor.id}/merge/',
            {'others': [b.id, c.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        survivor.refresh_from_db()
        b.refresh_from_db()
        c.refresh_from_db()
        self.assertTrue(b.is_archived)
        self.assertTrue(c.is_archived)
        self.assertFalse(survivor.is_archived)
        # Champs vides comblés depuis les absorbés.
        self.assertEqual(survivor.email, 'b@x.com')
        self.assertEqual(survivor.ville, 'Rabat')
        # Aucun devis orphelin : les deux suivent le survivant.
        self.assertEqual(survivor.devis.count(), 2)
        self.assertEqual(Devis.objects.filter(lead=b).count(), 0)
        self.assertEqual(Devis.objects.filter(lead=c).count(), 0)


class TestDoublonsEndpointEnrichment(TestCase):
    """L'endpoint doublons expose match_keys, merge_preview et nb_activites."""

    def setUp(self):
        self.company = make_company('doublons-enrich', 'Doublons Enrich')
        self.user = User.objects.create_user(
            username='dbl_enrich', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)

    def test_match_keys_and_preview(self):
        from apps.crm.services import cluster_match_keys
        a = Lead.objects.create(
            company=self.company, nom='Alaoui', telephone='0612345678')
        b = Lead.objects.create(
            company=self.company, nom='Alaoui', telephone='0612345678',
            email='a@x.com', ville='Rabat')
        client = Client.objects.create(
            company=self.company, nom='Cl', email='cl@x.com')
        Devis.objects.create(company=self.company, reference='D-1',
                             lead=b, client=client)
        groups, _ = find_duplicate_clusters(self.company)
        # téléphone partagé → 'telephone' dans les clés de rapprochement.
        keys = cluster_match_keys([a, b])
        self.assertIn('telephone', keys)

        resp = self.api.get('/api/django/crm/leads/doublons/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data)
        cluster = resp.data[0]
        self.assertIn('match_keys', cluster)
        self.assertIn('telephone', cluster['match_keys'])
        self.assertIn('merge_preview', cluster)
        self.assertIn('devis', cluster['merge_preview'])
        # Chaque membre porte un compteur d'activités.
        for m in cluster['members']:
            self.assertIn('nb_activites', m)
