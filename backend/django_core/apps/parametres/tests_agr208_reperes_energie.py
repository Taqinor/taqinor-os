"""AGR208 — les réglages « bonbonne » deviennent des REPÈRES datés et sourcés.

* migration aller-retour sur une société à 55 / 131 (les valeurs du test
  d'anonymisation) : le JSON est créé (source VIDE, relevé 2026-08-20), puis
  le retour restaure les deux colonnes à l'identique ;
* un repère SANS source n'est jamais servi à l'écran ; le repère « non
  subventionné » n'est jamais servi côté client ;
* le profil n'expose plus les deux anciens noms, et aucun lecteur backend ne
  les nomme encore (hors migrations historiques).
"""
import re
from decimal import Decimal
from importlib import import_module
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from . import selectors
from .models import CompanyProfile

User = get_user_model()

MIGRATION = 'apps.parametres.migrations.0113_agr208_reperes_energie_agricole'
ANCIENS = ('agricole_prix_bonbonne', 'agricole_cout_reel_bonbonne')


class _ProfilSimule:
    """Une ligne de profil telle que la voit la migration (colonnes + JSON)."""

    def __init__(self, prix, cout, reperes=None):
        self.agricole_prix_bonbonne = prix
        self.agricole_cout_reel_bonbonne = cout
        self.reperes_energie_agricole = reperes or {}
        self.sauvegardes = []

    def save(self, update_fields=None):
        self.sauvegardes.append(tuple(update_fields or ()))


class _Registre:
    def __init__(self, lignes):
        lignes_ = lignes

        class _QS:
            def iterator(self):
                return iter(lignes_)

        class _Manager:
            def all(self):
                return _QS()

        self._modele = type('CompanyProfile', (), {'objects': _Manager()})

    def get_model(self, app_label, model_name):
        assert (app_label, model_name) == ('parametres', 'CompanyProfile')
        return self._modele


class MigrationAllerRetourTests(SimpleTestCase):
    def test_55_131_vers_json_puis_colonnes_restaurees(self):
        module = import_module(MIGRATION)
        profil = _ProfilSimule(Decimal('55.00'), Decimal('131.00'))
        module.vers_reperes(_Registre([profil]), None)
        self.assertEqual(profil.reperes_energie_agricole, {
            'butane_12kg_detail': {'valeur': 55, 'source': '',
                                   'releve_le': '2026-08-20'},
            'butane_12kg_non_subventionne': {'valeur': 131, 'source': '',
                                             'releve_le': '2026-08-20'},
            'gasoil_litre': {'valeur': None, 'source': '',
                             'releve_le': None},
        })
        # Retour : les colonnes sont restaurées à l'identique.
        profil.agricole_prix_bonbonne = None
        profil.agricole_cout_reel_bonbonne = None
        module.vers_colonnes(_Registre([profil]), None)
        self.assertEqual(profil.agricole_prix_bonbonne, Decimal('55.00'))
        self.assertEqual(profil.agricole_cout_reel_bonbonne,
                         Decimal('131.00'))

    def test_valeur_decimale_conservee(self):
        module = import_module(MIGRATION)
        profil = _ProfilSimule(Decimal('52.50'), Decimal('128.00'))
        module.vers_reperes(_Registre([profil]), None)
        self.assertEqual(
            profil.reperes_energie_agricole['butane_12kg_detail']['valeur'],
            52.5)
        module.vers_colonnes(_Registre([profil]), None)
        self.assertEqual(profil.agricole_prix_bonbonne, Decimal('52.5'))

    def test_repere_deja_saisi_jamais_ecrase(self):
        module = import_module(MIGRATION)
        saisi = {'butane_12kg_detail': {'valeur': 60, 'source': 'Relevé',
                                        'releve_le': '2026-09-30'}}
        profil = _ProfilSimule(Decimal('50'), Decimal('128'), dict(saisi))
        module.vers_reperes(_Registre([profil]), None)
        self.assertEqual(profil.reperes_energie_agricole['butane_12kg_detail'],
                         saisi['butane_12kg_detail'])

    def test_operations_et_reversibilite(self):
        module = import_module(MIGRATION)
        for op in module.Migration.operations:
            self.assertTrue(op.reversible, op)

    def test_plus_aucun_lecteur_backend_des_anciens_noms(self):
        racine = Path(__file__).resolve().parents[2]  # backend/django_core
        motif = re.compile('|'.join(ANCIENS))
        fautifs = []
        for chemin in racine.rglob('*.py'):
            rel = chemin.relative_to(racine).as_posix()
            if '/migrations/' in rel or rel.endswith(
                    'tests_agr208_reperes_energie.py'):
                continue
            if motif.search(chemin.read_text(encoding='utf-8',
                                             errors='ignore')):
                fautifs.append(rel)
        self.assertEqual(fautifs, [])


class ReperesServisTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='agr208-co', defaults={'nom': 'AGR208 Co'})[0]
        self.profil = CompanyProfile.get(company=self.company)

    def _poser(self, reperes):
        CompanyProfile.objects.filter(pk=self.profil.pk).update(
            reperes_energie_agricole=reperes)

    def test_repere_sans_source_non_servi(self):
        self._poser({
            'butane_12kg_detail': {'valeur': 50, 'source': '',
                                   'releve_le': '2026-08-20'},
            'gasoil_litre': {'valeur': 11.2, 'source': 'Relevé station',
                             'releve_le': '2026-10-01'},
        })
        self.assertEqual(selectors.reperes_energie_agricole_affiches(
            self.company), [{'cle': 'gasoil_litre', 'valeur': 11.2,
                             'source': 'Relevé station',
                             'releve_le': '2026-10-01'}])

    def test_non_subventionne_jamais_servi_cote_client(self):
        self._poser({
            'butane_12kg_non_subventionne': {
                'valeur': 128, 'source': 'Note interne',
                'releve_le': '2026-08-20'},
        })
        self.assertEqual(
            selectors.reperes_energie_agricole_affiches(self.company), [])
        self.assertEqual(
            selectors.repere_butane_non_subventionne_interne(
                self.company)['valeur'], 128)

    def test_vierge_rien_servi(self):
        self._poser({})
        self.assertEqual(
            selectors.reperes_energie_agricole_affiches(self.company), [])
        self.assertIsNone(
            selectors.repere_butane_non_subventionne_interne(self.company))


class ApiReperesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='agr208-api', defaults={'nom': 'AGR208 Api'})[0]
        admin = User.objects.create_user(
            username='agr208_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')

    def test_anciens_noms_absents_du_profil(self):
        data = self.api.get('/api/django/parametres/').data
        for nom in ANCIENS:
            self.assertNotIn(nom, data)
        self.assertIn('reperes_energie_agricole', data)

    def test_patch_vider_un_repere_reste_vide(self):
        corps = {'reperes_energie_agricole': {
            'butane_12kg_detail': {'valeur': None, 'source': '',
                                   'releve_le': None},
            'gasoil_litre': {'valeur': '11.50', 'source': 'Relevé station',
                             'releve_le': '2026-10-01'}}}
        resp = self.api.patch('/api/django/parametres/update/', corps,
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        reperes = resp.data['reperes_energie_agricole']
        self.assertIsNone(reperes['butane_12kg_detail']['valeur'])
        self.assertEqual(reperes['gasoil_litre']['valeur'], 11.5)
        # Enregistrer → rouvrir → enregistrer sans toucher = identique.
        resp2 = self.api.patch('/api/django/parametres/update/',
                               {'reperes_energie_agricole': reperes},
                               format='json')
        self.assertEqual(resp2.data['reperes_energie_agricole'], reperes)

    def test_repere_hors_forme_refuse(self):
        for faute in ({'kerosene': {'valeur': 9}},
                      {'gasoil_litre': {'valeur': -1}},
                      {'gasoil_litre': {'valeur': 11, 'releve_le': '1/10'}}):
            resp = self.api.patch(
                '/api/django/parametres/update/',
                {'reperes_energie_agricole': faute}, format='json')
            self.assertEqual(resp.status_code, 400, faute)
            self.assertIn('reperes_energie_agricole', resp.data)
