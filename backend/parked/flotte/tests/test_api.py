"""Tests du module Gestion de flotte (FLOTTE2 / FLOTTE4).

Couvre : isolation par société (A ne voit/touche pas B), société posée côté
serveur (jamais lue du corps de requête), filtres et recherche, pour les deux
ressources Véhicule et Engin roulant.
"""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.flotte.models import EnginRoulant, ModeleVehicule, Vehicule
from apps.flotte.selectors import emplacement_stock_label, emplacements_stock_labels
from apps.stock.models import EmplacementStock

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


class FlotteVehiculeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('flotte-a', 'Flotte A')
        self.co_b = make_company('flotte-b', 'Flotte B')
        self.admin_a = make_user(self.co_a, 'flotte-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'flotte-admin-b', 'admin')

    # ── FLOTTE2 : véhicules ──
    def test_create_force_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/vehicules/', {
            'immatriculation': '1234-A-56', 'marque': 'Dacia',
            'modele': 'Duster', 'energie': 'diesel', 'kilometrage': 12000,
            'valeur': '180000.00', 'statut': 'actif',
            # Tentative d'injection d'une autre société — doit être ignorée.
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        veh = Vehicule.objects.get(id=resp.data['id'])
        self.assertEqual(veh.company_id, self.co_a.id)

    def test_tenant_isolation_list(self):
        Vehicule.objects.create(company=self.co_a, immatriculation='AAA-1')
        Vehicule.objects.create(company=self.co_b, immatriculation='BBB-1')
        resp = auth(self.admin_a).get('/api/django/flotte/vehicules/')
        immats = [r['immatriculation'] for r in rows(resp)]
        self.assertIn('AAA-1', immats)
        self.assertNotIn('BBB-1', immats)

    def test_cannot_retrieve_other_company_vehicule(self):
        b_veh = Vehicule.objects.create(
            company=self.co_b, immatriculation='BBB-2')
        resp = auth(self.admin_a).get(
            f'/api/django/flotte/vehicules/{b_veh.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_statut_and_energie(self):
        Vehicule.objects.create(
            company=self.co_a, immatriculation='V-ACTIF', statut='actif',
            energie='diesel')
        Vehicule.objects.create(
            company=self.co_a, immatriculation='V-MAINT', statut='maintenance',
            energie='electrique')
        api = auth(self.admin_a)
        r1 = api.get('/api/django/flotte/vehicules/?statut=maintenance')
        self.assertEqual([x['immatriculation'] for x in rows(r1)], ['V-MAINT'])
        r2 = api.get('/api/django/flotte/vehicules/?energie=electrique')
        self.assertEqual([x['immatriculation'] for x in rows(r2)], ['V-MAINT'])

    def test_search_and_display_fields(self):
        Vehicule.objects.create(
            company=self.co_a, immatriculation='X-99', marque='Renault',
            energie='hybride', statut='actif')
        resp = auth(self.admin_a).get(
            '/api/django/flotte/vehicules/?search=Renault')
        row = rows(resp)[0]
        self.assertEqual(row['immatriculation'], 'X-99')
        self.assertEqual(row['energie_display'], 'Hybride')
        self.assertEqual(row['statut_display'], 'Actif')

    def test_aud728_delete_vehicule_en_vie_bloque(self):
        """AUD728 — un véhicule encore EN VIE (statut ``actif``) ne peut pas
        être supprimé via l'API : avant ce correctif, ce DELETE effaçait en
        cascade (via ``ActifFlotte``) tout l'historique métier/légal du
        véhicule sans confirmation renforcée ni trace."""
        veh = Vehicule.objects.create(
            company=self.co_a, immatriculation='V-VIVANT', statut='actif')
        resp = auth(self.admin_a).delete(
            f'/api/django/flotte/vehicules/{veh.id}/')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertTrue(Vehicule.objects.filter(pk=veh.pk).exists())

    def test_aud728_delete_vehicule_reforme_autorise(self):
        """Un véhicule sorti du parc (réformé) reste supprimable."""
        veh = Vehicule.objects.create(
            company=self.co_a, immatriculation='V-REFORME',
            statut=Vehicule.Statut.REFORME)
        resp = auth(self.admin_a).delete(
            f'/api/django/flotte/vehicules/{veh.id}/')
        self.assertEqual(resp.status_code, 204, resp.data)
        self.assertFalse(Vehicule.objects.filter(pk=veh.pk).exists())

    def test_aud728_delete_vehicule_vendu_autorise(self):
        """Un véhicule cédé (vendu) reste supprimable."""
        veh = Vehicule.objects.create(
            company=self.co_a, immatriculation='V-VENDU',
            statut=Vehicule.Statut.VENDU)
        resp = auth(self.admin_a).delete(
            f'/api/django/flotte/vehicules/{veh.id}/')
        self.assertEqual(resp.status_code, 204, resp.data)
        self.assertFalse(Vehicule.objects.filter(pk=veh.pk).exists())


class FlotteEnginRoulantTests(TestCase):
    def setUp(self):
        self.co_a = make_company('flotte-ea', 'Flotte EA')
        self.co_b = make_company('flotte-eb', 'Flotte EB')
        self.admin_a = make_user(self.co_a, 'flotte-eadmin-a', 'admin')

    # ── FLOTTE4 : engins roulants ──
    def test_create_force_company_server_side(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/engins/', {
            'nom': 'Nacelle 12m', 'type_engin': 'nacelle',
            'compteur_heures': '350.5', 'valeur': '90000.00',
            'statut': 'actif',
            'company': self.co_b.id,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        engin = EnginRoulant.objects.get(id=resp.data['id'])
        self.assertEqual(engin.company_id, self.co_a.id)

    def test_tenant_isolation_list(self):
        EnginRoulant.objects.create(company=self.co_a, nom='Groupe A')
        EnginRoulant.objects.create(company=self.co_b, nom='Groupe B')
        resp = auth(self.admin_a).get('/api/django/flotte/engins/')
        noms = [r['nom'] for r in rows(resp)]
        self.assertIn('Groupe A', noms)
        self.assertNotIn('Groupe B', noms)

    def test_cannot_retrieve_other_company_engin(self):
        b_engin = EnginRoulant.objects.create(company=self.co_b, nom='Chariot B')
        resp = auth(self.admin_a).get(
            f'/api/django/flotte/engins/{b_engin.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_filter_by_type_and_display(self):
        EnginRoulant.objects.create(
            company=self.co_a, nom='Nacelle', type_engin='nacelle')
        EnginRoulant.objects.create(
            company=self.co_a, nom='Groupe', type_engin='groupe_electrogene')
        api = auth(self.admin_a)
        resp = api.get('/api/django/flotte/engins/?type_engin=groupe_electrogene')
        immats = rows(resp)
        self.assertEqual([x['nom'] for x in immats], ['Groupe'])
        self.assertEqual(immats[0]['type_engin_display'], 'Groupe électrogène')


class FlotteEmplacementLinkTests(TestCase):
    """FLOTTE3 — lien Vehicule -> stock.EmplacementStock (id via sélecteur)."""

    def setUp(self):
        self.co_a = make_company('flotte-loc-a', 'Flotte Loc A')
        self.co_b = make_company('flotte-loc-b', 'Flotte Loc B')
        self.admin_a = make_user(self.co_a, 'flotte-loc-admin-a', 'admin')
        self.empl_a = EmplacementStock.objects.create(
            company=self.co_a, nom='Dépôt principal', is_principal=True)
        self.empl_b = EmplacementStock.objects.create(
            company=self.co_b, nom='Dépôt B')

    def test_set_link_same_company_persists(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/vehicules/', {
            'immatriculation': 'L-1', 'energie': 'diesel',
            'emplacement_stock_id': self.empl_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        veh = Vehicule.objects.get(id=resp.data['id'])
        self.assertEqual(veh.emplacement_stock_id, self.empl_a.id)
        self.assertEqual(resp.data['emplacement_stock_id'], self.empl_a.id)
        # Le libellé est résolu via le sélecteur de stock.
        self.assertEqual(
            resp.data['emplacement_stock_label'], 'Dépôt principal')

    def test_set_link_other_company_rejected(self):
        """Un emplacement d'une AUTRE société est refusé (validation sélecteur)."""
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/vehicules/', {
            'immatriculation': 'L-2', 'energie': 'diesel',
            'emplacement_stock_id': self.empl_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('emplacement_stock_id', resp.data)
        self.assertFalse(
            Vehicule.objects.filter(immatriculation='L-2').exists())

    def test_set_link_unknown_id_rejected(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/vehicules/', {
            'immatriculation': 'L-3', 'energie': 'diesel',
            'emplacement_stock_id': 999999,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_clear_link_via_patch(self):
        veh = Vehicule.objects.create(
            company=self.co_a, immatriculation='L-4',
            emplacement_stock_id=self.empl_a.id)
        api = auth(self.admin_a)
        resp = api.patch(
            f'/api/django/flotte/vehicules/{veh.id}/',
            {'emplacement_stock_id': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        veh.refresh_from_db()
        self.assertIsNone(veh.emplacement_stock_id)
        self.assertIsNone(resp.data['emplacement_stock_label'])

    def test_create_without_link_is_allowed(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/flotte/vehicules/', {
            'immatriculation': 'L-5', 'energie': 'diesel',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['emplacement_stock_id'])
        self.assertIsNone(resp.data['emplacement_stock_label'])

    def test_selector_label_helper(self):
        """Le sélecteur résout le nom, dégrade sur l'id nu, None si vide."""
        self.assertEqual(
            emplacement_stock_label(self.co_a, self.empl_a.id),
            'Dépôt principal')
        # Emplacement d'une autre société : non résolu -> dégrade sur l'id nu.
        self.assertEqual(
            emplacement_stock_label(self.co_a, self.empl_b.id),
            f'#{self.empl_b.id}')
        # Id inexistant -> dégrade sur l'id nu.
        self.assertEqual(
            emplacement_stock_label(self.co_a, 999999), '#999999')
        # Pas de lien -> None.
        self.assertIsNone(emplacement_stock_label(self.co_a, None))

    def test_aud729_batch_selector_matches_unitaire(self):
        """AUD729 — la variante BATCH résout EXACTEMENT les mêmes libellés
        que la variante unitaire (même dégradation id nu / autre société),
        pour un lot d'ids en un seul appel groupé."""
        labels = emplacements_stock_labels(
            self.co_a, [self.empl_a.id, self.empl_b.id, 999999])
        self.assertEqual(labels[self.empl_a.id], 'Dépôt principal')
        self.assertEqual(labels[self.empl_b.id], f'#{self.empl_b.id}')
        self.assertEqual(labels[999999], '#999999')
        # Ids vides/None ignorés, aucune requête, dict vide.
        self.assertEqual(emplacements_stock_labels(self.co_a, []), {})
        self.assertEqual(emplacements_stock_labels(self.co_a, [None]), {})


class FlotteVehiculeListeNPlusUnTests(TestCase):
    """AUD729 — N+1 confirmé sur la liste des véhicules : ``modele_ref``
    (str(obj.modele_ref) par ligne) et ``emplacement_stock`` (un lookup DB
    de stock par ligne, jamais batché) étaient résolus un par un."""

    def setUp(self):
        self.co = make_company('flotte-n1', 'Flotte N+1')
        self.admin = make_user(self.co, 'flotte-n1-admin', 'admin')

    def _seed(self, n):
        Vehicule.objects.filter(company=self.co).delete()
        ModeleVehicule.objects.filter(company=self.co).delete()
        EmplacementStock.objects.filter(company=self.co).delete()
        for i in range(n):
            modele = ModeleVehicule.objects.create(
                company=self.co, marque='Renault', modele=f'Modele-{i}')
            emplacement = EmplacementStock.objects.create(
                company=self.co, nom=f'Dépôt {i}')
            Vehicule.objects.create(
                company=self.co, immatriculation=f'N1-{i}', energie='diesel',
                modele_ref=modele, emplacement_stock_id=emplacement.id)

    def test_liste_nombre_de_requetes_constant(self):
        """Le nombre de requêtes SQL de la liste ne doit PAS croître avec le
        nombre de véhicules : avant fix, chaque véhicule ajoutait jusqu'à 2
        requêtes supplémentaires (résolution ``modele_ref`` + emplacement de
        stock, chacune un aller-retour DB séparé, jusqu'à ~100 requêtes en
        plus pour 50 véhicules) — après fix (``select_related`` + batch), le
        nombre de requêtes reste CONSTANT, que la page contienne 3 ou 50
        véhicules aux ``modele_ref``/``emplacement_stock_id`` tous DIFFÉRENTS
        (pas seulement répétés — un simple cache par id ne suffirait pas)."""
        api = auth(self.admin)

        self._seed(3)
        with CaptureQueriesContext(connection) as small:
            resp_small = api.get('/api/django/flotte/vehicules/')
        self.assertEqual(resp_small.status_code, 200, resp_small.data)
        self.assertEqual(len(resp_small.data['results']), 3)

        self._seed(50)
        with CaptureQueriesContext(connection) as big:
            resp_big = api.get('/api/django/flotte/vehicules/')
        self.assertEqual(resp_big.status_code, 200, resp_big.data)
        self.assertEqual(len(resp_big.data['results']), 50)

        self.assertEqual(len(small.captured_queries), len(big.captured_queries))

    def test_labels_corrects_dans_la_reponse(self):
        """Les libellés résolus par lot restent CORRECTS (pas juste rapides)
        — chaque véhicule affiche bien SON propre modèle/emplacement."""
        self._seed(3)
        resp = auth(self.admin).get('/api/django/flotte/vehicules/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['results']
        self.assertEqual(len(rows), 3)
        for i, row in enumerate(sorted(rows, key=lambda r: r['immatriculation'])):
            self.assertEqual(row['modele_ref_label'], f'Renault Modele-{i}')
            self.assertEqual(row['emplacement_stock_label'], f'Dépôt {i}')
