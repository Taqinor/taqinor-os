"""Tests de la sous-traitance & clôture + REX (PROJ38).

Sous-traitants (carnet d'adresses), lots de sous-traitance (montant INTERNE) et
clôture de projet avec retour d'expérience. La clôture transitionne le projet
vers TERMINÉ (journalisée) ; un projet annulé ne peut pas être clôturé.

Couvre : CRUD sous-traitant (company serveur) ; lot même-société ; service
``cloturer_projet`` (REX + transition TERMINÉ + activité) ; refus clôture projet
annulé ; endpoint ``cloturer`` (cloture_par serveur) ; scoping ; accès
Administrateur/Responsable (403 pour ``normal``).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import (
    ClotureProjet,
    LotSousTraitance,
    Projet,
    ProjetActivity,
    SousTraitant,
)

User = get_user_model()


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


class ClotureServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-clo-svc', 'S')
        self.user = make_user(self.co, 'clo-svc')

    def test_cloturer_cree_rex_et_termine(self):
        projet = Projet.objects.create(
            company=self.co, code='P-CLO', nom='P',
            statut=Projet.Statut.EN_COURS)
        cloture = services.cloturer_projet(
            projet, date_cloture=date(2026, 6, 1),
            points_positifs='Bonne coordination',
            recommandations='Anticiper l\'appro', auteur=self.user)
        self.assertEqual(cloture.company_id, self.co.id)
        self.assertEqual(cloture.cloture_par_id, self.user.id)
        projet.refresh_from_db()
        self.assertEqual(projet.statut, Projet.Statut.TERMINE)
        # Transition journalisée.
        self.assertTrue(ProjetActivity.objects.filter(
            projet=projet, new_value=Projet.Statut.TERMINE).exists())

    def test_cloturer_projet_annule_refuse(self):
        projet = Projet.objects.create(
            company=self.co, code='P-ANN', nom='P',
            statut=Projet.Statut.ANNULE)
        with self.assertRaises(services.ClotureError):
            services.cloturer_projet(projet, date_cloture=date(2026, 6, 1))

    def test_cloturer_idempotent_met_a_jour_rex(self):
        projet = Projet.objects.create(
            company=self.co, code='P-IDEM', nom='P',
            statut=Projet.Statut.TERMINE)
        services.cloturer_projet(
            projet, date_cloture=date(2026, 6, 1), points_positifs='v1')
        services.cloturer_projet(
            projet, date_cloture=date(2026, 6, 2), points_positifs='v2')
        self.assertEqual(ClotureProjet.objects.filter(projet=projet).count(), 1)
        self.assertEqual(ClotureProjet.objects.get(projet=projet).points_positifs, 'v2')


class SousTraitanceApiTests(TestCase):
    ST = '/api/django/gestion-projet/sous-traitants/'
    LOTS = '/api/django/gestion-projet/lots-sous-traitance/'
    PROJETS = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-st-a', 'A')
        self.co_b = make_company('gp-st-b', 'B')
        self.user_a = make_user(self.co_a, 'st-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A',
            statut=Projet.Statut.EN_COURS)

    def test_creation_sous_traitant_company_serveur(self):
        api = auth(self.user_a)
        resp = api.post(self.ST, {
            'nom': 'Levage Pro', 'specialite': 'Grue',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        st = SousTraitant.objects.get(id=resp.data['id'])
        self.assertEqual(st.company_id, self.co_a.id)

    def test_lot_meme_societe(self):
        st = SousTraitant.objects.create(company=self.co_a, nom='ST')
        api = auth(self.user_a)
        resp = api.post(self.LOTS, {
            'projet': self.projet.id, 'sous_traitant': st.id,
            'libelle': 'Terrassement', 'montant': '12000',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lot = LotSousTraitance.objects.get(id=resp.data['id'])
        self.assertEqual(lot.montant, Decimal('12000'))

    def test_lot_sous_traitant_autre_societe_refuse(self):
        st_b = SousTraitant.objects.create(company=self.co_b, nom='STB')
        api = auth(self.user_a)
        resp = api.post(self.LOTS, {
            'projet': self.projet.id, 'sous_traitant': st_b.id,
            'libelle': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_cloturer_endpoint(self):
        api = auth(self.user_a)
        resp = api.post(f'{self.PROJETS}{self.projet.id}/cloturer/', {
            'date_cloture': '2026-06-01',
            'points_positifs': 'OK',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.statut, Projet.Statut.TERMINE)

    def test_cloturer_sans_date_400(self):
        api = auth(self.user_a)
        resp = api.post(f'{self.PROJETS}{self.projet.id}/cloturer/', {},
                        format='json')
        self.assertEqual(resp.status_code, 400)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'st-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.ST)
        self.assertEqual(resp.status_code, 403)
