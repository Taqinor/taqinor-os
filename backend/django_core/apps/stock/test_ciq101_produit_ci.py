"""CIQ101 — champs C&I sur ``Produit`` (``role_ci``, ``type_pose``,
``delai_appro_jours``) et fiches limiteur / logger / protection / câble /
structure + champs onduleur ajoutés.

Contrat partagé : ``contract_samples/produit_ci.json``. Vide = « non publié »,
jamais une valeur par défaut.
"""
import json
from importlib import import_module
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations import AddField, AlterField
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import Categorie, FicheTechnique, Produit
from authentication.models import Company
from core import product_roles

User = get_user_model()

URL_PRODUITS = '/api/django/stock/produits/'
URL_FICHES = '/api/django/stock/fiches-techniques/'
CONTRAT = json.loads(
    (Path(__file__).parent / 'contract_samples' / 'produit_ci.json')
    .read_text(encoding='utf-8'))
MIGRATION = '0163_ciq101_produit_ci'


def api_for(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


def _champs_fiches_ci():
    champs = []
    for nom, bloc in CONTRAT['fiches'].items():
        champs.extend(bloc['champs'])
    return champs


class CIQ101Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='ciq101-co', defaults={'nom': 'CIQ101 Co'})[0]
        roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            roles[nom] = Role.objects.create(
                company=cls.company, nom=nom, permissions=list(perms),
                est_systeme=True)
        cls.user = User.objects.create_user(
            username='ciq101_dir', password='x', company=cls.company,
            role=roles['Directeur'])


class TestVocabulaire(SimpleTestCase):
    def test_roles_ci_egaux_au_contrat(self):
        self.assertEqual(
            list(product_roles.ROLES_CI), list(CONTRAT['roles_ci']))
        self.assertEqual(product_roles.LIBELLES_ROLES_CI, CONTRAT['roles_ci'])

    def test_types_pose_egaux_au_contrat(self):
        self.assertEqual(
            list(product_roles.TYPES_POSE),
            CONTRAT['champs_produit']['type_pose']['choix'])

    def test_roles_ci_distincts_et_roles_devis_inchanges(self):
        # aucun rôle résidentiel ajouté : vocabulaire séparé
        self.assertNotIn('onduleur_string_tri', product_roles.ROLES_DEVIS)
        self.assertEqual(product_roles.ROLES_DEVIS[0], 'onduleur_reseau')

    def test_famille_vers_role_exhaustif_sans_modification(self):
        self.assertEqual(
            set(product_roles.FAMILLE_VERS_ROLE),
            {v for v, _ in Categorie.TypeEquipement.choices})
        self.assertIsNone(product_roles.FAMILLE_VERS_ROLE['compteur'])
        self.assertIsNone(product_roles.FAMILLE_VERS_ROLE['protection'])

    def test_types_fiche_ajoutes_et_anciens_conserves(self):
        valeurs = [c[0] for c in FicheTechnique.TypeFiche.choices]
        for v in ('module', 'onduleur', 'batterie', 'optimiseur', 'pompe',
                  'variateur_pompage', 'autre', 'limiteur', 'logger',
                  'protection', 'cable', 'structure'):
            self.assertIn(v, valeurs)

    def test_cles_des_fiches_du_contrat_sur_le_serializeur(self):
        from apps.stock.serializers_fiche_technique import FicheTechniqueSerializer
        champs = set(FicheTechniqueSerializer().fields)
        for cle in _champs_fiches_ci():
            self.assertIn(cle, champs)
        for cle in CONTRAT['fiches']['onduleur'][
                'champs_onduleur_existants']:
            self.assertIn(cle, champs)

    def test_pvond_non_etendu(self):
        """Les cinq champs onduleur ajoutés n'entrent PAS dans le verrou."""
        from apps.stock.selectors import CLES_CONTRAT_ONDULEUR
        for cle in CONTRAT['fiches']['onduleur']['champs']:
            self.assertNotIn(cle.removeprefix('ond_'), CLES_CONTRAT_ONDULEUR)
        self.assertEqual(len(CLES_CONTRAT_ONDULEUR), 10)


class TestMigration(SimpleTestCase):
    def test_operations_additives_et_reversibles(self):
        module = import_module(f'apps.stock.migrations.{MIGRATION}')
        ops = module.Migration.operations
        for op in ops:
            self.assertIsInstance(op, (AddField, AlterField))
            self.assertTrue(op.reversible)
        ajoutes = {op.name for op in ops if isinstance(op, AddField)}
        for cle in ('role_ci', 'type_pose', 'delai_appro_jours'):
            self.assertIn(cle, ajoutes)
        for cle in _champs_fiches_ci():
            self.assertIn(cle, ajoutes)

    def test_aller_retour_des_etats(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        apres = loader.project_state(('stock', MIGRATION)).apps
        avant = loader.project_state(
            ('stock', '0162_agr104_roles_pompage')).apps
        noms_apres = {f.name for f in apres.get_model(
            'stock', 'Produit')._meta.get_fields()}
        noms_avant = {f.name for f in avant.get_model(
            'stock', 'Produit')._meta.get_fields()}
        self.assertIn('role_ci', noms_apres)
        self.assertNotIn('role_ci', noms_avant)
        fiche_avant = {f.name for f in avant.get_model(
            'stock', 'FicheTechnique')._meta.get_fields()}
        for cle in _champs_fiches_ci():
            self.assertNotIn(cle, fiche_avant)


class TestSaisieEtLecture(CIQ101Base):
    def test_compteur_tc_declare_servi_tel_quel(self):
        client = api_for(self.user)
        r = client.post(URL_PRODUITS, {
            'nom': 'Compteur triphasé à TC 250 A', 'prix_vente': '3000',
            'role_ci': 'compteur_injection'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        pid = r.data['id']
        r = client.post(URL_FICHES, {
            'produit': pid, 'type_fiche': 'limiteur',
            'lim_mode': 'compteur_tc', 'lim_phases': 3}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        fiche = client.get(f'{URL_FICHES}{r.data["id"]}/').data
        self.assertEqual(fiche['lim_mode'], 'compteur_tc')
        self.assertIsNone(fiche['lim_onduleurs_max'])  # non publié
        self.assertEqual(fiche['lim_marques'], [])
        self.assertIsNone(fiche['lim_i_max_a'])
        produit = client.get(f'{URL_PRODUITS}{pid}/').data
        self.assertEqual(produit['role_ci'], 'compteur_injection')
        self.assertIsNone(produit['role_devis'])  # role_devis non touché

    def test_role_ci_hors_vocabulaire_400_nomme_le_champ(self):
        r = api_for(self.user).post(URL_PRODUITS, {
            'nom': 'Produit invalide', 'prix_vente': '1',
            'role_ci': 'turbine'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('role_ci', r.data)

    def test_type_pose_bac_acier_accepte_et_inconnu_refuse(self):
        client = api_for(self.user)
        r = client.post(URL_PRODUITS, {
            'nom': 'Structure bac acier', 'prix_vente': '1',
            'role_ci': 'structure_ci', 'type_pose': 'bac_acier'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['type_pose'], 'bac_acier')
        r = client.post(URL_PRODUITS, {
            'nom': 'Structure x', 'prix_vente': '1', 'type_pose': 'vitre'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('type_pose', r.data)

    def test_produit_sans_saisie_vide_non_publie(self):
        p = Produit.objects.create(
            company=self.company, nom='Produit vide', prix_vente=1)
        r = api_for(self.user).get(f'{URL_PRODUITS}{p.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['role_ci'], '')
        self.assertEqual(r.data['type_pose'], '')
        self.assertIsNone(r.data['delai_appro_jours'])

    def test_masse_sans_notice_refusee(self):
        p = Produit.objects.create(
            company=self.company, nom='Structure lestée', prix_vente=1)
        client = api_for(self.user)
        r = client.post(URL_FICHES, {
            'produit': p.pk, 'type_fiche': 'structure',
            'struct_type_pose': 'toit_plat_leste',
            'struct_masse_kg_m2': 12}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('struct_notice', r.data)
        r = client.post(URL_FICHES, {
            'produit': p.pk, 'type_fiche': 'structure',
            'struct_type_pose': 'toit_plat_leste', 'struct_masse_kg_m2': 12,
            'struct_notice': {'document': 'Notice X', 'date': '2026-01-02',
                              'page': 3}}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['struct_notice'], {
            'document': 'Notice X', 'date': '2026-01-02', 'page': 3})

    def test_options_servent_les_libelles_fr_des_roles(self):
        """CIQ104 — l'écran lit les libellés par OPTIONS (aucun miroir JS)."""
        r = api_for(self.user).options(URL_PRODUITS)
        self.assertEqual(r.status_code, 200)
        choix = {c['value']: c['display_name']
                 for c in r.data['actions']['POST']['role_ci']['choices']}
        self.assertEqual(choix, CONTRAT['roles_ci'])

    def test_etat_ci_servi_et_sans_prix_achat(self):
        """CIQ104 — ``etat_ci`` (filtre « C&I à compléter »)."""
        p = Produit.objects.create(
            company=self.company, nom='Structure bac acier', prix_vente=0,
            role_ci='structure_ci', type_pose='bac_acier')
        r = api_for(self.user).get(f'{URL_PRODUITS}{p.pk}/')
        self.assertEqual(r.data['etat_ci']['role_ci'], 'structure_ci')
        self.assertFalse(r.data['etat_ci']['prix_connu'])
        self.assertTrue(r.data['etat_ci']['eligible_ci'])
        self.assertNotIn('prix_achat', r.data['etat_ci'])
        autre = Produit.objects.create(
            company=self.company, nom='Article quelconque', prix_vente=1)
        r = api_for(self.user).get(f'{URL_PRODUITS}{autre.pk}/')
        self.assertIsNone(r.data['etat_ci'])

    def test_enregistrer_rouvrir_enregistrer_identique(self):
        client = api_for(self.user)
        r = client.post(URL_PRODUITS, {
            'nom': 'Disjoncteur AC 125 A', 'prix_vente': '900',
            'role_ci': 'protection_ac', 'delai_appro_jours': 21},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        url_p = f'{URL_PRODUITS}{r.data["id"]}/'
        r = client.post(URL_FICHES, {
            'produit': r.data['id'], 'type_fiche': 'protection',
            'prot_type': 'disjoncteur', 'prot_cote': 'ac',
            'prot_calibre_a': 125, 'prot_poles': 4}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        url_f = f'{URL_FICHES}{r.data["id"]}/'
        avant_p = client.get(url_p).data
        avant_f = client.get(url_f).data
        champs_p = ('role_ci', 'type_pose', 'delai_appro_jours')
        r = client.patch(url_p, {c: avant_p[c] for c in champs_p},
                         format='json')
        self.assertEqual(r.status_code, 200, r.data)
        champs_f = _champs_fiches_ci()
        r = client.patch(url_f, {c: avant_f[c] for c in champs_f},
                         format='json')
        self.assertEqual(r.status_code, 200, r.data)
        apres_p = client.get(url_p).data
        apres_f = client.get(url_f).data
        for c in champs_p:
            self.assertEqual(avant_p[c], apres_p[c], c)
        for c in champs_f:
            self.assertEqual(avant_f[c], apres_f[c], c)
