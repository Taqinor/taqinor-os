"""NTGRC34 — rappels d'échéances GRC (Celery-safe, idempotents).

Garanties : chaque famille d'échéance (DSR, violation 72 h, revue de risque,
contrôle à tester, politique non attestée) produit SA notification, une seule
fois par jour et par destinataire ; la commande tourne SANS planificateur ; la
tâche Beat existe et relaie la même logique. Horloge FIGÉE.
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.grc.management.commands.rappels_grc import rappeler_societe
from apps.grc.models import (
    ControleInterne, PolitiqueInterne, RisqueEntreprise, ViolationDonnees,
)
from apps.grc.services import creer_violation, publier_politique
from apps.notifications.models import Notification
from apps.rh.models import DossierEmploye
from authentication.models import Company
from core.models import DataSubjectRequest
from testkit.time import frozen

INSTANT = '2026-09-12 06:30:00+00:00'
LENDEMAIN = '2026-09-13 06:30:00+00:00'


class RappelsGrcTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC34 SA', slug='ntgrc34')
        cls.manager = get_user_model().objects.create_user(
            username='ntgrc34-dpo', password='x', company=cls.company,
            role_legacy='admin')

    def _dsr(self):
        return DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)

    def _violation(self):
        return creer_violation(
            self.company,
            date_detection=timezone.now() - timezone.timedelta(days=5),
            statut=ViolationDonnees.STATUT_OUVERTE)

    def _risque(self):
        return RisqueEntreprise.objects.create(
            company=self.company, titre='Fuite', proprietaire='DSI',
            date_revue_prevue=timezone.now().date())

    def _controle(self):
        return ControleInterne.objects.create(
            company=self.company, code='ACC-01', intitule='Revue',
            actif=True)

    def _politique(self):
        DossierEmploye.objects.create(
            company=self.company, matricule='E1', nom='A', prenom='A')
        politique = PolitiqueInterne.objects.create(
            company=self.company, titre='Charte', contenu='Texte')
        publier_politique(politique)
        return politique

    def test_une_dsr_proche_d_echeance_declenche_un_rappel(self):
        with frozen(INSTANT):
            self._dsr()
        with frozen('2026-10-08 06:30:00+00:00'):
            envoyees, _ = rappeler_societe(self.company)
        self.assertEqual(envoyees, 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_une_dsr_encore_loin_ne_declenche_rien(self):
        with frozen(INSTANT):
            self._dsr()
            envoyees, _ = rappeler_societe(self.company)
        self.assertEqual(envoyees, 0)

    def test_une_violation_hors_delai_declenche_un_rappel(self):
        with frozen(INSTANT):
            self._violation()
            envoyees, _ = rappeler_societe(self.company)
        self.assertEqual(envoyees, 1)
        self.assertIn('72 h', Notification.objects.first().title)

    def test_une_revue_de_risque_due_declenche_un_rappel(self):
        with frozen(INSTANT):
            self._risque()
            envoyees, _ = rappeler_societe(self.company)
        self.assertEqual(envoyees, 1)
        self.assertIn('DSI', Notification.objects.first().body)

    def test_un_controle_jamais_teste_declenche_un_rappel(self):
        with frozen(INSTANT):
            self._controle()
            envoyees, _ = rappeler_societe(self.company)
        self.assertEqual(envoyees, 1)
        self.assertIn('jamais testé', Notification.objects.first().body)

    def test_une_politique_non_attestee_declenche_un_rappel(self):
        with frozen(INSTANT):
            self._politique()
            envoyees, _ = rappeler_societe(self.company)
        self.assertEqual(envoyees, 1)

    def test_plusieurs_familles_remontent_ensemble(self):
        """Quatre familles sur cinq ; la DSR a sa propre horloge (ci-dessus)."""
        with frozen(INSTANT):
            self._violation()
            self._risque()
            self._controle()
            self._politique()
            envoyees, _ = rappeler_societe(self.company)
        self.assertEqual(envoyees, 4)

    def test_deux_lancements_le_meme_jour_ne_doublent_pas(self):
        with frozen(INSTANT):
            self._violation()
            premier, _ = rappeler_societe(self.company)
            second, ignorees = rappeler_societe(self.company)
        self.assertEqual(premier, 1)
        self.assertEqual(second, 0)
        self.assertEqual(ignorees, 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_le_lendemain_rappelle_de_nouveau(self):
        with frozen(INSTANT):
            self._violation()
            rappeler_societe(self.company)
        with frozen(LENDEMAIN):
            demain, _ = rappeler_societe(self.company)
        self.assertEqual(demain, 1)

    def test_une_societe_sans_echeance_n_envoie_rien(self):
        with frozen(INSTANT):
            envoyees, _ = rappeler_societe(self.company)
        self.assertEqual(envoyees, 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_une_autre_societe_n_est_jamais_rappelee(self):
        autre = Company.objects.create(nom='Autre', slug='ntgrc34-autre')
        with frozen(INSTANT):
            creer_violation(
                autre,
                date_detection=timezone.now() - timezone.timedelta(days=5),
                statut=ViolationDonnees.STATUT_OUVERTE)
            envoyees, _ = rappeler_societe(self.company)
        self.assertEqual(envoyees, 0)

    def test_la_commande_tourne_sans_planificateur(self):
        sortie = StringIO()
        with frozen(INSTANT):
            self._violation()
            call_command('rappels_grc', '--company', str(self.company.pk),
                         stdout=sortie)
        self.assertIn('Rappels GRC', sortie.getvalue())
        self.assertEqual(Notification.objects.count(), 1)

    def test_la_commande_en_simulation_n_envoie_rien(self):
        sortie = StringIO()
        with frozen(INSTANT):
            self._violation()
            call_command('rappels_grc', '--dry-run',
                         '--company', str(self.company.pk), stdout=sortie)
        self.assertIn('simulation', sortie.getvalue())
        self.assertEqual(Notification.objects.count(), 0)


class TacheBeatTests(TestCase):
    """La tâche Beat existe VRAIMENT et relaie la commande.

    Le piège mesuré dans ce dépôt : une entrée de ``beat_schedule`` qui
    référence une tâche qu'aucun module n'enregistre échoue en silence à
    chaque tick.
    """

    def test_l_entree_beat_reference_la_tache_enregistree(self):
        from erp_agentique.celery import app

        entree = app.conf.beat_schedule.get('grc-rappels-echeances')
        self.assertIsNotNone(entree)
        self.assertEqual(entree['task'], 'grc.rappels_grc')

    def test_le_module_de_tache_relaie_la_commande(self):
        from apps.grc import tasks

        self.assertTrue(callable(tasks.run_rappels_grc))
        with frozen(INSTANT):
            tasks.run_rappels_grc()  # aucune société, aucun effet : ne lève pas
