"""Tests WIR216 — « Mes livraisons » du portail client.

Le lien de l'email/WhatsApp de transition (``livraison_en_transit`` /
``livraison_livree``) pointait vers ``/portail/livraisons/<id>``, une route
qui n'existait NULLE PART côté frontend (404 garanti à chaque expédition).
Cette suite couvre :

1. ISOLATION — comme NTPRT10/11 : un compte portail ne voit que les
   livraisons des chantiers de SON client (jamais celles d'un autre client,
   jamais d'une autre société), et la portée doit être EXACTEMENT
   ``portail_client``.
2. Le sélecteur n'expose JAMAIS ``cout_transport`` ni de prix d'achat.
3. Le lien généré par ``livraison_client_notify._livraison_lien`` pointe
   maintenant vers ``/portail/client/livraisons`` (jamais l'ancienne route
   morte).

Run :
    python manage.py test apps.portail.tests.test_wir216_mes_livraisons -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.livraison_client_notify import _livraison_lien
from apps.installations.models import Installation, Livraison
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
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
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


def make_livraison(company, installation, cout_transport=None):
    n = next(_seq)
    return Livraison.objects.create(
        company=company, installation=installation,
        reference=f'LIV-WIR216-{n}', cout_transport=cout_transport)


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


class MesLivraisonsIsolationTests(TestCase):
    def setUp(self):
        self.company = make_company('wir216-co-a', 'WIR216 Société A')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.inst_a = make_installation(self.company, self.client_a)
        self.inst_b = make_installation(self.company, self.client_b)
        self.liv_a = make_livraison(
            self.company, self.inst_a, cout_transport='450.00')
        self.liv_b = make_livraison(self.company, self.inst_b)
        self.user_a = make_portal_user(
            self.company, 'wir216-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.api = APIClient()

    def test_liste_bornee_au_client_rattache(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-livraisons/')

        self.assertEqual(res.status_code, 200)
        ids = {ligne['id'] for ligne in res.data['results']}
        self.assertIn(self.liv_a.id, ids)
        self.assertNotIn(self.liv_b.id, ids)

    def test_cout_transport_et_prix_achat_ne_fuient_jamais(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get('/api/django/portail/mes-livraisons/')
        corps = str(res.data)
        self.assertNotIn('cout_transport', corps)
        self.assertNotIn('450.00', corps)
        self.assertNotIn('prix_achat', corps)

    def test_detail_d_une_livraison_d_autrui_est_introuvable(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(
            f'/api/django/portail/mes-livraisons/{self.liv_b.id}/')
        self.assertEqual(res.status_code, 404)

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
        self.assertNotIn(self.liv_a.id, ids)
        self.assertNotIn(self.liv_b.id, ids)


class LivraisonLienTests(TestCase):
    """WIR216 — le lien de notification pointe vers la vraie route (jamais
    l'ancienne route morte /portail/livraisons/<id>)."""

    def setUp(self):
        self.company = make_company('wir216-lien-co', 'WIR216 Lien')
        self.client_a = make_client(self.company, 'Alpha')
        self.inst = make_installation(self.company, self.client_a)
        self.liv = make_livraison(self.company, self.inst)

    def test_lien_pointe_vers_la_liste_du_portail_client(self):
        lien = _livraison_lien(self.liv)
        self.assertEqual(lien, '/portail/client/livraisons')
        self.assertNotIn(f'/portail/livraisons/{self.liv.id}', lien)
