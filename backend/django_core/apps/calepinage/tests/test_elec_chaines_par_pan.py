"""CAL124 — deux azimuts ne partagent JAMAIS une chaîne.

Le cas de référence est une toiture à TROIS pans sur un onduleur à DEUX
entrées MPPT : c'est là que la faute se produit (mélanger deux orientations en
série) et c'est là que le message doit NOMMER l'onduleur et le pan en trop.

Aucune base de données : le service prend un document de conception et deux
blocs de fiche technique (la forme rendue par
``apps.stock.selectors.specs_for_produit``), pas des enregistrements.

Les valeurs de fiche ci-dessous sont des VALEURS D'ESSAI, pas un produit du
catalogue : elles ne servent qu'à fermer la fenêtre de tension.

Run :
    python manage.py test apps.calepinage.tests.test_elec_chaines_par_pan -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import (
    concevoir_par_pan,
    _groupes_electriques,
    _pans_poses,
)
from apps.calepinage.services.electrique import temperatures_site

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}


def _layout(*comptes):
    """Un document v2 minimal : un pan par compte, azimuts TOUS différents."""
    azimuts = (180.0, 90.0, 270.0, 135.0)
    return {'version': 2, 'zones': [
        {'id': 'z%d' % rang, 'label': 'PAN-%d' % rang,
         'geometry': {'count': compte, 'azimuthDeg': azimuts[rang - 1],
                      'tiltDeg': 15.0}}
        for rang, compte in enumerate(comptes, start=1)]}


def _temperatures():
    return temperatures_site(
        saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0})


def _concevoir(layout, onduleur=None):
    return concevoir_par_pan(
        layout, module_specs=MODULE, onduleur_specs=onduleur or ONDULEUR,
        temperatures=_temperatures(), module_designation='Module d essai',
        onduleur_designation='Onduleur d essai 10 kW')


class LectureDuDocumentTest(SimpleTestCase):
    """Le compte POSÉ prime, l'orientation n'est jamais devinée."""

    def test_le_compte_pose_prime_sur_le_compte_souhaite(self):
        layout = {'zones': [{'label': 'A', 'neededPanels': 30,
                             'geometry': {'count': 12}}]}

        pans = _pans_poses(layout)

        self.assertEqual([(p.label, p.modules) for p in pans], [('A', 12)])

    def test_pan_sans_module_est_ignore(self):
        # ACAL61 — ``neededPanels`` n'est JAMAIS un compte posé (primitive
        # ``ventes.pans_du_document``) : B, non pavé, n'est pas chaîné non
        # plus ; seul C, posé, l'est.
        pans = _pans_poses({'zones': [{'label': 'A', 'geometry': {'count': 0}},
                                      {'label': 'B', 'neededPanels': 4},
                                      {'label': 'C', 'geometry': {'count': 4}}]})

        self.assertEqual([p.label for p in pans], ['C'])

    def test_orientation_absente_reste_inconnue(self):
        pans = _pans_poses({'zones': [{'label': 'A',
                                      'geometry': {'count': 4}}]})

        self.assertIsNone(pans[0].azimut_deg)
        self.assertIsNone(pans[0].source_orientation)

    def test_un_groupe_par_pan(self):
        groupes = _groupes_electriques(_layout(12, 8, 6))

        self.assertEqual([g.nb_modules for g in groupes], [12, 8, 6])


class TroisPansTest(SimpleTestCase):
    """Le cas à 3 pans sur 2 entrées MPPT."""

    def test_aucune_chaine_ne_melange_deux_pans(self):
        conception = _concevoir(_layout(12, 8, 6))

        self.assertTrue(conception.chaines)
        # Chaque chaîne porte UN pan, et la somme des chaînes d'un pan ne
        # dépasse jamais les modules posés sur ce pan.
        poses = {pan.label: pan.modules for pan in conception.pans}
        chaines_par_pan = {}
        for chaine in conception.chaines:
            self.assertIn(chaine.pan, poses)
            chaines_par_pan.setdefault(chaine.pan, 0)
            chaines_par_pan[chaine.pan] += chaine.nb_modules
        for pan, en_chaine in chaines_par_pan.items():
            self.assertLessEqual(en_chaine, poses[pan])

    def test_depassement_du_nombre_de_mppt_nomme_onduleur_et_pan(self):
        conception = _concevoir(_layout(12, 8, 6))

        message = '\n'.join(conception.alertes)
        self.assertIn("Onduleur d essai 10 kW", message)
        self.assertIn('PAN-3', message)
        self.assertFalse(conception.partage_mppt)
        self.assertIn('NON autorisé', conception.regle_mppt)

    def test_polystring_publie_autorise_le_partage_et_le_dit(self):
        onduleur = dict(ONDULEUR, chaines_max_par_mppt=2)

        conception = _concevoir(_layout(12, 8, 6), onduleur=onduleur)

        self.assertTrue(conception.partage_mppt)
        self.assertIn('AUTORISÉ', conception.regle_mppt)
        self.assertIn("Onduleur d essai 10 kW", conception.regle_mppt)
        # Aucun message de dépassement : la fiche autorise le partage.
        self.assertNotIn("n'a que 2 entrée(s) MPPT",
                         '\n'.join(conception.alertes))

    def test_deux_pans_pour_deux_entrees_ne_declenche_aucun_arbitrage(self):
        conception = _concevoir(_layout(12, 8))

        self.assertFalse(conception.partage_mppt)
        self.assertIn('un pan par entrée MPPT', conception.regle_mppt)
        self.assertNotIn("n'a que", '\n'.join(conception.alertes))

    def test_la_temperature_de_cal123_est_bien_celle_passee_au_noyau(self):
        conception = _concevoir(_layout(12, 8))

        self.assertEqual(conception.entree.temp_froid_c, -5.0)
        self.assertEqual(conception.entree.temp_chaud_c, 70.0)
        self.assertEqual(conception.temperatures.source, 'saisie')


class FicheIncompleteTest(SimpleTestCase):
    """Fiche muette ⇒ SILENCE nommé, jamais un verdict par défaut."""

    def test_module_sans_voc_ne_produit_aucun_verdict(self):
        incomplet = {cle: valeur for cle, valeur in MODULE.items()
                     if cle != 'voc_v'}

        conception = concevoir_par_pan(
            _layout(12), module_specs=incomplet, onduleur_specs=ONDULEUR,
            temperatures=_temperatures())

        self.assertTrue(conception.fiche_incomplete)
        self.assertEqual(conception.chaines, ())
        self.assertEqual(conception.bloquants, ())
        self.assertIn('module : tension à vide (Voc)', conception.manquantes)

    def test_onduleur_sans_plage_mppt_ne_produit_aucun_verdict(self):
        incomplet = {cle: valeur for cle, valeur in ONDULEUR.items()
                     if cle != 'mppt_v_max'}

        conception = concevoir_par_pan(
            _layout(12), module_specs=MODULE, onduleur_specs=incomplet,
            temperatures=_temperatures())

        self.assertTrue(conception.fiche_incomplete)
        self.assertIn('onduleur : haut de plage MPPT', conception.manquantes)

    def test_aucun_module_pose_le_dit_sans_bloquer(self):
        conception = _concevoir({'zones': []})

        self.assertFalse(conception.fiche_incomplete)
        self.assertEqual(conception.bloquants, ())
        self.assertIn("rien à chaîner", '\n'.join(conception.alertes))


class PansDeMemeOrientationTest(SimpleTestCase):
    """ACAL650 — deux pans de même orientation (tolérance SAISIE, orientation
    connue) forment UN groupe électrique : une chaîne peut les traverser."""

    #: Plage MPPT haute : 7 modules n'atteignent pas le bas de plage à chaud,
    #: 14 oui — la chaîne optimale est de 14 modules.
    ONDULEUR_14 = dict(ONDULEUR, mppt_v_min=400.0)

    def _deux_pans(self):
        layout = _layout(7, 7)
        layout['zones'][1]['geometry']['azimuthDeg'] = 180.0
        return layout

    def _concevoir(self, layout, tolerance):
        options = ({} if tolerance is None
                   else {'tolerance_orientation_deg': tolerance})
        return concevoir_par_pan(
            layout, module_specs=MODULE, onduleur_specs=self.ONDULEUR_14,
            temperatures=_temperatures(), module_designation='Module d essai',
            onduleur_designation='Onduleur d essai 10 kW', **options)

    def test_tolerance_saisie_aucun_module_hors_chaine(self):
        from apps.calepinage.services.chaines import (
            affectation, bloc_electrique, verdict_affectation)

        conception = self._concevoir(self._deux_pans(), 1.0)
        bloc, _a = bloc_electrique(conception)
        self.assertEqual(bloc['chainage']['reste'], 0)
        # UNE chaîne de 14, dans la fenêtre : plus de repli « chaîne de 7 ».
        self.assertEqual([c.nb_modules for c in conception.chaines], [14])
        self.assertFalse(any('aucune découpe' in a for a in conception.alertes))
        table = affectation(conception)
        self.assertEqual(len(table), 14)
        self.assertTrue(all(ligne['chaine'] is not None for ligne in table))
        # Chaque module garde SON pan d'origine.
        self.assertEqual([ligne['pan'] for ligne in table],
                         ['PAN-1'] * 7 + ['PAN-2'] * 7)
        # Une chaîne manuelle sur les deux pans fusionnés n'est pas refusée.
        imposee = [dict(ligne, chaine=1) for ligne in table]
        self.assertFalse(any('traverse les pans' in refus for refus in
                             verdict_affectation(conception, imposee)))

    def test_sans_tolerance_comportement_d_aujourd_hui(self):
        conception = self._concevoir(self._deux_pans(), None)
        self.assertEqual(len(_groupes_electriques(self._deux_pans())), 2)
        # Aujourd'hui : deux chaînes de 7 HORS fenêtre, repli annoncé.
        self.assertEqual([c.nb_modules for c in conception.chaines], [7, 7])
        self.assertTrue(any('aucune découpe' in a for a in conception.alertes))

    def test_le_reglage_se_lit_seulement_source(self):
        from apps.calepinage.services.chaines import (
            tolerance_orientation_societe)

        def reglage(saisie):
            return {'electrique_societe': {
                'tolerance_orientation_pans_deg': saisie}}

        self.assertEqual(tolerance_orientation_societe(reglage(
            {'valeur': 2, 'source': 'societe'})), 2.0)
        self.assertIsNone(tolerance_orientation_societe(reglage(
            {'valeur': 2})))
        self.assertIsNone(tolerance_orientation_societe({}))

    def test_orientations_differentes_jamais_fusionnees(self):
        groupes = _groupes_electriques(_layout(7, 7), tolerance_deg=1.0)
        self.assertEqual(len(groupes), 2)


class MpptNonIndependantsTest(SimpleTestCase):
    """ACAL661 — des entrées MPPT NON indépendantes selon la fiche forment UNE
    entrée logique ; drapeau vrai ou absent ⇒ résultat d'avant."""

    def _mppt_par_pan(self, conception):
        return {c.pan: c.mppt for c in conception.chaines}

    def test_drapeau_faux_une_seule_entree_logique_et_le_dit(self):
        conception = _concevoir(_layout(12, 8),
                                dict(ONDULEUR, mppt_independants=False))
        self.assertEqual(self._mppt_par_pan(conception),
                         {'PAN-1': 1, 'PAN-2': 1})
        self.assertIn("les 2 entrées de Onduleur d essai 10 kW ne sont pas "
                      "indépendantes selon sa fiche : une seule orientation "
                      "par suiveur", conception.regle_mppt)

    def test_drapeau_vrai_ou_absent_resultat_d_avant(self):
        avant = _concevoir(_layout(12, 8))
        for drapeau in (True, None):
            with self.subTest(drapeau=drapeau):
                onduleur = dict(ONDULEUR)
                if drapeau is not None:
                    onduleur['mppt_independants'] = drapeau
                apres = _concevoir(_layout(12, 8), onduleur)
                self.assertEqual(self._mppt_par_pan(apres),
                                 {'PAN-1': 1, 'PAN-2': 2})
                self.assertEqual(apres.regle_mppt, avant.regle_mppt)


class _CalepinageEssai:
    """Le strict minimum lu par ``evaluation_electrique`` — aucun ORM."""

    pk = 11
    statut = 'brouillon'
    company = None

    def __init__(self, *comptes):
        self.roof_layout = _layout(*comptes)
        self.resultat = {'entree_electrique': {
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0}}


def _materiel_essai(**onduleur):
    return {
        'module': MODULE, 'onduleur': dict(ONDULEUR, **onduleur),
        'optimiseur': None,
        'designations': {'module': 'Module d essai',
                         'onduleur': 'Onduleur d essai 10 kW',
                         'optimiseur': ''},
        'absents': (),
    }


class OnduleursMinimumTest(SimpleTestCase):
    """ACAL632 — le plus petit nombre d'onduleurs qui tient le champ."""

    def _suggestion(self, *comptes):
        from apps.calepinage.services.electrique import evaluation_electrique

        return evaluation_electrique(
            _CalepinageEssai(*comptes), materiel=_materiel_essai(
                isc_max_mppt_a=45.0))['onduleurs_suggeres']

    def test_trois_pans_sur_deux_entrees_demandent_deux_onduleurs(self):
        suggestion = self._suggestion(12, 8, 6)

        self.assertEqual(suggestion['nombre'], 2)
        self.assertIn('2 onduleurs sont nécessaires : 3 pans pour 2 entrées '
                      'par onduleur', suggestion['motif'])
        for pan in ('PAN-1', 'PAN-2', 'PAN-3'):
            self.assertIn(pan, suggestion['motif'])
        self.assertIn("n'a que 2 entrée(s) MPPT",
                      '\n'.join(suggestion['signaux_avec_1']))

    def test_deux_pans_tiennent_sur_un_seul_onduleur_sans_motif(self):
        suggestion = self._suggestion(12, 8)

        self.assertEqual(suggestion['nombre'], 1)
        self.assertEqual(suggestion['motif'], '')
        self.assertEqual(suggestion['signaux_avec_1'], [])


class Deye20kTrenteCinqModulesTest(SimpleTestCase):
    """Incident prod 26/11/2026 : 35 × 715 Wc, Deye 20 kW triphasé, 2 entrées
    MPPT, Isc 54,0 A publié par entrée, 800 V."""

    MODULE_715 = {
        'vmp_v': 41.0, 'voc_v': 49.1, 'isc_a': 22.3, 'imp_a': 17.44,
        'pmax_wc': 715.0, 'temp_coeff_voc_pct_c': -0.25,
        'temp_coeff_pmax_pct_c': -0.35,
    }
    DEYE_20K = {
        'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 750.0,
        'v_max_abs': 800.0, 'i_max_mppt_a': 36.0, 'ac_kw': 20.0,
        'phases': 3, 'isc_max_mppt_a': 54.0,
    }

    def _materiel(self):
        return dict(_materiel_essai(), module=self.MODULE_715,
                    onduleur=self.DEYE_20K)

    def _evaluer(self, *chaines):
        """``chaines`` = ``(longueur, entrée MPPT)`` dans l'ordre des modules."""
        lignes, rang = [], 0
        for numero, (longueur, mppt) in enumerate(chaines, start=1):
            for _ in range(longueur):
                rang += 1
                lignes.append({'module': 'z1#%d' % rang, 'chaine': numero,
                               'mppt': mppt, 'onduleur': 1})
        from apps.calepinage.services.electrique import evaluation_electrique

        return evaluation_electrique(
            _CalepinageEssai(35), entree={'affectation_manuelle': lignes},
            materiel=self._materiel())

    def test_automatique_douze_douze_sur_l_entree_1_onze_sur_la_2(self):
        conception = concevoir_par_pan(
            _layout(35), module_specs=self.MODULE_715,
            onduleur_specs=self.DEYE_20K, temperatures=_temperatures())
        self.assertEqual([(c.nb_modules, c.mppt) for c in conception.chaines],
                         [(12, 1), (12, 1), (11, 2)])
        self.assertEqual(conception.bloquants, ())
        fenetre = conception.resultat.fenetre
        self.assertTrue(all(fenetre.admet(c.nb_modules)
                            for c in conception.chaines))
        # Deux longueurs sur le pan : aucun nombre unique n'est publié.
        from apps.calepinage.services.chaines import bloc_electrique
        from apps.calepinage.services.electrique import (
            _longueur_chaine_retenue)

        retenue = _longueur_chaine_retenue(conception)
        self.assertIsNone(retenue['longueur'])
        self.assertEqual(retenue['par_pan'], {'PAN-1': 12})
        bloc, _avertissements = bloc_electrique(conception)
        self.assertIsNone(bloc['chainage']['modules_par_chaine'])
        self.assertEqual(bloc['chainage']['reste'], 0)
        self.assertEqual([ligne['chaine'] for ligne in bloc['affectation']],
                         [1] * 12 + [2] * 12 + [3] * 11)

    def test_manuel_douze_douze_onze_accepte(self):
        verdict = self._evaluer((12, 1), (12, 1), (11, 2))
        self.assertEqual(verdict['bloquants'], [])

    def test_l_entree_mppt_saisie_est_celle_qui_est_jugee(self):
        # 13 + 13 sur l'entrée 1 et 9 sur la 2 : un câblage qui n'est PAS
        # l'automatique ; puis la même chaîne 3 posée à la main sur l'entrée 1.
        self.assertEqual(self._evaluer((13, 1), (13, 1), (9, 2))['bloquants'],
                         [])
        bloquants = self._evaluer((13, 1), (13, 1), (9, 1))['bloquants']
        self.assertTrue(any('entrée MPPT 1' in b and 'CH1, CH2, CH3' in b
                            and '66,9 A' in b for b in bloquants), bloquants)

    def test_douze_et_onze_en_parallele_sur_l_entree_1_refuses(self):
        bloquants = self._evaluer((12, 1), (12, 1), (11, 1))['bloquants']
        self.assertIn(
            "Entrée MPPT 1 : chaînes 1, 2, 3 en parallèle de 12 et 11 modules "
            "— des chaînes en parallèle sur une même entrée doivent avoir la "
            "même longueur (des entrées différentes peuvent différer).",
            bloquants)
        self.assertFalse(any('en parallèle de' in b for b in self._evaluer(
            (12, 1), (12, 1), (11, 2))['bloquants']))

    def test_chaine_de_vingt_refusee_avec_la_vraie_borne(self):
        verdict = self._evaluer((20, 1), (15, 2))
        refus = [b for b in verdict['bloquants'] if b.startswith('Chaîne 1 ')]
        self.assertEqual(len(refus), 1, verdict['bloquants'])
        self.assertIn('20 modules, maximum 15', refus[0])
        self.assertIn("(Voc 1055,7 V à -5 °C) dépasse la tension maximale "
                      "800,0 V de l'onduleur", refus[0])
        self.assertIn('(15 modules au plus)', refus[0])
        self.assertFalse(any(b.startswith('Chaîne 2 ')
                             for b in verdict['bloquants']))

    def test_le_schema_juge_et_dessine_le_cablage_manuel(self):
        """Les portails du schéma (``sld.bloquants_du_cablage`` : planche,
        document « schéma électrique », export DXF) jugent le câblage EFFECTIF,
        et le document dessine ses chaînes : ici l'automatique est FORCÉ à 7
        (5 × 7 → 66,9 A sur l'entrée 1), le manuel 12 + 12 | 11 tient."""
        from apps.calepinage.services.sld import (
            _chaines_de_l_affectation, bloquants_du_cablage)

        conception = concevoir_par_pan(
            _layout(35), module_specs=self.MODULE_715,
            onduleur_specs=self.DEYE_20K, temperatures=_temperatures(),
            longueur_forcee=7)
        self.assertTrue(any('66,9 A' in b for b in bloquants_du_cablage(
            conception, {})))
        lignes, rang = [], 0
        for numero, (longueur, mppt) in enumerate(((12, 1), (12, 1), (11, 2)),
                                                  start=1):
            for _ in range(longueur):
                rang += 1
                lignes.append({'module': 'z1#%d' % rang, 'chaine': numero,
                               'mppt': mppt, 'onduleur': 1})
        donnees = {'affectation_manuelle': lignes}
        self.assertEqual(list(bloquants_du_cablage(conception, donnees)), [])
        self.assertEqual(
            [(c['nb_panneaux'], c['entree'])
             for c in _chaines_de_l_affectation(conception, donnees)],
            [(12, 1), (12, 1), (11, 2)])

    def test_les_codes_du_cablage_sont_ceux_du_noyau(self):
        import inspect
        import re

        from core.electrique import chaines as noyau

        from apps.calepinage.services.tensions_chaines import CODES_DU_CABLAGE

        source = (inspect.getsource(noyau._verdicts_tension)
                  + inspect.getsource(noyau._verdicts_courant))
        self.assertEqual(set(re.findall(r'"(CH_[A-Z_]+)"', source)),
                         set(CODES_DU_CABLAGE))
