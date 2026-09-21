"""CAD118 — l'issue de la touche vit SUR la touche.

Audit L3 du 21/09/2026, section CAD-K. On mesurait si les touches étaient
cochées, jamais si elles joignaient quelqu'un : l'issue ne vivait que sur la
ligne de chatter, et le seul rapprochement possible était une fenêtre de DEUX
MINUTES entre les deux horodatages — un bricolage qui casse en silence dès
qu'un traitement ralentit. Résultat : « quelle touche, à quelle heure, quel
jour, sur quel canal joint réellement le client » restait sans réponse, et
c'est le seul KPI marocain possible faute de source externe sur la
joignabilité.

Ce fichier verrouille :

  * toute touche close PAR UN HUMAIN porte son issue, écrite au même instant
    que la ligne d'historique ;
  * la ligne de chatter reste la source de vérité du chatter — elle porte la
    même issue, la colonne ne la remplace pas ;
  * aucune valeur d'énumération neuve : les choix sont ceux de
    ``LeadActivity.OUTCOMES`` ;
  * et l'agrégat de CAD87 se calcule DÉSORMAIS sur la colonne, sans la
    fenêtre de deux minutes — une ligne de chatter écrite une heure plus tard
    ne fausse plus rien.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, mesure_cadence, services, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Jeudi 10 septembre 2026, 10 h à Casablanca — jour ouvré, fenêtre ouverte.
MAINTENANT = datetime.datetime(2026, 9, 10, 10, 0, tzinfo=horaires.CASABLANCA)


class ChoixTests(SimpleTestCase):
    def test_aucune_valeur_denumeration_neuve(self):
        """Le chatter reste la source de vérité des issues possibles."""
        self.assertEqual(
            [valeur for valeur, _ in RelanceEtape._meta.get_field(
                'outcome').choices],
            [valeur for valeur, _ in LeadActivity.OUTCOMES])

    def test_la_colonne_porte_sa_question(self):
        """« Chaque champ EST le script d'appel » : la question vit ici."""
        champ = RelanceEtape._meta.get_field('outcome')
        self.assertTrue(champ.help_text)
        self.assertIn('joint', champ.help_text)

    def test_la_colonne_est_vue_par_la_mesure_de_cad87(self):
        self.assertTrue(mesure_cadence._colonne_issue_disponible())


class OutcomeSurLaToucheTests(TestCase):
    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='cad118', defaults={'nom': 'cad118'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad118-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', stage=stages.CONTACTED,
            owner=self.acteur, telephone='0600000031')

    def _touche(self, *, ordre=1, canal=RelanceEtape.Canal.APPEL):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=ordre, due_at=MAINTENANT, due_date=MAINTENANT.date(),
            canal=canal, libelle='Appel', statut=RelanceEtape.Statut.A_FAIRE)

    def test_une_touche_close_porte_son_issue(self):
        etape = self._touche()
        services.marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='joint')
        etape.refresh_from_db()
        self.assertEqual(etape.outcome, 'joint')
        self.assertEqual(etape.traite_par_id, self.acteur.id)
        self.assertIsNotNone(etape.traite_le)

    def test_la_ligne_de_chatter_porte_la_meme_issue(self):
        """La colonne s'ajoute au chatter, elle ne le remplace pas."""
        etape = self._touche(ordre=2)
        services.marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='interesse')
        etape.refresh_from_db()
        activite = (LeadActivity.objects
                    .filter(lead=self.lead).exclude(outcome='')
                    .order_by('-id').first())
        self.assertIsNotNone(activite)
        self.assertEqual(activite.outcome, etape.outcome)

    def test_une_cloture_sans_issue_laisse_la_colonne_vide(self):
        """Vide = rien n'a été saisi. Jamais un « non joint » supposé."""
        etape = self._touche(ordre=3)
        services.marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.SAUTEE, note='occupé')
        etape.refresh_from_db()
        self.assertEqual(etape.outcome, '')

    def test_une_ligne_davant_cad118_reste_vide(self):
        """Aucune donnée n'est inventée rétroactivement (migration additive)."""
        etape = self._touche(ordre=4)
        self.assertEqual(etape.outcome, '')


class MesureSansFenetreDeDeuxMinutesTests(TestCase):
    """CAD87 se calcule sur la colonne — la fenêtre de 2 min a disparu."""

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='cad118-mesure', defaults={'nom': 'cad118-mesure'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad118-mesure-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Chraibi', stage=stages.CONTACTED,
            owner=self.acteur)

    def test_une_issue_ecrite_une_heure_plus_tard_ne_fausse_plus_rien(self):
        instant = MAINTENANT - datetime.timedelta(days=2)
        etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=1,
            due_at=instant, due_date=instant.date(),
            canal=RelanceEtape.Canal.APPEL, libelle='Appel',
            statut=RelanceEtape.Statut.FAIT, outcome='joint',
            traite_par=self.acteur, traite_le=instant)
        # Une ligne de chatter écrite BIEN plus tard : sous l'ancien
        # rapprochement elle était perdue, la touche comptait « non jointe ».
        activite = LeadActivity.objects.create(
            company=self.company, lead=self.lead, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, body='Appel.', outcome='joint')
        LeadActivity.objects.filter(pk=activite.pk).update(
            created_at=instant + datetime.timedelta(hours=1))

        lignes = mesure_cadence.taux_joint_par_creneau(self.company)
        self.assertEqual(len(lignes), 1, lignes)
        self.assertEqual(lignes[0]['closes'], 1)
        self.assertEqual(lignes[0]['joints'], 1)
        self.assertEqual(lignes[0]['taux_joint_pct'], 100.0)
        self.assertEqual(etape.outcome, 'joint')

    def test_la_mesure_annonce_lire_la_colonne(self):
        mesure = mesure_cadence.mesure_cadence(self.company)
        self.assertEqual(mesure['source_issue'], 'colonne')
