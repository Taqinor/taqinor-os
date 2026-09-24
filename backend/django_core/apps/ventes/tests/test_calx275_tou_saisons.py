"""CALX275 — tranches horaires découpées PAR SAISON.

Ce qui est prouvé ici :

* ``{'annuel': [...], 'ete': [...]}`` ⇒ une heure d'août prend le libellé
  d'été, une heure de mars prend celui d'``annuel`` ;
* ``{'ete': [...]}`` seul ⇒ une heure de mars est publiée ``tranche: None``
  avec son motif (jamais « pleine » par défaut), et le surplus de mars sort
  des tranches (``non_attribue``) avec une économie omise ;
* liste plate ⇒ comportement d'aujourd'hui, terme à terme (même résultat
  qu'avant CALX275, et identique à ``{'annuel': liste}``) ;
* la validation société accepte le découpage par saison et refuse une
  saison inconnue en la nommant ;
* les saisons admises sont EXACTEMENT celles des profils de consommation
  (``ProfilTypeConsommation.SAISONS``) — verrou CI.

Run :
    python manage.py test apps.ventes.tests.test_calx275_tou_saisons -v2
"""
import datetime
import unittest

from django.test import SimpleTestCase

from apps.parametres import tariff
from apps.ventes import solar_design as sd

ANNUEL = ['creuse'] * 8 + ['pleine'] * 10 + ['pointe'] * 4 + ['pleine'] * 2
ETE = ['creuse'] * 8 + ['pleine'] * 11 + ['pointe'] * 4 + ['pleine']
TARIFS = {'pointe': 2.0, 'pleine': 1.0, 'creuse': 0.5}


def _heure_288(mois, heure):
    """Index d'une heure dans une courbe 288 h (12 journées types)."""
    return (mois - 1) * 24 + heure


class TranchesDuMoisTest(unittest.TestCase):
    def test_aout_prend_ete_et_mars_prend_annuel(self):
        tou = {'annuel': ANNUEL, 'ete': ETE}
        aout = sd.tranches_du_mois(tou, 8)
        mars = sd.tranches_du_mois(tou, 3)
        # 18 h : « pleine » en été (ETE), « pointe » dans l'annuel.
        self.assertEqual(aout[18]['tranche'], 'pleine')
        self.assertEqual(aout[18]['saison'], 'ete')
        self.assertEqual(mars[18]['tranche'], 'pointe')
        self.assertEqual(mars[18]['saison'], 'annuel')

    def test_ete_seul_mars_publie_tranche_nulle_avec_motif(self):
        mars = sd.tranches_du_mois({'ete': ETE}, 3)
        self.assertEqual(len(mars), 24)
        for entree in mars:
            self.assertIsNone(entree['tranche'])
            self.assertIn('printemps', entree['motif'])
            self.assertIn('tou_heures', entree['motif'])
        # Jamais « pleine » par défaut.
        self.assertNotIn('pleine', {e['tranche'] for e in mars})

    def test_liste_plate_meme_tranche_tous_les_mois(self):
        for mois in range(1, 13):
            self.assertEqual(
                [e['tranche'] for e in sd.tranches_du_mois(ANNUEL, mois)],
                ANNUEL)


class NetMeteringSaisonsTest(unittest.TestCase):
    def _courbes_288(self, mois, heure, kwh=4.0):
        inj = [0.0] * 288
        imp = [0.0] * 288
        inj[_heure_288(mois, heure)] = kwh
        imp[_heure_288(mois, heure)] = kwh
        return inj, imp

    def test_heure_d_aout_valorisee_au_libelle_d_ete(self):
        inj, imp = self._courbes_288(8, 18)
        res = sd.net_metering_savings(
            injected_curve=inj, import_curve=imp, days_per_year=1,
            hour_tranches={'annuel': ANNUEL, 'ete': ETE},
            tranche_tariffs=TARIFS)
        self.assertEqual(res['tranches']['pleine']['compensated_kwh'], 4.0)
        self.assertEqual(res['tranches']['pointe']['compensated_kwh'], 0.0)
        self.assertEqual(res['economie'], 4.0)   # 4 kWh × 1,00 (pleine)

    def test_heure_de_mars_valorisee_au_libelle_annuel(self):
        inj, imp = self._courbes_288(3, 18)
        res = sd.net_metering_savings(
            injected_curve=inj, import_curve=imp, days_per_year=1,
            hour_tranches={'annuel': ANNUEL, 'ete': ETE},
            tranche_tariffs=TARIFS)
        self.assertEqual(res['tranches']['pointe']['compensated_kwh'], 4.0)
        self.assertEqual(res['economie'], 8.0)   # 4 kWh × 2,00 (pointe)

    def test_ete_seul_le_surplus_de_mars_est_non_attribue(self):
        inj, imp = self._courbes_288(3, 18)
        res = sd.net_metering_savings(
            injected_curve=inj, import_curve=imp, days_per_year=1,
            hour_tranches={'ete': ETE}, tranche_tariffs=TARIFS)
        self.assertEqual(res['non_attribue']['injected_kwh'], 4.0)
        self.assertIsNone(res['non_attribue']['tranche'])
        self.assertIn('printemps', res['non_attribue']['motif'])
        self.assertIsNone(res['economie'])
        self.assertEqual(res['motif'], res['non_attribue']['motif'])
        # Aucune tranche n'a reçu l'énergie de mars.
        self.assertEqual(res['compensated_kwh'], 0.0)

    def test_annee_8760_mois_deduit_du_calendrier(self):
        inj = [0.0] * 8760
        jour_15_aout = sum((31, 28, 31, 30, 31, 30, 31)) + 14
        inj[jour_15_aout * 24 + 18] = 4.0
        res = sd.net_metering_savings(
            injected_curve=inj, import_curve=inj, days_per_year=1,
            hour_tranches={'annuel': ANNUEL, 'ete': ETE},
            tranche_tariffs=TARIFS)
        self.assertEqual(res['tranches']['pleine']['compensated_kwh'], 4.0)

    def test_liste_plate_terme_a_terme_comme_aujourd_hui(self):
        inj, imp = self._courbes_288(3, 18)
        inj[_heure_288(8, 7)] = 2.0
        imp[_heure_288(8, 7)] = 1.0
        plate = sd.net_metering_savings(
            injected_curve=inj, import_curve=imp, days_per_year=1,
            hour_tranches=ANNUEL, tranche_tariffs=TARIFS)
        annuelle = sd.net_metering_savings(
            injected_curve=inj, import_curve=imp, days_per_year=1,
            hour_tranches={'annuel': ANNUEL}, tranche_tariffs=TARIFS)
        self.assertEqual(plate['tranches'], annuelle['tranches'])
        self.assertEqual(plate['economie'], annuelle['economie'])
        # Valeurs d'aujourd'hui : pointe 4 × 2,00 + creuse 1 × 0,50 = 8,50.
        self.assertEqual(plate['economie'], 8.5)
        self.assertEqual(plate['non_attribue']['heures'], 0)


class ValidationSaisonsTest(unittest.TestCase):
    SOURCE = 'Contrat de test (jeu d’essai)'
    DATE = datetime.date(2026, 5, 8)

    def test_decoupage_par_saison_accepte_et_normalise(self):
        heures = {'annuel': ANNUEL, 'ete': [h.upper() for h in ETE]}
        self.assertEqual(
            tariff.erreurs_tou(heures, TARIFS, self.SOURCE, self.DATE), {})

        class Reglages:
            tou_heures = heures
            tou_tarifs = TARIFS
            tou_source = self.SOURCE
            tou_date_source = self.DATE
        tou = tariff.tou_depuis_reglages(Reglages())
        self.assertEqual(tou['heures']['ete'], ETE)
        self.assertEqual(tou['heures']['annuel'], ANNUEL)

    def test_saison_inconnue_refusee_en_la_nommant(self):
        erreurs = tariff.erreurs_tou(
            {'mousson': ANNUEL}, TARIFS, self.SOURCE, self.DATE)
        self.assertIn('tou_heures.mousson', erreurs['tou_heures'])

    def test_saison_de_longueur_fausse_refusee_en_la_nommant(self):
        erreurs = tariff.erreurs_tou(
            {'ete': ETE[:20]}, TARIFS, self.SOURCE, self.DATE)
        self.assertIn('tou_heures.ete', erreurs['tou_heures'])

    def test_mois_des_saisons_couvrent_l_annee_une_fois(self):
        mois = sorted(m for ms in tariff.MOIS_PAR_SAISON_TOU.values()
                      for m in ms)
        self.assertEqual(mois, list(range(1, 13)))
        self.assertEqual(tariff.saison_du_mois(8), 'ete')
        self.assertEqual(tariff.saison_du_mois(3), 'printemps')
        self.assertIsNone(tariff.saison_du_mois(None))


class SaisonsVerrouilleesAuxProfilsTest(SimpleTestCase):
    """Les saisons TOU sont celles des profils de consommation (CI)."""

    def test_saisons_identiques_a_profil_type_consommation(self):
        from apps.calepinage.models import ProfilTypeConsommation
        self.assertEqual(tuple(tariff.SAISONS_TOU),
                         tuple(ProfilTypeConsommation.SAISONS))
