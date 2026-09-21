"""NTEDU40 — rappels de relance réinscription (tâche planifiée, admin only,
jamais les familles)."""
from datetime import date, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from .models import (
    AnneeScolaire, Classe, Eleve, Famille, Inscription, Niveau,
    ParametresEducation,
)
from .services import eleves_sans_reinscription, relancer_reinscriptions_dues


class NTEDU40RelanceReinscriptionTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ecole-relance-test', defaults={'nom': 'École Relance Test'})
        self.annee_courante = AnneeScolaire.objects.create(
            company=self.company, libelle='2026-2027',
            date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30),
            statut=AnneeScolaire.Statut.ACTIVE)
        self.annee_suivante = AnneeScolaire.objects.create(
            company=self.company, libelle='2027-2028',
            date_debut=date(2027, 9, 1), date_fin=date(2028, 6, 30),
            statut=AnneeScolaire.Statut.ARCHIVEE)
        self.niveau = Niveau.objects.create(
            company=self.company, nom='CP', cycle=Niveau.Cycle.PRIMAIRE, ordre=1)
        self.classe = Classe.objects.create(
            company=self.company, annee_scolaire=self.annee_courante,
            niveau=self.niveau, nom='CP A', capacite_max=30)
        self.famille = Famille.objects.create(company=self.company, nom='Bennani')

        self.eleve_sans_reinscription = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine', classe=self.classe, statut=Eleve.Statut.INSCRIT)
        self.eleve_deja_reinscrit = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Karim', classe=self.classe, statut=Eleve.Statut.INSCRIT)
        Inscription.objects.create(
            company=self.company, eleve=self.eleve_deja_reinscrit,
            annee_scolaire=self.annee_suivante,
            statut=Inscription.Statut.VALIDEE)
        self.eleve_radie = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Nadia', statut=Eleve.Statut.RADIE)
        self.eleve_diplome = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Sara', statut=Eleve.Statut.DIPLOME)

    def test_exclut_deja_reinscrits_et_radies_diplomes(self):
        eleves = list(eleves_sans_reinscription(self.company))
        self.assertEqual(eleves, [self.eleve_sans_reinscription])
        self.assertNotIn(self.eleve_deja_reinscrit, eleves)
        self.assertNotIn(self.eleve_radie, eleves)
        self.assertNotIn(self.eleve_diplome, eleves)

    def test_sans_annee_suivante_renvoie_vide(self):
        self.annee_suivante.delete()
        eleves = list(eleves_sans_reinscription(self.company))
        self.assertEqual(eleves, [])

    def test_relance_no_op_avant_date_limite(self):
        params = ParametresEducation.get(self.company)
        params.date_limite_reinscription = (
            timezone.now().date() + timedelta(days=30))
        params.save(update_fields=['date_limite_reinscription'])

        with mock.patch(
                'apps.notifications.services.notify') as mocked_notify:
            resultat = relancer_reinscriptions_dues(self.company)

        self.assertEqual(resultat, 0)
        mocked_notify.assert_not_called()

    def test_relance_no_op_sans_date_limite_configuree(self):
        resultat = relancer_reinscriptions_dues(self.company)
        self.assertEqual(resultat, 0)

    def test_relance_notifie_administration_apres_date_limite(self):
        admin = self._creer_admin()
        params = ParametresEducation.get(self.company)
        params.date_limite_reinscription = (
            timezone.now().date() - timedelta(days=1))
        params.save(update_fields=['date_limite_reinscription'])

        with mock.patch(
                'apps.notifications.services.notify') as mocked_notify:
            resultat = relancer_reinscriptions_dues(self.company)

        self.assertEqual(resultat, 1)
        mocked_notify.assert_called_once()
        args, kwargs = mocked_notify.call_args
        self.assertEqual(args[0], admin)
        from apps.notifications.models import EventType
        self.assertEqual(args[1], EventType.EDUCATION_REINSCRIPTION_RELANCE)

    def _creer_admin(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # ``is_admin_role`` (authentication.models.CustomUser) est une
        # PROPRIÉTÉ dérivée de ``is_superuser``/``role``/``role_legacy`` —
        # ``is_superuser=True`` la rend vraie de façon déterministe, sans
        # dépendre du modèle ``roles.Role`` (hors périmètre de ce test).
        return User.objects.create_user(
            username='admin@ecole-relance-test.ma', password='x',
            company=self.company, is_superuser=True)
