"""CIQ108 — courbe de charge DÉCLARÉE en jours types (unittest pur, sans base)."""

import ast
import json
import os
import unittest

from apps.ventes.moteur_ci import charge
from apps.ventes.moteur_ci.charge import courbe_declaree

LUN_VEN = [True] * 5 + [False] * 2
TOUS = [True] * 7
# 2027 : Maroc à UTC+0 toute l'année (décret 2.26.530) ⇒ heure civile = GMT.
ANNEE = 2027


def _par(jours_types, mois, type_jour):
    return next(j for j in jours_types if j['mois'] == mois and j['type_jour'] == type_jour)


def _energie_mois(jours_types, mois):
    return sum(j['nb_jours'] * sum(j['charge_kwh']) for j in jours_types if j['mois'] == mois)


def _production_cloche():
    """Production de test PAR kWc (forme quelconque, diurne) — fixture, pas une donnée."""
    jour = [0.0] * 6 + [0.2, 0.4, 0.6, 0.8, 0.9, 1.0, 1.0, 0.9, 0.8, 0.6, 0.4, 0.2] + [0.0] * 6
    return [{'mois': m, 'production_kwh_kwc': list(jour)} for m in range(1, 13)]


class TestCourbeDeclaree(unittest.TestCase):

    def test_bureau_lun_ven_dimanche_talon(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]},
                  'talon': {'kw': 2.0}}
        jt, prov, _al = courbe_declaree(rythme, [10000] * 12, annee_reference=ANNEE, feries=[])
        self.assertEqual(prov['methode'], 'declare')
        dimanche = _par(jt, 3, 'ferme')
        for valeur in dimanche['charge_kwh']:
            self.assertAlmostEqual(valeur, 2.0)
        ouvre = _par(jt, 3, 'ouvre')
        self.assertAlmostEqual(ouvre['charge_kwh'][3], 2.0)      # nuit = talon
        self.assertGreater(ouvre['charge_kwh'][10], 2.0)          # plage chargée
        self.assertFalse(any(j['type_jour'] in ('samedi', 'dimanche') for j in jt))

    def test_ecole_fermee_ete_talon(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 17]]},
                  'fermetures': [{'du': '2027-07-01', 'au': '2027-08-31', 'motif': 'vacances'}],
                  'talon': {'kw': 1.5}}
        jt, _prov, _al = courbe_declaree(rythme, [4000] * 12, annee_reference=ANNEE, feries=[])
        for mois in (7, 8):
            types = {j['type_jour'] for j in jt if j['mois'] == mois}
            self.assertEqual(types, {'ferme'})
        self.assertIn('ouvre', {j['type_jour'] for j in jt if j['mois'] == 6})

    def test_3x8_continu_quasi_plat(self):
        rythme = {'jours_ouverts': TOUS, 'equipes': '3x8', 'talon': {'kw': 5.0}}
        jt, _prov, _al = courbe_declaree(rythme, [24000] * 12, annee_reference=ANNEE, feries=[])
        for j in jt:
            self.assertLess(max(j['charge_kwh']) - min(j['charge_kwh']), 1e-9)

    def test_somme_mois_egale_kwh_declares(self):
        kwh = [9800, 9200, 10100, 10800, 12500, 14800, 17200, 17600, 14900, 12100, 10200, 9900]
        rythme = {'jours_ouverts': [True] * 6 + [False],
                  'plages': {'ouvre': [[7.5, 19]], 'samedi': [[8, 13]]},
                  'talon': {'part_pct': 20}}
        jt, _prov, _al = courbe_declaree(rythme, kwh, annee_reference=ANNEE,
                                         feries=['2027-01-11', '2027-05-01'])
        for mois in range(1, 13):
            self.assertAlmostEqual(_energie_mois(jt, mois), kwh[mois - 1], delta=1e-6)
        # samedi : ses propres plages ; férié du 11/01 : jour fermé
        self.assertIn('samedi', {j['type_jour'] for j in jt if j['mois'] == 1})
        self.assertEqual(sum(j['nb_jours'] for j in jt if j['mois'] == 1
                             and j['type_jour'] == 'ferme'), 6)   # 5 dimanches + 1 férié

    def test_talon_inconnu_borne_conservatrice_et_alerte(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]}}
        production = _production_cloche()
        jt, prov, alertes = courbe_declaree(rythme, [10000] * 12, annee_reference=ANNEE,
                                            feries=[], production_jours_types=production)
        codes = {a['code'] for a in alertes}
        self.assertIn('talon_non_declare', codes)
        self.assertEqual(prov['talon']['statut'], 'borne_conservatrice')
        # bureau diurne : étaler sur 24 h donne MOINS d'autoconsommation que talon 0
        self.assertEqual(prov['bornes']['retenue'], 'etale_24h')
        for mois in range(1, 13):
            self.assertAlmostEqual(_energie_mois(jt, mois), 10000, delta=1e-6)
        # atelier de nuit : c'est le talon 0 (tout la nuit) qui est conservateur
        nuit = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[20, 6]]}}
        _jt, prov, _al = courbe_declaree(nuit, [10000] * 12, annee_reference=ANNEE,
                                         feries=[], production_jours_types=production)
        self.assertEqual(prov['bornes']['retenue'], 'talon_nul')

    def test_talon_inconnu_sans_production_rien_d_invente(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]}}
        jt, _prov, alertes = courbe_declaree(rythme, [10000] * 12, annee_reference=ANNEE, feries=[])
        self.assertIsNone(jt)
        self.assertIn('production_requise_pour_borne', {a['code'] for a in alertes})

    def test_jours_ouverts_non_declares_jamais_5_sur_7(self):
        rythme = {'plages': {'ouvre': [[8, 18]]}, 'talon': {'kw': 1}}
        jt, _prov, alertes = courbe_declaree(rythme, [1000] * 12, annee_reference=ANNEE, feries=[])
        self.assertIsNone(jt)
        self.assertIn('jours_ouverts_non_declares', {a['code'] for a in alertes})

    def test_archetype_seulement_sans_plage(self):
        jt, prov, alertes = courbe_declaree({}, 42000, annee_reference=ANNEE,
                                            archetype='bureau', feries=None)
        self.assertEqual(prov['methode'], 'archetype')
        self.assertEqual(prov['niveau_donnees'], 'estimation')
        self.assertEqual(prov['archetype']['cle'], 'bureau')
        self.assertEqual(prov['repartition'], 'annuel_prorata')
        total = sum(j['nb_jours'] * sum(j['charge_kwh']) for j in jt)
        self.assertAlmostEqual(total, 42000, delta=1e-6)
        codes = {a['code'] for a in alertes}
        self.assertIn('profil_estime', codes)
        self.assertIn('feries_non_saisis', codes)

    def test_sans_plage_ni_archetype_profil_exige(self):
        jt, _prov, alertes = courbe_declaree({'jours_ouverts': TOUS}, [1000] * 12,
                                             annee_reference=ANNEE, archetype='hammam', feries=[])
        self.assertIsNone(jt)
        self.assertIn('profil_declare_exige', {a['code'] for a in alertes})

    def test_heure_civile_vers_gmt_par_decalage_maroc(self):
        # janvier 2026 : UTC+1 (avant le décret) ⇒ 8 h civile = 7 h GMT
        rythme = {'jours_ouverts': TOUS, 'plages': {'ouvre': [[8, 9]]}, 'talon': {'kw': 0}}
        jt, prov, _al = courbe_declaree(rythme, [31] * 12, annee_reference=2026, feries=[],
                                        decalage_h='historique')
        self.assertEqual(prov['heures'], 'GMT')
        janvier = _par(jt, 1, 'ouvre')
        self.assertAlmostEqual(janvier['charge_kwh'][7], 1.0)
        self.assertAlmostEqual(janvier['charge_kwh'][8], 0.0)
        # novembre 2026 : UTC+0 ⇒ 8 h civile = 8 h GMT
        novembre = _par(jt, 11, 'ouvre')
        self.assertGreater(novembre['charge_kwh'][8], 0.0)
        self.assertAlmostEqual(novembre['charge_kwh'][7], 0.0)

    def test_mois_ferme_entier_rapport_archetype(self):
        # CAD177 (CIQ334) — hôtel, plages déclarées, talon NON déclaré (rapport
        # nuit/jour de l'archétype), fermeture du mois d'août entier.
        rythme = {'jours_ouverts': [True] * 6 + [False], 'plages': {'ouvre': [[8, 18]]},
                  'fermetures': [{'du': '2027-08-01', 'au': '2027-08-31', 'motif': 'annuelle'}]}
        kwh = [9800, 9200, 10100, 10800, 12500, 14800, 17200, 17600, 14900, 12100, 10200, 9900]
        # Facture d'août nulle (cohérente avec la fermeture) ⇒ charge nulle à
        # toute heure : la production d'août est entièrement en surplus.
        sans_facture = list(kwh)
        sans_facture[7] = 0
        jt, prov, alertes = courbe_declaree(rythme, sans_facture, annee_reference=ANNEE,
                                            archetype='hotel', feries=[])
        self.assertEqual(prov['talon']['statut'], 'estimation')
        aout = [j for j in jt if j['mois'] == 8]
        self.assertEqual({j['type_jour'] for j in aout}, {'ferme'})
        self.assertEqual(max(max(j['charge_kwh']) for j in aout), 0.0)
        self.assertNotIn('talon_incoherent', {a['code'] for a in alertes})
        # Facture d'août NON nulle malgré la fermeture : le niveau reste la
        # facture (Σ charge = kWh déclaré) mais la contradiction est DITE.
        jt, _prov, alertes = courbe_declaree(rythme, kwh, annee_reference=ANNEE,
                                             archetype='hotel', feries=[])
        self.assertAlmostEqual(_energie_mois(jt, 8), 17600, delta=1e-6)
        self.assertIn('talon_incoherent', {a['code'] for a in alertes})

    def test_mois_ferme_entier_bornes_alerte(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]},
                  'fermetures': [{'du': '2027-08-01', 'au': '2027-08-31', 'motif': 'annuelle'}]}
        _jt, prov, alertes = courbe_declaree(rythme, [10000] * 12, annee_reference=ANNEE,
                                             feries=[], production_jours_types=_production_cloche())
        self.assertEqual(prov['talon']['statut'], 'borne_conservatrice')
        self.assertIn('talon_incoherent', {a['code'] for a in alertes})

    def test_aucune_part_diurne(self):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]}, 'talon': {'kw': 2}}
        sortie = courbe_declaree(rythme, [10000] * 12, annee_reference=ANNEE, feries=[])
        texte = json.dumps(sortie)
        for interdit in ('part_diurne', 'day_share', 'dayPct'):
            self.assertNotIn(interdit, texte)


class TestTalonParTypeDeCommerce(unittest.TestCase):
    """Décision fondateur 26/10/2026 (lead 1637, boulangerie classée « autre »,
    7/7, 07–21 h, 6 000 kWh/mois) : horaires déclarés, talon NON déclaré ⇒ la
    courbe SUIT les horaires, talon par type de commerce (défaut fondateur 20 %)."""

    def _courbe(self, plages, categorie='autre', talon=None, segment='commercial'):
        rythme = {'jours_ouverts': TOUS, 'plages': {'ouvre': [plages]},
                  'categorie_commerciale': categorie}
        if talon is not None:
            rythme['talon'] = talon
        return courbe_declaree(rythme, [6000] * 12, annee_reference=ANNEE, archetype=categorie,
                               feries=[], production_jours_types=_production_cloche(),
                               segment=segment)

    def test_autre_suit_les_horaires_talon_defaut_fondateur(self):
        jt, prov, alertes = self._courbe([7, 21])
        self.assertEqual(prov['talon']['statut'], 'defaut_fondateur')
        self.assertIn('défaut fondateur (20 %)', prov['talon']['source'])
        self.assertIsNone(prov['bornes'])
        mars = _par(jt, 3, 'ouvre')['charge_kwh']
        self.assertAlmostEqual(mars[3] / mars[12], 0.20, places=9)   # nuit = 20 % du jour
        self.assertNotIn('talon_non_declare', {a['code'] for a in alertes})
        for mois in range(1, 13):
            self.assertAlmostEqual(_energie_mois(jt, mois), 6000, delta=1e-6)

    def test_regression_lead_1637_les_horaires_changent_la_courbe(self):
        jt_long, _p, _a = self._courbe([7, 21])
        jt_court, _p, _a = self._courbe([9, 18])
        self.assertNotEqual(_par(jt_long, 3, 'ouvre')['charge_kwh'],
                            _par(jt_court, 3, 'ouvre')['charge_kwh'])
        # À la taille de référence (production annuelle = consommation), la
        # journée plus courte et centrée sur le soleil autoconsomme PLUS.
        production = _production_cloche()
        prod_kwc = sum(j['nb_jours'] * sum(production[j['mois'] - 1]['production_kwh_kwc'])
                       for j in jt_long)
        kwc_ref = 6000 * 12 / prod_kwc
        self.assertGreater(charge._autoconso(jt_court, production, kwc_ref),
                           charge._autoconso(jt_long, production, kwc_ref))

    def test_talon_declare_passe_devant_le_defaut(self):
        _jt, prov, _al = self._courbe([7, 21], talon={'part_pct': 50})
        self.assertEqual(prov['talon'], {'valeur': {'part_pct': 50.0}, 'statut': 'declare'})

    def test_archetype_le_plus_proche_donne_le_talon(self):
        _jt, prov, _al = self._courbe([7, 21], categorie='supermarche')
        self.assertEqual(prov['talon']['statut'], 'estimation')
        self.assertIn('BDEW G3', prov['talon']['source'])
        self.assertIn('le plus proche', prov['talon']['source'])

    def test_reponse_hors_horaires_meme_definition_que_le_defaut(self):
        # Fondateur 27/10/2026 — « Un peu » = 20 % du niveau de jour : la MÊME
        # courbe que le défaut fondateur de 20 %, seul le statut change.
        jt_defaut, _p, _a = self._courbe([7, 21])
        jt_declare, prov, _a = self._courbe([7, 21], talon={'niveau_jour_pct': 20})
        self.assertEqual(prov['talon'], {'valeur': {'niveau_jour_pct': 20.0}, 'statut': 'declare'})
        for a, b in zip(jt_defaut, jt_declare):
            for x, y in zip(a['charge_kwh'], b['charge_kwh']):
                self.assertAlmostEqual(x, y, places=9)
        jt, _p, _a = self._courbe([7, 21], talon={'niveau_jour_pct': 50})
        mars = _par(jt, 3, 'ouvre')['charge_kwh']
        self.assertAlmostEqual(mars[3] / mars[12], 0.50, places=9)

    def test_commerce_sans_categorie_defaut_fondateur_industriel_borne(self):
        # Fondateur 27/10/2026 — commercial sans catégorie : 20 % ; l'industriel
        # sans archétype garde la borne conservatrice.
        _jt, prov, _al = self._courbe([7, 21], categorie=None)
        self.assertEqual(prov['talon']['statut'], 'defaut_fondateur')
        _jt, prov, _al = self._courbe([7, 21], categorie='industriel', segment='industriel')
        self.assertEqual(prov['talon']['statut'], 'borne_conservatrice')
        _jt, prov, _al = self._courbe([7, 21], categorie=None, segment=None)
        self.assertEqual(prov['talon']['statut'], 'borne_conservatrice')


class TestTalonMethodeArchetype(unittest.TestCase):
    """CLD1 — méthode archétype (aucune plage déclarée) : le talon DÉCLARÉ
    (``niveau_jour_pct`` / ``part_pct``) sert de PLANCHER, il n'est plus ignoré."""

    def _bureau(self, talon=None):
        rythme = {'jours_ouverts': LUN_VEN}
        if talon is not None:
            rythme['talon'] = talon
        return courbe_declaree(rythme, [10000] * 12, annee_reference=ANNEE,
                               archetype='bureau', feries=[])

    def _autoconso_ref(self, jt):
        production = _production_cloche()
        prod_kwc = sum(j['nb_jours'] * sum(production[j['mois'] - 1]['production_kwh_kwc'])
                       for j in jt)
        return charge._autoconso(jt, production, 10000 * 12 / prod_kwc)

    def test_niveau_jour_declare_change_la_courbe_et_conserve_l_energie(self):
        jt_rien, prov_rien, _a = self._bureau()
        jt_5, _p, _a = self._bureau({'niveau_jour_pct': 5})
        jt_50, prov_50, _a = self._bureau({'niveau_jour_pct': 50})
        self.assertEqual(prov_rien['talon']['statut'], 'estimation')
        self.assertEqual(prov_50['talon'],
                         {'valeur': {'niveau_jour_pct': 50.0}, 'statut': 'declare'})
        auto = [self._autoconso_ref(jt) for jt in (jt_rien, jt_5, jt_50)]
        self.assertNotAlmostEqual(auto[2], auto[0], places=3)
        self.assertNotAlmostEqual(auto[2], auto[1], places=3)
        # plancher : la nuit d'un jour ouvré vaut au moins 50 % du pic de jour
        mars = _par(jt_50, 3, 'ouvre')['charge_kwh']
        self.assertGreaterEqual(min(mars), 0.5 * max(mars) - 1e-9)
        mars_rien = _par(jt_rien, 3, 'ouvre')['charge_kwh']
        self.assertLess(min(mars_rien), 0.5 * max(mars_rien))
        for mois in range(1, 13):
            self.assertAlmostEqual(_energie_mois(jt_50, mois), 10000, delta=1e-6)

    def test_part_pct_declare_conserve_l_energie_et_releve_la_nuit(self):
        jt_rien, _p, _a = self._bureau()
        jt_40, prov, _a = self._bureau({'part_pct': 40})
        self.assertEqual(prov['talon'], {'valeur': {'part_pct': 40.0}, 'statut': 'declare'})
        for mois in range(1, 13):
            self.assertAlmostEqual(_energie_mois(jt_40, mois), 10000, delta=1e-6)
        self.assertGreater(min(_par(jt_40, 3, 'ouvre')['charge_kwh']),
                           min(_par(jt_rien, 3, 'ouvre')['charge_kwh']))
        # le talon vaut 40 % de l'énergie du mois, réparti à plat sur 24 h × jours
        self.assertGreaterEqual(min(_par(jt_40, 3, 'ouvre')['charge_kwh']),
                                10000 * 0.40 / (24 * 31) - 1e-9)


class TestTalonParDefautArchetype(unittest.TestCase):
    """CLD2 — talon par défaut d'un archétype = moyenne de la forme HORS des
    plages déclarées ÷ moyenne DANS les plages (saisons pondérées par les jours
    ouverts) : le niveau de jour sur ses heures, pas le creux sur le pic."""

    def test_boulangerie_part_d_energie_dans_les_plages_celle_de_l_archetype(self):
        from apps.ventes.moteur_ci.profils import forme_archetype
        rythme = {'jours_ouverts': TOUS, 'plages': {'ouvre': [[6, 22]]},
                  'categorie_commerciale': 'boulangerie'}
        jt, prov, alertes = courbe_declaree(rythme, [6000] * 12, annee_reference=ANNEE,
                                            archetype='boulangerie', feries=[])
        self.assertEqual(prov['talon']['statut'], 'estimation')
        self.assertIn('talon_estime', {a['code'] for a in alertes})
        total = sum(j['nb_jours'] * sum(j['charge_kwh']) for j in jt)
        dedans = sum(j['nb_jours'] * sum(j['charge_kwh'][6:22]) for j in jt)
        part_courbe = dedans / total
        # part 6-22 h de la forme de l'archétype, pondérée par les jours
        part_forme, jours = 0.0, 0
        for jour in charge._jours_annee(ANNEE):
            forme, _s = forme_archetype('boulangerie', 'ouvre', charge.saison_bdew(jour))
            part_forme += sum(forme[6:22]) / sum(forme)
            jours += 1
        self.assertAlmostEqual(part_courbe, part_forme / jours, delta=0.01)

    def test_plages_sur_24_heures_talon_sans_objet_aucune_exception(self):
        rythme = {'jours_ouverts': TOUS, 'plages': {'ouvre': [[0, 24]]},
                  'categorie_commerciale': 'hotel'}
        jt, prov, alertes = courbe_declaree(rythme, [6000] * 12, annee_reference=ANNEE,
                                            archetype='hotel', feries=[])
        self.assertIsNotNone(jt)
        self.assertIsNone(prov['talon']['valeur'])
        self.assertNotEqual(prov['talon']['statut'], 'defaut_fondateur')
        self.assertNotIn('talon_estime', {a['code'] for a in alertes})
        mars = _par(jt, 3, 'ouvre')['charge_kwh']
        self.assertAlmostEqual(max(mars), min(mars), places=9)
        for mois in range(1, 13):
            self.assertAlmostEqual(_energie_mois(jt, mois), 6000, delta=1e-6)

    def test_profil_societe_nuit_nulle_statut_estimation(self):
        profil = {'cle': 'jour-seul', 'libelle': 'Jour seul',
                  'courbe': {'annuel': [0] * 8 + [1] * 10 + [0] * 6},
                  'provenance': 'relevé compteur 2025'}
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]}}
        jt, prov, _al = courbe_declaree(rythme, [6000] * 12, annee_reference=ANNEE,
                                        archetype='bureau', feries=[],
                                        profil_societe=profil)
        self.assertEqual(prov['talon']['statut'], 'estimation')
        self.assertEqual(prov['talon']['valeur'], {'rapport_nuit_jour': 0.0})
        self.assertEqual(min(_par(jt, 3, 'ouvre')['charge_kwh']), 0.0)


class TestDecalageConstant(unittest.TestCase):
    """CLD3 — un site garde ses horaires d'horloge : décalage CONSTANT du régime
    en vigueur (Maroc UTC+0 depuis le 20/09/2026), plus la date homologue."""

    def _bureau(self, **kw):
        rythme = {'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]},
                  'talon': {'kw': 1.0}}
        return courbe_declaree(rythme, [10000] * 12, annee_reference=2025,
                               feries=[], **kw)[0]

    def test_decalage_zero_plateau_gmt_8_18_toute_l_annee(self):
        jt = self._bureau(decalage_h=0)
        for mois in (1, 6, 11):
            c = _par(jt, mois, 'ouvre')['charge_kwh']
            self.assertGreater(min(c[8:18]), max(c[:8] + c[18:]))

    def test_defaut_est_le_regime_en_vigueur_constant(self):
        from apps.parametres.pvgis_profils import decalage_maroc_h
        d = decalage_maroc_h(None)
        jt_defaut = self._bureau()
        jt_fixe = self._bureau(decalage_h=d)
        self.assertEqual(jt_defaut, jt_fixe)
        # un décalage différent change la courbe (le paramètre agit)
        self.assertNotEqual(self._bureau(decalage_h=d + 1), jt_fixe)


class TestProfilChargePrerequis(unittest.TestCase):
    """ADEV76 — LA règle des prérequis : un cas par branche de ``courbe_declaree``."""

    PROFIL_SOCIETE = {'cle': 'hotel', 'libelle': 'Hôtel relevé', 'provenance': 'relevé 2025',
                      'courbe': {'annuel': [0] * 8 + [10] * 10 + [0] * 6}}

    def _accord(self, rythme, categorie=None, profil_societe=None):
        """La règle et le moteur disent la MÊME chose (jours types ⇔ [])."""
        manquants = charge.profil_charge_prerequis(rythme, categorie, profil_societe)
        jt, _prov, alertes = courbe_declaree(
            dict(rythme, talon={'kw': 1}), [1000] * 12, annee_reference=ANNEE,
            archetype=categorie, profil_societe=profil_societe, feries=[])
        self.assertEqual(jt is None, bool(manquants), (rythme, manquants))
        bloquants = {a['champ'] for a in alertes if a['niveau'] == 'bloquant'}
        self.assertEqual(bloquants, set(manquants))
        return manquants

    def test_heures_et_jours_declares_pret(self):
        self.assertEqual(self._accord({'jours_ouverts': LUN_VEN, 'plages': {'ouvre': [[8, 18]]}}), [])

    def test_heures_sans_jours_exige_les_jours(self):
        self.assertEqual(self._accord({'plages': {'ouvre': [[8, 18]]}}, 'bureau'),
                         ['rythme.jours_ouverts'])

    def test_regime_3x8_sans_heures_pret(self):
        self.assertEqual(self._accord({'jours_ouverts': TOUS, 'equipes': '3x8'}, 'industriel'), [])

    def test_regime_2x8_sans_heure_de_debut_exige_les_heures(self):
        self.assertEqual(self._accord({'jours_ouverts': TOUS, 'equipes': '2x8'}, 'industriel'),
                         ['rythme.plages'])
        self.assertEqual(self._accord({'jours_ouverts': TOUS, 'equipes': '2x8',
                                       'debut_equipe_h': 6}, 'industriel'), [])

    def test_reponses_de_categorie_posent_des_plages(self):
        rythme = {'reponses_categorie': {'horaires': 'midi_soir', 'heures': [[11, 23]]}}
        # Des plages déclarées par la catégorie ⇒ les jours sont exigés (l'archétype
        # restaurant ne sert plus).
        self.assertEqual(self._accord(rythme, 'restaurant'), ['rythme.jours_ouverts'])
        self.assertEqual(self._accord({}, 'restaurant'), [])

    def test_sans_plage_archetype_vendorise_pret(self):
        self.assertEqual(self._accord({}, 'bureau'), [])

    def test_sans_plage_profil_societe_pret(self):
        self.assertEqual(self._accord({}, 'industriel', self.PROFIL_SOCIETE), [])

    def test_sans_plage_ni_repli_jours_puis_heures(self):
        self.assertEqual(self._accord({}, 'hammam'), ['rythme.jours_ouverts', 'rythme.plages'])
        self.assertEqual(self._accord({}, None), ['rythme.jours_ouverts', 'rythme.plages'])
        self.assertEqual(self._accord({'jours_ouverts': TOUS}, 'industriel'), ['rythme.plages'])


class TestPurete(unittest.TestCase):

    def test_aucun_import_django(self):
        with open(charge.__file__, encoding='utf-8') as fh:
            arbre = ast.parse(fh.read())
        modules = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                modules.extend(alias.name for alias in noeud.names)
            elif isinstance(noeud, ast.ImportFrom):
                modules.append(noeud.module or '')
        for module in modules:
            self.assertFalse(module.split('.')[0] in ('django', 'rest_framework', 'celery'), module)
            self.assertNotIn('models', module)
        self.assertTrue(os.path.exists(charge.__file__))


if __name__ == '__main__':
    unittest.main()
