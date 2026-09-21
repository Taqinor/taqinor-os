"""CAD131 — sauter une touche n'est pas « avoir contacté le client ».

Audit L3 du 21/09/2026, section CAD-K. ``first_contacted_at`` était posé dès
qu'une note, un appel, un e-mail ou un WhatsApp était écrit par un humain — or
SAUTER une touche écrit une NOTE signée par le commercial. Sauter la toute
première touche satisfaisait donc la promesse client (« rappelé en moins de
N minutes ») ET éteignait l'escalade, qui n'agit que sur les leads SANS
horodatage : personne n'avait parlé au client, et plus rien ne le signalait.

Ce fichier verrouille la séparation :

  * sauter la touche 1 ne pose PAS ``first_contacted_at`` et n'éteint donc
    pas l'escalade ;
  * faire la touche 1 (un appel réellement passé) le pose, comme avant ;
  * et une note ORDINAIRE de la commerciale reste un contact — MRY19 n'est
    pas défait au passage.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 15 septembre 2026, 10 h à Casablanca — jour ouvré, fenêtre ouverte.
MAINTENANT = datetime.datetime(2026, 9, 15, 10, 0, tzinfo=horaires.CASABLANCA)


class ReconnaissanceTests(SimpleTestCase):
    """La règle vit là où la note est ÉCRITE — pas dans un texte deviné."""

    def test_la_mention_est_celle_que_le_service_ecrit(self):
        self.assertIn(services.VERBE_TOUCHE_SAUTEE,
                      services.MENTION_TOUCHE_SAUTEE)

    def test_une_note_ordinaire_nest_pas_une_touche_sautee(self):
        note = LeadActivity(kind=LeadActivity.Kind.NOTE,
                            body='Appelé, pas de réponse')
        self.assertFalse(services.est_note_de_touche_sautee(note))

    def test_un_appel_nest_jamais_une_touche_sautee(self):
        appel = LeadActivity(kind=LeadActivity.Kind.APPEL,
                             body=services.MENTION_TOUCHE_SAUTEE)
        self.assertFalse(services.est_note_de_touche_sautee(appel))

    def test_une_absence_dactivite_ne_casse_rien(self):
        self.assertFalse(services.est_note_de_touche_sautee(None))


class PremierContactEtabliTests(TestCase):
    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='cad131', defaults={'nom': 'cad131'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad131-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', stage=stages.NEW,
            owner=self.acteur, telephone='0600000051')

    def _touche(self, *, ordre=1, canal=RelanceEtape.Canal.APPEL):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=ordre, canal=canal, libelle=f'Touche {ordre}',
            due_at=MAINTENANT, due_date=MAINTENANT.date(),
            statut=RelanceEtape.Statut.A_FAIRE)

    def test_sauter_la_touche_1_ne_pose_pas_le_premier_contact(self):
        services.marquer_etape_relance(
            self._touche(), self.acteur, RelanceEtape.Statut.SAUTEE,
            note='pas le moment')
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.first_contacted_at)

    def test_sauter_la_touche_1_neteint_pas_lescalade(self):
        """L'escalade vise les leads NEW SANS horodatage : il reste visé."""
        services.marquer_etape_relance(
            self._touche(), self.acteur, RelanceEtape.Statut.SAUTEE)
        self.lead.refresh_from_db()
        candidats = Lead.objects.filter(
            company=self.company, source=Lead.Source.OS_NATIVE,
            stage=stages.NEW, first_contacted_at__isnull=True,
            perdu=False, is_archived=False)
        self.assertIn(self.lead, list(candidats))

    def test_faire_la_touche_1_pose_bien_le_premier_contact(self):
        """Un appel réellement passé reste une tentative — rien n'est cassé."""
        services.marquer_etape_relance(
            self._touche(), self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)

    def test_une_note_manuelle_reste_un_contact(self):
        """MRY19 n'est pas défait : `noter` compte toujours."""
        LeadActivity.objects.create(
            company=self.company, lead=self.lead, user=self.acteur,
            kind=LeadActivity.Kind.NOTE, body='Appelé, pas de réponse')
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)

    def test_sauter_puis_faire_horodate_au_moment_de_lappel(self):
        services.marquer_etape_relance(
            self._touche(ordre=1), self.acteur,
            RelanceEtape.Statut.SAUTEE)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.first_contacted_at)
        services.marquer_etape_relance(
            self._touche(ordre=2), self.acteur, RelanceEtape.Statut.FAIT,
            outcome='joint')
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)
