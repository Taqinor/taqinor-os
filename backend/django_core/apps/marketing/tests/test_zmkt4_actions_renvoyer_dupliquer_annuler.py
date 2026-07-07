"""ZMKT4 — Actions Renvoyer les échecs / Dupliquer / Annuler sur une campagne.

Couvre : dupliquer crée un brouillon isolé, annuler stoppe les envois en
attente et bloque le beat, renvoyer-échecs ne cible que les échecs
récupérables et respecte la suppression, tests (annulation à mi-lot, renvoi
filtré, rôles).
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne, EnvoiCampagne


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ActionsRenvoyerDupliquerAnnulerTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt4', 'ZMKT4')

    def test_dupliquer_cree_brouillon_isole(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL,
            objet='Sujet', statut=Campagne.Statut.ENVOYEE)
        clone = services.dupliquer_campagne(camp)
        self.assertEqual(clone.statut, Campagne.Statut.BROUILLON)
        self.assertEqual(clone.objet, 'Sujet')
        self.assertNotEqual(clone.id, camp.id)

    def test_annuler_en_file(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL)
        services.planifier_campagne(
            camp, planifiee_le=timezone.now() + datetime.timedelta(hours=1))
        services.annuler_campagne(camp)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.ANNULEE)

    def test_annuler_bloque_beat(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C3', canal=Campagne.Canal.EMAIL)
        services.planifier_campagne(
            camp, planifiee_le=timezone.now() - datetime.timedelta(minutes=1))
        services.annuler_campagne(camp)
        envoyees = services.envoyer_campagnes_planifiees(self.co)
        self.assertEqual(len(envoyees), 0)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.ANNULEE)

    def test_annuler_deja_envoyee_no_op(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C4', canal=Campagne.Canal.EMAIL,
            statut=Campagne.Statut.ENVOYEE)
        services.annuler_campagne(camp)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.ENVOYEE)

    def test_renvoyer_echecs_cible_seulement_recuperables(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C5', canal=Campagne.Canal.EMAIL,
            statut=Campagne.Statut.ENVOYEE)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='echec@x.ma',
            statut=EnvoiCampagne.Statut.REBOND, raison_smtp='soft_bounce')
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='refuse@x.ma',
            statut=EnvoiCampagne.Statut.REBOND,
            raison_smtp='consentement_refuse_ou_absent')
        nouvelles = services.renvoyer_echecs_campagne(camp)
        self.assertEqual(len(nouvelles), 1)
        self.assertTrue(
            EnvoiCampagne.objects.filter(
                campagne=nouvelles[0], destinataire='echec@x.ma').exists())
        self.assertFalse(
            EnvoiCampagne.objects.filter(
                campagne=nouvelles[0], destinataire='refuse@x.ma').exists())

    def test_renvoyer_echecs_sans_echec_no_op(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C6', canal=Campagne.Canal.EMAIL)
        nouvelles = services.renvoyer_echecs_campagne(camp)
        self.assertEqual(nouvelles, [])

    def test_endpoint_annuler_role_responsable(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        camp = Campagne.objects.create(
            company=self.co, nom='C7', canal=Campagne.Canal.EMAIL)
        services.planifier_campagne(
            camp, planifiee_le=timezone.now() + datetime.timedelta(hours=1))
        user = User.objects.create_user(
            username='zmkt4-user', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.post(f'/api/django/compta/campagnes/{camp.id}/annuler/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['statut'], Campagne.Statut.ANNULEE)
