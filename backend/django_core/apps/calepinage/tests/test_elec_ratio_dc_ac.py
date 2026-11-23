"""CAL127 — le ratio DC/AC est publié AVEC la règle qui le juge.

Trois choses sont vérifiées, et la troisième est la plus importante :

1. la borne appliquée et SA SOURCE voyagent avec le ratio (marché > société >
   noyau) — aucune borne n'est écrite dans l'app, toutes sont lues ;
2. hors bornes, l'avertissement CITE la borne et sa source ;
3. la perte d'écrêtage n'est JAMAIS forfaitaire : sans série horaire (CAL135)
   elle vaut ``null`` et le résultat dit pourquoi.

Run :
    python manage.py test apps.calepinage.tests.test_elec_ratio_dc_ac -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import (
    SOURCE_BORNE_CAPACITE, SOURCE_BORNE_DEVIS, SOURCE_BORNE_MARCHE,
    SOURCE_BORNE_SOCIETE, _bloc_ratio_dc_ac, _bornes_ratio,
    ecretage_depuis_serie, temperatures_site,
)
from core.electrique.onduleurs import BORNE_USUELLE_DC_AC, SEUIL_ALERTE_DC_AC

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}


def _onduleur(ac_kw, **fiche):
    return {'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
            'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': ac_kw,
            'phases': 3, **fiche}


def _conception(modules, ac_kw, designation='Onduleur d essai', **fiche):
    layout = {'version': 2, 'zones': [
        {'label': 'PAN-A',
         'geometry': {'count': modules, 'azimuthDeg': 180.0,
                      'tiltDeg': 15.0}}]}
    return concevoir_par_pan(
        layout, module_specs=MODULE, onduleur_specs=_onduleur(ac_kw, **fiche),
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        onduleur_designation=designation)


class BornesLuesTest(SimpleTestCase):
    """Aucune borne n'est écrite dans l'app : elles sont toutes lues."""

    def test_defaut_lu_sur_la_regle_du_devis(self):
        # ACAL1954 (D-ACAL-91) — la borne du MOTEUR DE DEVIS, lue par ventes.
        from apps.ventes.selectors_calepinage import borne_dc_ac_du_moteur_devis

        borne, alerte, source, detail = _bornes_ratio()

        self.assertEqual(borne, borne_dc_ac_du_moteur_devis())
        self.assertEqual(borne, BORNE_USUELLE_DC_AC)
        self.assertEqual(alerte, SEUIL_ALERTE_DC_AC)
        self.assertEqual(source, SOURCE_BORNE_DEVIS)
        # ACAL1540 — la source dite en phrase, jamais un nom de module du code.
        self.assertIn('1,35', detail)
        self.assertNotIn('core.electrique', detail)

    def test_parametre_societe_prime_sur_le_noyau(self):
        borne, _, source, _ = _bornes_ratio(
            parametres_societe={'ratio_dc_ac_max': 1.2})

        self.assertEqual(borne, 1.2)
        self.assertEqual(source, SOURCE_BORNE_SOCIETE)

    def test_exigence_de_marche_prime_sur_la_societe(self):
        borne, _, source, reference = _bornes_ratio(
            exigence_marche={'ratio_dc_ac_max': 1.0,
                             'reference': 'CPS lot 3 art. 12'},
            parametres_societe={'ratio_dc_ac_max': 1.2})

        self.assertEqual(borne, 1.0)
        self.assertEqual(source, SOURCE_BORNE_MARCHE)
        self.assertEqual(reference, 'CPS lot 3 art. 12')


class RatioPublieTest(SimpleTestCase):
    """Le ratio publié porte sa borne, sa source et ses puissances."""

    def test_dans_les_bornes_aucun_avertissement(self):
        # 12 × 710 Wc = 8,52 kWc sur 10 kW AC → 0,85.
        bloc, messages = _bloc_ratio_dc_ac(_conception(12, 10.0))

        self.assertAlmostEqual(bloc['valeur'], 0.852, places=3)
        self.assertEqual(bloc['borne'], BORNE_USUELLE_DC_AC)
        self.assertEqual(bloc['borne_source'], SOURCE_BORNE_DEVIS)
        # ACAL1954 — la règle du devis JUGE (D-ACAL-91 remplace ACAL1538).
        self.assertIs(bloc['dans_bornes'], True)
        self.assertEqual(messages, ())

    def test_hors_bornes_l_avertissement_cite_la_borne_et_sa_source(self):
        # 24 × 710 Wc = 17,04 kWc sur 10 kW AC → 1,70.
        # ACAL1538 — seule une borne RÉGLÉE juge (ici la société).
        bloc, messages = _bloc_ratio_dc_ac(
            _conception(24, 10.0),
            parametres_societe={'ratio_dc_ac_max': 1.35,
                                'ratio_dc_ac_alerte': 1.5})

        self.assertFalse(bloc['dans_bornes'])
        texte = '\n'.join(messages)
        self.assertIn('1,35', texte)
        self.assertIn(SOURCE_BORNE_SOCIETE, texte)
        self.assertIn("seuil d'alerte", texte)

    def test_la_borne_societe_change_le_verdict_et_le_dit(self):
        bloc, messages = _bloc_ratio_dc_ac(
            _conception(12, 10.0),
            parametres_societe={'ratio_dc_ac_max': 0.80,
                                'reference': 'décision société 2026'})

        self.assertFalse(bloc['dans_bornes'])
        self.assertEqual(bloc['borne_source'], SOURCE_BORNE_SOCIETE)
        self.assertIn('décision société 2026', '\n'.join(messages))

    def test_sans_onduleur_evalue_le_ratio_est_null_jamais_zero(self):
        bloc, messages = _bloc_ratio_dc_ac(_conception(0, 10.0))

        self.assertIsNone(bloc['valeur'])
        self.assertIsNone(bloc['dans_bornes'])
        self.assertEqual(messages, ())


class UnSeulVerdictTest(SimpleTestCase):
    """ACAL1538 / ACAL1954 — le bloc, le verdict CAL244 et « Prêt à envoyer ? »
    disent le MÊME statut, jugé par la règle du devis sans fourchette société
    (D-ACAL-91) : au-dessus ⇒ « à régler », jamais « Bon »."""

    def _trois(self, conception, **bornes):
        from apps.calepinage.services.electrique import _verdicts_electriques
        from apps.calepinage.services.pret_a_envoyer import _ratio_dc_ac

        bloc, messages = _bloc_ratio_dc_ac(conception, **bornes)
        verdict = next(v for v in _verdicts_electriques(
            conception, bornes_ratio=_bornes_ratio(**bornes))
            if v['code'] == 'ratio_dc_ac')
        return bloc, messages, verdict, _ratio_dc_ac(bloc)

    def test_sans_fourchette_la_regle_du_devis_juge_partout(self):
        # 60 × 710 Wc = 42,6 kWc sur 10 kW réseau → 4,26 : à régler aux trois endroits.
        bloc, messages, verdict, controle = self._trois(_conception(60, 10.0))
        self.assertIs(bloc['dans_bornes'], False)
        self.assertIs(verdict['conforme'], False)
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertIn('4,26 pour 1,35 au plus (règle du devis)', verdict['detail'])
        self.assertEqual(controle['valeur_texte'], verdict['detail'])
        self.assertIn('1,35', '\n'.join(messages))
        bloc, messages, verdict, controle = self._trois(_conception(10, 10.0))  # 0,71
        self.assertIs(verdict['conforme'], True)
        self.assertEqual(controle['etat'], 'ok')
        self.assertEqual(messages, ())

    def test_hybride_juge_a_sa_capacite_publiee(self):
        # ACAL1954 (D-HYB-1) — hybride 20 kW publiant 40 kWc : 48 × 715 Wc ≈ 34,3 kWc.
        hybride = {'designation': 'Onduleur hybride Deye 20 kW', 'dc_max_kwc': 40.0}
        bloc, messages, verdict, controle = self._trois(_conception(48, 20.0, **hybride))
        self.assertIs(verdict['conforme'], True)
        self.assertEqual(bloc['borne_source'], SOURCE_BORNE_CAPACITE)
        self.assertIn("dans la capacité publiée de l'onduleur (40 kWc)", verdict['detail'])
        self.assertEqual(controle['etat'], 'ok')
        self.assertNotIn("seuil d'alerte", '\n'.join(messages))
        self.assertGreater(bloc['valeur'], 1.35)  # la borne de ratio l'aurait refusé
        # Capacité publiée SOUS la puissance raccordée : au-delà, à régler.
        petite = int(bloc['puissance_dc_kwc']) - 1
        bloc, messages, verdict, controle = self._trois(_conception(
            48, 20.0, designation=hybride['designation'], dc_max_kwc=float(petite)))
        self.assertIs(verdict['conforme'], False)
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertIn("au-delà de la capacité publiée de l'onduleur (%d kWc)" % petite, verdict['detail'])

    def test_onduleur_reseau_et_fiche_sans_capacite_inchanges(self):
        for fiche in ({'designation': 'Onduleur réseau 20 kW', 'dc_max_kwc': 40.0},
                      {'designation': 'Onduleur hybride 20 kW'}):
            bloc, _m, verdict, _c = self._trois(_conception(48, 20.0, **fiche))
            self.assertEqual(bloc['borne_source'], SOURCE_BORNE_DEVIS)
            self.assertIs(verdict['conforme'], False)  # 1,70 > 1,35

    def test_avec_fourchette_le_meme_statut_partout(self):
        bornes = {'parametres_societe': {'ratio_dc_ac_max': 1.2}}
        bloc, messages, verdict, controle = self._trois(
            _conception(24, 10.0), **bornes)
        self.assertFalse(bloc['dans_bornes'])
        self.assertIs(verdict['conforme'], False)
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual('\n'.join(messages).count('1,20'), 1)
        bloc, _m, verdict, controle = self._trois(
            _conception(12, 10.0), **bornes)
        self.assertTrue(bloc['dans_bornes'])
        self.assertIs(verdict['conforme'], True)
        self.assertEqual(controle['etat'], 'ok')


class EcretageTest(SimpleTestCase):
    """La perte d'écrêtage se calcule heure par heure, ou pas du tout."""

    def test_sans_serie_horaire_null_et_la_raison(self):
        bloc, _ = _bloc_ratio_dc_ac(_conception(24, 10.0))

        self.assertIsNone(bloc['ecretage_pct'])
        self.assertIn('CAL135', bloc['ecretage_methode'])
        # Ce qui EST dérivable des puissances est publié, lui.
        self.assertAlmostEqual(bloc['dc_au_dessus_de_l_ac_kwc'], 7.04,
                               places=2)

    def test_avec_serie_la_perte_est_calculee(self):
        # 3 heures : 12 kW, 8 kW, 4 kW sur 10 kW AC → 2 kW perdus sur 24.
        perte = ecretage_depuis_serie([12.0, 8.0, 4.0], 10.0)

        self.assertAlmostEqual(perte, 100.0 * 2.0 / 24.0, places=3)

    def test_serie_sous_la_capacite_ac_ne_perd_rien(self):
        self.assertEqual(ecretage_depuis_serie([4.0, 6.0], 10.0), 0.0)

    def test_puissance_ac_inconnue_ne_produit_aucun_chiffre(self):
        self.assertIsNone(ecretage_depuis_serie([12.0, 8.0], 0.0))
