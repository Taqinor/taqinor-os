"""Tests NTFIN26-34 — Close management (clôture rapide).

Couvre :

* NTFIN26 — le seed crée un modèle mensuel ≥ 8 tâches, idempotent.
* NTFIN27 — instancier une clôture crée une tâche par tâche-modèle ; cocher
  fait avancer le statut global.
* NTFIN28 — une période avec 2 tâches obligatoires ouvertes n'est pas prête.
* NTFIN29 — un accrual de 50 000 en juin poste une OD au 30/06 et son extourne
  au 01/07.
* NTFIN30 — une charge 100k→160k remonte +60k / +60 % au-dessus du seuil.
* NTFIN33 — deux écritures identiques remontent un doublon ; une déséquilibrée
  remonte en anomalie bloquante.
* NTFIN34 — le cockpit expose un close_status dérivé de l'avancement.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    AccrualCloture, EcritureComptable, ExerciceComptable, InstanceCloture,
    LigneEcriture, ModeleCloture, PeriodeComptable, TacheCloture)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ModeleClotureSeedTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin26', 'NTFIN26')

    def test_seed_cree_modele_mensuel_min_8_taches(self):
        modele = services.seed_modele_cloture_mensuel(self.co)
        self.assertEqual(modele.periodicite,
                         ModeleCloture.Periodicite.MENSUELLE)
        self.assertGreaterEqual(modele.taches.count(), 8)

    def test_seed_idempotent(self):
        services.seed_modele_cloture_mensuel(self.co)
        m2 = services.seed_modele_cloture_mensuel(self.co)
        self.assertEqual(ModeleCloture.objects.filter(company=self.co).count(), 1)
        self.assertEqual(
            m2.taches.count(), len(services._TACHES_CLOTURE_MENSUELLE))


class InstanceClotureTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin27', 'NTFIN27')
        self.modele = services.seed_modele_cloture_mensuel(self.co)
        self.periode = PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 30), libelle='Juin 2026')

    def test_instancier_cree_une_tache_par_modele(self):
        instance = services.instancier_cloture(self.periode, self.modele)
        self.assertEqual(instance.taches.count(), self.modele.taches.count())
        self.assertEqual(instance.statut, InstanceCloture.Statut.OUVERT)

    def test_cocher_fait_avancer_statut(self):
        instance = services.instancier_cloture(self.periode, self.modele)
        premiere = instance.taches.order_by('ordre').first()
        services.cocher_tache_cloture(premiere)
        instance.refresh_from_db()
        self.assertEqual(instance.statut, InstanceCloture.Statut.EN_COURS)


class PretACloturerTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin28', 'NTFIN28')
        self.periode = PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 30), libelle='Juin 2026')

    def test_deux_taches_obligatoires_ouvertes_bloquent(self):
        instance = InstanceCloture.objects.create(
            company=self.co, periode=self.periode)
        TacheCloture.objects.create(
            company=self.co, instance=instance, libelle='T1',
            obligatoire=True, ordre=1)
        TacheCloture.objects.create(
            company=self.co, instance=instance, libelle='T2',
            obligatoire=True, ordre=2)
        TacheCloture.objects.create(
            company=self.co, instance=instance, libelle='T3',
            obligatoire=False, ordre=3)
        result = selectors.pret_a_cloturer(self.periode)
        self.assertFalse(result['pret'])
        self.assertEqual(len(result['taches_manquantes']), 2)

    def test_periode_sans_instance_est_prete(self):
        result = selectors.pret_a_cloturer(self.periode)
        self.assertTrue(result['pret'])


class AccrualTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin29', 'NTFIN29')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = ExerciceComptable.objects.create(
            company=self.co, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31))
        self.periode = PeriodeComptable.objects.create(
            company=self.co, exercice=self.exercice, date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 30), libelle='Juin 2026')

    def test_accrual_poste_od_et_extourne(self):
        accrual = AccrualCloture.objects.create(
            company=self.co, periode=self.periode,
            type_accrual=AccrualCloture.Type.CHARGE_A_PAYER,
            compte_charge_produit='6111', compte_contrepartie='4417',
            montant=Decimal('50000'), libelle='FAP fournisseur')
        services.poster_accrual(accrual)
        accrual.refresh_from_db()
        self.assertIsNotNone(accrual.ecriture_id)
        self.assertIsNotNone(accrual.ecriture_extourne_id)
        self.assertEqual(accrual.ecriture.date_ecriture, date(2026, 6, 30))
        self.assertEqual(accrual.ecriture_extourne.date_ecriture,
                         date(2026, 7, 1))

    def test_accrual_idempotent(self):
        accrual = AccrualCloture.objects.create(
            company=self.co, periode=self.periode,
            compte_charge_produit='6111', compte_contrepartie='4417',
            montant=Decimal('50000'))
        services.poster_accrual(accrual)
        ec_id = accrual.ecriture_id
        services.poster_accrual(accrual)
        accrual.refresh_from_db()
        self.assertEqual(accrual.ecriture_id, ec_id)


class AnalyseVariationTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin30', 'NTFIN30')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.compte = services._assurer_compte(self.co, '6111')

    def _charge(self, montant, jour):
        journal = services._journal(
            self.co, services.Journal.Type.OPERATIONS_DIVERSES)
        contrep = services._assurer_compte(self.co, '4411')
        services.creer_ecriture(
            self.co, journal, jour, 'Charge test', [
                {'compte': self.compte, 'debit': montant, 'credit': Decimal('0')},
                {'compte': contrep, 'debit': Decimal('0'), 'credit': montant},
            ], statut=EcritureComptable.Statut.VALIDEE)

    def test_variation_materielle_signalee(self):
        self._charge(Decimal('100000'), date(2025, 6, 15))
        self._charge(Decimal('160000'), date(2026, 6, 15))
        data = selectors.analyse_variation(
            self.co, compte_prefixe='6111',
            periode=(date(2026, 6, 1), date(2026, 6, 30)),
            periode_comparee=(date(2025, 6, 1), date(2025, 6, 30)),
            seuil_materialite=Decimal('10000'))
        ligne = next(li for li in data['lignes'] if li['compte'] == '6111')
        self.assertEqual(ligne['variation'], Decimal('60000'))
        self.assertEqual(ligne['variation_pct'], Decimal('60.00'))
        self.assertTrue(ligne['a_expliquer'])


class AnomaliesEcrituresTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin33', 'NTFIN33')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.c1 = services._assurer_compte(self.co, '6111')
        self.c2 = services._assurer_compte(self.co, '5141')

    def test_doublon_probable_detecte(self):
        for _ in range(2):
            services.creer_ecriture(
                self.co,
                services._journal(self.co,
                                  services.Journal.Type.OPERATIONS_DIVERSES),
                date(2026, 6, 15), 'Achat', [
                    {'compte': self.c1, 'debit': Decimal('1500'),
                     'credit': Decimal('0'), 'tiers_type': 'fournisseur',
                     'tiers_id': 7},
                    {'compte': self.c2, 'debit': Decimal('0'),
                     'credit': Decimal('1500'), 'tiers_type': 'fournisseur',
                     'tiers_id': 7},
                ], statut=EcritureComptable.Statut.VALIDEE)
        data = selectors.anomalies_ecritures(
            self.co, date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 30))
        types = [a['type'] for a in data['anomalies']]
        self.assertIn('doublon_probable', types)

    def test_ecriture_desequilibree_bloquante(self):
        # Écriture déséquilibrée créée directement (contourne creer_ecriture).
        ec = EcritureComptable.objects.create(
            company=self.co,
            journal=services._journal(
                self.co, services.Journal.Type.OPERATIONS_DIVERSES),
            date_ecriture=date(2026, 6, 20), libelle='Déséquilibrée')
        LigneEcriture.objects.create(
            company=self.co, ecriture=ec, compte=self.c1,
            debit=Decimal('100'), credit=Decimal('0'))
        LigneEcriture.objects.create(
            company=self.co, ecriture=ec, compte=self.c2,
            debit=Decimal('0'), credit=Decimal('90'))
        data = selectors.anomalies_ecritures(
            self.co, date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 30))
        self.assertGreaterEqual(data['nb_bloquantes'], 1)


class CockpitClotureTests(TestCase):
    def setUp(self):
        self.co = make_company('ntfin34', 'NTFIN34')
        self.periode = PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 30), libelle='Juin 2026')

    def test_cockpit_close_status(self):
        instance = InstanceCloture.objects.create(
            company=self.co, periode=self.periode, date_cible=date(2026, 7, 5))
        TacheCloture.objects.create(
            company=self.co, instance=instance, libelle='T1',
            statut=TacheCloture.Statut.FAIT, ordre=1)
        TacheCloture.objects.create(
            company=self.co, instance=instance, libelle='T2',
            statut=TacheCloture.Statut.A_FAIRE, ordre=2)
        data = selectors.cockpit_cloture(self.co, self.periode)
        self.assertEqual(data['taches_total'], 2)
        self.assertEqual(data['taches_faites'], 1)
        self.assertIn(data['close_status'], ('en_retard', 'en_bonne_voie'))
