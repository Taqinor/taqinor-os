"""CIQ133 — une courbe de charge MESURÉE (export du compteur) alimente le même
moteur : jours types par mois × type de jour × heure, ``niveau_donnees =
mesure`` ; mois non mesurés complétés par les kWh déclarés (forme empruntée,
étiquetée) ; fichier illisible ⇒ 400 FR nommant la colonne (parseur unique du
calepinage, ``apps.calepinage.services.apercu_courbe_csv``).
"""
import datetime
import unittest

from apps.ventes.moteur_ci.charge import (
    courbe_mesuree_jours_types, valeurs_horaires_depuis_points,
)
from apps.ventes.tests.test_ciq122_cas_reference import _etudier

ANNEE = 2025


def _serie(jours, debut=datetime.date(ANNEE, 1, 1)):
    """Courbe horaire synthétique : jour ouvré 8 h-18 h à 10 kWh, sinon 2 kWh ;
    week-end 2 kWh. Énergie connue jour par jour."""
    valeurs, par_mois = [], {}
    for i in range(jours):
        date = debut + datetime.timedelta(days=i)
        ouvre = date.weekday() < 5
        jour = [10.0 if ouvre and 8 <= h < 18 else 2.0 for h in range(24)]
        valeurs.extend(jour)
        par_mois[date.month] = par_mois.get(date.month, 0.0) + sum(jour)
    return valeurs, par_mois


def _energie(jours_types, mois):
    return sum(jt['nb_jours'] * sum(jt['charge_kwh']) for jt in jours_types if jt['mois'] == mois)


class CourbeMesureeTests(unittest.TestCase):

    def test_douze_mois_energie_mensuelle_egale_la_mesure(self):
        valeurs, par_mois = _serie(365)
        jours, prov, _al = courbe_mesuree_jours_types(
            valeurs, '%d-01-01' % ANNEE, annee_reference=ANNEE, source='export compteur')
        self.assertEqual(prov['methode'], 'courbe_mesuree')
        self.assertEqual(prov['niveau_donnees'], 'mesure')
        self.assertEqual(prov['couverture']['jours'], 365)
        for mois in range(1, 13):
            self.assertAlmostEqual(_energie(jours, mois), par_mois[mois], delta=1e-6)

    def test_trois_mois_mesures_completes_par_les_kwh_declares(self):
        valeurs, par_mois = _serie(90)   # janvier → mars
        kwh = [5000.0] * 12
        jours, prov, alertes = courbe_mesuree_jours_types(
            valeurs, '%d-01-01' % ANNEE, annee_reference=ANNEE, kwh_mensuels=kwh)
        self.assertEqual(prov['mois_forme_empruntee'], list(range(4, 13)))
        self.assertEqual(sum(1 for a in alertes if a['code'] == 'forme_empruntee'), 9)
        for mois in (1, 2, 3):
            self.assertAlmostEqual(_energie(jours, mois), par_mois[mois], delta=1e-6)
        for mois in range(4, 13):
            self.assertAlmostEqual(_energie(jours, mois), 5000.0, delta=1e-6)

    def test_orchestrateur_niveau_mesure(self):
        valeurs, _ = _serie(365)
        e = _etudier(courbe_mesuree={'pas_minutes': 60, 'points': valeurs,
                                     'debut': '%d-01-01' % ANNEE, 'source': 'export',
                                     'date': '2026-09-30'},
                     consommation={}, taille_explicite_kwc=40)
        self.assertEqual(e['profil_charge']['methode'], 'courbe_mesuree')
        self.assertEqual(e['niveau_donnees'], 'mesure')

    def test_decalage_constant_serie_2025_plateau_civil_8_18_devient_gmt_8_18(self):
        valeurs = []
        for _ in range(365):
            valeurs.extend([10.0 if 8 <= h < 18 else 1.0 for h in range(24)])
        jours, _prov, _al = courbe_mesuree_jours_types(
            valeurs, '%d-01-01' % ANNEE, annee_reference=ANNEE, decalage_h=0)
        for jt in jours:
            c = jt['charge_kwh']
            self.assertEqual([h for h in range(24) if c[h] > 5], list(range(8, 18)))

    def test_mois_partiel_niveau_moyenne_des_jours_mesures_fois_jours_du_mois(self):
        valeurs = [5.0] * (24 * 10)    # 10 jours de janvier à 5 kWh/h = 120 kWh/jour
        jours, _prov, alertes = courbe_mesuree_jours_types(
            valeurs, '%d-01-01' % ANNEE, annee_reference=ANNEE)
        self.assertAlmostEqual(_energie(jours, 1), 3720.0, delta=1e-6)
        alerte = next(a for a in alertes if a['code'] == 'mesure_incomplete')
        self.assertTrue(alerte['interne'])
        self.assertIn('10', alerte['message'])
        self.assertIn('31', alerte['message'])

    def test_jour_avec_valeur_absente_est_ecarte_pas_un_zero(self):
        valeurs = [5.0] * (24 * 10)
        valeurs[24 * 9 + 3] = None     # un trou dans le 10e jour
        jours, _prov, alertes = courbe_mesuree_jours_types(
            valeurs, '%d-01-01' % ANNEE, annee_reference=ANNEE)
        moyenne = sum(jt['nb_jours'] * sum(jt['charge_kwh']) for jt in jours
                      if jt['mois'] == 1) / 31
        self.assertAlmostEqual(moyenne, 120.0, delta=1e-6)    # pas 108
        self.assertIn('mesure_incomplete', {a['code'] for a in alertes})

    def test_points_json_meme_profil_aux_pas_60_30_15_meme_courbe_horaire(self):
        horaire = [float(1 + h % 5) for h in range(48)]
        pas30 = [v / 2 for v in horaire for _ in range(2)]
        pas15 = [v / 4 for v in horaire for _ in range(4)]
        pas5 = [v / 12 for v in horaire for _ in range(12)]
        for pas, points in ((60, horaire), (30, pas30), (15, pas15), (5, pas5)):
            sortie = valeurs_horaires_depuis_points(points, pas_min=pas, unite='kwh')
            for a, b in zip(sortie, horaire):
                self.assertAlmostEqual(a, b, places=9)
            self.assertEqual(len(sortie), 48)
        # en kW : moyenne de la puissance sur l'heure = kWh de l'heure
        kw30 = [v for v in horaire for _ in range(2)]
        sortie = valeurs_horaires_depuis_points(kw30, pas_min=30, unite='kw')
        for a, b in zip(sortie, horaire):
            self.assertAlmostEqual(a, b, places=9)

    def test_points_json_pas_invalide_ou_longueur_tronquee_refus_nomme(self):
        with self.assertRaises(ValueError) as ctx:
            valeurs_horaires_depuis_points([1.0] * 40, pas_min=45, unite='kwh')
        self.assertIn('45', str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            valeurs_horaires_depuis_points([1.0] * 7, pas_min=15, unite='kwh')
        self.assertIn('multiple', str(ctx.exception))

    def test_points_pas_30_agreges_a_l_heure(self):
        """CLD6 — orchestrateur : pas 30 en kWh (2 pas sommés) et en kW (moyenne)
        donnent la MÊME étude que les points horaires ; pas 7 ou 61 points au
        pas 15 ⇒ 400 FR sur ``courbe_mesuree``, plus de troncature."""
        from rest_framework.exceptions import ValidationError
        valeurs, _ = _serie(365)

        def etude(points, pas, unite='kwh'):
            return _etudier(courbe_mesuree={'pas_minutes': pas, 'points': points, 'unite': unite,
                                            'debut': '%d-01-01' % ANNEE, 'source': 'export',
                                            'date': '2026-09-30'},
                            consommation={}, taille_explicite_kwc=40)['profil_charge']

        reference = etude(valeurs, 60)
        for points, unite in (([v / 2 for v in valeurs for _ in range(2)], 'kwh'),
                              ([v for v in valeurs for _ in range(2)], 'kw')):
            profil = etude(points, 30, unite)
            self.assertEqual(profil['methode'], 'courbe_mesuree')
            for mois in range(1, 13):
                self.assertAlmostEqual(_energie(profil['jours_types'], mois),
                                       _energie(reference['jours_types'], mois), delta=1e-6)
        for points, pas, attendu in (([1.0] * 48, 7, '7 min'), ([1.0] * 61, 15, '61 points')):
            with self.assertRaises(ValidationError) as ctx:
                etude(points, pas)
            self.assertIn(attendu, str(ctx.exception.detail['courbe_mesuree'][0]))

    def test_fichier_illisible_400_nomme_la_colonne(self):
        from rest_framework.exceptions import ValidationError
        contenu = 'horodatage;conso\n2025-01-01 00:00;1,2\n2025-01-01 01:00;abc\n'
        with self.assertRaises(ValidationError) as ctx:
            _etudier(courbe_mesuree={'contenu': contenu, 'colonne': 'conso', 'source': 'csv'},
                     taille_explicite_kwc=40)
        detail = ctx.exception.detail
        self.assertIn('conso', str(detail['courbe_mesuree'][0]))


if __name__ == '__main__':
    unittest.main()
