"""ASTK178 (C-ASTK-039) — `?fournisseur=<id>` filtre côté serveur les BCF et
les retours d'un fournisseur (même filtre que les factures fournisseur) :
la fiche 360 lit cette liste filtrée au lieu de filtrer en mémoire une page
de la liste globale (qui ratait les documents hors première page, et la
comparaison « '7' === 7 » de l'id de route).

Aucun mock : vues réelles.

Run :
    python manage.py test apps.stock.test_astk_fiche360_filtre -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, RetourFournisseur,
)

User = get_user_model()

BASE = '/api/django/stock'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids(rep):
    corps = rep.json()
    lignes = corps['results'] if isinstance(corps, dict) else corps
    return sorted(ligne['id'] for ligne in lignes)


class FiltreFournisseurTests(TestCase):
    def setUp(self):
        self.co = make_company('astk178-co', 'ASTK178 Co')
        self.autre = make_company('astk178-autre', 'ASTK178 Autre')
        self.admin = User.objects.create_user(
            username='astk178_admin', password='x', role_legacy='admin',
            company=self.co)
        self.api = auth(self.admin)
        self.f7 = Fournisseur.objects.create(company=self.co, nom='Sept')
        self.f8 = Fournisseur.objects.create(company=self.co, nom='Huit')
        self.f_autre = Fournisseur.objects.create(
            company=self.autre, nom='Ailleurs')
        self.bcf7 = [
            BonCommandeFournisseur.objects.create(
                company=self.co, reference=f'BCF-178-7-{i}',
                fournisseur=self.f7)
            for i in range(2)]
        for i in range(5):
            BonCommandeFournisseur.objects.create(
                company=self.co, reference=f'BCF-178-8-{i}',
                fournisseur=self.f8)
        BonCommandeFournisseur.objects.create(
            company=self.autre, reference='BCF-178-X', fournisseur=self.f_autre)
        self.retour7 = RetourFournisseur.objects.create(
            company=self.co, reference='RF-178-7', fournisseur=self.f7)
        RetourFournisseur.objects.create(
            company=self.co, reference='RF-178-8', fournisseur=self.f8)

    def test_bcf_filtre_par_fournisseur(self):
        rep = self.api.get(f'{BASE}/bons-commande-fournisseur/',
                           {'fournisseur': str(self.f7.id)})
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(ids(rep), sorted(b.id for b in self.bcf7))
        # Sans paramètre : la liste complète de la société (inchangée).
        tous = self.api.get(f'{BASE}/bons-commande-fournisseur/',
                            {'page_size': 100})
        self.assertEqual(len(ids(tous)), 7)

    def test_retours_filtre_par_fournisseur(self):
        rep = self.api.get(f'{BASE}/retours-fournisseur/',
                           {'fournisseur': self.f7.id})
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(ids(rep), [self.retour7.id])

    def test_fournisseur_autre_societe_liste_vide(self):
        for url in ('bons-commande-fournisseur', 'retours-fournisseur'):
            for valeur in (self.f_autre.id, 99999999, 'pas-un-id'):
                rep = self.api.get(f'{BASE}/{url}/', {'fournisseur': valeur})
                self.assertEqual(rep.status_code, 200, (url, valeur))
                self.assertEqual(ids(rep), [], (url, valeur))
