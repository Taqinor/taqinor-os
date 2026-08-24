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
