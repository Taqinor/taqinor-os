"""Tests NTPRT37 — sélecteur de site (multi-chantiers B2B), portail CLIENT.

Filtre ADDITIF sur les écrans NTPRT9 (tableau de bord) et NTPRT15 (ma
consommation) : ``?chantier=<id>`` borne les widgets LIÉS À UN SITE
(``prochain_jalon``, ``alertes_ouvertes``) sans ajouter de donnée nouvelle.
Critère d'acceptation vérifié : changer de site ne recharge QUE les widgets
concernés — ``devis_en_attente``/``factures_impayees`` restent au niveau
CLIENT, jamais scindés par site.

Run :
    python manage.py test apps.portail.tests.test_ntprt37_site_selector -v2
"""
import datetime
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.portail.services import (
    provisionner_compte_portail_client, upsert_jalon_chantier,
)
from apps.ventes.models import Devis
from authentication.models import Company

_seq = itertools.count(1)

URL_TABLEAU = '/api/django/portail/client/tableau-de-bord/'
URL_CONSOMMATION = '/api/django/portail/client/ma-consommation/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client_crm(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom=f'NTPRT37-{n}',
        email=f'ntprt37-{company.id}-{n}@example.invalid')


def make_admin(company):
    client = make_client_crm(company)
    admin, _ = provisionner_compte_portail_client(company, client.id)
    admin.must_change_password = False
    admin.save(update_fields=['must_change_password'])
    return client, admin


def make_installation(company, client):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CH-NTPRT37-{n}', client=client,
        site_ville='Casablanca', annule=False)


class TableauDeBordSiteSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt37-co', 'NTPRT37 Société')
        self.client_crm, self.admin = make_admin(self.company)
        self.site_a = make_installation(self.company, self.client_crm)
        self.site_b = make_installation(self.company, self.client_crm)
        upsert_jalon_chantier(
            self.company, self.site_a.id, 'installation', 'Installation',
            atteint=False, date_jalon=datetime.date(2026, 10, 1))
        upsert_jalon_chantier(
            self.company, self.site_b.id, 'mise_en_service',
            'Mise en service', atteint=False,
            date_jalon=datetime.date(2026, 11, 1))
        # Un devis EN ATTENTE — doit rester compté quel que soit le site.
        Devis.objects.create(
            company=self.company, reference='DEV-NTPRT37-1',
            client=self.client_crm, statut=Devis.Statut.ENVOYE)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)

    def test_sans_filtre_jalon_le_plus_proche_tous_sites(self):
        res = self.api.get(URL_TABLEAU)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIsNotNone(res.data['prochain_jalon'])

    def test_filtre_chantier_borne_le_prochain_jalon_a_ce_site(self):
        res = self.api.get(URL_TABLEAU, {'chantier': self.site_b.id})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(
            res.data['prochain_jalon']['chantier_id'], self.site_b.id)
        self.assertEqual(
            res.data['prochain_jalon']['libelle'], 'Mise en service')

    def test_devis_en_attente_ignore_le_filtre_de_site(self):
        res_sans = self.api.get(URL_TABLEAU)
        res_avec = self.api.get(URL_TABLEAU, {'chantier': self.site_a.id})
        self.assertEqual(
            res_sans.data['devis_en_attente'],
            res_avec.data['devis_en_attente'])
        self.assertGreaterEqual(res_avec.data['devis_en_attente'], 1)

    def test_chantier_dun_autre_client_ignore_sans_fuite(self):
        autre_client = make_client_crm(self.company)
        autre_site = make_installation(self.company, autre_client)
        upsert_jalon_chantier(
            self.company, autre_site.id, 'installation', 'Site autrui',
            atteint=False)
        res = self.api.get(URL_TABLEAU, {'chantier': autre_site.id})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIsNone(res.data['prochain_jalon'])


class MaConsommationSiteSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt37-cons', 'NTPRT37 Consommation')
        self.client_crm, self.admin = make_admin(self.company)
        self.site_a = make_installation(self.company, self.client_crm)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)

    def test_filtre_chantier_valide_ne_casse_pas_lecran(self):
        res = self.api.get(URL_CONSOMMATION, {'chantier': self.site_a.id})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['alertes_ouvertes'], 0)

    def test_chantier_dun_autre_client_est_ignore(self):
        autre_client = make_client_crm(self.company)
        autre_site = make_installation(self.company, autre_client)
        res = self.api.get(URL_CONSOMMATION, {'chantier': autre_site.id})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['alertes_ouvertes'], 0)
