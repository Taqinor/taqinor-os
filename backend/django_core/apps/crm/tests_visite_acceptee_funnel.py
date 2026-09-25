"""« Visite acceptée » est une réponse du client : le funnel avance.

Relevé du vérificateur (25/09/2026) sur la décision fondateur du 24/09/2026 :
l'issue « Visite acceptée » arrêtait bien la prise de contact et posait
« Planifier la visite technique convenue », mais la règle QJ7 (Nouveau →
Contacté sur une réponse confirmée) ne la lisait pas — un lead Nouveau qui
acceptait la visite dès le premier appel restait Nouveau. Même règle, même
table (``services.ISSUES_CLIENT_JOINT``) pour le cran QJ-FUNNEL (Devis envoyé
→ Relance) et pour la confirmation d'une réponse à l'annulation (RLC1).

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm.models import Client, Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
VISITE = services.OUTCOME_VISITE_ACCEPTEE


class _Base(TestCase):
    slug = 'vaf'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom=f'{self.slug} Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _lead(self, stage):
        return Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Fatima', stage=stage,
            owner=self.acteur, telephone='+212661000321')

    def _touche(self, lead, *, cadence, ordre, libelle, devis=None):
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence=cadence, ordre=ordre,
            canal=RelanceEtape.Canal.APPEL, libelle=libelle, devis=devis,
            due_at=GEL, due_date=GEL.date(), cadence_depart=GEL)


class NouveauVersContacteTests(_Base):
    slug = 'vaf-new'

    def test_visite_acceptee_au_premier_appel_passe_le_lead_a_contacte(self):
        lead = self._lead(stages.NEW)
        appel = self._touche(lead, cadence='contact', ordre=2,
                             libelle="Appel d'ouverture")

        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{appel.pk}/fait/',
            {'outcome': VISITE}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)
        self.assertIsNotNone(lead.first_contacted_at)
        self.assertTrue(lead.activites.filter(
            field='stage', body='auto — premier contact').exists())

    def test_depuis_le_journal_d_appel_aussi(self):
        lead = self._lead(stages.NEW)

        resp = self.api.post(
            f'/api/django/crm/leads/{lead.pk}/log-interaction/',
            {'kind': 'appel', 'outcome': VISITE}, format='json')

        self.assertEqual(resp.status_code, 201, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)

    def test_pas_de_reponse_ne_fait_toujours_pas_avancer(self):
        """Garde : seules les réponses CONFIRMÉES bougent le funnel."""
        lead = self._lead(stages.NEW)
        appel = self._touche(lead, cadence='contact', ordre=2,
                             libelle="Appel d'ouverture")

        self.api.post(f'/api/django/crm/relance-etapes/{appel.pk}/fait/',
                      {'outcome': 'non_joint'}, format='json')

        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.NEW)


class DevisEnvoyeVersRelanceTests(_Base):
    slug = 'vaf-quote'

    def test_visite_acceptee_apres_le_devis_passe_le_lead_en_relance(self):
        from apps.ventes.models import Devis

        lead = self._lead(stages.QUOTE_SENT)
        client = Client.objects.create(company=self.company, nom='Alaoui',
                                       email='vaf-quote@example.com')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-VAF-00001', client=client,
            lead=lead, statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20.00'),
            date_envoi=GEL - datetime.timedelta(days=3))
        appel = self._touche(lead, cadence='apres_devis', ordre=2,
                             libelle='Appel de suivi', devis=devis)

        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{appel.pk}/fait/',
            {'outcome': VISITE}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)


class TableUniqueTests(SimpleTestCase):
    def test_la_confirmation_rlc1_lit_la_meme_table(self):
        self.assertIn(VISITE, services.ISSUES_CLIENT_JOINT)
        self.assertEqual(services._OUTCOMES_REPONSE_CONFIRMEE,
                         services.ISSUES_CLIENT_JOINT)
