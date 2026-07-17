"""Tests de l'app éducation (``apps.education``).

Fondations NTEDU1-3 ici (structure année/niveau/classe, famille/élève,
workflow d'inscription) — prérequis direct des tâches NTEDU4-8/12-14 de ce
lot, dont les tests dédiés sont ajoutés section par section au fil des
commits (une classe de tests par tâche, en dessous de ce module).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .models import (
    AnneeScolaire, Classe, Eleve, Famille, Inscription, Niveau)
from .services import affecter_classe

User = get_user_model()


class EducationTestCaseMixin:
    def setUp(self):
        super().setUp()
        self.company, _ = Company.objects.get_or_create(
            slug='ecole-test', defaults={'nom': 'École Test'})
        self.user = User.objects.create_user(
            username='admin@ecole-test.ma', password='x', company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.annee = AnneeScolaire.objects.create(
            company=self.company, libelle='2026-2027',
            date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30))
        self.niveau_cp = Niveau.objects.create(
            company=self.company, nom='CP', cycle=Niveau.Cycle.PRIMAIRE, ordre=1)
        self.niveau_ce1 = Niveau.objects.create(
            company=self.company, nom='CE1', cycle=Niveau.Cycle.PRIMAIRE, ordre=2)
        self.classe = Classe.objects.create(
            company=self.company, annee_scolaire=self.annee,
            niveau=self.niveau_cp, nom='CP A', capacite_max=2)
        self.famille = Famille.objects.create(
            company=self.company, nom='Bennani',
            parent1_nom='Karim Bennani', parent1_whatsapp='+212600000000')


class FoundationTests(EducationTestCaseMixin, TestCase):
    def test_classe_effectif_vs_capacite(self):
        eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine', classe=self.classe)
        self.assertEqual(self.classe.effectif, 1)
        self.assertLess(self.classe.effectif, self.classe.capacite_max)
        self.assertEqual(eleve.statut, Eleve.Statut.PROSPECT)

    def test_eleve_radie_reste_consultable_mais_hors_liste_active(self):
        eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine', statut=Eleve.Statut.RADIE)
        actifs = Eleve.objects.filter(company=self.company).exclude(
            statut__in=[Eleve.Statut.RADIE, Eleve.Statut.DIPLOME])
        self.assertNotIn(eleve, actifs)
        self.assertIn(eleve, Eleve.objects.filter(company=self.company))

    def test_inscription_validee_sur_classe_pleine_va_en_liste_attente(self):
        for i in range(2):
            Eleve.objects.create(
                company=self.company, famille=self.famille, nom='X',
                prenom=f'E{i}', classe=self.classe, statut=Eleve.Statut.INSCRIT)
        self.assertEqual(self.classe.effectif, 2)

        nouvel_eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Y', prenom='Z')
        inscription = Inscription.objects.create(
            company=self.company, eleve=nouvel_eleve,
            annee_scolaire=self.annee, classe_demandee=self.classe)
        affecter_classe(inscription, self.classe)
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, Inscription.Statut.LISTE_ATTENTE)
        self.assertEqual(inscription.position_liste_attente, 1)
