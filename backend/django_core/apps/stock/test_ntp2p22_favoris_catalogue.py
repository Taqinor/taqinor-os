"""
NTP2P22 — Favoris du catalogue d'achat (punch-out interne).

CRITÈRE D'ACCEPTATION : un demandeur voit ses 5 DERNIERS produits demandés en
tête de liste.

Couvre aussi : les articles ÉPINGLÉS passent avant les récents, un id produit
d'une autre société n'est jamais stocké, le filtre « déjà commandé récemment »
(``?recent=1``), et l'isolation par utilisateur ET par société.

Run :
    python manage.py test apps.stock.test_ntp2p22_favoris_catalogue -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeAchat, DemandeAchatLigne
from apps.stock.models import FavorisCatalogueAchat, Produit

User = get_user_model()
_seq = itertools.count(1)
CATALOGUE = '/api/django/stock/catalogue-achat'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p22-co-{n}', defaults={'nom': f'NTP2P22 Co {n}'})
    return company


def make_user(company, role='normal'):
    return User.objects.create_user(
        username=f'ntp2p22-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom):
    return Produit.objects.create(
        company=company, nom=nom, prix_achat=100, prix_vente=150)


def demander(company, user, produits):
    da = DemandeAchat.objects.create(
        company=company, reference=f'DA-FAV-{next(_seq):04d}',
        objet='Réquisition', created_by=user)
    for produit in produits:
        DemandeAchatLigne.objects.create(
            demande=da, produit=produit, quantite=1, prix_estime=100)
    return da


class FavorisCatalogueTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.demandeur = make_user(self.company)
        self.api = auth(self.demandeur)
        self.produits = [
            make_produit(self.company, f'Article {i}') for i in range(8)]

    def test_liste_vide_au_depart(self):
        resp = self.api.get(f'{CATALOGUE}/favoris/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['epingles'], [])
        self.assertEqual(resp.data['recents'], [])
        self.assertEqual(resp.data['produit_ids'], [])

    def test_cinq_derniers_produits_demandes_en_tete(self):
        """CRITÈRE D'ACCEPTATION NTP2P22."""
        for produit in self.produits[:7]:
            demander(self.company, self.demandeur, [produit])
        resp = self.api.get(f'{CATALOGUE}/favoris/')
        recents = resp.data['recents']
        self.assertEqual(len(recents), 5)
        # Le plus récemment demandé arrive en premier.
        attendus = [p.pk for p in reversed(self.produits[2:7])]
        self.assertEqual(recents, attendus)
        self.assertEqual(resp.data['produit_ids'], attendus)

    def test_produits_dedoublonnes(self):
        produit = self.produits[0]
        for _ in range(3):
            demander(self.company, self.demandeur, [produit])
        resp = self.api.get(f'{CATALOGUE}/favoris/')
        self.assertEqual(resp.data['recents'], [produit.pk])

    def test_epingler_des_articles(self):
        cibles = [self.produits[3].pk, self.produits[1].pk]
        resp = self.api.put(f'{CATALOGUE}/favoris/',
                            {'produit_ids': cibles}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['epingles'], cibles)
        favoris = FavorisCatalogueAchat.objects.get(
            company=self.company, utilisateur=self.demandeur)
        self.assertEqual(favoris.produit_ids, cibles)

    def test_epingles_avant_recents(self):
        demander(self.company, self.demandeur, [self.produits[0]])
        epingle = self.produits[5].pk
        self.api.put(f'{CATALOGUE}/favoris/',
                     {'produit_ids': [epingle]}, format='json')
        resp = self.api.get(f'{CATALOGUE}/favoris/')
        self.assertEqual(resp.data['produit_ids'][0], epingle)
        self.assertIn(self.produits[0].pk, resp.data['produit_ids'])

    def test_id_dune_autre_societe_ecarte(self):
        autre = make_company()
        etranger = make_produit(autre, 'Article voisin')
        resp = self.api.put(
            f'{CATALOGUE}/favoris/',
            {'produit_ids': [self.produits[0].pk, etranger.pk]},
            format='json')
        self.assertEqual(resp.data['epingles'], [self.produits[0].pk])

    def test_charge_utile_invalide_ne_casse_pas(self):
        resp = self.api.put(f'{CATALOGUE}/favoris/',
                            {'produit_ids': 'pas-une-liste'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['epingles'], [])

    def test_favoris_isoles_par_utilisateur(self):
        autre_demandeur = make_user(self.company)
        self.api.put(f'{CATALOGUE}/favoris/',
                     {'produit_ids': [self.produits[0].pk]}, format='json')
        resp = auth(autre_demandeur).get(f'{CATALOGUE}/favoris/')
        self.assertEqual(resp.data['epingles'], [])

    def test_recents_isoles_par_utilisateur(self):
        autre_demandeur = make_user(self.company)
        demander(self.company, autre_demandeur, [self.produits[0]])
        resp = self.api.get(f'{CATALOGUE}/favoris/')
        self.assertEqual(resp.data['recents'], [])

    def test_filtre_deja_commande_recemment(self):
        demander(self.company, self.demandeur, [self.produits[0]])
        resp = self.api.get(f'{CATALOGUE}/', {'recent': '1'})
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual([a['id'] for a in data], [self.produits[0].pk])

    def test_sans_filtre_tout_le_catalogue(self):
        resp = self.api.get(f'{CATALOGUE}/')
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 8)
