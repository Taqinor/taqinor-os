"""ACAL48 — UNE empreinte de simulation, jugée partout (D-ACAL-21).

Constat C-ACAL-073 / C-ACAL-068 : la fraîcheur de la simulation était jugée
sur ``empreinte_entree`` — l'empreinte d'AFFECTATION (pans, fiches réduites,
températures, options du noyau). Saisir une IAM de 3 %, dessiner un horizon,
changer la salissure société ou la stratégie de batterie laissait la
simulation « fraîche » : le rapport d'étude, la présentation et l'API publique
diffusaient un P50 calculé sur d'autres entrées.

Désormais ``services/simulation.py::empreinte_simulation`` = empreinte
« document » (hors volatils) + entrées hors ``roof_layout`` +
``VERSION_SIMULATION`` ; elle est LA seule comparée — par la simulation
(court-circuit « déjà calculé »), par la vue ``simuler/`` et par
``GET resultat/``.

La chaîne est RÉELLE : le calepinage est simulé par ``simuler_calepinage``
(météo REJOUÉE par le client double de CALX5, matériel et réglages injectés
par les seams documentés), le résultat est relu par ``resultat_calepinage``.
Aucun mock de la source sous test.

Run :
    python manage.py test apps.calepinage.tests.test_acal_empreinte_simulation -v2
"""
import copy
import datetime
import gc
import json
import os
import pathlib
import sys
import urllib.parse
from unittest import mock

from django.test import SimpleTestCase, TestCase, tag

from apps.calepinage.services import simulation as service
from apps.calepinage.services.electrique import (
    enregistrer_fournisseur_temperatures, resultat_calepinage,
)
from apps.calepinage.services.pvgis_serie import (
    CACHE_LIGNES_MAX, ClientPvgis, _Cache,
)
from apps.calepinage.services.simulation import (
    VERSION_SIMULATION, empreinte_simulation, simuler_calepinage,
)

from .test_calx5_simulation import (
    LAYOUT, MATERIEL, REGLAGES, _Calepinage, _ClientRejoue,
)


def _simuler(calepinage, *, materiel=None, reglages=None, forcer=False):
    return simuler_calepinage(
        calepinage, client=_ClientRejoue(), materiel=materiel or MATERIEL,
        reglages=reglages or REGLAGES, enregistrer=True, forcer=forcer)


def _servi(calepinage, *, materiel=None, reglages=None):
    return resultat_calepinage(calepinage, materiel=materiel or MATERIEL,
                               reglages=reglages or REGLAGES)


def _pivot_simule():
    """Un calepinage SIMULÉ par la vraie chaîne (rien en base : ``pk`` None)."""
    pivot = _Calepinage(layout=copy.deepcopy(LAYOUT))
    _simuler(pivot)
    return pivot


def _entree(pivot, **saisie):
    """Pose une saisie dans l'entrée électrique STOCKÉE du pivot."""
    resultat = dict(pivot.resultat or {})
    entree = dict(resultat.get('entree_electrique') or {})
    entree.update(saisie)
    resultat['entree_electrique'] = entree
    pivot.resultat = resultat


def _document(pivot, modifier):
    layout = copy.deepcopy(pivot.roof_layout)
    modifier(layout)
    pivot.roof_layout = layout


def _reglage_simulation(cle, valeur):
    reglages = copy.deepcopy(REGLAGES)
    reglages['simulation'][cle] = {'valeur': valeur, 'source': 'societe',
                                   'reference': 'essai ACAL48'}
    return reglages


MATERIEL_TEMP = copy.deepcopy(MATERIEL)
MATERIEL_TEMP['module']['temp_coeff_pmax_pct_c'] = -0.29
MATERIEL_RENDEMENT = copy.deepcopy(MATERIEL)
MATERIEL_RENDEMENT['onduleur']['rendement_euro_pct'] = 97.1

HORIZON = {'source': 'saisie',
           'points': [{'azimuthDeg': 90, 'heightDeg': 8.0},
                      {'azimuthDeg': 270, 'heightDeg': 12.5}]}

#: UNE mutation par famille d'entrées (D-ACAL-21) : ``(nom, geste,
#: materiel, reglages)``. Le geste modifie le pivot EN PLACE.
MUTATIONS = (
    ('pertes saisies (IAM 3 %)',
     lambda p: setattr(p, 'pertes', [{'poste': 'iam', 'pct': 3.0,
                                      'source': 'saisie'}]), None, None),
    ('horizon dessiné',
     lambda p: _document(p, lambda d: d.update(horizonProfile=HORIZON)),
     None, None),
    ('ombrage 12x24',
     lambda p: _document(p, lambda d: d.update(
         shading12x24=[[0.0] * 24 for _ in range(12)])), None, None),
    ('hauteur d obstacle',
     lambda p: _document(p, lambda d: d['zones'][0].update(
         obstacles=[{'id': 'o1', 'heightM': 1.2}])), None, None),
    ('consommation',
     lambda p: _document(p, lambda d: d.update(
         consumption={'annuel_kwh': 9000})), None, None),
    ('stratégie batterie du document',
     lambda p: _document(p, lambda d: d.update(
         battery={'strategie': 'autoconsommation'})), None, None),
    ('épingle',
     lambda p: _document(p, lambda d: d.update(
         pin={'lat': 33.6, 'lng': -7.6})), None, None),
    ('cheminement',
     lambda p: _entree(p, cheminement='chemin de câbles'), None, None),
    ('affectation manuelle',
     lambda p: _entree(p, affectation_manuelle=[]), None, None),
    ('optimiseur désigné',
     lambda p: _entree(p, optimiseur_produit=9), None, None),
    ('polystring',
     lambda p: _entree(p, polystring=[]), None, None),
    ('raccordement',
     lambda p: p.resultat.update(raccordement_saisie={'cos_phi': 0.95}),
     None, None),
    ('températures saisies',
     lambda p: _entree(p, temperature_min_c=-5.0, temperature_max_c=45.0),
     None, None),
    ('batterie déclarée',
     lambda p: _entree(p, batterie={'strategie': 'autoconsommation'}),
     None, None),
    ('coefficient de température du module',
     lambda p: None, MATERIEL_TEMP, None),
    ('rendement européen de l onduleur',
     lambda p: None, MATERIEL_RENDEMENT, None),
    ('salissure mensuelle société',
     lambda p: None, None,
     _reglage_simulation('salissure_mensuelle_pct', [2.0] * 12)),
)


def _tmy_rejoue(lat, lon):
    """CI #956 (r13) — le fournisseur TMY REJOUÉ (année type PVGIS-SARAH3 de
    Casablanca, relevée le 12/10/2026). Sans lui, ``apps.py`` branche le
    fournisseur RÉEL et chaque ``resultat_calepinage`` du pivot interroge
    PVGIS en direct : un premier appel en échec (repli froid du noyau) suivi
    d'un second servi (4,18 °C) rendait deux lectures SANS GESTE différentes
    (shard 4). La chaîne reste réelle : c'est la seam documentée de CAL136,
    comme la météo rejouée par ``_ClientRejoue``."""
    return {'temperature_min_c': 4.18, 'temperature_max_c': 41.34,
            'base': 'PVGIS-SARAH3', 'fenetre_annees': '2005-2023'}


class EmpreinteSimulationTest(SimpleTestCase):

    def setUp(self):
        precedent = enregistrer_fournisseur_temperatures(_tmy_rejoue)
        self.addCleanup(enregistrer_fournisseur_temperatures, precedent)

    def test_chaque_entree_perime_la_simulation(self):
        for nom, geste, materiel, reglages in MUTATIONS:
            with self.subTest(famille=nom):
                pivot = _pivot_simule()
                avant = pivot.resultat['simulation']['hash_entree']
                geste(pivot)

                servi = _servi(pivot, materiel=materiel, reglages=reglages)

                self.assertTrue(servi['simulation_perimee'], nom)
                self.assertIsNone(servi['production'])
                self.assertTrue(servi['motif'])
                self.assertNotEqual(servi['hash_entree'], avant)
                rendu = _simuler(pivot, materiel=materiel, reglages=reglages)
                self.assertFalse(rendu['deja_calcule'], nom)

    def test_document_inchange_reste_frais(self):
        pivot = _pivot_simule()
        pivot.roof_layout = copy.deepcopy(pivot.roof_layout)

        servi = _servi(pivot)

        self.assertFalse(servi['simulation_perimee'])
        self.assertTrue(servi['simule'])
        self.assertTrue(_simuler(pivot)['deja_calcule'])

    def test_aller_retour_sans_geste_identique(self):
        pivot = _pivot_simule()

        premier = _servi(pivot)
        second = _servi(pivot)

        self.assertEqual(premier, second)
        self.assertEqual(premier['hash_entree'],
                         pivot.resultat['simulation']['hash_entree'])

    def test_champ_volatil_ne_perime_pas(self):
        pivot = _pivot_simule()
        _document(pivot, lambda d: d.update(
            activeAreaId='a', scene={'sunDay': 172, 'sunHour': 12}))
        # Les deux horodatages volatils nommés par D-ACAL-21.
        pivot_2 = _Calepinage(layout=dict(
            copy.deepcopy(LAYOUT),
            consumption={'annuel_kwh': 9000,
                         'source': {'saisi_le': '2026-10-01T10:00:00Z'}}))
        pivot_2.roof_layout['zones'][0]['geometry']['solarAccess'] = {
            'values': [1.0] * 12, 'computedAt': '2026-10-01T10:00:00Z'}
        _simuler(pivot_2)
        _document(pivot_2, lambda d: (
            d['consumption']['source'].update(
                saisi_le='2026-10-06T08:00:00Z'),
            d['zones'][0]['geometry']['solarAccess'].update(
                computedAt='2026-10-06T08:00:00Z')))

        for cas in (pivot, pivot_2):
            servi = _servi(cas)
            self.assertFalse(servi['simulation_perimee'])
            self.assertTrue(_simuler(cas)['deja_calcule'])

    def test_plafonds_de_numerotation_ne_perime_pas(self):
        """Numérotation stable (suite ACAL1720) — `plafondsNumerotation` (le
        plus haut numéro jamais attribué par pan) est une tenue de compte : la
        simulation reste fraîche et n'est pas relancée."""
        pivot = _pivot_simule()
        _document(pivot, lambda d: d.update(plafondsNumerotation={'z1': 99}))

        servi = _servi(pivot)

        self.assertFalse(servi['simulation_perimee'])
        self.assertTrue(_simuler(pivot)['deja_calcule'])

    def test_panne_tmy_ne_perime_pas(self):
        def tmy_disponible(lat, lon):
            return {'temp_min_c': 2.0, 'temp_max_c': 38.0,
                    'base': 'PVGIS-ERA5'}

        def tmy_en_panne(lat, lon):
            raise OSError('PVGIS TMY indisponible')

        precedent = enregistrer_fournisseur_temperatures(tmy_disponible)
        try:
            pivot = _pivot_simule()
            enregistrer_fournisseur_temperatures(tmy_en_panne)
            servi = _servi(pivot)
        finally:
            enregistrer_fournisseur_temperatures(precedent)

        self.assertFalse(servi['simulation_perimee'])
        self.assertTrue(servi['simule'])

    def test_version_simulation_perime(self):
        pivot = _pivot_simule()

        with mock.patch.object(service, 'VERSION_SIMULATION',
                               VERSION_SIMULATION + '-essai'):
            servi = _servi(pivot)
            rendu = _simuler(pivot)

        self.assertTrue(servi['simulation_perimee'])
        self.assertFalse(rendu['deja_calcule'])

    def test_reglages_utilises_figes_dans_le_resultat(self):
        reglages = _reglage_simulation('salissure_mensuelle_pct', [1.5] * 12)
        pivot = _Calepinage(layout=copy.deepcopy(LAYOUT))
        _simuler(pivot, reglages=reglages)

        entete = pivot.resultat['simulation']
        self.assertEqual(entete['version_simulation'], VERSION_SIMULATION)
        self.assertEqual(
            entete['reglages_utilises']['salissure_mensuelle_pct'],
            {'valeur': [1.5] * 12, 'source': 'societe',
             'reference': 'essai ACAL48'})
        self.assertEqual(entete['reglages_utilises']['mode_meteo']['valeur'],
                         'pluriannuel')
        # Servi tel quel par GET resultat/, même une fois périmé.
        servi = _servi(pivot, reglages=REGLAGES)
        self.assertTrue(servi['simulation_perimee'])
        self.assertEqual(servi['simulation']['reglages_utilises'],
                         entete['reglages_utilises'])
        self.assertEqual(servi['simulation']['version_simulation'],
                         VERSION_SIMULATION)

    def test_l_empreinte_prend_le_document_en_parametre(self):
        # D-ACAL-17 : la même fonction sert une variante (son document).
        pivot = _Calepinage(layout=copy.deepcopy(LAYOUT))
        autre = copy.deepcopy(LAYOUT)
        autre['zones'][0]['geometry']['count'] = 10
        commun = dict(donnees={}, materiel=MATERIEL, reglages=REGLAGES)

        self.assertNotEqual(
            empreinte_simulation(pivot, document=LAYOUT, **commun),
            empreinte_simulation(pivot, document=autre, **commun))
        self.assertEqual(
            empreinte_simulation(pivot, document=LAYOUT, **commun),
            empreinte_simulation(pivot, document=copy.deepcopy(LAYOUT),
                                 **commun))


class SimulerApresModificationApiTest(TestCase):
    """``POST simuler/`` sans ``forcer`` : 200 inchangé, 202 après un geste."""

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.roles.models import Role
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
        from authentication.models import Company
        from django.contrib.auth import get_user_model

        societe = Company.objects.create(nom='ACAL48', slug='acal48')
        role = Role.objects.create(company=societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = get_user_model().objects.create_user(
            username='acal48', password='x', company=societe, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        lead = Lead.objects.create(company=societe, nom='Toiture 48')
        self.calepinage = Calepinage.objects.create(
            company=societe, lead_id=lead.pk, titre='Simulation 48',
            roof_layout=copy.deepcopy(LAYOUT))
        self.url = (f'/api/django/calepinage/calepinages/'
                    f'{self.calepinage.pk}/simuler/')

    def _poser_simulation_fraiche(self):
        from apps.calepinage.services.simulation import construire_contexte

        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=MATERIEL), \
                mock.patch(
                    'apps.calepinage.services.electrique.parametres_societe',
                    return_value=REGLAGES):
            _contexte, meta = construire_contexte(self.calepinage)
        self.calepinage.resultat = {'simulation': {
            'hash_entree': meta['hash_entree'],
            'calcule_le': '2026-10-06T08:00:00Z'}}
        self.calepinage.save(update_fields=['resultat'])

    def _poster(self):
        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=MATERIEL), \
                mock.patch(
                    'apps.calepinage.services.electrique.parametres_societe',
                    return_value=REGLAGES), \
                mock.patch('core.jobs.submit') as soumettre:
            # La file de travaux est hors sujet (et lancerait PVGIS) : seul
            # le VERDICT de fraîcheur de la porte est sous test.
            soumettre.return_value = mock.Mock(
                pk=1, statut='pending', kind='calepinage', progress_pct=0,
                message_erreur='')
            return self.api.post(self.url, {}, format='json')

    def _hash(self):
        from apps.calepinage.services.simulation import construire_contexte

        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=MATERIEL), \
                mock.patch(
                    'apps.calepinage.services.electrique.parametres_societe',
                    return_value=REGLAGES):
            return construire_contexte(self.calepinage)[1]['hash_entree']

    def test_batterie_designee_puis_retiree_rend_l_empreinte_d_avant(self):
        """D-ACAL-157 — « Retirer la batterie » envoie `batterie: null` : l'entrée retrouve l'état « jamais désignée »
        (une clé à None n'entre pas dans l'empreinte), alors qu'un objet `{produit: None}` la ferait différer."""
        from apps.calepinage.services.electrique import entree_stockee

        avant = self._hash()
        self.calepinage.resultat = {'entree_electrique': {'batterie': {'produit': 5, 'packs': 1}}}
        designee = self._hash()
        self.assertNotEqual(designee, avant)
        self.calepinage.resultat = {'entree_electrique': {'batterie': {'produit': None, 'packs': 1}}}
        self.assertNotEqual(self._hash(), avant)  # l'ancien « Aucune » : un objet non nul, empreinte différente
        self.calepinage.resultat = {'entree_electrique': {'batterie': None}}
        self.assertIsNone(entree_stockee(self.calepinage)['batterie'])
        self.assertEqual(self._hash(), avant)

    def test_simuler_sans_forcer_recalcule_apres_modification(self):
        self._poser_simulation_fraiche()

        inchange = self._poster()
        self.assertEqual(inchange.status_code, 200, inchange.content[:300])
        self.assertTrue(inchange.data['deja_calcule'])

        # Le geste : une IAM de 3 % saisie dans les pertes du calepinage.
        self.calepinage.pertes = [{'poste': 'iam', 'pct': 3.0,
                                   'source': 'saisie'}]
        self.calepinage.save(update_fields=['pertes'])

        relance = self._poster()
        self.assertEqual(relance.status_code, 202, relance.content[:300])


# ── ACAL2044 — vingt simulations dans UN processus ─────────────────────────

#: L'année PLEINE 2020 réellement servie par PVGIS (8 784 h), rejouée sur deux
#: années à chaque point : la taille réelle d'une réponse horaire.
SERIE_2020 = (pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'
              / 'seriescalc_casablanca_annee_2020_sud_15.json')
ANNEES_SONDE = (2019, 2020)
#: La série COURTE des tests de la porte : les deux premiers jours de chaque
#: année (2 × 48 lignes par réponse) — assez pour faire évincer le cache.
HEURES_COURTES = 48


def _transport_pluriannuel(heures=None):
    base = json.loads(SERIE_2020.read_text(encoding='utf-8'))
    lignes = [dict(ligne, time=f'{annee}{ligne["time"][4:]}')
              for annee in range(ANNEES_SONDE[0], ANNEES_SONDE[1] + 1)
              for ligne in base['outputs']['hourly'][:heures]
              if annee % 4 == 0 or ligne['time'][4:8] != '0229']

    def transport(url, timeout_s):
        if '/seriescalc?' not in url:
            return 404, ''
        requete = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        charge = copy.deepcopy({k: v for k, v in base.items()
                                if k != 'outputs'})
        charge['inputs']['location'].update(
            latitude=float(requete['lat'][0]),
            longitude=float(requete['lon'][0]))
        charge['outputs'] = {'hourly': lignes}
        return 200, json.dumps(charge)
    return transport


def _octets_residents():
    """La mémoire RÉSIDENTE du processus, en octets (Linux, Windows), ou None."""
    try:
        with open('/proc/self/statm', encoding='ascii') as statm:
            return int(statm.read().split()[1]) * os.sysconf('SC_PAGE_SIZE')
    except (OSError, ValueError, AttributeError):
        pass
    if sys.platform != 'win32':
        return None
    import ctypes
    from ctypes import wintypes

    class _Compteurs(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('fautes', wintypes.DWORD)] + [
            (nom, ctypes.c_size_t) for nom in (
                'pic', 'residente', 'a', 'b', 'c', 'd', 'e', 'f')]

    compteurs = _Compteurs(cb=ctypes.sizeof(_Compteurs))
    noyau, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    noyau.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    psapi.GetProcessMemoryInfo(noyau.GetCurrentProcess(),
                               ctypes.byref(compteurs), compteurs.cb)
    return compteurs.residente


class MemoireVingtSimulationsTest(SimpleTestCase):
    """ACAL2044 — la cause : ``pvgis_serie._Cache`` (le cache PARTAGÉ du
    processus) gardait jusqu'à 200 réponses horaires décodées ; une réponse à
    la fenêtre plafond de 10 ans (87 672 lignes) pèse ~45 Mo et une
    simulation en fait 4. Sonde sur l'hôte le 25/11/2026 (vrai
    ``ClientPvgis``, transport rejoué, 10 ans, vingt plans) : mémoire
    résidente 409 Mo → 3 872 Mo (+182 Mo par simulation, 80 entrées) avant ;
    404 Mo → 670 Mo après (palier dès la 9e, 438 360 lignes, 5 entrées).

    Les tests de la porte sont DÉTERMINISTES (séries courtes, borne comptée en
    lignes) ; la mesure en octets est ``@tag('slow')`` (nocturne)."""

    def setUp(self):
        precedent = enregistrer_fournisseur_temperatures(_tmy_rejoue)
        self.addCleanup(enregistrer_fournisseur_temperatures, precedent)
        self.transport = _transport_pluriannuel(HEURES_COURTES)

    def _simuler(self, rang, cache):
        reglages = _reglage_simulation('fenetre_annees', list(ANNEES_SONDE))
        layout = dict(copy.deepcopy(LAYOUT), pin={
            'lat': 30.0 + rang * 0.37, 'lng': -9.0 + rang * 0.21})
        layout['zones'][0]['geometry'].update(count=10 + rang,
                                              tiltDeg=10.0 + rang)
        client = ClientPvgis(self.transport, cache=cache,
                             dormir=lambda _s: None)
        return simuler_calepinage(
            _Calepinage(layout=layout), client=client, materiel=MATERIEL,
            reglages=reglages, enregistrer=False,
            maintenant=datetime.datetime(2026, 11, 25, 10,
                                         tzinfo=datetime.timezone.utc))['blocs']

    def test_vingt_simulations_le_cache_reste_borne(self):
        """Vingt plans à vingt points dans UN cache partagé : la borne en
        lignes (mise à l'échelle de la série courte : 5 réponses, comme
        ``CACHE_LIGNES_MAX`` = 5 réponses à la fenêtre plafond) évince, le
        cache ne garde jamais plus de 5 réponses (80 sans la borne)."""
        lignes_par_reponse = 2 * HEURES_COURTES
        cache = _Cache(lignes_max=5 * lignes_par_reponse)
        for rang in range(20):
            self._simuler(rang, cache)
            self.assertLessEqual(cache.lignes_gardees(), cache.lignes_max)
            self.assertLessEqual(len(cache._entrees), 5)
        self.assertEqual(cache.lignes_gardees(), 5 * lignes_par_reponse)
        self.assertEqual(CACHE_LIGNES_MAX, 5 * 10 * 8784)

    @tag('slow')
    def test_vingt_simulations_la_memoire_ne_grossit_pas_au_dela_du_plafond(
            self):
        """La mesure en OCTETS (nocturne : bruit d'allocateur et de shard
        hors porte). Série de 2 ans (17 568 lignes par réponse), cache neuf
        partagé par les vingt simulations comme celui du processus, mesuré
        sur l'hôte Windows le 25/11/2026 : +170 Mo de mémoire résidente entre
        la 1re et la 20e avec la borne (palier ≈ ``CACHE_LIGNES_MAX`` lignes ≈
        225 Mo de réponses) ; +659 Mo sans elle (1 403 520 lignes, 80
        entrées). Plafond 300 Mo : la mesure + 130 Mo de marge (allocateur,
        ordre des tests), toujours 2,2 fois sous la croissance non bornée."""
        # Une mesure qui ne peut pas être prise n'est ni un succès ni un saut.
        self.assertIsNotNone(
            _octets_residents(),
            'mémoire résidente illisible sur ce système (ni /proc/self/statm '
            'ni GetProcessMemoryInfo) : la mesure ACAL2044 n\'est pas prise')
        self.transport = _transport_pluriannuel()
        cache = _Cache()
        for rang in range(20):
            self._simuler(rang, cache)
            gc.collect()
            if rang == 0:
                apres_la_premiere = _octets_residents()
        ecart = _octets_residents() - apres_la_premiere
        self.assertLessEqual(cache.lignes_gardees(), CACHE_LIGNES_MAX)
        self.assertLess(ecart, 300 * 10 ** 6,
                        f'+{ecart / 1e6:.0f} Mo en vingt simulations')

    def test_le_cache_partage_par_des_fils_reste_coherent(self):
        """gunicorn ``--threads 4`` : les fils d'un worker partagent le cache.
        Huit fils posent et relisent des clés distinctes sous une petite borne
        (évictions en continu) : aucune exception, et après eux le compte de
        lignes est EXACTEMENT celui des entrées gardées, jamais au-dessus de
        la borne."""
        import threading

        cache = _Cache(lignes_max=50)
        erreurs = []

        def fil(rang):
            try:
                for tour in range(400):
                    lignes = [{}] * (1 + (rang + tour) % 7)
                    cle = f'{rang}-{tour % 25}'
                    cache.poser(cle, {'outputs': {'hourly': lignes}})
                    cache.lire(f'{(rang + 1) % 8}-{tour % 25}')
                    self.assertLessEqual(cache.lignes_gardees(), 50)
            except Exception as erreur:  # noqa: BLE001 — l'erreur EST le constat
                erreurs.append(erreur)

        fils = [threading.Thread(target=fil, args=(rang,)) for rang in range(8)]
        for un_fil in fils:
            un_fil.start()
        for un_fil in fils:
            un_fil.join()
        self.assertEqual(erreurs, [])
        gardees = sum(len(valeur['outputs']['hourly'])
                      for _pose, valeur in cache._entrees.values())
        self.assertEqual(cache.lignes_gardees(), gardees)
        self.assertEqual(set(cache._lignes), set(cache._entrees))
        self.assertLessEqual(gardees, 50)

    def test_la_borne_pese_aussi_les_series_nasa_power(self):
        """Les réponses horaires de NASA POWER (``properties.parameter``)
        passent par le MÊME cache : elles comptent dans la borne."""
        cache = _Cache(lignes_max=10)
        heures = {f'20200101{h:02d}': 1.0 for h in range(6)}
        cache.poser('a', {'properties': {'parameter': {'T2M': heures}}})
        cache.poser('b', {'properties': {'parameter': {'T2M': heures}}})
        cache.poser('c', {'ok': 1})
        self.assertEqual((cache.lire('a'), cache.lignes_gardees()), (None, 6))

    def test_la_borne_ne_change_aucun_resultat(self):
        """Le cache n'est qu'un accélérateur : sous une borne d'UNE ligne
        (chaque réponse évince la précédente), la simulation rend les MÊMES
        blocs que sur un cache neuf à la borne de production — seuls le
        compte d'appels réseau, les drapeaux « servi par le cache » (ce que
        le cache EST) et la durée du calcul peuvent différer."""
        def sans_compteurs(valeur):
            if isinstance(valeur, dict):
                return {cle: sans_compteurs(sous) for cle, sous in valeur.items()
                        if cle not in ('appels_pvgis', 'depuis_cache',
                                       'duree_s')}
            if isinstance(valeur, list):
                return [sans_compteurs(sous) for sous in valeur]
            return valeur

        with mock.patch('apps.calepinage.services.pvgis_serie._maintenant_iso',
                        return_value='2026-11-25T10:00:00Z'):
            neuve = self._simuler(3, _Cache())
            evincee = self._simuler(3, _Cache(lignes_max=1))
        self.assertEqual(
            json.dumps(sans_compteurs(neuve), sort_keys=True, default=str),
            json.dumps(sans_compteurs(evincee), sort_keys=True, default=str))
