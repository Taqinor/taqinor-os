"""L-BACK T4 (24/08/2026) — unit tests PURS (sans BD) des deux helpers du
payload public qui composent depuis des blocs déjà persistés
(``etude_params['dimensionnement']``/``['etude_horaire']``) plutôt que de
recalculer : ``apps.ventes.public_views._tranche_tarifaire_publique`` et
``_batterie_regime_publique``. Les deux autres clés du contrat
(``estimation_conso``/``jours_types``) sont couvertes côté moteur pur dans
``test_etude_horaire.py`` (``EstimationConsoMensuelleTests``/
``JoursTypesPublicsTests``) — ce module ne les reteste pas.
"""
from django.test import SimpleTestCase

from apps.ventes.public_views import (
    _balayage_stockage_publique,
    _batterie_regime_publique,
    _tranche_tarifaire_publique,
)


class TrancheTarifairePubliqueTests(SimpleTestCase):
    def test_dimensionnement_absent_renvoie_none(self):
        self.assertIsNone(_tranche_tarifaire_publique(None))
        self.assertIsNone(_tranche_tarifaire_publique({}))

    def test_falaise_absente_renvoie_none(self):
        """Client déjà dans la tranche la plus basse : rien à annoncer."""
        self.assertIsNone(_tranche_tarifaire_publique({'falaise': None}))

    def test_falaise_et_meilleure_falaise_composent_les_quatre_champs(self):
        dimensionnement = {
            'falaise': {
                'cible_kwh_mois': 500.0,
                'tranche_actuelle': {'rang': 5, 'libelle': 'Tranche 5'},
                'tranche_visee': {'rang': 4, 'libelle': 'Tranche 4'},
            },
            'meilleure_falaise': {
                'residuel_kwh_mois': 412.3,
                'panneaux': 20,
            },
        }
        self.assertEqual(_tranche_tarifaire_publique(dimensionnement), {
            'tranche_actuelle': {'libelle': 'Tranche 5'},
            'tranche_visee': {'libelle': 'Tranche 4'},
            'cible_kwh_mois': 500.0,
            'residuel_kwh_mois': 412.3,
        })

    def test_sans_meilleure_falaise_residuel_est_none(self):
        """La marche existe mais AUCUNE combinaison ne la franchit — le
        pitch reste affichable (cible/tranches), résiduel simplement absent."""
        dimensionnement = {
            'falaise': {
                'cible_kwh_mois': 500.0,
                'tranche_actuelle': {'libelle': 'Tranche 5'},
                'tranche_visee': {'libelle': 'Tranche 4'},
            },
            'meilleure_falaise': None,
        }
        bloc = _tranche_tarifaire_publique(dimensionnement)
        self.assertIsNotNone(bloc)
        self.assertIsNone(bloc['residuel_kwh_mois'])

    def test_libelles_manquants_restent_none_sans_lever(self):
        dimensionnement = {'falaise': {'cible_kwh_mois': 500.0}}
        bloc = _tranche_tarifaire_publique(dimensionnement)
        self.assertEqual(bloc['tranche_actuelle'], {'libelle': None})
        self.assertEqual(bloc['tranche_visee'], {'libelle': None})


class BatterieRegimePubliqueTests(SimpleTestCase):
    def test_les_deux_absents_renvoie_none(self):
        self.assertIsNone(_batterie_regime_publique(None, None))
        self.assertIsNone(_batterie_regime_publique({}, {}))

    def test_remplissage_moyen_converti_en_pourcentage(self):
        dimensionnement = {
            'recommandation_avec': {'remplissage': {'moyen': 0.734}},
        }
        bloc = _batterie_regime_publique(dimensionnement, None)
        self.assertEqual(bloc['remplissage_moyen_pct'], 73.4)
        self.assertIsNone(bloc['couverture_glitch_pct'])

    def test_couverture_glitch_bornee_a_cent_pour_cent(self):
        bloc_horaire = {'annuel': {
            'part_glitch_sans_kwh': 10.0,
            'part_glitch_batterie_kwh': 8.5,
        }}
        bloc = _batterie_regime_publique(None, bloc_horaire)
        self.assertEqual(bloc['couverture_glitch_pct'], 85.0)
        self.assertIsNone(bloc['remplissage_moyen_pct'])

    def test_recapte_superieur_au_perdu_reste_borne_a_cent(self):
        """Garde défensive : jamais > 100 % même si un arrondi amont
        déborde légèrement."""
        bloc_horaire = {'annuel': {
            'part_glitch_sans_kwh': 5.0,
            'part_glitch_batterie_kwh': 5.4,
        }}
        bloc = _batterie_regime_publique(None, bloc_horaire)
        self.assertEqual(bloc['couverture_glitch_pct'], 100.0)

    def test_perdu_nul_ne_calcule_pas_de_couverture(self):
        """Aucune impulsion cette année : diviser par zéro serait un chiffre
        inventé — la clé reste absente plutôt qu'un 0 % trompeur."""
        bloc_horaire = {'annuel': {
            'part_glitch_sans_kwh': 0.0,
            'part_glitch_batterie_kwh': 0.0,
        }}
        self.assertIsNone(_batterie_regime_publique(None, bloc_horaire))

    def test_les_deux_champs_composent_ensemble(self):
        dimensionnement = {
            'recommandation_avec': {'remplissage': {'moyen': 0.5}},
        }
        bloc_horaire = {'annuel': {
            'part_glitch_sans_kwh': 4.0,
            'part_glitch_batterie_kwh': 2.0,
        }}
        bloc = _batterie_regime_publique(dimensionnement, bloc_horaire)
        self.assertEqual(bloc, {
            'remplissage_moyen_pct': 50.0,
            'couverture_glitch_pct': 50.0,
        })


class BalayageStockagePubliqueTests(SimpleTestCase):
    """ORDRE FONDATEUR (24/08/2026, soir) — sélection de plusieurs packs de
    batterie + message de sur-stockage sur la page publique : le
    sous-ensemble public de ``dimensionnement.recommandation_avec.
    balayage_stockage``/``stockage_refuse``."""

    def test_dimensionnement_absent_renvoie_none(self):
        self.assertIsNone(_balayage_stockage_publique(None))
        self.assertIsNone(_balayage_stockage_publique({}))

    def test_recommandation_avec_absente_renvoie_none(self):
        self.assertIsNone(_balayage_stockage_publique({'recommandation_avec': None}))

    def test_palier_sans_ligne_batterie_est_omis(self):
        """Aucune ligne role=batterie ⇒ aucun N de packs lisible : le palier
        interne ne sort pas (jamais un N inventé/à zéro)."""
        dimensionnement = {'recommandation_avec': {
            'balayage_stockage': [
                {'capacite_kwh': 5.0, 'cout_ttc': 42000.0, 'lignes_batterie': []},
            ],
        }}
        self.assertIsNone(_balayage_stockage_publique(dimensionnement))

    def test_paliers_retenus_composent_nb_packs_depuis_les_lignes(self):
        dimensionnement = {'recommandation_avec': {
            'balayage_stockage': [
                {
                    'capacite_kwh': 5.0,
                    'cout_ttc': 42000.0,
                    'remplissage': {'moyen': 0.982, 'pire_mois': {'ratio': 0.91}},
                    'lignes_batterie': [{'quantite': 1, 'designation': 'Dyness 5kWh'}],
                    'payback_annees': 6.2,
                    'economie_mad': 6774.19,
                },
                {
                    'capacite_kwh': 10.0,
                    'cout_ttc': 78000.0,
                    'remplissage': {'moyen': 0.915, 'pire_mois': {'ratio': 0.80}},
                    'lignes_batterie': [{'quantite': 2, 'designation': 'Dyness 5kWh'}],
                    'payback_annees': 7.9,
                    'economie_mad': 9873.42,
                },
            ],
        }}
        bloc = _balayage_stockage_publique(dimensionnement)
        self.assertEqual(bloc['paliers'], [
            {'nb_packs': 1, 'capacite_kwh': 5.0, 'cout_ttc': 42000.0,
             'remplissage_moyen_pct': 98.2, 'payback_annees': 6.2,
             'economie_mad': 6774.19},
            {'nb_packs': 2, 'capacite_kwh': 10.0, 'cout_ttc': 78000.0,
             'remplissage_moyen_pct': 91.5, 'payback_annees': 7.9,
             'economie_mad': 9873.42},
        ])
        self.assertIsNone(bloc['refuse'])

    def test_payback_et_economie_sont_la_passe_directe_du_moteur(self):
        """Les deux valeurs sortent EXACTEMENT celles du palier moteur —
        jamais une constante, jamais un recalcul depuis cout_ttc ici."""
        dimensionnement = {'recommandation_avec': {
            'balayage_stockage': [{
                'capacite_kwh': 5.0,
                'cout_ttc': 42000.0,
                'lignes_batterie': [{'quantite': 1}],
                'payback_annees': 4.37,
                'economie_mad': 9610.99,
            }],
        }}
        bloc = _balayage_stockage_publique(dimensionnement)
        self.assertEqual(bloc['paliers'][0]['payback_annees'], 4.37)
        self.assertEqual(bloc['paliers'][0]['economie_mad'], 9610.99)

    def test_payback_absent_ou_non_finissable_sort_none_sans_toucher_au_reste(self):
        """Palier moteur sans payback_annees exploitable (absent, 0, None,
        négatif ou non numérique) ⇒ omission propre côté public, le reste du
        palier reste intact."""
        cas = [
            {},
            {'payback_annees': None},
            {'payback_annees': 0},
            {'payback_annees': -3.1},
            {'payback_annees': float('nan')},
            {'payback_annees': float('inf')},
            {'payback_annees': 'six ans'},
        ]
        for extra in cas:
            with self.subTest(extra=extra):
                dimensionnement = {'recommandation_avec': {
                    'balayage_stockage': [{
                        'capacite_kwh': 5.0,
                        'cout_ttc': 42000.0,
                        'lignes_batterie': [{'quantite': 1}],
                        **extra,
                    }],
                }}
                bloc = _balayage_stockage_publique(dimensionnement)
                palier = bloc['paliers'][0]
                self.assertIsNone(palier['payback_annees'])
                self.assertEqual(palier['nb_packs'], 1)
                self.assertEqual(palier['capacite_kwh'], 5.0)
                self.assertEqual(palier['cout_ttc'], 42000.0)

    def test_economie_absente_ou_non_finissable_sort_none(self):
        cas = [
            {},
            {'economie_mad': None},
            {'economie_mad': 0},
            {'economie_mad': -50.0},
            {'economie_mad': float('nan')},
            {'economie_mad': 'beaucoup'},
        ]
        for extra in cas:
            with self.subTest(extra=extra):
                dimensionnement = {'recommandation_avec': {
                    'balayage_stockage': [{
                        'capacite_kwh': 5.0,
                        'cout_ttc': 42000.0,
                        'lignes_batterie': [{'quantite': 1}],
                        **extra,
                    }],
                }}
                bloc = _balayage_stockage_publique(dimensionnement)
                self.assertIsNone(bloc['paliers'][0]['economie_mad'])

    def test_palier_refuse_rend_le_pourcentage_reel_du_pire_mois(self):
        """Le pourcentage rendu est EXACTEMENT celui que ``motif_refus``
        calcule en interne (dimensionnement.py) — jamais un second calcul."""
        dimensionnement = {'recommandation_avec': {
            'balayage_stockage': [],
            'stockage_refuse': {
                'capacite_kwh': 15.0,
                'remplissage': {'pire_mois': {'ratio': 0.417}},
                'lignes_batterie': [{'quantite': 3, 'designation': 'Dyness 5kWh'}],
            },
        }}
        bloc = _balayage_stockage_publique(dimensionnement)
        self.assertEqual(bloc['paliers'], [])
        self.assertEqual(bloc['refuse'], {
            'nb_packs': 3, 'capacite_kwh': 15.0, 'remplissage_pire_mois_pct': 41.7,
        })

    def test_ne_leve_jamais_sur_une_forme_malformee(self):
        dimensionnement = {'recommandation_avec': {
            'balayage_stockage': [None, 'oops', {'capacite_kwh': 'x'}],
            'stockage_refuse': 'oops',
        }}
        self.assertIsNone(_balayage_stockage_publique(dimensionnement))

    def test_jamais_de_prix_achat_ou_marge_dans_le_rendu(self):
        """RULE #4 — le palier interne peut porter des champs de marge, le
        sous-ensemble public n'en recopie AUCUN."""
        dimensionnement = {'recommandation_avec': {
            'balayage_stockage': [{
                'capacite_kwh': 5.0,
                'cout_ttc': 42000.0,
                'prix_achat': 30000.0,
                'marge_mad': 12000.0,
                'lignes_batterie': [{'quantite': 1}],
            }],
        }}
        bloc = _balayage_stockage_publique(dimensionnement)
        self.assertEqual(set(bloc['paliers'][0].keys()),
                         {'nb_packs', 'capacite_kwh', 'cout_ttc',
                          'remplissage_moyen_pct', 'payback_annees', 'economie_mad'})
