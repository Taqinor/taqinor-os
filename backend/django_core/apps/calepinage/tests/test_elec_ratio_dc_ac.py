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


def _conception(modules, ac_kw, designation='Onduleur d essai', role='', **fiche):
    layout = {'version': 2, 'zones': [
        {'label': 'PAN-A',
         'geometry': {'count': modules, 'azimuthDeg': 180.0,
                      'tiltDeg': 15.0}}]}
    return concevoir_par_pan(
        layout, module_specs=MODULE, onduleur_specs=_onduleur(ac_kw, **fiche),
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        onduleur_designation=designation, onduleur_role=role)


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
        self.assertIn("dans la capacité publiée de l'onduleur (fiche constructeur : 40 kWc au plus)",
                      verdict['detail'])
        self.assertEqual(controle['etat'], 'ok')
        self.assertNotIn("seuil d'alerte", '\n'.join(messages))
        self.assertGreater(bloc['valeur'], 1.35)  # la borne de ratio l'aurait refusé
        # Capacité publiée SOUS la puissance raccordée : au-delà, à régler.
        petite = int(bloc['puissance_dc_kwc']) - 1
        bloc, messages, verdict, controle = self._trois(_conception(
            48, 20.0, designation=hybride['designation'], dc_max_kwc=float(petite)))
        self.assertIs(verdict['conforme'], False)
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertIn("au-delà de la capacité publiée de l'onduleur (fiche constructeur : %d kWc au plus)"
                      % petite, verdict['detail'])

    def test_onduleur_reseau_et_fiche_sans_capacite_inchanges(self):
        from apps.calepinage.services.ratio_devis import MOTIF_HYBRIDE_SANS_CAPACITE

        for fiche, dit in (({'designation': 'Onduleur réseau 20 kW', 'dc_max_kwc': 40.0}, False),
                           ({'designation': 'Onduleur hybride 20 kW'}, True)):
            from apps.calepinage.services.pret_a_envoyer import _ratio_dc_ac

            bloc, messages, verdict, _c = self._trois(_conception(48, 20.0, **fiche))
            self.assertEqual(bloc['borne_source'], SOURCE_BORNE_DEVIS)
            self.assertIs(verdict['conforme'], False)  # 1,70 > 1,35
            # D-HYB-1 (lead 1742) — l'hybride sans capacité publiée : la phrase dit que la fiche
            # ne publie rien et nomme le champ ; jamais pour un onduleur réseau.
            controle = _ratio_dc_ac(bloc, verdict=verdict)  # comme ``controles_electriques``
            for texte in (verdict['detail'], controle['valeur_texte'], ' | '.join(messages)):
                self.assertEqual(MOTIF_HYBRIDE_SANS_CAPACITE in texte, dit, texte)

    def test_meme_verdict_que_le_moteur_de_devis(self):
        """D-HYB-1 (lead 1742) — même module, même compte, même hybride : le calepinage et le
        moteur de devis C&I (``moteur_ci.onduleurs._capacite_kwc``, LA règle du noyau) disent
        tous deux oui ou tous deux non, la capacité publiée au-dessus, au-dessous ou absente."""
        from apps.ventes.moteur_ci.onduleurs import _capacite_kwc
        from core.electrique.onduleurs import bornes_dc_ac

        haute = bornes_dc_ac().borne_usuelle.valeur
        for dc_max, nom, role in ((40.0, 'Onduleur hybride Deye 20 kW', ''), (30.0, 'Onduleur hybride Deye 20 kW', ''),
                                  (None, 'Onduleur hybride Deye 20 kW', ''),
                                  (40.0, 'Deye SUN-20K-SG01HP3', 'onduleur_hybride')):  # D-HYB-1 : le rôle
            fiche = {} if dc_max is None else {'dc_max_kwc': dc_max}
            bloc, _m, verdict, controle = self._trois(_conception(48, 20.0, designation=nom, role=role, **fiche))
            devis = _capacite_kwc({'kw_ac': 20.0, 'dc_max_kwc': dc_max, '_fiche_fait_foi': True},
                                  haute)[0] >= bloc['puissance_dc_kwc'] - 1e-9
            self.assertEqual(verdict['conforme'], devis, dc_max)
            self.assertEqual(bloc['dans_bornes'], devis, dc_max)
            self.assertEqual(controle['etat'], 'ok' if devis else 'a_regler', dc_max)

    def test_sous_le_seuil_bas_la_borne_franchie_est_dite_aux_deux_ecrans(self):
        """Rejeu T3-VAGUEC2 — « 0,99 pour 1,35 au plus (règle du devis) » était
        « à régler » sans raison dite. La règle du devis n'a PAS de borne basse
        (``borne_dc_ac_du_moteur_devis`` : un plafond) : sans seuil bas réglé,
        0,99 est bon ; avec le seuil bas de la société (profil de départ :
        1,00, PV*SOL), la phrase NOMME ce seuil franchi."""
        from apps.calepinage.services.electrique import _verdicts_electriques
        from apps.calepinage.services.pret_a_envoyer import _ratio_dc_ac

        conception = _conception(14, 10.0)  # 14 × 710 Wc = 9,94 kWc sur 10 kW → 0,99
        verdict = next(v for v in _verdicts_electriques(conception) if v['code'] == 'ratio_dc_ac')
        self.assertIs(verdict['conforme'], True)
        self.assertEqual(verdict['detail'], '0,99 pour 1,35 au plus (règle du devis)')
        seuil = 1.0
        reglages = {'seuil_bas_dc_ac': {'valeur': seuil, 'source': 'PV*SOL, Configuration check'}}
        bloc, _messages = _bloc_ratio_dc_ac(conception, reglages=reglages)
        verdict = next(v for v in _verdicts_electriques(conception, reglages=reglages)
                       if v['code'] == 'ratio_dc_ac')
        controle = _ratio_dc_ac(bloc, verdict=verdict)
        self.assertIs(bloc['dans_bornes'], False)
        self.assertIs(verdict['conforme'], False)
        self.assertEqual(verdict['detail'], "0,99 : sous le seuil bas de 1,00 réglé par la société "
                                            "(la règle du devis n'a pas de borne basse, 1,35 au plus)")
        self.assertEqual(controle['etat'], 'a_regler')
        self.assertEqual(controle['valeur_texte'], verdict['detail'])

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


class PoseSurUnAutreOnduleurTest(SimpleTestCase):
    """D-HYB-1 (lead 1742) — « Prêt à envoyer ? » juge une pose dont l'onduleur n'est pas
    dans les lignes de la conception (``selectors_conception.verdicts_pour_le_calepinage`` :
    ligne sans désignation) : la porte du moteur lit le NOM du produit pour savoir s'il
    est hybride ; avant, un hybride publiant sa capacité était jugé à la borne 1,35."""

    def test_hybride_sans_designation_juge_a_sa_fiche(self):
        from unittest import mock

        from apps.ventes.conception import porte_calepinage as porte

        design = {'ratio_dc_ac': 1.72, 'chaines': [], 'materiel': {'onduleur': {'designation': None}}}
        lignes = [{'produit': 7, 'designation': None, 'quantite': 1}]
        fiche = {'ac_kw': 20.0, 'dc_max_kwc': 40.0}
        with mock.patch.object(porte, '_fiche_onduleur', return_value=fiche), mock.patch.object(
                porte, '_nom_produit', return_value='Deye hybride 20 kW'), mock.patch.object(
                porte, '_reglages_electriques', return_value={}), mock.patch.object(
                porte, '_role_onduleur', return_value=''):
            verdicts = porte.verdicts_electriques(object(), design, lignes, 34.32)
        self.assertIs(verdicts['ratio_dc_ac']['conforme'], True)
        self.assertEqual(verdicts['ratio_dc_ac']['borne_source'], SOURCE_BORNE_CAPACITE)
        self.assertIn('fiche constructeur : 40 kWc au plus', verdicts['ratio_dc_ac']['detail'])
        self.assertIs(verdicts['capacite_hybride']['conforme'], True)


class HybrideParRoleEtFicheTest(SimpleTestCase):
    """D-HYB-1 (fondateur 24/11/2026 : « un produit se reconnaît à son rôle et à sa fiche
    avant son nom ») — l'hybride est reconnu par son RÔLE, puis par le port batterie de sa
    FICHE, et par le mot de sa désignation en dernier seulement. Ici, aucun nom ne dit
    « hybride » : avant, ces onduleurs étaient jugés à la borne 1,35."""

    NOM = 'Deye SUN-20K-SG01HP3-EU-AM2'  # référence constructeur, sans le mot « hybride »

    def test_les_trois_rangs(self):
        from core.electrique.onduleurs import est_onduleur_hybride

        self.assertTrue(est_onduleur_hybride(self.NOM, role='onduleur_hybride'))
        self.assertFalse(est_onduleur_hybride('Onduleur hybride 20 kW', role='onduleur_reseau'))
        self.assertTrue(est_onduleur_hybride(self.NOM, ports_batterie_kw=(None, 25.0)))
        self.assertFalse(est_onduleur_hybride(self.NOM, role='', ports_batterie_kw=(None, 0)))
        self.assertTrue(est_onduleur_hybride('Onduleur hybride 20 kW', role='batterie'))  # le nom, en dernier

    def test_role_et_fiche_jugent_avant_le_nom_aux_trois_endroits(self):
        for jeu in ({'role': 'onduleur_hybride'}, {'bat_max_charge_kw': 25.0}):
            bloc, messages, verdict, controle = UnSeulVerdictTest._trois(
                self, _conception(48, 20.0, designation=self.NOM, dc_max_kwc=40.0, **jeu))
            self.assertEqual(bloc['borne_source'], SOURCE_BORNE_CAPACITE, jeu)
            self.assertIs(verdict['conforme'], True, jeu)
            self.assertEqual(controle['etat'], 'ok', jeu)
            self.assertNotIn("seuil d'alerte", ' | '.join(messages), jeu)
        # Un rôle d'onduleur RÉSEAU déclaré l'emporte sur le mot du nom.
        bloc, _m, verdict, _c = UnSeulVerdictTest._trois(self, _conception(
            48, 20.0, designation='Onduleur hybride 20 kW', role='onduleur_reseau', dc_max_kwc=40.0))
        self.assertEqual((bloc['borne_source'], verdict['conforme']), (SOURCE_BORNE_DEVIS, False))

    def test_role_lu_par_le_selecteur_du_stock(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services.ratio_devis import role_de_l_onduleur

        # Famille « onduleur » : ambiguë (``FAMILLE_VERS_ROLE``), elle ne dit rien ⇒ fiche puis nom.
        produit = SimpleNamespace(role_devis='', categorie=SimpleNamespace(type_equipement='onduleur'))
        with mock.patch('apps.stock.selectors.get_produit_scoped', return_value=produit) as lu:
            self.assertEqual(role_de_l_onduleur('societe', 7), '')
        lu.assert_called_once_with('societe', 7)
        with mock.patch('apps.stock.selectors.get_produit_scoped',
                        return_value=SimpleNamespace(role_devis='onduleur_hybride', categorie=None)):
            self.assertEqual(role_de_l_onduleur('societe', 7), 'onduleur_hybride')
        self.assertEqual(role_de_l_onduleur(None, 7), '')

    def test_pose_sur_un_autre_onduleur_par_son_role(self):
        from unittest import mock

        from apps.ventes.conception import porte_calepinage as porte

        design = {'ratio_dc_ac': 1.72, 'chaines': [], 'materiel': {'onduleur': {'designation': self.NOM}}}
        lignes = [{'produit': 7, 'designation': self.NOM, 'quantite': 1}]
        fiche = {'ac_kw': 20.0, 'dc_max_kwc': 40.0}
        with mock.patch.object(porte, '_fiche_onduleur', return_value=fiche), mock.patch.object(
                porte, '_role_onduleur', return_value='onduleur_hybride'), mock.patch.object(
                porte, '_reglages_electriques', return_value={}):
            verdicts = porte.verdicts_electriques(object(), design, lignes, 34.32)
        self.assertIs(verdicts['ratio_dc_ac']['conforme'], True)
        self.assertEqual(verdicts['ratio_dc_ac']['borne_source'], SOURCE_BORNE_CAPACITE)
        self.assertIs(verdicts['capacite_hybride']['conforme'], True)


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
