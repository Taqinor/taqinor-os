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
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.calepinage.services import simulation as service
from apps.calepinage.services.chaine_pertes import ORDRE_ETAPES
from apps.calepinage.services.simulation import (
    SimulationRefusee, construire_contexte, simuler_calepinage,
)
from apps.calepinage.tests._m0_en_attente import (
    EN_ATTENTE_SIMULATION as EN_ATTENTE, affirmer_non_servies, sans,
)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_simulation.json').read_text(encoding='utf-8'))
#: L'exemple privé des clés posées par ACAL8 avant leurs producteurs.
SERVI = sans(CONTRAT['exemple'], EN_ATTENTE)

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


def _geo(ville):
    """Le contexte géographique d'un lead SANS repère, de ville ``ville``."""
    return {'pin': None, 'outline': None, 'adresse': ville, 'ville': ville,
            'source': None}


class SiteSansEpingleTest(SimpleTestCase):
    """T4-U1-003 — jamais une simulation sur un point par défaut anonyme.

    Le toit créé « par ses dimensions » sur une carte jamais localisée
    arrivait avec l'épingle au CENTRE PAR DÉFAUT de la carte (31,79 ; −7,09) :
    le rapport imprimait « Coordonnées — », 737 m d'altitude et 1 832 kWh/kWc
    contre 1 599 au devis. Sans épingle, le site est la ville de référence du
    devis (dite) ; sans ville résolue, la simulation est refusée.
    """

    CENTRE = {'lat': 31.789999999984182, 'lng': -7.089999999999918}

    def _sans_pin(self, pin=None):
        layout = {cle: valeur for cle, valeur in LAYOUT.items()
                  if cle != 'pin'}
        if pin is not None:
            layout['pin'] = pin
        return _Calepinage(layout)

    def test_epingle_posee_simulee_telle_quelle_sans_site_de_reference(self):
        client = _ClientRejoue()
        resultat = _simuler(client=client)

        self.assertEqual(client.demandes[0]['lat'], 33.5731)
        self.assertEqual(client.demandes[0]['lon'], -7.5898)
        self.assertNotIn('site', resultat['blocs']['meteo'])

    def _sur_ville(self, calepinage, ville):
        client = _ClientRejoue()
        with mock.patch('apps.calepinage.selectors.contexte_geographique',
                        return_value=_geo(ville)):
            resultat = _simuler(calepinage, client=client)
        return client, resultat

    def test_centre_par_defaut_et_ville_connue_ville_de_reference_dite(self):
        client, resultat = self._sur_ville(self._sans_pin(self.CENTRE),
                                           'casa')

        self.assertEqual((client.demandes[0]['lat'],
                          client.demandes[0]['lon']), (33.573, -7.59))
        site = resultat['blocs']['meteo']['site']
        self.assertEqual(site['source'], 'ville_reference')
        self.assertEqual(site['ville_reference'], 'Casablanca')
        self.assertEqual(site['libelle'], 'Casablanca (ville de référence)')

    def test_sans_epingle_et_ville_connue_ville_de_reference_dite(self):
        client, resultat = self._sur_ville(self._sans_pin(), 'casa')

        self.assertEqual(client.demandes[0]['lat'], 33.573)
        self.assertEqual(resultat['blocs']['meteo']['site']['libelle'],
                         'Casablanca (ville de référence)')

    def test_sans_epingle_ni_ville_refus_dit_quoi_faire_rien_ecrit(self):
        for pin in (None, self.CENTRE):
            calepinage = self._sans_pin(pin)
            with self.subTest(pin=pin), mock.patch(
                    'apps.calepinage.selectors.contexte_geographique',
                    return_value=_geo('')), \
                    self.assertRaises(SimulationRefusee) as refus:
                _simuler(calepinage, enregistrer=True)
            self.assertEqual(refus.exception.champ, 'site.pin')
            self.assertTrue(refus.exception.motif.startswith(
                "Position du site manquante : posez l'épingle du site"))
            self.assertIn('ville du lead', refus.exception.motif)
            self.assertIsNone(calepinage.resultat)

    # T4-U4-013 — un toit tracé par clics à l'échelle du pays : l'épingle est
    # le centre du tracé, À CÔTÉ du centre par défaut (pas dessus), et le
    # document dit que personne n'a localisé le site (``siteLocalise: null``).
    TRACE_PAYS = {'lat': 31.6123, 'lng': -7.3456}

    def _trace_sans_site(self, provenance=None):
        calepinage = self._sans_pin(self.TRACE_PAYS)
        calepinage.roof_layout['siteLocalise'] = provenance
        return calepinage

    def test_t4_u4_013_trace_au_niveau_pays_sans_lead_refuse_rien_ecrit(self):
        calepinage = self._trace_sans_site()
        client = _ClientRejoue()
        with mock.patch('apps.calepinage.selectors.contexte_geographique',
                        return_value={'pin': None, 'outline': None,
                                      'adresse': None, 'ville': None,
                                      'source': None}), \
                self.assertRaises(SimulationRefusee) as refus:
            _simuler(calepinage, client=client, enregistrer=True)
        self.assertEqual(refus.exception.champ, 'site.pin')
        self.assertEqual(client.demandes, [])
        self.assertIsNone(calepinage.resultat)

    def test_t4_u4_013_trace_au_niveau_pays_lead_a_marrakech_dit(self):
        client, resultat = self._sur_ville(self._trace_sans_site(),
                                           'Marrakech')
        self.assertEqual(client.demandes[0]['lat'], 31.63)
        site = resultat['blocs']['meteo']['site']
        self.assertEqual(site['ville_reference'], 'Marrakech')
        self.assertEqual(site['libelle'], 'Marrakech (ville de référence)')

    def test_t4_u4_013_client_sans_lead_adresse_casablanca_dite(self):
        calepinage = self._trace_sans_site()
        client = _ClientRejoue()
        with mock.patch('apps.calepinage.selectors.contexte_geographique',
                        return_value={'pin': None, 'outline': None,
                                      'adresse': 'Casablanca', 'ville': None,
                                      'source': None}):
            resultat = _simuler(calepinage, client=client)
        self.assertEqual(client.demandes[0]['lat'], 33.573)
        self.assertEqual(resultat['blocs']['meteo']['site']['ville_reference'],
                         'Casablanca')

    def test_t4_u4_013_epingle_localisee_par_l_utilisateur_inchangee(self):
        for provenance in ('adresse', 'epingle', 'trace', 'lead'):
            client = _ClientRejoue()
            with self.subTest(provenance=provenance), mock.patch(
                    'apps.calepinage.selectors.contexte_geographique',
                    return_value=_geo('Marrakech')):
                resultat = _simuler(self._trace_sans_site(provenance),
                                    client=client)
                self.assertEqual((client.demandes[0]['lat'],
                                  client.demandes[0]['lon']),
                                 (31.6123, -7.3456))
                self.assertNotIn('site', resultat['blocs']['meteo'])

    def test_t4_u4_013_document_ancien_sans_provenance(self):
        """Règle sans migration : sans ``siteLocalise``, une épingle à moins de
        2 km d'un centre par défaut n'est pas un site, plus loin elle l'est."""
        pres = {'lat': 31.795, 'lng': -7.085}
        client, resultat = self._sur_ville(self._sans_pin(pres), 'Marrakech')
        self.assertEqual(resultat['blocs']['meteo']['site']['ville_reference'],
                         'Marrakech')
        client, resultat = self._sur_ville(self._sans_pin(self.TRACE_PAYS),
                                           'Marrakech')
        self.assertEqual(client.demandes[0]['lat'], 31.6123)
        self.assertNotIn('site', resultat['blocs']['meteo'])


class SiteDuLeadEnBaseTest(TestCase):
    """T4-U1-003, le cas réel en base : la géométrie porte le centre de carte
    par défaut, aucune épingle n'a été posée, le lead dit sa ville."""

    CENTRE = {'lat': 31.789999999984182, 'lng': -7.089999999999918}

    def _site(self, ville, pin):
        from authentication.models import Company

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead

        societe = Company.objects.create(nom='T4U1003', slug='t4u1003')
        lead = Lead.objects.create(company=societe, nom='Villa U1',
                                   ville=ville)
        layout = dict(LAYOUT, pin=pin)
        calepinage = Calepinage.objects.create(
            company=societe, lead_id=lead.pk, titre='Pose U1',
            roof_layout=layout)
        contexte, _meta = construire_contexte(calepinage, materiel=MATERIEL,
                                              reglages=REGLAGES)
        return contexte['site']

    def test_centre_par_defaut_et_lead_a_casablanca_site_de_reference(self):
        site = self._site('Casablanca', self.CENTRE)
        self.assertEqual((site['lat'], site['lon']), (33.573, -7.59))
        self.assertEqual(site['source'], 'ville_reference')
        self.assertEqual(site['libelle'], 'Casablanca (ville de référence)')

    def test_centre_par_defaut_sans_ville_aucun_point(self):
        site = self._site('', self.CENTRE)
        self.assertIsNone(site['lat'])
        self.assertNotIn('source', site)

    def test_epingle_posee_inchangee(self):
        site = self._site('Casablanca', {'lat': 33.5731, 'lng': -7.5898})
        self.assertEqual((site['lat'], site['lon']), (33.5731, -7.5898))
        self.assertNotIn('source', site)


# ═══════════════════════════════════════════════════════════════════════════
# 3. LA CHAÎNE RÉELLE — la production est un NOMBRE, la cascade est complète
# ═══════════════════════════════════════════════════════════════════════════

class ChaineReelleTest(SimpleTestCase):
    """La simulation passe par la VRAIE chaîne, pas par une doublure."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client_rejoue = _ClientRejoue()
        cls.rendu = _simuler(client=cls.client_rejoue)
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
        # Le compteur publié = les requêtes réellement parties : ce client
        # double ne répond jamais « depuis le cache », chaque demande compte.
        # Chaîne : UN pan, UNE requête, + UNE à 0° (ACAL706, gain
        # d'inclinaison) ; ACAL744 (comparer_bases) : + DEUX requêtes (la
        # base principale puis l'autre base), soit 4.
        self.assertEqual(self.blocs['meteo']['appels_pvgis'],
                         len(self.client_rejoue.demandes))
        self.assertEqual(self.blocs['meteo']['appels_pvgis'], 4)
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
            # ACAL54 — chaque année porte ``observe: true`` : un total
            # OBSERVÉ, jamais forcé à sommer au P50.
            self.assertEqual(sorted(ligne),
                             ['annee', 'kwh', 'observe', 'source'])
            self.assertIs(ligne['observe'], True)

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
        # ACAL48 — les réglages société entrent dans l'empreinte de
        # simulation : la lecture voit les MÊMES réglages que le calcul.
        return resultat_calepinage(calepinage, materiel=MATERIEL,
                                   reglages=REGLAGES)

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
        # ACAL8 (contrat v2) : + version_simulation, reglages_utilises,
        # meteo_fichier — servies par leurs producteurs (EN_ATTENTE).
        self.assertEqual(
            sorted(CONTRAT['exemple']['simulation']),
            ['calcule_le', 'duree_s', 'hash_entree', 'meteo_fichier',
             'reglages_utilises', 'version_moteur', 'version_simulation'])
        affirmer_non_servies(self, self.blocs, EN_ATTENTE)
        self.assertEqual(sorted(self.blocs[service.CLE_SIMULATION]),
                         sorted(SERVI['simulation']))

    def test_la_cascade_servie_a_les_cles_de_l_echantillon(self):
        self.assertEqual(sorted(self.blocs['cascade']),
                         sorted(SERVI['cascade']))

    def test_la_meteo_servie_a_les_cles_de_l_echantillon(self):
        self.assertEqual(sorted(self.blocs['meteo']),
                         sorted(SERVI['meteo']))

    def test_la_serie_horaire_servie_a_les_cles_de_l_echantillon(self):
        self.assertEqual(sorted(self.blocs['serie_horaire']),
                         sorted(CONTRAT['exemple']['serie_horaire']))

    def test_l_incertitude_servie_a_les_cles_de_l_echantillon(self):
        self.assertEqual(sorted(self.blocs['incertitude']),
                         sorted(CONTRAT['exemple']['incertitude']))

    def test_la_validation_servie_a_les_cles_de_l_echantillon(self):
        self.assertEqual(sorted(self.blocs['validation']),
                         sorted(CONTRAT['exemple']['validation']))

    def test_acal787_le_total_batterie_servi_a_les_cles_de_l_echantillon(self):
        # Le cas d'essai omet la batterie (pas de fuseau) : le total est
        # produit par l'étape réelle sur la série synthétique de CALX188.
        from apps.calepinage.services.etapes import batterie as etape
        from apps.calepinage.tests.test_calx188_batterie import (
            contexte_de_test, serie_de_test,
        )

        _suite, servi = etape.bloc_batterie(
            serie_de_test(heures=48),
            contexte_de_test(strategie='peak_shaving', heures=48,
                             seuil_effacement_kw=0.5))
        for nom in ('exemple', 'exemple_borne_haute'):
            with self.subTest(exemple=nom):
                attendu = CONTRAT[nom]['batterie']['total']
                self.assertEqual(sorted(servi['total']), sorted(attendu))
                self.assertEqual(sorted(servi['total']['energie']),
                                 sorted(attendu['energie']))
                self.assertEqual(sorted(servi['total']['vieillissement']),
                                 sorted(attendu['vieillissement']))
                # ACAL793 — les faits de la série.
                self.assertEqual(sorted(servi['total']['faits_serie']),
                                 sorted(attendu['faits_serie']))
                # ACAL794 — le mot de verdict : null + motif sans réglage.
                self.assertEqual(
                    sorted(attendu['verdict'] or ['mot', 'seuils_utilises']),
                    ['mot', 'seuils_utilises'])
        # ACAL797 — le secours : coupures null + motif, ou le bloc rejoué.
        sec = CONTRAT['exemple']['batterie']['total']['secours']
        self.assertIsNone(sec['coupures'])
        self.assertTrue(sec['motif_coupures'])
        rejoue = CONTRAT['exemple_borne_haute']['batterie']['total'][
            'secours']['coupures']
        self.assertEqual(sorted(rejoue), sorted([
            'nombre_par_an', 'duree_h', 'heure_debut', 'jours_testes',
            'energie_non_fournie_par_coupure_moyenne_kwh',
            'energie_non_fournie_par_coupure_pire_kwh',
            'energie_non_fournie_kwh', 'mention']))
        self.assertEqual(servi['total']['secours'].keys(), sec.keys())
        # ACAL798 — la liste d'appareils de l'exemple borne haute.
        liste = CONTRAT['exemple_borne_haute']['batterie']['total'][
            'secours']['appareils']
        self.assertEqual(sorted(liste[0]), sorted([
            'nom', 'quantite', 'puissance_continue_kw', 'heures_tenues']))
        self.assertIsNone(sec['appareils'])
        self.assertIsNone(CONTRAT['exemple']['batterie']['total']['verdict'])
        self.assertTrue(
            CONTRAT['exemple']['batterie']['total']['motif_verdict'])
        self.assertIn(
            CONTRAT['exemple_borne_haute']['batterie']['total'][
                'verdict']['mot'], ('trop_petite', 'trop_grande', 'adaptee'))
        self.assertIsNone(CONTRAT['exemple_vide']['batterie']['total'])

    def test_acal801_le_groupe_d_appoint_servi_a_les_cles_de_l_echantillon(
            self):
        from apps.calepinage.services.etapes import hors_reseau as etape
        from apps.calepinage.tests.test_calx191_hors_reseau import (
            GROUPE, contexte_de_test, serie_de_test,
        )

        contexte = contexte_de_test(heures=720, jours=0.1)
        contexte[etape.CLE_CONTEXTE]['groupe'] = GROUPE
        _suite, servi = etape.bloc_hors_reseau(serie_de_test(heures=720),
                                               contexte)
        self.assertEqual(sorted(servi), sorted(
            CONTRAT['exemple']['hors_reseau']))
        for nom in ('exemple', 'exemple_borne_haute'):
            with self.subTest(exemple=nom):
                attendu = CONTRAT[nom]['hors_reseau']['groupe']
                self.assertEqual(sorted(servi['groupe']), sorted(attendu))
                self.assertEqual(sorted(servi['groupe']['par_mois'][0]),
                                 sorted(attendu['par_mois'][0]))
        self.assertIsNone(CONTRAT['exemple_vide']['hors_reseau']['groupe'])
        # ACAL802 — la banque du mois chargé : mêmes clés que l'étape.
        from apps.calepinage.tests.test_calx191_hors_reseau import (
            contexte_de_test as contexte_hr, serie_de_test as serie_hr,
        )

        _suite, annuel = etape.bloc_hors_reseau(
            serie_hr(), contexte_hr(jours=2.0))
        for nom in ('exemple', 'exemple_borne_haute'):
            with self.subTest(exemple=nom, bloc='banque_mois_charge'):
                self.assertEqual(
                    sorted(annuel['banque_mois_charge']),
                    sorted(CONTRAT[nom]['hors_reseau']['banque_mois_charge']))
        self.assertIsNone(
            CONTRAT['exemple_vide']['hors_reseau']['banque_mois_charge'])

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

    def test_la_maille_electrique_est_au_contrat_et_toujours_servie(self):
        # CALX183 — les TROIS blocs de `agregation_electrique` sont toujours
        # PRÉSENTS. Sans table d'affectation ils valent `null` et leur motif
        # part dans `avertissements` : jamais des zéros.
        for cle in service.CLES_AGREGATION:
            with self.subTest(cle=cle):
                self.assertIn(cle, CONTRAT['exemple']['production'])
                self.assertIn(cle, CONTRAT['exemple_vide']['production'])
                self.assertIsNone(CONTRAT['exemple_vide']['production'][cle])
                self.assertIn(cle, self.blocs['production'])

    def test_chaque_chaine_de_l_echantillon_porte_ses_deux_pertes(self):
        # CALX183 — la maille chaîne porte mismatch et écrêtage ; une perte
        # non publiée DIT pourquoi (D-CALX 7), et les clés de CALX182 ne
        # disparaissent pas au passage.
        for ligne in CONTRAT['exemple']['production']['par_chaine']:
            for cle in service.CLES_PERTE_CHAINE:
                self.assertIn(cle, ligne)
            for cle in ('kwc', 'acces_solaire_min_pct',
                        'ecart_intra_chaine_pct', 'source'):
                self.assertIn(cle, ligne)
            if ligne['perte_mismatch_pct'] is None:
                self.assertTrue(ligne['motif_mismatch'])
            if ligne['perte_ecretage_pct'] is None:
                self.assertTrue(ligne['motif_ecretage'])


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

        # ACAL57 — ``_fusionner`` a disparu au profit de l'écrivain unique.
        from apps.calepinage.services.resultat import modifier_resultat

        modifier_resultat(calepinage, lambda resultat: resultat.update(
            {'production': {'total': {}}}))

        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat['entree_electrique'],
                         {'phases': 3})
        self.assertEqual(len(calepinage.resultat['pertes']), 1)
        self.assertIn('production', calepinage.resultat)


class _ProcessusTue(BaseException):
    """Le processus tué par le système (SIGKILL) : aucune exception Python
    n'est attrapée par la tâche, le job reste « en cours » et le message est
    remis en file (``CELERY_TASK_ACKS_LATE`` + ``REJECT_ON_WORKER_LOST``)."""


class LivraisonsBorneesTest(TestCase):
    """ACAL1622 — un calcul que le serveur tue deux fois finit en échec DIT."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        from authentication.models import Company
        from core.models import BackgroundJob

        from apps.calepinage.models import Calepinage
        from apps.calepinage.tasks import KIND_CALEPINAGE
        from apps.crm.models import Lead

        self.societe = Company.objects.create(nom='ACAL1622', slug='acal1622')
        user = get_user_model().objects.create_user(
            username='acal1622', password='x', company=self.societe)
        lead = Lead.objects.create(company=self.societe, nom='Toiture 1622')
        self.calepinage = Calepinage.objects.create(
            company=self.societe, lead_id=lead.pk, titre='Tué 1622',
            roof_layout=LAYOUT)
        self.job = BackgroundJob.objects.create(
            company=self.societe, user=user, kind=KIND_CALEPINAGE,
            statut=BackgroundJob.STATUT_QUEUED)

    def _livrer(self, tache, **corps):
        return tache(job_id=self.job.pk, company_id=self.societe.pk,
                     calepinage_id=self.calepinage.pk, **corps)

    def test_troisieme_livraison_d_un_job_deja_en_cours_echec_dit(self):
        from unittest import mock

        from apps.calepinage import tasks

        with mock.patch('apps.calepinage.services.simulation.'
                        'simuler_calepinage',
                        side_effect=_ProcessusTue) as calcul:
            for _ in range(2):
                with self.assertRaises(_ProcessusTue):
                    self._livrer(tasks.simuler_calepinage)
            self.job.refresh_from_db()
            self.assertEqual((self.job.statut, self.job.progress_pct),
                             ('running', 5))
            issue = self._livrer(tasks.simuler_calepinage)

        # Le calcul n'est PAS relancé une troisième fois.
        self.assertEqual(calcul.call_count, 2)
        self.assertEqual(issue['statut'], 'failed')
        self.job.refresh_from_db()
        self.assertEqual(self.job.statut, 'failed')
        self.assertIn('le calcul a été interrompu par le serveur (mémoire) : '
                      'réessayez ou réduisez la fenêtre météo',
                      self.job.message_erreur)
        # Relire / rouvrir : la charge servie à l'écran porte le motif.
        charge = tasks.resultat_du_job(self.job)
        self.assertEqual(charge['elements'][0]['statut'], 'failed')
        self.assertIn('interrompu', charge['elements'][0]['motif'])

    def test_une_tache_normale_n_est_jamais_marquee_en_echec(self):
        from unittest import mock

        from apps.calepinage import tasks

        rendu = {'deja_calcule': True, 'hash_entree': 'h',
                 'calcule_le': '2026-11-23T10:00:00Z'}
        with mock.patch('apps.calepinage.services.simulation.'
                        'simuler_calepinage', return_value=rendu):
            issue = self._livrer(tasks.simuler_calepinage)
        self.assertEqual(issue['statut'], 'done')
        self.job.refresh_from_db()
        self.assertEqual(self.job.statut, 'done')

    def test_le_balayage_a_la_meme_borne(self):
        from unittest import mock

        from apps.calepinage import tasks

        with mock.patch('apps.calepinage.services.balayage.balayer',
                        side_effect=_ProcessusTue) as calcul:
            for _ in range(2):
                with self.assertRaises(_ProcessusTue):
                    self._livrer(tasks.balayer_calepinage, corps={})
            issue = self._livrer(tasks.balayer_calepinage, corps={})
        self.assertEqual(calcul.call_count, 2)
        self.assertEqual(issue['statut'], 'failed')


class SimulationAutomatiqueTest(TestCase):
    """ACAL1987 (D-ACAL-90 renversée) — la simulation PART SEULE à
    l'enregistrement d'une pose complète : UN job, jamais deux, jamais de
    boucle, rien pour une pose incomplète (le manque est dit)."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        from authentication.models import Company

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead

        self.societe = Company.objects.create(nom='ACAL1987', slug='acal1987')
        self.user = get_user_model().objects.create_user(
            username='acal1987', password='x', company=self.societe)
        lead = Lead.objects.create(company=self.societe, nom='Toiture 1987')
        self.calepinage = Calepinage.objects.create(
            company=self.societe, lead_id=lead.pk, titre='Pose 1987')

    def _enregistrer(self, layout, *, user='auteur'):
        """``enregistrer_layout`` sous matériel et réglages du cas, les
        callbacks de fin de transaction JOUÉS, la tâche Celery interceptée."""
        import copy
        from unittest import mock

        from apps.calepinage import tasks
        from apps.calepinage.services.layout import enregistrer_layout

        from .acal_livrables_helpers import patch_materiel

        auteur = self.user if user == 'auteur' else user
        with patch_materiel(), mock.patch.object(
                tasks.simuler_calepinage, 'delay') as depart:
            with self.captureOnCommitCallbacks(execute=True):
                enregistrer_layout(self.calepinage, copy.deepcopy(layout),
                                   user=auteur)
        return depart

    def _jobs(self):
        from core.models import BackgroundJob

        return BackgroundJob.objects.filter(company=self.societe,
                                            kind='calepinage')

    def test_enregistrer_une_pose_neuve_cree_un_job_de_simulation(self):
        depart = self._enregistrer(LAYOUT)
        self.assertEqual(self._jobs().count(), 1)
        depart.assert_called_once()
        corps = depart.call_args.kwargs
        self.assertEqual(corps['calepinage_id'], self.calepinage.pk)
        self.assertEqual(corps['nature'], 'simulation')
        self.assertFalse(corps['forcer'])
        self.assertEqual(self._jobs().get().user_id, self.user.pk)

    def test_reenregistrer_sans_geste_n_en_cree_pas(self):
        self._enregistrer(LAYOUT)
        depart = self._enregistrer(LAYOUT)
        depart.assert_not_called()
        self.assertEqual(self._jobs().count(), 1)

    def test_une_pose_modifiee_relance_une_simulation(self):
        import copy

        from core.models import BackgroundJob

        self._enregistrer(LAYOUT)
        # ACAL2033 — un job EN COURS ne compte pas comme « en attente » : la
        # pose modifiée en lance un nouveau.
        self._jobs().update(statut=BackgroundJob.STATUT_RUNNING)
        autre = copy.deepcopy(LAYOUT)
        autre['zones'][0]['geometry']['count'] += 2
        depart = self._enregistrer(autre)
        depart.assert_called_once()
        self.assertEqual(self._jobs().count(), 2)

    def test_une_rafale_d_enregistrements_differents_ne_laisse_qu_un_job_en_file(
            self):
        import copy

        from apps.calepinage.services.simulation_auto import (
            simulation_automatique_en_cours)

        for rang in range(10):
            pose = copy.deepcopy(LAYOUT)
            pose['zones'][0]['geometry']['count'] += rang
            depart = self._enregistrer(pose)
            if rang:
                depart.assert_not_called()
        self.assertEqual(self._jobs().count(), 1)
        job = self._jobs().get()
        self.calepinage.refresh_from_db()
        self.assertEqual(simulation_automatique_en_cours(self.calepinage),
                         job.pk)
        # Le marqueur porte la DERNIERE empreinte (le job relit le document).
        from core import cache as cache_tenant

        from apps.calepinage.services.simulation import construire_contexte

        from .acal_livrables_helpers import patch_materiel

        marqueur = cache_tenant.get(
            self.societe.pk,
            'calepinage:simulation_auto:%s' % self.calepinage.pk)
        with patch_materiel():
            _contexte, meta = construire_contexte(self.calepinage)
        self.assertEqual(marqueur['hash_entree'], meta['hash_entree'])
        self.assertEqual(marqueur['job_id'], job.pk)

    def test_le_meme_etat_demande_deux_fois_ne_se_double_pas(self):
        from unittest import mock

        from apps.calepinage import tasks
        from apps.calepinage.services.simulation_auto import (
            ETAT_EN_FILE, lancer_simulation_automatique)

        from .acal_livrables_helpers import patch_materiel

        self._enregistrer(LAYOUT)
        self.assertEqual(self._jobs().count(), 1)
        with patch_materiel(), mock.patch.object(
                tasks.simuler_calepinage, 'delay'):
            self.calepinage.refresh_from_db()
            rendu = lancer_simulation_automatique(self.calepinage,
                                                  user=self.user)
        self.assertEqual(rendu['etat'], ETAT_EN_FILE)
        self.assertEqual(self._jobs().count(), 1)

    def test_une_pose_incomplete_ne_cree_rien_et_dit_ce_qui_manque(self):
        import copy
        from unittest import mock

        from apps.calepinage import tasks
        from apps.calepinage.services.simulation_auto import (
            ETAT_INCOMPLETE, lancer_simulation_automatique)

        from .acal_livrables_helpers import patch_materiel

        vide = copy.deepcopy(LAYOUT)
        vide['zones'][0]['geometry']['count'] = 0
        depart = self._enregistrer(vide)
        depart.assert_not_called()
        self.assertEqual(self._jobs().count(), 0)
        with patch_materiel(), mock.patch.object(
                tasks.simuler_calepinage, 'delay'):
            self.calepinage.refresh_from_db()
            rendu = lancer_simulation_automatique(self.calepinage,
                                                  user=self.user)
        self.assertEqual(rendu['etat'], ETAT_INCOMPLETE)
        self.assertIn('plans', [m['champ'] for m in rendu['manquants']])
        self.assertTrue(all(m['motif'] for m in rendu['manquants']))

    def test_sans_module_ni_onduleur_designes_rien_ne_part(self):
        from unittest import mock

        from apps.calepinage import tasks
        from apps.calepinage.services.simulation_auto import (
            ETAT_INCOMPLETE, lancer_simulation_automatique)

        from .acal_livrables_helpers import patch_materiel

        sans_materiel = dict(MATERIEL, module={}, onduleur={})
        with patch_materiel() as materiel, mock.patch.object(
                tasks.simuler_calepinage, 'delay') as depart:
            materiel.return_value = sans_materiel
            self.calepinage.roof_layout = LAYOUT
            self.calepinage.save()
            rendu = lancer_simulation_automatique(self.calepinage,
                                                  user=self.user)
        self.assertEqual(rendu['etat'], ETAT_INCOMPLETE)
        champs = [m['champ'] for m in rendu['manquants']]
        self.assertIn('materiel.module', champs)
        self.assertIn('materiel.onduleur', champs)
        depart.assert_not_called()

    def test_sans_auteur_rien_ne_part(self):
        depart = self._enregistrer(LAYOUT, user=None)
        depart.assert_not_called()
        self.assertEqual(self._jobs().count(), 0)

    def test_un_calepinage_fige_n_est_jamais_resimule(self):
        from unittest import mock

        with mock.patch('apps.calepinage.services.verrou.est_verrouille',
                        return_value=True):
            depart = self._enregistrer(LAYOUT)
        depart.assert_not_called()
        self.assertEqual(self._jobs().count(), 0)

    def test_une_simulation_a_jour_n_est_pas_relancee(self):
        from unittest import mock

        from apps.calepinage import tasks
        from apps.calepinage.services.simulation import simuler_calepinage
        from apps.calepinage.services.simulation_auto import (
            ETAT_A_JOUR, lancer_simulation_automatique)

        from .acal_livrables_helpers import patch_materiel

        self.calepinage.roof_layout = LAYOUT
        self.calepinage.save()
        with patch_materiel(), mock.patch.object(
                tasks.simuler_calepinage, 'delay') as depart:
            simuler_calepinage(self.calepinage, client=_ClientRejoue(),
                               materiel=MATERIEL, enregistrer=True)
            self.calepinage.refresh_from_db()
            rendu = lancer_simulation_automatique(self.calepinage,
                                                  user=self.user)
        self.assertEqual(rendu['etat'], ETAT_A_JOUR)
        depart.assert_not_called()

    def test_ecrire_le_resultat_ne_relance_jamais_de_simulation(self):
        """Pas de boucle : la simulation écrit ``resultat`` sans repasser par
        ``enregistrer_layout`` ni par la mise en file."""
        from unittest import mock

        from apps.calepinage.services.simulation import simuler_calepinage

        from .acal_livrables_helpers import patch_materiel

        self.calepinage.roof_layout = LAYOUT
        self.calepinage.save()
        with patch_materiel(), \
                mock.patch('core.jobs.submit') as mise_en_file, \
                mock.patch('apps.calepinage.services.layout.'
                           'enregistrer_layout') as ecriture:
            with self.captureOnCommitCallbacks(execute=True):
                simuler_calepinage(self.calepinage, client=_ClientRejoue(),
                                   materiel=MATERIEL, enregistrer=True)
        mise_en_file.assert_not_called()
        ecriture.assert_not_called()
        self.calepinage.refresh_from_db()
        self.assertIn('production', self.calepinage.resultat)

    def test_la_simulation_en_cours_se_lit_par_le_selecteur(self):
        from apps.calepinage.selectors import simulation_automatique_en_cours

        self.assertIsNone(simulation_automatique_en_cours(self.calepinage))
        self._enregistrer(LAYOUT)
        self.assertEqual(simulation_automatique_en_cours(self.calepinage),
                         self._jobs().get().pk)

    def test_la_simulation_automatique_est_la_tache_du_bouton(self):
        """Même kind, même tâche, même borne de livraisons que « Simuler »."""
        from apps.calepinage import tasks

        self._enregistrer(LAYOUT)
        self.assertEqual(self._jobs().get().kind, tasks.KIND_CALEPINAGE)
        self.assertEqual(tasks.LIVRAISONS_MAX, 2)

    def test_designer_le_materiel_electrique_lance_la_simulation(self):
        """Désigner le matériel (``POST entree-electrique/``) est le dernier
        geste d'une pose complète : il met la simulation en file, seul."""
        from unittest import mock

        from apps.calepinage import tasks
        from apps.calepinage.services.electrique import enregistrer_entree

        from .acal_livrables_helpers import patch_materiel

        self.calepinage.roof_layout = LAYOUT
        self.calepinage.save()
        self.assertEqual(self._jobs().count(), 0)
        with patch_materiel(), mock.patch.object(
                tasks.simuler_calepinage, 'delay') as depart:
            with self.captureOnCommitCallbacks(execute=True):
                enregistrer_entree(self.calepinage, {'dc_m': 42.0},
                                   user=self.user)
        depart.assert_called_once()
        self.assertEqual(self._jobs().count(), 1)

    def _etat_servi(self):
        """``simulation_automatique`` lu par la VRAIE porte ``GET resultat/``."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.roles.models import Role
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS

        from .acal_livrables_helpers import patch_materiel

        self.user.role, _cree = Role.objects.get_or_create(
            company=self.societe, nom='Directeur',
            defaults={'permissions': list(DIRECTEUR_PERMISSIONS)})
        self.user.save()
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        with patch_materiel():
            reponse = api.get('/api/django/calepinage/calepinages/'
                              f'{self.calepinage.pk}/resultat/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.data['simulation_automatique']

    def test_get_resultat_dit_simulation_en_cours(self):
        echantillon = json.loads(
            (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
             / 'calepinage_resultat.json').read_text(encoding='utf-8'))
        self._enregistrer(LAYOUT)
        etat = self._etat_servi()
        self.assertEqual(sorted(etat), sorted(
            echantillon['acal1987_simulation_automatique']))
        self.assertTrue(etat['en_cours'])
        self.assertEqual(etat['job_id'], self._jobs().get().pk)
        self.assertEqual(etat['manquants'], [])

    def test_get_resultat_dit_ce_qui_manque_tant_que_la_pose_n_a_pas_bouge(
            self):
        import copy

        vide = copy.deepcopy(LAYOUT)
        vide['zones'][0]['geometry']['count'] = 0
        self._enregistrer(vide)
        etat = self._etat_servi()
        self.assertFalse(etat['en_cours'])
        self.assertIn('plans', [m['champ'] for m in etat['manquants']])
        self.assertTrue(all(m['motif'] for m in etat['manquants']))
        # La pose a changé depuis (sans passer par l'enregistrement) : la liste
        # ne décrit plus ce dossier, elle n'est plus servie.
        self.calepinage.roof_layout = LAYOUT
        self.calepinage.save()
        self.assertEqual(self._etat_servi()['manquants'], [])


class PosePourMoteurTest(TestCase):
    """ACAL2018 — la façade de la pose pour le moteur unique : pose complète ⇒ production de
    LA simulation (détail au même ``hash_entree``) ; incomplète ⇒ manque nommé, aucune
    simulation ; ajustée à la main ⇒ ``a_la_main``. Une autre société n'y lit rien."""

    def setUp(self):
        from authentication.models import Company

        from apps.calepinage.models import Calepinage

        from apps.crm.models import Lead

        self.societe = Company.objects.create(nom='ACAL2018', slug='acal2018')
        lead = Lead.objects.create(company=self.societe, nom='Toiture 2018')
        self.calepinage = Calepinage.objects.create(company=self.societe, lead_id=lead.pk, titre='Pose 2018',
                                                    roof_layout=LAYOUT, layout_hash='e' * 64)

    def _poser(self, **zone):
        import copy

        layout = copy.deepcopy(LAYOUT)
        layout['zones'][0].update(zone)
        self.calepinage.roof_layout = layout
        self.calepinage.save()

    def test_pose_complete_production_de_la_simulation(self):
        from apps.calepinage.services.pose_pour_moteur import pose_servie, simuler_pose

        from .acal_livrables_helpers import patch_materiel

        with patch_materiel():
            pose = pose_servie(self.societe, self.calepinage.pk)
            sortie = simuler_pose(self.calepinage, materiel={'module': 1, 'onduleur': 2}, client=_ClientRejoue())
        self.assertEqual((pose['nb_panneaux'], pose['complete'], pose['a_la_main'], pose['empreinte_pose']),
                         (12, True, False, 'e' * 64))
        self.calepinage.refresh_from_db()
        production = self.calepinage.resultat['production']
        self.assertEqual((sortie['complete'], sortie['production_annuelle'], sortie['hash_entree']),
                         (True, production['total']['p50_kwh'],
                          self.calepinage.resultat[service.CLE_SIMULATION]['hash_entree']))
        self.assertEqual(sortie['production_mensuelle'], [m['p50_kwh'] for m in production['mensuel']])

    def test_pose_incomplete_manque_nomme_aucune_simulation(self):
        from apps.calepinage.services import pose_pour_moteur

        from .acal_livrables_helpers import patch_materiel

        self._poser(geometry=dict(LAYOUT['zones'][0]['geometry'], count=0))
        with patch_materiel(), mock.patch.object(service, 'simuler_calepinage') as simulation:
            pose = pose_pour_moteur.pose_servie(self.societe, self.calepinage.pk)
            sortie = pose_pour_moteur.simuler_pose(self.calepinage, materiel={'module': 1})
        simulation.assert_not_called()  # mutant « simuler une pose incomplète » : rouge
        self.assertFalse(pose['complete'])
        self.assertEqual(sortie['complete'], False)
        self.assertIn('plans', [m['champ'] for m in sortie['manquants']])

    def test_pose_ajustee_a_la_main_et_autre_societe(self):
        from authentication.models import Company

        from apps.calepinage.services.pose_pour_moteur import pose_servie

        from .acal_livrables_helpers import patch_materiel

        self._poser(neededPanels=10)
        with patch_materiel():
            self.assertIs(pose_servie(self.societe, self.calepinage.pk)['a_la_main'], True)
            self._poser(neededPanels=12)
            self.assertIs(pose_servie(self.societe, self.calepinage.pk)['a_la_main'], False)
        autre = Company.objects.create(nom='Autre 2018', slug='autre-2018')
        self.assertIsNone(pose_servie(autre, self.calepinage.pk))
