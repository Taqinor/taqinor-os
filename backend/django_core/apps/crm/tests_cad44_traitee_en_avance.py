"""CAD44 — agir en avance (TRANCHÉ 21/09/2026, MRY32 rouverte).

Décision fondateur : sur une touche À VENIR, Appeler, WhatsApp et Reporter
sont actionnables ; « Fait » reste verrouillé À L'ÉCRAN (on ne coche pas un
geste qui n'a pas eu lieu). Le garde-fou serveur, pour toute touche qui serait
malgré tout close avant son jour :

  * le serveur la marque à sa date RÉELLE (``traite_le`` = l'instant du geste) ;
  * le journal dit « traitée en avance » (avec l'échéance d'origine) ;
  * le reste du plan ne bouge pas — la touche suivante reste datée depuis
    l'ancre ``cadence_depart``, qui n'est pas déplacée ;
  * CKP3 ne compte AUCUNE faute pour elle (``selectors._a_lheure``, CAD22).

Une touche faite LE JOUR de son échéance ne porte aucune mention.

Temps gelé : mercredi 23/09/2026, 10 h à Casablanca.
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
from apps.crm.selectors import _a_lheure
from apps.crm.services import touche_traitee_en_avance
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

#: Mercredi 23 septembre 2026, 10 h à Casablanca.
GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
#: L'ancre de la cadence : ce matin, à l'ouverture des messages.
ANCRE = datetime.datetime(2026, 9, 23, 8, 30, tzinfo=horaires.CASABLANCA)
#: L'« Appel 3 » (J+1, 10 h 30) de ce départ tombe JEUDI — une touche à venir.
JEUDI = datetime.date(2026, 9, 24)


class TraiteeEnAvanceTests(TestCase):
    slug = 'cad44'

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD44 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        CadenceRelanceEtape.cadence_pour(self.company, 'contact')
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661004401')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _touche(self, due):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=4,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel 3',
            due_at=due, due_date=due.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=ANCRE)

    def _faire(self, etape):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'non_joint'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        return etape

    def _ligne_de_la_touche(self):
        return (LeadActivity.objects
                .filter(lead=self.lead, kind=LeadActivity.Kind.APPEL)
                .order_by('-pk').first())

    def test_la_touche_est_marquee_a_sa_date_reelle(self):
        etape = self._faire(self._touche(
            datetime.datetime(2026, 9, 24, 10, 30,
                              tzinfo=horaires.CASABLANCA)))
        self.assertEqual(etape.statut, RelanceEtape.Statut.FAIT)
        self.assertEqual(
            etape.traite_le.astimezone(horaires.CASABLANCA).date(),
            GEL.date())
        self.assertEqual(etape.due_date, JEUDI)
        self.assertTrue(touche_traitee_en_avance(etape))

    def test_le_journal_dit_traitee_en_avance(self):
        self._faire(self._touche(
            datetime.datetime(2026, 9, 24, 10, 30,
                              tzinfo=horaires.CASABLANCA)))
        ligne = self._ligne_de_la_touche()
        self.assertIsNotNone(ligne)
        self.assertIn('Traitée en avance', ligne.body)
        self.assertIn('24/09/2026', ligne.body)

    def test_le_reste_du_plan_ne_bouge_pas(self):
        self._faire(self._touche(
            datetime.datetime(2026, 9, 24, 10, 30,
                              tzinfo=horaires.CASABLANCA)))
        suivante = (self.lead.relance_etapes
                    .filter(cadence='contact', statut=RelanceEtape.Statut.A_FAIRE)
                    .order_by('ordre').first())
        self.assertIsNotNone(suivante)
        self.assertGreater(suivante.ordre, 4)
        # L'ancre n'a pas bougé : la suite reste datée depuis le départ.
        self.assertEqual(suivante.cadence_depart, ANCRE)
        # Et elle ne naît pas AVANT l'échéance de la touche traitée en avance.
        self.assertGreaterEqual(suivante.due_date, JEUDI)

    def test_ckp3_ne_compte_aucune_faute(self):
        etape = self._faire(self._touche(
            datetime.datetime(2026, 9, 24, 10, 30,
                              tzinfo=horaires.CASABLANCA)))
        self.assertTrue(_a_lheure(etape))

    def test_a_l_heure_aucune_mention(self):
        # Une touche faite LE JOUR de son échéance n'est pas « en avance ».
        self._faire(self._touche(GEL))
        ligne = self._ligne_de_la_touche()
        self.assertIsNotNone(ligne)
        self.assertNotIn('en avance', ligne.body)
