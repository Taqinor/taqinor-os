"""XMKT7 — Planification, throttling et fenêtres de silence d'envoi.

Couvre : une campagne planifiée part à l'heure dite par lots throttlés, un
contact au plafond est sauté (journalisé dans XMKT2), aucun SMS hors
fenêtre, défauts = comportement actuel (aucune limite si non configuré).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    AbonnementListe, Campagne, EnvoiCampagne, ListeDiffusion,
)
from apps.notifications import selectors as notifications_selectors
from apps.parametres.models_company import CompanyProfile

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PlanificationThrottlingTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt7', 'XMKT7')

    def test_campagne_planifiee_part_a_echeance(self):
        liste = ListeDiffusion.objects.create(company=self.co, nom='L1')
        AbonnementListe.objects.create(
            company=self.co, liste=liste, destinataire='a@x.ma',
            statut=AbonnementListe.Statut.INSCRIT)
        camp = Campagne.objects.create(
            company=self.co, nom='Planifiée', canal=Campagne.Canal.EMAIL,
            planifiee_le=timezone.now() - datetime.timedelta(minutes=1))
        camp.listes.add(liste)
        services.envoyer_campagnes_planifiees(self.co)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.ENVOYEE)

    def test_campagne_planifiee_future_ne_part_pas(self):
        liste = ListeDiffusion.objects.create(company=self.co, nom='L2')
        camp = Campagne.objects.create(
            company=self.co, nom='Future', canal=Campagne.Canal.EMAIL,
            planifiee_le=timezone.now() + datetime.timedelta(hours=1))
        camp.listes.add(liste)
        services.envoyer_campagnes_planifiees(self.co)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.BROUILLON)

    def test_debit_max_par_heure_tronque_le_lot(self):
        liste = ListeDiffusion.objects.create(company=self.co, nom='L3')
        for i in range(5):
            AbonnementListe.objects.create(
                company=self.co, liste=liste, destinataire=f'u{i}@x.ma',
                statut=AbonnementListe.Statut.INSCRIT)
        camp = Campagne.objects.create(
            company=self.co, nom='Throttled', canal=Campagne.Canal.EMAIL,
            planifiee_le=timezone.now() - datetime.timedelta(minutes=1),
            debit_max_par_heure=2)
        camp.listes.add(liste)
        services.envoyer_campagnes_planifiees(self.co)
        camp.refresh_from_db()
        self.assertEqual(camp.nb_destinataires, 2)

    def test_sans_reglage_aucune_limite_de_pression(self):
        self.assertFalse(
            services._plafond_pression_atteint(self.co, 'a@x.ma'))

    def test_plafond_pression_sauté_et_journalisé(self):
        CompanyProfile.objects.create(
            company=self.co, pression_marketing_max_par_contact=1,
            pression_marketing_periode_jours=7)
        camp1 = Campagne.objects.create(
            company=self.co, nom='C1', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp1, destinataires=['plafonne@x.ma'])
        camp2 = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp2, destinataires=['plafonne@x.ma'])
        camp2.refresh_from_db()
        self.assertEqual(camp2.nb_destinataires, 0)
        envoi = EnvoiCampagne.objects.get(
            campagne=camp2, destinataire='plafonne@x.ma')
        self.assertEqual(envoi.raison_smtp, 'plafond_pression_marketing')

    def test_silence_window_selector_nuit(self):
        moment_nuit = timezone.make_aware(
            datetime.datetime(2026, 7, 6, 2, 0))  # lundi 02h00
        self.assertTrue(
            notifications_selectors.est_hors_fenetre_silence(
                moment_nuit, self.co))

    def test_silence_window_selector_jour(self):
        moment_jour = timezone.make_aware(
            datetime.datetime(2026, 7, 6, 10, 0))  # lundi 10h00
        self.assertFalse(
            notifications_selectors.est_hors_fenetre_silence(
                moment_jour, self.co))

    def test_sms_hors_fenetre_ne_part_pas(self):
        from apps.notifications.models import Holiday
        # Bloque le jour du test comme férié (toujours hors fenêtre, peu
        # importe l'heure d'exécution du test).
        aujourdhui = timezone.now().date()
        Holiday.objects.create(
            company=self.co, date=aujourdhui, nom='Test férié',
            recurrent_annuel=False)
        camp = Campagne.objects.create(
            company=self.co, nom='SMS', canal=Campagne.Canal.SMS)
        services.envoyer_campagne(camp, destinataires=['0612345678'])
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.BROUILLON)
        self.assertEqual(EnvoiCampagne.objects.filter(campagne=camp).count(), 0)
