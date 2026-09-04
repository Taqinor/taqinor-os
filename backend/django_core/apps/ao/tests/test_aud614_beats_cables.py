"""AUD614 — deux automatismes AO écrits, testés… et jamais exécutés.

* ``generer_echeancier_ao`` n'était dispatchée par AUCUN chemin de production :
  seul ``ao.rappeler_echeances`` tournait, et il rappelait donc un échéancier
  qui n'existait pas — un no-op silencieux, la pire forme de panne (l'écran
  « Tâches planifiées » affichait vert).
* ``pieces_administratives_a_renouveler`` n'existait qu'en action GET : il
  fallait ALLER VOIR pour apprendre qu'une attestation expire, alors qu'une
  attestation périmée le jour de l'ouverture fait ÉCARTER le pli.

Run :
    python manage.py test apps.ao.tests.test_aud614_beats_cables -v2
"""
from datetime import date, timedelta

from django.test import SimpleTestCase, TestCase

from apps.ao.models import (
    AppelOffre, DossierAO, EcheanceAO, PieceAdministrative,
)
from apps.ao.scheduled import (
    INTERVALLE_RELANCE_JOURS, generer_echeanciers,
    relancer_pieces_administratives,
)
from apps.records.models import Activity
from authentication.models import Company


class TestLesTachesSontAuBeat(SimpleTestCase):
    """Une tâche absente du beat est le mode de panne dominant du dépôt."""

    def test_les_trois_entrees_existent(self):
        from erp_agentique.celery import app

        planifiees = {entree['task']
                      for entree in app.conf.beat_schedule.values()}
        for nom in ('ao.generer_echeanciers',
                    'ao.relancer_pieces_administratives',
                    'veille_ao.expirer_avis_depasses'):
            with self.subTest(tache=nom):
                self.assertIn(nom, planifiees)

    def test_la_generation_passe_AVANT_le_rappel(self):
        """Générer après le rappel ferait attendre un jour chaque échéance."""
        from erp_agentique.celery import app

        par_tache = {e['task']: e['schedule']
                     for e in app.conf.beat_schedule.values()}
        generation = par_tache['ao.generer_echeanciers']
        rappel = par_tache['ao.rappeler_echeances']
        self.assertLess(min(generation.hour) * 60 + min(generation.minute),
                        min(rappel.hour) * 60 + min(rappel.minute))


class BaseBeat(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD614 Co',
                                              slug='aud614-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-614-1', objet='Beats',
            date_limite=date.today() + timedelta(days=20),
            statut=AppelOffre.Statut.CHIFFRAGE)


class TestGenerationDesEcheanciers(BaseBeat):
    def test_le_beat_cree_l_echeancier_d_un_ao_vivant(self):
        self.assertEqual(EcheanceAO.objects.filter(appel_offre=self.ao)
                         .count(), 0)
        resume = generer_echeanciers()
        self.assertGreaterEqual(resume['creees'], 1)
        self.assertTrue(
            EcheanceAO.objects.filter(appel_offre=self.ao).exists(),
            "Aucune échéance n'existe après le tick : le rappel du matin "
            'continuerait de rappeler un échéancier inexistant.')

    def test_rejouer_le_beat_ne_cree_rien_de_plus(self):
        generer_echeanciers()
        avant = EcheanceAO.objects.filter(appel_offre=self.ao).count()
        deuxieme = generer_echeanciers()
        self.assertEqual(deuxieme['creees'], 0)
        self.assertEqual(
            EcheanceAO.objects.filter(appel_offre=self.ao).count(), avant)

    def test_un_ao_perdu_est_ignore(self):
        """Un dossier clos n'a plus d'échéance à tenir : ce serait du bruit."""
        AppelOffre.objects.filter(pk=self.ao.pk).update(
            statut=AppelOffre.Statut.PERDU)
        generer_echeanciers()
        self.assertFalse(
            EcheanceAO.objects.filter(appel_offre=self.ao).exists())


class TestRelanceDesPiecesAdministratives(BaseBeat):
    def setUp(self):
        super().setUp()
        self.dossier = DossierAO.objects.create(
            company=self.company, appel_offre=self.ao,
            reference='AODOS-614')
        # Émise il y a 100 jours, valable 120 : expire dans 20 jours, donc
        # DANS la fenêtre de rappel par défaut (30 jours).
        self.piece = PieceAdministrative.objects.create(
            company=self.company, type_piece='attestation_fiscale',
            libelle='Attestation fiscale 2026',
            date_emission=date.today() - timedelta(days=100),
            duree_validite_jours=120)
        self.piece.dossiers.add(self.dossier)

    def _notes(self):
        return Activity.objects.filter(company=self.company)

    def test_une_piece_dans_sa_fenetre_declenche_une_relance(self):
        resultat = relancer_pieces_administratives()
        self.assertEqual(resultat['relances'], 1)
        self.assertTrue(self._notes().exists())

    def test_la_relance_est_cadencee(self):
        """Trente notes pour une info, c'est un canal qu'on cesse de lire."""
        relancer_pieces_administratives()
        apres_premiere = self._notes().count()
        self.assertEqual(relancer_pieces_administratives()['relances'], 0)
        self.assertEqual(self._notes().count(), apres_premiere)

    def test_la_relance_repart_apres_l_intervalle(self):
        relancer_pieces_administratives()
        PieceAdministrative.objects.filter(pk=self.piece.pk).update(
            derniere_relance_le=(
                date.today() - timedelta(days=INTERVALLE_RELANCE_JOURS + 1)))
        self.assertEqual(relancer_pieces_administratives()['relances'], 1)

    def test_une_piece_loin_de_l_expiration_ne_declenche_rien(self):
        PieceAdministrative.objects.filter(pk=self.piece.pk).update(
            date_emission=date.today(), duree_validite_jours=365)
        self.assertEqual(relancer_pieces_administratives()['relances'], 0)

    def test_le_marqueur_est_pose(self):
        relancer_pieces_administratives()
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.derniere_relance_le, date.today())
