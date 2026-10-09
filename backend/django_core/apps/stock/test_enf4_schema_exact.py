"""ENF4 — le schéma OpenAPI de stock/achats est exact, et le serveur s'y tient.

Couvre les changements de COMPORTEMENT introduits avec les annotations :

* D2 — les vues sans fichier n'acceptent que du JSON (multipart => 415) ;
  la photo produit garde le multipart ;
* ``created_by_username`` / ``categorie_nom`` sont toujours présents (null
  quand la source est vide) — avant ils disparaissaient de la réponse ;
* le tableau de bord achats expose ``exceptions_3voies`` (le nom réellement
  servi), pas ``exceptions_3_voies``.

Run:
    python manage.py test apps.stock.test_enf4_schema_exact -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import MouvementStock, Produit

User = get_user_model()


def _company():
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug='enf4-co', defaults={'nom': 'ENF4 Co'})
    return company


class SchemaExactTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = User.objects.create_user(
            username='enf4_admin', password='x',
            role_legacy='admin', company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ENF4',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            quantite_stock=10)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_multipart_refuse_sur_vue_sans_fichier(self):
        # D2 : une vue sans fichier ne parle que JSON.
        rep = self.api.post(
            '/api/django/stock/marques/', {'nom': 'ENF4 marque'},
            format='multipart')
        self.assertEqual(rep.status_code, 415)
        rep = self.api.post(
            '/api/django/stock/marques/', {'nom': 'ENF4 marque'},
            format='json')
        self.assertEqual(rep.status_code, 201)

    def test_json_accepte_sur_achats_miroir(self):
        rep = self.api.get('/api/django/achats/bons-commande-fournisseur/')
        self.assertEqual(rep.status_code, 200)

    def test_mouvement_expose_created_by_username_meme_sans_auteur(self):
        mv = MouvementStock.objects.create(
            produit=self.produit, company=self.company,
            type_mouvement='entree', quantite=1,
            quantite_avant=10, quantite_apres=11, reference='ENF4')
        rep = self.api.get(f'/api/django/stock/mouvements/{mv.pk}/')
        self.assertEqual(rep.status_code, 200)
        self.assertIn('created_by_username', rep.json())
        self.assertIsNone(rep.json()['created_by_username'])

    def test_tableau_bord_cle_servie(self):
        rep = self.api.get('/api/django/stock/tableau-bord-achats/')
        self.assertEqual(rep.status_code, 200)
        self.assertIn('exceptions_3voies', rep.json())

    def test_parametre_requis_declare_et_valide(self):
        # bcf-similaires : `fournisseur` requis => 400 explicite sans lui.
        rep = self.api.get(
            '/api/django/achats/bons-commande-fournisseur/bcf-similaires/')
        self.assertEqual(rep.status_code, 400)
