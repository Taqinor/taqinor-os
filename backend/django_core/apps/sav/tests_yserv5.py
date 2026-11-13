"""YSERV5 — Génération automatique planifiée des visites préventives dues.

Couvre :
  * OFF (défaut) = rien, la tâche n'agit pas sur une société non opt-in ;
  * ON → les visites dues sous N jours sont créées, notification émise ;
  * idempotence préservée (un second run le même jour ne double pas) ;
  * `generer_visites_dues(avance_jours=...)` matérialise en avance une visite
    dont l'échéance n'est pas encore atteinte aujourd'hui.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_yserv5 -v 2
"""
import threading
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.maintenance import generer_visites_dues
from apps.sav.models import ContratMaintenance, SavSlaSettings, Ticket
from apps.sav.tasks import generer_visites_dues_quotidien
from apps.notifications.models import Notification
from core.test_utils import WideTeardownTimeoutMixin

User = get_user_model()


def make_company(slug='sav-yserv5', nom='Sav Co YSERV5'):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom, 'actif': True})
    return company


class YSERV5GenerationAutoTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='yserv5_admin', password='x', role_legacy='admin',
            company=self.company, is_active=True)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YSERV5',
            email='yserv5-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-YSERV5', client=self.client_obj)
        # Contrat dont la visite tombe dans 5 jours.
        self.contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst,
            date_debut=date.today() - timedelta(days=360), actif=True)

    def test_off_par_defaut_aucun_effet(self):
        # generation_auto_visites reste False par défaut.
        result = generer_visites_dues_quotidien()
        self.assertEqual(result['societes'], 0)
        self.assertFalse(
            Ticket.objects.filter(company=self.company).exists())

    def test_on_genere_visites_avance_et_notifie(self):
        reglage = SavSlaSettings.get(self.company)
        reglage.generation_auto_visites = True
        reglage.visites_avance_jours = 10
        reglage.save(update_fields=[
            'generation_auto_visites', 'visites_avance_jours'])

        result = generer_visites_dues_quotidien()
        self.assertEqual(result['societes'], 1)
        self.assertGreaterEqual(result['visites_generees'], 1)
        self.assertTrue(
            Ticket.objects.filter(
                company=self.company, type=Ticket.Type.PREVENTIF).exists())
        notif = Notification.objects.filter(
            recipient=self.admin, event_type='sav_visites_auto_generees',
        ).first()
        self.assertIsNotNone(notif)
        # SAV-LIEN-MORT — la route frontend réelle est `/sav/contrats`
        # (`frontend/src/features/sav/module.config.jsx`), jamais
        # `/sav/contrats-maintenance` (lien mort avant ce correctif).
        self.assertEqual(notif.link, '/sav/contrats')

    def test_idempotent_pas_de_doublon_meme_jour(self):
        reglage = SavSlaSettings.get(self.company)
        reglage.generation_auto_visites = True
        reglage.visites_avance_jours = 10
        reglage.save(update_fields=[
            'generation_auto_visites', 'visites_avance_jours'])

        generer_visites_dues_quotidien()
        n1 = Ticket.objects.filter(company=self.company).count()
        generer_visites_dues_quotidien()
        n2 = Ticket.objects.filter(company=self.company).count()
        self.assertEqual(n1, n2)

    def test_avance_jours_materialise_avant_echeance(self):
        # self.contrat (setUp) a sa prochaine visite dans 5 jours (date_debut
        # = J-360, périodicité annuelle par défaut => J-360+12mois = J+5).
        # Un second contrat, dont la prochaine visite (date_debut + 12 mois)
        # tombe loin dans le futur, sert de témoin « jamais dû ».
        contrat_lointain = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst,
            date_debut=date.today() + timedelta(days=5), actif=True)
        n0 = generer_visites_dues(self.company, self.admin, avance_jours=0)
        self.assertEqual(n0, 0)
        # Avec 10 jours d'avance : la visite de self.contrat (dans 5 jours) est due.
        n1 = generer_visites_dues(self.company, self.admin, avance_jours=10)
        self.assertGreaterEqual(n1, 1)
        self.contrat.refresh_from_db()
        self.assertIsNotNone(self.contrat.derniere_visite)
        contrat_lointain.refresh_from_db()
        self.assertIsNone(contrat_lointain.derniere_visite)

    def test_erreur_apres_creation_ne_laisse_pas_de_ticket_double(self):
        # ACEL47 — ticket + avance du contrat dans UNE transaction : une erreur
        # après la création du ticket ne laisse aucun ticket orphelin.
        from unittest import mock

        from apps.sav import services as sav_services

        vrai = sav_services.poser_sla_due_at
        appels = {'n': 0}

        def poser_puis_lever(ticket):
            appels['n'] += 1
            if appels['n'] == 1:
                raise RuntimeError('panne simulée')
            return vrai(ticket)

        preventifs = Ticket.objects.filter(
            company=self.company, type=Ticket.Type.PREVENTIF)
        with mock.patch.object(
                sav_services, 'poser_sla_due_at', side_effect=poser_puis_lever):
            with self.assertRaises(RuntimeError):
                generer_visites_dues(self.company, self.admin, avance_jours=10)
            self.assertEqual(preventifs.count(), 0)
            self.contrat.refresh_from_db()
            self.assertIsNone(self.contrat.derniere_visite)
            echeance = self.contrat.prochaine_visite()

            generer_visites_dues(self.company, self.admin, avance_jours=10)
            self.assertEqual(preventifs.count(), 1)
            ticket = preventifs.get()
            self.assertEqual(ticket.statut, Ticket.Statut.NOUVEAU)
            self.assertEqual(ticket.date_ouverture, echeance)
            self.contrat.refresh_from_db()
            self.assertEqual(self.contrat.derniere_visite, echeance)

            generer_visites_dues(self.company, self.admin, avance_jours=10)
            self.assertEqual(preventifs.count(), 1)


class YSERV5GenerationCroiseeTest(WideTeardownTimeoutMixin, TransactionTestCase):
    """ACNC35 — deux « Générer les visites dues » croisés sur DEUX vraies
    connexions (patron `TestSavPiecesConcurrence._course` de `tests_pieces.py`) :
    A génère dans sa transaction et tient le contrat ; B arrive avant le commit."""

    def setUp(self):
        self.company = make_company(slug='sav-acnc35', nom='Sav Co ACNC35')
        self.admin = User.objects.create_user(
            username='acnc35_admin', password='x', role_legacy='admin',
            company=self.company, is_active=True)
        client = Client.objects.create(company=self.company, nom='Client', prenom='ACNC35')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-ACNC35', client=client)
        # Échéance annuelle passée de 35 jours : due aujourd'hui sans avance.
        self.contrat = ContratMaintenance.objects.create(
            company=self.company, client=client, installation=inst,
            date_debut=date.today() - timedelta(days=400), actif=True)
        self.echeance = self.contrat.prochaine_visite()

    def test_deux_generations_croisees_un_ticket_par_contrat(self):
        a_tient, res = threading.Event(), {}

        def fil_a():
            with transaction.atomic():
                res['a'] = generer_visites_dues(self.company, self.admin)
                a_tient.set()
                threading.Event().wait(1.5)  # B arrive avant le commit de A
            connection.close()

        def fil_b():
            a_tient.wait(5)
            api = APIClient()
            api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
            r = api.post('/api/django/sav/contrats-maintenance/generer-dus/')
            res['b'] = (r.status_code, r.data.get('tickets_generes'))
            connection.close()
        fils = [threading.Thread(target=fil_a), threading.Thread(target=fil_b)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(20)
        self.assertEqual(res, {'a': 1, 'b': (200, 0)})
        self.assertEqual(Ticket.objects.filter(
            company=self.company, type=Ticket.Type.PREVENTIF).count(), 1)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.derniere_visite, self.echeance)
