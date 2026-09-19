"""Tests NTAI27 (moitié ``core``) — seuils de scorer résolus par société.

Acceptance criteria couverte côté ``core`` : « le scorer lit les params actifs
avec fallback inchangé ». Le registre ``ModeleML`` et son
``selectors.params_actifs`` vivent dans ``apps/mlops`` (hors ``core``, construit
par une autre lane) : ici on prouve la COUTURE — le résolveur enregistré, la
liste blanche, la conversion de type, et surtout le repli STRICTEMENT
non régressif.

Tests PURS : aucun modèle n'est touché, le résolveur est un double de test.
"""
from django.test import SimpleTestCase

from core import score_params
from core.anomaly import scan_for_outliers
from core.churn_risk import churn_risk
from core.payment_delay import payment_delay_risk
from core.stock_reorder import predict_reorder
from core.win_probability import win_probability


class SocieteFictive:
    """Un jeton de société : le résolveur est un double, pas la vraie base."""

    def __init__(self, nom='acme'):
        self.nom = nom


class ResolveurTests(SimpleTestCase):

    def tearDown(self):
        score_params.clear_params_resolver()
        super().tearDown()

    def test_sans_resolveur_les_params_sont_vides(self):
        score_params.clear_params_resolver()
        self.assertIsNone(score_params.registered_params_resolver())
        self.assertEqual(
            score_params.params_actifs(SocieteFictive(),
                                       score_params.NOM_CHURN), {})

    def test_enregistrement_exige_un_callable(self):
        with self.assertRaises(ValueError):
            score_params.register_params_resolver('pas un callable')

    def test_un_second_enregistrement_remplace_le_premier(self):
        score_params.register_params_resolver(lambda c, n: {'a': 1})
        score_params.register_params_resolver(lambda c, n: {'b': 2})
        self.assertEqual(
            score_params.params_actifs(SocieteFictive(), 'churn'), {'b': 2})

    def test_societe_absente_nappelle_jamais_le_resolveur(self):
        appels = []

        def resolveur(company, nom):
            appels.append((company, nom))
            return {'WEIGHT_SAV': 0.9}

        score_params.register_params_resolver(resolveur)
        self.assertEqual(score_params.params_actifs(None, 'churn'), {})
        self.assertEqual(appels, [])

    def test_resolveur_en_echec_retombe_sur_les_defauts(self):
        def resolveur(company, nom):
            raise RuntimeError('registre en panne')

        score_params.register_params_resolver(resolveur)
        with self.assertLogs('core.score_params', level='ERROR'):
            self.assertEqual(
                score_params.params_actifs(SocieteFictive(), 'churn'), {})

    def test_valeur_non_mappable_ignoree(self):
        score_params.register_params_resolver(lambda c, n: 42)
        with self.assertLogs('core.score_params', level='WARNING'):
            self.assertEqual(
                score_params.params_actifs(SocieteFictive(), 'churn'), {})

    def test_liste_blanche_refuse_une_cle_inconnue(self):
        score_params.register_params_resolver(
            lambda c, n: {'CLE_INVENTEE': 999, 'poids': 0.5})
        effectifs = score_params.resoudre(
            SocieteFictive(), 'churn', {'poids': 0.1})
        self.assertEqual(effectifs, {'poids': 0.5})
        self.assertNotIn('CLE_INVENTEE', effectifs)

    def test_conversion_au_type_du_defaut(self):
        score_params.register_params_resolver(
            lambda c, n: {'entier': '7', 'reel': '0.25', 'drapeau': 'oui'})
        effectifs = score_params.resoudre(
            SocieteFictive(), 'churn',
            {'entier': 1, 'reel': 0.5, 'drapeau': False})
        self.assertEqual(effectifs['entier'], 7)
        self.assertEqual(effectifs['reel'], 0.25)
        self.assertIs(effectifs['drapeau'], True)

    def test_valeur_intypable_garde_le_defaut(self):
        score_params.register_params_resolver(
            lambda c, n: {'reel': 'beaucoup'})
        self.assertEqual(
            score_params.resoudre(SocieteFictive(), 'churn', {'reel': 0.5}),
            {'reel': 0.5})

    def test_table_fusionnee_sur_ses_seules_cles_connues(self):
        score_params.register_params_resolver(
            lambda c, n: {'table': {'NEW': 0.5, 'INVENTEE': 0.9}})
        effectifs = score_params.resoudre(
            SocieteFictive(), 'win_proba',
            {'table': {'NEW': 0.10, 'SIGNED': 1.0}})
        self.assertEqual(effectifs['table'],
                         {'NEW': 0.5, 'SIGNED': 1.0})

    def test_resoudre_ne_mute_jamais_la_table_de_defauts(self):
        score_params.register_params_resolver(lambda c, n: {'poids': 0.9})
        defauts = {'poids': 0.1}
        score_params.resoudre(SocieteFictive(), 'churn', defauts)
        self.assertEqual(defauts, {'poids': 0.1})

    def test_valeur_resout_un_seul_seuil(self):
        score_params.register_params_resolver(lambda c, n: {'seuil': 5})
        self.assertEqual(
            score_params.valeur(SocieteFictive(), 'churn', 'seuil', 3), 5)
        self.assertEqual(
            score_params.valeur(None, 'churn', 'seuil', 3), 3)

    def test_les_cinq_scorers_sont_nommes(self):
        self.assertEqual(set(score_params.NOMS_SCORERS), {
            'churn', 'win_proba', 'retard_paiement', 'reappro', 'anomalie'})


class ScorersLisentLeursParamsTests(SimpleTestCase):
    """Chaque scorer lit sa version active, et retombe proprement sans elle."""

    def setUp(self):
        super().setUp()
        self.company = SocieteFictive()
        self.appels = []

    def tearDown(self):
        score_params.clear_params_resolver()
        super().tearDown()

    def _resolveur(self, par_nom):
        def resolveur(company, nom):
            self.appels.append(nom)
            return par_nom.get(nom, {})
        score_params.register_params_resolver(resolveur)

    def test_churn_lit_ses_poids_et_seuils(self):
        features = {'days_since_last_activity': 100, 'open_sav_tickets': 5}
        defaut = churn_risk(features)

        self._resolveur({score_params.NOM_CHURN: {
            # L'inactivité sature dix fois plus vite : le même client devient
            # nettement plus à risque.
            'INACTIVITY_SATURATION_DAYS': 36.5,
        }})
        calibre = churn_risk(features, company=self.company)

        self.assertEqual(self.appels, [score_params.NOM_CHURN])
        self.assertGreater(calibre.score, defaut.score)
        # Et sans société, le résultat reste EXACTEMENT celui d'avant.
        self.assertEqual(churn_risk(features).score, defaut.score)

    def test_churn_lit_les_seuils_de_bande(self):
        features = {'days_since_last_activity': 200}
        self.assertEqual(churn_risk(features).band, 'moyen')

        self._resolveur({score_params.NOM_CHURN: {
            'BAND_THRESHOLD_ELEVE': 0.5,
        }})
        self.assertEqual(
            churn_risk(features, company=self.company).band, 'élevé')

    def test_churn_repli_lit_son_risque_par_defaut(self):
        self._resolveur({score_params.NOM_CHURN: {'DEFAULT_RISK': 0.8}})
        resultat = churn_risk({}, company=self.company)
        self.assertTrue(resultat.used_fallback)
        self.assertEqual(resultat.score, 0.8)
        # Sans société : le repli historique, inchangé.
        self.assertEqual(churn_risk({}).score, 0.30)

    def test_win_probability_lit_sa_base_detape(self):
        features = {'stage': 'QUOTE_SENT'}
        self.assertEqual(win_probability(features).base, 0.40)

        self._resolveur({score_params.NOM_WIN_PROBA: {
            'STAGE_BASE_PROBABILITY': {'QUOTE_SENT': 0.70},
        }})
        calibre = win_probability(features, company=self.company)
        self.assertEqual(self.appels, [score_params.NOM_WIN_PROBA])
        self.assertEqual(calibre.base, 0.70)
        # Les autres étapes gardent la table du code.
        self.assertEqual(
            win_probability({'stage': 'NEW'}, company=self.company).base, 0.10)

    def test_win_probability_lit_son_plafond_de_relances(self):
        features = {'stage': 'QUOTE_SENT', 'relances': 10}
        self.assertEqual(win_probability(features).factors['relances_bonus'],
                         0.12)

        self._resolveur({score_params.NOM_WIN_PROBA: {
            'RELANCE_BONUS_CAP': 0.30,
        }})
        self.assertEqual(
            win_probability(features, company=self.company)
            .factors['relances_bonus'], 0.30)

    def test_payment_delay_lit_sa_saturation(self):
        features = {'days_overdue': 30}
        defaut = payment_delay_risk(features)

        self._resolveur({score_params.NOM_RETARD_PAIEMENT: {
            'OVERDUE_SATURATION_DAYS': 30.0,
        }})
        calibre = payment_delay_risk(features, company=self.company)
        self.assertEqual(self.appels, [score_params.NOM_RETARD_PAIEMENT])
        self.assertEqual(calibre.score, 1.0)
        self.assertLess(defaut.score, 1.0)
        self.assertEqual(payment_delay_risk(features).score, defaut.score)

    def test_reappro_lit_son_cycle_de_commande(self):
        import datetime
        commun = {
            'current_stock': 10,
            'today': datetime.date(2026, 9, 19),
            'avg_daily_consumption': 1.0,
            'lead_time_days': 5,
        }
        defaut = predict_reorder(**commun)

        self._resolveur({score_params.NOM_REAPPRO: {
            'DEFAULT_REVIEW_PERIOD_DAYS': 60.0,
        }})
        calibre = predict_reorder(company=self.company, **commun)
        self.assertEqual(self.appels, [score_params.NOM_REAPPRO])
        self.assertGreater(calibre.suggested_quantity,
                           defaut.suggested_quantity)

        # Un argument passé EXPLICITEMENT l'emporte sur la configuration.
        explicite = predict_reorder(
            company=self.company, review_period_days=30.0, **commun)
        self.assertEqual(explicite.suggested_quantity,
                         defaut.suggested_quantity)

    def test_anomalie_lit_son_seuil_de_z_score(self):
        points = [{'id': str(i), 'value': v}
                  for i, v in enumerate([10, 10, 10, 10, 13])]
        self.assertEqual(scan_for_outliers(points), [])

        self._resolveur({score_params.NOM_ANOMALIE: {
            'DEFAULT_Z_THRESHOLD': 1.5,
        }})
        candidats = scan_for_outliers(points, company=self.company)
        self.assertEqual(self.appels, [score_params.NOM_ANOMALIE])
        self.assertEqual([c.subject_id for c in candidats], ['4'])

        # Un seuil passé EXPLICITEMENT — même 0.0 — l'emporte.
        self.assertEqual(
            len(scan_for_outliers(points, z_threshold=0.0,
                                  company=self.company)), len(points))

    def test_aucun_scorer_nappelle_le_resolveur_sans_societe(self):
        self._resolveur({})
        churn_risk({'open_sav_tickets': 1})
        win_probability({'stage': 'NEW'})
        payment_delay_risk({'days_overdue': 1})
        scan_for_outliers([{'id': '1', 'value': 1}])
        self.assertEqual(self.appels, [])
