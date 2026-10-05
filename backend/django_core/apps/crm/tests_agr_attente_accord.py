"""AGR520 — la réponse « En attente d'un accord (DPA / banque) ».

Un client qui attend l'approbation préalable de son dossier FDA (Guide FDA
2024 p.22-23 : AVANT la réalisation) ou un accord de crédit n'a dit ni oui ni
non : il ne doit recevoir ni « je classe ? » (J7), ni « dernier message »
(J13), ni la pause (J14). La réponse pose une étiquette, puis applique
EXACTEMENT la veille de « Plus tard » (CAD6/CAD26) : date obligatoire, la
même touche revient à la date convenue ; au-delà d'un mois, la cadence
s'arrête et un réveil (premier geste : un APPEL) est daté du jour choisi. Le
dossier ne change jamais d'étape par cette réponse.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    REPONSES_TOUCHE, TAG_ATTENTE_ACCORD, calculer_echeances_cadence)
from apps.crm.views import _DEFAULT_TAGS
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
J10 = (MERCREDI + datetime.timedelta(days=10)).date()   # samedi 3 octobre
J90 = (MERCREDI + datetime.timedelta(days=90)).date()


class _Base(TestCase):
    slug = 'agr520'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='AGR520 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661000520',
            whatsapp='+212661000520', type_installation='agricole')
        gabarits = CadenceRelanceEtape.cadence_pour(self.company, 'contact')
        echeances = calculer_echeances_cadence(
            self.lead, 'contact', MERCREDI, gabarits=gabarits)
        gabarit, echeance = next(
            (g, e) for g, e in echeances if g.ordre == 4)
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=gabarit.ordre, due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            canal=gabarit.canal, libelle=gabarit.libelle,
            template_cle=gabarit.template_cle or '', cadence_depart=MERCREDI)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _attente(self, **corps):
        corps.setdefault('rappel_heure', '11:00')
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/fait/',
            {'reponse': 'attente_accord', **corps}, format='json')


class SpecTests(TestCase):
    def test_la_reponse_est_connue_du_serveur(self):
        spec = REPONSES_TOUCHE['attente_accord']
        self.assertEqual(spec['libelle'],
                         "En attente d'un accord (DPA / banque)")
        self.assertEqual(spec['outcome'], 'rappel')
        self.assertTrue(spec['date_requise'])
        self.assertIsNone(spec['message'])
        self.assertEqual(spec['cadences'],
                         REPONSES_TOUCHE['plus_tard']['cadences'])

    def test_l_etiquette_est_seedee(self):
        self.assertIn(TAG_ATTENTE_ACCORD, _DEFAULT_TAGS)


class AttenteAccordTests(_Base):
    slug = 'agr520-base'

    def test_a_sans_date_400_nomme_le_champ_date(self):
        resp = self._attente(rappel_le='', rappel_heure='')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('rappel_le', resp.data['erreurs'])
        self.assertIn("En attente d'un accord",
                      resp.data['erreurs']['rappel_le'])
        self.lead.refresh_from_db()
        self.assertNotIn(TAG_ATTENTE_ACCORD, self.lead.tags or '')

    def test_b_date_a_j10_etiquette_et_meme_touche_deplacee(self):
        resp = self._attente(rappel_le=J10.isoformat())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertIn(TAG_ATTENTE_ACCORD, self.lead.tags)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)
        self.assertEqual(self.etape.ordre, 4)
        # La date convenue (recalée au besoin sur un créneau ouvré) : jamais
        # avant la date du client.
        self.assertGreaterEqual(self.etape.due_date, J10)
        # Aucune autre touche avant la date, aucun barreau consommé.
        self.assertFalse(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE,
            due_date__lt=J10).exists())
        self.assertFalse(self.lead.relance_etapes.filter(
            statut__in=(RelanceEtape.Statut.FAIT,
                        RelanceEtape.Statut.SAUTEE)).exists())
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_b_une_ligne_d_historique_typee(self):
        self._attente(rappel_le=J10.isoformat(), note='Dossier FDA déposé')
        ligne = LeadActivity.objects.filter(
            lead=self.lead, outcome='rappel').get()
        self.assertIn("En attente d'un accord (DPA / banque)", ligne.body)
        self.assertIn(TAG_ATTENTE_ACCORD, ligne.body)
        self.assertIn('Dossier FDA déposé', ligne.body)

    def test_c_date_a_j90_cadence_arretee_reveil_appel_date(self):
        resp = self._attente(rappel_le=J90.isoformat())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.ANNULEE)
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='contact', statut=RelanceEtape.Statut.A_FAIRE).exists())
        reveil = (self.lead.relance_etapes
                  .filter(cadence='reveil',
                          statut=RelanceEtape.Statut.A_FAIRE)
                  .order_by('due_at').first())
        self.assertIsNotNone(reveil)
        self.assertEqual(reveil.canal, RelanceEtape.Canal.APPEL)
        self.assertGreaterEqual(reveil.due_date, J90)
        self.assertLess((reveil.due_date - J90).days, 7)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)
        self.assertIn(TAG_ATTENTE_ACCORD, self.lead.tags)
