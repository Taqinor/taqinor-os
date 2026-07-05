"""XMKT23 — Approbation avant envoi de masse + journal d'audit.

Couvre : une campagne au-dessus du seuil reste bloquée en attente
d'approbation, l'approbation déclenche l'envoi, le journal liste envoyeur/
approbateur/volume, seuil configurable.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import ApprobationEnvoiCampagne, Campagne
from apps.parametres.models_company import CompanyProfile

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class ApprobationEnvoiMasseTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt23', 'XMKT23')

    def test_sous_seuil_envoie_directement(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        _c, approbation = services.demander_ou_envoyer_campagne(
            camp, destinataires=['a@x.ma', 'b@x.ma'])
        self.assertIsNone(approbation)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.ENVOYEE)

    def test_au_dessus_du_seuil_reste_bloquee(self):
        CompanyProfile.objects.create(
            company=self.co, seuil_approbation_envoi_masse=5)
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL)
        destinataires = [f'u{i}@x.ma' for i in range(10)]
        _c, approbation = services.demander_ou_envoyer_campagne(
            camp, destinataires=destinataires)
        self.assertIsNotNone(approbation)
        self.assertEqual(
            approbation.statut, ApprobationEnvoiCampagne.Statut.EN_ATTENTE)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.BROUILLON)

    def test_approbation_declenche_envoi(self):
        CompanyProfile.objects.create(
            company=self.co, seuil_approbation_envoi_masse=5)
        camp = Campagne.objects.create(
            company=self.co, nom='C3', canal=Campagne.Canal.EMAIL)
        destinataires = [f'u{i}@x.ma' for i in range(10)]
        _c, approbation = services.demander_ou_envoyer_campagne(
            camp, destinataires=destinataires)
        user = make_user(self.co, 'xmkt23-approbateur')
        services.approuver_envoi_campagne(approbation, user=user)
        camp.refresh_from_db()
        approbation.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.ENVOYEE)
        self.assertEqual(
            approbation.statut, ApprobationEnvoiCampagne.Statut.APPROUVE)

    def test_rejet_ne_declenche_pas_envoi(self):
        CompanyProfile.objects.create(
            company=self.co, seuil_approbation_envoi_masse=5)
        camp = Campagne.objects.create(
            company=self.co, nom='C4', canal=Campagne.Canal.EMAIL)
        destinataires = [f'u{i}@x.ma' for i in range(10)]
        _c, approbation = services.demander_ou_envoyer_campagne(
            camp, destinataires=destinataires)
        services.rejeter_envoi_campagne(approbation, motif='pas prêt')
        camp.refresh_from_db()
        approbation.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.BROUILLON)
        self.assertEqual(
            approbation.statut, ApprobationEnvoiCampagne.Statut.REJETE)
        self.assertEqual(approbation.motif_rejet, 'pas prêt')

    def test_journal_audit_liste_envoyeur_approbateur_volume(self):
        CompanyProfile.objects.create(
            company=self.co, seuil_approbation_envoi_masse=5)
        camp = Campagne.objects.create(
            company=self.co, nom='C5', canal=Campagne.Canal.EMAIL)
        destinataires = [f'u{i}@x.ma' for i in range(10)]
        demandeur = make_user(self.co, 'xmkt23-demandeur')
        _c, approbation = services.demander_ou_envoyer_campagne(
            camp, destinataires=destinataires, user=demandeur)
        approbateur = make_user(self.co, 'xmkt23-approbateur2')
        services.approuver_envoi_campagne(approbation, user=approbateur)
        journal = services.journal_audit_envois(self.co)
        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0]['nb_destinataires'], 10)
        self.assertEqual(journal[0]['demande_par'], 'xmkt23-demandeur')
        self.assertEqual(journal[0]['decide_par'], 'xmkt23-approbateur2')

    def test_seuil_par_defaut_100(self):
        self.assertEqual(services.seuil_approbation_envoi_masse(self.co), 100)

    def test_deja_decide_reste_inchange(self):
        CompanyProfile.objects.create(
            company=self.co, seuil_approbation_envoi_masse=5)
        camp = Campagne.objects.create(
            company=self.co, nom='C6', canal=Campagne.Canal.EMAIL)
        destinataires = [f'u{i}@x.ma' for i in range(10)]
        _c, approbation = services.demander_ou_envoyer_campagne(
            camp, destinataires=destinataires)
        services.approuver_envoi_campagne(approbation)
        avant = approbation.date_decision
        services.rejeter_envoi_campagne(approbation, motif='trop tard')
        approbation.refresh_from_db()
        self.assertEqual(
            approbation.statut, ApprobationEnvoiCampagne.Statut.APPROUVE)
        self.assertEqual(approbation.date_decision, avant)
