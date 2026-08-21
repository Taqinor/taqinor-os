"""Bloc ``courbes_journalieres`` de la proposition — niveaux réels, unités justes.

Le graphe « une journée type » de ``/proposition`` dessinait une cloche
SYNTHÉTIQUE et affichait son sommet en « kWh » alors que c'est une PUISSANCE.
Ces tests verrouillent le contrat serveur : formes PVGIS, niveaux tirés du
devis (kWc + factures réelles du lead), pic en kW, variantes batterie réelles,
drapeau d'occupation, et OMISSION quand la donnée manque.

Épingles PVGIS issues du relevé du 21/08/2026 (URLs citées dans
``apps/parametres/pvgis_profils.py`` : PVcalc et DRcalc v5.3, angle 30,
aspect 0, loss 14, crystSi). AUCUN accès réseau : les seuls chemins live sont
mockés, et les chemins testés ici passent par la table de référence.
"""
from unittest import mock

from django.core.cache import cache as django_cache
from django.test import SimpleTestCase

from apps.parametres import pvgis_profils as pp
from apps.ventes import courbes_journalieres as cj

CASA_CONSO = [900, 880, 860, 840, 900, 1100,
              1300, 1350, 1100, 900, 870, 910]


def _data(**extra):
    """Sortie ``build_quote_data`` minimale utile au graphe."""
    base = {
        'puissance_kwc': 10.0,
        'client_city': 'Casablanca',
        'mode_installation': 'residentiel',
        'sans_ok': True,
        'avec_ok': True,
        'deux_options': True,
        'batterie_kwh_total': 10.0,
    }
    base.update(extra)
    return base


class _CourbesBase(SimpleTestCase):
    def setUp(self):
        django_cache.clear()
        # Pas de lead → pas de GPS : la chaîne passe par la ville (aucun réseau).
        patch_loc = mock.patch(
            'apps.crm.selectors.site_location_for_devis',
            return_value={'site_adresse': None, 'site_ville': None,
                          'gps_lat': None, 'gps_lng': None})
        patch_profil = mock.patch(
            'apps.crm.selectors.profil_activite_pour_devis', return_value=None)
        self.loc = patch_loc.start()
        self.profil = patch_profil.start()
        self.addCleanup(patch_loc.stop)
        self.addCleanup(patch_profil.stop)

    def _bloc(self, data=None, conso=None):
        return cj.construire_courbes_journalieres(
            object(), _data() if data is None else data,
            monthly_consumption=conso)


class ProductionTests(_CourbesBase):
    def test_niveau_reel_productible_pvgis_fois_kwc(self):
        bloc = self._bloc(conso=CASA_CONSO)
        hiver = bloc['production']['hiver']
        attendu = pp.moyenne_journaliere_saison(
            pp.PRODUCTIBLE_MENSUEL_VILLE['casablanca']['e_m'], 'hiver') * 10.0
        self.assertAlmostEqual(hiver['kwh_jour'], round(attendu, 1), places=6)
        # Épingle : 10 kWc à Casablanca en hiver ≈ 40,7 kWh/jour (PVcalc).
        self.assertAlmostEqual(hiver['kwh_jour'], 40.7, delta=0.2)
        # L'été produit plus que l'hiver — sinon la saisonnalité est inversée.
        self.assertGreater(bloc['production']['ete']['kwh_jour'],
                           hiver['kwh_jour'])

    def test_pic_est_une_puissance_kw_pas_une_energie(self):
        bloc = self._bloc(conso=CASA_CONSO)
        for saison, serie in bloc['production'].items():
            attendu = serie['kwh_jour'] * max(serie['forme'])
            self.assertAlmostEqual(serie['pic_kw'], attendu,
                                   delta=0.02, msg=saison)
            # Une puissance de pointe reste très en-dessous de l'énergie du
            # jour : c'est exactement la confusion que l'ancien libellé faisait.
            self.assertLess(serie['pic_kw'], serie['kwh_jour'])
        self.assertEqual(bloc['unites']['pic_kw'], 'kW')

    def test_aucune_cle_de_pic_libellee_en_kwh(self):
        bloc = self._bloc(conso=CASA_CONSO)
        for serie in bloc['production'].values():
            for cle in serie:
                if 'pic' in cle:
                    self.assertTrue(cle.endswith('_kw'), cle)
                    self.assertFalse(cle.endswith('_kwh'), cle)

    def test_forme_servie_en_heure_locale_utc_plus_un(self):
        bloc = self._bloc(conso=CASA_CONSO)
        forme = bloc['production']['hiver']['forme']
        self.assertEqual(len(forme), 24)
        self.assertAlmostEqual(sum(forme), 1.0, places=4)
        # PVGIS place le pic de janvier à 12 h UTC → 13 h en heure marocaine.
        self.assertEqual(forme.index(max(forme)), 13)
        self.assertEqual(
            forme, pp.vers_heure_locale(
                pp.profil_production_journalier(
                    saison='hiver', ville='Casablanca')[0]))

    def test_source_tracable(self):
        bloc = self._bloc(conso=CASA_CONSO)
        hiver = bloc['production']['hiver']
        self.assertEqual(hiver['source'], 'pvgis_ville:casablanca')
        self.assertEqual(hiver['source_productible'], 'pvgis_ville:casablanca')

    def test_gps_du_lead_declenche_le_live_mocke(self):
        self.loc.return_value = {'site_adresse': None, 'site_ville': 'Casablanca',
                                 'gps_lat': 33.5, 'gps_lng': -7.6}
        profil = [{'month': 1, 'time': '%02d:00' % h,
                   'G(i)': (900.0 if h == 11 else (100.0 if 7 <= h <= 17 else 0.0))}
                  for h in range(24)]
        pvcalc = {'outputs': {'monthly': {'fixed': [
            {'month': i + 1, 'E_m': 150.0} for i in range(12)]}}}

        def _reponse(url):
            return pvcalc if '/PVcalc?' in url else {
                'outputs': {'daily_profile': profil}}

        with mock.patch.object(pp, '_appel_pvgis', side_effect=_reponse):
            bloc = self._bloc(conso=CASA_CONSO)
        hiver = bloc['production']['hiver']
        self.assertEqual(hiver['source'], 'pvgis_live')
        self.assertEqual(hiver['source_productible'], 'pvgis_live')
        # 150 kWh/mois sur 31/31/28 jours × 10 kWc ≈ 50,1 kWh/jour.
        self.assertAlmostEqual(hiver['kwh_jour'], 50.1, delta=0.2)
        # Pic à 11 h UTC → 12 h locale.
        self.assertEqual(hiver['forme'].index(max(hiver['forme'])), 12)

    def test_ville_inconnue_omet_la_production(self):
        # Q6 — jamais de courbe devinée pour une ville hors table.
        bloc = self._bloc(_data(client_city='Ifrane'), conso=CASA_CONSO)
        self.assertNotIn('production', bloc)
        self.assertIn('consommation', bloc)

    def test_puissance_inconnue_omet_la_production(self):
        bloc = self._bloc(_data(puissance_kwc=None), conso=CASA_CONSO)
        self.assertNotIn('production', bloc)


class ConsommationTests(_CourbesBase):
    def test_niveau_reel_par_saison_depuis_les_factures(self):
        bloc = self._bloc(conso=CASA_CONSO)
        for saison in pp.SAISONS:
            attendu = pp.moyenne_journaliere_saison(CASA_CONSO, saison)
            self.assertAlmostEqual(bloc['consommation'][saison]['kwh_jour'],
                                   round(attendu, 1), places=6, msg=saison)
        # L'été consomme plus (climatisation) : la série le dit, pas nous.
        self.assertGreater(bloc['consommation']['ete']['kwh_jour'],
                           bloc['consommation']['hiver']['kwh_jour'])

    def test_la_forme_24h_de_consommation_reste_cote_page(self):
        bloc = self._bloc(conso=CASA_CONSO)
        for serie in bloc['consommation'].values():
            self.assertEqual(list(serie), ['kwh_jour'])

    def test_sans_facture_pas_de_consommation(self):
        for vide in (None, [], [1, 2, 3]):
            bloc = self._bloc(conso=vide)
            self.assertNotIn('consommation', bloc, repr(vide))


class OptionsEtBatterieTests(_CourbesBase):
    def test_deux_options(self):
        bloc = self._bloc(conso=CASA_CONSO)
        self.assertEqual(bloc['options'], ['sans', 'avec'])
        self.assertEqual(bloc['batterie_kwh'], 10.0)

    def test_option_sans_batterie_seule(self):
        bloc = self._bloc(
            _data(avec_ok=False, deux_options=False, batterie_kwh_total=None),
            conso=CASA_CONSO)
        self.assertEqual(bloc['options'], ['sans'])
        self.assertNotIn('batterie_kwh', bloc)

    def test_option_avec_batterie_seule(self):
        bloc = self._bloc(
            _data(sans_ok=False, deux_options=False, batterie_kwh_total=15.0),
            conso=CASA_CONSO)
        self.assertEqual(bloc['options'], ['avec'])
        self.assertEqual(bloc['batterie_kwh'], 15.0)

    def test_mono_option_hybride_sans_batterie_suit_le_stockage_reel(self):
        bloc = self._bloc(
            _data(deux_options=False, batterie_kwh_total=None),
            conso=CASA_CONSO)
        self.assertEqual(bloc['options'], ['sans'])

    def test_aucune_option_valide_omet_la_cle(self):
        bloc = self._bloc(
            _data(sans_ok=False, avec_ok=False, deux_options=False,
                  batterie_kwh_total=None),
            conso=CASA_CONSO)
        self.assertNotIn('options', bloc)


class OccupationTests(_CourbesBase):
    def test_residentiel_present_en_journee_par_defaut(self):
        """Décision terrain du fondateur (21/08/2026), pas une statistique."""
        bloc = self._bloc(conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'presence_jour')
        self.assertEqual(bloc['occupation_source'],
                         'defaut_residentiel_fondateur')

    def test_non_residentiel_absent_par_defaut(self):
        bloc = self._bloc(_data(mode_installation='industriel'),
                          conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'absence_jour')
        self.assertEqual(bloc['occupation_source'], 'defaut_non_residentiel')

    def test_profil_activite_pro_declare_prime_sur_le_defaut(self):
        self.profil.return_value = 'day'
        bloc = self._bloc(_data(mode_installation='commercial'),
                          conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'presence_jour')
        self.assertEqual(bloc['occupation_source'], 'lead_profil_activite:day')

    def test_mode_inconnu_traite_comme_non_residentiel(self):
        bloc = self._bloc(_data(mode_installation=None), conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'absence_jour')


class OmissionTests(_CourbesBase):
    def test_rien_a_servir_renvoie_none(self):
        # Ville inconnue ET aucune facture → la page garde son affichage actuel.
        self.assertIsNone(self._bloc(_data(client_city='Ifrane'), conso=[]))

    def test_note_horaire_dit_le_cas_ramadan(self):
        bloc = self._bloc(conso=CASA_CONSO)
        self.assertIn('UTC+1', bloc['note_horaire'])
        self.assertIn('Ramadan', bloc['note_horaire'])

    def test_donnee_illisible_ne_casse_jamais_la_page(self):
        self.assertIsNone(cj.construire_courbes_journalieres(
            object(), None, monthly_consumption=None))
