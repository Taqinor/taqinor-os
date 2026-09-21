"""Tests NTHCM3 — organigramme matriciel (rattachement fonctionnel).

Couvre :
* un employé porte 1 manager HIÉRARCHIQUE + N rattachements FONCTIONNELS
  actifs en même temps ;
* la fenêtre de dates borne l'activité d'un rattachement ;
* l'organigramme superpose les deux lignes seulement sur demande
  (``inclure_matriciel``), la clé restant TOUJOURS présente ;
* l'auto-rattachement et le cross-tenant sont refusés ;
* CRUD company-scopé.

Horloge FIGÉE (``aujourdhui=``) pour les fenêtres de dates.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, RattachementFonctionnel

User = get_user_model()

JOUR_FIGE = date(2026, 5, 15)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def lignes(reponse):
    donnees = reponse.data
    return donnees['results'] if isinstance(donnees, dict) else donnees


class RattachementFonctionnelTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm3-a', 'A')
        self.rh = make_user(self.co, 'nthcm3-rh')
        self.api = auth(self.rh)
        self.chef = DossierEmploye.objects.create(
            company=self.co, matricule='F-001', nom='Bennani', prenom='Y')
        self.qhse = DossierEmploye.objects.create(
            company=self.co, matricule='F-002', nom='Qhse', prenom='Q')
        self.chef_projet = DossierEmploye.objects.create(
            company=self.co, matricule='F-003', nom='Projet', prenom='P')
        self.poseur = DossierEmploye.objects.create(
            company=self.co, matricule='F-004', nom='Poseur', prenom='X',
            manager=self.chef)

    def test_un_hierarchique_et_plusieurs_fonctionnels(self):
        RattachementFonctionnel.objects.create(
            company=self.co, employe=self.poseur,
            manager_fonctionnel=self.qhse, role_fonctionnel='QHSE')
        RattachementFonctionnel.objects.create(
            company=self.co, employe=self.poseur,
            manager_fonctionnel=self.chef_projet, role_fonctionnel='Projet')
        self.assertEqual(self.poseur.manager_id, self.chef.id)
        self.assertEqual(self.poseur.rattachements_fonctionnels.count(), 2)

    def test_fenetre_de_dates(self):
        lien = RattachementFonctionnel.objects.create(
            company=self.co, employe=self.poseur,
            manager_fonctionnel=self.qhse, role_fonctionnel='QHSE',
            date_debut=date(2026, 6, 1))
        self.assertFalse(lien.actif_le(JOUR_FIGE))
        self.assertTrue(lien.actif_le(date(2026, 6, 2)))

        lien.date_debut = None
        lien.date_fin = date(2026, 5, 1)
        self.assertFalse(lien.actif_le(JOUR_FIGE))

        lien.date_fin = None
        self.assertTrue(lien.actif_le(JOUR_FIGE))

    def test_auto_rattachement_refuse(self):
        lien = RattachementFonctionnel(
            company=self.co, employe=self.poseur,
            manager_fonctionnel=self.poseur)
        with self.assertRaises(ValidationError):
            lien.full_clean()

    def test_fenetre_incoherente_refusee(self):
        lien = RattachementFonctionnel(
            company=self.co, employe=self.poseur,
            manager_fonctionnel=self.qhse,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 5, 1))
        with self.assertRaises(ValidationError):
            lien.full_clean()

    def test_cross_tenant_refuse(self):
        autre = make_company('nthcm3-b', 'B')
        etranger = DossierEmploye.objects.create(
            company=autre, matricule='B-1', nom='Voisin', prenom='V')
        lien = RattachementFonctionnel(
            company=self.co, employe=self.poseur,
            manager_fonctionnel=etranger)
        with self.assertRaises(ValidationError):
            lien.full_clean()

    # ── superposition dans l'organigramme ─────────────────────────────────
    def test_cle_toujours_presente_meme_sans_matriciel(self):
        arbre = selectors.arbre_hierarchique(self.co)
        self.assertFalse(arbre['matriciel'])
        for racine in arbre['racines']:
            self.assertEqual(racine['rattachements_fonctionnels'], [])

    def test_superposition_sur_demande(self):
        RattachementFonctionnel.objects.create(
            company=self.co, employe=self.poseur,
            manager_fonctionnel=self.qhse, role_fonctionnel='QHSE')
        arbre = selectors.arbre_hierarchique(
            self.co, inclure_matriciel=True, aujourdhui=JOUR_FIGE)
        self.assertTrue(arbre['matriciel'])
        racine_chef = next(
            r for r in arbre['racines'] if r['id'] == self.chef.id)
        noeud_poseur = racine_chef['subordonnes'][0]
        self.assertEqual(noeud_poseur['id'], self.poseur.id)
        liens = noeud_poseur['rattachements_fonctionnels']
        self.assertEqual(len(liens), 1)
        self.assertEqual(liens[0]['role_fonctionnel'], 'QHSE')
        self.assertEqual(
            liens[0]['manager_fonctionnel_id'], self.qhse.id)
        self.assertEqual(liens[0]['manager_fonctionnel'], 'Qhse Q')

    def test_rattachement_inactif_non_superpose(self):
        RattachementFonctionnel.objects.create(
            company=self.co, employe=self.poseur,
            manager_fonctionnel=self.qhse, role_fonctionnel='QHSE',
            date_fin=date(2026, 1, 1))
        arbre = selectors.arbre_hierarchique(
            self.co, inclure_matriciel=True, aujourdhui=JOUR_FIGE)
        racine_chef = next(
            r for r in arbre['racines'] if r['id'] == self.chef.id)
        self.assertEqual(
            racine_chef['subordonnes'][0]['rattachements_fonctionnels'], [])

    # ── API ───────────────────────────────────────────────────────────────
    def test_api_crud_scope_societe(self):
        reponse = self.api.post(
            '/api/django/rh/rattachements-fonctionnels/',
            {'employe': self.poseur.id,
             'manager_fonctionnel': self.qhse.id,
             'role_fonctionnel': 'QHSE'},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        lien = RattachementFonctionnel.objects.get(pk=reponse.data['id'])
        self.assertEqual(lien.company_id, self.co.id)

        autre = make_company('nthcm3-c', 'C')
        voisin = make_user(autre, 'nthcm3-voisin')
        vue = auth(voisin).get('/api/django/rh/rattachements-fonctionnels/')
        self.assertEqual(vue.status_code, 200, vue.content)
        self.assertEqual(list(lignes(vue)), [])

    def test_api_auto_rattachement_refuse(self):
        reponse = self.api.post(
            '/api/django/rh/rattachements-fonctionnels/',
            {'employe': self.poseur.id,
             'manager_fonctionnel': self.poseur.id},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.content)

    def test_endpoint_organigramme_matriciel(self):
        RattachementFonctionnel.objects.create(
            company=self.co, employe=self.poseur,
            manager_fonctionnel=self.qhse, role_fonctionnel='QHSE')
        reponse = self.api.get(
            '/api/django/rh/employes/organigramme/?inclure_matriciel=1')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertTrue(reponse.data['matriciel'])
