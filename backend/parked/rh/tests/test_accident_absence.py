"""Tests YHIRE10 — Un accident du travail avec arrêt produit l'absence
correspondante (roster + import paie), synchronisée à chaque màj.

Couvre :
* Un AT 5 j d'arrêt crée UNE ``DemandeConge`` validée du type AT, couvrant
  date_accident → date_accident+4.
* Prolongation (màj ``nb_jours_arret``) ÉTEND la même ligne (jamais de
  doublon).
* Retrait de l'arrêt (``arret_travail=False``) annule l'absence liée.
* Sans arrêt déclaré (``arret_travail=False`` dès la création) — aucune
  absence créée.
* API : création via le viewset propage l'effet ; màj aussi.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import AccidentTravail, DemandeConge, DossierEmploye, TypeAbsence

User = get_user_model()

URL = '/api/django/rh/accidents-travail/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P')


def seed_type_at(company):
    return TypeAbsence.objects.create(
        company=company, code='AT', libelle='Accident du travail',
        decompte_jours_ouvres=False, deduit_solde=False, remunere=True,
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SynchroniserAbsenceAccidentServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('yhire10-a', 'A')
        self.employe = make_employe(self.company, 'M1')
        seed_type_at(self.company)

    def test_at_avec_arret_cree_absence(self):
        accident = AccidentTravail.objects.create(
            company=self.company, employe=self.employe, reference='AT-1',
            date_accident=timezone.localdate(),
            arret_travail=True, nb_jours_arret=5,
        )
        demande = services.synchroniser_absence_accident_travail(accident)
        self.assertIsNotNone(demande)
        self.assertEqual(demande.statut, DemandeConge.Statut.VALIDEE)
        self.assertEqual(demande.jours, 5)
        self.assertEqual(demande.date_debut, accident.date_accident)

    def test_prolongation_etend_meme_ligne(self):
        accident = AccidentTravail.objects.create(
            company=self.company, employe=self.employe, reference='AT-2',
            date_accident=timezone.localdate(),
            arret_travail=True, nb_jours_arret=3,
        )
        services.synchroniser_absence_accident_travail(accident)
        accident.nb_jours_arret = 7
        accident.save(update_fields=['nb_jours_arret'])
        services.synchroniser_absence_accident_travail(accident)

        demandes = DemandeConge.objects.filter(employe=self.employe).exclude(
            statut=DemandeConge.Statut.ANNULEE)
        self.assertEqual(demandes.count(), 1)
        self.assertEqual(demandes.first().jours, 7)

    def test_retrait_arret_annule_absence(self):
        accident = AccidentTravail.objects.create(
            company=self.company, employe=self.employe, reference='AT-3',
            date_accident=timezone.localdate(),
            arret_travail=True, nb_jours_arret=2,
        )
        services.synchroniser_absence_accident_travail(accident)
        accident.arret_travail = False
        accident.save(update_fields=['arret_travail'])
        services.synchroniser_absence_accident_travail(accident)

        demande = DemandeConge.objects.get(employe=self.employe)
        self.assertEqual(demande.statut, DemandeConge.Statut.ANNULEE)

    def test_sans_arret_aucune_absence(self):
        accident = AccidentTravail.objects.create(
            company=self.company, employe=self.employe, reference='AT-4',
            date_accident=timezone.localdate(),
            arret_travail=False, nb_jours_arret=0,
        )
        result = services.synchroniser_absence_accident_travail(accident)
        self.assertIsNone(result)
        self.assertEqual(
            DemandeConge.objects.filter(employe=self.employe).count(), 0)


class AccidentTravailApiEffectsTests(TestCase):
    def setUp(self):
        self.company = make_company('yhire10-api', 'API')
        self.admin = make_user(self.company, 'admin-yhire10', role='admin')
        self.employe = make_employe(self.company, 'M2')
        seed_type_at(self.company)

    def test_creation_avec_arret_propage(self):
        api = auth(self.admin)
        resp = api.post(URL, {
            'employe': self.employe.pk,
            'date_accident': timezone.localdate().isoformat(),
            'arret_travail': True,
            'nb_jours_arret': 4,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            DemandeConge.objects.filter(employe=self.employe).count(), 1)

    def test_maj_prolonge_arret(self):
        api = auth(self.admin)
        create = api.post(URL, {
            'employe': self.employe.pk,
            'date_accident': timezone.localdate().isoformat(),
            'arret_travail': True,
            'nb_jours_arret': 3,
        })
        accident_id = create.data['id']
        resp = api.patch(f'{URL}{accident_id}/', {'nb_jours_arret': 10})
        self.assertEqual(resp.status_code, 200, resp.data)
        demandes = DemandeConge.objects.filter(
            employe=self.employe).exclude(
            statut=DemandeConge.Statut.ANNULEE)
        self.assertEqual(demandes.count(), 1)
        self.assertEqual(demandes.first().jours, 10)
