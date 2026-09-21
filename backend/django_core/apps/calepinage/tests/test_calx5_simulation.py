"""CALX5 — L'ORCHESTRATION de la simulation, bout en bout et SANS BASE.

CE QUE CE FICHIER AFFIRME
--------------------------
1. **le contexte** que ``services/simulation.py`` bâtit porte EXACTEMENT ce
   que les vingt-quatre étapes et les six blocs aval déclarent lire — une clé
   oubliée ici, et l'étape correspondante s'omet en silence sur toute la
   flotte ;
2. **les refus NOMMENT le champ** : sans mode météo saisi, la simulation est
   refusée en nommant ``parametres.simulation.mode_meteo`` (jamais un
   « simulation impossible » générique, règle fondateur du 08/09/2026) ;
3. **la chaîne RÉELLE tourne** sur une réponse météo rejouée : la production
   publiée est un NOMBRE, la cascade suit ``ORDRE_ETAPES`` au poste près, et
   l'en-tête ``simulation`` est écrit avec l'empreinte des entrées ;
4. **la porte HTTP** est routée sous ``simuler/``, en POST, et le suivi passe
   par le kind EXISTANT (D-CALX 12) ;
5. **le contrat committé** ``contract_samples/calepinage_simulation.json`` a
   bien les clés que les producteurs publient — la FORME, jamais les valeurs :
   les nombres de l'exemple sont des placeholders assumés.

AUCUNE BASE, AUCUN RÉSEAU. Le matériel et les réglages société sont INJECTÉS
(``materiel=`` / ``reglages=``, les mêmes seams que
``services/electrique.py::conception_du_calepinage``), et la météo vient d'un
client DOUBLE qui rejoue une réponse fabriquée ici. Les tests qui exigeraient
l'ORM (l'écriture sur ``Calepinage.resultat``, la relecture par
``GET resultat/``) sont écrits en ``TestCase`` et NE SONT PAS EXÉCUTÉS sur le
poste de développement (aucune base) — ils tournent en CI.

Run :
    python manage.py test apps.calepinage.tests.test_calx5_simulation -v2
"""
import json
import pathlib

from django.test import SimpleTestCase, TestCase

from apps.calepinage.services import simulation as service
from apps.calepinage.services.chaine_pertes import ORDRE_ETAPES
from apps.calepinage.services.simulation import (
    SimulationRefusee, construire_contexte, simuler_calepinage,
)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_simulation.json').read_text(encoding='utf-8'))

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}
MATERIEL = {
    'module': MODULE, 'onduleur': ONDULEUR, 'optimiseur': None,
    'designations': {'module': 'Module d essai',
                     'onduleur': 'Onduleur d essai', 'optimiseur': ''},
    'absents': (),
}

#: Les réglages société SAISIS du cas — chacun avec sa provenance (CALX145).
#: Aucun n'est un défaut : sans eux, la simulation refuse, et c'est le sujet
#: du premier test.
REGLAGES = {
    'simulation': {
        'mode_meteo': {'valeur': 'pluriannuel', 'source': 'note interne',
                       'reference': 'choix du bureau d’études'},
        'fenetre_annees': {'valeur': [2020, 2021], 'source': 'note interne',
                           'reference': 'base PVGIS disponible'},
    },
    'imagerie': {},
    'norme_electrique': {},
    'electrique_societe': {},
}

LAYOUT = {
    'version': 2,
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [
        {'id': 'a', 'label': 'PAN-A',
         'geometry': {'count': 12, 'azimuthDeg': 180.0, 'tiltDeg': 15.0,
                      'family': 'surimposition'}},
    ],
}


class _Calepinage:
    """Le strict minimum que le service lit sur un pivot — aucun ORM.

    ``pk = None`` : rien n'est enregistré, et la recherche d'un fichier météo
    déposé (CALX62) s'arrête avant la moindre requête.
    """

    pk = None
    devis_id = None
    titre = 'Calepinage d essai'

    def __init__(self, layout=None, resultat=None, pertes=None):
        self.roof_layout = layout if layout is not None else LAYOUT
        self.resultat = resultat
        self.pertes = pertes or []
        self.company = None


def _points():
    """Deux jours de janvier sur DEUX années — le strict nécessaire.

    Deux années, parce que la variabilité interannuelle ne se MESURE que sur
    plusieurs années observées (CALX184) ; deux jours, parce qu'une année
    entière ne dirait rien de plus sur la FORME publiée.
    """
    points = []
    for annee in (2020, 2021):
        for jour in (15, 16):
            for heure in range(24):
                globale = max(0.0, 700.0 - abs(heure - 13) * 90.0)
                points.append({
                    'annee': annee, 'mois': 1, 'jour': jour, 'heure': heure,
                    'gi_w_m2': globale,
                    'gb_i_w_m2': globale * 0.8,
                    'gd_i_w_m2': globale * 0.18,
                    'gr_i_w_m2': globale * 0.02,
                    't2m_c': 14.0, 'ws10m': 2.5,
                    'h_sun_deg': max(0.0, 55.0 - abs(heure - 13) * 7.0),
                })
    return points


def _reponse_meteo():
    """La réponse d'irradiance REJOUÉE, à la forme de ``serie_irradiance``."""
    points = _points()
    return {
        'service': 'seriescalc',
        'points': points,
        'composantes_disponibles': True,
        'motif_composantes': None,
        'serie_horaire': {'pas_minutes': 60, 'tronquee': False,
                          'colonnes': ['annee', 'mois', 'jour', 'heure',
                                       'gi_w_m2', 't2m_c'],
                          'points': points},
        'meteo': {
            'service': 'seriescalc',
            'base_rayonnement': 'PVGIS-SARAH3',
            'base_meteo': 'ERA5',
            'fenetre_annees': '2020-2021',
            'annees': [2020, 2021],
            'point': {'lat': 33.5731, 'lon': -7.5898, 'altitude_m': 50.0},
            'horizon': {'origine': 'dem_pvgis', 'hauteur_max_deg': 8.5,
                        'base_horizon': 'SRTM'},
            'url': 'https://re.jrc.ec.europa.eu/api/v5_3/seriescalc',
            'obtenue_le': '2026-09-21T10:14:00Z',
            'depuis_cache': False,
            'convention_azimut': 'pvgis_sud_0_est_-90',
            'heure': {'base': 'locale_standard', 'fuseau_site': None,
                      'decalage_minutes': []},
        },
        'annees': [2020, 2021],
        'url': 'https://re.jrc.ec.europa.eu/api/v5_3/seriescalc',
        'depuis_cache': False,
    }


class _ClientRejoue:
    """Un client PVGIS double : il rejoue une réponse, il n'appelle rien.

    Il n'expose QUE ``serie_irradiance`` : l'écart contre PVcalc (CALX195) est
    donc publié sans mesure, avec son motif — ce qui est exactement ce qu'on
    veut affirmer d'un client qui ne sait pas demander une production.
    """

    def __init__(self, reponse=None):
        self.reponse = reponse if reponse is not None else _reponse_meteo()
        self.demandes = []

    def serie_irradiance(self, **parametres):
        self.demandes.append(parametres)
        return self.reponse


def _simuler(calepinage=None, **kwargs):
    """La simulation du cas, matériel et réglages INJECTÉS, rien d'écrit."""
    kwargs.setdefault('client', _ClientRejoue())
    kwargs.setdefault('materiel', MATERIEL)
    kwargs.setdefault('reglages', REGLAGES)
    kwargs.setdefault('enregistrer', False)
    return simuler_calepinage(calepinage or _Calepinage(), **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# 1. LE CONTEXTE — ce que les producteurs purs déclarent lire
# ═══════════════════════════════════════════════════════════════════════════

class ContexteTest(SimpleTestCase):
    """Le contexte porte CHAQUE clé qu'une étape ou un bloc aval lit."""

    #: Les clés que les vingt-quatre étapes et les six blocs aval lisent,
    #: relevées dans leurs modules (``contexte.get('…')``). Une clé qui
    #: disparaîtrait d'ici ferait s'omettre son étape en silence.
    ATTENDUES = (
        'reglages_simulation', 'fiche_module', 'fiche_onduleur',
        'fiche_optimiseur', 'fiches_modules', 'designations', 'materiel',
        'site', 'plans', 'layout', 'ombrage', 'horizon', 'entree_electrique',
        'electrique', 'affectation', 'cables', 'cheminement', 'norme',
        'suivi_mpp_par_module', 'postes_saisis', 'consommation', 'batterie',
        'raccordement', 'hors_reseau', 'hash_entree',
    )

    def test_toutes_les_cles_declarees_sont_presentes(self):
        contexte, _meta = construire_contexte(_Calepinage(),
                                              materiel=MATERIEL,
                                              reglages=REGLAGES)

        manquantes = sorted(set(self.ATTENDUES) - set(contexte))
        self.assertEqual(
            manquantes, [],
            'Clé(s) de contexte absente(s) : %s. Une étape qui la lit '
            's\'omettrait en silence sur toute la flotte.' % manquantes)

    def test_le_pan_porte_l_azimut_pvgis_et_sa_geometrie_brute(self):
        contexte, meta = construire_contexte(_Calepinage(),
                                             materiel=MATERIEL,
                                             reglages=REGLAGES)

        plan = contexte['plans'][0]
        self.assertEqual(plan['cle'], 'PAN-A')
        self.assertEqual(plan['azimut_deg'], 180.0)
        # Convention PVGIS : 0 = sud. Un azimut de FACE à 180° (plein sud)
        # devient donc 0 — c'est la conversion, pas un chiffre inventé.
        self.assertEqual(plan['azimut_pvgis_deg'], 0.0)
        self.assertEqual(plan['geometry']['tiltDeg'], 15.0)
        self.assertEqual(plan['type_pose'], 'surimposition')
        self.assertEqual([p['cle'] for p in meta['plans_equipes']], ['PAN-A'])

    def test_l_ombrage_porte_le_document_pour_l_acces_par_module(self):
        contexte, _meta = construire_contexte(_Calepinage(),
                                              materiel=MATERIEL,
                                              reglages=REGLAGES)

        self.assertIs(contexte['ombrage']['layout'], contexte['layout'])

    def test_les_postes_saisis_restent_la_liste_plate(self):
        calepinage = _Calepinage(pertes=[
            {'poste': 'soiling', 'libelle': 'Salissure', 'pct': 2.0,
             'source': 'societe'},
        ])
        contexte, _meta = construire_contexte(calepinage, materiel=MATERIEL,
                                              reglages=REGLAGES)

        self.assertIsInstance(contexte['postes_saisis'], list)
        self.assertEqual(contexte['postes_saisis'][0]['poste'], 'soiling')

    def test_aucune_epingle_aucune_coordonnee_inventee(self):
        sans_pin = {cle: valeur for cle, valeur in LAYOUT.items()
                    if cle != 'pin'}
        contexte, _meta = construire_contexte(_Calepinage(sans_pin),
                                              materiel=MATERIEL,
                                              reglages=REGLAGES)

        self.assertIsNone(contexte['site']['lat'])
        self.assertIsNone(contexte['site']['lon'])


# ═══════════════════════════════════════════════════════════════════════════
# 2. LES REFUS — chacun NOMME son champ
# ═══════════════════════════════════════════════════════════════════════════

class RefusTest(SimpleTestCase):
    """Un refus pointe LE champ à corriger, jamais un message générique."""

    def test_sans_mode_meteo_la_simulation_est_refusee_en_le_nommant(self):
        reglages = dict(REGLAGES, simulation={})

        with self.assertRaises(SimulationRefusee) as refus:
            _simuler(reglages=reglages)

        self.assertEqual(refus.exception.champ,
                         'parametres.simulation.mode_meteo')
        self.assertIn('mode météo', refus.exception.motif)

    def test_un_mode_inconnu_est_refuse_sous_la_meme_cle(self):
        reglages = dict(REGLAGES, simulation={
            'mode_meteo': {'valeur': 'meteonorm', 'source': 'note'},
        })

        with self.assertRaises(SimulationRefusee) as refus:
            _simuler(reglages=reglages)

        self.assertEqual(refus.exception.champ,
                         'parametres.simulation.mode_meteo')

    def test_le_mode_annee_type_est_refuse_en_nommant_l_irradiance(self):
        reglages = dict(REGLAGES, simulation={
            'mode_meteo': {'valeur': 'tmy', 'source': 'note interne'},
        })

        with self.assertRaises(SimulationRefusee) as refus:
            _simuler(reglages=reglages)

        self.assertEqual(refus.exception.champ,
                         'parametres.simulation.mode_meteo')
        self.assertIn('horizontale', refus.exception.motif.lower())

    def test_sans_pan_equipe_le_refus_nomme_les_plans(self):
        vide = dict(LAYOUT, zones=[])

        with self.assertRaises(SimulationRefusee) as refus:
            _simuler(_Calepinage(vide))

        self.assertEqual(refus.exception.champ, 'plans')

    def test_sans_epingle_le_refus_nomme_le_point_du_site(self):
        sans_pin = {cle: valeur for cle, valeur in LAYOUT.items()
                    if cle != 'pin'}

        with self.assertRaises(SimulationRefusee) as refus:
            _simuler(_Calepinage(sans_pin))

        self.assertEqual(refus.exception.champ, 'site.pin')


# ═══════════════════════════════════════════════════════════════════════════
# 3. LA CHAÎNE RÉELLE — la production est un NOMBRE, la cascade est complète
# ═══════════════════════════════════════════════════════════════════════════

class ChaineReelleTest(SimpleTestCase):
    """La simulation passe par la VRAIE chaîne, pas par une doublure."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rendu = _simuler()
        cls.blocs = cls.rendu['blocs']

    def test_la_production_annuelle_est_un_nombre(self):
        p50 = self.blocs['production']['total']['p50_kwh']

        self.assertIsInstance(p50, float)
        self.assertGreater(p50, 0.0)

    def test_la_cascade_suit_l_ordre_des_etapes(self):
        ordre = [etape['etape'] for etape in self.blocs['cascade']['etapes']]

        self.assertEqual(ordre, list(ORDRE_ETAPES))

    def test_chaque_etape_publie_les_douze_cles_du_contrat(self):
        attendues = sorted(CONTRAT['exemple']['cascade']['etapes'][0])

        for etape in self.blocs['cascade']['etapes']:
            self.assertEqual(sorted(etape), attendues, etape['etape'])

    def test_la_meteo_publiee_compte_les_appels_reellement_partis(self):
        # UN pan, UNE requête : la mémoire du fournisseur est devant le
        # client, elle ne le contourne pas.
        self.assertEqual(self.blocs['meteo']['appels_pvgis'], 1)
        self.assertEqual(self.blocs['meteo']['service'], 'seriescalc')

    def test_l_entete_de_simulation_porte_l_empreinte_et_la_duree(self):
        entete = self.blocs[service.CLE_SIMULATION]

        self.assertEqual(entete['hash_entree'], self.rendu['hash_entree'])
        self.assertTrue(entete['calcule_le'].endswith('Z'))
        self.assertIsInstance(entete['duree_s'], float)
        self.assertTrue(entete['version_moteur'])

    def test_les_blocs_du_contrat_sont_tous_ecrits(self):
        attendus = {'production', 'cascade', 'meteo', 'serie_horaire',
                    'incertitude', 'performance', 'validation',
                    'autoconsommation', 'batterie', 'hors_reseau',
                    'consommation', service.CLE_SIMULATION}

        self.assertEqual(sorted(attendus - set(self.blocs)), [])

    def test_les_pertes_saisies_ne_sont_jamais_reecrites(self):
        # D-CALX 11 : ``resultat['pertes']`` est la liste plate des postes
        # SAISIS ; la simulation n'y touche pas.
        self.assertNotIn('pertes', self.blocs)

    def test_sans_fuseau_les_trois_blocs_horaires_sont_omis_avec_leur_motif(
            self):
        for nom in ('batterie', 'autoconsommation', 'hors_reseau'):
            with self.subTest(bloc=nom):
                self.assertTrue(self.blocs[nom]['motif_absence'],
                                'Le bloc « %s » doit DIRE pourquoi il est '
                                'omis.' % nom)

    def test_la_projection_pluriannuelle_a_sa_cle_propre(self):
        # ARBITRAGE de clôture : ``annees[]`` reste les années MÉTÉO
        # observées, la projection de vieillissement vit sous ``projection``.
        production = self.blocs['production']
        self.assertIn('projection', production)
        self.assertIsInstance(production['projection'], list)
        for ligne in production['annees']:
            self.assertEqual(sorted(ligne), ['annee', 'kwh', 'source'])

    def test_l_incertitude_refuse_les_quantiles_sans_sigma_source(self):
        # Aucune composante saisie : σ ne peut pas être publié, et les
        # quantiles restent nuls AVEC leur motif (jamais un P50 recopié).
        incertitude = self.blocs['incertitude']
        if incertitude['sigma_total'] is None:
            self.assertTrue(incertitude['motif_refus'])
            self.assertIsNone(incertitude['quantiles']['p90_kwh'])

    def test_la_validation_est_publiee_sans_ecart_faute_de_mesure(self):
        validation = self.blocs['validation']

        self.assertIsNone(validation['ecart_pct'])
        self.assertTrue(validation['motif'])

    def test_aucun_chiffre_n_entre_sans_la_serie(self):
        # La série d'entrée est la DÉFINITION du kWc : p_w = kWc × G(i).
        # Un point sans irradiance n'a donc pas de puissance — pas un zéro.
        reponse = _reponse_meteo()
        reponse['points'][0]['gi_w_m2'] = None
        rendu = _simuler(client=_ClientRejoue(reponse))

        premier = rendu['blocs']['serie_horaire']['points'][0]
        self.assertIsNone(premier['p_w'])


class FraicheurTest(SimpleTestCase):
    """``forcer=False`` et empreinte inchangée ⇒ aucun recalcul."""

    def test_une_entree_inchangee_rend_la_date_du_calcul_existant(self):
        empreinte = _simuler()['hash_entree']
        calepinage = _Calepinage(resultat={
            service.CLE_SIMULATION: {'hash_entree': empreinte,
                                     'calcule_le': '2026-09-21T10:15:00Z'},
        })

        rendu = _simuler(calepinage)

        self.assertTrue(rendu['deja_calcule'])
        self.assertEqual(rendu['calcule_le'], '2026-09-21T10:15:00Z')

    def test_forcer_recalcule_malgre_l_empreinte_inchangee(self):
        empreinte = _simuler()['hash_entree']
        calepinage = _Calepinage(resultat={
            service.CLE_SIMULATION: {'hash_entree': empreinte,
                                     'calcule_le': '2026-09-21T10:15:00Z'},
        })

        rendu = _simuler(calepinage, forcer=True)

        self.assertFalse(rendu['deja_calcule'])
        self.assertIn('blocs', rendu)


class ServiParResultatTest(SimpleTestCase):
    """CALX70 — ce que la simulation ÉCRIT, ``GET resultat/`` le SERT."""

    def _servi(self, blocs, entete):
        from apps.calepinage.services.electrique import resultat_calepinage

        stocke = dict(blocs)
        stocke[service.CLE_SIMULATION] = entete
        calepinage = _Calepinage(resultat=stocke)
        return resultat_calepinage(calepinage, materiel=MATERIEL)

    def test_une_simulation_fraiche_est_servie_telle_quelle(self):
        rendu = _simuler()
        blocs = rendu['blocs']

        servi = self._servi(blocs, blocs[service.CLE_SIMULATION])

        self.assertTrue(servi['simule'])
        self.assertFalse(servi['simulation_perimee'])
        self.assertEqual(servi['production']['total']['p50_kwh'],
                         blocs['production']['total']['p50_kwh'])
        self.assertEqual(servi['calcule_le'],
                         blocs[service.CLE_SIMULATION]['calcule_le'])

    def test_une_empreinte_perimee_ne_sert_aucun_chiffre(self):
        blocs = _simuler()['blocs']
        entete = dict(blocs[service.CLE_SIMULATION], hash_entree='0' * 64)

        servi = self._servi(blocs, entete)

        self.assertTrue(servi['simulation_perimee'])
        self.assertIsNone(servi['production'])
        # D-CALX 11 : ``pertes`` garde son TYPE même périmée.
        self.assertEqual(servi['pertes'], [])
        self.assertTrue(servi['motif'])


# ═══════════════════════════════════════════════════════════════════════════
# 4. LA PORTE HTTP — routée, en POST, sur le kind EXISTANT
# ═══════════════════════════════════════════════════════════════════════════

class PorteHttpTest(SimpleTestCase):
    """L'action est DÉCOUVERTE par le routeur DRF, sous le bon chemin."""

    def test_l_action_simuler_est_rattachee_au_viewset(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet

        par_nom = {action.__name__: action
                   for action in CalepinageViewSet.get_extra_actions()}

        self.assertIn('simuler', par_nom)
        self.assertEqual(set(par_nom['simuler'].mapping), {'post'})

    def test_le_chemin_est_celui_du_contrat(self):
        from django.urls import reverse

        self.assertEqual(
            reverse('calepinage-simuler', args=('1',)),
            '/api/django/calepinage/calepinages/1/simuler/')

    def test_la_garde_est_celle_de_la_gestion(self):
        from apps.calepinage.permissions import PeutGererCalepinage
        from apps.calepinage.views.simulation import simuler

        self.assertIn(PeutGererCalepinage,
                      simuler.kwargs['permission_classes'])

    def test_le_suivi_passe_par_le_kind_existant(self):
        # D-CALX 12 — un SECOND kind rendrait GET moteur/resultat/<job>/ 404.
        from apps.calepinage.tasks import KIND_CALEPINAGE, NATURE_SIMULATION

        self.assertEqual(KIND_CALEPINAGE, 'calepinage')
        self.assertEqual(NATURE_SIMULATION, 'simulation')

    def test_l_accuse_a_les_cles_du_contrat(self):
        from apps.calepinage.views.simulation import accuse_de_simulation

        class _Job:
            pk = 7
            kind = 'calepinage'
            statut = 'en_attente'
            progress_pct = 0
            message_erreur = ''

        self.assertEqual(sorted(accuse_de_simulation(_Job())),
                         sorted(CONTRAT['exemple_accepte']))


# ═══════════════════════════════════════════════════════════════════════════
# 5. LE CONTRAT COMMITTÉ — la FORME, jamais les valeurs
# ═══════════════════════════════════════════════════════════════════════════

class ContratTest(SimpleTestCase):
    """L'échantillon décrit ce que les producteurs publient RÉELLEMENT."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.blocs = _simuler()['blocs']

    def test_l_echantillon_porte_les_trois_cles_de_pact10(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, CONTRAT)

    def test_l_endpoint_est_celui_de_l_action(self):
        self.assertEqual(
            CONTRAT['endpoint'],
            'POST /api/django/calepinage/calepinages/<int:pk>/simuler/')

    def test_les_pertes_restent_une_liste(self):
        # D-CALX 11 : quatre lecteurs itèrent ``pertes`` telle quelle.
        self.assertIsInstance(CONTRAT['exemple']['pertes'], list)
        self.assertIsInstance(CONTRAT['exemple_vide']['pertes'], list)

    def test_l_entete_de_simulation_a_les_quatre_cles(self):
        self.assertEqual(
            sorted(CONTRAT['exemple']['simulation']),
            ['calcule_le', 'duree_s', 'hash_entree', 'version_moteur'])
        self.assertEqual(sorted(self.blocs[service.CLE_SIMULATION]),
                         sorted(CONTRAT['exemple']['simulation']))

    def test_la_cascade_servie_a_les_cles_de_l_echantillon(self):
        self.assertEqual(sorted(self.blocs['cascade']),
                         sorted(CONTRAT['exemple']['cascade']))

    def test_la_meteo_servie_a_les_cles_de_l_echantillon(self):
        self.assertEqual(sorted(self.blocs['meteo']),
                         sorted(CONTRAT['exemple']['meteo']))

    def test_la_serie_horaire_servie_a_les_cles_de_l_echantillon(self):
        self.assertEqual(sorted(self.blocs['serie_horaire']),
                         sorted(CONTRAT['exemple']['serie_horaire']))

    def test_l_incertitude_servie_a_les_cles_de_l_echantillon(self):
        self.assertEqual(sorted(self.blocs['incertitude']),
                         sorted(CONTRAT['exemple']['incertitude']))

    def test_la_validation_servie_a_les_cles_de_l_echantillon(self):
        self.assertEqual(sorted(self.blocs['validation']),
                         sorted(CONTRAT['exemple']['validation']))

    def test_les_trois_blocs_horaires_omis_ont_les_cles_de_exemple_vide(self):
        for nom in ('batterie', 'autoconsommation', 'hors_reseau'):
            with self.subTest(bloc=nom):
                self.assertEqual(sorted(self.blocs[nom]),
                                 sorted(CONTRAT['exemple_vide'][nom]))

    def test_la_production_servie_couvre_les_cles_de_l_echantillon(self):
        # ``par_module`` / ``par_chaine`` n'entrent que lorsque le document
        # porte un accès solaire par module (CALX182) : l'échantillon les
        # décrit, le cas d'essai ne les produit pas.
        attendues = set(CONTRAT['exemple']['production'])
        servies = set(self.blocs['production'])

        self.assertEqual(sorted(attendues - servies - {'par_module',
                                                       'par_chaine'}), [])
        self.assertEqual(sorted(servies - attendues), [])


# ═══════════════════════════════════════════════════════════════════════════
# 6. L'ÉCRITURE EN BASE — écrite, NON EXÉCUTÉE sur le poste (aucune base)
# ═══════════════════════════════════════════════════════════════════════════

class EcritureTest(TestCase):
    """La fusion de clés préserve ce que la simulation ne produit pas.

    NON EXÉCUTÉ localement : ``TestCase`` exige une base de données, et le
    poste de développement n'en a pas. Ce test tourne en CI.
    """

    def test_la_fusion_preserve_les_cles_etrangeres(self):
        from authentication.models import Company

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client

        societe = Company.objects.create(nom='Simulation Co',
                                         slug='simulation-co')
        client = Client.objects.create(company=societe, nom='Client')
        calepinage = Calepinage.objects.create(
            company=societe, client=client, titre='Simulation',
            roof_layout=LAYOUT,
            resultat={'entree_electrique': {'phases': 3},
                      'pertes': [{'poste': 'soiling', 'pct': 2.0}]})

        service._fusionner(calepinage, {'production': {'total': {}}})

        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat['entree_electrique'],
                         {'phases': 3})
        self.assertEqual(len(calepinage.resultat['pertes']), 1)
        self.assertIn('production', calepinage.resultat)
