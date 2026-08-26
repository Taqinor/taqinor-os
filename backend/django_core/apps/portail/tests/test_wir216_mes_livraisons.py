"""Tests WIR216 — « Mes livraisons » : le lien mort expédié par
``apps.installations.livraison_client_notify`` (FG228/XSTK22) pointait vers
une section portail INEXISTANTE (``/portail/livraisons/<id>``, 404 systématique).

Deux volets :

1. ISOLATION — même patron que NTPRT10/NTPRT11 : un compte portail ne voit
   QUE les livraisons des chantiers de SON client (jamais celles d'un autre
   client de la même société, jamais d'une autre société, jamais un compte
   portail fournisseur), et ``cout_transport`` (interne) ne fuit JAMAIS.
2. LIEN — ``_livraison_lien`` pointe désormais vers
   ``/portail/client/livraisons`` (la liste, jamais un id de livraison
   fabriqué dans l'URL — le scope réel vient du compte portail connecté).

Run :
    python manage.py test apps.portail.tests.test_wir216_mes_livraisons -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.livraison_client_notify import _livraison_lien
from apps.installations.models import Installation, Livraison, LivraisonLigne
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    Role,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'WIR216-{n}',
        email=f'wir216-{company.id}-{n}@example.invalid')


def make_installation(company, client):
    n = next(_seq)
    return Installation.objects.create(
        company=company, client=client, reference=f'CH-WIR216-{n}')


def make_livraison(company, installation, **kwargs):
    n = next(_seq)
    defaults = dict(
        company=company, installation=installation,
        reference=f'LIV-WIR216-{n}')
    defaults.update(kwargs)
    return Livraison.objects.create(**defaults)


_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_CLIENT: (
        ROLE_PORTAIL_CLIENT, 'portail_client_id', PORTAIL_CLIENT_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}


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


class LienNotificationLivraisonTests(TestCase):
    """WIR216 — le lien de l'email pointe vers la LISTE (scopée serveur),
    jamais un id de livraison fabriqué dans l'URL."""

    def test_lien_pointe_vers_mes_livraisons_jamais_un_id(self):
        company = make_company('wir216-lien-co', 'WIR216 Lien')
        client_crm = make_client(company)
        installation = make_installation(company, client_crm)
        livraison = make_livraison(company, installation)

        lien = _livraison_lien(livraison)

        self.assertEqual(lien, '/portail/client/livraisons')
        self.assertNotIn('/portail/livraisons/', lien)
        self.assertNotIn(str(livraison.id), lien)


class MesLivraisonsIsolationTests(TestCase):
    def setUp(self):
        self.company = make_company('wir216-co-a', 'WIR216 Société A')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.inst_a = make_installation(self.company, self.client_a)
        self.inst_b = make_installation(self.company, self.client_b)
        self.livraison_a = make_livraison(
            self.company, self.inst_a, numero_suivi='TRACK-A',
            cout_transport=500)
        LivraisonLigne.objects.create(
            livraison=self.livraison_a, designation='Panneau 550W',
            quantite=10)
        self.livraison_b = make_livraison(self.company, self.inst_b)
        self.user_a = make_portal_user(
            self.company, 'wir216-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.api = APIClient()

    def test_liste_bornee_au_client_rattache(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-livraisons/')

        self.assertEqual(res.status_code, 200, res.data)
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertIn(self.livraison_a.id, ids)
        self.assertNotIn(self.livraison_b.id, ids)

    def test_articles_et_numero_suivi_exposes(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-livraisons/')
        ligne = next(
            r for r in res.data['results'] if r['id'] == self.livraison_a.id)
        self.assertEqual(ligne['numero_suivi'], 'TRACK-A')
        self.assertEqual(len(ligne['articles']), 1)
        self.assertEqual(ligne['articles'][0]['designation'], 'Panneau 550W')
        self.assertEqual(ligne['articles'][0]['quantite'], 10)

    def test_cout_transport_ne_fuit_jamais(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-livraisons/')
        self.assertNotIn('cout_transport', str(res.data))
        self.assertNotIn('500', str(res.data))

    def test_compte_portail_fournisseur_refuse(self):
        fournisseur = make_portal_user(
            self.company, 'wir216-portail-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 1)
        self.api.force_authenticate(user=fournisseur)
        res = self.api.get('/api/django/portail/mes-livraisons/')
        self.assertEqual(res.status_code, 403)

    def test_compte_portail_sans_rattachement_refuse(self):
        orphelin = make_portal_user(
            self.company, 'wir216-orphelin',
            CustomUser.PORTEE_PORTAIL_CLIENT, None)
        self.api.force_authenticate(user=orphelin)
        res = self.api.get('/api/django/portail/mes-livraisons/')
        self.assertEqual(res.status_code, 403)

    def test_anonyme_refuse(self):
        res = APIClient().get('/api/django/portail/mes-livraisons/')
        self.assertIn(res.status_code, (401, 403))

    def test_client_d_une_autre_societe_ne_voit_rien(self):
        autre = make_company('wir216-co-b', 'WIR216 Société B')
        client_autre = make_client(autre, 'Gamma')
        etranger = make_portal_user(
            autre, 'wir216-portail-b', CustomUser.PORTEE_PORTAIL_CLIENT,
            client_autre.id)
        self.api.force_authenticate(user=etranger)
        res = self.api.get('/api/django/portail/mes-livraisons/')
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertNotIn(self.livraison_a.id, ids)
        self.assertNotIn(self.livraison_b.id, ids)
