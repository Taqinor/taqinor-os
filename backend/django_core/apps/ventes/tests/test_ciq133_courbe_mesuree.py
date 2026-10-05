"""CIQ133 — une courbe de charge MESURÉE (export du compteur) alimente le même
moteur : jours types par mois × type de jour × heure, ``niveau_donnees =
mesure`` ; mois non mesurés complétés par les kWh déclarés (forme empruntée,
étiquetée) ; fichier illisible ⇒ 400 FR nommant la colonne (parseur unique du
calepinage, ``apps.calepinage.services.apercu_courbe_csv``).
"""
import datetime
import unittest

from apps.ventes.moteur_ci.charge import courbe_mesuree_jours_types
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
