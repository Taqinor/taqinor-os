"""
NTP2P3 — Catalogue interne d'achat pour les demandeurs.

CRITÈRE D'ACCEPTATION : un demandeur non-admin peut lister le catalogue pour
composer sa demande d'achat SANS voir les marges — c'est-à-dire sans que
``prix_vente`` (ni aucun champ permettant de la reconstituer) ne soit jamais
sérialisé.

Couvre aussi : le scope société, la recherche nom/SKU/catégorie, le
``prix_achat_dernier`` (tarif fournisseur le plus récent, repli sur le prix
d'achat catalogue) et l'absence totale d'écriture (lecture seule).

Run :
    python manage.py test apps.stock.test_ntp2p3_catalogue_achat -v2
"""
import itertools
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Categorie, Fournisseur, Produit

User = get_user_model()
_seq = itertools.count(1)
URL = '/api/django/stock/catalogue-achat/'

# Tout champ qui permettrait de calculer une marge côté client.
CHAMPS_INTERDITS = {'prix_vente', 'marge', 'taux_marge', 'prix_ttc'}


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p3-co-{n}', defaults={'nom': f'NTP2P3 Co {n}'})
    return company


def make_user(company, role='normal'):
    return User.objects.create_user(
        username=f'ntp2p3-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class CatalogueAchatTests(TestCase):

    def setUp(self):
        self.company = make_company()
        # Un DEMANDEUR ordinaire (rôle `normal`) : c'est lui le sujet du
        # critère d'acceptation.
        self.demandeur = make_user(self.company, role='normal')
        self.api = auth(self.demandeur)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Panneaux')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='SolarImport')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PV-550',
            categorie=self.categorie, fournisseur=self.fournisseur,
            prix_achat=1000, prix_vente=1500)

    def test_demandeur_non_admin_voit_le_catalogue(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_aucune_marge_exposee(self):
        """CRITÈRE D'ACCEPTATION — aucun prix de vente, donc aucune marge."""
        resp = self.api.get(URL)
        article = rows(resp)[0]
        for champ in CHAMPS_INTERDITS:
            self.assertNotIn(champ, article)
        self.assertEqual(
            set(article),
            {'id', 'nom', 'sku', 'categorie', 'categorie_nom',
             'fournisseur_prefere', 'fournisseur_prefere_nom',
             'prix_achat_dernier'})

    def test_champs_utiles_presents(self):
        article = rows(self.api.get(URL))[0]
        self.assertEqual(article['nom'], 'Panneau 550W')
        self.assertEqual(article['sku'], 'PV-550')
        self.assertEqual(article['categorie_nom'], 'Panneaux')
        self.assertEqual(article['fournisseur_prefere'], self.fournisseur.pk)
        self.assertEqual(article['fournisseur_prefere_nom'], 'SolarImport')

    def test_prix_achat_dernier_replie_sur_le_produit(self):
        article = rows(self.api.get(URL))[0]
        self.assertEqual(str(article['prix_achat_dernier']), '1000.00')

    def test_prix_achat_dernier_prend_le_tarif_fournisseur_recent(self):
        from apps.stock.models import PrixFournisseur
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=880,
            date_dernier_achat=date(2026, 1, 5))
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=930,
            date_dernier_achat=date(2026, 6, 20))
        article = rows(self.api.get(URL))[0]
        self.assertEqual(str(article['prix_achat_dernier']), '930.00')

    def test_recherche_par_nom_sku_et_categorie(self):
        Produit.objects.create(
            company=self.company, nom='Câble 6mm', sku='CB-6',
            prix_achat=10, prix_vente=15)
        self.assertEqual(len(rows(self.api.get(URL, {'q': 'panneau'}))), 1)
        self.assertEqual(len(rows(self.api.get(URL, {'q': 'CB-6'}))), 1)
        self.assertEqual(len(rows(self.api.get(URL, {'q': 'Panneaux'}))), 1)
        self.assertEqual(len(rows(self.api.get(URL, {'q': 'introuvable'}))), 0)

    def test_filtre_categorie_et_fournisseur(self):
        Produit.objects.create(
            company=self.company, nom='Câble 6mm', prix_achat=10,
            prix_vente=15)
        self.assertEqual(
            len(rows(self.api.get(URL, {'categorie': self.categorie.pk}))), 1)
        self.assertEqual(
            len(rows(self.api.get(URL, {'fournisseur': self.fournisseur.pk}))),
            1)

    def test_produit_archive_exclu(self):
        self.produit.is_archived = True
        self.produit.save(update_fields=['is_archived'])
        self.assertEqual(len(rows(self.api.get(URL))), 0)

    def test_scope_societe_etanche(self):
        autre = make_company()
        Produit.objects.create(
            company=autre, nom='Produit voisin', prix_achat=1, prix_vente=2)
        noms = [a['nom'] for a in rows(self.api.get(URL))]
        self.assertEqual(noms, ['Panneau 550W'])

    def test_lecture_seule(self):
        resp = self.api.post(URL, {'nom': 'Injecté', 'prix_vente': '1.00'},
                             format='json')
        self.assertIn(resp.status_code, (403, 405))
        self.assertFalse(Produit.objects.filter(nom='Injecté').exists())

    def test_anonyme_refuse(self):
        resp = APIClient().get(URL)
        self.assertIn(resp.status_code, (401, 403))
