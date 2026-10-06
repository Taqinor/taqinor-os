"""ADOC69 — les documents de chantier suivent la portée de la fiche chantier.

Constat C-ADOC-037 (S2) : ``_get_chantier_or_404`` ne filtrait que la société
— un rôle restreint (``records_scope_equipe``) recevait 404 sur la fiche d'un
chantier hors portée mais 200 sur son PV, son BL, son dossier de remise et son
attestation (nom, téléphone, adresse du client, numéros de série). L'attestation
(signature de la société) était en plus servie à tout rôle.

Run :
    python manage.py test apps.documents.tests.test_adoc_portee_documents -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.roles.models import Role
from apps.roles.permissions_registre import SCOPE_TEAM
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
DOCS = '/api/django/documents/chantiers'
FICHE = '/api/django/installations/chantiers'
ROUTES = ('pv-reception', 'bon-livraison', 'dossier-remise', 'attestation')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PorteeDocumentsChantierTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'adoc69-co-{n}', nom=f'ADOC69 Co {n}')
        self.autre = Company.objects.create(
            slug=f'adoc69-autre-{n}', nom=f'ADOC69 Autre {n}')
        self.resp = User.objects.create_user(
            username=f'adoc69-resp-{n}', password='x',
            company=self.company, role_legacy='responsable')
        # A : rôle d'équipe AVEC droit d'écriture (passe IsResponsableOrAdmin)
        # mais ni technicien ni créateur du chantier X → hors portée.
        role_a = Role.objects.create(
            company=self.company, nom='Chef équipe restreint',
            permissions=[SCOPE_TEAM, 'installations_modifier'])
        self.user_a = User.objects.create_user(
            username=f'adoc69-a-{n}', password='x', company=self.company,
            role=role_a)
        # T : technicien de portée restreinte, lecture seule.
        role_t = Role.objects.create(
            company=self.company, nom='Technicien restreint',
            permissions=[SCOPE_TEAM, 'installations_voir'])
        self.tech = User.objects.create_user(
            username=f'adoc69-t-{n}', password='x', company=self.company,
            role=role_t)
        self.client_crm = Client.objects.create(
            company=self.company, nom='Idrissi', prenom='Nadia',
            telephone='+212600000069', adresse='3 rue Secret, Rabat')
        self.chantier_x = Installation.objects.create(
            company=self.company, reference=f'CH-ADOC69-X-{n}',
            client=self.client_crm, created_by=self.resp,
            technicien_responsable=self.resp,
            statut=Installation.Statut.INSTALLE)
        self.chantier_y = Installation.objects.create(
            company=self.company, reference=f'CH-ADOC69-Y-{n}',
            client=self.client_crm, created_by=self.resp,
            technicien_responsable=self.tech,
            statut=Installation.Statut.INSTALLE)

    def test_role_restreint_404_sur_les_quatre_documents(self):
        api = _api(self.user_a)
        self.assertEqual(
            api.get(f'{FICHE}/{self.chantier_x.pk}/').status_code, 404)
        for route in ROUTES:
            with self.subTest(route=route):
                r = api.get(f'{DOCS}/{self.chantier_x.pk}/{route}/')
                self.assertEqual(r.status_code, 404, route)
                self.assertNotIn(b'Idrissi', r.content)

    def test_technicien_obtient_ses_documents(self):
        api = _api(self.tech)
        for route in ('pv-reception', 'bon-livraison', 'dossier-remise'):
            with self.subTest(route=route):
                r = api.get(f'{DOCS}/{self.chantier_y.pk}/{route}/')
                self.assertEqual(r.status_code, 200, route)
                self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_attestation_reservee_responsable(self):
        r = _api(self.tech).get(
            f'{DOCS}/{self.chantier_y.pk}/attestation/')
        self.assertEqual(r.status_code, 403)
        r = _api(self.resp).get(
            f'{DOCS}/{self.chantier_y.pk}/attestation/')
        self.assertEqual(r.status_code, 200)

    def test_inter_societe_404_inchange(self):
        etranger = User.objects.create_user(
            username=f'adoc69-ext-{next(_seq)}', password='x',
            company=self.autre, role_legacy='responsable')
        api = _api(etranger)
        for route in ROUTES:
            with self.subTest(route=route):
                self.assertEqual(
                    api.get(f'{DOCS}/{self.chantier_x.pk}/{route}/')
                    .status_code, 404)

    def test_compte_portail_refuse(self):
        portail = User.objects.create_user(
            username=f'adoc69-portail-{next(_seq)}', password='x',
            company=self.company, portee='portail_client',
            portail_client_id=self.client_crm.pk)
        api = _api(portail)
        for route in ROUTES:
            with self.subTest(route=route):
                r = api.get(f'{DOCS}/{self.chantier_x.pk}/{route}/')
                self.assertIn(r.status_code, (403, 404))
                self.assertNotIn(b'Idrissi', r.content)
