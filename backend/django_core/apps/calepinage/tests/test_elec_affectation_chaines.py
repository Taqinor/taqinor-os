"""CAL125 — l'affectation module → chaîne → MPPT est PUBLIÉE et REJOUABLE.

Deux garanties, et elles comptent autant l'une que l'autre :

1. **la forme est celle du contrat committé** ``contract_samples/
   calepinage_resultat.json`` (CAL244, parti seul sur ``main`` avant cette
   tâche — PACT10). Le test lit le contrat SUR LE DISQUE et compare les clés :
   une clé inventée ici ferait rougir, exactement comme l'incident du
   03/08/2026 ;
2. **entrée identique ⇒ affectation identique.** Un écran qui teinte les
   modules par chaîne (CAL126) doit pouvoir rejouer le même résultat ; une
   partition qui bouge d'un calcul à l'autre teindrait deux fois la même
   toiture de deux façons.

Aucune base de données : le matériel est injecté (``materiel=``), exactement
comme le sélecteur du stock le rendrait.

Run :
    python manage.py test apps.calepinage.tests.test_elec_affectation_chaines -v2
"""
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.chaines import (
    affectation, bloc_electrique, concevoir_par_pan, empreinte_entree,
)
from apps.calepinage.services.electrique import (
    resultat_calepinage, temperatures_site, _verdicts_electriques,
)
from apps.calepinage.tests._m0_en_attente import EN_ATTENTE_RESULTAT, sans

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_resultat.json').read_text(encoding='utf-8'))
#: L'exemple privé des clés posées par ACAL8 avant leurs producteurs
#: (couleurs ACAL285, affectation_obsolete ACAL265…).
EXEMPLE_SERVI = sans(CONTRAT['exemple'], EN_ATTENTE_RESULTAT)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}
MATERIEL = {
    'module': MODULE, 'onduleur': ONDULEUR, 'optimiseur': None,
    'designations': {'module': 'Module d essai',
                     'onduleur': 'Onduleur d essai', 'optimiseur': ''},
    'absents': (),
}
LAYOUT = {
    'version': 2,
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [
        {'id': 'a', 'label': 'PAN-A',
         'geometry': {'count': 12, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}},
        {'id': 'b', 'label': 'PAN-B',
         'geometry': {'count': 7, 'azimuthDeg': 90.0, 'tiltDeg': 15.0}},
    ],
}


class _Calepinage:
    """Le strict minimum que le service lit sur un pivot — aucun ORM."""

    pk = 1

    def __init__(self, layout):
        self.roof_layout = layout
        self.resultat = None
        self.company = None


def _temperatures():
    return temperatures_site(
        saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0})


def _conception(layout=None):
    return concevoir_par_pan(
        layout or LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=_temperatures(), module_designation='Module d essai',
        onduleur_designation='Onduleur d essai')


class AffectationTest(SimpleTestCase):
    """La table nomme CHAQUE module posé, affecté ou non."""

    def test_chaque_module_pose_a_sa_ligne(self):
        lignes = affectation(_conception())

        self.assertEqual(len(lignes), 19)
        # ACAL265 — '<zone.id>#<n>' : le libellé n'est plus la clé.
        self.assertEqual(lignes[0]['module'], 'a#1')
        self.assertEqual(lignes[-1]['pan'], 'PAN-B')

    def test_les_cinq_cles_du_contrat_sont_toujours_presentes(self):
        attendues = sorted(EXEMPLE_SERVI['electrique']['affectation'][0])

        for ligne in affectation(_conception()):
            self.assertEqual(sorted(ligne), attendues)

    def test_un_module_hors_chaine_garde_ses_cles_a_null(self):
        # PAN-B porte 7 modules : la longueur de chaîne retenue ne tombe pas
        # forcément juste, et le reste doit rester VISIBLE (gris à l'écran).
        lignes = affectation(_conception())
        non_affectes = [ligne for ligne in lignes
                        if ligne['chaine'] is None]

        for ligne in non_affectes:
            self.assertIsNone(ligne['mppt'])
            self.assertIsNone(ligne['onduleur'])
            self.assertTrue(ligne['module'])

    def test_les_panneaux_raccordes_a_rien_sont_dits_dans_les_avertissements(self):
        """ACAL1912 — « N panneaux ne sont raccordés à aucun onduleur : ils ne
        sont pas comptés » : servi par le bloc ``avertissements`` existant,
        dans le bloc électrique ET dans le résultat servi."""
        from unittest import mock

        from apps.calepinage.services import chaines
        from apps.calepinage.services.agregation_electrique import (
            phrase_non_raccordes)

        original = chaines.affectation
        retires = 4

        def quatre_en_reserve(conception, **kwargs):
            table = [dict(ligne) for ligne in original(conception, **kwargs)]
            for ligne in table[-retires:]:
                ligne.update(chaine=None, mppt=None, onduleur=None)
            return table

        conception = _conception()
        with mock.patch.object(chaines, 'affectation',
                               side_effect=quatre_en_reserve):
            _bloc, avertissements = bloc_electrique(conception)
            servi = resultat_calepinage(_Calepinage(LAYOUT), materiel=MATERIEL)
        phrase = phrase_non_raccordes(retires)
        self.assertIn(phrase, avertissements)
        self.assertIn(phrase, servi['avertissements'])
        self.assertTrue(phrase.startswith('%d panneaux' % retires))
        # Rien de non raccordé : aucune phrase.
        _bloc, sans = bloc_electrique(conception)
        self.assertFalse(any('aucun onduleur' in texte for texte in sans))

    def test_aucune_chaine_ne_recoit_deux_pans(self):
        par_chaine = {}
        for ligne in affectation(_conception()):
            if ligne['chaine'] is None:
                continue
            par_chaine.setdefault(ligne['chaine'], set()).add(ligne['pan'])

        for pans in par_chaine.values():
            self.assertEqual(len(pans), 1)


class ReproductibiliteTest(SimpleTestCase):
    """Entrée identique ⇒ empreinte identique ET affectation identique."""

    def test_deux_calculs_donnent_la_meme_table(self):
        premier = affectation(_conception())
        second = affectation(_conception())

        self.assertEqual(premier, second)

    def test_l_empreinte_est_stable_et_change_avec_l_entree(self):
        base = empreinte_entree(LAYOUT, module_specs=MODULE,
                                onduleur_specs=ONDULEUR,
                                temperatures=_temperatures())
        identique = empreinte_entree(LAYOUT, module_specs=MODULE,
                                     onduleur_specs=ONDULEUR,
                                     temperatures=_temperatures())
        autre_layout = json.loads(json.dumps(LAYOUT))
        autre_layout['zones'][0]['geometry']['count'] = 13
        change = empreinte_entree(autre_layout, module_specs=MODULE,
                                  onduleur_specs=ONDULEUR,
                                  temperatures=_temperatures())

        self.assertEqual(base, identique)
        self.assertEqual(len(base), 64)
        self.assertNotEqual(base, change)


class FormeDuResultatTest(SimpleTestCase):
    """Le ``resultat`` publié a EXACTEMENT les blocs du contrat CAL244."""

    #: CALX16 — la CINQUIÈME clé du bloc, posée non pas par
    #: ``bloc_electrique`` mais par ``resultat_calepinage`` (elle a besoin du
    #: DOCUMENT, que la conception ne porte plus), et CONDITIONNELLE : sans
    #: accès solaire par module, elle est absente et son motif part dans
    #: ``avertissements``.
    POSEE_PAR_LE_RESULTAT = ('chaine_la_plus_faible',)

    def test_le_bloc_electrique_a_les_quatre_cles(self):
        bloc, _ = bloc_electrique(_conception(),
                                  verdicts=_verdicts_electriques(
                                      _conception()))

        self.assertEqual(
            sorted(bloc),
            sorted(set(EXEMPLE_SERVI['electrique'])
                   - set(self.POSEE_PAR_LE_RESULTAT)))
        self.assertEqual(sorted(bloc['onduleurs'][0]),
                         sorted(EXEMPLE_SERVI['electrique']
                                ['onduleurs'][0]))
        self.assertEqual(sorted(bloc['chainage']),
                         sorted(EXEMPLE_SERVI['electrique']['chainage']))
        self.assertEqual(sorted(bloc['verdicts'][0]),
                         sorted(EXEMPLE_SERVI['electrique']
                                ['verdicts'][0]))

    def test_la_cinquieme_cle_est_celle_du_resultat_et_reste_conditionnelle(
            self):
        # Le document d'essai ne porte AUCUN accès solaire : la clé doit être
        # absente, et le motif dit pourquoi (jamais un 100 % supposé).
        from apps.calepinage.services.ombrage_chaines import MOTIF_SANS_ACCES

        servi = resultat_calepinage(_Calepinage(LAYOUT), materiel=MATERIEL)

        self.assertNotIn('chaine_la_plus_faible', servi['electrique'])
        self.assertIn(MOTIF_SANS_ACCES, servi['avertissements'])

    def test_les_cinq_codes_de_verdict_du_contrat_sont_servis(self):
        codes = [v['code'] for v in _verdicts_electriques(_conception())]
        attendus = [v['code']
                    for v in EXEMPLE_SERVI['electrique']['verdicts']]

        self.assertEqual(codes, attendus)

    def test_resultat_complet_sans_simulation_de_production(self):
        resultat = resultat_calepinage(_Calepinage(LAYOUT),
                                       materiel=MATERIEL)

        # La POSE est un fait : elle reste chiffrée.
        self.assertEqual(resultat['pose']['total_modules'], 19)
        self.assertTrue(resultat['electrique']['affectation'])
        # La PRODUCTION n'a pas été lancée : toutes ses clés sont présentes et
        # valent null — jamais 0 (un « 0 kWh » se lirait « ne produit rien »).
        self.assertIsNone(resultat['production']['total']['p50_kwh'])
        self.assertEqual(resultat['production']['mensuel'], [])
        self.assertEqual(resultat['pertes'], [])
        self.assertEqual(len(resultat['hash_entree']), 64)
        self.assertTrue(any("La production n'est pas encore calculée" in message
                            for message in resultat['avertissements']))

    def test_aucun_prix_dans_le_resultat(self):
        rendu = json.dumps(resultat_calepinage(_Calepinage(LAYOUT),
                                               materiel=MATERIEL),
                           ensure_ascii=False)

        for interdit in ('prix_achat', 'prix_vente', 'marge'):
            self.assertNotIn(interdit, rendu)

    def test_sans_materiel_designe_le_resultat_le_dit_sans_verdict(self):
        vide = {'module': {}, 'onduleur': {}, 'optimiseur': None,
                'designations': {'module': '', 'onduleur': '',
                                 'optimiseur': ''},
                'absents': ('module PV non désigné',)}

        resultat = resultat_calepinage(_Calepinage(LAYOUT), materiel=vide)

        self.assertFalse(resultat['simule'])
        self.assertIsNone(resultat['electrique']['chainage'])
        self.assertEqual(resultat['electrique']['verdicts'], [])
        self.assertIn('module PV non désigné', resultat['avertissements'])


FICHE_665 = {'voc_v': 49.5, 'isc_a': 13.9, 'pmax_wc': 710.0,
             'temp_coeff_voc_pct_c': -0.25, 'temp_coeff_pmax_pct_c': -0.30}


def _table_665(modules=10):
    return [{'module': 'z1#%d' % k, 'chaine': 1} for k in range(modules)]


class ValeursAttenduesParChaineTest(SimpleTestCase):
    """ACAL665 - modules, Voc, Isc, Pmax attendus par chaine, a STC."""

    def attendues(self, fiche=FICHE_665, table=None, **correction):
        from apps.calepinage.services.valeurs_attendues import (
            valeurs_attendues)
        return valeurs_attendues(table or _table_665(), fiche, 'Module X',
                                 **correction)

    def test_dix_modules_a_49_5_v_rendent_495_v_et_nomment_la_source(self):
        lignes, manquants = self.attendues()

        self.assertEqual(manquants, [])
        self.assertEqual(lignes, [{
            'chaine': 1, 'modules': 10, 'voc_stc_v': 495.0, 'isc_stc_a': 13.9,
            'pmax_stc_w': 7100.0, 'sources': ['fiche module Module X'],
            'corrigee': False}])

    def test_pmax_se_multiplie_par_les_modules_pas_par_les_chaines(self):
        table = _table_665(10) + [{'module': 'z2#%d' % k, 'chaine': 2}
                                  for k in range(4)]
        lignes, _ = self.attendues(table=table)

        self.assertEqual([(c['chaine'], c['modules'], c['pmax_stc_w'])
                          for c in lignes], [(1, 10, 7100.0), (2, 4, 2840.0)])

    def test_isc_sans_coefficient_est_nomme_et_non_devine(self):
        lignes, _ = self.attendues(temperature_c=45.0, eclairement_w_m2=800.0)

        self.assertTrue(lignes[0]['corrigee'])
        self.assertIsNone(lignes[0]['isc_a'])
        self.assertEqual(lignes[0]['isc_corrige_motif'],
                         'coefficient de Isc absent de la fiche')
        # Voc : 495 x (1 - 0,25 % x 20 K) = 470,25 V.
        self.assertEqual(lignes[0]['voc_v'], 470.25)

    def test_isc_corrige_quand_son_coefficient_existe(self):
        fiche = dict(FICHE_665, temp_coeff_isc_pct_c=0.05)
        lignes, _ = self.attendues(fiche, temperature_c=45.0,
                                   eclairement_w_m2=1000.0)

        self.assertEqual(lignes[0]['isc_a'], 14.039)
        self.assertNotIn('isc_corrige_motif', lignes[0])

    def test_fiche_incomplete_rend_none_et_nomme_le_champ(self):
        lignes, manquants = self.attendues({'voc_v': 49.5})

        self.assertIsNone(lignes)
        self.assertIn('courant de court-circuit (Isc)', manquants)

    def test_sans_chaine_publiee_rien(self):
        lignes, _ = self.attendues(table=[{'module': 'z1#1', 'chaine': None}])
        self.assertIsNone(lignes)

    def test_le_selecteur_rend_none_sans_calepinage_retenu(self):
        from unittest import mock
        from apps.calepinage import selectors_chantier as sel

        with mock.patch.object(sel, 'calepinage_retenu_pour_devis',
                               return_value=None):
            self.assertIsNone(sel.valeurs_attendues_par_chaine(1, None))


class DeuxOnduleursTest(SimpleTestCase):
    """ACAL633 — N onduleurs acceptés : l'onduleur de chaque chaîne est numéroté."""

    LAYOUT_4_PANS = {'version': 2, 'zones': [
        {'id': 'z%d' % rang, 'label': 'PAN-%d' % rang,
         'geometry': {'count': 12, 'azimuthDeg': azimut, 'tiltDeg': 15.0}}
        for rang, azimut in enumerate((180.0, 90.0, 270.0, 135.0), start=1)]}

    def _conception(self, **options):
        return concevoir_par_pan(
            self.LAYOUT_4_PANS, module_specs=MODULE, onduleur_specs=ONDULEUR,
            temperatures=_temperatures(), module_designation='Module d essai',
            onduleur_designation='Onduleur d essai', **options)

    @staticmethod
    def _par_chaine(lignes):
        vus = {}
        for ligne in lignes:
            if ligne['chaine'] is not None:
                vus[ligne['chaine']] = (ligne['onduleur'], ligne['mppt'])
        return [vus[cle] for cle in sorted(vus)]

    def test_quatre_chaines_sur_deux_onduleurs_sont_numerotees_1_1_2_2(self):
        from apps.calepinage.services.chaines import evaluer_onduleurs

        conception = self._conception(nombre_onduleurs=2)

        self.assertEqual(self._par_chaine(affectation(conception)),
                         [(1, 1), (1, 2), (2, 1), (2, 2)])
        self.assertEqual(evaluer_onduleurs(conception).nombre, 2)

    def test_sans_la_cle_le_comportement_d_aujourd_hui_est_inchange(self):
        conception = self._conception()

        for ligne in affectation(conception):
            self.assertNotIn(ligne['onduleur'], (2,))
        self.assertIsNone(conception.nombre_onduleurs)


class MotifDAffectationTest(SimpleTestCase):
    """ACAL642 — le motif d'affectation par pan : ``rangee`` ou ``u``."""

    @staticmethod
    def _layout_2_rangees():
        panneaux = [{'cx': float(colonne), 'cy': 0.0}
                    for colonne in range(10)]
        panneaux += [{'cx': float(colonne), 'cy': 1.7}
                     for colonne in range(10)]
        return {'version': 2, 'zones': [{
            'id': 'z1', 'label': 'PAN-1',
            'geometry': {'count': 20, 'azimuthDeg': 180.0, 'tiltDeg': 15.0,
                         'panels': panneaux}}]}

    def _rangs_chaine_1(self, **options):
        conception = concevoir_par_pan(
            self._layout_2_rangees(), module_specs=MODULE,
            onduleur_specs=ONDULEUR, temperatures=_temperatures(),
            module_designation='Module d essai',
            onduleur_designation='Onduleur d essai', **options)
        return [int(ligne['module'].split('#')[1])
                for ligne in affectation(conception)
                if ligne['chaine'] == 1], conception

    def test_l_ordre_en_u_est_1_a_10_puis_20_a_11(self):
        from apps.calepinage.services.chaines import _ordre_du_motif

        centres = tuple((float(c), 0.0) for c in range(10)) + tuple(
            (float(c), 1.7) for c in range(10))

        self.assertEqual(_ordre_du_motif(list(range(1, 21)), centres, 'u'),
                         list(range(1, 11)) + list(range(20, 10, -1)))

    def test_le_motif_u_change_les_modules_de_la_chaine(self):
        # Chaîne imposée à 15 modules sur 20 : « rangée » prend 1…15, « u »
        # prend la rangée 1 puis la fin de la rangée 2 (20…16).
        rangs_u, conception = self._rangs_chaine_1(
            motifs_affectation={'z1': 'u'}, longueur_forcee=15)
        rangs_rangee, _ = self._rangs_chaine_1(longueur_forcee=15)

        self.assertEqual(rangs_rangee, list(range(1, 16)))
        self.assertEqual(rangs_u, list(range(1, 11)) + list(range(16, 21)))
        self.assertEqual(conception.pans[0].motif_affectation, 'u')

    def test_sans_motif_ou_rangee_l_ordre_est_celui_du_document(self):
        sans, _ = self._rangs_chaine_1()
        rangee, _ = self._rangs_chaine_1(motifs_affectation={'z1': 'rangee'})

        self.assertEqual(sans, rangee)
        self.assertEqual(sans, list(range(1, len(sans) + 1)))

    def test_centres_absents_gardent_l_ordre_du_document(self):
        from apps.calepinage.services.chaines import _ordre_du_motif

        self.assertEqual(_ordre_du_motif([1, 2, 3], (), 'u'), [1, 2, 3])
        self.assertEqual(_ordre_du_motif([1, 2, 3], ((0, 0),), 'u'),
                         [1, 2, 3])

    def test_motif_inconnu_est_refuse_en_nommant_le_champ(self):
        from apps.calepinage.services.electrique import (
            EntreeInvalide, _valider_cheminement)

        class _C:
            roof_layout = None

        with self.assertRaises(EntreeInvalide) as capture:
            _valider_cheminement(_C(), {'pans': {'z1': {
                'motif_affectation': 'zigzag'}}})

        self.assertEqual(capture.exception.champ,
                         'cheminement.pans.z1.motif_affectation')
        self.assertIn('rangee', str(capture.exception))
        self.assertIn('u', str(capture.exception))
