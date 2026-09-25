"""La réponse du « Fait » annonce la prochaine étape du LEAD.

Relevé du vérificateur (25/09/2026) sur la décision fondateur du 24/09/2026 :
``prochaine_touche`` (réponse de ``POST relance-etapes/<id>/fait/``) était lue
DANS LA CADENCE de la touche close. Or la suite d'une touche vit souvent
ailleurs : « Visite acceptée » sur un appel de prise de contact pose
« Planifier la visite technique convenue » (cadence du suivi de proposition),
« Client joint » pose « Préparer et envoyer le devis » (cadence générique).
La réponse annonçait « rien » alors qu'une étape du jour attendait — l'écran
se taisait. Elle lit désormais la MÊME prochaine étape que
``Lead.relance_date`` (``services._prochaine_touche_a_faire``).

Horloge FIXE : mercredi 23/09/2026, 10 h à Casablanca.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CADENCES_DEFAUT, CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE


class ProchaineEtapeDuLeadTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='FPE Solaire', slug='fpe')
        CompanyProfile.objects.get_or_create(company=self.company)
        for cadence in CADENCES_DEFAUT:
            CadenceRelanceEtape.cadence_pour(self.company, cadence)
        self.acteur = User.objects.create_user(
            username='fpe-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom='Tazi', prenom='Youssef',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212661000654')
        self.appel = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=2,
            canal=RelanceEtape.Canal.APPEL, libelle="Appel d'ouverture",
            due_at=GEL, due_date=GEL.date(), cadence_depart=GEL)

    def _fait(self, outcome):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{self.appel.pk}/fait/',
            {'outcome': outcome}, format='json')

    def test_visite_acceptee_annonce_l_etape_planifier_du_jour(self):
        resp = self._fait(services.OUTCOME_VISITE_ACCEPTEE)

        self.assertEqual(resp.status_code, 200, resp.data)
        planifier = self.lead.relance_etapes.get(
            libelle=services.VISITE_FILET_LIBELLE, statut=A_FAIRE)
        self.assertNotEqual(planifier.cadence, self.appel.cadence)
        prochaine = resp.data['prochaine_touche']
        self.assertIsNotNone(prochaine)
        self.assertEqual(prochaine['due_date'], GEL.date().isoformat())
        self.assertEqual(prochaine['due_date'],
                         planifier.due_date.isoformat())
        self.assertEqual(prochaine['canal'], planifier.canal)
        self.assertEqual(prochaine['due_at'], planifier.due_at.isoformat())

    def test_client_joint_annonce_l_etape_devis(self):
        resp = self._fait('joint')

        self.assertEqual(resp.status_code, 200, resp.data)
        devis = self.lead.relance_etapes.get(
            libelle=services.FILET_JOINT_LIBELLE, statut=A_FAIRE)
        self.assertEqual(resp.data['prochaine_touche']['due_date'],
                         devis.due_date.isoformat())
