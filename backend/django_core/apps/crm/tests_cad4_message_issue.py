"""CAD4 (résiduel) — le refus « issue obligatoire » cite les réponses RÉELLES.

CAD4 a fait d'« Intéressé » et de « Client joint » UN SEUL mot à l'écran
(« Client joint »). Le 400 renvoyé quand un appel est coché « Fait » sans issue
listait encore « Intéressé » : il renvoyait la commerciale vers un bouton
introuvable. Il nomme désormais le champ (`outcome`) ET les réponses que le
panneau propose vraiment.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.views import MESSAGE_ISSUE_APPEL_OBLIGATOIRE

User = get_user_model()

#: Les libellés que `RelanceEtapeRow.jsx` (QUESTIONS.contact) propose.
REPONSES_ECRAN = ('Client joint', 'Pas de réponse', 'À rappeler le…', 'Refus')


class MessageIssuePurTests(SimpleTestCase):

    def test_plus_jamais_interesse(self):
        self.assertNotIn('Intéressé', MESSAGE_ISSUE_APPEL_OBLIGATOIRE)

    def test_les_reponses_de_l_ecran_sont_citees(self):
        for libelle in REPONSES_ECRAN:
            with self.subTest(libelle=libelle):
                self.assertIn(libelle, MESSAGE_ISSUE_APPEL_OBLIGATOIRE)


class MessageIssueApiTests(TestCase):

    def test_le_refus_nomme_le_champ_et_les_vraies_reponses(self):
        company = Company.objects.create(nom='CAD4 Solaire', slug='cad4-msg')
        acteur = User.objects.create_user(
            username='cad4-msg-resp', password='x', role_legacy='responsable',
            company=company)
        lead = Lead.objects.create(company=company, nom='Benali',
                                   stage=stages.CONTACTED, owner=acteur,
                                   telephone='+212661000004')
        quand = datetime.datetime(2026, 9, 23, 10, 0,
                                  tzinfo=horaires.CASABLANCA)
        etape = RelanceEtape.objects.create(
            company=company, lead=lead, cadence='contact', ordre=2,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel 2',
            due_at=quand, due_date=quand.date())
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(acteur)}')
        resp = api.post(f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
                        {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data, {'erreurs': {
            'outcome': MESSAGE_ISSUE_APPEL_OBLIGATOIRE}})
