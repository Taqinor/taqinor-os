"""CALX241 — l'élévation de tension au point de raccordement.

CE QUE CE FICHIER GARDE
-----------------------
1. **Le chiffre existe même sans limite.** Sans ``limite_elevation_pct``
   saisie, l'élévation est CALCULÉE et PUBLIÉE ; c'est le VERDICT qui vaut
   ``non_verifiable`` (publié ``omis`` par le contrat CALX205), avec son
   motif. Aucune limite marocaine n'est supposée — ni 3 %, ni 10 %.
2. **Une limite sans source est REFUSÉE en nommant le champ.** Un seuil sans
   provenance n'est pas opposable (D-CALX 7).
3. **La somme des contributions par tronçon égale l'élévation publiée.**
   C'est l'arme du calcul : une décomposition qui ne se raccorde pas à son
   total est une décomposition décorative.
4. **Une entrée manquante OMET tout le calcul en nommant le champ.** Une
   somme partielle sous-estimerait l'élévation en ayant l'air d'un résultat.

Aucun seuil n'est écrit dans ce module de test : les limites comparées sont
celles que les cas de test SAISISSENT, avec leur source.

Aucune base de données, aucun réseau : des dicts et le noyau pur.

Run :
    python manage.py test apps.calepinage.tests.test_calx241_elevation_tension
"""
from django.test import SimpleTestCase

from apps.calepinage.services.raccordement import (
    CODE_ELEVATION, RaccordementInvalide, elevation_de_tension,
)
from core.electrique.cables import RHO_CUIVRE_20C, chute_tension_v

#: Deux tronçons de la liaison AC, longueurs et sections SAISIES avec leur
#: origine (discipline `Longueur` de `services/cables.py`).
TRONCONS = (
    {'repere': 'W2 — onduleur → coffret AC', 'longueur_m': 18.0,
     'section_mm2': 6.0, 'origine_longueur': 'plan'},
    {'repere': 'W3 — coffret AC → point de livraison',
     'longueur_m': {'valeur_m': 32.0, 'origine': 'saisie',
                    'detail': 'métré du cheminement'},
     'section_mm2': 10.0},
)

#: L'injection : courant, tension nominale et régime, tous SAISIS.
INJECTION = {'courant_a': 14.4, 'tension_nominale_v': 400.0, 'phases': 3}


def _avec(**ajouts):
    saisie = dict(INJECTION)
    saisie.update(ajouts)
    return saisie


class SansLimiteTest(SimpleTestCase):
    """Le chiffre est publié, le verdict est omis — et il dit pourquoi."""

    def test_l_elevation_est_publiee_sans_limite_saisie(self):
        bloc = elevation_de_tension(TRONCONS, INJECTION)

        self.assertIsNotNone(bloc['elevation_pct'])
        self.assertGreater(bloc['elevation_pct'], 0.0)
        self.assertIsNone(bloc['limite_pct'])

    def test_le_verdict_est_non_verifiable_et_nomme_le_champ(self):
        verdict = elevation_de_tension(TRONCONS, INJECTION)['verdict']

        self.assertEqual(verdict.code, CODE_ELEVATION)
        self.assertEqual(verdict.statut, 'non_verifiable')
        self.assertIn('limite_elevation_pct', verdict.libelle)
        self.assertIsNone(verdict.borne)

    def test_aucun_bareme_marocain_n_est_suppose(self):
        verdict = elevation_de_tension(TRONCONS, INJECTION)['verdict']

        self.assertIn('marocain', verdict.libelle)
        self.assertIsNone(verdict.borne)

    def test_la_marge_est_nulle_pas_zero(self):
        # `0` se lirait « limite atteinte » : sans limite, il n'y a AUCUNE
        # marge à calculer.
        self.assertIsNone(elevation_de_tension(TRONCONS, INJECTION)
                          ['marge_pct'])


class LimiteSaisieTest(SimpleTestCase):
    """Respectée, franchie — et jamais enregistrée sans sa source."""

    def test_limite_respectee(self):
        bloc = elevation_de_tension(
            TRONCONS, _avec(limite_elevation_pct=3.0,
                            source_limite='contrat de raccordement du site'))

        self.assertEqual(bloc['verdict'].statut, 'ok')
        self.assertEqual(bloc['verdict'].borne, 3.0)
        self.assertAlmostEqual(bloc['marge_pct'],
                               3.0 - bloc['elevation_pct'], places=3)
        self.assertIn('contrat de raccordement', bloc['verdict'].source)

    def test_limite_franchie(self):
        eleve = elevation_de_tension(TRONCONS, INJECTION)['elevation_pct']
        limite = round(eleve / 2.0, 4)
        bloc = elevation_de_tension(
            TRONCONS, _avec(limite_elevation_pct=limite,
                            source_limite='contrat de raccordement du site'))

        self.assertEqual(bloc['verdict'].statut, 'bloquant')
        self.assertEqual(bloc['verdict'].valeur, eleve)
        self.assertLess(bloc['marge_pct'], 0.0)

    def test_limite_sans_source_refusee_en_nommant_le_champ(self):
        with self.assertRaises(RaccordementInvalide) as refus:
            elevation_de_tension(TRONCONS, _avec(limite_elevation_pct=3.0))

        self.assertEqual(refus.exception.champ, 'raccordement.source_limite')
        self.assertIn('source', str(refus.exception))


class DecompositionTest(SimpleTestCase):
    """L'arme : la somme des tronçons EST l'élévation publiée."""

    def test_la_somme_des_troncons_egale_le_total(self):
        bloc = elevation_de_tension(TRONCONS, INJECTION)

        self.assertEqual(len(bloc['par_troncon']), len(TRONCONS))
        self.assertAlmostEqual(
            sum(ligne['elevation_pct'] for ligne in bloc['par_troncon']),
            bloc['elevation_pct'], places=3)

    def test_chaque_troncon_publie_l_origine_de_sa_longueur(self):
        for ligne in elevation_de_tension(TRONCONS, INJECTION)['par_troncon']:
            self.assertTrue(ligne['origine_longueur'],
                            '%s : longueur sans origine.' % ligne['repere'])

    def test_le_volt_est_celui_du_noyau(self):
        # La remontée d'un tronçon se calcule avec la MÊME formule que la
        # chute : u = k·ρ·L·I/S (core/electrique/cables.py).
        premier = elevation_de_tension(TRONCONS, INJECTION)['par_troncon'][0]
        attendu = chute_tension_v(18.0, 14.4, 6.0, premier['coefficient'],
                                  RHO_CUIVRE_20C)

        self.assertAlmostEqual(premier['elevation_v'], attendu, places=3)

    def test_un_troncon_non_parcouru_ne_compte_pas(self):
        antenne = dict(TRONCONS[0])
        antenne['parcouru'] = False
        bloc = elevation_de_tension(TRONCONS + (antenne,), INJECTION)

        self.assertEqual(len(bloc['par_troncon']), len(TRONCONS))


class OmissionsTest(SimpleTestCase):
    """Une entrée manquante OMET le calcul en nommant le champ fautif."""

    def test_sans_section_le_calcul_est_omis_en_nommant_le_champ(self):
        ampute = ({'repere': 'W2', 'longueur_m': 18.0},) + TRONCONS[1:]
        bloc = elevation_de_tension(ampute, INJECTION)

        self.assertIsNone(bloc['elevation_pct'])
        self.assertTrue(any('section_mm2' in motif
                            for motif in bloc['omissions']))
        self.assertTrue(any('W2' in motif for motif in bloc['omissions']))

    def test_sans_tension_nominale_le_pourcentage_est_omis(self):
        bloc = elevation_de_tension(
            TRONCONS, {'courant_a': 14.4, 'phases': 3})

        self.assertIsNone(bloc['elevation_pct'])
        self.assertTrue(any('tension_nominale_v' in motif
                            for motif in bloc['omissions']))

    def test_sans_regime_saisi_aucun_coefficient_n_est_suppose(self):
        bloc = elevation_de_tension(
            TRONCONS, {'courant_a': 14.4, 'tension_nominale_v': 400.0})

        self.assertIsNone(bloc['elevation_pct'])
        self.assertTrue(any('phases' in motif for motif in bloc['omissions']))

    def test_sans_troncon_le_motif_le_dit(self):
        bloc = elevation_de_tension((), INJECTION)

        self.assertIsNone(bloc['elevation_pct'])
        self.assertTrue(any('cheminement' in motif
                            for motif in bloc['omissions']))
