"""NTAI29 — Tests de la surveillance de dérive (drift) des features.

Couvre : PSI pur (stdlib, déterministe), baseline implicite, montée du PSI
au-dessus du seuil → alerte notifiée, scoping société des snapshots, et la
tâche Celery mensuelle (no-op propre sans fournisseur déclaré).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from ..drift import (PSI_SEUIL_ALERTE, baseline_pour, distribution_providers,
                     enregistrer_snapshot, normaliser_distribution, psi,
                     register_distribution_provider)
from ..models import DriftSnapshot
from ..tasks import surveiller_drift_mensuel_task

User = get_user_model()

STABLE = {'bas': 50, 'moyen': 30, 'haut': 20}
IDENTIQUE = {'bas': 100, 'moyen': 60, 'haut': 40}       # mêmes proportions
DERIVE = {'bas': 2, 'moyen': 8, 'haut': 90}             # population renversée


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Ntai29PsiPurTests(TestCase):
    """Le calcul est PUR : aucun accès base, aucun LLM."""

    def test_normalisation_en_proportions(self):
        self.assertEqual(normaliser_distribution({'a': 1, 'b': 3}),
                         {'a': 0.25, 'b': 0.75})

    def test_normalisation_vide_ou_nulle(self):
        self.assertEqual(normaliser_distribution({}), {})
        self.assertEqual(normaliser_distribution({'a': 0}), {})
        self.assertEqual(normaliser_distribution('pas un dict'), {})
        # Valeurs non numériques ou négatives ignorées, jamais d'exception.
        self.assertEqual(normaliser_distribution({'a': 'x', 'b': -3, 'c': 2}),
                         {'c': 1.0})

    def test_psi_nul_sur_distributions_identiques(self):
        self.assertAlmostEqual(psi(STABLE, STABLE), 0.0, places=9)
        # Mêmes PROPORTIONS avec des effectifs doublés : toujours 0.
        self.assertAlmostEqual(psi(STABLE, IDENTIQUE), 0.0, places=9)

    def test_psi_positif_et_symetrique_sur_une_derive(self):
        valeur = psi(STABLE, DERIVE)
        self.assertGreater(valeur, PSI_SEUIL_ALERTE)
        self.assertAlmostEqual(valeur, psi(DERIVE, STABLE), places=9)

    def test_psi_croit_avec_lampleur_de_la_derive(self):
        legere = psi(STABLE, {'bas': 45, 'moyen': 33, 'haut': 22})
        forte = psi(STABLE, DERIVE)
        self.assertLess(legere, forte)

    def test_psi_zero_si_une_distribution_est_vide(self):
        self.assertEqual(psi({}, STABLE), 0.0)
        self.assertEqual(psi(STABLE, {}), 0.0)

    def test_psi_gere_un_bucket_disparu_sans_exploser(self):
        # Un bucket absent du courant vaudrait log(0) : borné par epsilon.
        valeur = psi({'a': 50, 'b': 50}, {'a': 100})
        self.assertGreater(valeur, 0.0)
        self.assertLess(valeur, 1000.0)


class Ntai29SnapshotTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntai29-co', 'NTAI29 Co')
        # Garde CI : la seconde société porte un slug distinct explicite.
        cls.autre = make_company('ntai29-autre', 'NTAI29 Autre')
        cls.responsable = User.objects.create_user(
            username='ntai29-resp', password='x', company=cls.company,
            role_legacy='responsable')

    def test_premier_snapshot_devient_la_baseline(self):
        snap = enregistrer_snapshot(
            company=self.company, modele='win_proba', distribution=STABLE,
            date=date(2026, 1, 1))
        self.assertTrue(snap.est_baseline)
        self.assertEqual(snap.psi, 0.0)
        self.assertFalse(snap.alerte_emise)
        self.assertEqual(baseline_pour(self.company, 'win_proba'), snap)

    def test_derive_fait_monter_le_psi_et_declenche_une_alerte(self):
        from apps.notifications.models import Notification

        enregistrer_snapshot(
            company=self.company, modele='win_proba', distribution=STABLE,
            date=date(2026, 1, 1))
        avant = Notification.objects.count()

        derive = enregistrer_snapshot(
            company=self.company, modele='win_proba', distribution=DERIVE,
            date=date(2026, 2, 1))

        self.assertFalse(derive.est_baseline)
        self.assertGreater(derive.psi, PSI_SEUIL_ALERTE)
        self.assertTrue(derive.alerte_emise)
        self.assertGreater(Notification.objects.count(), avant)

    def test_pas_dalerte_sous_le_seuil(self):
        from apps.notifications.models import Notification

        enregistrer_snapshot(
            company=self.company, modele='churn', distribution=STABLE,
            date=date(2026, 1, 1))
        avant = Notification.objects.count()

        stable = enregistrer_snapshot(
            company=self.company, modele='churn',
            distribution={'bas': 51, 'moyen': 29, 'haut': 20},
            date=date(2026, 2, 1))

        self.assertLess(stable.psi, PSI_SEUIL_ALERTE)
        self.assertFalse(stable.alerte_emise)
        self.assertEqual(Notification.objects.count(), avant)

    def test_idempotent_sur_la_meme_periode(self):
        enregistrer_snapshot(
            company=self.company, modele='churn', distribution=STABLE,
            date=date(2026, 1, 1))
        enregistrer_snapshot(
            company=self.company, modele='churn', distribution=DERIVE,
            date=date(2026, 2, 1))
        enregistrer_snapshot(
            company=self.company, modele='churn', distribution=DERIVE,
            date=date(2026, 2, 1))
        self.assertEqual(
            DriftSnapshot.objects.filter(
                company=self.company, modele='churn').count(), 2)

    def test_snapshots_scopes_societe(self):
        enregistrer_snapshot(
            company=self.company, modele='win_proba', distribution=STABLE,
            date=date(2026, 1, 1))
        # L'autre société n'hérite PAS de cette baseline : son premier
        # snapshot est le sien.
        snap_autre = enregistrer_snapshot(
            company=self.autre, modele='win_proba', distribution=DERIVE,
            date=date(2026, 2, 1))
        self.assertTrue(snap_autre.est_baseline)
        self.assertEqual(snap_autre.psi, 0.0)
        self.assertIsNone(baseline_pour(self.autre, 'churn'))
        self.assertEqual(
            DriftSnapshot.objects.filter(company=self.company).count(), 1)

    def test_notifier_desactivable(self):
        from apps.notifications.models import Notification

        enregistrer_snapshot(
            company=self.company, modele='win_proba', distribution=STABLE,
            date=date(2026, 1, 1))
        avant = Notification.objects.count()
        snap = enregistrer_snapshot(
            company=self.company, modele='win_proba', distribution=DERIVE,
            date=date(2026, 2, 1), notifier=False)
        self.assertGreater(snap.psi, PSI_SEUIL_ALERTE)
        self.assertFalse(snap.alerte_emise)
        self.assertEqual(Notification.objects.count(), avant)


class Ntai29TacheMensuelleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntai29t-co', 'NTAI29T Co')
        cls.autre = make_company('ntai29t-autre', 'NTAI29T Autre')

    def test_noop_propre_sans_fournisseur(self):
        self.assertEqual(distribution_providers(), {})
        self.assertEqual(surveiller_drift_mensuel_task(), {})
        self.assertEqual(DriftSnapshot.objects.count(), 0)

    def _register(self, modele, fonction):
        from .. import drift as drift_mod

        register_distribution_provider(modele, fonction)
        self.addCleanup(
            drift_mod._DISTRIBUTION_PROVIDERS.pop, modele, None)

    def test_fournisseur_declare_produit_un_snapshot_par_societe(self):
        self._register('win_proba', lambda company: STABLE)

        resultat = surveiller_drift_mensuel_task()
        self.assertIn(self.company.id, resultat)
        self.assertEqual(resultat[self.company.id]['win_proba'], 0.0)
        self.assertTrue(
            DriftSnapshot.objects.filter(
                company=self.company, modele='win_proba').exists())

    def test_fournisseur_en_echec_narrete_pas_la_tache(self):
        def casse(company):
            raise RuntimeError('scorer indisponible')

        self._register('casse', casse)
        self._register('ok', lambda company: STABLE)

        resultat = surveiller_drift_mensuel_task()
        self.assertIn(self.company.id, resultat)
        self.assertIn('ok', resultat[self.company.id])
        self.assertNotIn('casse', resultat[self.company.id])
