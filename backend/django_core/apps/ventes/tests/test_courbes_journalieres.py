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


# ── L4 (extension fondateur, 21/08/2026) — occupation_jour du lead PRIME ─────
class OccupationLeadTests(_CourbesBase):
    """``crm.Lead.occupation_jour`` (script d'appel) PRIME sur tout le reste
    quand renseigné ; absent ⇒ comportement HISTORIQUE (``OccupationTests``
    ci-dessus, byte-identique — aucun mock de ``occupation_jour_pour_devis``
    n'est posé par ces tests-là, donc le VRAI sélecteur tourne sur
    ``object()`` et renvoie ``None``)."""

    def _bloc_occ(self, occ, data=None):
        with mock.patch('apps.crm.selectors.occupation_jour_pour_devis',
                        return_value=occ):
            return self._bloc(data=data, conso=CASA_CONSO)

    def test_partiel_prime_sur_le_defaut_residentiel(self):
        bloc = self._bloc_occ('partiel')
        self.assertEqual(bloc['occupation'], 'presence_partielle')
        self.assertEqual(bloc['occupation_source'], 'lead_occupation_jour:partiel')

    def test_absent_prime_sur_le_defaut_residentiel(self):
        bloc = self._bloc_occ('absent')
        self.assertEqual(bloc['occupation'], 'absence_jour')
        self.assertEqual(bloc['occupation_source'], 'lead_occupation_jour:absent')

    def test_present_prime_sur_le_defaut_non_residentiel(self):
        bloc = self._bloc_occ('present', _data(mode_installation='industriel'))
        self.assertEqual(bloc['occupation'], 'presence_jour')
        self.assertEqual(bloc['occupation_source'], 'lead_occupation_jour:present')

    def test_valeur_non_reconnue_ignoree_retombe_sur_le_defaut(self):
        bloc = self._bloc_occ('n_importe_quoi')
        self.assertEqual(bloc['occupation_source'], 'defaut_residentiel_fondateur')

    def test_absent_du_lead_comportement_historique_inchange(self):
        # Aucun mock posé : le VRAI sélecteur tourne sur object() (pas de
        # .lead) ⇒ None ⇒ repli identique à OccupationTests d'avant L4.
        bloc = self._bloc(conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'presence_jour')
        self.assertEqual(bloc['occupation_source'], 'defaut_residentiel_fondateur')


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


# ── L4 (21/08/2026) — Équipements du lead : couches sourcées de la courbe ────
class EquipementsTests(_CourbesBase):
    """``apps.crm.selectors.equipements_pour_devis`` mocké par test (comme
    ``site_location_for_devis``/``profil_activite_pour_devis`` ci-dessus) : la
    base ``_CourbesBase`` laisse le VRAI sélecteur tourner sur un ``object()``
    (aucun ``.lead``) ⇒ ``{}`` ⇒ tests existants byte-identiques (pinné par
    ``ConsommationTests.test_la_forme_24h_de_consommation_reste_cote_page``)."""

    def _bloc_equip(self, equip, data=None, conso=None):
        with mock.patch('apps.crm.selectors.equipements_pour_devis',
                        return_value=equip):
            return self._bloc(data=data, conso=CASA_CONSO if conso is None else conso)

    def test_aucun_equipement_ne_change_rien(self):
        bloc = self._bloc_equip({})
        self.assertNotIn('equipements', bloc)
        for saison in pp.SAISONS:
            attendu = round(pp.moyenne_journaliere_saison(CASA_CONSO, saison), 1)
            self.assertEqual(bloc['consommation'][saison]['kwh_jour'], attendu)

    def test_piscine_avec_puissance_reelle_redistribue_sans_changer_le_niveau(self):
        bloc = self._bloc_equip({'piscine': True, 'piscine_pompe_kw': 1.5})
        self.assertEqual(bloc['equipements']['piscine'], {
            'kw': 1.5,
            'heures': list(range(10, 18)),
            'saisons': ['ete'],
            'mode': 'redistribution',
            'source': 'memo_2026-08-21_etage2:piscine_bloc_10_18h',
        })
        # Redistribution PURE : le niveau kwh_jour reste EXACTEMENT celui des
        # factures — la piscine ne fait que déplacer la forme, jamais ajouter.
        for saison in pp.SAISONS:
            attendu = round(pp.moyenne_journaliere_saison(CASA_CONSO, saison), 1)
            self.assertEqual(bloc['consommation'][saison]['kwh_jour'], attendu,
                             msg=saison)

    def test_piscine_sans_puissance_ne_produit_aucune_couche(self):
        # Bool vrai mais AUCUNE grandeur réelle saisie ⇒ omission (jamais un
        # défaut de puissance inventé).
        bloc = self._bloc_equip({'piscine': True, 'piscine_pompe_kw': None})
        self.assertNotIn('equipements', bloc)

    def test_clim_kw_derive_du_nombre_de_pieces(self):
        bloc = self._bloc_equip({'clim': True, 'clim_pieces': 2})
        self.assertEqual(bloc['equipements']['clim'], {
            'kw': 2.8,  # 2 pièces × 1,4 kWh/h (mémo, 12000 BTU non-inverter)
            'heures': list(range(13, 21)),
            'saisons': ['ete'],
            'mode': 'redistribution',
            'source': 'memo_2026-08-21_etage2:clim_12000btu_1p4kwh_h',
        })

    def test_ve_ajoute_au_niveau_toutes_saisons(self):
        # 140 km/sem × 19,8 kWh/100 km ADEME ÷ 7 = 3,96 kWh/jour — la SEULE
        # couche qui change kwh_jour (charge future, absente des factures).
        bloc = self._bloc_equip(
            {'voiture_electrique': True, 've_km_semaine': 140})
        self.assertEqual(bloc['equipements']['ve'], {
            'kwh_jour': 3.96,
            'heures': [21, 22, 23, 0, 1, 2, 3, 4, 5],
            'saisons': None,
            'mode': 'addition',
            'source': 'memo_2026-08-21_etage2:ve_ademe_19_8kwh_100km',
        })
        for saison in pp.SAISONS:
            attendu = round(
                pp.moyenne_journaliere_saison(CASA_CONSO, saison) + 3.96, 1)
            self.assertEqual(bloc['consommation'][saison]['kwh_jour'], attendu,
                             msg=saison)

    def test_ve_sans_km_saisi_ne_produit_aucune_couche(self):
        # « PAS de défaut km, saisie obligatoire » (mémo) — bool seul n'ajoute
        # rien tant que le km/semaine réel n'est pas connu.
        bloc = self._bloc_equip(
            {'voiture_electrique': True, 've_km_semaine': None})
        self.assertNotIn('equipements', bloc)
        for saison in pp.SAISONS:
            attendu = round(pp.moyenne_journaliere_saison(CASA_CONSO, saison), 1)
            self.assertEqual(bloc['consommation'][saison]['kwh_jour'], attendu)

    def test_chauffe_eau_ne_produit_jamais_de_couche(self):
        # Aucune fenêtre/puissance sourcée pour le chauffe-eau (mémo : kWh/
        # personne/an sans champ « nombre de personnes ») — omission voulue,
        # même quand le booléen est vrai.
        bloc = self._bloc_equip({'chauffe_eau_electrique': True})
        self.assertNotIn('equipements', bloc)

    def test_plusieurs_couches_actives_coexistent(self):
        bloc = self._bloc_equip({
            'piscine': True, 'piscine_pompe_kw': 1.0,
            'clim': True, 'clim_pieces': 1,
            'voiture_electrique': True, 've_km_semaine': 70,
            'chauffe_eau_electrique': True,
        })
        self.assertEqual(set(bloc['equipements']), {'piscine', 'clim', 've'})

    def test_equipements_absent_sans_courbe_de_conso_a_ajuster(self):
        # Piscine renseignée mais AUCUNE facture ⇒ pas de bloc consommation
        # ⇒ rien à composer : la clé equipements reste absente.
        bloc = self._bloc_equip(
            {'piscine': True, 'piscine_pompe_kw': 1.5}, conso=[])
        self.assertNotIn('consommation', bloc)
        self.assertNotIn('equipements', bloc)
