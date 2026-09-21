"""NTRET12 — Moteur de promotions panier : tests du module PUR ``engine.py``.

``unittest.TestCase`` volontairement (PAS ``django.test.TestCase``) : ce
module n'a aucune dépendance ORM/DB — ces tests le prouvent en tournant sans
jamais toucher la base ni les settings Django au-delà de l'import minimal.
"""
import datetime
import unittest
from decimal import Decimal

from apps.promotions.engine import (
    LignePanier, Regle, evaluer_promotions, total_remises,
)


def ligne(produit_id=1, categorie_id=10, quantite='1', prix='100'):
    return LignePanier(
        produit_id=produit_id, categorie_id=categorie_id,
        quantite=Decimal(quantite), prix_unitaire_ttc=Decimal(prix))


class RemisePourcentageProduitTests(unittest.TestCase):
    def test_applique_pourcentage_sur_lignes_categorie_ciblee(self):
        lignes = [ligne(categorie_id=10, prix='200'), ligne(categorie_id=99, prix='50')]
        regle = Regle(
            id=1, type_regle='remise_pourcentage_produit', categorie_id=10,
            remise_pct=Decimal('10'))
        remises = evaluer_promotions(lignes, [regle])
        self.assertEqual(len(remises), 1)
        self.assertEqual(remises[0].montant, Decimal('20.00'))  # 10% de 200

    def test_sans_ciblage_s_applique_a_tout_le_panier(self):
        lignes = [ligne(prix='100'), ligne(produit_id=2, categorie_id=20, prix='50')]
        regle = Regle(id=1, type_regle='remise_pourcentage_produit', remise_pct=Decimal('10'))
        remises = evaluer_promotions(lignes, [regle])
        self.assertEqual(remises[0].montant, Decimal('15.00'))  # 10% de 150


class RemiseMontantPanierTests(unittest.TestCase):
    def test_remise_montant_fixe(self):
        lignes = [ligne(prix='300')]
        regle = Regle(id=1, type_regle='remise_montant_panier', remise_montant=Decimal('50'))
        remises = evaluer_promotions(lignes, [regle])
        self.assertEqual(remises[0].montant, Decimal('50.00'))

    def test_remise_plafonnee_au_total_panier(self):
        lignes = [ligne(prix='30')]
        regle = Regle(id=1, type_regle='remise_montant_panier', remise_montant=Decimal('50'))
        remises = evaluer_promotions(lignes, [regle])
        self.assertEqual(remises[0].montant, Decimal('30.00'))

    def test_montant_min_panier_bloque_la_regle(self):
        lignes = [ligne(prix='30')]
        regle = Regle(
            id=1, type_regle='remise_montant_panier', remise_montant=Decimal('10'),
            montant_min_panier=Decimal('100'))
        self.assertEqual(evaluer_promotions(lignes, [regle]), [])


class NPourMTests(unittest.TestCase):
    def test_3_pour_2_sur_categorie(self):
        # 3 unités à 100 MAD dans la catégorie ciblée → la moins chère (100)
        # des 3 est offerte.
        lignes = [ligne(categorie_id=10, quantite='3', prix='100')]
        regle = Regle(
            id=1, type_regle='n_pour_m', categorie_id=10, n_achete=3, m_paye=2)
        remises = evaluer_promotions(lignes, [regle])
        self.assertEqual(remises[0].montant, Decimal('100.00'))

    def test_offre_la_moins_chere_du_groupe(self):
        lignes = [
            ligne(categorie_id=10, produit_id=1, quantite='1', prix='300'),
            ligne(categorie_id=10, produit_id=2, quantite='1', prix='150'),
            ligne(categorie_id=10, produit_id=3, quantite='1', prix='90'),
        ]
        regle = Regle(
            id=1, type_regle='n_pour_m', categorie_id=10, n_achete=3, m_paye=2)
        remises = evaluer_promotions(lignes, [regle])
        self.assertEqual(remises[0].montant, Decimal('90.00'))  # la moins chère

    def test_pas_assez_d_unites_ne_declenche_rien(self):
        lignes = [ligne(categorie_id=10, quantite='2', prix='100')]
        regle = Regle(
            id=1, type_regle='n_pour_m', categorie_id=10, n_achete=3, m_paye=2)
        self.assertEqual(evaluer_promotions(lignes, [regle]), [])

    def test_deux_groupes_complets(self):
        lignes = [ligne(categorie_id=10, quantite='6', prix='100')]
        regle = Regle(
            id=1, type_regle='n_pour_m', categorie_id=10, n_achete=3, m_paye=2)
        remises = evaluer_promotions(lignes, [regle])
        self.assertEqual(remises[0].montant, Decimal('200.00'))  # 2 offertes


class PlageHoraireTests(unittest.TestCase):
    def test_applicable_dans_la_fenetre_horaire(self):
        lignes = [ligne(prix='100')]
        regle = Regle(
            id=1, type_regle='plage_horaire', remise_pct=Decimal('20'),
            heure_debut=datetime.time(17, 0), heure_fin=datetime.time(19, 0),
            jours_semaine=[0, 1, 2, 3, 4])
        maintenant = datetime.datetime(2026, 8, 10, 18, 0)  # lundi 18h
        remises = evaluer_promotions(lignes, [regle], maintenant=maintenant)
        self.assertEqual(remises[0].montant, Decimal('20.00'))

    def test_hors_fenetre_horaire_ne_s_applique_pas(self):
        lignes = [ligne(prix='100')]
        regle = Regle(
            id=1, type_regle='plage_horaire', remise_pct=Decimal('20'),
            heure_debut=datetime.time(17, 0), heure_fin=datetime.time(19, 0),
            jours_semaine=[0, 1, 2, 3, 4])
        maintenant = datetime.datetime(2026, 8, 10, 12, 0)  # lundi midi
        self.assertEqual(evaluer_promotions(lignes, [regle], maintenant=maintenant), [])

    def test_hors_jours_configures_ne_s_applique_pas(self):
        lignes = [ligne(prix='100')]
        regle = Regle(
            id=1, type_regle='plage_horaire', remise_pct=Decimal('20'),
            heure_debut=datetime.time(17, 0), heure_fin=datetime.time(19, 0),
            jours_semaine=[5, 6])  # week-end seulement
        maintenant = datetime.datetime(2026, 8, 10, 18, 0)  # lundi 18h
        self.assertEqual(evaluer_promotions(lignes, [regle], maintenant=maintenant), [])


class PeriodeValiditeTests(unittest.TestCase):
    def test_regle_hors_periode_de_validite_ignoree(self):
        lignes = [ligne(prix='100')]
        regle = Regle(
            id=1, type_regle='remise_montant_panier', remise_montant=Decimal('10'),
            date_debut=datetime.date(2026, 1, 1), date_fin=datetime.date(2026, 1, 31))
        maintenant = datetime.datetime(2026, 3, 1, 10, 0)
        self.assertEqual(evaluer_promotions(lignes, [regle], maintenant=maintenant), [])


class CumulabiliteTests(unittest.TestCase):
    def test_regles_cumulables_s_additionnent(self):
        lignes = [ligne(prix='200')]
        r1 = Regle(id=1, type_regle='remise_pourcentage_produit',
                   remise_pct=Decimal('10'), cumulable=True)
        r2 = Regle(id=2, type_regle='remise_montant_panier',
                   remise_montant=Decimal('15'), cumulable=True)
        remises = evaluer_promotions(lignes, [r1, r2])
        self.assertEqual(len(remises), 2)
        self.assertEqual(total_remises(lignes, [r1, r2]), Decimal('35.00'))

    def test_regles_non_cumulables_se_neutralisent_priorite_gagne(self):
        lignes = [ligne(prix='200')]
        # r1 = priorité plus haute (nombre plus petit) mais remise plus faible.
        r1 = Regle(id=1, type_regle='remise_montant_panier',
                   remise_montant=Decimal('10'), cumulable=False, priorite=1)
        r2 = Regle(id=2, type_regle='remise_montant_panier',
                   remise_montant=Decimal('50'), cumulable=False, priorite=5)
        remises = evaluer_promotions(lignes, [r1, r2])
        self.assertEqual(len(remises), 1)
        self.assertEqual(remises[0].regle_id, 1)
        self.assertEqual(remises[0].montant, Decimal('10.00'))

    def test_a_egalite_de_priorite_la_remise_la_plus_forte_gagne(self):
        lignes = [ligne(prix='200')]
        r1 = Regle(id=1, type_regle='remise_montant_panier',
                   remise_montant=Decimal('10'), cumulable=False, priorite=1)
        r2 = Regle(id=2, type_regle='remise_montant_panier',
                   remise_montant=Decimal('50'), cumulable=False, priorite=1)
        remises = evaluer_promotions(lignes, [r1, r2])
        self.assertEqual(len(remises), 1)
        self.assertEqual(remises[0].regle_id, 2)

    def test_cumulables_et_non_cumulables_coexistent(self):
        lignes = [ligne(prix='200')]
        cumulable = Regle(id=1, type_regle='remise_pourcentage_produit',
                          remise_pct=Decimal('5'), cumulable=True)
        non_cum_faible = Regle(id=2, type_regle='remise_montant_panier',
                               remise_montant=Decimal('10'), cumulable=False, priorite=1)
        non_cum_forte = Regle(id=3, type_regle='remise_montant_panier',
                              remise_montant=Decimal('50'), cumulable=False, priorite=9)
        remises = evaluer_promotions(lignes, [cumulable, non_cum_faible, non_cum_forte])
        self.assertEqual(len(remises), 2)  # la cumulable + la non-cumulable gagnante
        montants = sorted(r.montant for r in remises)
        self.assertEqual(montants, [Decimal('10.00'), Decimal('10.00')])


class DesactivationTests(unittest.TestCase):
    def test_panier_vide_ne_declenche_aucune_regle(self):
        regle = Regle(id=1, type_regle='remise_montant_panier', remise_montant=Decimal('10'))
        self.assertEqual(evaluer_promotions([], [regle]), [])

    def test_aucune_regle_fournie(self):
        self.assertEqual(evaluer_promotions([ligne()], []), [])


if __name__ == '__main__':
    unittest.main()
