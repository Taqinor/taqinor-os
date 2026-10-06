"""CIQ513 — « Qui décide : avec un associé / la direction » (et
``conjoint_famille``, ``proprietaire_tiers``) pose ENFIN l'étiquette
« Décision à plusieurs » quand la commerciale le note sur le lead.

Test COMPORTEMENTAL par l'API réelle : PATCH du lead (panneau d'appel →
``crmApi.updateLead`` → ``LeadViewSet.perform_update``). La partition
recalculée contient alors la touche « dimanche famille » si son jour n'est
pas passé — jamais inventée, aucun barreau créé. Le temps est GELÉ.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.services import TAG_DECISION_A_PLUSIEURS, calculer_echeances_cadence
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape
from apps.ventes.models import Devis

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
#: Devis parti la veille : suivi après devis à J+1, dimanche famille à venir.
DEPART = MERCREDI - datetime.timedelta(days=1)
DIMANCHE_FAMILLE = 'dimanche_famille'


class DecideurEtiquetteTests(TestCase):

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CIQ513 Solaire', slug='ciq513')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='ciq513-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Atelier', stage=stages.QUOTE_SENT,
            owner=self.acteur, telephone='+212661000513',
            type_installation='commercial')
        client = Client.objects.create(
            company=self.company, nom='Atelier', email='ciq513@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-CIQ513-0001',
            client=client, lead=self.lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), date_envoi=DEPART)
        self.gabarits = CadenceRelanceEtape.cadence_pour(
            self.company, 'apres_devis')
        self.assertNotIn(DIMANCHE_FAMILLE, self._partition())
        RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=1, due_at=MERCREDI, due_date=MERCREDI.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel de suivi',
            devis=self.devis, cadence_depart=DEPART)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _partition(self):
        self.lead.refresh_from_db()
        return [g.template_cle for g, _e in calculer_echeances_cadence(
            self.lead, 'apres_devis', DEPART, gabarits=self.gabarits)]

    def _patch(self, decideur):
        resp = self.api.patch(f'/api/django/crm/leads/{self.lead.pk}/',
                              {'decideur': decideur}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        return resp

    def _nb_etiquettes(self):
        return [t.strip() for t in (self.lead.tags or '').split(',')
                ].count(TAG_DECISION_A_PLUSIEURS)

    def test_associe_direction_pose_l_etiquette_et_reinjecte_la_touche(self):
        self._patch('associe_direction')
        self.assertEqual(self._nb_etiquettes(), 1)
        self.assertIn(DIMANCHE_FAMILLE, self._partition())

    def test_rejouer_le_meme_patch_une_seule_etiquette(self):
        self._patch('associe_direction')
        self._patch('conjoint_famille')
        self._patch('associe_direction')
        self.assertEqual(self._nb_etiquettes(), 1)

    def test_seul_ne_pose_rien(self):
        self._patch('seul')
        self.assertEqual(self._nb_etiquettes(), 0)
        self.assertNotIn(DIMANCHE_FAMILLE, self._partition())

    def test_repasser_a_seul_ne_retire_rien(self):
        self._patch('proprietaire_tiers')
        self._patch('seul')
        self.assertEqual(self._nb_etiquettes(), 1)

    def test_aucun_barreau_cree(self):
        avant = self.lead.relance_etapes.count()
        self._patch('associe_direction')
        self.assertEqual(self.lead.relance_etapes.count(), avant)
