"""ZMKT1 — Statuts de pipeline mailing (Brouillon / En file / Envoi /
Envoyée) + vue Kanban.

Couvre : une campagne planifiée passe en_file puis envoi_en_cours puis
envoyee, le endpoint kanban renvoie les campagnes groupées par statut
scoping société, migration additive (choices), tests transitions +
multi-tenant.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import AbonnementListe, Campagne, ListeDiffusion


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PipelineKanbanTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt1', 'ZMKT1')

    def test_planifier_passe_en_file(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.planifier_campagne(
            camp, planifiee_le=timezone.now() + datetime.timedelta(hours=1))
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.EN_FILE)

    def test_pipeline_complet_en_file_vers_envoyee(self):
        liste = ListeDiffusion.objects.create(company=self.co, nom='L')
        AbonnementListe.objects.create(
            company=self.co, liste=liste, destinataire='a@x.ma',
            statut=AbonnementListe.Statut.INSCRIT)
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL)
        camp.listes.add(liste)
        services.planifier_campagne(
            camp, planifiee_le=timezone.now() - datetime.timedelta(minutes=1))
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.EN_FILE)
        services.envoyer_campagnes_planifiees(self.co)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.ENVOYEE)

    def test_envoi_direct_brouillon_toujours_supporte(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C3', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['a@x.ma'])
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.ENVOYEE)

    def test_kanban_groupe_par_statut(self):
        Campagne.objects.create(
            company=self.co, nom='Brouillon1', canal=Campagne.Canal.EMAIL)
        camp2 = Campagne.objects.create(
            company=self.co, nom='EnFile1', canal=Campagne.Canal.EMAIL)
        services.planifier_campagne(
            camp2, planifiee_le=timezone.now() + datetime.timedelta(hours=1))
        kanban = services.campagnes_par_statut(self.co)
        self.assertEqual(len(kanban[Campagne.Statut.BROUILLON]), 1)
        self.assertEqual(len(kanban[Campagne.Statut.EN_FILE]), 1)

    def test_kanban_taux_ouverture_calcule(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C4', canal=Campagne.Canal.EMAIL,
            nb_envois=10, nb_ouvertures=5, statut=Campagne.Statut.ENVOYEE)
        kanban = services.campagnes_par_statut(self.co)
        entry = next(
            c for c in kanban[Campagne.Statut.ENVOYEE] if c['id'] == camp.id)
        self.assertEqual(entry['taux_ouverture_pct'], 50.0)

    def test_isolation_multi_tenant_kanban(self):
        other = make_company('zmkt1-b', 'ZMKT1-B')
        Campagne.objects.create(
            company=self.co, nom='Mine', canal=Campagne.Canal.EMAIL)
        kanban_other = services.campagnes_par_statut(other)
        self.assertEqual(len(kanban_other[Campagne.Statut.BROUILLON]), 0)

    def test_silence_window_repasse_en_file_jamais_coincee(self):
        from apps.notifications.models import Holiday
        aujourdhui = timezone.now().date()
        Holiday.objects.create(
            company=self.co, date=aujourdhui, nom='Test férié',
            recurrent_annuel=False)
        camp = Campagne.objects.create(
            company=self.co, nom='SMS', canal=Campagne.Canal.SMS)
        services.planifier_campagne(
            camp, planifiee_le=timezone.now() - datetime.timedelta(minutes=1))
        services.envoyer_campagnes_planifiees(self.co)
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.EN_FILE)
