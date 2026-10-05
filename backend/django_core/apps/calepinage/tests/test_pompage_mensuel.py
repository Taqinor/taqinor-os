"""AGR125 (ex-CAL157) — les 12 volumes du calepinage par le calcul du devis.

``m3_mois_pvgis`` porte désormais la production PHYSIQUE de
``core.pompage.volumes.production_mensuelle`` (heure par heure, lois de
similitude) — plus le volume plat × part mensuelle PVGIS. Ce qui est prouvé
ici, sur des VALEURS PHYSIQUES EXACTES (jamais une tolérance) :

* champ largement dimensionné (P ≥ P_plaque dès la première heure
  ensoleillée) ⇒ la pompe tourne à pleine vitesse à chaque heure de soleil :
  m³/jour = débit à la HMT × heures ensoleillées, au m³ près ;
* le m³/jour PLAT historique (débit × heures) reste PUBLIÉ à côté, jamais
  remplacé en silence, avec l'écart mois par mois ;
* site sans profil PVGIS ⇒ ``m3_mois_pvgis`` et ``source_irradiation`` à
  ``None``, le plat reste publié avec un avertissement explicite ;
* pompe SANS courbe ⇒ aucun volume, ni plat ni physique ;
* kWc inconnu ⇒ aucune production physique (jamais un volume inventé).

Run :
    python manage.py test apps.calepinage.tests.test_pompage_mensuel -v2
"""
import unittest

from apps.calepinage.services.pompage import JOURS_PAR_MOIS, volumes_mensuels
from core.pompage.volumes import production_mensuelle

#: Courbe de test : à 60 m de HMT la pompe débite EXACTEMENT 30 m³/h (point
#: de la courbe, aucune interpolation).
COURBE = {'debits_m3h': [0, 12, 24, 30, 36, 39],
          'hmt_m': [91, 85, 70, 60, 43, 34]}
#: Journée type de test : 13 heures ensoleillées (G > 0), 11 heures de nuit.
JOUR = [0] * 6 + [100, 300, 500, 700, 850, 950, 1000, 950, 850, 700, 500,
                  300, 100] + [0] * 5
PROFILS = [list(JOUR) for _ in range(12)]


def _volumes(**kwargs):
    entrees = dict(debit_hmt_m3h=30.0, pumping_hours=7, courbe_pompe=COURBE,
                   hmt_m=60, kwc=1000, p_plaque_kw=7.5, profils_horaires=PROFILS,
                   source_irradiation='pvgis_ville:agadir')
    entrees.update(kwargs)
    return volumes_mensuels(**entrees)


class VolumesMensuelsTest(unittest.TestCase):
    def test_valeurs_physiques_exactes_pleine_vitesse(self):
        # 1000 kWc × 100 W/m² = 100 kW ≫ 7,5 kW de plaque : n = 1 à chaque
        # heure ensoleillée ⇒ 30 m³/h × 13 h = 390 m³/jour.
        resultat = _volumes()
        self.assertEqual(resultat['m3_mois_pvgis'],
                         [390.0 * jours for jours in JOURS_PAR_MOIS])
        self.assertEqual(resultat['source_irradiation'], 'pvgis_ville:agadir')

    def test_meme_calcul_que_production_mensuelle(self):
        resultat = _volumes(kwc=9.94)
        production = production_mensuelle(
            kwc=9.94, profils_horaires=PROFILS, courbe_pompe=COURBE, hmt_m=60,
            p_plaque_kw=7.5)
        self.assertEqual(resultat['m3_mois_pvgis'],
                         [round(production['m3_jour_mois'][i] * JOURS_PAR_MOIS[i], 1)
                          for i in range(12)])
        # champ plus petit : vitesse réduite aux heures faibles ⇒ moins qu'à pleine vitesse
        self.assertLess(resultat['m3_mois_pvgis'][0], 390.0 * 31)

    def test_plat_jamais_remplace_en_silence(self):
        resultat = _volumes()
        self.assertEqual(resultat['m3_jour_plat'], 210.0)          # 30 m³/h × 7 h
        self.assertEqual(resultat['m3_mois_plat'][0], 210.0 * 31)
        self.assertEqual(resultat['ecart_m3_mois'][0], 390.0 * 31 - 210.0 * 31)

    def test_site_sans_profil_pvgis_rend_physique_none(self):
        resultat = _volumes(profils_horaires=None)
        self.assertIsNone(resultat['m3_mois_pvgis'])
        self.assertIsNone(resultat['source_irradiation'])
        self.assertIsNone(resultat['ecart_m3_mois'])
        self.assertIsNotNone(resultat['m3_mois_plat'])
        self.assertTrue(any('PVGIS' in w for w in resultat['warnings']))

    def test_pompe_sans_courbe_aucun_volume(self):
        resultat = _volumes(debit_hmt_m3h=None, courbe_pompe=None)
        self.assertIsNone(resultat['m3_jour_plat'])
        self.assertIsNone(resultat['m3_mois_plat'])
        self.assertIsNone(resultat['m3_mois_pvgis'])
        self.assertTrue(resultat['warnings'])

    def test_kwc_inconnu_aucune_production_inventee(self):
        resultat = _volumes(kwc=None)
        self.assertIsNone(resultat['m3_mois_pvgis'])
        self.assertIsNotNone(resultat['m3_mois_plat'])
        self.assertTrue(any('kWc' in w for w in resultat['warnings']))

    def test_ancien_calcul_supprime(self):
        from apps.calepinage.services import pompage
        self.assertFalse(hasattr(pompage, 'pompage_mensuel_pvgis'))


if __name__ == '__main__':
    unittest.main()
