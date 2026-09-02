"""XSAL1 — Listes de prix clients (détail / revendeur / export).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xsal1_listes_prix -v 2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import CustomUser
from apps.ventes.models import ListePrix, LignePrixListe
from apps.ventes.services import prix_applicable
from testkit.factories import (
    CompanyFactory, ClientFactory, ProduitFactory, UserFactory, another_tenant,
)


def _sans_request_id(donnees):
    """Corps d'erreur privé de son ``request_id``.

    L'enveloppe d'erreur maison pose un ``request_id`` de CORRÉLATION, unique
    par requête : il ne dit rien de l'existence de la ressource et ne peut donc
    pas servir d'oracle. Deux réponses ne sont comparables qu'une fois ce
    champ volatil écarté.
    """
    if not isinstance(donnees, dict):
        return donnees
    copie = dict(donnees)
    erreur = copie.get('error')
    if isinstance(erreur, dict):
        copie['error'] = {c: v for c, v in erreur.items() if c != 'request_id'}
    copie.pop('request_id', None)
    return copie


class TestPrixApplicableResolution(TestCase):
    """XSAL1 — service `prix_applicable` (résolution liste client)."""

    def setUp(self):
        self.company = CompanyFactory()
        self.produit = ProduitFactory(
            company=self.company, prix_vente=Decimal('1000.00'),
            prix_achat=Decimal('600.00'))
        self.client_sans_liste = ClientFactory(company=self.company)
        self.liste = ListePrix.objects.create(
            company=self.company, nom='Revendeur')
        self.client_revendeur = ClientFactory(
            company=self.company, liste_prix=self.liste)

    def test_client_sans_liste_garde_prix_vente(self):
        resolved = prix_applicable(
            produit=self.produit, client=self.client_sans_liste, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('1000.00'))
        self.assertEqual(resolved['source'], 'standard')

    def test_client_none_garde_prix_vente(self):
        resolved = prix_applicable(produit=self.produit, client=None, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('1000.00'))

    def test_liste_prix_ligne_fixe_prefill(self):
        LignePrixListe.objects.create(
            liste=self.liste, produit=self.produit,
            prix_unitaire=Decimal('850.00'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client_revendeur, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('850.00'))
        self.assertEqual(resolved['source'], 'liste')
        self.assertEqual(resolved['liste_nom'], 'Revendeur')

    def test_archived_liste_falls_back_to_standard(self):
        self.liste.archived = True
        self.liste.save()
        LignePrixListe.objects.create(
            liste=self.liste, produit=self.produit,
            prix_unitaire=Decimal('850.00'))
        resolved = prix_applicable(
            produit=self.produit, client=self.client_revendeur, quantite=1)
        self.assertEqual(resolved['prix'], Decimal('1000.00'))
        self.assertEqual(resolved['source'], 'standard')

    def test_never_exposes_prix_achat(self):
        resolved = prix_applicable(
            produit=self.produit, client=self.client_revendeur, quantite=1)
        self.assertNotIn('prix_achat', resolved)


class TestListePrixViewSetTenantIsolation(TestCase):
    """XSAL1 — le ViewSet reste company-scoped, écriture responsable/admin."""

    def setUp(self):
        self.company = CompanyFactory()
        self.admin = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_ADMIN)
        self.normal = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.liste = ListePrix.objects.create(
            company=self.company, nom='Export')

    def _api_for(self, user):
        api = APIClient()
        token = AccessToken.for_user(user)
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return api

    def test_admin_can_create_liste(self):
        api = self._api_for(self.admin)
        resp = api.post('/api/django/ventes/listes-prix/', {
            'nom': 'Nouvelle liste', 'devise': 'MAD',
        })
        self.assertEqual(resp.status_code, 201)
        created = ListePrix.objects.get(id=resp.data['id'])
        self.assertEqual(created.company_id, self.company.id)

    def test_company_forced_server_side_ignores_body_override(self):
        other_company, _ = another_tenant()
        api = self._api_for(self.admin)
        resp = api.post('/api/django/ventes/listes-prix/', {
            'nom': 'Hack', 'company': other_company.id,
        })
        self.assertEqual(resp.status_code, 201)
        created = ListePrix.objects.get(id=resp.data['id'])
        self.assertEqual(created.company_id, self.company.id)

    def test_normal_role_forbidden_from_creating(self):
        api = self._api_for(self.normal)
        resp = api.post('/api/django/ventes/listes-prix/', {'nom': 'X'})
        self.assertEqual(resp.status_code, 403)

    def test_cross_tenant_list_hidden(self):
        _other_company, other_user = another_tenant()
        api = self._api_for(other_user)
        resp = api.get('/api/django/ventes/listes-prix/')
        self.assertEqual(resp.status_code, 200)
        ids = [row['id'] for row in resp.data.get('results', resp.data)]
        self.assertNotIn(self.liste.id, ids)

    def test_lignes_action_upserts_price(self):
        produit = ProduitFactory(company=self.company, prix_vente=Decimal('500'))
        api = self._api_for(self.admin)
        resp = api.post(
            f'/api/django/ventes/listes-prix/{self.liste.id}/lignes/',
            {'produit': produit.id, 'prix_unitaire': '420.00'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            LignePrixListe.objects.filter(
                liste=self.liste, produit=produit,
                prix_unitaire=Decimal('420.00')).exists())

    # ── CRX18 — le produit d'une ligne de liste de prix est scopé société ────

    def test_lignes_refuse_un_produit_d_une_autre_societe(self):
        """``produit_id`` était posé tel quel : un id d'une AUTRE société
        créait la ligne ET la réponse renvoyait son ``produit_nom`` — une fuite
        en un seul appel. 404, exactement comme un id inexistant."""
        autre_company, _ = another_tenant()
        produit_voisin = ProduitFactory(
            company=autre_company, nom='Onduleur du voisin',
            prix_vente=Decimal('900'))
        api = self._api_for(self.admin)
        resp = api.post(
            f'/api/django/ventes/listes-prix/{self.liste.id}/lignes/',
            {'produit': produit_voisin.id, 'prix_unitaire': '420.00'})
        self.assertEqual(resp.status_code, 404, getattr(resp, 'data', resp))
        self.assertNotIn('Onduleur du voisin', resp.content.decode())
        self.assertFalse(
            LignePrixListe.objects.filter(
                liste=self.liste, produit=produit_voisin).exists())

    def test_lignes_produit_inexistant_repond_comme_un_produit_voisin(self):
        """Même code ET même message qu'un produit d'une autre société :
        aucun oracle d'existence inter-société."""
        autre_company, _ = another_tenant()
        produit_voisin = ProduitFactory(
            company=autre_company, prix_vente=Decimal('900'))
        api = self._api_for(self.admin)
        url = f'/api/django/ventes/listes-prix/{self.liste.id}/lignes/'
        voisin = api.post(
            url, {'produit': produit_voisin.id, 'prix_unitaire': '1'})
        absent = api.post(url, {'produit': 999_999_999, 'prix_unitaire': '1'})
        self.assertEqual(voisin.status_code, absent.status_code)
        # Tout SAUF le ``request_id`` (identifiant de corrélation, unique par
        # requête par construction) : c'est le code + le message + les champs
        # qui ne doivent pas distinguer « existe ailleurs » de « n'existe pas ».
        self.assertEqual(_sans_request_id(voisin.data),
                         _sans_request_id(absent.data))
        self.assertEqual(str(voisin.data['detail']),
                         str(absent.data['detail']))

    def test_lignes_produit_non_numerique_ne_leve_pas_500(self):
        api = self._api_for(self.admin)
        resp = api.post(
            f'/api/django/ventes/listes-prix/{self.liste.id}/lignes/',
            {'produit': 'abc', 'prix_unitaire': '1'})
        self.assertEqual(resp.status_code, 404, getattr(resp, 'data', resp))
