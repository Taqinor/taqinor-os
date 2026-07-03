"""Tests XRH8 — horaires de travail par gabarit (44 h, Ramadan, saisonnier).

Couvre :
* ``selectors.horaire_actif`` : résout l'horaire temporaire dans sa fenêtre,
  retombe sur ``None`` (→ seuil par défaut) hors fenêtre ou sans horaire ;
  un horaire permanent (bornes vides) s'applique toujours ;
* activer un horaire Ramadan (6 h/j) ABAISSE le seuil HS sur sa période
  (``HeuresSuppViewSet`` dérive le seuil quand non fourni explicitement) ;
* retour automatique au standard (8 h) après ``date_fin`` ;
* un ``seuil_journalier`` fourni explicitement n'est jamais écrasé ;
* isolation multi-société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.rh import selectors
from apps.rh.models import DossierEmploye, HoraireTravail

User = get_user_model()

HS_URL = '/api/django/rh/heures-supp/'


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


class HoraireActifSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('hor-a', 'A')

    def test_horaire_permanent_toujours_actif(self):
        horaire = HoraireTravail.objects.create(
            company=self.co, nom='Standard', heures_jour_defaut=Decimal('8'))
        emp = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='X', prenom='Y',
            horaire=horaire)
        self.assertEqual(
            selectors.horaire_actif(emp, date(2026, 1, 1)), horaire)
        self.assertEqual(
            selectors.horaire_actif(emp, date(2030, 6, 6)), horaire)

    def test_horaire_temporaire_dans_la_fenetre(self):
        ramadan = HoraireTravail.objects.create(
            company=self.co, nom='Ramadan 2026', type_horaire='ramadan',
            heures_jour_defaut=Decimal('6'),
            date_debut=date(2026, 3, 1), date_fin=date(2026, 3, 30))
        emp = DossierEmploye.objects.create(
            company=self.co, matricule='E2', nom='X', prenom='Y',
            horaire=ramadan)
        self.assertEqual(
            selectors.horaire_actif(emp, date(2026, 3, 15)), ramadan)
        self.assertEqual(
            selectors.horaire_actif(emp, date(2026, 3, 1)), ramadan)
        self.assertEqual(
            selectors.horaire_actif(emp, date(2026, 3, 30)), ramadan)

    def test_retour_automatique_apres_date_fin(self):
        ramadan = HoraireTravail.objects.create(
            company=self.co, nom='Ramadan 2026', type_horaire='ramadan',
            heures_jour_defaut=Decimal('6'),
            date_debut=date(2026, 3, 1), date_fin=date(2026, 3, 30))
        emp = DossierEmploye.objects.create(
            company=self.co, matricule='E3', nom='X', prenom='Y',
            horaire=ramadan)
        self.assertIsNone(selectors.horaire_actif(emp, date(2026, 4, 1)))
        self.assertIsNone(selectors.horaire_actif(emp, date(2026, 2, 28)))

    def test_sans_horaire_assigne_none(self):
        emp = DossierEmploye.objects.create(
            company=self.co, matricule='E4', nom='X', prenom='Y')
        self.assertIsNone(selectors.horaire_actif(emp))

    def test_horaire_inactif_none(self):
        horaire = HoraireTravail.objects.create(
            company=self.co, nom='Désactivé', actif=False)
        emp = DossierEmploye.objects.create(
            company=self.co, matricule='E5', nom='X', prenom='Y',
            horaire=horaire)
        self.assertIsNone(selectors.horaire_actif(emp, date(2026, 1, 1)))


class HeuresSuppSeuilDeriveTests(TestCase):
    def setUp(self):
        self.co = make_company('hor-hs-a', 'A')
        self.user = make_user(self.co, 'hor-hs-a')

    def test_ramadan_abaisse_seuil_hs(self):
        ramadan = HoraireTravail.objects.create(
            company=self.co, nom='Ramadan', type_horaire='ramadan',
            heures_jour_defaut=Decimal('6'),
            date_debut=date(2026, 3, 1), date_fin=date(2026, 3, 30))
        emp = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='X', prenom='Y',
            horaire=ramadan, cout_horaire=Decimal('50'))
        # 7h travaillées en Ramadan (seuil 6h) → 1h supplémentaire (25%).
        resp = auth(self.user).post(HS_URL, {
            'employe': emp.id, 'date': '2026-03-15',
            'heures_travaillees': '7'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['heures_normales']), Decimal('6.00'))
        self.assertEqual(Decimal(resp.data['hs_25']), Decimal('1.00'))

    def test_retour_standard_hors_fenetre(self):
        ramadan = HoraireTravail.objects.create(
            company=self.co, nom='Ramadan', type_horaire='ramadan',
            heures_jour_defaut=Decimal('6'),
            date_debut=date(2026, 3, 1), date_fin=date(2026, 3, 30))
        emp = DossierEmploye.objects.create(
            company=self.co, matricule='E2', nom='X', prenom='Y',
            horaire=ramadan, cout_horaire=Decimal('50'))
        # Même 7h mais HORS fenêtre Ramadan → seuil standard 8h, pas d'HS.
        resp = auth(self.user).post(HS_URL, {
            'employe': emp.id, 'date': '2026-04-15',
            'heures_travaillees': '7'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['heures_normales']), Decimal('7.00'))
        self.assertEqual(Decimal(resp.data['hs_25']), Decimal('0.00'))

    def test_seuil_explicite_jamais_ecrase(self):
        ramadan = HoraireTravail.objects.create(
            company=self.co, nom='Ramadan', type_horaire='ramadan',
            heures_jour_defaut=Decimal('6'),
            date_debut=date(2026, 3, 1), date_fin=date(2026, 3, 30))
        emp = DossierEmploye.objects.create(
            company=self.co, matricule='E3', nom='X', prenom='Y',
            horaire=ramadan, cout_horaire=Decimal('50'))
        # Le client force explicitement 8h malgré le Ramadan : respecté.
        resp = auth(self.user).post(HS_URL, {
            'employe': emp.id, 'date': '2026-03-15',
            'heures_travaillees': '7', 'seuil_journalier': '8'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['heures_normales']), Decimal('7.00'))
        self.assertEqual(Decimal(resp.data['hs_25']), Decimal('0.00'))

    def test_sans_horaire_seuil_standard_8h(self):
        emp = DossierEmploye.objects.create(
            company=self.co, matricule='E4', nom='X', prenom='Y',
            cout_horaire=Decimal('50'))
        resp = auth(self.user).post(HS_URL, {
            'employe': emp.id, 'date': '2026-06-01',
            'heures_travaillees': '9'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['heures_normales']), Decimal('8.00'))
        self.assertEqual(Decimal(resp.data['hs_25']), Decimal('1.00'))


class HoraireTravailApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('hor-api-a', 'A')
        self.co_b = make_company('hor-api-b', 'B')
        self.user_a = make_user(self.co_a, 'hor-api-a')
        self.user_b = make_user(self.co_b, 'hor-api-b')

    def test_crud_isolation_societe(self):
        HoraireTravail.objects.create(company=self.co_a, nom='Standard A')
        HoraireTravail.objects.create(company=self.co_b, nom='Standard B')
        resp = auth(self.user_a).get('/api/django/rh/horaires-travail/')
        noms = [row['nom'] for row in resp.data.get('results', resp.data)]
        self.assertEqual(noms, ['Standard A'])

    def test_assigner_horaire_a_employe_meme_societe(self):
        horaire = HoraireTravail.objects.create(
            company=self.co_a, nom='Standard A')
        emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='E1', nom='X', prenom='Y')
        resp = auth(self.user_a).patch(
            f'/api/django/rh/employes/{emp.id}/',
            {'horaire': horaire.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_assigner_horaire_autre_societe_refuse(self):
        horaire_b = HoraireTravail.objects.create(
            company=self.co_b, nom='Standard B')
        emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='E2', nom='X', prenom='Y')
        resp = auth(self.user_a).patch(
            f'/api/django/rh/employes/{emp.id}/',
            {'horaire': horaire_b.id}, format='json')
        self.assertEqual(resp.status_code, 400)
