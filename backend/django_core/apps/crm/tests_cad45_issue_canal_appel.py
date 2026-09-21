"""CAD45 — traiter PAR ÉCRIT une touche « appel » n'impose plus une issue.

Les boutons « Appeler » et « WhatsApp » sont rendus sur CHAQUE ligne, quel
que soit le canal : le geste est déjà libre, et la commerciale écrit parfois
au lieu d'appeler. L'issue restait pourtant OBLIGATOIRE dès que
``canal == 'appel'`` — il fallait répondre « Joint / Non joint » à propos
d'un appel qui n'avait pas eu lieu. C'est ce frottement-là que CAD45
supprime, et rien d'autre.

Les deux moitiés du Done sont ici :

  * touche d'appel + message ouvert depuis l'ERP (trace RLC3) → clôture
    acceptée sans issue ;
  * touche d'appel SANS message ouvert → 400 inchangé, avec le champ fautif
    nommé (``erreurs.outcome``).

Plus deux garde-fous : la trace d'une AUTRE touche ne dispense de rien, et
une société voisine ne peut pas servir d'alibi.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import journaliser_whatsapp_ouvert
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 22 septembre 2026, 10 h à Casablanca — jour ouvré, dans la fenêtre.
MARDI = datetime.datetime(2026, 9, 22, 10, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad45'

    def setUp(self):
        gel = frozen(MARDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD45 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Aziz', stage=stages.CONTACTED,
            owner=self.acteur, telephone='+212661004501')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _touche_appel(self, libelle="Appel d'ouverture", cadence='contact'):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence=cadence, ordre=2,
            due_at=MARDI, due_date=MARDI.date(),
            canal=RelanceEtape.Canal.APPEL, libelle=libelle,
            cadence_depart=MARDI)

    def _fait(self, etape, **corps):
        return self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/', corps,
            format='json')


class IssueExigeeSurUnAppelTests(_Base):
    """Sans trace d'écrit, rien ne change."""

    slug = 'cad45-exigee'

    def test_sans_issue_ni_message_ouvert_la_cloture_est_refusee(self):
        etape = self._touche_appel()
        resp = self._fait(etape)
        self.assertEqual(resp.status_code, 400, resp.data)
        # L'erreur NOMME le champ fautif (règle fondateur 08/09/2026).
        self.assertIn('outcome', resp.data['erreurs'])
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)

    def test_avec_issue_la_cloture_passe_comme_avant(self):
        etape = self._touche_appel()
        resp = self._fait(etape, outcome='non_joint')
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.FAIT)


class TraiteeParEcritTests(_Base):
    """Le message de la touche a été ouvert : plus d'issue exigée."""

    slug = 'cad45-ecrit'

    def test_message_ouvert_puis_cloture_sans_issue(self):
        etape = self._touche_appel()
        journaliser_whatsapp_ouvert(etape, self.acteur)
        resp = self._fait(etape)
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.FAIT)

    def test_le_clic_whatsapp_de_l_ERP_suffit(self):
        etape = self._touche_appel()
        # Le chemin RÉEL : l'écran ouvre la conversation depuis la touche.
        ouverture = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/whatsapp/', {},
            format='json')
        self.assertEqual(ouverture.status_code, 200, ouverture.data)
        resp = self._fait(etape)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_la_trace_d_une_autre_touche_ne_dispense_de_rien(self):
        autre = self._touche_appel(libelle='Appel 4', cadence='contact')
        journaliser_whatsapp_ouvert(autre, self.acteur)
        etape = self._touche_appel()
        resp = self._fait(etape)
        self.assertEqual(resp.status_code, 400, resp.data)


class IsolationSocieteTests(_Base):
    """Une trace d'une AUTRE société ne dispense de rien."""

    slug = 'cad45-tenant'

    def test_la_trace_d_une_autre_societe_ne_dispense_de_rien(self):
        autre = Company.objects.create(nom='CAD45 Autre', slug='cad45-autre')
        CompanyProfile.objects.get_or_create(company=autre)
        autre_resp = User.objects.create_user(
            username='cad45-autre-resp', password='x',
            role_legacy='responsable', company=autre)
        lead_autre = Lead.objects.create(
            company=autre, nom='Voisin', stage=stages.CONTACTED,
            owner=autre_resp, telephone='+212661004599')
        etape_autre = RelanceEtape.objects.create(
            company=autre, lead=lead_autre, cadence='contact', ordre=2,
            due_at=MARDI, due_date=MARDI.date(),
            canal=RelanceEtape.Canal.APPEL, libelle="Appel d'ouverture")
        journaliser_whatsapp_ouvert(etape_autre, autre_resp)
        etape = self._touche_appel()
        resp = self._fait(etape)
        self.assertEqual(resp.status_code, 400, resp.data)
