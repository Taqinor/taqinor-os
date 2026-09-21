"""Tests NTHCM29 — corrélation formation → performance (ROI simple du LMS).

Couvre :
* la comparaison avant/après se calcule sur un échantillon suffisant ;
* elle est MASQUÉE sous 3 employés comparables ;
* un employé sans note d'un des deux côtés n'est pas comparable (jamais
  comblé par un zéro) ;
* le libellé reste PRUDENT (aucune affirmation causale) ;
* isolation société.

Toutes les dates sont FIXES (aucune lecture d'horloge).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import (
    CampagneEvaluation,
    DossierEmploye,
    EvaluationEmploye,
    ParcoursFormation,
    ProgressionParcours,
)

User = get_user_model()

COMPLETION = date(2026, 6, 15)


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


class CorrelationFormationTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm29-a', 'A')
        self.rh = make_user(self.co, 'nthcm29-rh')
        self.api = auth(self.rh)
        self.parcours = ParcoursFormation.objects.create(
            company=self.co, titre='Pose avancée')
        # DEUX campagnes : `EvaluationEmploye` porte une contrainte unique
        # (campagne, employe) — un même employé ne peut pas avoir deux
        # entretiens dans la MÊME campagne.
        self.campagne_avant = CampagneEvaluation.objects.create(
            company=self.co, intitule='2026 S1', annee=2026)
        self.campagne_apres = CampagneEvaluation.objects.create(
            company=self.co, intitule='2026 S2', annee=2026)

    def _employe(self, matricule):
        return DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom=matricule, prenom='X')

    def _termine(self, employe, completion=COMPLETION):
        progression = ProgressionParcours.objects.create(
            company=self.co, parcours=self.parcours, employe=employe,
            statut=ProgressionParcours.Statut.TERMINE,
            date_completion=completion, pourcentage=100)
        return progression

    def _note(self, employe, jour, valeur, *, apres=False):
        campagne = self.campagne_apres if apres else self.campagne_avant
        return EvaluationEmploye.objects.create(
            company=self.co, campagne=campagne, employe=employe,
            date_entretien=jour, note_globale=Decimal(str(valeur)))

    def _trois_comparables(self):
        for i, (avant, apres) in enumerate([(3, 4), (2, 4), (3, 3)]):
            employe = self._employe(f'C-{i}')
            self._termine(employe)
            self._note(employe, date(2026, 3, 1), avant)
            self._note(employe, date(2026, 9, 1), apres, apres=True)

    def test_comparaison_sur_echantillon_suffisant(self):
        self._trois_comparables()
        resultat = selectors.correlation_formation_performance(
            self.co, self.parcours.id)
        self.assertFalse(resultat['masque'])
        self.assertEqual(resultat['nb_employes_comparables'], 3)
        # Moyennes avant (3, 2, 3) = 2.67 ; après (4, 4, 3) = 3.67.
        self.assertEqual(resultat['moyenne_avant'], 2.67)
        self.assertEqual(resultat['moyenne_apres'], 3.67)
        self.assertEqual(resultat['ecart'], 1.0)

    def test_masque_sous_le_seuil(self):
        employe = self._employe('S-1')
        self._termine(employe)
        self._note(employe, date(2026, 3, 1), 3)
        self._note(employe, date(2026, 9, 1), 5, apres=True)
        resultat = selectors.correlation_formation_performance(
            self.co, self.parcours.id)
        self.assertTrue(resultat['masque'])
        self.assertIsNone(resultat['moyenne_avant'])
        self.assertIsNone(resultat['moyenne_apres'])
        self.assertIsNone(resultat['ecart'])
        self.assertEqual(resultat['nb_employes_comparables'], 1)

    def test_employe_sans_note_dun_cote_nest_pas_comparable(self):
        self._trois_comparables()
        borgne = self._employe('B-1')
        self._termine(borgne)
        self._note(borgne, date(2026, 3, 1), 1)  # aucune note APRÈS
        resultat = selectors.correlation_formation_performance(
            self.co, self.parcours.id)
        self.assertEqual(resultat['nb_employes_termine'], 4)
        self.assertEqual(resultat['nb_employes_comparables'], 3)
        # La note « 1 » du borgne n'a pas tiré la moyenne AVANT vers le bas.
        self.assertEqual(resultat['moyenne_avant'], 2.67)

    def test_notes_hors_fenetre_ignorees(self):
        self._trois_comparables()
        hors = self._employe('H-1')
        self._termine(hors)
        self._note(hors, date(2024, 1, 1), 1)   # > 6 mois avant
        self._note(hors, date(2028, 1, 1), 5, apres=True)  # > 6 mois après
        resultat = selectors.correlation_formation_performance(
            self.co, self.parcours.id)
        self.assertEqual(resultat['nb_employes_comparables'], 3)

    def test_parcours_non_termine_ignore(self):
        employe = self._employe('N-1')
        ProgressionParcours.objects.create(
            company=self.co, parcours=self.parcours, employe=employe,
            statut=ProgressionParcours.Statut.EN_COURS, pourcentage=50)
        resultat = selectors.correlation_formation_performance(
            self.co, self.parcours.id)
        self.assertEqual(resultat['nb_employes_termine'], 0)

    def test_libelle_reste_prudent(self):
        resultat = selectors.correlation_formation_performance(
            self.co, self.parcours.id)
        self.assertEqual(resultat['libelle'], selectors.LIBELLE_NON_CAUSAL)
        self.assertIn('non causale', resultat['libelle'])

    def test_isolation_societe(self):
        self._trois_comparables()
        autre = make_company('nthcm29-b', 'B')
        resultat = selectors.correlation_formation_performance(
            autre, self.parcours.id)
        self.assertEqual(resultat['nb_employes_termine'], 0)

    # ── API ───────────────────────────────────────────────────────────────
    def test_endpoint_correlation(self):
        self._trois_comparables()
        reponse = self.api.get(
            f'/api/django/rh/parcours-formation/{self.parcours.id}'
            '/correlation-performance/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.data['nb_employes_comparables'], 3)
        self.assertIn('non causale', reponse.data['libelle'])

    def test_endpoint_fenetre_invalide_refusee(self):
        reponse = self.api.get(
            f'/api/django/rh/parcours-formation/{self.parcours.id}'
            '/correlation-performance/?fenetre_mois=0')
        self.assertEqual(reponse.status_code, 400, reponse.content)
