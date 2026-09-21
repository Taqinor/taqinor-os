"""AUD730 — les 4 producteurs RH « automatiques » sont enfin planifiés.

DÉFAUT (rouge avant ce correctif) : `accruer_conges_mensuel`,
`clore_pointages_ouverts`, `purger_candidatures` et
`planifier_appreciations_pour_societe` n'avaient NI `@shared_task` NI entrée
`beat_schedule` — grep exhaustif zéro référence dans `apps/rh/tasks.py` (qui ne
contenait que `rh.alertes_expiration`/`rh.alertes_cdd`) ni dans
`erp_agentique/celery.py`. Chacun avait une management command dédiée mais
jamais planifiée, accessible seulement par une exécution manuelle serveur,
alors que leurs propres docstrings les décrivent comme automatiques. Sans
exécution périodique, la rétention CNDP des CV n'était JAMAIS appliquée (enjeu
PII, pas seulement opérationnel).

Après correctif : 4 `@shared_task` nommées `rh.<nom_de_commande>` (la
convention qu'impose `scripts/check_commandes_planifiees.py`) + 4 entrées beat.
Les deux balayages non neutres (anonymisation IRRÉVERSIBLE, cadence
d'appréciation = décision métier) tournent en DRY-RUN tant que leur variable
d'environnement n'est pas posée — même convention que `GED_PURGE_AUTO_APPLY`.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from authentication.models import Company
from apps.rh import tasks
from apps.rh.models import (
    Candidature,
    DossierEmploye,
    OuverturePoste,
    Pointage,
    ReglageRH,
    SoldeConge,
)

NOMS = (
    'rh.accruer_conges',
    'rh.clore_pointages_ouverts',
    'rh.purger_candidatures',
    'rh.planifier_appreciations',
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class BeatReachabilityTests(TestCase):
    """Les 4 noms sont enregistrés ET planifiés — c'était le cœur du constat."""

    def test_les_quatre_taches_sont_enregistrees(self):
        for nom in NOMS:
            self.assertTrue(
                hasattr(tasks, nom.split('.', 1)[1]),
                f'{nom} : fonction absente de apps/rh/tasks.py')

    def test_les_quatre_taches_sont_dans_le_beat_schedule(self):
        from erp_agentique.celery import app
        planifiees = {
            entree['task'] for entree in app.conf.beat_schedule.values()}
        for nom in NOMS:
            self.assertIn(
                nom, planifiees,
                f'{nom} n\'est dans AUCUN beat_schedule : elle ne tournera '
                'jamais')


class AccruerCongesTaskTests(TestCase):
    def setUp(self):
        self.co = make_company('aud730-acc', 'A')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='A1', nom='Tazi', prenom='Reda',
            statut=DossierEmploye.Statut.ACTIF,
            date_embauche=timezone.localdate() - timedelta(days=800))

    def test_credite_le_solde_du_mois_courant(self):
        resultat = tasks.accruer_conges()
        self.assertEqual(resultat['credites'], 1)
        solde = SoldeConge.objects.get(
            company=self.co, employe=self.emp, annee=resultat['annee'])
        self.assertGreater(solde.acquis, Decimal('0'))

    def test_idempotente_le_meme_mois(self):
        premier = tasks.accruer_conges()
        acquis = SoldeConge.objects.get(
            company=self.co, employe=self.emp,
            annee=premier['annee']).acquis
        second = tasks.accruer_conges()
        self.assertEqual(second['credites'], 0)
        self.assertEqual(second['deja_acquis'], 1)
        self.assertEqual(
            SoldeConge.objects.get(
                company=self.co, employe=self.emp,
                annee=premier['annee']).acquis, acquis)


class ClorePointagesTaskTests(TestCase):
    def setUp(self):
        self.co = make_company('aud730-pt', 'B')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='P1', nom='Alami', prenom='Sara',
            statut=DossierEmploye.Statut.ACTIF)

    def test_no_op_sans_seuil_configure(self):
        Pointage.objects.create(
            company=self.co, employe=self.emp,
            heure_arrivee=timezone.now() - timedelta(hours=30))
        self.assertEqual(tasks.clore_pointages_ouverts(), {'clotures': 0})

    def test_cloture_un_pointage_ouvert_au_dela_du_seuil(self):
        ReglageRH.objects.create(
            company=self.co, pointage_auto_depart_apres_h=12)
        pointage = Pointage.objects.create(
            company=self.co, employe=self.emp,
            heure_arrivee=timezone.now() - timedelta(hours=30))
        resultat = tasks.clore_pointages_ouverts()
        self.assertEqual(resultat['clotures'], 1)
        pointage.refresh_from_db()
        self.assertIsNotNone(pointage.heure_depart)


class PurgerCandidaturesTaskTests(TestCase):
    """L'anonymisation est IRRÉVERSIBLE : dry-run tant que l'opt-in est absent."""

    def setUp(self):
        self.co = make_company('aud730-cv', 'C')
        ouverture = OuverturePoste.objects.create(
            company=self.co, intitule='Technicien PV')
        self.cand = Candidature.objects.create(
            company=self.co, ouverture=ouverture, nom='Karim Bennani',
            email='karim@example.ma', etape=Candidature.Etape.REJETE)
        Candidature.objects.filter(pk=self.cand.pk).update(
            date_modification=timezone.now() - timedelta(days=365 * 3))

    @override_settings(RH_PURGE_CANDIDATURES_AUTO_APPLY=False)
    def test_dry_run_par_defaut_ne_modifie_rien(self):
        resultat = tasks.purger_candidatures()
        self.assertTrue(resultat['dry_run'])
        self.assertEqual(resultat['anonymisees'], 0)
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.nom, 'Karim Bennani')

    @override_settings(RH_PURGE_CANDIDATURES_AUTO_APPLY=True)
    def test_opt_in_applique_reellement(self):
        resultat = tasks.purger_candidatures()
        self.assertFalse(resultat['dry_run'])
        if resultat['eligibles']:
            self.cand.refresh_from_db()
            self.assertNotEqual(self.cand.nom, 'Karim Bennani')


class PlanifierAppreciationsTaskTests(TestCase):
    """La cadence d'un cycle d'appréciation reste une décision du fondateur."""

    def setUp(self):
        self.co = make_company('aud730-ap', 'D')

    @override_settings(RH_APPRECIATIONS_AUTO_APPLY=False)
    def test_dry_run_par_defaut(self):
        resultat = tasks.planifier_appreciations()
        self.assertTrue(resultat['dry_run'])

    @override_settings(RH_APPRECIATIONS_AUTO_APPLY=True)
    def test_opt_in_bascule_en_application(self):
        resultat = tasks.planifier_appreciations()
        self.assertFalse(resultat['dry_run'])
