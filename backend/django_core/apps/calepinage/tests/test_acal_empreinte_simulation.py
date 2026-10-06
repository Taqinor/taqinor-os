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
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.calepinage.services import simulation as service
from apps.calepinage.services.electrique import (
    enregistrer_fournisseur_temperatures, resultat_calepinage,
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


class EmpreinteSimulationTest(SimpleTestCase):

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
