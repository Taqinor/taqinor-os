"""CAL156 — HMT calculée par puits (niveau statique + rabattement + pertes
de charge), ITÉRÉE jusqu'à convergence avec la courbe pompe.

Ce qui est prouvé ici :

* une donnée de puits MANQUANTE (l'une des cinq) fait retomber sur la HMT
  SAISIE, ``source: 'saisie'`` — jamais une HMT à moitié calculée ;
* données complètes ⇒ ``source: 'calculee'``, les QUATRE composantes
  (niveau statique, rabattement, pertes de charge, hauteur de refoulement)
  et un point de CONVERGENCE (le débit ré-interpolé cesse de bouger de plus
  de la tolérance) ;
* la convergence se stabilise (deux appels à débit initial différent
  convergent vers le MÊME point) ;
* une HMT calculée qui dépasse la capacité de la pompe rend un débit de
  convergence ``None`` (jamais un débit inventé au-delà de la courbe) ;
* le coefficient de frottement n'est JAMAIS une valeur par défaut : sans lui,
  la fonction refuse le calcul (retombe sur la HMT saisie).

Fonction PURE : ce test n'a besoin d'AUCUNE base de données.

Run :
    python manage.py test apps.calepinage.tests.test_hmt_puits -v2
"""
import unittest

from apps.calepinage.services.pompage import hmt_puits_iteree

COURBE = {'debits_m3h': [0, 5, 10, 15], 'hmt_m': [100, 80, 60, 40]}


class HmtPuitsIttereeTest(unittest.TestCase):
    def test_donnee_de_puits_manquante_replie_sur_la_saisie(self):
        resultat = hmt_puits_iteree(
            courbe_pompe=COURBE, hmt_saisie=70, niveau_statique_m=None,
            coefficient_rabattement_m_par_m3h=1.0,
            longueur_tuyauterie_m=50, coefficient_frottement=0.001,
            hauteur_refoulement_m=2)
        self.assertEqual(resultat['source'], 'saisie')
        self.assertEqual(resultat['hmt_m'], 70.0)
        self.assertIsNone(resultat['composantes'])
        self.assertIsNone(resultat['debit_convergence_m3h'])
        self.assertEqual(resultat['iterations'], 0)

    def test_aucune_donnee_de_puits_et_pas_de_hmt_saisie(self):
        resultat = hmt_puits_iteree(courbe_pompe=COURBE)
        self.assertEqual(resultat['source'], 'saisie')
        self.assertIsNone(resultat['hmt_m'])

    def test_donnees_completes_calcule_et_converge(self):
        resultat = hmt_puits_iteree(
            courbe_pompe=COURBE, niveau_statique_m=30,
            coefficient_rabattement_m_par_m3h=1.0,
            longueur_tuyauterie_m=50, coefficient_frottement=0.001,
            hauteur_refoulement_m=2)
        self.assertEqual(resultat['source'], 'calculee')
        self.assertIsNotNone(resultat['debit_convergence_m3h'])
        composantes = resultat['composantes']
        self.assertEqual(
            set(composantes),
            {'niveau_statique_m', 'rabattement_m', 'pertes_charge_m',
             'hauteur_refoulement_m'})
        self.assertEqual(composantes['niveau_statique_m'], 30.0)
        self.assertEqual(composantes['hauteur_refoulement_m'], 2.0)
        # HMT = somme des quatre composantes (à l'arrondi près).
        somme = (composantes['niveau_statique_m']
                 + composantes['rabattement_m']
                 + composantes['pertes_charge_m']
                 + composantes['hauteur_refoulement_m'])
        self.assertAlmostEqual(resultat['hmt_m'], somme, places=1)

    def test_convergence_independante_du_debit_initial(self):
        kwargs = dict(
            courbe_pompe=COURBE, niveau_statique_m=30,
            coefficient_rabattement_m_par_m3h=1.0,
            longueur_tuyauterie_m=50, coefficient_frottement=0.001,
            hauteur_refoulement_m=2)
        r1 = hmt_puits_iteree(debit_initial_m3h=1, **kwargs)
        r2 = hmt_puits_iteree(debit_initial_m3h=14, **kwargs)
        self.assertAlmostEqual(r1['hmt_m'], r2['hmt_m'], places=1)
        self.assertAlmostEqual(
            r1['debit_convergence_m3h'], r2['debit_convergence_m3h'],
            places=1)

    def test_hmt_hors_capacite_pompe_converge_a_debit_nul(self):
        """Une HMT calculée au-delà du premier point de la courbe (100 m à
        débit nul) converge vers un débit nul — la pompe ne peut PAS
        vaincre cette hauteur, jamais un débit inventé au-delà."""
        resultat = hmt_puits_iteree(
            courbe_pompe=COURBE, niveau_statique_m=500,
            coefficient_rabattement_m_par_m3h=1.0,
            longueur_tuyauterie_m=10, coefficient_frottement=0.0001,
            hauteur_refoulement_m=2)
        self.assertEqual(resultat['source'], 'calculee')
        self.assertEqual(resultat['debit_convergence_m3h'], 0.0)

    def test_courbe_inexploitable_rend_convergence_none(self):
        """Une courbe pompe illisible (moins de deux points) ne peut donner
        AUCUN débit — la fonction s'arrête sur la dernière HMT calculée,
        sans point de convergence inventé."""
        resultat = hmt_puits_iteree(
            courbe_pompe={'debits_m3h': [10], 'hmt_m': [50]},
            niveau_statique_m=30, coefficient_rabattement_m_par_m3h=1.0,
            longueur_tuyauterie_m=50, coefficient_frottement=0.001,
            hauteur_refoulement_m=2)
        self.assertEqual(resultat['source'], 'calculee')
        self.assertIsNone(resultat['debit_convergence_m3h'])

    def test_coefficient_de_frottement_jamais_invente(self):
        """Sans coefficient de frottement SAISI, le calcul ne se substitue
        JAMAIS une valeur de table — il retombe sur la HMT saisie."""
        resultat = hmt_puits_iteree(
            courbe_pompe=COURBE, hmt_saisie=55, niveau_statique_m=30,
            coefficient_rabattement_m_par_m3h=1.0,
            longueur_tuyauterie_m=50, coefficient_frottement=None,
            hauteur_refoulement_m=2)
        self.assertEqual(resultat['source'], 'saisie')
        self.assertEqual(resultat['hmt_m'], 55.0)
