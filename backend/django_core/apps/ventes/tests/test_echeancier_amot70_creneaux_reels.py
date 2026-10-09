"""AMOT70 (C-AMOT-017, volet amont) — ``termes_paiement_devis`` rend les
créneaux RÉELS de l'échéancier du devis : un créneau absent vaut 0 (jamais le
défaut société), la somme fait 100 %, et les tranches non typées sont
rabattues sur les mêmes créneaux que ``montants_tranches`` (première =
acompte, dernière = solde, milieu = matériel).

Devis ORM réel, fonction réelle. Test-du-test : remettre
``termes.get('materiel', 60)`` comme valeur de départ ⇒
``test_deux_tranches_typees`` échoue (160 %).
"""
from decimal import Decimal

from hypothesis.extra.django import TestCase
from hypothesis import given, settings
from hypothesis import strategies as st

from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import repartition_paiement
from apps.ventes.utils.echeancier import termes_paiement_devis

_SOCIETE = {'acompte': 30, 'materiel': 60, 'solde': 10}


class CreneauxReelsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from authentication.models import Company
        cls.company = Company.objects.create(nom='AMOT70', slug='amot70-co')
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Créneaux', prenom='Client')
        cls.n = 0

    def _termes(self, echeancier):
        type(self).n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-AMOT70-{self.n}',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20'), echeancier=echeancier)
        return {k: float(v) for k, v in
                termes_paiement_devis(devis, _SOCIETE).items()}

    def test_deux_tranches_typees(self):
        self.assertEqual(self._termes([
            {'libelle': 'Commande', 'type': 'acompte', 'pct_or_montant': 45},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 55}]),
            {'acompte': 45, 'materiel': 0, 'solde': 55})

    def test_deux_tranches_non_typees(self):
        self.assertEqual(self._termes([
            {'libelle': 'T1', 'pct_or_montant': 45},
            {'libelle': 'T2', 'pct_or_montant': 55}]),
            {'acompte': 45, 'materiel': 0, 'solde': 55})

    def test_quatre_tranches_non_typees(self):
        self.assertEqual(self._termes([
            {'libelle': 'T1', 'pct_or_montant': 30},
            {'libelle': 'T2', 'pct_or_montant': 20},
            {'libelle': 'T3', 'pct_or_montant': 40},
            {'libelle': 'T4', 'pct_or_montant': 10}]),
            {'acompte': 30, 'materiel': 60, 'solde': 10})

    def test_trois_positionnelles_inchangees(self):
        self.assertEqual(self._termes([
            {'libelle': 'A', 'pct_or_montant': 40},
            {'libelle': 'B', 'pct_or_montant': 50},
            {'libelle': 'C', 'pct_or_montant': 10}]),
            {'acompte': 40, 'materiel': 50, 'solde': 10})

    def test_sans_echeancier_la_societe(self):
        self.assertEqual(self._termes(None), {'acompte': 30, 'materiel': 60,
                                              'solde': 10})

    def test_jumeau_cases(self):
        """Le jumeau ``builder.repartition_paiement`` (normalisation
        ``pm = 100 − a − s``) donne les MÊMES pourcentages."""
        termes = self._termes([
            {'libelle': 'Commande', 'type': 'acompte', 'pct_or_montant': 45},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 55}])
        cases = repartition_paiement(10000, termes)
        self.assertEqual((cases['pct_a'], cases['pct_s']), (45, 55))
        self.assertTrue(cases['deux_cases'])

    @settings(max_examples=40, deadline=None)
    @given(st.lists(st.integers(1, 60), min_size=2, max_size=5))
    def test_propriete_somme_100(self, poids):
        total = sum(poids)
        pcts = [round(p * 100 / total) for p in poids]
        pcts[-1] = 100 - sum(pcts[:-1])
        if pcts[-1] <= 0:
            return
        termes = self._termes([{'libelle': f'T{i}', 'pct_or_montant': p}
                               for i, p in enumerate(pcts)])
        self.assertAlmostEqual(sum(termes.values()), 100, places=6)
