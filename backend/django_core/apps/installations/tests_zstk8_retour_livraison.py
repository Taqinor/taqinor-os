"""ZSTK8 — Retour / transfert inverse depuis une Livraison validée (returns).

Odoo génère un « return picking » depuis une livraison validée ; les retours
FOURNISSEUR existent mais rien ne permettait un retour CLIENT depuis une
`Livraison` livrée. Couvre :

  * générer un retour depuis une livraison LIVREE pré-remplit les lignes
    (quantite_livree = quantité livrée) ;
  * valider ré-incrémente le stock du dépôt source EXACTEMENT une fois ;
  * quantité retournée > livrée → refusée (400 / ValueError) ;
  * générer un retour depuis une livraison NON livrée est refusé ;
  * cross-company → 404 ;
  * ré-validation idempotente.

Run :
    python manage.py test apps.installations.tests_zstk8_retour_livraison -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit, EmplacementStock
from apps.installations.models import (
    Installation, Livraison, LivraisonLigne, RetourLivraison,
)
from apps.installations.services import (
    generer_retour_livraison, valider_retour_livraison,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'zstk8-co-{n}', defaults={'nom': f'ZSTK8 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'zstk8-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='ZSTK8',
        email=f'zstk8-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-ZSTK8-{n}', client=client,
        statut=Installation.Statut.PLANIFIE)


def make_livraison_livree(company, installation, quantite=10):
    depot = EmplacementStock.objects.create(
        company=company, nom='Dépôt principal', is_principal=True)
    produit = Produit.objects.create(
        company=company, nom='Batterie ZSTK8',
        prix_vente=Decimal('300'), quantite_stock=Decimal('0'))
    liv = Livraison.objects.create(
        company=company, reference=f'LIV-ZSTK8-{next(_seq)}',
        installation=installation, depot=depot,
        statut=Livraison.Statut.LIVREE)
    LivraisonLigne.objects.create(
        livraison=liv, produit=produit, designation=produit.nom,
        quantite=quantite)
    return liv, produit, depot


class TestGenererRetourLivraison(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.liv, self.produit, self.depot = make_livraison_livree(
            self.company, self.inst, quantite=10)

    def test_generer_prefill_lignes(self):
        retour = generer_retour_livraison(self.liv, self.user)
        lignes = list(retour.lignes.all())
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].quantite_livree, 10)
        self.assertEqual(lignes[0].quantite_retournee, 0)
        self.assertEqual(retour.statut, RetourLivraison.Statut.BROUILLON)

    def test_valider_reincremente_stock_une_fois(self):
        retour = generer_retour_livraison(self.liv, self.user)
        ligne = retour.lignes.first()
        ligne.quantite_retournee = 4
        ligne.save(update_fields=['quantite_retournee'])

        applied = valider_retour_livraison(retour, self.user)
        self.assertEqual(applied, 1)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('4'))

        retour.refresh_from_db()
        self.assertEqual(retour.statut, RetourLivraison.Statut.VALIDE)

        # Ré-valider : idempotent (ValueError, aucun second mouvement).
        with self.assertRaises(ValueError):
            valider_retour_livraison(retour, self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('4'))

    def test_quantite_retournee_superieure_a_livree_refusee(self):
        retour = generer_retour_livraison(self.liv, self.user)
        ligne = retour.lignes.first()
        ligne.quantite_retournee = 999
        ligne.save(update_fields=['quantite_retournee'])
        with self.assertRaises(ValueError):
            valider_retour_livraison(retour, self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('0'))

    def test_endpoint_generer_retour_refuse_si_pas_livree(self):
        self.liv.statut = Livraison.Statut.PLANIFIEE
        self.liv.save(update_fields=['statut'])
        r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/generer-retour/')
        self.assertEqual(r.status_code, 400)

    def test_endpoint_generer_puis_valider(self):
        r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/generer-retour/')
        self.assertEqual(r.status_code, 201, r.data)
        retour_id = r.data['id']
        ligne_id = r.data['lignes'][0]['id']

        r2 = self.api.patch(
            f'{BASE}/retour-livraison-lignes/{ligne_id}/',
            {'quantite_retournee': 3}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)

        r3 = self.api.post(f'{BASE}/retours-livraison/{retour_id}/valider/')
        self.assertEqual(r3.status_code, 200, r3.data)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('3'))

    def test_cross_company_404(self):
        other_company = make_company()
        other_inst = make_installation(other_company)
        other_liv, _p, _d = make_livraison_livree(other_company, other_inst)
        r = self.api.post(
            f'{BASE}/livraisons/{other_liv.id}/generer-retour/')
        self.assertEqual(r.status_code, 404)
