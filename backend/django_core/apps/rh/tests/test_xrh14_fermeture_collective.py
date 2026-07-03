"""Tests XRH14 — Fermetures collectives / congés imposés.

Couvre :
* appliquer une fermeture de 2 j crée N demandes VALIDÉES décomptées (une par
  employé actif concerné) ;
* ré-appliquer ne duplique PAS (idempotent) ;
* un département EXCLU (hors ``departements`` M2M de la fermeture) n'est pas
  touché ;
* ``departements`` vide = toute la société ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    Departement,
    DemandeConge,
    DossierEmploye,
    PeriodeFermeture,
    TypeAbsence,
)

User = get_user_model()

FERMETURES = '/api/django/rh/periodes-fermeture/'


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


class FermetureCollectiveTests(TestCase):
    def setUp(self):
        self.co = make_company('ferm-a', 'A')
        self.rh = make_user(self.co, 'ferm-rh')
        self.type_cp = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=False, deduit_solde=True)
        self.dep_prod = Departement.objects.create(
            company=self.co, nom='Production')
        self.dep_com = Departement.objects.create(
            company=self.co, nom='Commercial')
        self.emp_prod = DossierEmploye.objects.create(
            company=self.co, matricule='F1', nom='Tazi', prenom='Reda',
            departement=self.dep_prod, statut=DossierEmploye.Statut.ACTIF)
        self.emp_com = DossierEmploye.objects.create(
            company=self.co, matricule='F2', nom='Chraibi', prenom='Sanae',
            departement=self.dep_com, statut=DossierEmploye.Statut.ACTIF)

    def _creer_fermeture(self, departements=None):
        resp = auth(self.rh).post(FERMETURES, {
            'libelle': 'Fermeture Aïd',
            'date_debut': '2026-08-10',
            'date_fin': '2026-08-11',
            'type_absence': self.type_cp.id,
            'departements': departements or [],
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['id']

    def test_appliquer_toute_societe_cree_n_demandes(self):
        fermeture_id = self._creer_fermeture()
        resp = auth(self.rh).post(f'{FERMETURES}{fermeture_id}/appliquer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['demandes_creees'], 2)

        demandes = DemandeConge.objects.filter(company=self.co)
        self.assertEqual(demandes.count(), 2)
        for d in demandes:
            self.assertEqual(d.statut, DemandeConge.Statut.VALIDEE)
            self.assertEqual(d.jours, 2)

        fermeture = PeriodeFermeture.objects.get(pk=fermeture_id)
        self.assertTrue(fermeture.appliquee)

    def test_reappliquer_ne_duplique_pas(self):
        fermeture_id = self._creer_fermeture()
        auth(self.rh).post(f'{FERMETURES}{fermeture_id}/appliquer/')
        resp = auth(self.rh).post(f'{FERMETURES}{fermeture_id}/appliquer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['demandes_creees'], 0)
        self.assertEqual(
            DemandeConge.objects.filter(company=self.co).count(), 2)

    def test_departement_exclu_non_touche(self):
        fermeture_id = self._creer_fermeture(
            departements=[self.dep_prod.id])
        resp = auth(self.rh).post(f'{FERMETURES}{fermeture_id}/appliquer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['demandes_creees'], 1)

        demandes = DemandeConge.objects.filter(company=self.co)
        self.assertEqual(demandes.count(), 1)
        self.assertEqual(demandes.first().employe, self.emp_prod)

    def test_isolation_societe(self):
        co_b = make_company('ferm-b', 'B')
        rh_b = make_user(co_b, 'ferm-rh-b')
        fermeture_id = self._creer_fermeture()
        resp = auth(rh_b).post(f'{FERMETURES}{fermeture_id}/appliquer/')
        self.assertEqual(resp.status_code, 404)
