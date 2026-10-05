"""AGR100 — champs structurés pompage sur ``Produit`` + vocabulaire
``ROLES_POMPAGE`` (distinct de ``ROLES_DEVIS``).

Contrat partagé : ``contract_samples/produit_pompage.json``.
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import Produit
from authentication.models import Company
from core import product_roles

User = get_user_model()

URL_PRODUITS = '/api/django/stock/produits/'
CONTRAT = json.loads(
    (Path(__file__).parent / 'contract_samples' / 'produit_pompage.json')
    .read_text(encoding='utf-8'))


def api_for(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class AGR100Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='agr100-co', defaults={'nom': 'AGR100 Co'})[0]
        cls.roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            cls.roles[nom] = Role.objects.create(
                company=cls.company, nom=nom, permissions=list(perms),
                est_systeme=True)
        cls.user = User.objects.create_user(
            username='agr100_dir', password='x', company=cls.company,
            role=cls.roles['Directeur'])


class TestVocabulaire(SimpleTestCase):
    def test_roles_pompage_egal_au_contrat(self):
        self.assertEqual(
            list(product_roles.ROLES_POMPAGE), list(CONTRAT['roles_pompage']))
        self.assertEqual(
            product_roles.LIBELLES_ROLES_POMPAGE, CONTRAT['roles_pompage'])

    def test_choix_des_champs_egaux_au_contrat(self):
        champs = CONTRAT['champs_produit']
        self.assertEqual(
            list(product_roles.TYPES_POMPE), champs['type_pompe']['choix'])
        self.assertEqual(
            list(product_roles.ALIMENTATIONS_POMPAGE),
            champs['alimentation']['choix'])

    def test_famille_vers_role_inchange_et_exhaustif(self):
        from apps.stock.models import Categorie
        self.assertEqual(
            set(product_roles.FAMILLE_VERS_ROLE),
            {v for v, _ in Categorie.TypeEquipement.choices})
        # pompe / variateur : toujours PAS DE RÔLE DE DEVIS (arbitrage respecté)
        self.assertIsNone(product_roles.FAMILLE_VERS_ROLE['pompe'])
        self.assertIsNone(product_roles.FAMILLE_VERS_ROLE['variateur'])
        self.assertNotIn('pompe', product_roles.ROLES_DEVIS)


class TestSaisieEtLecture(AGR100Base):
    def test_pompe_sans_mot_immerg_servie_avec_ses_valeurs_declarees(self):
        payload = {
            'nom': 'Électropompe submersible 4 pouces',
            'prix_vente': '5000',
            'role_pompage': 'pompe',
            'type_pompe': 'immergee',
            'alimentation': 'mono',
            'courbe_frequence_hz': 50,
            'courbe_source': {
                'document': 'Fiche OSP 30', 'date': '2026-01-15', 'page': 4},
        }
        client = api_for(self.user)
        r = client.post(URL_PRODUITS, payload, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = client.get(f'{URL_PRODUITS}{r.data["id"]}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['role_pompage'], 'pompe')
        self.assertEqual(r.data['type_pompe'], 'immergee')
        self.assertEqual(r.data['alimentation'], 'mono')
        self.assertEqual(r.data['courbe_frequence_hz'], 50)
        self.assertEqual(
            r.data['courbe_source'],
            {'document': 'Fiche OSP 30', 'date': '2026-01-15', 'page': 4})

    def test_cles_du_detail_couvrent_le_contrat(self):
        p = Produit.objects.create(
            company=self.company, nom='Produit contrat', prix_vente=1)
        r = api_for(self.user).get(f'{URL_PRODUITS}{p.pk}/')
        self.assertEqual(r.status_code, 200)
        for cle in CONTRAT['champs_produit']:
            self.assertIn(cle, r.data)
        # produit sans rien de saisi : vide = « non publié », jamais 0
        self.assertEqual(r.data['role_pompage'], '')
        self.assertIsNone(r.data['courbe_frequence_hz'])
        self.assertEqual(
            r.data['courbe_source'],
            {'document': '', 'date': None, 'page': None})

    def test_role_hors_vocabulaire_400_nomme_le_champ(self):
        r = api_for(self.user).post(URL_PRODUITS, {
            'nom': 'Pompe invalide', 'prix_vente': '1',
            'role_pompage': 'turbine'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('role_pompage', r.data)

    def test_type_et_alimentation_hors_vocabulaire_400(self):
        r = api_for(self.user).post(URL_PRODUITS, {
            'nom': 'Pompe invalide 2', 'prix_vente': '1',
            'type_pompe': 'flottante', 'alimentation': 'quadri'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('type_pompe', r.data)
        self.assertIn('alimentation', r.data)

    def test_role_devis_non_touche(self):
        r = api_for(self.user).post(URL_PRODUITS, {
            'nom': 'Pompe sans rôle devis', 'prix_vente': '1',
            'role_pompage': 'pompe'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['role_devis'])

    def test_enregistrer_rouvrir_enregistrer_est_identique(self):
        client = api_for(self.user)
        r = client.post(URL_PRODUITS, {
            'nom': 'Pompe aller-retour', 'prix_vente': '100',
            'role_pompage': 'pompe', 'type_pompe': 'surface',
            'alimentation': 'tri',
            'courbe_source': {'document': 'Doc', 'date': None, 'page': 2},
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        url = f'{URL_PRODUITS}{r.data["id"]}/'
        avant = client.get(url).data
        champs = ('role_pompage', 'type_pompe', 'alimentation',
                  'courbe_source', 'courbe_frequence_hz')
        r = client.patch(url, {c: avant[c] for c in champs}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        apres = client.get(url).data
        for c in champs:
            self.assertEqual(avant[c], apres[c], c)

    def test_pas_de_fuite_entre_societes(self):
        autre = Company.objects.create(slug='agr100-autre', nom='Autre')
        Produit.objects.create(
            company=autre, nom='Pompe autre société', prix_vente=1,
            role_pompage='pompe')
        r = api_for(self.user).get(URL_PRODUITS)
        self.assertEqual(r.status_code, 200)
        data = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertNotIn('Pompe autre société', [p['nom'] for p in data])
