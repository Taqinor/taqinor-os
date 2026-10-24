"""FG270 — tests de l'éligibilité & du suivi des subventions/incitations.

Couvre : création (company forcée depuis le devis), isolation société, filtres
programme/statut, suivi des montants et des pièces (JSON).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg270_subvention -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis, SubventionDossier
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()


def make_company(slug):
    return Company.objects.create(nom=f'Co {slug}', slug=slug)


def make_user(company, name):
    return User.objects.create_user(
        username=name, password='x',
        role_legacy='responsable', company=company)


def make_devis(company, user, ref='DEV-FG270-1'):
    client = Client.objects.create(
        company=company, nom='Alaoui', prenom='Yassine',
        email=f'y_{company.slug}@example.com', telephone='+212622222222')
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='brouillon', created_by=user)


class SubventionDossierApiTest(TestCase):
    def setUp(self):
        self.company = make_company('subv-acme')
        self.other = make_company('subv-other')
        self.user = make_user(self.company, 'subv_user')
        self.devis = make_devis(self.company, self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = '/api/django/ventes/subventions/'

    def test_create_forces_company_and_tracks_montant(self):
        resp = self.api.post(self.url, {
            'devis': self.devis.id, 'programme': 'iresen',
            'statut': 'eligible', 'montant_demande': '25000.00',
            'pieces': [{'code': 'rc', 'label': 'RC', 'fourni': False}],
            'company': self.other.id,  # ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        subv = SubventionDossier.objects.get(id=resp.data['id'])
        self.assertEqual(subv.company_id, self.company.id)
        self.assertEqual(subv.montant_demande, Decimal('25000.00'))
        self.assertEqual(len(subv.pieces), 1)

    def test_corps_fuzz_pieces_liste_jamais_nulle(self):
        # CI M1 tour 3 (api-fuzz run 38295727060) — le ``JSONField`` publiait
        # ``pieces`` « toute valeur » puis refusait ``null`` (400 sur un corps
        # conforme). ``pieces`` est désormais une LISTE d'objets : ``null`` est
        # hors schéma (400), ``[]`` est accepté ; les décimaux et textes sont
        # stricts (un nombre JSON n'est plus converti en silence).
        corps = {'devis': self.devis.id, 'programme': 'masen',
                 'statut': 'a_qualifier', 'montant_demande': '0',
                 'montant_accorde': '0', 'reference': '',
                 'eligibilite_note': None, 'pieces': None,
                 'date_depot': '2000-01-01', 'date_decision': None}
        self.assertEqual(
            self.api.post(self.url, corps, format='json').status_code, 400)
        for champ, valeur in (('pieces', [1]), ('montant_demande', 0),
                              ('reference', 0)):
            with self.subTest(champ=champ):
                resp = self.api.post(self.url, {**corps, 'pieces': [],
                                                champ: valeur}, format='json')
                self.assertEqual(resp.status_code, 400, resp.content)
        self.assertFalse(SubventionDossier.objects.exists())
        resp = self.api.post(self.url, {**corps, 'pieces': []}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['pieces'], [])

    def test_devis_of_other_company_refused(self):
        other_user = make_user(self.other, 'subv_o')
        other_devis = make_devis(self.other, other_user, ref='DEV-OTHER-SUB')
        resp = self.api.post(self.url, {
            'devis': other_devis.id, 'programme': 'masen',
        }, format='json')
        # CI #997 fuzz (24/10) : id bien formé mais inconnu = 404.
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_filtres_stricts_et_pieces_normalisees(self):
        # CI #997 fuzz (24/10) : ``?devis=`` vide, ``?programme=`` hors liste
        # (dont le caractère nul, 500 avant) = 400 nommé ; des pièces au nul /
        # demi-substitut isolé sont normalisées, jamais une 500.
        for params in ({'devis': ''}, {'devis': 'abc'},
                       {'programme': 'inconnu'}, {'programme': 'm\x00'},
                       {'statut': ''}):
            with self.subTest(params=params):
                resp = self.api.get(self.url, params)
                self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.post(self.url, {
            'devis': self.devis.id, 'programme': 'masen',
            'pieces': [{'code': 'a\x00b', 'label': 'x\ud800y'}]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['pieces'],
                         [{'code': 'ab', 'label': 'x�y'}])

    def test_filter_by_programme_and_statut(self):
        SubventionDossier.objects.create(
            company=self.company, devis=self.devis, programme='masen',
            statut='accorde')
        SubventionDossier.objects.create(
            company=self.company, devis=self.devis, programme='tatwir',
            statut='depose')
        resp = self.api.get(self.url, {'programme': 'masen'})
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['programme'], 'masen')

    def test_list_scoped_to_company(self):
        SubventionDossier.objects.create(
            company=self.company, devis=self.devis, programme='iresen')
        other_user = make_user(self.other, 'subv_o2')
        other_devis = make_devis(self.other, other_user, ref='DEV-OTHER-SUB2')
        SubventionDossier.objects.create(
            company=self.other, devis=other_devis, programme='iresen')
        resp = self.api.get(self.url)
        rows = resp.data['results'] if isinstance(
            resp.data, dict) and 'results' in resp.data else resp.data
        for r in rows:
            self.assertEqual(
                SubventionDossier.objects.get(id=r['id']).company_id,
                self.company.id)
