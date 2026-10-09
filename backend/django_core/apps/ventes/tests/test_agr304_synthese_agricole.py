"""AGR304 — ``synthese_agricole(data)`` : fonction serveur PURE (dict → dict)
qui dit l'eau, la pompe, les hypothèses et leur provenance d'un devis de
pompage, servie à l'identique au PDF et à /proposition.

Tests PURS (aucune base, aucun rendu) : l'entrée est une charge utile de la
forme ``build_quote_data`` dont l'étude porte les clés ``etude_params``
pompage v2 du contrat partagé ``etude_pompage_preview.json`` (AGR2) et dont
les items portent ``role_pompage``/``courbe_pompe`` (contrat AGR7). La sortie
est confrontée à la forme ``exemple_agricole.synthese_agricole`` du contrat
partagé ``proposal_data.json`` (AGR4).
"""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.quote_engine.agricole.synthese import synthese_agricole

_CONTRATS = Path(__file__).resolve().parents[1] / 'contract_samples'

COURBE_OSP_30_8 = {'debits_m3h': [0, 12, 24, 30, 36, 39],
                   'hmt_m': [91, 85, 70, 60, 43, 34]}

PROVENANCE_MESUREE = {
    'volume_m3_jour': {'origine': 'lead', 'detail': 'client',
                       'date': '2026-09-12'},
    'niveau_statique_m': {'origine': 'lead', 'detail': 'mesure_visite',
                          'date': '2026-09-15'},
    'niveau_dynamique_m': {'origine': 'lead', 'detail': 'mesure_visite',
                           'date': '2026-09-15'},
    'debit_exploitation_m3h': {'origine': 'saisie', 'detail': 'foreur',
                               'date': '2026-09-15'},
}


def _data_complete():
    """Charge utile d'un devis agricole complet — valeurs reprises de
    l'``exemple`` du contrat AGR2 (illustratives, jamais inventées ici)."""
    etude = {
        'mode_pompe': 'neuve', 'plaque': None,
        'besoin': {'mode': 'volume_declare', 'volume_m3_jour': 135,
                   'cultures': [], 'region': 'souss-massa'},
        'source': {'niveau_statique_m': 32, 'niveau_dynamique_m': 40,
                   'debit_exploitation_m3h': 36, 'profondeur_forage_m': 90,
                   'volume_reservoir_m3': None},
        'distance_champ_m': 25,
        'hmt_composantes': {'niveau_dynamique_m': 40, 'denivele_m': 4,
                            'pertes_lineaires_m': 3.7,
                            'pertes_singulieres_m': 0.8,
                            'pression_service_m': 10.2},
        'besoin_mensuel': {'m3_jour_mois': [135] * 12, 'nature': 'declare',
                           'source_et0': None},
        'production': {
            'm3_jour_mois': [140.3, 161.7, 186.0, 207.4, 219.6, 225.7,
                             228.8, 222.7, 201.3, 173.8, 146.4, 134.2],
            'heures_equivalentes_mois': [4.6, 5.3, 6.1, 6.8, 7.2, 7.4,
                                         7.5, 7.3, 6.6, 5.7, 4.8, 4.4],
            'source_irradiation': 'pvgis', 'mode': 'courbe'},
        'conception': {'mois_critique': 12, 'debit_conception_m3h': 30.7},
        'champ': {'kwc': 9.94, 'nb_panneaux': 14},
        'ha_irrigables': {'valeur': None, 'base': None, 'motif': 'x'},
        # AMOT43 — la forme RÉELLE du producteur (``domain.pompage``).
        'provenance_pompage': {'entrees': copy.deepcopy(PROVENANCE_MESUREE),
                               '_empreinte': 'fixture'},
        # Dérivées v1 écrites par le nouveau moteur pour son rendu.
        'pompe_cv': 10.2, 'pompe_kw': 7.5, 'hmt_m': 58.7,
        'debit_hmt_m3h': 30.5, 'm3_jour': 134.2, 'heures_pompage': 4.4,
        'champ_kwc': 9.94,
    }
    items = [
        {'designation': 'Pompe immergée OSP 30/8', 'quantite': 1,
         'prix_unit_ht': 15000.0, 'role_pompage': 'pompe',
         'courbe_pompe': copy.deepcopy(COURBE_OSP_30_8)},
        {'designation': 'VARIATEUR VEICHI SI23 7.5KW 380V', 'quantite': 1,
         'prix_unit_ht': 6000.0, 'role_pompage': 'variateur_pompage',
         'courbe_pompe': None},
        {'designation': 'Panneau 710W', 'quantite': 14,
         'prix_unit_ht': 1100.0, 'role_pompage': None, 'courbe_pompe': None},
    ]
    return {
        'mode_installation': 'agricole', 'etude': etude,
        'all_items': items, 'sans_items': list(items),
        'options_proposees': [
            {'id': 90311, 'designation': 'Afficheur du variateur',
             'quantite': 1.0, 'prix_unit_ht': 791.67,
             'prix_unit_ttc': 950.0, 'total_ht': 791.67,
             'total_ttc': 950.0}],
    }


def _parcours(o):
    """Toutes les clés et toutes les valeurs, récursivement."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _parcours(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _parcours(v)
    else:
        yield o


def _motifs(s):
    return {o['bloc']: o['motif'] for o in s['omissions']}


class Agr304DevisCompletTests(SimpleTestCase):

    def test_un_devis_complet_rend_toutes_les_cles_du_contrat(self):
        contrat = json.loads((_CONTRATS / 'proposal_data.json').read_text(
            encoding='utf-8'))['exemple_agricole']['synthese_agricole']
        s = synthese_agricole(_data_complete())
        # Les clés que CETTE tâche construit (AGR305-AGR309 ajoutent
        # garanties, aide_fda, formalites, economies, schema_svg…).
        for cle in ('version', 'mode_pompe', 'eau', 'provenance',
                    'a_confirmer_par_visite', 'pompe', 'champ',
                    'besoin_vs_livre', 'point_fonctionnement', 'schema',
                    'options_kit', 'non_inclus', 'omissions'):
            with self.subTest(cle=cle):
                self.assertIn(cle, s)
                self.assertIn(cle, contrat)
        for bloc in ('eau', 'besoin_vs_livre', 'point_fonctionnement',
                     'schema', 'champ'):
            with self.subTest(bloc=bloc):
                self.assertEqual(set(s[bloc]), set(contrat[bloc]))
        self.assertEqual(set(s['options_kit'][0]),
                         set(contrat['options_kit'][0]))

    def test_les_valeurs_sont_lues_telles_que_servies(self):
        s = synthese_agricole(_data_complete())
        self.assertEqual(s['version'], 2)
        self.assertEqual(s['mode_pompe'], 'neuve')
        self.assertEqual(s['eau'], {'m3_jour': 134.2, 'heures_pompage': 4.4,
                                    'hmt_m': 58.7, 'debit_hmt_m3h': 30.5,
                                    'estimation': False})
        self.assertEqual(s['pompe'], {'cv': 10.2, 'kw': 7.5})
        self.assertEqual(s['champ'], {'kwc': 9.94, 'nb_panneaux': 14})
        bvl = s['besoin_vs_livre']
        self.assertEqual(len(bvl['mois']), 12)
        self.assertEqual(bvl['mois'][11],
                         {'besoin_m3_jour': 135, 'livre_m3_jour': 134.2})
        self.assertEqual(bvl['mois_le_plus_serre'], 12)
        self.assertIsNone(bvl['hectares_irrigables'])
        self.assertEqual(bvl['base_besoin'], 'declare')
        self.assertEqual(s['point_fonctionnement']['point'],
                         {'debit_m3h': 30.5, 'hmt_m': 58.7})
        self.assertEqual(s['point_fonctionnement']['courbe'][0], [0, 91])
        self.assertEqual(s['schema'], {'profondeur_m': 90, 'niveau_m': 40,
                                       'distance_m': 25, 'hmt_m': 58.7,
                                       'bassin': None})
        self.assertEqual(s['options_kit'], [
            {'ligne_id': 90311, 'designation': 'Afficheur du variateur',
             'total_ttc': 950.0}])
        self.assertEqual(s['non_inclus'], ['forage', 'genie_civil'])

    def test_provenance_reprise_dans_la_forme_unique(self):
        s = synthese_agricole(_data_complete())
        self.assertEqual(s['provenance'], PROVENANCE_MESUREE)
        for prov in s['provenance'].values():
            self.assertEqual(set(prov), {'origine', 'detail', 'date'})

    def test_point_d_eau_mesure_seule_la_profondeur_reste_a_confirmer(self):
        s = synthese_agricole(_data_complete())
        self.assertEqual(s['a_confirmer_par_visite'],
                         ['profondeur_forage_m'])

    def test_fonction_pure_meme_entree_meme_sortie_sans_muter(self):
        data = _data_complete()
        avant = copy.deepcopy(data)
        self.assertEqual(synthese_agricole(data), synthese_agricole(data))
        self.assertEqual(data, avant)

    def test_omissions_de_principe_preuve_et_co2(self):
        motifs = _motifs(synthese_agricole(_data_complete()))
        self.assertIn('preuve_realisation', motifs)
        self.assertIn('co2', motifs)


class Agr304OmissionsTests(SimpleTestCase):

    def test_pompe_sans_courbe_point_absent_avec_motif(self):
        data = _data_complete()
        data['all_items'][0]['courbe_pompe'] = None
        s = synthese_agricole(data)
        self.assertNotIn('point_fonctionnement', s)
        self.assertIn('courbe constructeur non disponible',
                      _motifs(s)['point_fonctionnement'])

    def test_culture_inconnue_besoin_vs_livre_absent_avec_motif(self):
        data = _data_complete()
        etude = data['etude']
        etude['besoin'] = {'mode': 'agronomique', 'region': 'souss-massa',
                           'cultures': [{'crop': '', 'surface_ha': 2,
                                         'irrigation': 'goutte'}]}
        etude['besoin_mensuel'] = {'m3_jour_mois': [90] * 12,
                                   'nature': 'agronomique_plein',
                                   'source_et0': 'EST.'}
        s = synthese_agricole(data)
        self.assertNotIn('besoin_vs_livre', s)
        self.assertIn('culture', _motifs(s)['besoin_vs_livre'])

    def test_serie_absente_besoin_vs_livre_absent_jamais_complete(self):
        data = _data_complete()
        data['etude']['production'] = None
        s = synthese_agricole(data)
        self.assertNotIn('besoin_vs_livre', s)
        self.assertIn('besoin_vs_livre', _motifs(s))
        # Sans production, le m³/jour n'est plus une mesure de courbe.
        self.assertTrue(s['eau']['estimation'])

    def test_hmt_declaree_reste_a_confirmer_par_visite(self):
        data = _data_complete()
        etude = data['etude']
        etude['hmt_composantes'] = None
        etude['provenance_pompage'] = {'entrees': {
            'hmt_saisie_m': {'origine': 'lead', 'detail': 'client',
                             'date': '2026-09-12'}}}
        s = synthese_agricole(data)
        self.assertTrue(s['a_confirmer_par_visite'])
        self.assertIn('hmt_m', s['a_confirmer_par_visite'])
        self.assertIn('niveau_dynamique_m', s['a_confirmer_par_visite'])
        self.assertIn('debit_exploitation_m3h', s['a_confirmer_par_visite'])

    def test_mode_existante_reprend_la_plaque(self):
        data = _data_complete()
        etude = data['etude']
        etude['mode_pompe'] = 'existante'
        etude['plaque'] = {'kw': 4.0, 'tension_v': 380, 'phases': 3,
                           'cv': None, 'courant_a': None}
        data['all_items'] = data['all_items'][1:]  # aucune pompe fournie
        s = synthese_agricole(data)
        self.assertEqual(s['mode_pompe'], 'existante')
        self.assertEqual(s['pompe']['plaque'],
                         {'kw': 4.0, 'tension_v': 380, 'phases': 3,
                          'cv': None, 'courant_a': None})
        self.assertNotIn('point_fonctionnement', s)

    def test_mode_neuve_ne_porte_pas_de_plaque(self):
        self.assertNotIn('plaque', synthese_agricole(_data_complete())['pompe'])

    def test_aucun_bassin_sans_reservoir_declare(self):
        s = synthese_agricole(_data_complete())
        self.assertIsNone(s['schema']['bassin'])
        data = _data_complete()
        data['etude']['source']['volume_reservoir_m3'] = 60
        self.assertEqual(synthese_agricole(data)['schema']['bassin'], 60)

    def test_entree_vide_ne_leve_pas_et_n_invente_rien(self):
        s = synthese_agricole({})
        self.assertEqual(s['eau']['m3_jour'], None)
        self.assertNotIn('mode_pompe', s)
        self.assertNotIn('besoin_vs_livre', s)
        self.assertNotIn('point_fonctionnement', s)
        self.assertEqual(s['options_kit'], [])


class Agr304AucunPrixAchatNiMontantFdaTests(SimpleTestCase):

    def test_aucun_prix_achat_ni_marge_meme_si_les_items_en_portent(self):
        data = _data_complete()
        for it in data['all_items']:
            it['prix_achat'] = 1234.5
            it['marge'] = 99
        data['options_proposees'][0]['prix_achat'] = 1234.5
        s = synthese_agricole(data)
        tout = list(_parcours(s))
        self.assertNotIn('prix_achat', tout)
        self.assertNotIn('marge', tout)
        self.assertNotIn(1234.5, tout)

    def test_aucun_montant_fda(self):
        """D-AGR-6 : jamais un montant d'aide propre au client, jamais un
        verdict d'éligibilité, jamais « jusqu'à » (la RÈGLE seule arrive par
        AGR306)."""
        s = synthese_agricole(_data_complete())
        tout = list(_parcours(s))
        for cle in ('fda_eligible', 'montant_fda', 'montant_aide',
                    'aide_mad', 'subvention_mad'):
            with self.subTest(cle=cle):
                self.assertNotIn(cle, tout)
        self.assertFalse(any("jusqu" in str(x).lower() for x in tout))
