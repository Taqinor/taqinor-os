"""PV74 — l'étude bankable d'un devis, lancée en tâche de fond.

L'étude interroge PVGIS PAR PAN de toiture : la faire dans la requête bloque un
slot serveur pendant des secondes et casse au premier hoquet réseau. Elle passe
donc par le MÊME motif asynchrone que les exports de cette app (SCA41) — jeton
opaque, état en cache scopé société, endpoint de statut qui vérifie la société
avant de répondre.

Ce module verrouille :

1. ``POST /simuler/`` répond ``202`` avec un jeton, et le sondage rend ensuite
   la simulation rangée sur le devis ;
2. l'idempotence par le cache PVGIS (PV73) : simuler deux fois le même toit ne
   recoûte AUCUN aller-retour réseau — sauf ``force_refresh`` ;
3. la mise à jour d'``etude_params`` est CHIRURGICALE : ``simulation`` est
   ajoutée, les autres clés d'étude sont intactes, et le STATUT ne bouge pas
   (règle #4) ;
4. le bornage société du job (une autre société ne voit jamais le jeton).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv74_simulation_async -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache as django_cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes import tasks as tasks_mod
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _fake_productible(settings, lat, lon, *, peakpower_kwc=1.0, tilt=None,
                      azimuth=None):
    return {'source': 'pvgis', 'productible_kwh_kwc': 1700.0,
            'production_mensuelle_kwh_kwc': None, 'reason': None}


def _fake_tmy(lat, lon):
    return {'source': 'pvgis', 'irradiance_annuelle_kwh_m2': 2000.0,
            'irradiance_mensuelle_kwh_m2': [120.0] * 12,
            'temperature_moyenne_c': 19.0, 'reason': None}


def pans_geometry(nb=1):
    """``_pans_geometry`` (QJ21) — un pan par orientation, azimut PVGIS."""
    pans = [{'label': 'Pan Sud', 'orientation': 'Sud', 'azimut_deg': 0,
             'inclinaison_deg': 30, 'nb_panneaux': 16, 'kwc': 8.8,
             'roof_type': 'pitched'}]
    if nb > 1:
        pans.append({'label': 'Pan Est', 'orientation': 'Est',
                     'azimut_deg': -90, 'inclinaison_deg': 30,
                     'nb_panneaux': 8, 'kwc': 4.4, 'roof_type': 'pitched'})
    return pans[:nb]


class _Base(TestCase):
    def setUp(self):
        django_cache.clear()
        self.co = Company.objects.create(slug='pv74-co', nom='PV74 Co')
        self.user = User.objects.create_user(
            username='pv74_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = _auth(self.user)
        self.cli = Client.objects.create(
            company=self.co, nom='Etude', prenom='PV74',
            email='pv74@example.invalid')
        self.lead = Lead.objects.create(
            company=self.co, nom='Etude', prenom='PV74',
            email='pv74@example.invalid',
            gps_lat=Decimal('33.5731'), gps_lng=Decimal('-7.5898'))

    def _devis(self, *, pans=1, reference='DEV-PV74-001', etude=None,
               layout=None):
        if layout is None:
            layout = ({'version': 2, '_pans_geometry': pans_geometry(pans)}
                      if pans else {'version': 2})
        devis = Devis.objects.create(
            company=self.co, reference=reference, client=self.cli,
            lead=self.lead, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), remise_globale=Decimal('0'),
            created_by=self.user, roof_layout=layout, etude_params=etude)
        produit = Produit.objects.create(
            company=self.co, nom='Panneau mono 550W',
            sku='PV74-%s' % reference[-3:], prix_vente=Decimal('1100'),
            prix_achat=Decimal('800'), quantite_stock=100)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau mono 550W',
            quantite=Decimal('16'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'))
        return devis

    def _url(self, devis):
        return '/api/django/ventes/devis/%s/simuler/' % devis.pk


class LesZonesViennentDuCalepinage(_Base):
    """Un pan de calepinage = une zone d'étude, au point GPS du lead."""

    def test_chaque_pan_devient_une_zone(self):
        devis = self._devis(pans=2)
        zones = tasks_mod.zones_etude_du_devis(devis)
        self.assertEqual([z['label'] for z in zones], ['Pan Sud', 'Pan Est'])
        self.assertEqual([z['kwc'] for z in zones], [8.8, 4.4])
        # L'azimut est déjà en convention PVGIS des deux côtés : jamais converti.
        self.assertEqual([z['azimuth'] for z in zones], [0.0, -90.0])
        self.assertEqual([z['tilt'] for z in zones], [30.0, 30.0])

    def test_le_point_gps_vient_du_lead(self):
        zones = tasks_mod.zones_etude_du_devis(self._devis())
        self.assertAlmostEqual(zones[0]['lat'], 33.5731, places=4)
        self.assertAlmostEqual(zones[0]['lon'], -7.5898, places=4)

    def test_sans_lead_gps_le_repere_de_l_outil_3d_prend_le_relais(self):
        layout = {'version': 2, '_pans_geometry': pans_geometry(1),
                  'pin': {'lat': 31.63, 'lng': -8.01}}
        devis = self._devis(layout=layout, reference='DEV-PV74-PIN')
        Lead.objects.filter(pk=self.lead.pk).update(gps_lat=None,
                                                    gps_lng=None)
        devis = Devis.objects.get(pk=devis.pk)
        zones = tasks_mod.zones_etude_du_devis(devis)
        self.assertAlmostEqual(zones[0]['lat'], 31.63, places=4)
        self.assertAlmostEqual(zones[0]['lon'], -8.01, places=4)

    def test_sans_calepinage_aucune_zone(self):
        self.assertEqual(
            tasks_mod.zones_etude_du_devis(
                self._devis(pans=0, reference='DEV-PV74-NOGEO')), [])


@mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy',
            side_effect=_fake_tmy)
@mock.patch('apps.parametres.pvgis.fetch_productible',
            side_effect=_fake_productible)
class LeLancementRepond202(_Base):
    def test_202_avec_jeton_et_url_de_suivi(self, _prod, _tmy):
        devis = self._devis(pans=2)
        with mock.patch.object(
                tasks_mod.task_simulate_bankable_study, 'apply_async') as m:
            resp = self.api.post(self._url(devis), {}, format='json')
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data['status'], 'pending')
        self.assertEqual(resp.data['zones'], 2)
        self.assertIn('/simulation-status/', resp.data['status_url'])
        self.assertIn(resp.data['job_id'], resp.data['status_url'])
        m.assert_called_once()
        _, kwargs = m.call_args
        self.assertEqual(kwargs.get('queue'), 'interactive')
        self.assertEqual(kwargs['args'][0], devis.pk)
        self.assertEqual(kwargs['args'][1], self.co.id)
        self.assertFalse(kwargs['kwargs']['force_refresh'])

    def test_force_refresh_traverse_jusqu_a_la_tache(self, _prod, _tmy):
        devis = self._devis()
        with mock.patch.object(
                tasks_mod.task_simulate_bankable_study, 'apply_async') as m:
            resp = self.api.post(self._url(devis), {'force_refresh': True},
                                 format='json')
        self.assertEqual(resp.status_code, 202)
        self.assertTrue(m.call_args[1]['kwargs']['force_refresh'])

    def test_un_devis_sans_calepinage_est_refuse(self, _prod, _tmy):
        devis = self._devis(pans=0, reference='DEV-PV74-NOGEO2')
        with mock.patch.object(
                tasks_mod.task_simulate_bankable_study, 'apply_async') as m:
            resp = self.api.post(self._url(devis), {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('calepinage', resp.data['detail'])
        m.assert_not_called()

    def test_le_lancement_n_ecrit_aucun_statut(self, _prod, _tmy):
        devis = self._devis()
        with mock.patch.object(
                tasks_mod.task_simulate_bankable_study, 'apply_async'):
            self.api.post(self._url(devis), {}, format='json')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)


@mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy',
            side_effect=_fake_tmy)
@mock.patch('apps.parametres.pvgis.fetch_productible',
            side_effect=_fake_productible)
class LeSondageRendLaSimulation(_Base):
    def _lancer(self, devis):
        with mock.patch.object(
                tasks_mod.task_simulate_bankable_study, 'apply_async'):
            resp = self.api.post(self._url(devis), {}, format='json')
        return resp.data['job_id'], resp.data['status_url']

    def test_pending_puis_ready_avec_la_simulation(self, _prod, _tmy):
        devis = self._devis(pans=2)
        token, status_url = self._lancer(devis)

        # Tant que la tâche n'a pas tourné : 202 pending.
        attente = self.api.get(status_url)
        self.assertEqual(attente.status_code, 202)
        self.assertEqual(attente.data['status'], 'pending')

        tasks_mod.task_simulate_bankable_study.run(devis.pk, self.co.id, token)

        pret = self.api.get(status_url)
        self.assertEqual(pret.status_code, 200)
        self.assertEqual(pret.data['status'], 'ready')
        simulation = pret.data['simulation']
        self.assertIsInstance(simulation, dict)
        # Le contrat PACT10 complet, pas un sous-ensemble improvisé.
        for cle in ('version', 'computed_at', 'source', 'zones', 'pr',
                    'self_consumption', 'net_metering', 'subscribed_power',
                    'degradation', 'projection_25y', 'warnings'):
            self.assertIn(cle, simulation)
        self.assertEqual(len(simulation['zones']), 2)

    def test_la_simulation_est_relue_sur_le_devis(self, _prod, _tmy):
        devis = self._devis()
        token, _ = self._lancer(devis)
        tasks_mod.task_simulate_bankable_study.run(devis.pk, self.co.id, token)
        devis.refresh_from_db()
        self.assertIn('simulation', devis.etude_params)
        self.assertEqual(devis.etude_params['simulation']['zones'][0]['label'],
                         'Pan Sud')

    def test_un_jeton_inconnu_est_un_404(self, _prod, _tmy):
        devis = self._devis()
        resp = self.api.get(
            '/api/django/ventes/devis/%s/simulation-status/%s/'
            % (devis.pk, '0' * 32))
        self.assertEqual(resp.status_code, 404)

    def test_une_autre_societe_ne_voit_jamais_le_job(self, _prod, _tmy):
        devis = self._devis()
        token, status_url = self._lancer(devis)
        autre_co = Company.objects.create(slug='pv74-autre', nom='Autre')
        autre = User.objects.create_user(
            username='pv74_autre', password='x', role_legacy='responsable',
            company=autre_co)
        self.assertEqual(_auth(autre).get(status_url).status_code, 404)

    def test_un_jeton_d_un_autre_devis_est_un_404(self, _prod, _tmy):
        """Le jeton est lié à SON devis : il ne s'utilise pas ailleurs."""
        devis = self._devis()
        autre_devis = self._devis(reference='DEV-PV74-002')
        token, _ = self._lancer(devis)
        resp = self.api.get(
            '/api/django/ventes/devis/%s/simulation-status/%s/'
            % (autre_devis.pk, token))
        self.assertEqual(resp.status_code, 404)


@mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy',
            side_effect=_fake_tmy)
@mock.patch('apps.parametres.pvgis.fetch_productible',
            side_effect=_fake_productible)
class LeCachePvgisRendLaSimulationIdempotente(_Base):
    """PV73 — deux simulations du même toit = UN seul aller-retour réseau."""

    def test_une_seconde_simulation_ne_refetch_rien(self, prod, tmy):
        devis = self._devis()
        tasks_mod.task_simulate_bankable_study.run(devis.pk, self.co.id, 't1')
        self.assertEqual(prod.call_count, 1)
        self.assertEqual(tmy.call_count, 1)

        tasks_mod.task_simulate_bankable_study.run(devis.pk, self.co.id, 't2')
        self.assertEqual(prod.call_count, 1)
        self.assertEqual(tmy.call_count, 1)

    def test_force_refresh_refait_les_appels(self, prod, tmy):
        devis = self._devis()
        tasks_mod.task_simulate_bankable_study.run(devis.pk, self.co.id, 't1')
        tasks_mod.task_simulate_bankable_study.run(
            devis.pk, self.co.id, 't2', force_refresh=True)
        self.assertEqual(prod.call_count, 2)
        self.assertEqual(tmy.call_count, 2)


@mock.patch('apps.ventes.weather_feed.fetch_irradiance_tmy',
            side_effect=_fake_tmy)
@mock.patch('apps.parametres.pvgis.fetch_productible',
            side_effect=_fake_productible)
class LaMiseAJourDeLEtudeEstChirurgicale(_Base):
    """Règle #4 — la simulation s'ajoute ; elle n'écrase rien, ni le statut."""

    ETUDE_EXISTANTE = {
        'puissance_kwc': 8.8,
        'production_annuelle': 14000,
        'economies_annuelles': 11000,
        'toiture': {'nb_pans': 2, 'surface_m2': 60.0},
        'taux_autoconsommation': 65,
    }

    def test_les_autres_cles_d_etude_survivent(self, _prod, _tmy):
        devis = self._devis(etude=dict(self.ETUDE_EXISTANTE))
        tasks_mod.task_simulate_bankable_study.run(devis.pk, self.co.id, 'tk')
        devis.refresh_from_db()
        for cle, valeur in self.ETUDE_EXISTANTE.items():
            self.assertEqual(devis.etude_params[cle], valeur,
                             'la clé d\'étude « %s » a été écrasée' % cle)
        self.assertIn('simulation', devis.etude_params)

    def test_aucun_statut_ni_aucune_ligne_ne_bouge(self, _prod, _tmy):
        devis = self._devis(etude=dict(self.ETUDE_EXISTANTE))
        avant = [(li.designation, li.quantite, li.prix_unitaire)
                 for li in devis.lignes.all()]
        tasks_mod.task_simulate_bankable_study.run(devis.pk, self.co.id, 'tk')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual([(li.designation, li.quantite, li.prix_unitaire)
                          for li in devis.lignes.all()], avant)

    def test_une_seconde_simulation_remplace_la_precedente(self, _prod, _tmy):
        devis = self._devis(etude=dict(self.ETUDE_EXISTANTE))
        # Le delta est mesuré sur l'état RÉEL d'avant la tâche, pas sur le
        # dictionnaire de classe : le récepteur QX24 dérive ``payback_annees``
        # à l'écriture de la ligne du montage, bien avant toute simulation.
        # Le comparer au dictionnaire retapé accusait la tâche d'une clé
        # qu'elle n'écrit pas — et masquait la vraie promesse.
        devis.refresh_from_db()
        avant = set(devis.etude_params)
        tasks_mod.task_simulate_bankable_study.run(devis.pk, self.co.id, 'tk')
        tasks_mod.task_simulate_bankable_study.run(devis.pk, self.co.id, 'tk2')
        devis.refresh_from_db()
        # UNE simulation vit sur le devis, jamais un historique implicite qui
        # ferait enfler ``etude_params`` à chaque clic.
        self.assertIsInstance(devis.etude_params['simulation'], dict)
        self.assertEqual(set(devis.etude_params) - avant, {'simulation'})

    def test_un_devis_introuvable_ne_fait_pas_boucler_la_tache(self, _prod,
                                                               _tmy):
        """Devis absent (ou d'une autre société) : ÉCHEC NET, jamais un retry.

        Réessayer trois fois avec un back-off ne fera pas réapparaître un devis
        supprimé — ce serait trois créneaux de worker pour rien.
        """
        from django.core.cache import cache

        introuvable = self._devis().pk + 10_000
        resultat = tasks_mod.task_simulate_bankable_study.run(
            introuvable, self.co.id, 'tk-mort')
        self.assertIsNone(resultat)
        job = cache.get(tasks_mod.simulation_job_cache_key('tk-mort'))
        self.assertEqual(job['status'], 'error')
