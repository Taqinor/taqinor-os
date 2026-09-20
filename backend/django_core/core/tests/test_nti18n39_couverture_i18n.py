"""NTI18N39 — job Beat hebdomadaire de la couverture i18n.

Ce que ces tests PROUVENT :

* la tâche est PLANIFIÉE au beat, ROUTÉE vers `scheduled`, et son module
  (`core/tasks_i18n.py`) est bien couvert par l'autodécouverte Celery — sinon
  le worker la rejetterait en « unregistered task » (incident du 14/09/2026) ;
* elle réutilise `build_report()` du script NTI18N1 sans le dupliquer ;
* elle N'ÉCRIT RIEN quand le rapport n'est pas mesurable (scripts/ ou
  frontend/src absents du conteneur) — jamais un instantané à 0 % qui
  afficherait un effondrement faux ;
* l'idempotence (société, lundi de la semaine) : un rejeu met à jour, il
  n'empile pas ;
* le delta vaut ``None`` sans semaine antérieure (jamais 0, qui voudrait dire
  « aucun progrès »).
"""
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from core import tasks_i18n
from core.models import I18nCoverageSnapshot

RAPPORT = {
    'generated_at': '2026-09-14T06:00:00+00:00',
    'total_components': 200,
    'migrated_components': 50,
    'coverage_pct': 25.0,
    'domains': {
        'crm': {'total': 40, 'migrated': 10, 'hardcoded_strings': 300,
                'pct': 25.0},
        'ventes': {'total': 60, 'migrated': 20, 'hardcoded_strings': 450,
                   'pct': 33.3},
    },
}


def make_company(slug, nom, actif=True):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    if company.actif != actif:
        company.actif = actif
        # SCA18 — `Company.save()` réconcilie le pont bool↔statut : on laisse
        # `statut` dans `update_fields` pour que la suspension soit persistée
        # entièrement, pas seulement le booléen.
        company.save(update_fields=['actif', 'statut'])
    return company


class CablageBeatTests(SimpleTestCase):
    def test_tache_planifiee_au_beat(self):
        from erp_agentique.celery import app
        noms = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('core.recalculer_couverture_i18n', noms)

    def test_tache_routee_vers_scheduled(self):
        route = settings.CELERY_TASK_ROUTES[
            'core.recalculer_couverture_i18n']
        self.assertEqual(route['queue'], 'scheduled')

    def test_module_couvert_par_autodecouverte(self):
        """`tasks_i18n` doit figurer dans la boucle `related_name` de
        celery.py : sans lui, le worker n'importe jamais ce module."""
        from erp_agentique.celery import app
        app.loader.import_default_modules()
        self.assertIn('core.recalculer_couverture_i18n', app.tasks)


class RapportUtilisableTests(SimpleTestCase):
    def test_rapport_mesure_est_utilisable(self):
        self.assertTrue(tasks_i18n.rapport_utilisable(RAPPORT))

    def test_rapport_sans_composant_refuse(self):
        self.assertFalse(tasks_i18n.rapport_utilisable(
            {'total_components': 0, 'coverage_pct': 0.0, 'domains': {}}))

    def test_rapport_vide_refuse(self):
        self.assertFalse(tasks_i18n.rapport_utilisable({}))
        self.assertFalse(tasks_i18n.rapport_utilisable(None))

    def test_chiffres_somment_les_chaines_par_domaine(self):
        chiffres = tasks_i18n._chiffres(RAPPORT)
        self.assertEqual(chiffres['chaines_en_dur'], 750)
        self.assertEqual(chiffres['composants_total'], 200)
        self.assertEqual(chiffres['composants_migres'], 50)
        self.assertEqual(chiffres['couverture_pct'], Decimal('25.0'))


class ExtracteurTests(SimpleTestCase):
    def test_script_charge_depuis_la_racine_du_depot(self):
        """Sur l'hôte/la CI le dépôt est complet : le script DOIT se charger et
        exposer `build_report` — la logique est réutilisée, pas recopiée."""
        module = tasks_i18n.charger_extracteur()
        if module is None:
            self.skipTest(
                "scripts/extract_i18n_strings.py hors de portée depuis ce "
                "conteneur — c'est le cas de production, couvert par "
                'test_rien_ecrit_sans_rapport_mesurable.')
        self.assertTrue(callable(module.build_report))


class RecalculTests(TestCase):
    def setUp(self):
        self.a = make_company('nti18n39-a', 'NTI18N39 A')
        self.b = make_company('nti18n39-b', 'NTI18N39 B')
        self.suspendue = make_company(
            'nti18n39-sus', 'NTI18N39 Suspendue', actif=False)

    def test_un_instantane_par_societe_active(self):
        ecrits = tasks_i18n.recalculer_couverture_i18n(
            semaine=date(2026, 9, 14), rapport=RAPPORT)
        self.assertEqual(len(ecrits), 2)
        societes = set(
            I18nCoverageSnapshot.objects.values_list('company_id', flat=True))
        self.assertEqual(societes, {self.a.id, self.b.id})

    def test_societe_suspendue_ignoree(self):
        tasks_i18n.recalculer_couverture_i18n(
            semaine=date(2026, 9, 14), rapport=RAPPORT)
        self.assertFalse(
            I18nCoverageSnapshot.objects
            .filter(company=self.suspendue).exists())

    def test_chiffres_persistes(self):
        tasks_i18n.recalculer_couverture_i18n(
            semaine=date(2026, 9, 14), rapport=RAPPORT)
        snap = I18nCoverageSnapshot.objects.get(
            company=self.a, semaine=date(2026, 9, 14))
        self.assertEqual(snap.couverture_pct, Decimal('25.0'))
        self.assertEqual(snap.composants_total, 200)
        self.assertEqual(snap.composants_migres, 50)
        self.assertEqual(snap.chaines_en_dur, 750)
        self.assertIn('crm', snap.par_domaine)

    def test_rejeu_met_a_jour_sans_empiler(self):
        tasks_i18n.recalculer_couverture_i18n(
            semaine=date(2026, 9, 14), rapport=RAPPORT)
        rapport_2 = dict(RAPPORT, coverage_pct=31.5, migrated_components=63)
        tasks_i18n.recalculer_couverture_i18n(
            semaine=date(2026, 9, 14), rapport=rapport_2)
        qs = I18nCoverageSnapshot.objects.filter(
            company=self.a, semaine=date(2026, 9, 14))
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().couverture_pct, Decimal('31.5'))

    def test_rien_ecrit_sans_rapport_mesurable(self):
        ecrits = tasks_i18n.recalculer_couverture_i18n(
            semaine=date(2026, 9, 14),
            rapport={'total_components': 0, 'coverage_pct': 0.0,
                     'domains': {}})
        self.assertEqual(ecrits, [])
        self.assertFalse(I18nCoverageSnapshot.objects.exists())

    def test_semaine_par_defaut_est_un_lundi(self):
        ecrits = tasks_i18n.recalculer_couverture_i18n(rapport=RAPPORT)
        self.assertTrue(ecrits)
        self.assertEqual(ecrits[0].semaine.weekday(), 0)


class DeltaTests(TestCase):
    def setUp(self):
        self.company = make_company('nti18n39-delta', 'NTI18N39 Delta')

    def _snap(self, semaine, pct):
        return I18nCoverageSnapshot.objects.create(
            company=self.company, semaine=semaine,
            couverture_pct=Decimal(pct), composants_total=200,
            composants_migres=50, chaines_en_dur=750)

    def test_delta_none_sans_semaine_anterieure(self):
        snap = self._snap(date(2026, 9, 14), '25.0')
        self.assertIsNone(snap.precedent())
        self.assertIsNone(snap.delta_pct)

    def test_delta_calcule_vs_semaine_precedente(self):
        self._snap(date(2026, 9, 7), '20.0')
        snap = self._snap(date(2026, 9, 14), '25.5')
        self.assertEqual(snap.delta_pct, Decimal('5.5'))

    def test_delta_ignore_une_autre_societe(self):
        autre = make_company('nti18n39-delta-b', 'NTI18N39 Delta B')
        I18nCoverageSnapshot.objects.create(
            company=autre, semaine=date(2026, 9, 7),
            couverture_pct=Decimal('10.0'), composants_total=200,
            composants_migres=20, chaines_en_dur=800)
        snap = self._snap(date(2026, 9, 14), '25.0')
        self.assertIsNone(snap.delta_pct)

    def test_lundi_de_ramene_au_lundi(self):
        # 2026-09-17 est un jeudi ; son lundi ISO est le 2026-09-14.
        self.assertEqual(
            I18nCoverageSnapshot.lundi_de(date(2026, 9, 17)),
            date(2026, 9, 14))
        self.assertEqual(
            I18nCoverageSnapshot.lundi_de(date(2026, 9, 14)),
            date(2026, 9, 14))
