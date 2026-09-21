"""Tests FG162/FG163/FG164/FG165 — soldes, demandes/validation, typologie,
calendrier d'équipe.

Couvre la LOGIQUE de décompte/acquisition (services + holidays) et le workflow
API : décompte jours ouvrés hors fériés/WE, déduction de solde à la validation,
recrédit à l'annulation, isolation société, et le verrou de dispatch (un employé
en congé validé n'est pas assignable).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.rh import holidays, selectors, services
from apps.rh.models import DemandeConge, DossierEmploye, SoldeConge, TypeAbsence

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class HolidaysTests(TestCase):
    def test_working_days_skips_weekend(self):
        # 2026-06-22 (lundi) → 2026-06-28 (dimanche) = 5 jours ouvrés.
        n = holidays.working_days(date(2026, 6, 22), date(2026, 6, 28))
        self.assertEqual(n, 5)

    def test_working_days_skips_fixed_holiday(self):
        # 2026-05-01 (Fête du Travail) tombe un vendredi : exclu.
        # plage vendredi 2026-05-01 → vendredi 2026-05-08
        # jours ouvrés = 04,05,06,07,08 (lun-ven) = 5 ; le 01 férié exclu.
        n = holidays.working_days(date(2026, 5, 1), date(2026, 5, 8))
        self.assertEqual(n, 5)

    def test_calendar_days_inclusive(self):
        self.assertEqual(
            holidays.calendar_days(date(2026, 6, 1), date(2026, 6, 3)), 3)

    def test_invalid_range_zero(self):
        self.assertEqual(
            holidays.working_days(date(2026, 6, 5), date(2026, 6, 1)), 0)


class AcquisitionTests(TestCase):
    def test_droit_annuel_base_18(self):
        self.assertEqual(services.droit_annuel(0), Decimal('18.00'))

    def test_bonus_anciennete(self):
        self.assertEqual(services.bonus_anciennete(4), Decimal('0'))
        self.assertEqual(services.bonus_anciennete(5), Decimal('1.5'))
        self.assertEqual(services.bonus_anciennete(11), Decimal('3.0'))

    def test_droit_annuel_avec_anciennete(self):
        self.assertEqual(services.droit_annuel(6), Decimal('19.50'))

    def test_acquisition_mensuelle_base(self):
        self.assertEqual(services.acquisition_mensuelle(0), Decimal('1.50'))


class DemandeCongeTests(TestCase):
    BASE = '/api/django/rh/demandes-conge/'

    def setUp(self):
        self.co_a = make_company('cg-a', 'A')
        self.co_b = make_company('cg-b', 'B')
        self.user_a = make_user(self.co_a, 'cg-a')
        self.user_b = make_user(self.co_b, 'cg-b')
        self.emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='E1', nom='X', prenom='Y')
        self.cp = TypeAbsence.objects.create(
            company=self.co_a, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=True, deduit_solde=True)
        self.sans_solde = TypeAbsence.objects.create(
            company=self.co_a, code='SS', libelle='Sans solde',
            decompte_jours_ouvres=True, deduit_solde=False)

    def test_create_computes_jours_ouvres(self):
        # lundi 2026-06-22 → dimanche 2026-06-28 = 5 jours ouvrés.
        resp = auth(self.user_a).post(self.BASE, {
            'employe': self.emp.id, 'type_absence': self.cp.id,
            'date_debut': '2026-06-22', 'date_fin': '2026-06-28'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data['jours']), Decimal('5'))
        self.assertEqual(resp.data['statut'], 'soumise')

    def test_validation_deduit_solde(self):
        SoldeConge.objects.create(
            company=self.co_a, employe=self.emp, annee=2026,
            acquis=Decimal('18'))
        demande = DemandeConge.objects.create(
            company=self.co_a, employe=self.emp, type_absence=self.cp,
            date_debut=date(2026, 6, 22), date_fin=date(2026, 6, 28),
            jours=Decimal('5'))
        resp = auth(self.user_a).post(
            f'{self.BASE}{demande.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'validee')
        solde = SoldeConge.objects.get(employe=self.emp, annee=2026)
        self.assertEqual(solde.pris, Decimal('5'))
        self.assertEqual(solde.disponible, Decimal('13'))

    def test_sans_solde_ne_deduit_pas(self):
        SoldeConge.objects.create(
            company=self.co_a, employe=self.emp, annee=2026,
            acquis=Decimal('18'))
        demande = DemandeConge.objects.create(
            company=self.co_a, employe=self.emp, type_absence=self.sans_solde,
            date_debut=date(2026, 6, 22), date_fin=date(2026, 6, 24),
            jours=Decimal('3'))
        services.valider_demande(demande)
        solde = SoldeConge.objects.get(employe=self.emp, annee=2026)
        self.assertEqual(solde.pris, Decimal('0'))

    def test_refuser_demande(self):
        demande = DemandeConge.objects.create(
            company=self.co_a, employe=self.emp, type_absence=self.cp,
            date_debut=date(2026, 6, 22), date_fin=date(2026, 6, 24),
            jours=Decimal('3'))
        resp = auth(self.user_a).post(
            f'{self.BASE}{demande.id}/refuser/',
            {'motif_refus': 'Période de pointe'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'refusee')
        self.assertEqual(resp.data['motif_refus'], 'Période de pointe')

    def test_annuler_recredite_solde(self):
        solde = SoldeConge.objects.create(
            company=self.co_a, employe=self.emp, annee=2026,
            acquis=Decimal('18'), pris=Decimal('5'))
        demande = DemandeConge.objects.create(
            company=self.co_a, employe=self.emp, type_absence=self.cp,
            date_debut=date(2026, 6, 22), date_fin=date(2026, 6, 28),
            jours=Decimal('5'), statut=DemandeConge.Statut.VALIDEE)
        services.annuler_demande(demande)
        solde.refresh_from_db()
        self.assertEqual(solde.pris, Decimal('0'))

    def test_valider_refuse_si_pas_soumise(self):
        demande = DemandeConge.objects.create(
            company=self.co_a, employe=self.emp, type_absence=self.cp,
            date_debut=date(2026, 6, 22), date_fin=date(2026, 6, 24),
            jours=Decimal('3'), statut=DemandeConge.Statut.VALIDEE)
        resp = auth(self.user_a).post(
            f'{self.BASE}{demande.id}/valider/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_date_fin_avant_debut_refuse(self):
        resp = auth(self.user_a).post(self.BASE, {
            'employe': self.emp.id, 'type_absence': self.cp.id,
            'date_debut': '2026-06-28', 'date_fin': '2026-06-22'},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_type_autre_societe(self):
        type_b = TypeAbsence.objects.create(
            company=self.co_b, code='CP', libelle='CP')
        resp = auth(self.user_a).post(self.BASE, {
            'employe': self.emp.id, 'type_absence': type_b.id,
            'date_debut': '2026-06-22', 'date_fin': '2026-06-24'},
            format='json')
        self.assertEqual(resp.status_code, 400)


class CalendrierEquipeTests(TestCase):
    def setUp(self):
        self.co = make_company('cal-a', 'A')
        self.user = make_user(self.co, 'cal-a')
        self.emp1 = DossierEmploye.objects.create(
            company=self.co, matricule='T1', nom='A', prenom='A',
            statut=DossierEmploye.Statut.ACTIF)
        self.emp2 = DossierEmploye.objects.create(
            company=self.co, matricule='T2', nom='B', prenom='B',
            statut=DossierEmploye.Statut.ACTIF)
        self.cp = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='CP')
        # emp1 en congé validé du 22 au 26 juin.
        DemandeConge.objects.create(
            company=self.co, employe=self.emp1, type_absence=self.cp,
            date_debut=date(2026, 6, 22), date_fin=date(2026, 6, 26),
            jours=Decimal('5'), statut=DemandeConge.Statut.VALIDEE)

    def test_employe_absent_le(self):
        self.assertTrue(selectors.employe_absent_le(
            self.co, self.emp1.id, date(2026, 6, 24)))
        self.assertFalse(selectors.employe_absent_le(
            self.co, self.emp1.id, date(2026, 7, 1)))

    def test_employes_assignables_exclut_absent(self):
        ids = list(selectors.employes_assignables(
            self.co, date(2026, 6, 24)).values_list('id', flat=True))
        self.assertNotIn(self.emp1.id, ids)
        self.assertIn(self.emp2.id, ids)

    def test_soumise_non_bloquante(self):
        # une demande seulement SOUMISE ne bloque pas le dispatch.
        DemandeConge.objects.create(
            company=self.co, employe=self.emp2, type_absence=self.cp,
            date_debut=date(2026, 6, 24), date_fin=date(2026, 6, 24),
            jours=Decimal('1'), statut=DemandeConge.Statut.SOUMISE)
        ids = list(selectors.employes_assignables(
            self.co, date(2026, 6, 24)).values_list('id', flat=True))
        self.assertIn(self.emp2.id, ids)

    def test_calendrier_endpoint(self):
        resp = auth(self.user).get(
            '/api/django/rh/demandes-conge/calendrier-equipe/'
            '?debut=2026-06-20&fin=2026-06-30')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)
