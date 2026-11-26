"""CAL131 — les sections se calculent sur les LONGUEURS DU PLAN.

Le plan à deux pans est le cas de référence : la liaison DC dimensionnante est
la plus longue des deux, mesurée sur les CENTRES DE MODULES POSÉS, à quoi
s'ajoutent la descente et la liaison coffret → onduleur, qui elles sont
SAISIES (aucun plan ne les porte).

Les deux refus tenus par ce test :

* longueur inconnue ⇒ AUCUNE section publiée (jamais le forfait de 15 m du
  devis) ;
* norme non sélectionnée ⇒ calcul OMIS (règle D5, CAL130).

Run :
    python manage.py test apps.calepinage.tests.test_elec_cables_longueurs_plan -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.cables import (
    ORIGINE_MIXTE, ORIGINE_PLAN, ORIGINE_SAISIE, cables_du_calepinage, longueur_ac,
    longueur_dc,
)
from apps.calepinage.services.chaines import concevoir_par_pan
from apps.calepinage.services.electrique import temperatures_site
from apps.calepinage.services.norme import norme_applicable

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}
NORME_FR = norme_applicable({'imagerie': {'pays': 'fr'},
                             'norme_electrique': {}})
NORME_MA = norme_applicable({'imagerie': {'pays': 'ma'},
                             'norme_electrique': {}})


def _panneaux(nombre, x0, ecart=1.2):
    return [{'cx': x0 + rang * ecart, 'cy': 0.0} for rang in range(nombre)]


LAYOUT = {'version': 2, 'zones': [
    {'id': 'PAN-A', 'label': 'PAN-A', 'geometry': {
        'count': 6, 'azimuthDeg': 180.0, 'tiltDeg': 15.0,
        'panels': _panneaux(6, 0.0)}},
    {'id': 'PAN-B', 'label': 'PAN-B', 'geometry': {
        'count': 6, 'azimuthDeg': 90.0, 'tiltDeg': 15.0,
        'panels': _panneaux(6, 10.0)}},
]}

CHEMINEMENT = {
    'pans': {'PAN-A': {'point_collecte': {'cx': 0.0, 'cy': 0.0}},
             'PAN-B': {'point_collecte': {'cx': 10.0, 'cy': 0.0}}},
    'descente_m': 6.0,
    'coffret_vers_onduleur_m': 4.0,
    'onduleur_vers_tgbt_m': 12.0,
}


def _conception():
    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        onduleur_designation='Onduleur d essai')


class LongueursTest(SimpleTestCase):
    """La longueur vient du plan, et elle DIT d'où elle vient."""

    def test_la_course_dc_est_celle_du_pan_le_plus_long(self):
        longueur, manques = longueur_dc(LAYOUT, CHEMINEMENT)

        self.assertEqual(manques, ())
        # 6 modules espacés de 1,2 m → 6 m du point de collecte, + 6 m de
        # descente + 4 m vers l'onduleur.
        self.assertAlmostEqual(longueur.valeur_m, 6.0 + 6.0 + 4.0, places=2)
        self.assertEqual(longueur.origine, ORIGINE_MIXTE)
        self.assertEqual(len(longueur.composantes), 3)

    def test_un_pan_sans_point_de_collecte_empeche_la_mesure(self):
        cheminement = dict(CHEMINEMENT, pans={
            'PAN-A': CHEMINEMENT['pans']['PAN-A']})

        longueur, manques = longueur_dc(LAYOUT, cheminement)

        self.assertIsNone(longueur)
        self.assertIn('PAN-B', manques[0])

    def test_la_descente_non_saisie_empeche_la_mesure(self):
        cheminement = {cle: valeur for cle, valeur in CHEMINEMENT.items()
                       if cle != 'descente_m'}

        longueur, manques = longueur_dc(LAYOUT, cheminement)

        self.assertIsNone(longueur)
        self.assertIn('descente verticale', manques[0])

    def test_la_liaison_ac_est_saisie_et_le_dit(self):
        longueur, manques = longueur_ac(CHEMINEMENT)

        self.assertEqual(manques, ())
        self.assertEqual(longueur.valeur_m, 12.0)
        self.assertEqual(longueur.origine, ORIGINE_SAISIE)

    def test_sans_liaison_ac_saisie_aucun_forfait(self):
        longueur, manques = longueur_ac({})

        self.assertIsNone(longueur)
        self.assertIn('aucun forfait', manques[0])


class CablesPubliesTest(SimpleTestCase):
    """Chaque câble porte section, critère, chute, longueur et origine."""

    def test_les_deux_cables_sont_dimensionnes(self):
        resultat = cables_du_calepinage(
            _conception(), cheminement=CHEMINEMENT, norme=NORME_FR,
            layout=LAYOUT)
        reperes = {cable['repere']: cable for cable in resultat['cables']}

        self.assertEqual(sorted(reperes), ['W1', 'W2'])
        for cable in reperes.values():
            self.assertGreater(cable['section_mm2'], 0)
            self.assertTrue(cable['critere_dimensionnant'])
            self.assertIsNotNone(cable['chute_tension_pct'])
            self.assertTrue(cable['longueur_origine'])
            self.assertTrue(cable['regle_source'])
        self.assertAlmostEqual(reperes['W1']['longueur_m'], 16.0, places=2)
        self.assertAlmostEqual(reperes['W2']['longueur_m'], 12.0, places=2)

    def test_longueur_dc_inconnue_ne_publie_aucune_section_dc(self):
        cheminement = {'onduleur_vers_tgbt_m': 12.0}

        resultat = cables_du_calepinage(
            _conception(), cheminement=cheminement, norme=NORME_FR,
            layout=LAYOUT)
        reperes = [cable['repere'] for cable in resultat['cables']]

        self.assertNotIn('W1', reperes)
        self.assertIsNone(resultat['longueurs']['dc'])
        self.assertTrue(resultat['omissions'])

    def test_sans_norme_selectionnee_le_calcul_est_omis(self):
        resultat = cables_du_calepinage(
            _conception(), cheminement=CHEMINEMENT, norme=NORME_MA,
            layout=LAYOUT)

        self.assertEqual(resultat['cables'], [])
        self.assertIn('ne sont pas calculés', resultat['omissions'][0])

    def test_sans_chaine_il_n_y_a_rien_a_dimensionner(self):
        vide = concevoir_par_pan(
            {'zones': []}, module_specs=MODULE, onduleur_specs=ONDULEUR,
            temperatures=temperatures_site(
                saisie={'temperature_min_c': -5.0,
                        'temperature_max_c': 70.0}))

        resultat = cables_du_calepinage(vide, cheminement=CHEMINEMENT,
                                        norme=NORME_FR, layout=LAYOUT)

        self.assertEqual(resultat['cables'], [])
        self.assertIn("pas de liaison", resultat['omissions'][0])


# ─── Liaison DC tracée (suite ACAL1317) — UNE longueur DC : celle du tracé ───
#
# Le plan porte un onduleur ``eq1`` et un coffret DC ``eq2`` ; PAN-A est tracé
# droit jusqu'à l'onduleur, PAN-B passe par le coffret. Les longueurs ATTENDUES
# sont celles que ``troncons.py`` publie (la pastille « Câble côté panneaux ») :
# jamais recalculées ici.
def _point(lng, lat, altitude=None):
    point = {'lng': lng, 'lat': lat}
    if altitude is not None:
        point['altitudeM'] = altitude
    return point


def _trace(identifiant, de, vers, *points):
    return {'id': identifiant, 'cote': 'dc', 'de': de, 'vers': vers,
            'points': list(points), 'origine': 'plan'}


EQUIPEMENTS = [
    {'id': 'eq1', 'type': 'onduleur', 'lng': -7.6002, 'lat': 33.5001},
    {'id': 'eq2', 'type': 'coffret_dc', 'lng': -7.6003, 'lat': 33.5002},
]
TRACES = [
    _trace('chA', 'PAN-A', 'eq1', _point(-7.6001, 33.5003, 6.0),
           _point(-7.6002, 33.5003, 6.0), _point(-7.6002, 33.5001, 0.0)),
    _trace('chB', 'PAN-B', 'eq2', _point(-7.6006, 33.5004),
           _point(-7.6003, 33.5002)),
    _trace('chB2', 'eq2', 'eq1', _point(-7.6003, 33.5002),
           _point(-7.6002, 33.5001)),
]


def _avec_electrique(equipements=EQUIPEMENTS, cheminements=TRACES):
    return dict(LAYOUT, electrical={'equipements': list(equipements),
                                    'cheminements': list(cheminements)})


LAYOUT_TRACE = _avec_electrique()

#: Rien de SAISI côté DC (ni descente, ni coffret → onduleur) : seul le TGBT.
NON_SAISI = {'pans': CHEMINEMENT['pans'], 'onduleur_vers_tgbt_m': 12.0}


def _jour_de_coupure(decalage_jours=0):
    import datetime

    from apps.ventes.domain.regles_calcul import COUPURE_LIAISON_DC_TRACEE

    return (datetime.date(*COUPURE_LIAISON_DC_TRACEE)
            + datetime.timedelta(days=decalage_jours))


def _longueurs_des_troncons(document):
    """``{id: longueur_m}`` tels que ``troncons.py`` les PUBLIE (pastille)."""
    from apps.calepinage.services.troncons import troncons_de_la_conception

    publies = troncons_de_la_conception(_conception(), document, NORME_FR)
    return {t['id']: t['longueur_m'] for t in publies['troncons']}


def _cables(layout, cheminement, jour, conception=None):
    return cables_du_calepinage(conception or _conception(), cheminement=cheminement,
                                norme=NORME_FR, layout=layout, jour=jour)


def _sans_noyau(resultat):
    return {cle: valeur for cle, valeur in resultat.items() if cle != 'noyau'}


class LiaisonDcTraceeTest(SimpleTestCase):
    """Le tracé mesuré sert la simulation et la chute — quand rien n'est saisi."""

    def test_le_trace_mesure_sert_quand_rien_n_est_saisi(self):
        from apps.calepinage.services.cables import SOURCE_DC_TRACE
        from apps.calepinage.services.liaison_dc_tracee import PREFIXE_DETAIL_TRACE

        mesures = _longueurs_des_troncons(LAYOUT_TRACE)
        resultat = _cables(LAYOUT_TRACE, NON_SAISI, _jour_de_coupure())
        w1 = {c['repere']: c for c in resultat['cables']}['W1']

        # Chaque pan prend SON tracé ; la liaison retenue est la plus longue
        # (PAN-B : chB + chB2, par le coffret), à la même mesure que les tronçons.
        # (Somme de deux tronçons publiés au centième : ± 1 cm d'arrondi.)
        attendu = max(mesures['chA'], mesures['chB'] + mesures['chB2'])
        self.assertAlmostEqual(w1['longueur_m'], attendu, delta=0.01)
        self.assertGreater(w1['section_mm2'], 0)
        self.assertIsNotNone(w1['chute_tension_pct'])
        self.assertTrue(w1['longueur_detail'].startswith(PREFIXE_DETAIL_TRACE))
        self.assertEqual(resultat['longueurs']['source_dc'], SOURCE_DC_TRACE)
        self.assertEqual(resultat['longueurs']['dc']['origine'], ORIGINE_PLAN)
        self.assertNotIn('W1', ' '.join(resultat['omissions']))

    def test_un_seul_pan_trace_droit_vaut_la_pastille(self):
        document = _avec_electrique(cheminements=TRACES[:1])
        document = dict(document, zones=document['zones'][:1])
        mesures = _longueurs_des_troncons(document)

        w1 = {c['repere']: c for c in _cables(
            document, NON_SAISI, _jour_de_coupure())['cables']}['W1']

        self.assertEqual(w1['longueur_m'], mesures['chA'])

    def test_le_producteur_sert_l_exemple_du_contrat(self):
        import json
        import pathlib

        contrat = json.loads((pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
                              / 'calepinage_resultat.json').read_text(encoding='utf-8'))
        attendu = contrat['liaison_dc_tracee']
        document = _avec_electrique(cheminements=TRACES[:1])
        document = dict(document, zones=document['zones'][:1])

        servi = _cables(document, NON_SAISI, _jour_de_coupure())
        w1 = {c['repere']: c for c in servi['cables']}['W1']

        self.assertEqual(servi['longueurs'], attendu['longueurs'])
        self.assertEqual({cle: w1[cle] for cle in attendu['cables'][0]}, attendu['cables'][0])
        self.assertEqual(_longueurs_des_troncons(document)['chA'],
                         attendu['troncons']['troncons'][0]['longueur_m'])

    def test_une_longueur_saisie_l_emporte_toujours(self):
        from apps.calepinage.services.cables import SOURCE_DC_SAISIE

        jour = _jour_de_coupure()
        for cheminement in (CHEMINEMENT,
                            dict(NON_SAISI, descente_m=6.0),
                            dict(NON_SAISI, coffret_vers_onduleur_m=4.0)):
            with self.subTest(cheminement=sorted(cheminement)):
                self.assertEqual(_sans_noyau(_cables(LAYOUT_TRACE, cheminement, jour)),
                                 _sans_noyau(_cables(LAYOUT, cheminement, jour)))
        self.assertEqual(_cables(LAYOUT_TRACE, CHEMINEMENT, jour)['longueurs']['source_dc'],
                         SOURCE_DC_SAISIE)
        # ``dc_m`` SAISI dans l'entrée : le tracé n'est pas substitué non plus.
        import dataclasses
        base = _conception()
        saisie_dc = dataclasses.replace(base, entree=dataclasses.replace(base.entree, dc_m=25.0))
        self.assertEqual(_sans_noyau(_cables(LAYOUT_TRACE, NON_SAISI, jour, saisie_dc)),
                         _sans_noyau(_cables(LAYOUT, NON_SAISI, jour, saisie_dc)))

    def test_sans_trace_les_chiffres_d_aujourd_hui_octet_pour_octet(self):
        import json

        avant, apres = _jour_de_coupure(-1), _jour_de_coupure()
        for cheminement in (CHEMINEMENT, NON_SAISI):
            with self.subTest(cheminement=sorted(cheminement)):
                self.assertEqual(
                    json.dumps(_sans_noyau(_cables(LAYOUT, cheminement, apres)), sort_keys=True),
                    json.dumps(_sans_noyau(_cables(LAYOUT, cheminement, avant)), sort_keys=True))

    def test_avant_la_coupure_le_trace_ne_sert_pas(self):
        from apps.calepinage.services.cables import SOURCE_DC_DEFAUT

        avant = _jour_de_coupure(-1)
        resultat = _cables(LAYOUT_TRACE, NON_SAISI, avant)

        self.assertEqual(_sans_noyau(resultat), _sans_noyau(_cables(LAYOUT, NON_SAISI, avant)))
        self.assertNotIn('W1', [c['repere'] for c in resultat['cables']])
        self.assertEqual(resultat['longueurs']['source_dc'], SOURCE_DC_DEFAUT)

    def test_un_trace_qui_n_aboutit_pas_a_un_onduleur_est_ignore(self):
        jour = _jour_de_coupure()
        temoin = _sans_noyau(_cables(LAYOUT, NON_SAISI, jour))
        orphelins = (
            _avec_electrique(cheminements=[TRACES[1]]),  # s'arrête au coffret
            _avec_electrique(cheminements=[_trace('chX', 'PAN-A', 'eq9', *TRACES[0]['points']),
                                           _trace('chY', 'PAN-B', 'eq9', *TRACES[1]['points'])]),
            _avec_electrique(equipements=EQUIPEMENTS[1:]),  # aucun onduleur posé
        )
        for document in orphelins:
            with self.subTest(document=document['electrical']):
                self.assertEqual(_sans_noyau(_cables(document, NON_SAISI, jour)), temoin)

    def test_un_pan_sans_trace_garde_la_regle_des_longueurs_saisies(self):
        from apps.calepinage.services.cables import MOTIF_PAN_SANS_TRACE

        resultat = _cables(_avec_electrique(cheminements=TRACES[:1]), NON_SAISI,
                           _jour_de_coupure())

        self.assertNotIn('W1', [c['repere'] for c in resultat['cables']])
        self.assertIsNone(resultat['longueurs']['dc'])
        self.assertIn(MOTIF_PAN_SANS_TRACE, resultat['omissions'])

    def test_le_trace_est_deja_dans_l_empreinte_du_document(self):
        from apps.calepinage.services.layout import empreinte_document

        deplace = _avec_electrique(cheminements=[
            dict(TRACES[0], points=TRACES[0]['points'][:2])] + TRACES[1:])

        self.assertEqual(empreinte_document(LAYOUT_TRACE), empreinte_document(_avec_electrique()))
        self.assertNotEqual(empreinte_document(LAYOUT_TRACE), empreinte_document(deplace))


class LeDevisNeBougePasTest(SimpleTestCase):
    """Le devis ne lit que la longueur SAISIE ``dc_m`` : le tracé ne le touche pas."""

    def _site_lu_par_le_devis(self, layout, donnees):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage import selectors
        from apps.calepinage.services.electrique import CLE_ENTREE

        calepinage = SimpleNamespace(pk=7, roof_layout=layout, resultat={CLE_ENTREE: donnees})
        with mock.patch.object(selectors, '_calepinage_lisible_pour_devis', return_value=calepinage), \
                mock.patch.object(selectors, '_module_du_devis', return_value=None), \
                mock.patch('apps.calepinage.services.electrique.resoudre_materiel', return_value={}), \
                mock.patch('apps.calepinage.services.electrique.temperatures_pour_calepinage',
                           return_value=SimpleNamespace(source=None)), \
                mock.patch('django.utils.timezone.localdate', return_value=_jour_de_coupure(1)):
            return selectors.entree_electrique_du_devis(3, object())

    def test_la_longueur_lue_par_le_devis_reste_la_saisie(self):
        for donnees, attendu in (({'cheminement': NON_SAISI}, None),
                                 ({'cheminement': NON_SAISI, 'dc_m': 9.0}, 9.0)):
            with self.subTest(attendu=attendu):
                avec_trace = self._site_lu_par_le_devis(LAYOUT_TRACE, donnees)
                self.assertEqual(avec_trace, self._site_lu_par_le_devis(LAYOUT, donnees))
                self.assertEqual(avec_trace['dc_m'], attendu)

    def test_l_empreinte_et_les_cables_du_devis_ne_bougent_pas(self):
        import dataclasses
        from types import SimpleNamespace

        from apps.ventes.electrical_service import empreinte_entree
        from core.electrique import concevoir

        def du_devis(layout):
            site = self._site_lu_par_le_devis(layout, {'cheminement': NON_SAISI, 'dc_m': 9.0})
            entree = dataclasses.replace(_conception().entree, dc_m=site['dc_m'])
            devis = SimpleNamespace(layout_hash='empreinte-imprimee')
            return empreinte_entree(devis, entree), concevoir(entree).cables

        self.assertEqual(du_devis(LAYOUT_TRACE), du_devis(LAYOUT))


class _Pivot:
    """Le strict minimum que ``resultat_calepinage`` lit sur un pivot — aucun ORM."""

    def __init__(self, layout, resultat):
        self.pk, self.roof_layout, self.resultat, self.company = 1, layout, resultat, None

    def save(self, update_fields=None):
        pass


MATERIEL_INJECTE = {'module': MODULE, 'onduleur': ONDULEUR, 'optimiseur': None,
                    'designations': {'module': 'Module d essai', 'onduleur': 'Onduleur d essai',
                                     'optimiseur': ''}, 'absents': ()}
REGLAGES_FR = {'imagerie': {'pays': 'fr'}, 'norme_electrique': {}}


class LaLectureMontreCeQueLaSimulationACalcule(SimpleTestCase):
    """``GET resultat/`` : le W1 servi suit la DATE de la simulation servie."""

    def _servi(self, simulation=None, aujourd_hui=None):
        from unittest import mock

        from apps.calepinage.services.electrique import CLE_ENTREE, CLE_SIMULATION, resultat_calepinage

        stocke = {CLE_ENTREE: {'cheminement': NON_SAISI, 'temperature_min_c': -5.0,
                               'temperature_max_c': 70.0}}
        if simulation is not None:
            stocke[CLE_SIMULATION] = simulation
        with mock.patch('django.utils.timezone.localdate',
                        return_value=aujourd_hui or _jour_de_coupure()):
            return resultat_calepinage(_Pivot(LAYOUT_TRACE, stocke), materiel=MATERIEL_INJECTE,
                                       reglages=REGLAGES_FR)

    def _empreinte(self):
        return self._servi()['hash_entree']

    def test_simulation_fraiche_d_avant_la_coupure_le_w1_reste_celui_qu_elle_a_compte(self):
        from apps.calepinage.services.cables import SOURCE_DC_DEFAUT

        veille = '%sT10:00:00Z' % _jour_de_coupure(-1).isoformat()
        servi = self._servi({'hash_entree': self._empreinte(), 'calcule_le': veille})

        self.assertFalse(servi['simulation_perimee'])
        self.assertNotIn('W1', [c['repere'] for c in servi['cables']])
        self.assertEqual(servi['longueurs']['source_dc'], SOURCE_DC_DEFAUT)
        # Sans date enregistrée, une simulation fraîche est d'AVANT la coupure.
        sans_date = self._servi({'hash_entree': self._empreinte()})
        self.assertEqual(sans_date['longueurs'], servi['longueurs'])

    def test_simulation_fraiche_du_jour_de_la_coupure_le_w1_compte_le_trace(self):
        from apps.calepinage.services.cables import SOURCE_DC_DEFAUT

        jour = '%sT10:00:00Z' % _jour_de_coupure().isoformat()
        servi = self._servi({'hash_entree': self._empreinte(), 'calcule_le': jour},
                            aujourd_hui=_jour_de_coupure(-1))

        self.assertIn('W1', [c['repere'] for c in servi['cables']])
        self.assertNotEqual(servi['longueurs']['source_dc'], SOURCE_DC_DEFAUT)

    def test_sans_simulation_ou_perimee_le_w1_est_celui_d_aujourd_hui(self):
        apres = self._servi()
        perimee = self._servi({'hash_entree': 'autre-document', 'calcule_le': '2026-01-01T10:00:00Z'})

        self.assertTrue(perimee['simulation_perimee'])
        for servi in (apres, perimee):
            self.assertIn('W1', [c['repere'] for c in servi['cables']])
        self.assertNotIn('W1', [c['repere'] for c in self._servi(
            aujourd_hui=_jour_de_coupure(-1))['cables']])

    def test_la_date_est_celle_du_fuseau_du_projet(self):
        import datetime
        from types import SimpleNamespace

        from apps.calepinage.services.cables import jour_du_calcul_servi

        from django.utils import timezone

        fraiche = SimpleNamespace(resultat={'simulation': {'hash_entree': 'h'}})
        # Le MÊME jour que celui que la simulation lit (``timezone.localdate`` du
        # sélecteur) : la date LOCALE de l'instant UTC enregistré, jamais sa date UTC.
        veille_tard = '%sT23:30:00Z' % _jour_de_coupure(-1).isoformat()
        instant = datetime.datetime.combine(_jour_de_coupure(-1), datetime.time(23, 30),
                                            tzinfo=datetime.timezone.utc)
        self.assertEqual(jour_du_calcul_servi(fraiche, False, veille_tard),
                         timezone.localdate(instant))
        self.assertEqual(jour_du_calcul_servi(fraiche, False, None), datetime.date.min)
        self.assertIsNone(jour_du_calcul_servi(fraiche, True, veille_tard))
        self.assertIsNone(jour_du_calcul_servi(SimpleNamespace(resultat={}), False, None))
