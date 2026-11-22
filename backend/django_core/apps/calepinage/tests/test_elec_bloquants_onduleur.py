"""CAL128 — les contraintes onduleur BLOQUANTES remontent jusqu'au plan.

Trois cas, et la frontière entre les deux premiers est la leçon de l'incident
DEV-202608-0016 :

* **bloquant** — l'Isc cumulé d'une entrée dépasse le courant de
  court-circuit PUBLIÉ par la fiche : le montage sort de ce que le
  constructeur garantit, le dossier ne se publie pas ;
* **alerte** — l'Imp cumulé dépasse le courant d'entrée admissible : ça
  s'installe, ça écrête, ça produit moins. Ce n'est pas un blocage ;
* **fiche muette** — aucun verdict. Ni faux vert, ni faux rouge : le silence,
  avec la liste de ce qui manque.

Run :
    python manage.py test apps.calepinage.tests.test_elec_bloquants_onduleur -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    PublicationBloquee, evaluation_electrique, garde_publication,
)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 1, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 20.0, 'phases': 3,
}


class _Calepinage:
    """Le strict minimum lu par le service — aucun ORM, aucune base."""

    pk = 7
    statut = 'brouillon'

    def __init__(self, modules):
        self.roof_layout = {'version': 2, 'zones': [
            {'label': 'PAN-A', 'geometry': {
                'count': modules, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}}]}
        self.resultat = {'entree_electrique': {
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0}}
        self.company = None


def _materiel(**onduleur):
    return {
        'module': MODULE, 'onduleur': dict(ONDULEUR, **onduleur),
        'optimiseur': None,
        'designations': {'module': 'Module d essai',
                         'onduleur': 'Onduleur d essai', 'optimiseur': ''},
        'absents': (),
    }


class VerdictBloquantTest(SimpleTestCase):
    """Isc publié dépassé : bloquant, et le message NOMME tout."""

    def test_isc_cumule_au_dessus_du_publie_bloque(self):
        # 24 modules sur UNE entrée MPPT → 2 chaînes en parallèle,
        # Isc cumulé 36,8 A face aux 26 A publiés par la fiche.
        evaluation = evaluation_electrique(
            _Calepinage(24), materiel=_materiel(isc_max_mppt_a=26.0))

        self.assertEqual(evaluation['verdict'], 'bloquant')
        self.assertFalse(evaluation['publiable'])
        message = evaluation['bloquants'][0]
        self.assertIn('Isc', message)
        self.assertIn('MPPT 1', message)
        self.assertIn('PAN-A', message)
        self.assertIn('CH1, CH2', message)
        self.assertIn('Onduleur d essai', message)

    def test_la_publication_est_refusee_et_le_refus_porte_les_bloquants(self):
        calepinage = _Calepinage(24)

        with self.assertRaises(PublicationBloquee) as capture:
            garde_publication_materiel(calepinage,
                                       _materiel(isc_max_mppt_a=26.0))

        self.assertTrue(capture.exception.bloquants)
        self.assertIn('Isc', capture.exception.bloquants[0])
        # Le statut n'est PAS touché : la garde refuse, elle ne rétrograde pas.
        self.assertEqual(calepinage.statut, 'brouillon')


def garde_publication_materiel(calepinage, materiel):
    """``garde_publication`` avec matériel injecté (aucune base de données).

    La garde de production lit le matériel par le sélecteur du stock ; ici on
    lui donne les mêmes blocs de fiche, pour tester la RÈGLE sans base.
    """
    evaluation = evaluation_electrique(calepinage, materiel=materiel)
    if evaluation['publiable']:
        return evaluation
    raise PublicationBloquee(
        'Publication refusée', bloquants=(evaluation['bloquants']
                                          or evaluation['manquantes']))


class VerdictAlerteTest(SimpleTestCase):
    """Imp dépassé : ça écrête, ça ne bloque pas."""

    def test_imp_cumule_alerte_mais_ne_bloque_pas(self):
        evaluation = evaluation_electrique(
            _Calepinage(24),
            materiel=_materiel(i_max_mppt_a=20.0, isc_max_mppt_a=45.0))

        self.assertEqual(evaluation['verdict'], 'alerte')
        self.assertTrue(evaluation['publiable'])
        self.assertEqual(evaluation['bloquants'], [])
        self.assertIn('ÉCRÊTAGE', '\n'.join(evaluation['alertes']))

    def test_champ_conforme(self):
        evaluation = evaluation_electrique(
            _Calepinage(12), materiel=_materiel(isc_max_mppt_a=45.0))

        self.assertEqual(evaluation['verdict'], 'conforme')
        self.assertTrue(evaluation['publiable'])
        self.assertEqual(evaluation['alertes'], [])


class FicheMuetteTest(SimpleTestCase):
    """Fiche incomplète ⇒ SILENCE, jamais un faux vert."""

    def test_onduleur_sans_tension_maximale_ne_rend_aucun_verdict(self):
        materiel = _materiel()
        materiel['onduleur'] = {cle: valeur
                                for cle, valeur in materiel['onduleur'].items()
                                if cle != 'v_max_abs'}

        evaluation = evaluation_electrique(_Calepinage(24),
                                           materiel=materiel)

        self.assertEqual(evaluation['verdict'], 'indetermine')
        self.assertFalse(evaluation['publiable'])
        self.assertEqual(evaluation['bloquants'], [])
        self.assertEqual(evaluation['alertes'], [])
        self.assertIn('onduleur : tension DC maximale absolue',
                      evaluation['manquantes'])

    def test_materiel_non_designe_ne_rend_aucun_verdict(self):
        vide = {'module': {}, 'onduleur': {}, 'optimiseur': None,
                'designations': {'module': '', 'onduleur': '',
                                 'optimiseur': ''},
                'absents': ('module PV non désigné',
                            'onduleur non désigné')}

        evaluation = evaluation_electrique(_Calepinage(24), materiel=vide)

        self.assertEqual(evaluation['verdict'], 'indetermine')
        self.assertIn('module PV non désigné', evaluation['manquantes'])

    def test_une_publication_indeterminee_passe_en_le_disant(self):
        # Aucun matériel injecté : la garde de PRODUCTION résout le matériel
        # elle-même et ne trouve aucune désignation. ACAL170 (D-ACAL-9) :
        # l'indéterminé ne bloque pas, il NOMME ce qui manque.
        garde = garde_publication(_Calepinage(24))

        self.assertEqual(garde['verdict'], 'indetermine')
        # ACAL56 — l'absence NOMME le geste : « module PV non désigné —
        # désignez-le dans l'onglet Matériel électrique ».
        self.assertIn(
            "module PV non désigné — désignez-le dans l'onglet Matériel "
            "électrique", garde['manquantes'])


class EvaluationAChaudTest(SimpleTestCase):
    """L'évaluation à chaud lit le dessin EN COURS et n'écrit rien."""

    def test_le_layout_du_corps_remplace_celui_enregistre(self):
        calepinage = _Calepinage(12)
        chaud = {'version': 2, 'zones': [
            {'label': 'PAN-A', 'geometry': {'count': 24, 'azimuthDeg': 180.0,
                                            'tiltDeg': 15.0}}]}

        evaluation = evaluation_electrique(
            calepinage, layout=chaud,
            materiel=_materiel(isc_max_mppt_a=26.0))

        self.assertEqual(evaluation['verdict'], 'bloquant')
        # Le document enregistré n'a pas bougé : c'est une évaluation.
        self.assertEqual(
            calepinage.roof_layout['zones'][0]['geometry']['count'], 12)


class ControleChaineSansDessinTest(SimpleTestCase):
    """ACAL627 — 22 × 49,5 V à −5 °C sur 1 000 V : rouge, borne nommée."""

    MODULE_22 = dict(MODULE, voc_v=49.5)

    def _controle(self, nombre, tmin=-5.0, onduleur=None):
        from apps.calepinage.services.controle_chaine import (
            _controler_chaine)
        return _controler_chaine(self.MODULE_22, onduleur or ONDULEUR,
                                 nombre, tmin, 70.0)

    def _voc(self, reponse):
        return next(c for c in reponse['controles']
                    if c['code'] == 'voc_froid')

    def test_22_modules_rouges_sur_1000_v(self):
        reponse = self._controle(22)
        voc = self._voc(reponse)
        # 22 × 49,5 × (1 + 0,0027 × 30) = 1 177,2 V.
        self.assertAlmostEqual(voc['valeur'], 1177.2, places=1)
        self.assertIs(voc['conforme'], False)
        self.assertTrue(voc['bloquant'])
        self.assertEqual(voc['borne'],
                         "tension maximale absolue de l'onduleur (1 000 V)")
        self.assertEqual(reponse['verdict'], 'bloquant')

    def test_la_temperature_saisie_fait_le_calcul(self):
        # Mutant « 25 °C au lieu de la saisie » : 22 × 49,5 = 1 089 V.
        self.assertGreater(self._voc(self._controle(22))['valeur'],
                           self._voc(self._controle(22, tmin=25.0))['valeur'])
        self.assertAlmostEqual(
            self._voc(self._controle(22, tmin=25.0))['valeur'], 1089.0, 1)

    def test_chaine_courte_conforme_et_fenetre(self):
        reponse = self._controle(16)
        self.assertIs(self._voc(reponse)['conforme'], True)
        # min(⌊1000 / 53,51⌋, ⌊800 / (41,5 × 1,105)⌋) = min(18, 17).
        self.assertEqual(reponse['longueur_max'], 17)
        self.assertEqual(reponse['manquantes'], [])

    def test_fiche_incomplete_indeterminee(self):
        onduleur = {cle: v for cle, v in ONDULEUR.items()
                    if cle != 'v_max_abs'}
        reponse = self._controle(22, onduleur=onduleur)
        self.assertEqual(reponse['verdict'], 'indetermine')
        self.assertEqual(reponse['controles'], [])
        self.assertTrue(any('tension DC maximale absolue' in m
                            for m in reponse['manquantes']))


class TensionsParChaineTest(SimpleTestCase):
    """ACAL618 — ``chaines[]`` : N × la tension d'UN module, chaîne par chaîne.

    Oracle indépendant, recalculé ici : Voc(T) = Voc_stc × (1 + coeff/100 ×
    (T − 25)) pour un module, multiplié par le nombre de modules.
    """

    @staticmethod
    def _voc_froid_module():
        return 49.6 * (1 + (-0.27 / 100) * (-5.0 - 25.0))

    def test_chaque_chaine_automatique_porte_n_fois_un_module(self):
        evaluation = evaluation_electrique(
            _Calepinage(24), materiel=_materiel(isc_max_mppt_a=45.0))

        lignes = evaluation['chaines']
        self.assertEqual([ligne['chaine'] for ligne in lignes], [1, 2])
        for ligne in lignes:
            self.assertEqual(ligne['nombre_modules'], 12)
            self.assertEqual(ligne['source'], 'automatique')
            self.assertAlmostEqual(
                ligne['voc_froid_v'], round(12 * self._voc_froid_module(), 1),
                places=6)
            self.assertEqual(ligne['voc_froid_limite_v'], 1000.0)
            self.assertTrue(ligne['voc_froid_conforme'])
            self.assertEqual(ligne['temperature_froide_c'], -5.0)
            self.assertEqual(ligne['temperature_chaude_c'], 70.0)
            self.assertEqual(ligne['demarrage_v'], 150.0)
            self.assertEqual(ligne['demarrage_source'], 'bas_de_plage_mppt')
            self.assertEqual(ligne['isc_a'], 18.4)
            self.assertEqual(ligne['indetermine'], [])

    def test_une_chaine_imposee_est_comptee_avec_ses_modules(self):
        base = evaluation_electrique(
            _Calepinage(24), materiel=_materiel(isc_max_mppt_a=45.0))
        from apps.calepinage.services.chaines import affectation
        from apps.calepinage.services.electrique import (
            conception_du_calepinage)
        conception = conception_du_calepinage(
            _Calepinage(24), materiel=_materiel(isc_max_mppt_a=45.0))[0]
        modules = [ligne['module'] for ligne in affectation(conception)][:8]
        imposee = [{'module': module, 'chaine': 9, 'mppt': 1, 'onduleur': 1}
                   for module in modules]

        evaluation = evaluation_electrique(
            _Calepinage(24), entree={'affectation_manuelle': imposee},
            materiel=_materiel(isc_max_mppt_a=45.0))

        par_chaine = {ligne['chaine']: ligne for ligne in evaluation['chaines']}
        self.assertEqual(par_chaine[9]['nombre_modules'], 8)
        self.assertEqual(par_chaine[9]['source'], 'affectation manuelle')
        self.assertAlmostEqual(
            par_chaine[9]['voc_froid_v'],
            round(8 * self._voc_froid_module(), 1), places=6)
        self.assertEqual(len(base['chaines']), 2)

    def test_le_demarrage_de_la_fiche_est_cite_comme_tel(self):
        evaluation = evaluation_electrique(
            _Calepinage(12), materiel=_materiel(isc_max_mppt_a=45.0,
                                                v_demarrage_v=180.0))

        ligne = evaluation['chaines'][0]
        self.assertEqual(ligne['demarrage_v'], 180.0)
        self.assertEqual(ligne['demarrage_source'], 'fiche')

    def test_fiche_muette_rend_une_liste_vide(self):
        materiel = _materiel()
        del materiel['onduleur']['v_max_abs']

        evaluation = evaluation_electrique(_Calepinage(24), materiel=materiel)

        self.assertEqual(evaluation['chaines'], [])


class BoucleDeChaineTest(SimpleTestCase):
    """ACAL677 — ``boucles_dc[]`` par ``evaluation_electrique``."""

    @staticmethod
    def _calepinage(collecte=None):
        calepinage = _Calepinage(4)
        zone = calepinage.roof_layout['zones'][0]
        zone['id'] = 'z1'
        zone['geometry']['panels'] = [
            {'cx': float(n), 'cy': 0.0, 'n': n + 1} for n in range(4)]
        if collecte is not None:
            calepinage.resultat['entree_electrique']['cheminement'] = {
                'pans': {'z1': {'point_collecte': collecte}}}
        return calepinage

    def test_quatre_modules_alignes_publient_4_5_m2(self):
        evaluation = evaluation_electrique(
            self._calepinage({'cx': 1.5, 'cy': 3.0}),
            materiel=_materiel(isc_max_mppt_a=45.0))

        boucles = evaluation['boucles_dc']
        self.assertEqual(len(boucles), 1)
        self.assertEqual(boucles[0]['chaine'], 1)
        self.assertEqual(boucles[0]['nombre_modules'], 4)
        self.assertEqual(boucles[0]['surface_m2'], 4.5)
        self.assertIn('estimation géométrique', boucles[0]['base'])

    def test_sans_point_de_collecte_la_surface_est_null_et_nommee(self):
        evaluation = evaluation_electrique(
            self._calepinage(), materiel=_materiel(isc_max_mppt_a=45.0))

        self.assertIsNone(evaluation['boucles_dc'][0]['surface_m2'])
        self.assertTrue(evaluation['boucles_dc'][0]['indetermine'])

    def test_fiche_muette_rend_une_liste_vide(self):
        materiel = _materiel()
        del materiel['onduleur']['v_max_abs']

        evaluation = evaluation_electrique(self._calepinage(),
                                           materiel=materiel)

        self.assertEqual(evaluation['boucles_dc'], [])


class LimiteDeBoucleTest(SimpleTestCase):
    """ACAL678 — la limite de surface de boucle est un RÉGLAGE société."""

    def _evaluer(self, reglage):
        from unittest import mock

        calepinage = BoucleDeChaineTest._calepinage({'cx': 1.5, 'cy': 3.0})
        with mock.patch(
                'apps.calepinage.services.electrique.'
                '_reglages_electrique_societe',
                return_value=({'boucle_dc_max_m2': reglage}
                              if reglage is not None else {})):
            return evaluation_electrique(
                calepinage, materiel=_materiel(isc_max_mppt_a=45.0))

    def test_limite_saisie_avec_source_ajoute_une_alerte_nommee(self):
        evaluation = self._evaluer(
            {'valeur': 3, 'source': 'societe', 'reference': 'essai'})

        ligne = evaluation['boucles_dc'][0]
        self.assertEqual((ligne['limite_m2'], ligne['limite_source'],
                          ligne['depasse']), (3, 'societe', True))
        self.assertIn(
            "Chaîne 1 : boucle de 4,5 m², au-dessus de la limite de 3 m² "
            "fixée par la société (source : societe) — rapprochez le point "
            "de collecte du pan.", evaluation['alertes'])
        self.assertEqual(evaluation['verdict'], 'alerte')
        self.assertEqual(evaluation['bloquants'], [])
        self.assertTrue(evaluation['publiable'])

    def test_limite_sans_source_ou_vide_n_ajoute_aucune_alerte(self):
        for reglage in ({'valeur': 3, 'source': ''}, None):
            evaluation = self._evaluer(reglage)

            ligne = evaluation['boucles_dc'][0]
            self.assertIsNone(ligne['limite_m2'])
            self.assertIsNone(ligne['depasse'])
            self.assertFalse([a for a in evaluation['alertes']
                              if 'boucle' in a])
            self.assertIn('limite non saisie : réglage `boucle_dc_max_m2`',
                          ligne['indetermine'])

    def test_limite_au_dessus_de_la_surface_ne_depasse_pas(self):
        evaluation = self._evaluer(
            {'valeur': 10, 'source': 'societe', 'reference': 'essai'})

        self.assertIs(evaluation['boucles_dc'][0]['depasse'], False)
        self.assertFalse([a for a in evaluation['alertes'] if 'boucle' in a])


class ModulesSousSeuilTest(SimpleTestCase):
    """ACAL647 — ``modules_sous_seuil[]`` : les modules à proposer à un optimiseur."""

    ACCES = [0.95, 0.4, 0.3, 0.9]

    def _evaluer(self, reglage):
        from unittest import mock

        calepinage = BoucleDeChaineTest._calepinage()
        calepinage.roof_layout['zones'][0]['geometry']['solarAccess'] = {
            'values': list(self.ACCES)}
        with mock.patch(
                'apps.calepinage.services.electrique.'
                '_reglages_electrique_societe',
                return_value=({'seuil_acces_optimiseur': reglage}
                              if reglage is not None else {})):
            return evaluation_electrique(
                calepinage, materiel=_materiel(isc_max_mppt_a=45.0))

    def test_seuil_vide_rend_une_liste_vide(self):
        self.assertEqual(self._evaluer(None)['modules_sous_seuil'], [])
        self.assertEqual(self._evaluer(
            {'valeur': 0.5, 'source': ''})['modules_sous_seuil'], [])

    def test_seuil_saisi_rend_les_modules_sous_le_seuil(self):
        evaluation = self._evaluer({'valeur': 0.5, 'source': 'societe'})

        self.assertEqual(evaluation['modules_sous_seuil'], ['z1#2', 'z1#3'])

    def test_fiche_muette_garde_la_cle_vide(self):
        materiel = _materiel()
        del materiel['onduleur']['v_max_abs']

        evaluation = evaluation_electrique(
            BoucleDeChaineTest._calepinage(), materiel=materiel)

        self.assertEqual(evaluation['modules_sous_seuil'], [])
