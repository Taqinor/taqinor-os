"""Tests YHIRE11 — Relier le conducteur flotte au dossier employé.

Couvre :
- ``Conducteur.employe_id`` (string-ref nullable vers ``rh.DossierEmploye``) :
  additif, un conducteur EXTERNE (``employe_id`` vide) garde le comportement
  historique inchangé.
- ``services.controle_permis`` : quand le conducteur est LIÉ à un dossier RH,
  la validité RH (``rh.selectors.peut_conduire``) PRIME sur les champs
  locaux — un permis RH expiré est refusé/averti à l'affectation même si les
  champs locaux du ``Conducteur`` semblent valides ; un permis RH valide fait
  passer l'affectation même si les champs locaux sont vides.
- ``selectors.affectations_ouvertes_pour_employe`` : liste les affectations
  flotte OUVERTES d'un employé lié, vide pour un employé sans lien.
- ``selectors.divergences_permis_flotte_rh`` : rapport de réconciliation.
- API d'affectation ``/affectations/`` avec ``force`` (soft-warn) pour un
  conducteur lié dont le permis RH est expiré.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import AffectationConducteur, Conducteur, Vehicule
from apps.flotte.selectors import (
    affectations_ouvertes_pour_employe, divergences_permis_flotte_rh,
)
from apps.flotte.services import controle_permis

User = get_user_model()

URL_AFFECT = '/api/django/flotte/affectations/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_vehicule(company, immat='YH11', categorie_requise='B'):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie='diesel',
        categorie_permis_requise=categorie_requise)


def make_conducteur(company, employe_id=None, **kwargs):
    defaults = dict(nom='Conducteur Test', employe_id=employe_id)
    defaults.update(kwargs)
    return Conducteur.objects.create(company=company, **defaults)


def make_dossier_employe(company, matricule='EMP1'):
    """Créé via ``apps.rh.models`` (dépendance de test uniquement — la
    flotte, elle, ne l'importe JAMAIS)."""
    from apps.rh.models import DossierEmploye
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P')


def make_permis_rh(company, employe, categorie='B', date_expiration=None):
    from apps.rh.models import PermisConduire
    return PermisConduire.objects.create(
        company=company, employe=employe, categorie=categorie,
        numero='PRH-1', date_expiration=date_expiration)


class ConducteurEmployeIdModelTests(TestCase):
    def setUp(self):
        self.co = make_company('yh11-model', 'YH11 Model')

    def test_conducteur_externe_sans_lien(self):
        """Additif : employe_id vide = comportement historique, aucune
        régression."""
        conducteur = make_conducteur(self.co, employe_id=None, categorie_permis='B')
        self.assertIsNone(conducteur.employe_id)


class ControlePermisRhPrimeTests(TestCase):
    def setUp(self):
        self.co = make_company('yh11-permis', 'YH11 Permis')
        self.vehicule = make_vehicule(self.co, categorie_requise='B')
        self.today = datetime.date.today()

    def test_conducteur_externe_garde_comportement_local(self):
        """Un conducteur SANS lien RH est contrôlé sur ses champs locaux
        (comportement FLOTTE9 historique, inchangé)."""
        conducteur = make_conducteur(
            self.co, employe_id=None, numero_permis='L1',
            categorie_permis='B',
            date_expiration=self.today + datetime.timedelta(days=365))
        ok, code, _msg = controle_permis(conducteur, self.vehicule)
        self.assertTrue(ok)
        self.assertEqual(code, '')

    def test_conducteur_lie_permis_rh_expire_refuse(self):
        """Le permis RH est expiré : REFUSÉ même si les champs locaux du
        Conducteur semblent valides (le lien RH PRIME)."""
        dossier = make_dossier_employe(self.co, 'EMP-EXP')
        make_permis_rh(
            self.co, dossier, categorie='B',
            date_expiration=self.today - datetime.timedelta(days=1))
        conducteur = make_conducteur(
            self.co, employe_id=dossier.pk, numero_permis='LOCAL-OK',
            categorie_permis='B',
            date_expiration=self.today + datetime.timedelta(days=365))
        ok, code, _msg = controle_permis(conducteur, self.vehicule)
        self.assertFalse(ok)
        self.assertEqual(code, 'permis_rh_invalide')

    def test_conducteur_lie_permis_rh_valide_accepte(self):
        """Le permis RH est valide : ACCEPTÉ même si les champs locaux du
        Conducteur sont vides (repli only, RH prime)."""
        dossier = make_dossier_employe(self.co, 'EMP-OK')
        make_permis_rh(
            self.co, dossier, categorie='B',
            date_expiration=self.today + datetime.timedelta(days=365))
        conducteur = make_conducteur(
            self.co, employe_id=dossier.pk, numero_permis='', categorie_permis='')
        ok, code, _msg = controle_permis(conducteur, self.vehicule)
        self.assertTrue(ok)
        self.assertEqual(code, '')

    def test_vehicule_sans_exigence_toujours_libre(self):
        """Comportement historique préservé : aucune catégorie exigée = pas
        de contrôle, même pour un conducteur lié."""
        dossier = make_dossier_employe(self.co, 'EMP-NOREQ')
        conducteur = make_conducteur(self.co, employe_id=dossier.pk)
        vehicule_libre = make_vehicule(
            self.co, immat='YH11-LIBRE', categorie_requise='')
        ok, _code, _msg = controle_permis(conducteur, vehicule_libre)
        self.assertTrue(ok)


class AffectationsOuvertesPourEmployeTests(TestCase):
    def setUp(self):
        self.co = make_company('yh11-affect', 'YH11 Affect')

    def test_liste_les_affectations_ouvertes(self):
        dossier = make_dossier_employe(self.co, 'EMP-AFF')
        conducteur = make_conducteur(self.co, employe_id=dossier.pk)
        vehicule = make_vehicule(self.co, immat='YH11-V1', categorie_requise='')
        AffectationConducteur.objects.create(
            company=self.co, conducteur=conducteur, vehicule=vehicule,
            date_debut=datetime.date.today(), actif=True)

        resultat = affectations_ouvertes_pour_employe(self.co, dossier.pk)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]['vehicule_id'], vehicule.id)

    def test_conducteur_externe_jamais_retourne(self):
        conducteur = make_conducteur(self.co, employe_id=None)
        vehicule = make_vehicule(self.co, immat='YH11-V2', categorie_requise='')
        AffectationConducteur.objects.create(
            company=self.co, conducteur=conducteur, vehicule=vehicule,
            date_debut=datetime.date.today(), actif=True)
        resultat = affectations_ouvertes_pour_employe(self.co, 99999)
        self.assertEqual(resultat, [])

    def test_employe_id_vide_renvoie_liste_vide(self):
        self.assertEqual(affectations_ouvertes_pour_employe(self.co, None), [])

    def test_affectation_cloturee_non_retournee(self):
        dossier = make_dossier_employe(self.co, 'EMP-CLOS')
        conducteur = make_conducteur(self.co, employe_id=dossier.pk)
        vehicule = make_vehicule(self.co, immat='YH11-V3', categorie_requise='')
        AffectationConducteur.objects.create(
            company=self.co, conducteur=conducteur, vehicule=vehicule,
            date_debut=datetime.date.today(), actif=False)
        self.assertEqual(
            affectations_ouvertes_pour_employe(self.co, dossier.pk), [])


class DivergencesPermisFlotteRhTests(TestCase):
    def setUp(self):
        self.co = make_company('yh11-diverg', 'YH11 Diverg')
        self.today = datetime.date.today()

    def test_divergence_detectee_local_valide_rh_invalide(self):
        dossier = make_dossier_employe(self.co, 'EMP-DIV1')
        make_permis_rh(
            self.co, dossier, categorie='B',
            date_expiration=self.today - datetime.timedelta(days=10))
        make_conducteur(
            self.co, employe_id=dossier.pk,
            date_expiration=self.today + datetime.timedelta(days=100))

        rapport = divergences_permis_flotte_rh(self.co)
        self.assertEqual(rapport['nb_divergences'], 1)
        self.assertEqual(rapport['nb_conducteurs_lies'], 1)
        self.assertTrue(rapport['divergences'][0]['local_valide'])
        self.assertFalse(rapport['divergences'][0]['rh_valide'])

    def test_pas_de_divergence_quand_les_deux_concordent(self):
        dossier = make_dossier_employe(self.co, 'EMP-DIV2')
        make_permis_rh(
            self.co, dossier, categorie='B',
            date_expiration=self.today + datetime.timedelta(days=100))
        make_conducteur(
            self.co, employe_id=dossier.pk,
            date_expiration=self.today + datetime.timedelta(days=100))
        rapport = divergences_permis_flotte_rh(self.co)
        self.assertEqual(rapport['nb_divergences'], 0)

    def test_conducteur_externe_jamais_inclus(self):
        make_conducteur(self.co, employe_id=None)
        rapport = divergences_permis_flotte_rh(self.co)
        self.assertEqual(rapport['nb_conducteurs_lies'], 0)


class AffectationApiRhPrimeTests(TestCase):
    def setUp(self):
        self.co = make_company('yh11-api', 'YH11 Api')
        self.admin = make_user(self.co, 'yh11-admin', 'admin')
        self.today = datetime.date.today().isoformat()

    def test_affectation_refusee_permis_rh_expire(self):
        dossier = make_dossier_employe(self.co, 'EMP-API1')
        make_permis_rh(
            self.co, dossier, categorie='B',
            date_expiration=datetime.date.today() - datetime.timedelta(days=1))
        conducteur = make_conducteur(
            self.co, employe_id=dossier.pk, numero_permis='X',
            categorie_permis='B')
        vehicule = make_vehicule(self.co, categorie_requise='B')

        resp = auth(self.admin).post(URL_AFFECT, {
            'conducteur': conducteur.id, 'vehicule': vehicule.id,
            'date_debut': self.today,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_affectation_forcee_soft_warn(self):
        dossier = make_dossier_employe(self.co, 'EMP-API2')
        make_permis_rh(
            self.co, dossier, categorie='B',
            date_expiration=datetime.date.today() - datetime.timedelta(days=1))
        conducteur = make_conducteur(
            self.co, employe_id=dossier.pk, numero_permis='X',
            categorie_permis='B')
        vehicule = make_vehicule(self.co, categorie_requise='B')

        resp = auth(self.admin).post(URL_AFFECT, {
            'conducteur': conducteur.id, 'vehicule': vehicule.id,
            'date_debut': self.today, 'force': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNotNone(resp.data['permis_avertissement'])
