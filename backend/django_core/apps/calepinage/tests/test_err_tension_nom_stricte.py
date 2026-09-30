"""ERR-QAH-DIFF-POMPAGE-TENSION-NOM-2200W — la tension lue dans le NOM d'un
produit pompe/variateur suit UNE règle stricte, jumelle de ``solar.js
tensionOf`` : le nombre ISOLÉ 220/380 immédiatement suivi de « V ».

Avant : « 220 » n'importe où ET un « v » n'importe où ⇒ « Variateur VEICHI
SVF3 2.2kW 2200W » lu 220 V côté calepinage, inconnu côté écran — sélection
de variateur divergente.

Fonction PURE : aucune base.

Run :
    python manage.py test apps.calepinage.tests.test_err_tension_nom_stricte
"""
import unittest

from apps.calepinage.services.pompage import selection_variateur, tension_produit


class TensionNomStricteTest(unittest.TestCase):

    def test_puissance_en_watts_n_est_pas_une_tension(self):
        self.assertIsNone(tension_produit(
            {'nom': 'Variateur VEICHI SVF3 2.2kW 2200W', 'tension_v': None}))
        self.assertIsNone(tension_produit({'nom': 'Pompe 1220V'}))
        self.assertIsNone(tension_produit({'nom': 'Pompe 3800W'}))

    def test_tension_explicite_lue(self):
        for nom, attendu in (('VARIATEUR VEICHI SI22 2.2KW 220V', 220),
                             ('Pompe 380 V', 380), ('Pompe 220Vac', 220),
                             ('Moteur 380 volts', 380),
                             ('Pompe 220V/380V', 220)):
            self.assertEqual(tension_produit({'nom': nom}), attendu, nom)

    def test_champ_tension_v_prioritaire(self):
        self.assertEqual(tension_produit({'nom': 'X 220V', 'tension_v': 380}),
                         380)

    def test_variateur_2200w_sans_tension_n_est_plus_retenu_en_mono(self):
        """Cas du corpus : alim mono, fiche sans ``tension_v`` dont le nom
        porte une puissance en W. L'écran ne retient AUCUN variateur (tension
        inconnue) ; le calepinage le retenait comme un 220 V. Désormais,
        même verdict des deux côtés."""
        v = {'id': 1, 'nom': 'Variateur VEICHI SVF3 2.2kW 2200W',
             'pompe_kw': 2.2, 'tension_v': None, 'prix_vente': 3000}
        resultat = selection_variateur([v], kw=2.2, alim='mono')
        self.assertIsNone(resultat['variateur'])
        # Le même variateur, tension renseignée : retenu.
        v220 = dict(v, tension_v=220)
        self.assertIs(
            selection_variateur([v220], kw=2.2, alim='mono')['variateur'], v220)
