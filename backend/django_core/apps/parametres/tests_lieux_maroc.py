"""VREF-LIEUX (fondateur 08/09/2026, cas « Sidi Hashass ») — lieux-dits GeoNames.

Verrouille : un douar absent du gazetier des villes et inconnu de Nominatim
est placé depuis son NOM (graphie du lead à une faute près, préfixe « douar »
toléré) ; les homonymes ne sont jamais tranchés en silence (la ville de
contexte départage, une contradiction refuse) ; un morceau d'adresse exige
une ville de contexte ; une VILLE du gazetier ou un mot générique ne sont
jamais rendus comme lieu-dit. Tests purs (aucune base, aucun réseau).
"""
from django.test import SimpleTestCase

from apps.parametres.lieux_maroc import position_lieu_dit

SIDI_HASHAS = (35.00611, -2.37346, 'Douar Sidi Hashas')


class LieuxDitsTests(SimpleTestCase):
    def test_nom_exact_faute_de_frappe_et_prefixe_douar(self):
        self.assertEqual(position_lieu_dit('Douar Sidi Hashas'), SIDI_HASHAS)
        # La graphie tapée sur le lead (deux « s » finaux) et le préfixe.
        self.assertEqual(position_lieu_dit('sidi hashass'), SIDI_HASHAS)
        self.assertEqual(position_lieu_dit('douar sidi hashass'), SIDI_HASHAS)

    def test_homonymes_sans_contexte_restent_ambigus(self):
        # « Oulad Ali » existe des dizaines de fois : jamais un choix silencieux.
        self.assertIsNone(position_lieu_dit('oulad ali'))
        self.assertIsNone(position_lieu_dit('douar lhamri'))

    def test_la_ville_de_contexte_departage_ou_contredit(self):
        self.assertEqual(
            position_lieu_dit('douar lhamri', contexte_ville='Madagh'),
            (34.98459, -2.38806, 'Douar Lhamri'))
        self.assertEqual(
            position_lieu_dit('sidi hashass', contexte_ville='Berkane'), SIDI_HASHAS)
        # Un lieu-dit unique mais à des centaines de km de la ville tapée :
        # contradiction → refus, l'écran carte tranche.
        self.assertIsNone(position_lieu_dit('sidi hashass', contexte_ville='Casablanca'))

    def test_un_morceau_d_adresse_exige_une_ville_de_contexte(self):
        self.assertIsNone(position_lieu_dit('douar sidi hashass km 3 bis'))
        # Une ville du gazetier citée DANS le texte corrobore.
        self.assertEqual(
            position_lieu_dit('douar sidi hashass route de madagh'), SIDI_HASHAS)

    def test_une_ville_ou_un_mot_generique_ne_sont_pas_des_lieux_dits(self):
        for texte in ('Casablanca', 'Rabat', 'Madagh', 'centre ville', 'sidi', 'xyz'):
            self.assertIsNone(position_lieu_dit(texte), texte)
