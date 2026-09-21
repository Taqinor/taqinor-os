"""Tests PROJ17 -- Indisponibilites ressources (conge/formation/arret).

Couvre :
- Creation d'une indisponibilite (conge/formation/arret) sur une periode
- Societe posee cote serveur (company ignoree du corps de requete)
- Validation date_fin >= date_debut
- Ressource d'une autre societe refusee
- Isolation entre societes (list/detail)
- Filtres ?ressource, ?type, ?debut&fin (chevauchement)
- Selecteurs : disponibilite sur une fenetre + detection de chevauchement
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    Indisponibilite,
    RessourceProfil,
)

User = get_user_model()

BASE = '/api/django/gestion-projet/indisponibilites/'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def make_ressource(company, nom='Technicien'):
    return RessourceProfil.objects.create(
        company=company, nom=nom, cout_horaire=Decimal('0'))


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------

class IndisponibiliteCreateTests(TestCase):

    def setUp(self):
        self.co = make_company('proj17-cr', 'Societe A')
        self.user = make_user(self.co, 'proj17-cr-u')
        self.ressource = make_ressource(self.co, 'Youssef Technicien')

    def _payload(self, **kw):
        return {
            'ressource': self.ressource.id,
            'type_indispo': 'conge',
            'date_debut': '2026-07-01',
            'date_fin': '2026-07-05',
            **kw,
        }

    def test_create_conge(self):
        resp = auth(self.user).post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Indisponibilite.objects.get(id=resp.data['id'])
        self.assertEqual(obj.ressource, self.ressource)
        self.assertEqual(obj.type_indispo, 'conge')

    def test_create_formation(self):
        resp = auth(self.user).post(
            BASE, self._payload(type_indispo='formation'), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['type_indispo'], 'formation')

    def test_create_arret_avec_motif(self):
        resp = auth(self.user).post(
            BASE,
            self._payload(type_indispo='arret', motif='Arret maladie'),
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Indisponibilite.objects.get(id=resp.data['id'])
        self.assertEqual(obj.type_indispo, 'arret')
        self.assertEqual(obj.motif, 'Arret maladie')

    def test_company_force_server_side(self):
        resp = auth(self.user).post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Indisponibilite.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co)

    def test_ressource_nom_in_response(self):
        resp = auth(self.user).post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['ressource_nom'], 'Youssef Technicien')


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class IndisponibiliteValidationTests(TestCase):

    def setUp(self):
        self.co = make_company('proj17-val', 'Societe Val')
        self.user = make_user(self.co, 'proj17-val-u')
        self.ressource = make_ressource(self.co, 'Ressource Val')

    def test_date_fin_anterieure_debut_refuse(self):
        payload = {
            'ressource': self.ressource.id,
            'type_indispo': 'conge',
            'date_debut': '2026-07-10',
            'date_fin': '2026-07-05',
        }
        resp = auth(self.user).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_ressource_obligatoire(self):
        payload = {
            'type_indispo': 'conge',
            'date_debut': '2026-07-01',
            'date_fin': '2026-07-05',
        }
        resp = auth(self.user).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


# ---------------------------------------------------------------------------
# Isolation entre societes
# ---------------------------------------------------------------------------

class IndisponibiliteIsolationTests(TestCase):

    def setUp(self):
        self.co_a = make_company('proj17-iso-a', 'A')
        self.co_b = make_company('proj17-iso-b', 'B')
        self.user_a = make_user(self.co_a, 'proj17-iso-ua')
        self.user_b = make_user(self.co_b, 'proj17-iso-ub')
        self.ressource_a = make_ressource(self.co_a, 'Ressource Iso A')
        self.indispo_a = Indisponibilite.objects.create(
            company=self.co_a,
            ressource=self.ressource_a,
            type_indispo='conge',
            date_debut=date(2026, 7, 1),
            date_fin=date(2026, 7, 5),
        )

    def test_list_isolation(self):
        resp = auth(self.user_b).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_detail_isolation(self):
        resp = auth(self.user_b).get(f'{BASE}{self.indispo_a.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_ressource_autre_societe_refuse(self):
        ressource_b = make_ressource(self.co_b, 'Ressource B pour A')
        payload = {
            'ressource': ressource_b.id,
            'type_indispo': 'conge',
            'date_debut': '2026-07-01',
            'date_fin': '2026-07-05',
        }
        resp = auth(self.user_a).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


# ---------------------------------------------------------------------------
# Filtres
# ---------------------------------------------------------------------------

class IndisponibiliteFiltresTests(TestCase):

    def setUp(self):
        self.co = make_company('proj17-flt', 'Societe Filtre')
        self.user = make_user(self.co, 'proj17-flt-u')
        self.res1 = make_ressource(self.co, 'Ressource 1')
        self.res2 = make_ressource(self.co, 'Ressource 2')
        self.ind1 = Indisponibilite.objects.create(
            company=self.co, ressource=self.res1, type_indispo='conge',
            date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 5))
        self.ind2 = Indisponibilite.objects.create(
            company=self.co, ressource=self.res2, type_indispo='formation',
            date_debut=date(2026, 7, 20), date_fin=date(2026, 7, 25))

    def test_filter_par_ressource(self):
        resp = auth(self.user).get(f'{BASE}?ressource={self.res1.id}')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.ind1.id, ids)
        self.assertNotIn(self.ind2.id, ids)

    def test_filter_par_type(self):
        resp = auth(self.user).get(f'{BASE}?type=formation')
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(self.ind1.id, ids)
        self.assertIn(self.ind2.id, ids)

    def test_filter_par_fenetre_chevauchement(self):
        # Fenetre 2026-07-04 -> 2026-07-10 chevauche ind1 (01-05), pas ind2.
        resp = auth(self.user).get(f'{BASE}?debut=2026-07-04&fin=2026-07-10')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.ind1.id, ids)
        self.assertNotIn(self.ind2.id, ids)

    def test_filter_fenetre_hors_periode(self):
        # Fenetre 2026-07-06 -> 2026-07-10 ne chevauche aucune indispo.
        resp = auth(self.user).get(f'{BASE}?debut=2026-07-06&fin=2026-07-10')
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'proj17-flt-normal', role='normal')
        resp = auth(normal).get(BASE)
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Selecteurs (disponibilite / chevauchement)
# ---------------------------------------------------------------------------

class IndisponibiliteSelectorsTests(TestCase):

    def setUp(self):
        self.co = make_company('proj17-sel', 'Societe Sel')
        self.ressource = make_ressource(self.co, 'Ressource Sel')
        self.indispo = Indisponibilite.objects.create(
            company=self.co, ressource=self.ressource, type_indispo='conge',
            date_debut=date(2026, 7, 1), date_fin=date(2026, 7, 5))

    def test_indisponible_sur_fenetre_chevauchante(self):
        # Fenetre 2026-07-03 -> 2026-07-04 tombe dans l'indispo.
        disponible = selectors.ressource_disponible_sur_periode(
            self.ressource, date(2026, 7, 3), date(2026, 7, 4))
        self.assertFalse(disponible)

    def test_disponible_avant_indispo(self):
        disponible = selectors.ressource_disponible_sur_periode(
            self.ressource, date(2026, 6, 20), date(2026, 6, 30))
        self.assertTrue(disponible)

    def test_disponible_apres_indispo(self):
        disponible = selectors.ressource_disponible_sur_periode(
            self.ressource, date(2026, 7, 6), date(2026, 7, 10))
        self.assertTrue(disponible)

    def test_bornes_inclusives(self):
        # Fenetre qui touche juste la borne de fin (2026-07-05) -> indisponible.
        disponible = selectors.ressource_disponible_sur_periode(
            self.ressource, date(2026, 7, 5), date(2026, 7, 8))
        self.assertFalse(disponible)
        # Fenetre qui touche juste la borne de debut (2026-07-01).
        disponible2 = selectors.ressource_disponible_sur_periode(
            self.ressource, date(2026, 6, 28), date(2026, 7, 1))
        self.assertFalse(disponible2)

    def test_fenetre_englobante(self):
        # Une fenetre qui englobe entierement l'indispo -> chevauchement.
        disponible = selectors.ressource_disponible_sur_periode(
            self.ressource, date(2026, 6, 1), date(2026, 12, 31))
        self.assertFalse(disponible)

    def test_indisponibilites_sur_periode_queryset(self):
        qs = selectors.indisponibilites_sur_periode(
            self.ressource, date(2026, 7, 2), date(2026, 7, 3))
        self.assertEqual(list(qs), [self.indispo])

    def test_chevauche_methode_modele(self):
        self.assertTrue(self.indispo.chevauche(date(2026, 7, 4), date(2026, 7, 9)))
        self.assertFalse(self.indispo.chevauche(date(2026, 7, 6), date(2026, 7, 9)))

    def test_isolation_societe_selecteur(self):
        # Une indispo d'une AUTRE societe sur la meme ressource-image ne fuit pas :
        # ici on verifie simplement que le selecteur filtre sur ressource.company.
        autre_co = make_company('proj17-sel-b', 'Societe Sel B')
        autre_res = make_ressource(autre_co, 'Ressource Autre')
        Indisponibilite.objects.create(
            company=autre_co, ressource=autre_res, type_indispo='conge',
            date_debut=date(2026, 7, 3), date_fin=date(2026, 7, 4))
        # autre_res est indisponible chez elle, mais self.ressource reste isolee.
        self.assertFalse(selectors.ressource_disponible_sur_periode(
            autre_res, date(2026, 7, 3), date(2026, 7, 4)))
        # La ressource de co reste affectee uniquement par SES indispos.
        qs = selectors.indisponibilites_de_ressource(self.ressource)
        self.assertEqual(list(qs), [self.indispo])
