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
    resultat_calepinage, temperatures_site, verdicts_electriques,
)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_resultat.json').read_text(encoding='utf-8'))

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
        self.assertEqual(lignes[0]['module'], 'PAN-A#1')
        self.assertEqual(lignes[-1]['pan'], 'PAN-B')

    def test_les_cinq_cles_du_contrat_sont_toujours_presentes(self):
        attendues = sorted(CONTRAT['exemple']['electrique']['affectation'][0])

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

    def test_le_bloc_electrique_a_les_quatre_cles(self):
        bloc, _ = bloc_electrique(_conception(),
                                  verdicts=verdicts_electriques(
                                      _conception()))

        self.assertEqual(sorted(bloc),
                         sorted(CONTRAT['exemple']['electrique']))
        self.assertEqual(sorted(bloc['onduleurs'][0]),
                         sorted(CONTRAT['exemple']['electrique']
                                ['onduleurs'][0]))
        self.assertEqual(sorted(bloc['chainage']),
                         sorted(CONTRAT['exemple']['electrique']['chainage']))
        self.assertEqual(sorted(bloc['verdicts'][0]),
                         sorted(CONTRAT['exemple']['electrique']
                                ['verdicts'][0]))

    def test_les_cinq_codes_de_verdict_du_contrat_sont_servis(self):
        codes = [v['code'] for v in verdicts_electriques(_conception())]
        attendus = [v['code']
                    for v in CONTRAT['exemple']['electrique']['verdicts']]

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
        self.assertTrue(any('Production non simulée' in message
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
