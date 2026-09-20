"""CAL148 — import CSV d'une courbe de charge horaire : lu, ou refusé nommé.

Tests PURS. Les séries d'essai sont fabriquées ICI et assumées comme telles :
ce sont des relevés de COMPTEUR (donnée client), pas une grandeur physique
qu'on pourrait « sourcer » — ce que ces tests vérifient est la LECTURE du
fichier, jamais un niveau de consommation.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.consommation import (
    ImportCourbeInvalide, apercu_courbe_csv,
)

HEURES = 8760
QUARTS = 35040


def csv_horaire(separateur=';', decimale=',', entete=True, valeur=1.5,
                lignes=HEURES):
    texte = f'{valeur:.2f}'.replace('.', decimale)
    corps = '\n'.join(f'{heure}{separateur}{texte}' for heure in range(lignes))
    if not entete:
        return corps
    return f'horodatage{separateur}consommation\n{corps}'


class TroisFormatsDeSeparateurTest(unittest.TestCase):
    """« Tests sur trois formats de séparateurs » — point-virgule, tab, virgule."""

    def test_point_virgule_et_decimale_virgule(self):
        apercu = apercu_courbe_csv(csv_horaire(';', ','),
                                   colonne='consommation')
        self.assertEqual(apercu['separateur'], ';')
        self.assertEqual(apercu['decimale'], ',')
        self.assertEqual(len(apercu['valeurs']), HEURES)
        self.assertEqual(apercu['total_annuel_kwh'], round(1.5 * HEURES, 1))

    def test_tabulation(self):
        apercu = apercu_courbe_csv(csv_horaire('\t', ','),
                                   colonne='consommation')
        self.assertEqual(apercu['separateur'], '\t')
        self.assertEqual(apercu['decimale'], ',')
        self.assertEqual(apercu['total_annuel_kwh'], round(1.5 * HEURES, 1))

    def test_virgule_separatrice_impose_la_decimale_point(self):
        apercu = apercu_courbe_csv(csv_horaire(',', '.'),
                                   colonne='consommation')
        self.assertEqual(apercu['separateur'], ',')
        self.assertEqual(apercu['decimale'], '.')
        self.assertEqual(apercu['total_annuel_kwh'], round(1.5 * HEURES, 1))


class PasDeQuinzeMinutesTest(unittest.TestCase):

    def test_kwh_par_pas_sadditionnent_a_lheure(self):
        apercu = apercu_courbe_csv(
            csv_horaire(';', ',', valeur=0.25, lignes=QUARTS),
            colonne='consommation', unite='kwh')
        self.assertEqual(apercu['pas_minutes'], 15)
        self.assertEqual(apercu['points_lus'], QUARTS)
        self.assertEqual(len(apercu['valeurs']), HEURES)
        self.assertEqual(apercu['valeurs'][0], 1.0)     # 4 × 0,25 kWh

    def test_kw_instantanes_se_moyennent(self):
        apercu = apercu_courbe_csv(
            csv_horaire(';', ',', valeur=2.0, lignes=QUARTS),
            colonne='consommation', unite='kw')
        self.assertEqual(apercu['valeurs'][0], 2.0)     # kW moyen × 1 h
        self.assertEqual(apercu['total_annuel_kwh'], round(2.0 * HEURES, 1))

    def test_unite_inconnue_refusee(self):
        with self.assertRaises(ImportCourbeInvalide) as capture:
            apercu_courbe_csv(csv_horaire(), colonne='consommation',
                              unite='joules')
        self.assertEqual(capture.exception.champ, 'unite')


class RefusNommesTest(unittest.TestCase):
    """Jamais un zéro silencieux : la ligne ET la colonne sont nommées."""

    def test_ligne_illisible_nomme_la_ligne_et_la_colonne(self):
        lignes = csv_horaire().splitlines()
        lignes[43] = '42;abc'                      # 44ᵉ ligne du fichier
        with self.assertRaises(ImportCourbeInvalide) as capture:
            apercu_courbe_csv('\n'.join(lignes), colonne='consommation')
        self.assertEqual(capture.exception.ligne, 44)
        self.assertEqual(capture.exception.champ, 'consommation')
        self.assertIn('Ligne 44', capture.exception.motif)
        self.assertIn('consommation', capture.exception.motif)

    def test_cellule_vide_refusee_et_non_transformee_en_zero(self):
        lignes = csv_horaire().splitlines()
        lignes[10] = '9;'
        with self.assertRaises(ImportCourbeInvalide) as capture:
            apercu_courbe_csv('\n'.join(lignes), colonne='consommation')
        self.assertEqual(capture.exception.ligne, 11)
        self.assertIn('zéro', capture.exception.motif)

    def test_valeur_negative_refusee(self):
        lignes = csv_horaire().splitlines()
        lignes[5] = '4;-3,2'
        with self.assertRaises(ImportCourbeInvalide) as capture:
            apercu_courbe_csv('\n'.join(lignes), colonne='consommation')
        self.assertEqual(capture.exception.ligne, 6)

    def test_colonne_absente_liste_les_colonnes_presentes(self):
        with self.assertRaises(ImportCourbeInvalide) as capture:
            apercu_courbe_csv(csv_horaire(), colonne='kwh')
        self.assertEqual(capture.exception.champ, 'colonne')
        self.assertIn('consommation', capture.exception.motif)

    def test_plusieurs_colonnes_chiffrees_sans_choix_refuse(self):
        entete = 'index;conso_hp;conso_hc'
        corps = '\n'.join(f'{h};1,0;0,5' for h in range(HEURES))
        with self.assertRaises(ImportCourbeInvalide) as capture:
            apercu_courbe_csv(f'{entete}\n{corps}')
        self.assertEqual(capture.exception.champ, 'colonne')
        self.assertIn('conso_hp', capture.exception.motif)

    def test_nombre_de_mesures_inattendu_refuse_sans_completer(self):
        with self.assertRaises(ImportCourbeInvalide) as capture:
            apercu_courbe_csv(csv_horaire(lignes=120),
                              colonne='consommation')
        self.assertEqual(capture.exception.champ, 'fichier')
        self.assertIn('120 mesures', capture.exception.motif)
        self.assertIn('8760', capture.exception.motif)

    def test_fichier_vide_refuse(self):
        with self.assertRaises(ImportCourbeInvalide) as capture:
            apercu_courbe_csv('   \n\n')
        self.assertEqual(capture.exception.champ, 'fichier')


class SansEnteteTest(unittest.TestCase):

    def test_colonne_par_rang_quand_le_fichier_na_pas_dentete(self):
        apercu = apercu_courbe_csv(csv_horaire(entete=False), colonne=1)
        self.assertEqual(apercu['colonne'], 'colonne 1')
        self.assertEqual(len(apercu['valeurs']), HEURES)

    def test_nom_de_colonne_refuse_sur_un_fichier_sans_entete(self):
        with self.assertRaises(ImportCourbeInvalide) as capture:
            apercu_courbe_csv(csv_horaire(entete=False),
                              colonne='consommation')
        self.assertEqual(capture.exception.champ, 'colonne')
        self.assertIn('rang', capture.exception.motif)


class ApercuAvantEcritureTest(unittest.TestCase):

    def test_lapercu_publie_ce_quil_a_compris_et_necrit_rien(self):
        apercu = apercu_courbe_csv(csv_horaire(), colonne='consommation',
                                   origine='relevé compteur 2025')
        self.assertEqual(apercu['origine'], 'relevé compteur 2025')
        self.assertEqual(apercu['unite'], 'kwh')
        self.assertEqual(apercu['pas_minutes'], 60)
        self.assertTrue(any('rien' in avis.lower()
                            for avis in apercu['avertissements']))

    def test_origine_absente_est_dite_non_renseignee(self):
        apercu = apercu_courbe_csv(csv_horaire(), colonne='consommation')
        self.assertEqual(apercu['origine'], 'non renseignée')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
