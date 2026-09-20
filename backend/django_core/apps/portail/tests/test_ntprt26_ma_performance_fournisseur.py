"""Tests NTPRT26 — carte « Ma performance » du portail FOURNISSEUR
authentifié.

Monte ``stock.selectors.performance_portail_fournisseur`` sur
``GET /api/django/portail/ma-performance/`` (``apps.portail.views_externes.
ma_performance_fournisseur``). Vérifie l'isolation (portée EXACTE
fournisseur, jamais les chiffres d'un autre fournisseur ni d'un compte
client) et qu'un fournisseur SANS aucune réception contrôlée obtient un taux
de conformité ``None`` (jamais un faux zéro).

Run :
    python manage.py test \\
        apps.portail.tests.test_ntprt26_ma_performance_fournisseur -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    Role,
)
from apps.stock.models import Fournisseur
from authentication.models import Company, CustomUser

URL = '/api/django/portail/ma-performance/'

_seq = itertools.count(1)

_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_CLIENT: (
        ROLE_PORTAIL_CLIENT, 'portail_client_id', PORTAIL_CLIENT_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_portal_user(company, username, portee, scope_id):
    role_nom, champ, perms = _PORTAIL[portee]
    role, _ = Role.objects.get_or_create(
        company=company, nom=role_nom,
        defaults={'permissions': list(perms), 'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = portee
    setattr(user, champ, scope_id)
    user.save()
    return user


def make_fournisseur(company, nom='Fournisseur'):
    return Fournisseur.objects.create(
        company=company, nom=f'{nom}-{next(_seq)}')


class MaPerformanceFournisseurTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt26-co', 'NTPRT26 Société')
        self.f_a = make_fournisseur(self.company, 'Alpha')
        self.f_b = make_fournisseur(self.company, 'Beta')
        self.user_a = make_portal_user(
            self.company, 'ntprt26-f-a',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, self.f_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def test_carte_vide_sans_reception_controlee(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['fournisseur_nom'], self.f_a.nom)
        self.assertIsNone(res.data['taux_conformite_reception_pct'])
        self.assertEqual(res.data['receptions_controlees'], 0)

    def test_le_fournisseur_ne_voit_que_SON_nom(self):
        res = self.api.get(URL)
        self.assertNotIn(self.f_b.nom, str(res.data))

    def test_aucune_donnee_de_marge_ou_de_risque_interne(self):
        res = self.api.get(URL)
        for champ_interdit in ('montant', 'depenses', 'prix_achat',
                               'score_risque', 'chiffre_affaires'):
            self.assertNotIn(champ_interdit, res.data)

    def test_un_compte_client_est_refuse(self):
        client_user = make_portal_user(
            self.company, 'ntprt26-client', CustomUser.PORTEE_PORTAIL_CLIENT,
            None)
        api = APIClient()
        api.force_authenticate(user=client_user)
        res = api.get(URL)
        self.assertEqual(res.status_code, 403)

    def test_fournisseur_dune_autre_societe_carte_vide(self):
        autre = make_company('ntprt26-co-b', 'NTPRT26 Société B')
        autre_fournisseur = make_fournisseur(autre, 'Gamma')
        autre_user = make_portal_user(
            autre, 'ntprt26-f-c', CustomUser.PORTEE_PORTAIL_FOURNISSEUR,
            autre_fournisseur.id)
        api = APIClient()
        api.force_authenticate(user=autre_user)
        res = api.get(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['fournisseur_nom'], autre_fournisseur.nom)
