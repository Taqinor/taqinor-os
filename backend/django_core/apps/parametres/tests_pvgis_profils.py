"""Profils PVGIS journaliers — chaîne de résolution, décalage UTC+1, épingles.

Les valeurs ÉPINGLÉES ici viennent du relevé PVGIS 5.3 du 21/08/2026 (13 villes
marocaines), aux URLs citées dans ``apps/parametres/pvgis_profils.py`` ::

    https://re.jrc.ec.europa.eu/api/v5_3/PVcalc?lat={lat}&lon={lon}
        &peakpower=1&loss=14&pvtechchoice=crystSi&outputformat=json
        &angle=30&aspect=0&mountingplace=free
    https://re.jrc.ec.europa.eu/api/v5_3/DRcalc?lat={lat}&lon={lon}
        &month={1|4|7}&angle=30&aspect=0&global=1&outputformat=json

AUCUN test ne touche le réseau : le seul point de sortie
(``_appel_pvgis``) est mocké partout où le chemin « live » est exercé.
"""
from unittest import mock

from django.core.cache import cache as django_cache
from django.test import SimpleTestCase

from apps.parametres import pvgis_profils as pp


def _payload_drcalc(pic_heure_utc=11):
    """Réponse DRcalc factice : profil 24 h avec un pic à l'heure demandée."""
    profil = []
    for h in range(24):
        gi = 0.0
        if 6 <= h <= 18:
            gi = max(0.0, 1000.0 - abs(h - pic_heure_utc) * 120.0)
        profil.append({'month': 1, 'time': '%02d:00' % h, 'G(i)': gi})
    return {'outputs': {'daily_profile': profil}}


def _payload_pvcalc(valeurs):
    return {'outputs': {'monthly': {
        'fixed': [{'month': i + 1, 'E_m': v} for i, v in enumerate(valeurs)]}}}


class TableReferenceTests(SimpleTestCase):
    """Intégrité du jeu de données committé (13 villes → 7 courbes)."""

    def test_treize_villes_sept_courbes(self):
        self.assertEqual(len(pp.PRODUCTIBLE_MENSUEL_VILLE), 13)
        self.assertEqual(len(pp.COURBES_REFERENCE), 7)

    def test_chaque_ville_pointe_sur_une_courbe_existante(self):
        for ville, entree in pp.PRODUCTIBLE_MENSUEL_VILLE.items():
            self.assertIn(entree['courbe'], pp.COURBES_REFERENCE, ville)
            self.assertEqual(len(entree['e_m']), 12, ville)
            self.assertTrue(all(v > 0 for v in entree['e_m']), ville)

    def test_somme_des_e_m_egale_le_e_y_pvgis(self):
        # Cohérence interne de la réponse PVcalc : les 12 E_m somment au E_y.
        for ville, entree in pp.PRODUCTIBLE_MENSUEL_VILLE.items():
            self.assertAlmostEqual(
                sum(entree['e_m']), entree['e_y'], delta=1.0, msg=ville)

    def test_chaque_courbe_a_24_valeurs_par_saison(self):
        for cle, courbe in pp.COURBES_REFERENCE.items():
            for saison in ('jan', 'avr', 'juil'):
                self.assertEqual(len(courbe[saison]), 24, (cle, saison))
                self.assertAlmostEqual(sum(courbe[saison]), 1.0, delta=0.005)

    def test_epingle_pic_janvier_casablanca(self):
        """ÉPINGLE PVGIS : part de l'énergie du jour à l'heure de pointe.

        DRcalc Casablanca (33.573, -7.59), mois 1 : le pic est à 12 h UTC et
        vaut 0,151 du total journalier. Toute dérive de plus de 0,002 signale
        une donnée retouchée à la main.
        """
        forme = pp.COURBES_REFERENCE['casa_atlantique']['jan']
        self.assertEqual(forme.index(max(forme)), 12)
        self.assertAlmostEqual(max(forme), 0.151, delta=0.002)

    def test_epingle_ordre_des_productibles_annuels(self):
        """ÉPINGLE PVGIS : classement E_y (PVcalc, 21/08/2026)."""
        attendu = [
            'dakhla', 'laayoune', 'ouarzazate', 'agadir', 'el jadida',
            'marrakech', 'casablanca', 'bouskoura', 'mohammedia', 'oujda',
            'rabat', 'fes', 'tanger',
        ]
        obtenu = sorted(pp.PRODUCTIBLE_MENSUEL_VILLE,
                        key=lambda v: -pp.PRODUCTIBLE_MENSUEL_VILLE[v]['e_y'])
        self.assertEqual(obtenu, attendu)
        # Les deux extrêmes, verbatim du relevé.
        self.assertAlmostEqual(
            pp.PRODUCTIBLE_MENSUEL_VILLE['dakhla']['e_y'], 1927.71, places=2)
        self.assertAlmostEqual(
            pp.PRODUCTIBLE_MENSUEL_VILLE['tanger']['e_y'], 1660.57, places=2)

    def test_saisons_couvrent_les_douze_mois_une_seule_fois(self):
        vus = []
        for saison in pp.SAISONS:
            vus.extend(pp.MOIS_PAR_SAISON[saison])
        self.assertEqual(sorted(vus), list(range(1, 13)))


class NormalisationVilleTests(SimpleTestCase):
    def test_accents_casse_et_espaces(self):
        for ecriture in ('Laâyoune', 'LAAYOUNE', '  laayoune  ', 'Layoune'):
            self.assertEqual(pp.cle_ville(ecriture), 'laayoune', ecriture)
        self.assertEqual(pp.cle_ville('El Jadida'), 'el jadida')
        self.assertEqual(pp.cle_ville('Fès'), 'fes')
        self.assertEqual(pp.cle_ville('Marrakesh'), 'marrakech')

    def test_ville_inconnue_reste_inconnue(self):
        # Q6 : jamais de « ville la plus proche » devinée.
        for inconnue in ('Ifrane', 'Chefchaouen', '', None, '   '):
            self.assertIsNone(pp.cle_ville(inconnue), repr(inconnue))
            self.assertFalse(pp.ville_connue(inconnue))


class DecalageHoraireTests(SimpleTestCase):
    def test_utc_plus_un_deplace_le_pic_de_12_a_13(self):
        forme_utc = pp.COURBES_REFERENCE['casa_atlantique']['jan']
        self.assertEqual(forme_utc.index(max(forme_utc)), 12)
        locale = pp.vers_heure_locale(forme_utc)
        self.assertEqual(locale.index(max(locale)), 13)
        self.assertAlmostEqual(sum(locale), sum(forme_utc), places=6)

    def test_ramadan_utc_zero_est_la_forme_brute(self):
        forme_utc = pp.COURBES_REFERENCE['casa_atlantique']['jan']
        self.assertEqual(pp.vers_heure_locale(forme_utc, 0), list(forme_utc))

    def test_forme_invalide_renvoie_none(self):
        self.assertIsNone(pp.vers_heure_locale(None))
        self.assertIsNone(pp.vers_heure_locale([0.5, 0.5]))


class MoyenneJournaliereTests(SimpleTestCase):
    def test_moyenne_des_quotidiens_pas_le_quotidien_des_moyennes(self):
        # 31 kWh en janvier (31 j) = 1,0/j ; 28 en février (28 j) = 1,0/j ;
        # 62 en décembre (31 j) = 2,0/j → moyenne d'hiver = 4/3.
        mensuel = [31.0, 28.0] + [0.0] * 9 + [62.0]
        self.assertAlmostEqual(
            pp.moyenne_journaliere_saison(mensuel, 'hiver'), 4.0 / 3.0, places=6)

    def test_serie_absente_ou_nulle_renvoie_none(self):
        self.assertIsNone(pp.moyenne_journaliere_saison([], 'hiver'))
        self.assertIsNone(pp.moyenne_journaliere_saison([1.0] * 11, 'hiver'))
        self.assertIsNone(pp.moyenne_journaliere_saison([0.0] * 12, 'hiver'))
        self.assertIsNone(pp.moyenne_journaliere_saison([1.0] * 12, 'automne'))


class ChaineResolutionTests(SimpleTestCase):
    """(a) coordonnées → live, (b) ville → référence, (c) inconnue → absent."""

    def setUp(self):
        django_cache.clear()

    def test_b_ville_connue_sert_la_courbe_de_reference(self):
        with mock.patch.object(pp, '_appel_pvgis') as reseau:
            resolu = pp.profil_production_journalier(
                saison='hiver', ville='Casablanca')
        reseau.assert_not_called()  # aucun appel réseau sans coordonnées
        forme, source = resolu
        self.assertEqual(source, 'pvgis_ville:casablanca')
        self.assertEqual(len(forme), 24)
        self.assertAlmostEqual(sum(forme), 1.0, places=4)
        self.assertEqual(forme.index(max(forme)), 12)  # stockée en UTC

    def test_b_villes_du_meme_groupe_partagent_la_courbe(self):
        casa = pp.profil_production_journalier(saison='ete', ville='Casablanca')
        rabat = pp.profil_production_journalier(saison='ete', ville='Rabat')
        self.assertEqual(casa, rabat)
        # Mais PAS le productible : le niveau reste par ville.
        self.assertNotEqual(
            pp.productible_mensuel(ville='Casablanca')[0],
            pp.productible_mensuel(ville='Rabat')[0])

    def test_c_ville_inconnue_sans_coordonnees_renvoie_none(self):
        self.assertIsNone(pp.profil_production_journalier(
            saison='hiver', ville='Ifrane'))
        self.assertIsNone(pp.profil_production_journalier(saison='hiver'))
        self.assertIsNone(pp.productible_mensuel(ville='Ifrane'))
        self.assertIsNone(pp.productible_mensuel())

    def test_saison_inconnue_renvoie_none(self):
        self.assertIsNone(pp.profil_production_journalier(
            saison='automne', ville='Casablanca'))

    def test_a_coordonnees_declenchent_le_live(self):
        with mock.patch.object(pp, '_appel_pvgis',
                               return_value=_payload_drcalc(11)) as reseau:
            forme, source = pp.profil_production_journalier(
                saison='hiver', lat=33.5, lon=-7.6, ville='Casablanca')
        self.assertEqual(source, 'pvgis_live')
        self.assertEqual(forme.index(max(forme)), 11)
        self.assertAlmostEqual(sum(forme), 1.0, places=4)
        # L'URL appelée est bien DRcalc, mois 1, avec les paramètres figés.
        url = reseau.call_args[0][0]
        self.assertIn('/DRcalc?', url)
        self.assertIn('month=1', url)
        self.assertIn('angle=30', url)
        self.assertIn('aspect=0', url)

    def test_a_saison_ete_demande_le_mois_7(self):
        with mock.patch.object(pp, '_appel_pvgis',
                               return_value=_payload_drcalc(12)) as reseau:
            pp.profil_production_journalier(saison='ete', lat=31.0, lon=-8.0)
        self.assertIn('month=7', reseau.call_args[0][0])

    def test_a_live_indisponible_retombe_sur_la_ville(self):
        with mock.patch.object(pp, '_appel_pvgis', return_value=None):
            forme, source = pp.profil_production_journalier(
                saison='hiver', lat=33.5, lon=-7.6, ville='Casablanca')
        self.assertEqual(source, 'pvgis_ville:casablanca')
        self.assertEqual(forme.index(max(forme)), 12)

    def test_a_live_indisponible_et_ville_inconnue_renvoie_none(self):
        with mock.patch.object(pp, '_appel_pvgis', return_value=None):
            self.assertIsNone(pp.profil_production_journalier(
                saison='hiver', lat=33.5, lon=-7.6, ville='Ifrane'))

    def test_coordonnees_nulles_ignorees(self):
        # (0, 0) = coordonnée non renseignée, pas l'Atlantique.
        with mock.patch.object(pp, '_appel_pvgis') as reseau:
            resolu = pp.profil_production_journalier(
                saison='hiver', lat=0, lon=0, ville='Tanger')
        reseau.assert_not_called()
        self.assertEqual(resolu[1], 'pvgis_ville:tanger')

    def test_productible_mensuel_live(self):
        valeurs = [100.0 + i for i in range(12)]
        with mock.patch.object(pp, '_appel_pvgis',
                               return_value=_payload_pvcalc(valeurs)) as reseau:
            servi, source = pp.productible_mensuel(lat=33.5, lon=-7.6)
        self.assertEqual(servi, valeurs)
        self.assertEqual(source, 'pvgis_live')
        self.assertIn('/PVcalc?', reseau.call_args[0][0])

    def test_productible_mensuel_par_ville(self):
        valeurs, source = pp.productible_mensuel(ville='Agadir')
        self.assertEqual(source, 'pvgis_ville:agadir')
        self.assertEqual(valeurs,
                         pp.PRODUCTIBLE_MENSUEL_VILLE['agadir']['e_m'])
        # Copie : le consommateur ne peut pas muter la table de référence.
        valeurs[0] = 0.0
        self.assertNotEqual(
            pp.PRODUCTIBLE_MENSUEL_VILLE['agadir']['e_m'][0], 0.0)

    def test_reponse_pvgis_malformee_retombe_sur_la_ville(self):
        for mauvais in ({}, {'outputs': {}},
                        {'outputs': {'daily_profile': []}},
                        {'outputs': {'daily_profile': [{'time': 'x'}] * 24}}):
            with mock.patch.object(pp, '_appel_pvgis', return_value=mauvais):
                resolu = pp.profil_production_journalier(
                    saison='hiver', lat=33.5, lon=-7.6, ville='Casablanca')
            self.assertEqual(resolu[1], 'pvgis_ville:casablanca', mauvais)


class CacheTests(SimpleTestCase):
    def setUp(self):
        django_cache.clear()

    def test_second_appel_meme_point_ne_retouche_pas_le_reseau(self):
        with mock.patch.object(pp, '_appel_pvgis',
                               return_value=_payload_drcalc(11)) as reseau:
            pp.profil_production_journalier(saison='hiver', lat=33.5, lon=-7.6)
            self.assertEqual(reseau.call_count, 1)
            pp.profil_production_journalier(saison='hiver', lat=33.5, lon=-7.6)
            self.assertEqual(reseau.call_count, 1)

    def test_cache_systeme_jamais_scope_societe(self):
        from core import cache as tenant_cache
        with mock.patch.object(pp, '_appel_pvgis',
                               return_value=_payload_drcalc(11)):
            pp.profil_horaire_live(33.5, -7.6, 1)
        cle = 'pvgis:drprofil:33.500:-7.600:1'
        self.assertIsNotNone(tenant_cache.get(None, cle))
        self.assertIsNone(tenant_cache.get(1, cle))

    def test_coupe_circuit_evite_les_timeouts_en_cascade(self):
        """PVGIS injoignable : UN seul aller-retour, pas un par saison."""
        import urllib.error

        with mock.patch('urllib.request.urlopen',
                        side_effect=urllib.error.URLError('offline')) as urlopen:
            for saison in pp.SAISONS:
                resolu = pp.profil_production_journalier(
                    saison=saison, lat=33.5, lon=-7.6, ville='Casablanca')
                self.assertEqual(resolu[1], 'pvgis_ville:casablanca')
        self.assertEqual(urlopen.call_count, 1)
