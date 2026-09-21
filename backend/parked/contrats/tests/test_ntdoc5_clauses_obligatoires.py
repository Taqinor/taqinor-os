"""Tests NTDOC5 — Bibliothèque de clauses obligatoires par type de contrat.

Critère d'acceptation :
- un contrat d'un type donné SANS la clause obligatoire de ce type ressort dans
  la liste des clauses manquantes ;
- un contrat complet renvoie une liste VIDE ;
- aucune clause existante n'est renommée (le champ est purement additif et la
  liste vide par défaut laisse le comportement inchangé).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors
from apps.contrats.models import Clause, ClauseContrat, Contrat

User = get_user_model()

BASE = '/api/django/contrats/contrats/'
CLAUSES = '/api/django/contrats/clauses/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ClausesObligatoiresTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc5', 'Obligatoires')
        self.admin = User.objects.create_user(
            username='ntdoc5-admin', password='x', company=self.co,
            role_legacy='admin')
        self.contrat = Contrat.objects.create(
            company=self.co, objet='Maintenance annuelle',
            type_contrat=Contrat.TypeContrat.MAINTENANCE)
        self.responsabilite = Clause.objects.create(
            company=self.co, titre='Responsabilité',
            corps='Le prestataire répond de…',
            obligatoire_pour_types=[Contrat.TypeContrat.MAINTENANCE])

    def test_clause_obligatoire_absente_ressort(self):
        manquantes = selectors.clauses_obligatoires_manquantes(self.contrat)
        self.assertEqual([c.id for c in manquantes],
                         [self.responsabilite.id])

    def test_contrat_complet_renvoie_liste_vide(self):
        ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat,
            clause=self.responsabilite, titre='Responsabilité',
            corps='Le prestataire répond de…')
        self.assertEqual(
            selectors.clauses_obligatoires_manquantes(self.contrat), [])

    def test_clause_ad_hoc_de_meme_titre_compte_comme_presente(self):
        """Une clause retapée à la main (sans FK) compte quand même."""
        ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat,
            titre='  responsabilité ', corps='Texte retapé')
        self.assertEqual(
            selectors.clauses_obligatoires_manquantes(self.contrat), [])

    def test_clause_obligatoire_d_un_autre_type_ignoree(self):
        Clause.objects.create(
            company=self.co, titre='Garantie décennale', corps='…',
            obligatoire_pour_types=[Contrat.TypeContrat.PPA])
        manquantes = selectors.clauses_obligatoires_manquantes(self.contrat)
        self.assertEqual([c.titre for c in manquantes], ['Responsabilité'])

    def test_clause_inactive_ignoree(self):
        self.responsabilite.actif = False
        self.responsabilite.save(update_fields=['actif'])
        self.assertEqual(
            selectors.clauses_obligatoires_manquantes(self.contrat), [])

    def test_clause_d_une_autre_societe_ignoree(self):
        autre = make_company('ntdoc5-b', 'B')
        Clause.objects.create(
            company=autre, titre='Clause étrangère', corps='…',
            obligatoire_pour_types=[Contrat.TypeContrat.MAINTENANCE])
        manquantes = selectors.clauses_obligatoires_manquantes(self.contrat)
        self.assertEqual([c.titre for c in manquantes], ['Responsabilité'])

    def test_defaut_vide_ne_change_rien(self):
        """Une clause existante (liste vide par défaut) n'est jamais exigée."""
        clause = Clause.objects.create(
            company=self.co, titre='Clause facultative', corps='…')
        self.assertEqual(clause.obligatoire_pour_types, [])
        manquantes = selectors.clauses_obligatoires_manquantes(self.contrat)
        self.assertNotIn(clause.id, [c.id for c in manquantes])


class ClausesManquantesApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc5-api', 'API')
        self.admin = User.objects.create_user(
            username='ntdoc5-api-admin', password='x', company=self.co,
            role_legacy='admin')
        self.contrat = Contrat.objects.create(
            company=self.co, objet='Maintenance',
            type_contrat=Contrat.TypeContrat.MAINTENANCE)
        self.clause = Clause.objects.create(
            company=self.co, titre='Responsabilité', corps='…',
            obligatoire_pour_types=[Contrat.TypeContrat.MAINTENANCE])

    def test_endpoint_liste_les_manquantes(self):
        api = auth(self.admin)
        resp = api.get(f'{BASE}{self.contrat.id}/clauses-manquantes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['type_contrat'], 'maintenance')
        self.assertEqual(resp.data['results'][0]['titre'], 'Responsabilité')

    def test_endpoint_vide_quand_complet(self):
        ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, clause=self.clause,
            titre='Responsabilité', corps='…')
        api = auth(self.admin)
        resp = api.get(f'{BASE}{self.contrat.id}/clauses-manquantes/')
        self.assertEqual(resp.data['count'], 0)
        self.assertEqual(resp.data['results'], [])

    def test_contrat_d_une_autre_societe_404(self):
        autre_co = make_company('ntdoc5-api-b', 'B')
        user_b = User.objects.create_user(
            username='ntdoc5-api-b-admin', password='x', company=autre_co,
            role_legacy='admin')
        resp = auth(user_b).get(
            f'{BASE}{self.contrat.id}/clauses-manquantes/')
        self.assertEqual(resp.status_code, 404)

    def test_type_inconnu_refuse_a_l_ecriture(self):
        """Le champ n'accepte que des codes ``Contrat.TypeContrat`` réels."""
        api = auth(self.admin)
        resp = api.patch(
            f'{CLAUSES}{self.clause.id}/',
            {'obligatoire_pour_types': ['type-inexistant']}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('obligatoire_pour_types', resp.data)

    def test_ecriture_valide_acceptee(self):
        api = auth(self.admin)
        resp = api.patch(
            f'{CLAUSES}{self.clause.id}/',
            {'obligatoire_pour_types': ['ppa', 'maintenance']},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.clause.refresh_from_db()
        self.assertEqual(self.clause.obligatoire_pour_types,
                         ['ppa', 'maintenance'])
