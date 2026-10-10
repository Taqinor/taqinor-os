"""COCKPIT-CONTRÔLE B1 — les deux traces d'une étape : origine et reports.

Ordre fondateur du 30/09/2026 (« voir si la commerciale a fait tout ce
qu'elle devait ») : ``reporter_prochaine_touche`` ÉCRASAIT l'échéance — une
étape repoussée trois fois se lisait comme une étape du jour, et son retard
disparaissait en silence. Deux colonnes additives
(``RelanceEtape.due_initial_at`` / ``nb_reports``, migration 0116) :

  * à la CRÉATION, l'échéance d'origine est l'échéance posée — partout, y
    compris le ``bulk_create`` du plan et la touche née d'une issue ;
  * un geste HUMAIN qui repousse CETTE étape (« Reporter », « Mettre en
    veille », rappel du journal d'appel, date de relance de la fiche) compte
    un report et garde l'origine ; la suite du plan décalée par ricochet
    n'est pas comptée, son origine glisse du même écart ;
  * un déplacement du MOTEUR (relances décalées autour d'une visite, rappel
    demandé par le client, recalage d'un geste de visite, placement de la
    touche qu'une réponse vient de faire naître) ne compte rien et l'origine
    suit l'échéance ;
  * la reprise de la migration pose l'origine des lignes existantes.

Horloge FIXE : mercredi 30/09/2026, 10 h à Casablanca (jour ouvré).
"""
import datetime
import importlib
import itertools

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services, stages
from apps.crm import cadence_touche
from apps.crm import cadence_filet
from apps.crm import cadence_plan
from apps.crm import cadence_reperes
from apps.crm.cadence_config import CLE_CONFIRMATION
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import CadenceRelanceEtape

User = get_user_model()

GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=horaires.CASABLANCA)
A_FAIRE = RelanceEtape.Statut.A_FAIRE

_seq = itertools.count(1)


def _a(jours, heure=10, minute=0):
    """Un instant AWARE (Casablanca), ``jours`` après le jour gelé."""
    jour = GEL.date() + datetime.timedelta(days=jours)
    return datetime.datetime.combine(
        jour, datetime.time(heure, minute), tzinfo=horaires.CASABLANCA)


class _Base(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        n = next(_seq)
        self.n = n
        self.company = Company.objects.create(
            nom=f'Cockpit traces {n}', slug=f'cockpit-traces-{n}')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'cockpit-traces-resp-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.lead = Lead.objects.create(
            company=self.company, nom=f'Prospect traces {n}',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone=f'+21266181{n:04d}')

    def _touche(self, quand, *, cadence='contact', ordre=2,
                canal=RelanceEtape.Canal.APPEL, libelle='Appel', **champs):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence=cadence,
            ordre=ordre, canal=canal, libelle=libelle, due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=GEL, **champs)

    def _ouvertes(self):
        return list(self.lead.relance_etapes.filter(statut=A_FAIRE))


class OrigineALaCreationTests(_Base):

    def test_une_etape_creee_porte_son_origine(self):
        etape = self._touche(_a(1))
        etape.refresh_from_db()
        self.assertEqual(etape.due_initial_at, etape.due_at)
        self.assertEqual(etape.nb_reports, 0)

    def test_une_etape_sans_heure_n_a_pas_d_origine_inventee(self):
        etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=2,
            canal=RelanceEtape.Canal.APPEL, libelle='Sans heure',
            due_date=GEL.date())
        etape.refresh_from_db()
        self.assertIsNone(etape.due_initial_at)

    def test_le_bulk_create_du_plan_pose_l_origine(self):
        etapes = cadence_plan.initialiser_plan_relance(
            self.lead, self.acteur, cadence='contact', depart=GEL)
        self.assertTrue(etapes)
        for etape in etapes:
            etape.refresh_from_db()
            with self.subTest(ordre=etape.ordre):
                self.assertIsNotNone(etape.due_initial_at)
                self.assertEqual(etape.due_initial_at, etape.due_at)
                self.assertEqual(etape.nb_reports, 0)

    def test_la_touche_nee_d_une_issue_porte_son_origine(self):
        cadence_plan.initialiser_plan_relance(
            self.lead, self.acteur, cadence='contact', depart=GEL)
        [ouverte] = self._ouvertes()
        cadence_touche.marquer_etape_relance(
            ouverte, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        [nee] = self._ouvertes()
        self.assertNotEqual(nee.pk, ouverte.pk)
        self.assertEqual(nee.due_initial_at, nee.due_at)
        self.assertEqual(nee.nb_reports, 0)


class ReportHumainTests(_Base):

    def test_reporter_compte_un_report_et_garde_l_origine(self):
        cible = self._touche(_a(1), ordre=2)
        suivante = self._touche(_a(2), ordre=3)
        origine = cible.due_at
        cadence_plan.reporter_prochaine_touche(
            self.lead, self.acteur, _a(5, 11), etape=cible)
        cible.refresh_from_db()
        suivante.refresh_from_db()
        self.assertEqual(cible.nb_reports, 1)
        self.assertEqual(cible.due_initial_at, origine)
        self.assertNotEqual(cible.due_at, origine)
        # Ricochet : la suite glisse, n'est pas comptée, son origine suit.
        self.assertEqual(suivante.nb_reports, 0)
        self.assertEqual(suivante.due_initial_at, suivante.due_at)
        self.assertEqual(suivante.due_at - _a(2), cible.due_at - origine)

    def test_deux_reports_comptent_deux(self):
        cible = self._touche(_a(1))
        origine = cible.due_at
        cadence_plan.reporter_prochaine_touche(
            self.lead, self.acteur, _a(2, 11), etape=cible)
        cadence_plan.reporter_prochaine_touche(
            self.lead, self.acteur, _a(6, 11), etape=cible)
        cible.refresh_from_db()
        self.assertEqual(cible.nb_reports, 2)
        self.assertEqual(cible.due_initial_at, origine)

    def test_l_action_reporter_compte(self):
        cible = self._touche(_a(1))
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{cible.pk}/reporter/',
            {'rappel_le': _a(5).date().isoformat(), 'rappel_heure': '11:00'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cible.refresh_from_db()
        self.assertEqual(cible.nb_reports, 1)
        self.assertEqual(cible.due_initial_at, _a(1))

    def test_mettre_en_veille_compte(self):
        cible = self._touche(_a(1))
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{cible.pk}/reporter/',
            {'rappel_le': _a(12).date().isoformat(), 'rappel_heure': '11:00',
             'mode': 'veille'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cible.refresh_from_db()
        self.assertEqual(cible.statut, A_FAIRE)
        self.assertEqual(cible.nb_reports, 1)
        self.assertEqual(cible.due_initial_at, _a(1))

    def test_le_rappel_du_journal_d_appel_compte(self):
        cible = self._touche(_a(1))
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/log-interaction/',
            {'kind': 'appel', 'outcome': 'rappel',
             'rappel_le': _a(5).date().isoformat(), 'rappel_heure': '11:00'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cible.refresh_from_db()
        self.assertEqual(cible.nb_reports, 1)
        self.assertEqual(cible.due_initial_at, _a(1))

    def test_la_date_de_relance_de_la_fiche_compte(self):
        cible = self._touche(_a(1))
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'relance_date': _a(5).date().isoformat()}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cible.refresh_from_db()
        self.assertEqual(cible.nb_reports, 1)
        self.assertEqual(cible.due_initial_at, _a(1))


class DeplacementMoteurTests(_Base):

    def test_les_relances_decalees_autour_de_la_visite_ne_comptent_pas(self):
        touche = self._touche(_a(1), cadence=cadence_reperes.VISITE_CADENCE,
                              ordre=2, libelle='Relance proposition')
        deplacee = services.suspendre_plan_jusqu_apres_visite(
            self.lead, self.acteur, _a(5).date())
        self.assertIsNotNone(deplacee)
        touche.refresh_from_db()
        self.assertGreater(touche.due_at, _a(1))
        self.assertEqual(touche.nb_reports, 0)
        self.assertEqual(touche.due_initial_at, touche.due_at)

    def test_un_rappel_demande_par_le_client_ne_compte_pas(self):
        touche = self._touche(_a(2))
        services.poser_touche_rappel_demande(self.lead, user=None)
        touche.refresh_from_db()
        self.assertLess(touche.due_at, _a(2))
        self.assertEqual(touche.nb_reports, 0)
        self.assertEqual(touche.due_initial_at, touche.due_at)

    def test_le_recalage_d_un_geste_de_visite_ne_compte_pas(self):
        premiere = cadence_filet._poser_etape_visite(
            self.lead, cle=CLE_CONFIRMATION,
            ordre=cadence_reperes.VISITE_ORDRE_CONFIRMATION,
            quand=_a(3).date())
        recalee = cadence_filet._poser_etape_visite(
            self.lead, cle=CLE_CONFIRMATION,
            ordre=cadence_reperes.VISITE_ORDRE_CONFIRMATION,
            quand=_a(6).date())
        self.assertEqual(recalee.pk, premiere.pk)
        recalee.refresh_from_db()
        self.assertEqual(recalee.nb_reports, 0)
        self.assertEqual(recalee.due_initial_at, recalee.due_at)

    def test_la_touche_placee_par_a_rappeler_le_n_est_pas_un_report(self):
        """« À rappeler le… » sur un barreau CONSOMME la touche : la date
        PLACE celle qui lui succède — un placement, jamais un report."""
        gabarits = CadenceRelanceEtape.cadence_pour(self.company, 'contact')
        echeances = cadence_plan.calculer_echeances_cadence(
            self.lead, 'contact', GEL, gabarits=gabarits)
        gabarit, echeance = next(
            (g, e) for g, e in echeances if g.ordre == 2)
        touche = self._touche(echeance, ordre=gabarit.ordre,
                              canal=gabarit.canal, libelle=gabarit.libelle)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{touche.pk}/fait/',
            {'outcome': 'rappel', 'rappel_le': _a(2).date().isoformat(),
             'rappel_heure': '11:00'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ouvertes = self._ouvertes()
        self.assertTrue(ouvertes)
        for etape in ouvertes:
            with self.subTest(ordre=etape.ordre):
                self.assertEqual(etape.nb_reports, 0)
                self.assertEqual(etape.due_initial_at, etape.due_at)


class RepriseMigrationTests(_Base):

    def test_la_reprise_pose_l_origine_des_lignes_existantes(self):
        avec_heure = self._touche(_a(1))
        sans_heure = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=3,
            canal=RelanceEtape.Canal.APPEL, libelle='Sans heure',
            due_date=GEL.date())
        RelanceEtape.objects.filter(pk=avec_heure.pk).update(
            due_initial_at=None)
        migration = importlib.import_module(
            'apps.crm.migrations.0116_cockpit_relance_etape_traces')
        migration.reprendre_due_initial(django_apps, None)
        avec_heure.refresh_from_db()
        sans_heure.refresh_from_db()
        self.assertEqual(avec_heure.due_initial_at, avec_heure.due_at)
        self.assertIsNone(sans_heure.due_initial_at)
        self.assertEqual(avec_heure.nb_reports, 0)
