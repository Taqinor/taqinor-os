"""Tests XQHS14 — Registre des risques & opportunités SMQ (ISO 6.1) +
contexte/parties intéressées (clause 4).

Couvre :

* la criticité inhérente/résiduelle calculée et stockée au save() ;
* la liaison CAPA idempotente ;
* la détection des revues dues ;
* PartieInteressee et ContexteOrganisation (1 par société) ;
* les actions API ``revues-dues``/``lier-capa`` (PACT183) ;
* le scoping société.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import (
    ActionCorrectivePreventive, ContexteOrganisation, NonConformite,
    PartieInteressee, RisqueOpportunite, RisqueOpportuniteCapa,
)
from apps.qhse.services import (
    lier_capa_risque_opportunite, risques_opportunites_revue_due,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return (data['results']
            if isinstance(data, dict) and 'results' in data else data)


class CriticiteCalculeeTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs14-crit', 'CoXqhs14Crit')

    def test_criticite_inherente_calculee(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Rupture fournisseur clé',
            probabilite_inherente=4, gravite_inherente=3)
        self.assertEqual(ro.criticite_inherente, 12)

    def test_criticite_residuelle_calculee_si_fournie(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque X',
            probabilite_inherente=4, gravite_inherente=3,
            probabilite_residuelle=2, gravite_residuelle=2)
        self.assertEqual(ro.criticite_residuelle, 4)

    def test_criticite_residuelle_none_sans_traitement(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque Y',
            probabilite_inherente=3, gravite_inherente=3)
        self.assertIsNone(ro.criticite_residuelle)


class LierCapaTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs14-capa', 'CoXqhs14Capa')
        self.ncr = NonConformite.objects.create(
            company=self.company, titre='NCR support')
        self.capa = ActionCorrectivePreventive.objects.create(
            company=self.company, non_conformite=self.ncr,
            description='Plan de mitigation')

    def test_lie_capa(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque lié')
        lien = lier_capa_risque_opportunite(ro, self.capa)
        self.assertIsInstance(lien, RisqueOpportuniteCapa)
        self.assertEqual(ro.capa_liees.count(), 1)

    def test_idempotent(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque lié 2')
        lier_capa_risque_opportunite(ro, self.capa)
        lier_capa_risque_opportunite(ro, self.capa)
        self.assertEqual(ro.capa_liees.count(), 1)


class RisquesOpportunitesRevueDueTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs14-due', 'CoXqhs14Due')

    def test_due_sans_date_revue(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Nouveau risque')
        dus = risques_opportunites_revue_due(self.company)
        self.assertIn(ro, dus)

    def test_pas_due_avant_frequence(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque récent',
            date_revue=date.today() - timedelta(days=10),
            frequence_revue_jours=180)
        dus = risques_opportunites_revue_due(self.company)
        self.assertNotIn(ro, dus)

    def test_due_apres_frequence_depassee(self):
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque ancien',
            date_revue=date.today() - timedelta(days=200),
            frequence_revue_jours=180)
        dus = risques_opportunites_revue_due(self.company)
        self.assertIn(ro, dus)

    def test_isolation_societe(self):
        autre = make_company('co-xqhs14-due-autre', 'CoXqhs14DueAutre')
        RisqueOpportunite.objects.create(
            company=self.company, description='Risque isolé')
        dus = risques_opportunites_revue_due(autre)
        self.assertEqual(dus, [])


class PartieInteresseeEtContexteTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs14-partie', 'CoXqhs14Partie')

    def test_cree_partie_interessee(self):
        partie = PartieInteressee.objects.create(
            company=self.company, partie='Client',
            attentes='Qualité et délais', pertinence=PartieInteressee.Pertinence.FORTE)
        self.assertEqual(partie.pertinence, PartieInteressee.Pertinence.FORTE)

    def test_contexte_unique_par_societe(self):
        ContexteOrganisation.objects.create(
            company=self.company, swot='Forces: équipe qualifiée')
        with self.assertRaises(Exception):
            ContexteOrganisation.objects.create(company=self.company, swot='Autre')


class RisqueOpportuniteApiTests(TestCase):
    """PACT183 — endpoint « revues dues » + action de liaison CAPA
    (``risques_opportunites_revue_due`` et ``lier_capa_risque_opportunite``
    n'avaient aucun appelant hors tests)."""

    REVUES_DUES_URL = '/api/django/qhse/risques-opportunites/revues-dues/'

    def setUp(self):
        self.company = make_company('co-xqhs14-api', 'CoXqhs14Api')
        self.user = User.objects.create_user(
            username='resp-xqhs14-api', password='x', company=self.company,
            role_legacy='responsable')

    def test_revues_dues_via_api(self):
        du = RisqueOpportunite.objects.create(
            company=self.company, description='Risque dû',
            date_revue=date.today() - timedelta(days=200),
            frequence_revue_jours=180)
        RisqueOpportunite.objects.create(
            company=self.company, description='Risque récent',
            date_revue=date.today() - timedelta(days=10),
            frequence_revue_jours=180)
        resp = auth_client(self.user).get(self.REVUES_DUES_URL)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], du.id)

    def test_lier_capa_via_api(self):
        ncr = NonConformite.objects.create(
            company=self.company, titre='NCR support API')
        capa = ActionCorrectivePreventive.objects.create(
            company=self.company, non_conformite=ncr,
            description='Plan de mitigation API')
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque à lier')
        url = f'/api/django/qhse/risques-opportunites/{ro.id}/lier-capa/'
        resp = auth_client(self.user).post(url, {'capa': capa.id})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(ro.capa_liees.count(), 1)

    def test_lier_capa_idempotent_via_api(self):
        ncr = NonConformite.objects.create(
            company=self.company, titre='NCR support API 2')
        capa = ActionCorrectivePreventive.objects.create(
            company=self.company, non_conformite=ncr,
            description='Plan de mitigation API 2')
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque à lier 2')
        url = f'/api/django/qhse/risques-opportunites/{ro.id}/lier-capa/'
        client = auth_client(self.user)
        client.post(url, {'capa': capa.id})
        client.post(url, {'capa': capa.id})
        self.assertEqual(
            RisqueOpportuniteCapa.objects.filter(
                risque_opportunite=ro, capa=capa).count(), 1)

    def test_lier_capa_autre_societe_404(self):
        autre = make_company('co-xqhs14-api-autre', 'CoXqhs14ApiAutre')
        ncr_autre = NonConformite.objects.create(
            company=autre, titre='NCR autre société')
        capa_autre = ActionCorrectivePreventive.objects.create(
            company=autre, non_conformite=ncr_autre,
            description='Plan autre société')
        ro = RisqueOpportunite.objects.create(
            company=self.company, description='Risque société A')
        url = f'/api/django/qhse/risques-opportunites/{ro.id}/lier-capa/'
        resp = auth_client(self.user).post(url, {'capa': capa_autre.id})
        self.assertEqual(resp.status_code, 404)
