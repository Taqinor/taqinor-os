"""CALX72 — l'écran Tarification saisit TOUS les réglages du lot 5.

Ce qui est prouvé ici (côté serveur de la porte de saisie) :

* le sérialiseur de ``GET/PATCH tarification/`` SERT chaque réglage du lot 5
  (CALX274 → CALX284) — l'écran ``TarificationSection.jsx`` lit la même
  liste dans ce fichier (son test vitest) ;
* une société VIERGE sert ces réglages VIDES (aucune valeur préremplie, hors
  les deux déclarations d'aujourd'hui : structure ``tranches`` et prix TTC) ;
* ``validate()`` relaie ``erreurs_reglages_tarif`` : chaque refus est rangé
  sous le NOM du champ fautif (une grille horaire sans ``tou_source``, une
  indexation sans ``indexation_source``, un dégressif sans
  ``amortissement_coefficient``, un taux d'imposition sans
  ``fiscalite_source``, un prix unique sans ``prix_unique_kwh``) ;
* un PATCH partiel est validé sur l'état FUSIONNÉ (base + requête) ;
* une saisie complète et sourcée passe.

Tests PURS : ``TariffSettings()`` non enregistré, aucune requête SQL.

Run :
    python manage.py test apps.parametres.tests_calx72_ecran_tarification
"""
import unittest

from apps.parametres.models_tariff import TariffSettings
from apps.parametres.serializers_tariff import (
    CHAMPS_LOT5, TariffSettingsSerializer)

SOURCE = 'Facture SRM (jeu d’essai)'
HEURES = ['creuse'] * 8 + ['pleine'] * 10 + ['pointe'] * 4 + ['creuse'] * 2


def erreurs_de(data, instance=None):
    serializer = TariffSettingsSerializer(
        instance=instance if instance is not None else TariffSettings(),
        data=data, partial=True)
    valide = serializer.is_valid()
    return valide, serializer.errors


class ChampsServisTest(unittest.TestCase):
    def test_chaque_reglage_du_lot_5_est_servi(self):
        attendus = {
            'tou_heures', 'tou_tarifs', 'tou_source', 'tou_date_source',
            'mecanisme_compensation', 'report_periode', 'plafond_annuel_kwh',
            'ratio_compensation', 'structure_tarif', 'pays_tarif',
            'prix_unique_kwh', 'poste_haut', 'poste_bas',
            'prix_incluent_taxes', 'taxes', 'charge_minimale_mad_jour',
            'indexation_tarif_pct_an', 'indexation_source',
            'taux_imposition_pct', 'amortissement_mode',
            'amortissement_duree_ans', 'amortissement_coefficient',
            'fiscalite_source'}
        self.assertEqual(set(CHAMPS_LOT5), attendus)
        self.assertTrue(attendus <= set(TariffSettingsSerializer.Meta.fields))
        # company n'est jamais exposée ni acceptée.
        self.assertNotIn('company', TariffSettingsSerializer.Meta.fields)

    def test_societe_vierge_sert_des_reglages_vides(self):
        data = TariffSettingsSerializer(TariffSettings()).data
        for champ in ('tou_heures', 'tou_tarifs', 'tou_date_source',
                      'report_periode', 'plafond_annuel_kwh',
                      'ratio_compensation', 'prix_unique_kwh', 'poste_haut',
                      'poste_bas', 'taxes', 'charge_minimale_mad_jour',
                      'indexation_tarif_pct_an', 'taux_imposition_pct',
                      'amortissement_duree_ans', 'amortissement_coefficient'):
            self.assertIsNone(data[champ], champ)
        for champ in ('tou_source', 'mecanisme_compensation', 'pays_tarif',
                      'indexation_source', 'fiscalite_source'):
            self.assertEqual(data[champ], '', champ)
        # Les deux déclarations d'aujourd'hui (facture inchangée).
        self.assertEqual(data['structure_tarif'], 'tranches')
        self.assertIs(data['prix_incluent_taxes'], True)
        self.assertEqual(data['amortissement_mode'], 'aucun')


class ValidationNommeLeChampTest(unittest.TestCase):
    def test_grille_horaire_sans_source_ni_date(self):
        valide, erreurs = erreurs_de({
            'tou_heures': HEURES,
            'tou_tarifs': {'creuse': '0.9', 'pleine': '1.1', 'pointe': '1.5'}})
        self.assertFalse(valide)
        self.assertIn('tou_source', erreurs)
        self.assertIn('tou_date_source', erreurs)
        self.assertIn('tou_source', str(erreurs['tou_source'][0]))

    def test_indexation_sans_source(self):
        valide, erreurs = erreurs_de({'indexation_tarif_pct_an': '4'})
        self.assertFalse(valide)
        self.assertEqual(set(erreurs), {'indexation_source'})

    def test_degressif_sans_coefficient(self):
        valide, erreurs = erreurs_de({
            'amortissement_mode': 'degressif', 'amortissement_duree_ans': 5,
            'fiscalite_source': SOURCE})
        self.assertFalse(valide)
        self.assertEqual(set(erreurs), {'amortissement_coefficient'})
        self.assertIn('amortissement_coefficient',
                      str(erreurs['amortissement_coefficient'][0]))

    def test_taux_d_imposition_sans_source(self):
        valide, erreurs = erreurs_de({'taux_imposition_pct': '31'})
        self.assertFalse(valide)
        self.assertEqual(set(erreurs), {'fiscalite_source'})

    def test_prix_unique_sans_prix(self):
        valide, erreurs = erreurs_de({'structure_tarif': 'prix_unique'})
        self.assertFalse(valide)
        self.assertEqual(set(erreurs), {'prix_unique_kwh'})

    def test_patch_partiel_valide_sur_l_etat_fusionne(self):
        # La base porte déjà un taux ; retirer la source par PATCH est refusé.
        base = TariffSettings(taux_imposition_pct='31',
                              fiscalite_source=SOURCE)
        valide, erreurs = erreurs_de({'fiscalite_source': ''}, instance=base)
        self.assertFalse(valide)
        self.assertIn('fiscalite_source', erreurs)
        # Et un PATCH qui ne touche que la source reste valide.
        valide, erreurs = erreurs_de({'fiscalite_source': 'CGI art. 19'},
                                     instance=base)
        self.assertTrue(valide, erreurs)

    def test_saisie_complete_et_sourcee_passe(self):
        valide, erreurs = erreurs_de({
            'tou_heures': HEURES,
            'tou_tarifs': {'creuse': '0.9', 'pleine': '1.1', 'pointe': '1.5'},
            'tou_source': SOURCE, 'tou_date_source': '2026-05-08',
            'mecanisme_compensation': 'net_metering_report',
            'report_periode': 12,
            'structure_tarif': 'deux_postes', 'poste_haut': '1.4',
            'poste_bas': '0.8', 'pays_tarif': 'MA',
            'taxes': [{'libelle': 'TVA', 'taux_pct': '20',
                       'assiette': 'total', 'source': 'CGI art. 99'}],
            'charge_minimale_mad_jour': '1.5',
            'indexation_tarif_pct_an': '0', 'indexation_source': SOURCE,
            'taux_imposition_pct': '31', 'amortissement_mode': 'lineaire',
            'amortissement_duree_ans': 10, 'fiscalite_source': 'CGI'})
        self.assertTrue(valide, erreurs)

    def test_la_societe_vierge_reste_valide(self):
        valide, erreurs = erreurs_de({})
        self.assertTrue(valide, erreurs)


if __name__ == '__main__':
    unittest.main()
