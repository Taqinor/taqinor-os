"""Tests PROJ16 -- Affectation des ressources.

Couvre :
- Affectation par ressource (RessourceProfil)
- Affectation par equipe (Equipe)
- Affectation par actif materiel (reference lache flotte)
- Validation : exactement un vecteur (0 vecteur -> 400, >1 vecteur -> 400)
- Societe posee cote serveur (company ignoree du corps de requete)
- Isolation entre societes
- Filtres ?tache, ?projet, ?ressource, ?equipe
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.gestion_projet.models import (
    AffectationRessource,
    Equipe,
    Projet,
    RessourceProfil,
    Tache,
)

User = get_user_model()

BASE = '/api/django/gestion-projet/affectations/'


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


def make_projet(company, code='P1'):
    return Projet.objects.create(company=company, code=code, nom='Projet test')


def make_tache(company, projet, libelle='Tache test'):
    return Tache.objects.create(
        company=company, projet=projet, libelle=libelle)


def make_ressource(company, nom='Technicien'):
    return RessourceProfil.objects.create(
        company=company, nom=nom, cout_horaire=Decimal('0'))


def make_equipe(company, nom='Equipe A'):
    return Equipe.objects.create(company=company, nom=nom)


# ---------------------------------------------------------------------------
# Tests d'affectation par type de ressource
# ---------------------------------------------------------------------------

class AffectationParRessourceProfilTests(TestCase):

    def setUp(self):
        self.co = make_company('proj16-rp', 'Societe A')
        self.user = make_user(self.co, 'proj16-rp-u')
        self.projet = make_projet(self.co, 'P16-RP')
        self.tache = make_tache(self.co, self.projet, 'Pose panneau')
        self.ressource = make_ressource(self.co, 'Youssef Technicien')

    def _payload(self, **kw):
        return {
            'tache': self.tache.id,
            'ressource': self.ressource.id,
            'date_debut': '2026-07-01',
            'date_fin': '2026-07-05',
            **kw,
        }

    def test_create_par_ressource(self):
        resp = auth(self.user).post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = AffectationRessource.objects.get(id=resp.data['id'])
        self.assertEqual(obj.ressource, self.ressource)
        self.assertIsNone(obj.equipe)
        self.assertIsNone(obj.actif_id)

    def test_company_force_server_side(self):
        resp = auth(self.user).post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = AffectationRessource.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co)

    def test_charge_jours_and_quantite_optional(self):
        resp = auth(self.user).post(
            BASE,
            self._payload(charge_jours='2.5', quantite='1.000'),
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['charge_jours']), Decimal('2.5'))

    def test_tache_libelle_in_response(self):
        resp = auth(self.user).post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['tache_libelle'], 'Pose panneau')

    def test_ressource_nom_in_response(self):
        resp = auth(self.user).post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['ressource_nom'], 'Youssef Technicien')


class AffectationParEquipeTests(TestCase):

    def setUp(self):
        self.co = make_company('proj16-eq', 'Societe B')
        self.user = make_user(self.co, 'proj16-eq-u')
        self.projet = make_projet(self.co, 'P16-EQ')
        self.tache = make_tache(self.co, self.projet)
        self.equipe = make_equipe(self.co, 'Equipe Pose Casa')

    def _payload(self, **kw):
        return {
            'tache': self.tache.id,
            'equipe': self.equipe.id,
            'date_debut': '2026-07-10',
            'date_fin': '2026-07-15',
            **kw,
        }

    def test_create_par_equipe(self):
        resp = auth(self.user).post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = AffectationRessource.objects.get(id=resp.data['id'])
        self.assertEqual(obj.equipe, self.equipe)
        self.assertIsNone(obj.ressource)
        self.assertIsNone(obj.actif_id)

    def test_equipe_nom_in_response(self):
        resp = auth(self.user).post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['equipe_nom'], 'Equipe Pose Casa')


class AffectationParActifTests(TestCase):

    def setUp(self):
        self.co = make_company('proj16-af', 'Societe C')
        self.user = make_user(self.co, 'proj16-af-u')
        self.projet = make_projet(self.co, 'P16-AF')
        self.tache = make_tache(self.co, self.projet)

    def _payload(self, **kw):
        return {
            'tache': self.tache.id,
            'actif_type': 'actif_flotte',
            'actif_id': 42,
            'date_debut': '2026-08-01',
            'date_fin': '2026-08-03',
            **kw,
        }

    def test_create_par_actif_lache(self):
        resp = auth(self.user).post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = AffectationRessource.objects.get(id=resp.data['id'])
        self.assertEqual(obj.actif_type, 'actif_flotte')
        self.assertEqual(obj.actif_id, 42)
        self.assertIsNone(obj.ressource)
        self.assertIsNone(obj.equipe)


# ---------------------------------------------------------------------------
# Validation : exactement un vecteur
# ---------------------------------------------------------------------------

class AffectationValidationVecteurTests(TestCase):

    def setUp(self):
        self.co = make_company('proj16-val', 'Societe Val')
        self.user = make_user(self.co, 'proj16-val-u')
        self.projet = make_projet(self.co, 'P16-VAL')
        self.tache = make_tache(self.co, self.projet)
        self.ressource = make_ressource(self.co, 'Ressource Val')
        self.equipe = make_equipe(self.co, 'Equipe Val')

    def test_zero_vecteur_refuse(self):
        """Aucun vecteur renseigne -> 400."""
        payload = {
            'tache': self.tache.id,
            'date_debut': '2026-07-01',
            'date_fin': '2026-07-05',
        }
        resp = auth(self.user).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_deux_vecteurs_refuse(self):
        """Ressource + equipe simultanement -> 400."""
        payload = {
            'tache': self.tache.id,
            'ressource': self.ressource.id,
            'equipe': self.equipe.id,
            'date_debut': '2026-07-01',
            'date_fin': '2026-07-05',
        }
        resp = auth(self.user).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_ressource_et_actif_refuse(self):
        """Ressource + actif -> 400."""
        payload = {
            'tache': self.tache.id,
            'ressource': self.ressource.id,
            'actif_type': 'actif_flotte',
            'actif_id': 7,
            'date_debut': '2026-07-01',
            'date_fin': '2026-07-05',
        }
        resp = auth(self.user).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_date_fin_anterieure_debut_refuse(self):
        """date_fin < date_debut -> 400."""
        payload = {
            'tache': self.tache.id,
            'ressource': self.ressource.id,
            'date_debut': '2026-07-10',
            'date_fin': '2026-07-05',
        }
        resp = auth(self.user).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_actif_type_sans_actif_id_refuse(self):
        """actif_type renseigne mais actif_id absent -> vecteur incomplet -> 400."""
        payload = {
            'tache': self.tache.id,
            'actif_type': 'actif_flotte',
            # actif_id absent
            'date_debut': '2026-07-01',
            'date_fin': '2026-07-05',
        }
        resp = auth(self.user).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


# ---------------------------------------------------------------------------
# Isolation entre societes
# ---------------------------------------------------------------------------

class AffectationIsolationTests(TestCase):

    def setUp(self):
        self.co_a = make_company('proj16-iso-a', 'A')
        self.co_b = make_company('proj16-iso-b', 'B')
        self.user_a = make_user(self.co_a, 'proj16-iso-ua')
        self.user_b = make_user(self.co_b, 'proj16-iso-ub')
        projet_a = make_projet(self.co_a, 'ISO-A')
        self.tache_a = make_tache(self.co_a, projet_a)
        self.ressource_a = make_ressource(self.co_a, 'Ressource Iso A')
        # Creer une affectation pour co_a
        self.affectation_a = AffectationRessource.objects.create(
            company=self.co_a,
            tache=self.tache_a,
            ressource=self.ressource_a,
            date_debut=date(2026, 7, 1),
            date_fin=date(2026, 7, 5),
        )

    def test_list_isolation(self):
        resp = auth(self.user_b).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_detail_isolation(self):
        resp = auth(self.user_b).get(f'{BASE}{self.affectation_a.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_tache_autre_societe_refuse(self):
        """Tache d'une autre societe -> 400."""
        co_b = self.co_b
        proj_b = make_projet(co_b, 'ISO-B')
        tache_b = make_tache(co_b, proj_b)
        ressource_b = make_ressource(co_b, 'Ressource Iso B')
        payload = {
            'tache': tache_b.id,
            'ressource': ressource_b.id,
            'date_debut': '2026-07-01',
            'date_fin': '2026-07-05',
        }
        # user_a essaie d'affecter la tache de co_b
        resp = auth(self.user_a).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_ressource_autre_societe_refuse(self):
        """Ressource d'une autre societe -> 400."""
        ressource_b = make_ressource(self.co_b, 'Ressource B pour A')
        payload = {
            'tache': self.tache_a.id,
            'ressource': ressource_b.id,
            'date_debut': '2026-07-01',
            'date_fin': '2026-07-05',
        }
        resp = auth(self.user_a).post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


# ---------------------------------------------------------------------------
# Filtres
# ---------------------------------------------------------------------------

class AffectationFiltresTests(TestCase):

    def setUp(self):
        self.co = make_company('proj16-flt', 'Societe Filtre')
        self.user = make_user(self.co, 'proj16-flt-u')
        self.projet = make_projet(self.co, 'FLT')
        self.tache1 = make_tache(self.co, self.projet, 'Tache 1')
        self.tache2 = make_tache(self.co, self.projet, 'Tache 2')
        self.ressource = make_ressource(self.co, 'Ressource Filtre')
        self.equipe = make_equipe(self.co, 'Equipe Filtre')
        self.aff1 = AffectationRessource.objects.create(
            company=self.co,
            tache=self.tache1,
            ressource=self.ressource,
            date_debut=date(2026, 7, 1),
            date_fin=date(2026, 7, 3),
        )
        self.aff2 = AffectationRessource.objects.create(
            company=self.co,
            tache=self.tache2,
            equipe=self.equipe,
            date_debut=date(2026, 7, 5),
            date_fin=date(2026, 7, 10),
        )

    def test_filter_par_tache(self):
        resp = auth(self.user).get(f'{BASE}?tache={self.tache1.id}')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.aff1.id, ids)
        self.assertNotIn(self.aff2.id, ids)

    def test_filter_par_projet(self):
        resp = auth(self.user).get(f'{BASE}?projet={self.projet.id}')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.aff1.id, ids)
        self.assertIn(self.aff2.id, ids)

    def test_filter_par_ressource(self):
        resp = auth(self.user).get(f'{BASE}?ressource={self.ressource.id}')
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.aff1.id, ids)
        self.assertNotIn(self.aff2.id, ids)

    def test_filter_par_equipe(self):
        resp = auth(self.user).get(f'{BASE}?equipe={self.equipe.id}')
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(self.aff1.id, ids)
        self.assertIn(self.aff2.id, ids)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'proj16-flt-normal', role='normal')
        resp = auth(normal).get(BASE)
        self.assertEqual(resp.status_code, 403)
