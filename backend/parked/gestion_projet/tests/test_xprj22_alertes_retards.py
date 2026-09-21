"""Tests XPRJ22 — alertes automatiques de retard planning.

Couvre : notifications émises pour retards/à-risque, IDEMPOTENCE même jour
(jamais deux alertes pour le même (projet, élément) le même jour), et
projets TERMINÉ/ANNULÉ exclus.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.gestion_projet.models import Projet, Tache
from apps.gestion_projet.services import alertes_retards_projets
from apps.notifications.models import EventType, Notification

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class AlertesRetardsProjetsTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj22', 'S')
        self.responsable = make_user(self.co, 'resp-xprj22')

    def test_notification_emise_pour_tache_en_retard(self):
        projet = Projet.objects.create(
            company=self.co, code='P-X22', nom='Projet X22',
            statut=Projet.Statut.EN_COURS, responsable=self.responsable)
        Tache.objects.create(
            company=self.co, projet=projet, libelle='Tâche en retard',
            date_fin_prevue=date.today() - timedelta(days=3))
        resultat = alertes_retards_projets(self.co)
        self.assertEqual(resultat['nb_alertes_envoyees'], 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.responsable,
                event_type=EventType.PROJET_RETARD).exists())

    def test_idempotence_meme_jour(self):
        projet = Projet.objects.create(
            company=self.co, code='P-X22B', nom='Projet X22B',
            statut=Projet.Statut.EN_COURS, responsable=self.responsable)
        Tache.objects.create(
            company=self.co, projet=projet, libelle='Tâche en retard',
            date_fin_prevue=date.today() - timedelta(days=1))
        alertes_retards_projets(self.co)
        resultat2 = alertes_retards_projets(self.co)
        self.assertEqual(resultat2['nb_alertes_envoyees'], 0)
        self.assertEqual(resultat2['nb_deja_notifiees'], 1)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.responsable,
                event_type=EventType.PROJET_RETARD).count(), 1)

    def test_projet_termine_exclu(self):
        projet = Projet.objects.create(
            company=self.co, code='P-X22C', nom='Projet X22C',
            statut=Projet.Statut.TERMINE, responsable=self.responsable)
        Tache.objects.create(
            company=self.co, projet=projet, libelle='Tâche',
            date_fin_prevue=date.today() - timedelta(days=5))
        resultat = alertes_retards_projets(self.co)
        self.assertEqual(resultat['nb_alertes_envoyees'], 0)

    def test_projet_annule_exclu(self):
        projet = Projet.objects.create(
            company=self.co, code='P-X22D', nom='Projet X22D',
            statut=Projet.Statut.ANNULE, responsable=self.responsable)
        Tache.objects.create(
            company=self.co, projet=projet, libelle='Tâche',
            date_fin_prevue=date.today() - timedelta(days=5))
        resultat = alertes_retards_projets(self.co)
        self.assertEqual(resultat['nb_alertes_envoyees'], 0)

    def test_projet_sans_responsable_ignore(self):
        projet = Projet.objects.create(
            company=self.co, code='P-X22E', nom='Projet X22E',
            statut=Projet.Statut.EN_COURS)
        Tache.objects.create(
            company=self.co, projet=projet, libelle='Tâche',
            date_fin_prevue=date.today() - timedelta(days=5))
        resultat = alertes_retards_projets(self.co)
        self.assertEqual(resultat['nb_alertes_envoyees'], 0)

    def test_aucun_retard_aucune_alerte(self):
        projet = Projet.objects.create(
            company=self.co, code='P-X22F', nom='Projet X22F',
            statut=Projet.Statut.EN_COURS, responsable=self.responsable)
        Tache.objects.create(
            company=self.co, projet=projet, libelle='Tâche future',
            date_fin_prevue=date.today() + timedelta(days=60))
        resultat = alertes_retards_projets(self.co)
        self.assertEqual(resultat['nb_alertes_envoyees'], 0)
