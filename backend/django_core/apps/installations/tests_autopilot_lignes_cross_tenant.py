"""Error-autopilot — isolation multi-tenant en création sur deux ViewSets
« ligne » scopés seulement via leur parent (pas de `company` propre) :

  * ``RetourLivraisonLigneViewSet`` (``retour-livraison-lignes``) :
    ``_check_parent`` valide ``retour.livraison.company_id`` sur update
    uniquement — jamais appelé depuis ``perform_create``.
  * ``OrdreDemontageLigneViewSet`` (``ordre-demontage-lignes``) : même
    lacune, plus le verrou ``ordre.statut == PLANIFIE`` contourné en
    création.

Sans ``perform_create`` appelant ``_check_parent``, un responsable de la
société A peut poster une ligne sur un parent (retour / ordre) de la
société B — le serializer expose des PK writable (`retour`/`ordre`,
`produit`) sur des querysets non filtrés par société.

Run :
    python manage.py test \
        apps.installations.tests_autopilot_lignes_cross_tenant -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.crm.models import Client
from apps.stock.models import EmplacementStock
from apps.installations.models import (
    Installation, Livraison, LivraisonLigne, RetourLivraison,
    RetourLivraisonLigne, Kit, OrdreDemontage, OrdreDemontageLigne,
)

BASE = '/api/django/installations'
_seq = itertools.count(1)


def _n():
    return next(_seq)


def make_company():
    n = _n()
    company, _created = Company.objects.get_or_create(
        slug=f'autopilot-lignes-co-{n}', defaults={'nom': f'Société {n}'})
    return company


def make_user(company, role=CustomUser.ROLE_RESPONSABLE):
    return CustomUser.objects.create_user(
        username=f'autopilot-lignes-{_n()}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company):
    n = _n()
    client = Client.objects.create(
        company=company, nom='Client', prenom=f'Autopilot{n}',
        email=f'autopilot-lignes-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-AUTOP-{n}', client=client,
        statut=Installation.Statut.PLANIFIE)


def make_retour(company):
    """Un `RetourLivraison` (+ sa `Livraison` parente) dans `company`."""
    inst = make_installation(company)
    depot = EmplacementStock.objects.create(
        company=company, nom=f'Dépôt {_n()}', is_principal=True)
    liv = Livraison.objects.create(
        company=company, reference=f'LIV-AUTOP-{_n()}',
        installation=inst, depot=depot, statut=Livraison.Statut.LIVREE)
    LivraisonLigne.objects.create(
        livraison=liv, designation='Batterie', quantite=5)
    return RetourLivraison.objects.create(
        company=company, livraison=liv,
        statut=RetourLivraison.Statut.BROUILLON)


def make_ordre_demontage(company, statut=OrdreDemontage.Statut.PLANIFIE):
    """Un `OrdreDemontage` (+ son `Kit` parent) dans `company`."""
    kit = Kit.objects.create(company=company, nom=f'Kit {_n()}')
    return OrdreDemontage.objects.create(
        company=company, kit=kit, reference=f'DSM-AUTOP-{_n()}',
        statut=statut)


class TestRetourLivraisonLigneCrossTenant(TestCase):
    """`retour-livraison-lignes` : POST sur un retour d'une AUTRE société
    doit être refusé (400/404), jamais créer de ligne."""

    def setUp(self):
        self.company_a = make_company()
        self.company_b = make_company()
        self.user_a = make_user(self.company_a)
        self.api_a = auth(self.user_a)
        self.retour_b = make_retour(self.company_b)

    def test_post_on_other_company_parent_is_refused(self):
        before = RetourLivraisonLigne.objects.filter(
            retour=self.retour_b).count()
        r = self.api_a.post(
            f'{BASE}/retour-livraison-lignes/',
            {'retour': self.retour_b.id, 'designation': 'Batterie',
             'quantite_retournee': 1},
            format='json')
        self.assertIn(r.status_code, (400, 404), r.data)
        if r.status_code == 400:
            self.assertIn('retour', r.data)
        after = RetourLivraisonLigne.objects.filter(
            retour=self.retour_b).count()
        self.assertEqual(before, after)
        self.assertEqual(after, 0)

    def test_post_on_own_company_parent_succeeds(self):
        """Contrôle : le même POST sur un retour de la société A réussit."""
        retour_a = make_retour(self.company_a)
        r = self.api_a.post(
            f'{BASE}/retour-livraison-lignes/',
            {'retour': retour_a.id, 'designation': 'Batterie',
             'quantite_retournee': 1},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            RetourLivraisonLigne.objects.filter(retour=retour_a).count(), 1)


class TestOrdreDemontageLigneCrossTenant(TestCase):
    """`ordre-demontage-lignes` : POST sur un ordre d'une AUTRE société
    doit être refusé (400/404), jamais créer de ligne ; un ordre non
    PLANIFIE refuse aussi la création (verrou contourné en POST)."""

    def setUp(self):
        self.company_a = make_company()
        self.company_b = make_company()
        self.user_a = make_user(self.company_a)
        self.api_a = auth(self.user_a)
        self.ordre_b = make_ordre_demontage(self.company_b)

    def test_post_on_other_company_parent_is_refused(self):
        before = OrdreDemontageLigne.objects.filter(
            ordre=self.ordre_b).count()
        r = self.api_a.post(
            f'{BASE}/ordre-demontage-lignes/',
            {'ordre': self.ordre_b.id, 'designation': 'Onduleur',
             'quantite_attendue': 1, 'quantite_recuperee': 1},
            format='json')
        self.assertIn(r.status_code, (400, 404), r.data)
        if r.status_code == 400:
            self.assertIn('ordre', r.data)
        after = OrdreDemontageLigne.objects.filter(
            ordre=self.ordre_b).count()
        self.assertEqual(before, after)
        self.assertEqual(after, 0)

    def test_post_on_own_company_parent_succeeds(self):
        """Contrôle : le même POST sur un ordre PLANIFIE de la société A
        réussit."""
        ordre_a = make_ordre_demontage(self.company_a)
        r = self.api_a.post(
            f'{BASE}/ordre-demontage-lignes/',
            {'ordre': ordre_a.id, 'designation': 'Onduleur',
             'quantite_attendue': 1, 'quantite_recuperee': 1},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            OrdreDemontageLigne.objects.filter(ordre=ordre_a).count(), 1)

    def test_post_on_non_planifie_own_ordre_is_refused(self):
        """Un ordre TERMINE (même société) refuse aussi la création : le
        verrou `_check_parent` (statut PLANIFIE) ne doit pas être
        contournable en passant par POST plutôt que PATCH."""
        ordre_termine = make_ordre_demontage(
            self.company_a, statut=OrdreDemontage.Statut.TERMINE)
        before = OrdreDemontageLigne.objects.filter(
            ordre=ordre_termine).count()
        r = self.api_a.post(
            f'{BASE}/ordre-demontage-lignes/',
            {'ordre': ordre_termine.id, 'designation': 'Onduleur',
             'quantite_attendue': 1, 'quantite_recuperee': 1},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('ordre', r.data)
        after = OrdreDemontageLigne.objects.filter(
            ordre=ordre_termine).count()
        self.assertEqual(before, after)
        self.assertEqual(after, 0)
